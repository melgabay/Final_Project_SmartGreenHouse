"""
Plant analysis – v5-dupGuard (forced plant_name = "Cucumber")
------------------------------------------------------------
Always plant_name="Cucumber", id=999
Skip if the image + timestamp has already been processed
"""
from __future__ import annotations
import re   # ⇦ place cet import en haut de plant_analysis.py s’il n’existe pas
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
HOST = "smartgreen-884cb6eb.a03.euc1.aws.hivemq.cloud"
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
    if plant not in hist:
        hist[plant] = []

    # 0️⃣ – déjà enregistré ? ───────────────────────────────────────────
    for blk in hist[plant]:
        if any(img["file_name_image"] == record["file_name_image"] for img in blk["images"]):
            return                      # déjà dans le JSON

    # 1️⃣ – analyse stricte du nom de fichier *_1_* ou *_2_* ────────────
    stem = Path(record["file_name_image"]).stem            # ex. "347_1_2025-07-02"
    m = re.match(r"^(\d+)_([12])_(.+)", stem)
    if not m:
        return  # nom hors format ==> on ignore
    group_id, suffix = m.group(1), m.group(2)              # "347", "1" ou "2"

    # 2️⃣ – cache en mémoire des paires en attente ─────────────────────
    pending = getattr(_save_history_atomic, "_pending", {})
    _save_history_atomic._pending = pending                # persiste entre appels

    # si on reçoit un nouveau *_1 alors qu’un autre *_1 est orphelin → on garde le + récent
    if suffix == "1":
        def _get_suffix(fname):
            mm = re.match(r"(.+)_([12])(?:_[^_]*)?$", Path(fname).stem)
            return mm.group(2) if mm else None
        orphan_1 = [gid for gid, imgs in pending.items()
                    if len(imgs) == 1 and _get_suffix(imgs[0]["file_name_image"]) == "1"]
        for gid in orphan_1:
            del pending[gid]

    pending.setdefault(group_id, []).append(record)

    # 3️⃣ – attendre la paire complète ────────────────────────────────
    if len(pending[group_id]) < 2:
        return                                  # pas encore la paire

    images = sorted(pending[group_id], key=lambda r: r["file_name_image"])
    del pending[group_id]                       # paire consommée

    # ─── 4️⃣  calculs globaux et individuels  ────────────────────────────
    global_current_px = sum(img["current_day_px"] for img in images)

    previous_block = hist[plant][-1] if hist[plant] else None
    previous_global_px = previous_block["global_current_px"] if previous_block else None
    difference_global_growth = 0 if previous_global_px is None else global_current_px - previous_global_px

    # ➜ pct maintenant comparé au Δ du bloc précédent (si non nul)
    difference_global_growth_pct = (
        0.0 if previous_global_px in (None, 0)
        else round(100 * difference_global_growth / previous_global_px, 2)
    )

    # ───  Calcul GROWTH par image : on compare suffixe 1→1 et 2→2 ───────
    for img in images:
        suffix_cur = Path(img["file_name_image"]).stem.split("_")[1]  # "1" ou "2"
        prev_px = None

        for blk in reversed(hist[plant]):  # blocs précédents seulement
            for past in blk["images"]:
                suffix_past = Path(past["file_name_image"]).stem.split("_")[1]
                if suffix_past == suffix_cur:  # même suffixe => même position dans la paire
                    prev_px = past["current_day_px"];
                    break
            if prev_px is not None:
                break

        growth = 0 if prev_px is None else img["current_day_px"] - prev_px
        pct = 0.0 if prev_px in (None, 0) else round(100 * growth / prev_px, 2)
        img["growth"], img["growth_pourcentage"] = growth, pct

    # 5️⃣ – écriture JSON + S3 + MQTT ─────────────────────────────────
    block = {
        "global_current_px"            : global_current_px,
        "difference_global_growth"     : difference_global_growth,
        "difference_global_growth_pct" : difference_global_growth_pct,
        "id"                           : FORCED_ID,
        "disease_class"                : images[0]["disease_class"],
        "images"                       : [
            {
                "file_name_image"   : img["file_name_image"],
                "date"              : img["date"],
                "s3_ident"          : img["s3_ident"],
                "current_day_px"    : img["current_day_px"],
                "growth"            : img["growth"],
                "growth_pourcentage": img["growth_pourcentage"]
            } for img in images
        ]
    }

    hist[plant].append(block)
    with open(LOCAL_JSON, "w") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)
    s3.upload_file(LOCAL_JSON, BUCKET, JSON_S3_KEY)

    for img in images:
        _publish_mqtt({
            "plant_name"   : plant,
            "disease_class": images[0]["disease_class"],
            **img
        })

# ──────────────────── Public entry point ─────────────────────────
def analyse_one_s3_key(key: str, *, last_modified=None, crop=contour.DEFAULT_CROP):
    ident = f"{key}@{(last_modified.isoformat() if last_modified else 'NA')}"

    with _LOCK:
        if ident in _ALREADY_PROCESSED:
            return {"skipped": ident}
        _ALREADY_PROCESSED.add(ident)

    fname = os.path.basename(key)
    s3.download_file(BUCKET, key, fname)

    surface = contour.process_and_save(fname, crop=crop)
    area_px = surface["area_px"]

    disease_class, _ = classify_image(fname)

    record = {
        "date": last_modified.strftime("%Y-%m-%d %H:%M:%S"),
        "file_name_image": key,
        "s3_ident": ident,
        "current_day_px": area_px,
        "disease_class": disease_class
    }

    _save_history_atomic(FORCED_PLANT_NAME, record)
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

    # On garde uniquement les blocs les plus récents (paires)
    entries = hist[plant_name][-limit:]

    # Extraire un résumé pour chaque paire (bloc)
    out = []
    for block in entries:
        first_img = block["images"][0]
        out.append({
            "timestamp": first_img["date"],
            "global_px": block["global_current_px"],
            "difference_growth": block["difference_global_growth"]
        })
    return out

def _insert_sorted(hist_list: list, record: dict):
    """Add the record and keep the list sorted on the 'date' field."""
    hist_list.append(record)
    hist_list.sort(key=lambda e: e["date"])      # chronological order