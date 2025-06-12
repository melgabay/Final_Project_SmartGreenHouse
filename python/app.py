from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import boto3
import threading
import time
import requests
import logging

from sensor_pipeline import load_data, get_series, get_latest
from plant_analysis import get_growth_series

# ─────────────────────── Flask Initialization ───────────────────────
app = Flask(__name__)
CORS(
    app,
    resources={r"/api/*": {"origins": "*"}},
    supports_credentials=False,
    max_age=86400
)
# ─────────────────────── Configuration ───────────────────────
DATA_FILE = "sensor_data.json"
ACTUATOR_FILE = "actuators.json"
PLANT_DATA_FILE = "plant_data.json"

BUCKET = os.getenv("AWS_BUCKET_NAME")
JSON_KEY = os.getenv("JSON_S3_KEY", DATA_FILE)
ACT_KEY = os.getenv("ACT_S3_KEY", ACTUATOR_FILE)
AWS_REGION = os.getenv("AWS_REGION")

S3_PREFIX = "plant_images/"
CHECK_INTERVAL = 15

s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=AWS_REGION,
)

_last_key_seen = None

# ─────────────────────── Default States ───────────────────────
def default_actuators():
    return {
        "uv_light_on": "OFF",
        "irrigation_on": "OFF",
        "force_ventilation_on": "OFF"
    }

def default_thresholds():
    return {
        "uv_on_value": "",
        "uv_off_value": "",
        "irrigation_on_value": "",
        "irrigation_off_value": "",
        "force_ventilation_on_value": "",
        "force_ventilation_off_value": ""
    }

# ─────────────────────── Load Actuator State ───────────────────────
if os.path.exists(ACTUATOR_FILE):
    try:
        with open(ACTUATOR_FILE) as f:
            saved = json.load(f)
            ACTUATORS = saved.get("actuators", default_actuators())
            THRESHOLDS = saved.get("thresholds", default_thresholds())
    except Exception:
        ACTUATORS = default_actuators()
        THRESHOLDS = default_thresholds()
else:
    ACTUATORS = default_actuators()
    THRESHOLDS = default_thresholds()

# ─────────────────────── Utility Functions ───────────────────────
def save_actuator_state():
    """Save current actuator state and thresholds to local file and S3."""
    with open(ACTUATOR_FILE, "w") as f:
        json.dump({"actuators": ACTUATORS, "thresholds": THRESHOLDS}, f, indent=2)
    try:
        s3_client.upload_file(
            ACTUATOR_FILE,
            BUCKET,
            ACT_KEY,
            ExtraArgs={"ContentType": "application/json"},
        )
    except Exception as e:
        print("Failed to upload actuators.json to S3:", e)

def save_local_data(data: list):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def upload_sensor_json():
    try:
        s3_client.upload_file(
            DATA_FILE,
            BUCKET,
            JSON_KEY,
            ExtraArgs={"ContentType": "application/json"},
        )
    except Exception as e:
        print("Failed to upload sensor_data.json to S3:", e)

def get_latest_image_key():
    response = s3_client.list_objects_v2(Bucket=BUCKET, Prefix=S3_PREFIX)
    if "Contents" not in response:
        return None
    return max(response["Contents"], key=lambda o: o["LastModified"])["Key"]

def watch_for_new_images():
    global _last_key_seen
    while True:
        try:
            latest_key = get_latest_image_key()
            if latest_key and latest_key != _last_key_seen:
                _last_key_seen = latest_key
                try:
                    requests.post("http://localhost:5500/api/process-latest", timeout=10)
                    logging.info("Triggered analysis of new image.")
                except Exception as e:
                    logging.error(f"Failed to call /api/process-latest: {e}")
        except Exception as e:
            logging.error(f"Watcher error: {e}")
        time.sleep(CHECK_INTERVAL)

# ─────────────────────── API Routes ───────────────────────

# Sensor history
@app.route("/api/history/<sensor_key>")
# ─── Sensor history ─────────────────────────────────────────────
@app.route("/api/history/<sensor_key>")
def history(sensor_key):
    limit = int(request.args.get("limit", 360))
    raw = get_series(sensor_key, limit)      # ← ta fonction utilitaire
    series = [
        {
            "timestamp": p["timestamp"],
            "value": float(p["value"])       # ← force numérique
        }
        for p in raw
        if p.get("value") not in (None, "")
    ]
    return jsonify(series), 200
# Submit new data point
@app.route("/api/submit_data", methods=["POST"])
def submit_data():
    payload = request.get_json(force=True)
    if not payload or "timestamp" not in payload:
        return jsonify({"error": "Invalid payload"}), 400
    data = load_data()
    data.append(payload)
    save_local_data(data)
    upload_sensor_json()
    return jsonify({"status": "ok"}), 201

# Get full sensor data
@app.route("/api/sensor-data")
def all_sensor_data():
    return jsonify(load_data()), 200

# Get or update actuators and thresholds
@app.route("/api/update_actuators", methods=["POST"])
@app.route("/api/actuators", methods=["GET", "POST"])
def actuators():
    if request.method == "POST":
        updates = request.get_json(force=True) or {}
        for k in ACTUATORS.keys() & updates.keys():
            ACTUATORS[k] = str(updates[k]).upper()
        for k in THRESHOLDS.keys() & updates.keys():
            THRESHOLDS[k] = str(updates[k])
        save_actuator_state()
    return jsonify({**ACTUATORS, **THRESHOLDS}), 200

# Latest sensor + actuator state
@app.route("/api/latest-sensor")
def latest_sensor():
    latest = get_latest() or {}
    latest.update(ACTUATORS)
    latest.update(THRESHOLDS)
    return jsonify(latest), 200

# Load plant data from local
@app.route("/api/plant_data")
def plant_data():
    try:
        with open(PLANT_DATA_FILE) as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get pre-signed S3 URL
@app.route("/api/s3url")
def get_s3_url():
    key = request.args.get("key")
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=3600,
    )
    return jsonify({"url": url})

# Load plant data from S3
@app.route("/api/plant-data")
def get_plant_data_from_s3():
    try:
        obj = s3_client.get_object(Bucket=BUCKET, Key=PLANT_DATA_FILE)
        return jsonify(json.loads(obj["Body"].read().decode("utf-8")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Growth history for a plant
@app.route("/api/growth/<plant_name>")
def growth(plant_name):
    limit = int(request.args.get("limit", 30))
    return jsonify(get_growth_series(plant_name, limit)), 200

# Process latest S3 image
@app.route("/api/process-latest", methods=["POST"])
def process_latest():
    try:
        from plant_analysis import process_latest_image
        result, image_key = process_latest_image()
        return jsonify({"status": "success", "image_key": image_key, "entry": result}), 200
    except ValueError as e:
        if "already processed" in str(e).lower():
            return jsonify({"status": "duplicate", "message": str(e)}), 200
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Find latest image key
@app.route("/api/latest-image-key")
def latest_image_key():
    from plant_analysis import find_latest_image_in_s3
    try:
        key = find_latest_image_in_s3() or ""
        return jsonify({"key": key}), 200
    except Exception as e:
        app.logger.error(f"/api/latest-image-key error: {e}")
        return jsonify({"key": ""}), 200
# ─────────────────────── Background Watcher ───────────────────────
threading.Thread(target=watch_for_new_images, daemon=True).start()

# ─────────────────────── Launch Server ───────────────────────
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5500)),
        debug=bool(int(os.getenv("FLASK_DEBUG", 1)))
    )