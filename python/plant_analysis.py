"""
Plant analysis – v5-dupGuard (forced plant_name = "Cucumber")
------------------------------------------------------------
Always plant_name = "Cucumber", id = 999
Skips image if its S3 key + timestamp has already been processed.
"""

from __future__ import annotations
import re
import threading
import os, json, ssl, time, boto3, paho.mqtt.client as mqtt
from datetime import datetime
from pathlib import Path
import numpy as np
from dotenv import load_dotenv
from tensorflow.keras.preprocessing import image as keras_image
import tensorflow as tf, tensorflow_datasets as tfds
import contour  # surface detection + overlay drawing

# ─────────────── Setup (env, model, S3, MQTT, etc.) ───────────────
_LOCK = threading.Lock()
_ALREADY_PROCESSED = set()
load_dotenv()

FORCED_PLANT_NAME = "Cucumber"
FORCED_ID         = 999

MODEL_S3_KEY = "plant_village_CNN.h5"
LOCAL_MODEL  = "plant_village_CNN.h5"
LOCAL_JSON   = "plant_data.json"
JSON_S3_KEY  = "plant_data.json"

# AWS S3 setup
s3 = boto3.client(
    "s3",
    aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name           = os.getenv("AWS_REGION"),
)
BUCKET = os.getenv("AWS_BUCKET_NAME")

# Load CNN model and class names from PlantVillage dataset
model = tf.keras.models.load_model(LOCAL_MODEL)
ds_info = tfds.builder("plant_village").info
class_names = ds_info.features["label"].names

# MQTT broker credentials
HOST = "smartgreen-884cb6eb.a03.euc1.aws.hivemq.cloud"
PORT = 8883
USERNAME = "SmartGreenHouse"
PASSWORD = "SmartGreenHouse2025"

def _publish_mqtt(payload: dict):
    """Send the final result via MQTT to the frontend or any subscriber."""
    try:
        client = mqtt.Client(protocol=mqtt.MQTTv311)
        client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        client.username_pw_set(USERNAME, PASSWORD)
        client.connect(HOST, PORT)
        client.loop_start(); time.sleep(2)
        client.publish("test/plant_growth", json.dumps(payload), qos=1, retain=True)
        client.loop_stop(); client.disconnect()
    except Exception as e:
        print(f"[MQTT] {e}")

# ─────────────── JSON handling: local + S3 fallback ───────────────
def _download_json():
    """Try downloading JSON from S3. If it fails, return empty dict."""
    try:
        s3.download_file(BUCKET, JSON_S3_KEY, LOCAL_JSON)
        with open(LOCAL_JSON) as f:
            return json.load(f)
    except Exception:
        return {}

def _load_hist_local_first():
    """Use local JSON file if available and valid, otherwise fetch from S3."""
    if Path(LOCAL_JSON).exists():
        try:
            with open(LOCAL_JSON) as f:
                return json.load(f)
        except Exception:
            pass
    return _download_json()

