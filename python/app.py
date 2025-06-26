"""
S3 Watcher → analyse_one_s3_key() (only files ≥ START_FROM_UTC)
Routes:
GET /api/latest-image-key
GET /api/plant-data (/api/plant_data alias)
/api/contour/overlays & /api/contour/process-all preserved
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, boto3, time, logging
from multiprocessing import Process
from pathlib import Path
from datetime import datetime, timezone
import contour
from sensor_pipeline import get_series, get_latest, load_data
from plant_analysis import analyse_one_s3_key, get_growth_series  # ALLOWED_BASENAMES

# ───────────────────── App & AWS config ─────────────────────
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, max_age=86400)
app.logger.setLevel(logging.INFO)

BUCKET  = os.getenv("AWS_BUCKET_NAME")
REGION  = os.getenv("AWS_REGION")
DATA_FILE, ACTUATOR_FILE, PLANT_FILE = "sensor_data.json", "actuators.json", "plant_data.json"

s3 = boto3.client(
    "s3",
    aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name           = REGION,
)

CHECK_EVERY   = 5  # s
START_FROM_UTC = datetime(2025, 6, 24, 12, 46, 12, tzinfo=timezone.utc)
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")
# ───────────────────── Image helpers ─────────────────────
def _list_recent_s3_objects(start_dt: datetime = START_FROM_UTC):
    """Yield (key, last_modified) for every S3 object ≥ start_dt (UTC)."""
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET):
        for obj in page.get("Contents", []):
            lm = obj["LastModified"]            # tz-aware, UTC
            key = obj["Key"]
            if lm >= start_dt and key.lower().endswith(IMAGE_EXTS):
                yield key, lm


def _find_latest_image_key():
    objs = list(_list_recent_s3_objects())
    return max(objs, key=lambda x: x[1])[0] if objs else None

# ───────────────────── S3 processing loop ─────────────────────
def process_s3_loop():
    """
    Infinite loop: scans S3 every CHECK_EVERY seconds,
    processes frames ≥ START_FROM_UTC in chronological order.
    """
    while True:
        try:
            for key, lm in sorted(_list_recent_s3_objects(), key=lambda x: x[1]):
                analyse_one_s3_key(key, last_modified=lm)
        except Exception as e:
            app.logger.warning(f"[LOOP] {e}")
        time.sleep(CHECK_EVERY)
# ───────────────────── Routes API ─────────────────────
@app.get("/api/latest-image-key")
def latest_image_key():
    return jsonify({"key": _find_latest_image_key() or ""})

app.add_url_rule("/api/latest_image_key", view_func=latest_image_key, methods=["GET"])

@app.get("/api/plant-data")
def plant_data():
    try:
        if not Path(PLANT_FILE).exists():
            s3.download_file(BUCKET, PLANT_FILE, PLANT_FILE)
        with open(PLANT_FILE) as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

app.add_url_rule("/api/plant_data", view_func=plant_data, methods=["GET"])

@app.get("/api/history/<sensor_key>")
def history(sensor_key):
    limit = int(request.args.get("limit", 360))
    raw   = get_series(sensor_key, limit)
    series = [
        {"timestamp": p["timestamp"], "value": float(p["value"])}
        for p in raw if p.get("value") not in (None, "")
    ]
    return jsonify(series)

@app.get("/api/growth/<plant_name>")
def growth(plant_name):
    limit = int(request.args.get("limit", 30))
    return jsonify(get_growth_series(plant_name, limit))

# ────────────── S3 presigned URL ──────────────
@app.get("/api/s3url")
def presigned_url():
    key = request.args.get("key")
    if not key:
        return jsonify({"error": "missing key param"}), 400
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=3600,     # 1 h
        )
        return jsonify({"url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 404

# ────────────── Contour helper routes ──────────────

@app.get("/api/contour/overlays")
def list_overlays():
    files = [f.name for f in Path(contour.OVERLAY_DIR).glob("*_full.jpg")]
    files += [f.name for f in Path(contour.OVERLAY_DIR).glob("*_crop.jpg")]
    return jsonify({"overlays": sorted(files)})

@app.post("/api/contour/process-all")
def process_all_contours():
    processed = []
    for key, lm in _list_recent_s3_objects():
        processed.append(analyse_one_s3_key(key, last_modified=lm))
    return jsonify(processed)


@app.post("/api/process-latest")
def process_latest():
    objs = list(_list_recent_s3_objects())
    if not objs:
        return jsonify({"error": "no image found"}), 404
    key, lm = max(objs, key=lambda x: x[1])
    result  = analyse_one_s3_key(key, last_modified=lm)
    return jsonify(result)

app.add_url_rule("/api/process_latest", view_func=process_latest, methods=["POST"])
# ───────────────────── Main ─────────────────────
if __name__ == "__main__":
    Process(target=process_s3_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5500)), debug=True)