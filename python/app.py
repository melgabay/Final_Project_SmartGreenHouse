from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import os, json, boto3, threading, time, requests, logging

from sensor_pipeline import load_data, get_series, get_latest
from plant_analysis   import get_growth_series

# ────────────────────────── Flask init ──────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=False, max_age=86400)

# ───────────────────────── Configuration ───────────────────────
DATA_FILE        = "sensor_data.json"
ACTUATOR_FILE    = "actuators.json"
PLANT_DATA_FILE  = "plant_data.json"

BUCKET           = os.getenv("AWS_BUCKET_NAME")
JSON_KEY         = os.getenv("JSON_S3_KEY", DATA_FILE)
ACT_KEY          = os.getenv("ACT_S3_KEY", ACTUATOR_FILE)
AWS_REGION       = os.getenv("AWS_REGION")

S3_PREFIX        = "plant_images/"
CHECK_INTERVAL   = 15          # seconds

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name           = AWS_REGION,
)

# Threading lock and cache variable
lock = threading.Lock()
_last_key_seen = None

# ────────────────────── Helpers S3 / files ────────────────────
def s3_download(key: str, local: str, default_as_list: bool = True):
    try:
        s3_client.download_file(BUCKET, key, local)
    except Exception:
        with open(local, "w") as f:
            json.dump([] if default_as_list else {}, f)

def s3_upload(local: str, key: str):
    try:
        s3_client.upload_file(local, BUCKET, key, ExtraArgs={"ContentType": "application/json"})
    except Exception as e:
        app.logger.error(f"Upload {local} → S3 failed: {e}")

# initial sync
for _key, _local, _is_list in (
    (JSON_KEY, DATA_FILE,  True),
    (ACT_KEY,  ACTUATOR_FILE, False),
):
    s3_download(_key, _local, default_as_list=_is_list)


# ─────────────────── Actuator File Format Management ───────────────────
try:
    with open(ACTUATOR_FILE) as f:
        saved = json.load(f)

        # ► fichier déjà au bon format
        if {"states", "mode", "thresholds"} <= saved.keys():
            ACTUATORS = saved

        # ► ancien format à plat → conversion
        else:
            ACTUATORS = {
                "states": {
                    "uv_light_on":          saved.get("uv_light_on", "OFF"),
                    "irrigation_on":        saved.get("irrigation_on", "OFF"),
                    "force_ventilation_on": saved.get("force_ventilation_on", "OFF"),
                },
                "mode": {
                    "uv_light_on":          "AUTO",
                    "irrigation_on":        "AUTO",
                    "force_ventilation_on": "AUTO",
                },
                "thresholds": {
                    "uv_light_on":          {"on": 8,  "off": 20},
                    "irrigation_on":        {"on": 40, "off": 50},
                    "force_ventilation_on": {"on": 40, "off": 50},
                }
            }
except FileNotFoundError:
    ACTUATORS = {
        "states": {
            "uv_light_on": "OFF",
            "irrigation_on": "OFF",
            "force_ventilation_on": "OFF",
        },
        "mode": {
            "uv_light_on": "AUTO",
            "irrigation_on": "AUTO",
            "force_ventilation_on": "AUTO",
        },
        "thresholds": {
            "uv_light_on":          {"on": 8,  "off": 20},
            "irrigation_on":        {"on": 40, "off": 50},
            "force_ventilation_on": {"on": 40, "off": 50},
        }
    }

# Save actuators state to local + upload to S3
def save_actuator_state():
    with lock:
        with open(ACTUATOR_FILE, "w") as f:
            json.dump(ACTUATORS, f, indent=2)   # ← on écrit l’objet complet
        s3_upload(ACTUATOR_FILE, ACT_KEY)

# Save full sensor dataset to disk and S3
def save_sensor_data(data):
    with lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        s3_upload(DATA_FILE, JSON_KEY)

# Get latest image key from S3 sorted by modification date
def latest_image_key_s3():
    resp = s3_client.list_objects_v2(Bucket=BUCKET, Prefix=S3_PREFIX)
    if "Contents" not in resp:
        return None
    return max(resp["Contents"], key=lambda o: o["LastModified"])["Key"]

