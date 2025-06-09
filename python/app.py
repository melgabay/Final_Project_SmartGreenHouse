# app.py – Flask API + S3 integration  (persistant)
from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, boto3
from sensor_pipeline import load_data, get_series, get_latest
from plant_analysis   import get_growth_series

# ───────────────────────── Flask init ─────────────────────────
app = Flask(__name__)
CORS(app)

# ───────────────────────── Configuration ─────────────────────
DATA_FILE       = "sensor_data.json"
ACTUATOR_FILE   = "actuators.json"          # NEW ⟶ fichier dédié
BUCKET          = os.getenv("AWS_BUCKET_NAME")
JSON_KEY        = os.getenv("JSON_S3_KEY", DATA_FILE)
ACT_KEY         = os.getenv("ACT_S3_KEY",  ACTUATOR_FILE)  # NEW ⟶ clé S3

# ─────────────────────── Actuators in-memory ──────────────────
def default_actuators():
    return {
        "uv_light_on":            "OFF",
        "irrigation_on":          "OFF",
        "force_ventilation_on":   "OFF",
    }

def default_thresholds():
    return {
        "uv_on_value":                "",
        "uv_off_value":               "",
        "irrigation_on_value":        "",
        "irrigation_off_value":       "",
        "force_ventilation_on_value": "",
        "force_ventilation_off_value": "",
    }

# NEW ⟶ charge depuis actuators.json au démarrage
if os.path.exists(ACTUATOR_FILE):
    try:
        with open(ACTUATOR_FILE) as f:
            saved = json.load(f)
            ACTUATORS  = saved.get("actuators",  default_actuators())
            THRESHOLDS = saved.get("thresholds", default_thresholds())
    except Exception:
        ACTUATORS, THRESHOLDS = default_actuators(), default_thresholds()
else:
    ACTUATORS, THRESHOLDS = default_actuators(), default_thresholds()

# ────────────────────── Utils persistants ─────────────────────
def save_actuator_state():
    """Écrit {actuators, thresholds} → actuators.json puis push S3."""
    with open(ACTUATOR_FILE, "w") as f:
        json.dump({"actuators": ACTUATORS, "thresholds": THRESHOLDS}, f, indent=2)
    try:
        boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION"),
        ).upload_file(
            ACTUATOR_FILE,
            BUCKET,
            ACT_KEY,
            ExtraArgs={"ContentType": "application/json"},
        )
    except Exception as e:
        print("S3 upload (actuators) failed:", e)

def save_local_data(data: list):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def upload_sensor_json():
    try:
        boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION"),
        ).upload_file(
            DATA_FILE,
            BUCKET,
            JSON_KEY,
            ExtraArgs={"ContentType": "application/json"},
        )
    except Exception as e:
        print("S3 upload (sensor_data) failed:", e)

# ─────────────────────────── Routes ───────────────────────────
@app.route("/api/history/<sensor_key>")
def history(sensor_key):
    limit = int(request.args.get("limit", 360))
    return jsonify(get_series(sensor_key, limit)), 200

@app.route("/api/submit_data", methods=["POST"])
def submit_data():
    payload = request.get_json(force=True)
    if not payload or "timestamp" not in payload:
        return jsonify({"error": "invalid payload"}), 400
    data = load_data()
    data.append(payload)
    save_local_data(data)
    upload_sensor_json()
    return jsonify({"status": "ok"}), 201

@app.route("/api/sensor-data")
def all_sensor_data():
    return jsonify(load_data()), 200

# ───── Actuators persistant ─────
@app.route("/api/update_actuators", methods=["POST"])
@app.route("/api/actuators",        methods=["GET", "POST"])
def actuators():
    """
    GET  → état actuel + seuils.
    POST → met à jour et persiste.
    """
    if request.method == "POST":
        updates = request.get_json(force=True) or {}
        # ON/OFF
        for k in ACTUATORS.keys() & updates.keys():
            ACTUATORS[k] = str(updates[k]).upper()
        # seuils
        for k in THRESHOLDS.keys() & updates.keys():
            THRESHOLDS[k] = str(updates[k])
        save_actuator_state()          # NEW ⟶ persiste disque + S3
    return jsonify({**ACTUATORS, **THRESHOLDS}), 200

@app.route("/api/latest-sensor")
def latest_sensor():
    latest = get_latest() or {}
    latest.update(ACTUATORS)
    latest.update(THRESHOLDS)
    return jsonify(latest), 200

# ───── Plantes & S3 helpers (inchangé) ─────
@app.route("/api/plant_data")
def plant_data():
    try:
        with open("plant_data.json") as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/s3url")
def get_s3_url():
    key = request.args.get("key")
    url = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION"),
    ).generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=3600,
    )
    return jsonify({"url": url})

@app.route("/api/plant-data")
def get_plant_data_from_s3():
    try:
        obj = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION"),
        ).get_object(Bucket=BUCKET, Key="plant_data.json")
        return jsonify(json.loads(obj["Body"].read().decode("utf-8")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ───── Growth ─────
@app.route("/api/growth/<plant_name>")
def growth(plant_name):
    limit = int(request.args.get("limit", 30))
    return jsonify(get_growth_series(plant_name, limit)), 200

# ───── Launch ─────
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5500)),
        debug=bool(int(os.getenv("FLASK_DEBUG", 1)))
    )