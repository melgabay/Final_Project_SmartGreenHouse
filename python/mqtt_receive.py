import paho.mqtt.client as mqtt

# MQTT configuration for subscribing to plant growth updates
HOST = "smartgreen-884cb6eb.a03.euc1.aws.hivemq.cloud"
PORT = 8883
USERNAME = "SmartGreenHouse"
PASSWORD = "SmartGreenHouse2025"
TOPIC = "test/plant_growth"

# Callback function triggered when the client connects to the broker
def on_connect(client, userdata, flags, rc):
    print("[MQTT] Connected with result code", rc)
    # Subscribe to the topic once connected
    client.subscribe(TOPIC)

# Callback function triggered when a message is received on the subscribed topic
def on_message(client, userdata, message):
    payload = message.payload.decode("utf-8")
    print(f"\n Message received on topic '{message.topic}':\n{payload}\n")

# Initialize MQTT client with TLS and credentials
client = mqtt.Client()
client.tls_set()
client.username_pw_set(USERNAME, PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

# Connect to the MQTT broker
client.connect(HOST, PORT)
print(f" Waiting for messages on the topic '{TOPIC}'...")

# Start the MQTT loop to process incoming messages
client.loop_forever()