# Background thread that watches for new images in S3 and triggers analysis
def watch_for_new_images():
    global _last_key_seen
    while True:
        try:
            key = latest_image_key_s3()
            if key and key != _last_key_seen:
                _last_key_seen = key
                try:
                    requests.post("http://localhost:5500/api/process-latest", timeout=10)
                    app.logger.info("New image detected – analysis triggered")
                except Exception as e:
                    app.logger.error(f"/api/process-latest fail: {e}")
        except Exception as e:
            app.logger.error(f"Watcher error: {e}")
        time.sleep(CHECK_INTERVAL)

# Start background watcher
threading.Thread(target=watch_for_new_images, daemon=True).start()

# ──────────────── API Routes ────────────────
@app.get("/api/history/<sensor_key>")
def history(sensor_key):
    limit = int(request.args.get("limit", 360))
    raw   = get_series(sensor_key, limit)
    series = [
        {"timestamp": p["timestamp"], "value": float(p["value"])}
        for p in raw if p.get("value") not in (None, "")
    ]
    return jsonify(series), 200

@app.post("/api/submit_data")
def submit_data():
    payload = request.get_json(force=True)
    if not payload or "timestamp" not in payload:
        return jsonify({"error": "Invalid payload"}), 400
    data = load_data()
    data.append(payload)
    save_sensor_data(data)
    return jsonify({"status": "ok"}), 201

@app.get("/api/sensor-data")
def sensor_data_all():
    return jsonify(load_data()), 200

@app.route("/api/update_actuators", methods=["POST"])
def update_actuators():
    """Réception payload Dashboard → maj states, mode, thresholds"""
    payload = request.get_json(force=True) or {}

    # --- STATES (ON/OFF) -----------------
    for k in ACTUATORS["states"]:
        if k in payload:
            ACTUATORS["states"][k] = payload[k]       # "ON"/"OFF"

    # --- MODE (AUTO / MANUAL) -------------
    for k in ACTUATORS["mode"]:
        manual_key = f"{k}_manual"                   # ex: uv_light_on_manual
        if manual_key in payload:
            ACTUATORS["mode"][k] = "MANUAL" if payload[manual_key] else "AUTO"

    # --- THRESHOLDS -----------------------
    for k in ACTUATORS["thresholds"]:
        th_on  = f"{k}_on"
        th_off = f"{k}_off"
        if th_on  in payload: ACTUATORS["thresholds"][k]["on"]  = float(payload[th_on])
        if th_off in payload: ACTUATORS["thresholds"][k]["off"] = float(payload[th_off])

    save_actuator_state()
    return jsonify(ACTUATORS), 200

@app.get("/api/latest-sensor")
def latest_sensor():
    latest = get_latest() or {}

    # états ON/OFF
    latest.update(ACTUATORS["states"])

    # ajoute seuils + mode pour le front
    latest["thresholds"] = ACTUATORS["thresholds"]
    latest["mode"]       = ACTUATORS["mode"]

    return jsonify(latest), 200

@app.get("/api/growth/<plant_name>")
def growth(plant_name):
    limit = int(request.args.get("limit", 30))
    return jsonify(get_growth_series(plant_name, limit)), 200

@app.post("/api/process-latest")
def process_latest():
    from plant_analysis import process_latest_image
    try:
        res, key = process_latest_image()
        return jsonify({"status": "success", "image_key": key, "entry": res}), 200
    except ValueError as e:
        if "already processed" in str(e).lower():
            return jsonify({"status": "duplicate", "message": str(e)}), 200
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.get("/api/latest-image-key")
def latest_image_key():
    from plant_analysis import find_latest_image_in_s3
    try:
        key = find_latest_image_in_s3() or ""
        return jsonify({"key": key}), 200
    except Exception as e:
        app.logger.error(f"latest-image-key error: {e}")
        return jsonify({"key": ""}), 200

@app.get("/api/s3url")
def presigned_url():
    key = request.args.get("key")
    url = s3_client.generate_presigned_url(
        "get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=3600
    )
    return jsonify({"url": url})

@app.get("/api/plant_data")
def plant_data_local():
    try:
        with open(PLANT_DATA_FILE) as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/plant-data")
def plant_data_s3():
    try:
        obj = s3_client.get_object(Bucket=BUCKET, Key=PLANT_DATA_FILE)
        return jsonify(json.loads(obj["Body"].read().decode())), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run Flask app on port 5500
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5500)), debug=True)
