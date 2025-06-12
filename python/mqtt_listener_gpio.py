import paho.mqtt.client as mqtt

try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    from mock_gpio import gpio as GPIO
# Configuration des pins GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

PIN_LIGHT = 17       # GPIO pour lumière UV
PIN_IRRIGATION = 27  # GPIO pour pompe à eau
PIN_FAN = 22         # GPIO pour ventilation

GPIO.setup(PIN_LIGHT, GPIO.OUT)
GPIO.setup(PIN_IRRIGATION, GPIO.OUT)
GPIO.setup(PIN_FAN, GPIO.OUT)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe("env_monitoring_system/actuators/fan/dc")
    client.subscribe("env_monitoring_system/actuators/water_pump/dc")
    client.subscribe("env_monitoring_system/actuators/light/dc")

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode().upper()
    print(f"[MQTT] Topic: {topic} | Payload: {payload}")

    if topic == "env_monitoring_system/actuators/fan/dc":
        GPIO.output(PIN_FAN, GPIO.HIGH if payload == "ON" else GPIO.LOW)

    elif topic == "env_monitoring_system/actuators/water_pump/dc":
        GPIO.output(PIN_IRRIGATION, GPIO.HIGH if payload == "ON" else GPIO.LOW)

    elif topic == "env_monitoring_system/actuators/light/dc":
        GPIO.output(PIN_LIGHT, GPIO.HIGH if payload == "ON" else GPIO.LOW)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("broker.hivemq.com", 1883, 60)
client.loop_forever()
