# mqtt_publisher.py – Publishes sensor values + allows actuator commands
import time
import random
import ssl
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish

# ───── MQTT Config ─────
MQTT_HOST     = "33ea71e0e0034036b86bee133525b810.s1.eu.hivemq.cloud"
MQTT_PORT     = 8883
MQTT_USERNAME = "SmartGreenHouse"
MQTT_PASSWORD = "SmartGreenHouse2025"

# ───── Topics: capteurs simulés ─────
sensor_topics = {
    "env_monitoring_system/sensors/air_temperature_C": lambda: round(20 + random.random() * 5, 2),
    "env_monitoring_system/sensors/air_humidity": lambda: round(50 + random.random() * 20, 2),
    "env_monitoring_system/sensors/light_intensity": lambda: round(random.random() * 10, 2),
    "env_monitoring_system/sensors/soil_ph": lambda: round(6 + random.random() * 1.5, 2),
    "env_monitoring_system/sensors/soil_ec": lambda: random.randint(200, 300),
    "env_monitoring_system/sensors/soil_temp": lambda: round(18 + random.random() * 5, 2),
    "env_monitoring_system/sensors/soil_humidity": lambda: round(30 + random.random() * 30, 2),
}

# ───── Publication pour les actuators ─────
def publish_command(topic: str, payload: str):
    try:
        publish.single(
            topic,
            payload=str(payload),
            hostname=MQTT_HOST,
            port=MQTT_PORT,
            auth={'username': MQTT_USERNAME, 'password': MQTT_PASSWORD},
            tls={'tls_version': ssl.PROTOCOL_TLS}
        )
        print(f"[ACTUATOR] Published to {topic}: {payload}")
    except Exception as e:
        print(f"[ERROR] Failed to publish actuator command: {e}")

# ───── Simulation continue des capteurs ─────
if __name__ == "__main__":
    while True:
        for topic, generate in sensor_topics.items():
            value = generate()
            try:
                publish.single(
                    topic,
                    str(value),
                    hostname=MQTT_HOST,
                    port=MQTT_PORT,
                    auth={'username': MQTT_USERNAME, 'password': MQTT_PASSWORD},
                    tls={'tls_version': ssl.PROTOCOL_TLS}
                )
                print(f"[SENSOR] Published to {topic}: {value}")
            except Exception as e:
                print(f"[ERROR] Failed to publish to {topic}: {e}")
        time.sleep(10)