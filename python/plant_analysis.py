"""
Plant analysis – v5-dupGuard (forced plant_name = "Cucumber")
------------------------------------------------------------
Always plant_name="Cucumber", id=999
Skip if the image + timestamp has already been processed
"""

from __future__ import annotations
import threading
import os, json, ssl, time, boto3, paho.mqtt.client as mqtt
from datetime import datetime
from pathlib import Path
import numpy as np
from dotenv import load_dotenv
from tensorflow.keras.preprocessing import image as keras_image
import tensorflow as tf, tensorflow_datasets as tfds
import contour  # surface detection + overlay

# ───────────────────────────── Setup ─────────────────────────────
_LOCK = threading.Lock()
_ALREADY_PROCESSED = set()
load_dotenv()

FORCED_PLANT_NAME = "Cucumber"
FORCED_ID         = 999

MODEL_S3_KEY = "plant_village_CNN.h5"
LOCAL_MODEL  = "plant_village_CNN.h5"
LOCAL_JSON   = "plant_data.json"
JSON_S3_KEY  = "plant_data.json"

s3 = boto3.client(
    "s3",
    aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name           = os.getenv("AWS_REGION"),
)
BUCKET = os.getenv("AWS_BUCKET_NAME")

# ───────────────────────── Model load ────────────────────────────
model = tf.keras.models.load_model(LOCAL_MODEL)
ds_info = tfds.builder("plant_village").info
class_names = ds_info.features["label"].names

# ───────────────────────── MQTT helper ───────────────────────────
HOST = "33ea71e0e0034036b86bee133525b810.s1.eu.hivemq.cloud"
PORT = 8883
USERNAME = "SmartGreenHouse"
PASSWORD = "SmartGreenHouse2025"

def _publish_mqtt(payload: dict):
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

# ───────────────────────── JSON helpers ──────────────────────────
def _download_json():
    """Downloads the S3 version and returns it (dict)."""
    try:
        s3.download_file(BUCKET, JSON_S3_KEY, LOCAL_JSON)
        with open(LOCAL_JSON) as f:
            return json.load(f)
    except Exception:
        return {}

def _load_hist_local_first():
    """Returns history: first local file, otherwise S3."""
    if Path(LOCAL_JSON).exists():
        try:
            with open(LOCAL_JSON) as f:
                return json.load(f)
        except Exception:
            pass
    return _download_json()

def _save_history_atomic(plant: str, record: dict):
    hist = _load_hist_local_first()

    # déjà présent ?
    if any(e.get("s3_ident") == record["s3_ident"] for e in hist.get(plant, [])):
        return

    _insert_sorted(hist.setdefault(plant, []), record)

    with open(LOCAL_JSON, "w") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)
    s3.upload_file(LOCAL_JSON, BUCKET, JSON_S3_KEY)
# ──────────────────── Public entry point ─────────────────────────
def analyse_one_s3_key(key: str, *, last_modified=None, crop=contour.DEFAULT_CROP):
    """Parse key; skip if already processed (ident = key@LastModified)."""
    ident = f"{key}@{(last_modified.isoformat() if last_modified else 'NA')}"

    # -- double-check
    with _LOCK:
        if ident in _ALREADY_PROCESSED:
            return {"skipped": ident}
        _ALREADY_PROCESSED.add(ident)
        # -- double-check sur disque
        data = _load_hist_local_first()
        if any(e.get("s3_ident") == ident for e in data.get(FORCED_PLANT_NAME, [])):
            return {"skipped": ident}

    # -- image download
    fname = os.path.basename(key)
    s3.download_file(BUCKET, key, fname)

    # -- green area
    surface = contour.process_and_save(fname, crop=crop)
    area_px = surface["area_px"]

    # -- CNN (ignored species, conserved disease)
    disease_class, _ = classify_image(fname)

    # -- growth vs previous value
    prev_px = None
    if data.get(FORCED_PLANT_NAME):
        current_ts = last_modified.strftime("%Y-%m-%d %H:%M:%S")
        # iter upside down in sorted list
        for e in reversed(data[FORCED_PLANT_NAME]):
            if e["date"] < current_ts:  # strictly before
                prev_px = e["size_compare"]["current_day_px"]
                break

    growth = 0 if prev_px is None else area_px - prev_px

    record = {
        "date"           : last_modified.strftime("%Y-%m-%d %H:%M:%S"),
        "file_name_image": key,
        "s3_ident"       : ident,
        "disease_class"  : disease_class,
        "size_compare"   : {"current_day_px": area_px, "growth": growth},
    }

    _save_history_atomic(FORCED_PLANT_NAME, record)
    _publish_mqtt({"plant_name": FORCED_PLANT_NAME, **record})
    return record

# ───────────────────────── internal utilities─────────────────────────
def classify_image(image_path: str):
    img   = keras_image.load_img(image_path, target_size=(128, 128))
    arr   = keras_image.img_to_array(img)[None] / 255.0
    preds = model.predict(arr, verbose=0)
    idx   = int(np.argmax(preds, axis=1)[0])
    return {"id": FORCED_ID, "name": class_names[idx]}, class_names[idx].split("___")[0]

# ───────────────────────── Front helper ──────────────────────────
def get_growth_series(plant_name: str | None = None, limit: int = 30):
    plant_name = plant_name or FORCED_PLANT_NAME
    hist = _load_hist_local_first()
    if plant_name not in hist:
        return []
    entries = sorted(hist[plant_name], key=lambda e: e["date"])[-limit:]
    out, prev = [], None
    for e in entries:
        cur = e["size_compare"]["current_day_px"]
        out.append(
            {
                "timestamp": e["date"],
                "current_px": cur,
                "growth_px": 0 if prev is None else cur - prev,
            }
        )
        prev = cur
    return out

def _insert_sorted(hist_list: list, record: dict):
    """Add the record and keep the list sorted on the 'date' field."""
    hist_list.append(record)
    hist_list.sort(key=lambda e: e["date"])      # chronological order