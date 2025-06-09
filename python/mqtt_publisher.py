# mqtt_publisher.py – Simulates sensor data and publishes to MQTT broker
import paho.mqtt.publish as publish
import time
import random
import ssl

# MQTT Broker Configuration
MQTT_HOST = "33ea71e0e0034036b86bee133525b810.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "SmartGreenHouse"
MQTT_PASSWORD = "SmartGreenHouse2025"

# Sensor Topics & Value Generators
sensor_topics = {
    "env_monitoring_system/sensors/air_temperature_C": lambda: round(20 + random.random() * 5, 2),
    "env_monitoring_system/sensors/air_humidity": lambda: round(50 + random.random() * 20, 2),
    "env_monitoring_system/sensors/light_intensity": lambda: round(random.random() * 10, 2),
    "env_monitoring_system/sensors/soil_ph": lambda: round(6 + random.random() * 1.5, 2),
    "env_monitoring_system/sensors/soil_ec": lambda: random.randint(200, 300),
    "env_monitoring_system/sensors/soil_temp": lambda: round(18 + random.random() * 5, 2),
    "env_monitoring_system/sensors/soil_humidity": lambda: round(30 + random.random() * 30, 2),
}

# Main Publishing Loop
while True:
    for topic, value_generator in sensor_topics.items():
        value = value_generator()
        try:
            publish.single(
                topic,
                str(value),
                hostname=MQTT_HOST,
                port=MQTT_PORT,
                auth={'username': MQTT_USERNAME, 'password': MQTT_PASSWORD},
                tls={'tls_version': ssl.PROTOCOL_TLS}
            )
            print(f"Published to {topic}: {value}")
        except Exception as e:
            print(f"Failed to publish to {topic}: {e}")

    # Wait 30 seconds before sending the next batch
    time.sleep(30)