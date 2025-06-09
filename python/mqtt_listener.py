# mqtt_listener.py – HiveMQ ➜ Local JSON ➜ Flask API
import paho.mqtt.client as mqtt
import json
import ssl
import datetime
import pytz
import os
import requests

#  MQTT Connection Configuration
MQTT_HOST = "33ea71e0e0034036b86bee133525b810.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "SmartGreenHouse"
MQTT_PASSWORD = "SmartGreenHouse2025"

# Sensor Topics to Subscribe
sensor_topics = [
    "env_monitoring_system/sensors/air_temperature_C",
    "env_monitoring_system/sensors/air_humidity",
    "env_monitoring_system/sensors/light_intensity",
    "env_monitoring_system/sensors/soil_ph",
    "env_monitoring_system/sensors/soil_ec",
    "env_monitoring_system/sensors/soil_temp",
    "env_monitoring_system/sensors/soil_humidity",
]
sensor_keys = [topic.split("/")[-1] for topic in sensor_topics]

#  File and API Target
DATA_FILE = "sensor_data.json"
FLASK_API_ENDPOINT = os.getenv("FLASK_API", "http://localhost:5500/api/submit_data")

#  Timezone Configuration
timezone = pytz.timezone("Asia/Jerusalem")
current_data_buffer = {}

# Utility Functions

def save_to_local_file(row: dict):
    """
    Append a new sensor reading `row` to the local JSON file.
    Creates the file if it doesn't exist.
    """
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                data = json.load(f)
        else:
            data = []
    except json.JSONDecodeError:
        data = []

    data.append(row)

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def push_to_flask_api(row: dict):
    """
    Send the sensor data to the Flask backend API.
    Will not interrupt flow if request fails.
    """
    try:
        requests.post(FLASK_API_ENDPOINT, json=row, timeout=2)
    except requests.RequestException as e:
        print("Flask API unreachable:", e)

# MQTT Callbacks

def on_connect(client, userdata, flags, rc):
    """
    Called when the client connects to the MQTT broker.
    Subscribes to all sensor topics.
    """
    if rc == 0:
        print("Connected to MQTT broker")
        for topic in sensor_topics:
            client.subscribe(topic)
            print(f"Subscribed to: {topic}")
    else:
        print("Connection failed with code:", rc)

def on_message(client, userdata, msg):
    """
    Called when a message is received on a subscribed topic.
    Buffers incoming data and sends to Flask once all sensors are collected.
    """
    global current_data_buffer
    try:
        value = msg.payload.decode("utf-8")
        sensor_name = msg.topic.split("/")[-1]
        print(f"Received {sensor_name}: {value}")

        # Try converting to float
        try:
            current_data_buffer[sensor_name] = float(value)
        except ValueError:
            current_data_buffer[sensor_name] = value

        # If all sensors are present, process and send data
        if all(key in current_data_buffer for key in sensor_keys):
            timestamp = datetime.datetime.now(timezone).strftime("%Y-%m-%dT%H:%M:%S")
            row = {
                **current_data_buffer,
                "timestamp": timestamp,
                # Default actuator states (can be updated later via /api/actuators)
                "uv_light_on": False,
                "irrigation_on": False,
                "force_ventilation_on": False,
            }

            # save_to_local_file(row)
            push_to_flask_api(row)

            # Reset buffer for next data batch
            current_data_buffer = {}

    except Exception as e:
        print("Error while processing message:", e)

#  MQTT Client Setup

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS)
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_HOST, MQTT_PORT)
mqtt_client.loop_forever()