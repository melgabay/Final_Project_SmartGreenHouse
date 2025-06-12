#!/usr/bin/env python3
# Réception capteurs MQTT → JSON local + logique AUTO

import json, os, threading, ssl, datetime, pytz, boto3, paho.mqtt.client as mqtt

##### Config MQTT (HiveMQ) ################################################
MQTT_HOST     = "33ea71e0e0034036b86bee133525b810.s1.eu.hivemq.cloud"
MQTT_PORT     = 8883
MQTT_USER     = "SmartGreenHouse"
MQTT_PASS     = "SmartGreenHouse2025"
SENSOR_TOPICS = [
    "env_monitoring_system/sensors/air_temperature_C",
    "env_monitoring_system/sensors/air_humidity",
    "env_monitoring_system/sensors/light_intensity",
    "env_monitoring_system/sensors/soil_ph",
    "env_monitoring_system/sensors/soil_ec",
    "env_monitoring_system/sensors/soil_temp",
    "env_monitoring_system/sensors/soil_humidity",
]
###########################################################################

##### Fichiers + S3 #######################################################
SENSOR_FILE   = "sensor_data.json"
ACTUATOR_FILE = "actuators.json"
AWS_BUCKET    = os.getenv("AWS_BUCKET_NAME")
S3            = boto3.client("s3")
lock          = threading.Lock()
MAX_ENTRIES   = 10_000
###########################################################################

def load_json(path, default):
    try:    return json.load(open(path))
    except: return default

def save_json(path, obj):
    tmp = f"{path}.tmp"
    json.dump(obj, open(tmp, "w"), indent=2)
    os.replace(tmp, path)

def s3_upload(local, key):
    threading.Thread(
        target=S3.upload_file, args=(local, AWS_BUCKET, key), daemon=True
    ).start()

sensors   = load_json(SENSOR_FILE , [])
actuators = load_json(ACTUATOR_FILE, {"states": {}, "mode": {}, "thresholds": {}})

timezone = pytz.timezone("Asia/Jerusalem")
buffer   = {}

def decide_auto(reading):
    updated = False
    for name, state in actuators["states"].items():
        if actuators["mode"][name] != "AUTO":
            continue
        metric = (
            reading.get("soil_humidity")  if "irrigation" in name else
            reading.get("air_humidity")   if "ventilation" in name else
            reading.get("light_intensity")
        )
        if metric is None:
            continue
        th = actuators["thresholds"][name]
        if not state and metric < th["on"]:
            actuators["states"][name] = True;  updated = True
        elif state and metric > th["off"]:
            actuators["states"][name] = False; updated = True
    return updated

def on_connect(cli, *_):
    for t in SENSOR_TOPICS:
        cli.subscribe(t); print("sub", t)

def on_message(cli, *_args):
    global buffer
    sensor_key = _args[2].topic.split("/")[-1]
    try:
        buffer[sensor_key] = float(_args[2].payload.decode())
    except ValueError:
        buffer[sensor_key] = _args[2].payload.decode()

    if len(buffer) == len(SENSOR_TOPICS):
        row = {**buffer}
        row["timestamp"] = datetime.datetime.now(timezone).strftime("%Y-%m-%dT%H:%M:%S")

        with lock:
            # logique AUTO + éventuelle publication
            if decide_auto(row):
                for k, v in actuators["states"].items():
                    cli.publish(f"env_monitoring_system/actuators/{k}/dc", "ON" if v else "OFF")

            row.update(actuators["states"])
            sensors.append(row)
            sensors[:] = sensors[-MAX_ENTRIES:]
            save_json(SENSOR_FILE , sensors)
            save_json(ACTUATOR_FILE, actuators)
            s3_upload(SENSOR_FILE , SENSOR_FILE )
            s3_upload(ACTUATOR_FILE, ACTUATOR_FILE)

        buffer = {}

client = mqtt.Client()
client.tls_set(tls_version=ssl.PROTOCOL_TLS)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT)
client.loop_forever()