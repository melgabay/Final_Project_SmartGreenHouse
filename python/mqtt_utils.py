# mqtt_utils.py – Utility function to publish plant analysis results over MQTT

import paho.mqtt.client as mqtt
import ssl
import json

# MQTT Broker Configuration
HOST = "33ea71e0e0034036b86bee133525b810.s1.eu.hivemq.cloud"
PORT = 8883
USERNAME = "SmartGreenHouse"
PASSWORD = "SmartGreenHouse2025"

# Topic used to broadcast plant analysis results
TOPIC = "test/plant_growth"

# Publish a dictionary payload to the configured MQTT topic
def publish_plant_analysis(payload: dict):
    try:
        # Create a new MQTT client instance with secure TLS connection
        client = mqtt.Client(protocol=mqtt.MQTTv311)
        client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        client.username_pw_set(USERNAME, PASSWORD)
        client.connect(HOST, PORT)
        client.loop_start()

        # Publish the payload to the topic with QoS 1 and retain flag
        client.publish(TOPIC, json.dumps(payload), qos=1, retain=True)

        client.loop_stop()
        client.disconnect()
        print("[MQTT] Published analysis result")
    except Exception as e:
        print(f"[MQTT] Error: {e}")