# ─────────────── Save new image record + growth calculations ───────────────
def _save_history_atomic(plant: str, record: dict):
    hist = _load_hist_local_first()
    if plant not in hist:
        hist[plant] = []

    # 1. Check if already saved
    for blk in hist[plant]:
        if any(img["file_name_image"] == record["file_name_image"] for img in blk["images"]):
            return

    # 2. Parse file name to get group id and side number (1 or 2)
    stem = Path(record["file_name_image"]).stem
    m = re.match(r"^(\d+)_([12])_(.+)", stem)
    if not m:
        return
    group_id, suffix = m.group(1), m.group(2)

    # 3. Use a memory-based pending cache to wait for both sides (1 and 2)
    pending = getattr(_save_history_atomic, "_pending", {})
    _save_history_atomic._pending = pending

    # Remove stale entry if two consecutive "1" images with no "2"
    if suffix == "1":
        def _get_suffix(fname):
            mm = re.match(r"(.+)_([12])(?:_[^_]*)?$", Path(fname).stem)
            return mm.group(2) if mm else None
        orphan_1 = [gid for gid, imgs in pending.items()
                    if len(imgs) == 1 and _get_suffix(imgs[0]["file_name_image"]) == "1"]
        for gid in orphan_1:
            del pending[gid]

    pending.setdefault(group_id, []).append(record)

    # 4. If we only have one side, wait
    if len(pending[group_id]) < 2:
        return

    # 5. We have both sides. Sort and remove from pending.
    images = sorted(pending[group_id], key=lambda r: r["file_name_image"])
    del pending[group_id]

    # 6. Compute global surface and compare with last block
    global_current_px = sum(img["current_day_px"] for img in images)
    previous_block = hist[plant][-1] if hist[plant] else None
    previous_global_px = previous_block["global_current_px"] if previous_block else None
    difference_global_growth = 0 if previous_global_px is None else global_current_px - previous_global_px
    difference_global_growth_pct = (
        0.0 if previous_global_px in (None, 0)
        else round(100 * difference_global_growth / previous_global_px, 2)
    )

    # 7. Individual image growth comparison based on suffix (1 vs 1, 2 vs 2)
    for img in images:
        suffix_cur = Path(img["file_name_image"]).stem.split("_")[1]
        prev_px = None
        for blk in reversed(hist[plant]):
            for past in blk["images"]:
                suffix_past = Path(past["file_name_image"]).stem.split("_")[1]
                if suffix_past == suffix_cur:
                    prev_px = past["current_day_px"]
                    break
            if prev_px is not None:
                break
        growth = 0 if prev_px is None else img["current_day_px"] - prev_px
        pct = 0.0 if prev_px in (None, 0) else round(100 * growth / prev_px, 2)
        img["growth"] = growth
        img["growth_pourcentage"] = pct

    # 8. Save canonical block to file and push to S3
    block = {
        "global_current_px": global_current_px,
        "difference_global_growth": difference_global_growth,
        "difference_global_growth_pct": difference_global_growth_pct,
        "id": FORCED_ID,
        "disease_class": images[0]["disease_class"],
        "images": images
    }

    hist[plant].append(block)
    with open(LOCAL_JSON, "w") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)
    s3.upload_file(LOCAL_JSON, BUCKET, JSON_S3_KEY)

    # 9. Prepare MQTT version of the block (renamed image keys)
    payload_images = []
    for idx, img in enumerate(images, start=1):
        tmp = img.copy()
        tmp[f"file_name_image{idx}"] = tmp.pop("file_name_image")
        payload_images.append(tmp)

    mqtt_block = {**block, "images": payload_images}

    _publish_mqtt({
        "plant_name": plant,
        **mqtt_block
    })

# ─────────────── Entry point to analyze a single S3 image ───────────────
IMG_DIR = Path(__file__).parent / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)

def analyse_one_s3_key(key: str, *, last_modified=None, crop=contour.DEFAULT_CROP):
    ident = f"{key}@{(last_modified.isoformat() if last_modified else 'NA')}"

    with _LOCK:
        if ident in _ALREADY_PROCESSED:
            return {"skipped": ident}
        _ALREADY_PROCESSED.add(ident)

    fname       = Path(key).name
    local_path  = IMG_DIR / fname
    s3.download_file(BUCKET, key, str(local_path))

    surface = contour.process_and_save(str(local_path), crop=crop)
    area_px = surface["area_px"]

    disease_class, _ = classify_image(str(local_path))

    record = {
        "date": last_modified.strftime("%Y-%m-%d %H:%M:%S"),
        "file_name_image": key,
        "s3_ident": ident,
        "current_day_px": area_px,
        "disease_class": disease_class
    }

    _save_history_atomic(FORCED_PLANT_NAME, record)
    return record

# ─────────────── Image classifier using CNN ───────────────
def classify_image(image_path: str):
    img   = keras_image.load_img(image_path, target_size=(128, 128))
    arr   = keras_image.img_to_array(img)[None] / 255.0
    preds = model.predict(arr, verbose=0)
    idx   = int(np.argmax(preds, axis=1)[0])
    return {"id": FORCED_ID, "name": class_names[idx]}, class_names[idx].split("___")[0]

# ─────────────── Growth chart frontend API ───────────────
def get_growth_series(plant_name: str | None = None, limit: int = 30):
    plant_name = plant_name or FORCED_PLANT_NAME
    hist = _load_hist_local_first()

    if plant_name not in hist:
        return []

    # Keep only the most recent entries
    entries = hist[plant_name][-limit:]

    # Return summary: timestamp + surface + delta
    out = []
    for block in entries:
        first_img = block["images"][0]
        out.append({
            "timestamp": first_img["date"],
            "global_px": block["global_current_px"],
            "difference_growth": block["difference_global_growth"]
        })
    return out

# ─────────────── Utility to insert sorted record ───────────────
def _insert_sorted(hist_list: list, record: dict):
    """Insert the record into the list and sort by 'date'."""
    hist_list.append(record)
    hist_list.sort(key=lambda e: e["date"])