import os
import json
import ssl
import cv2
import numpy as np
from datetime import datetime
import time
import boto3
import paho.mqtt.client as mqtt
from tensorflow.keras.preprocessing import image as keras_image
import tensorflow as tf
import tensorflow_datasets as tfds
from dotenv import load_dotenv

# ─────────────────────── Configuration ───────────────────────
load_dotenv()

# Model location in S3
MODEL_PATH = "plant_village_CNN.h5"
MODEL_S3_KEY = "plant_village_CNN.h5"
LOCAL_JSON = "plant_data.json"
LATEST_IMAGE_NAME = "latest_plant.jpg"
PREVIOUS_IMAGE_NAME = "previous_plant.jpg"
JSON_S3_KEY = "plant_data.json"
IMAGE_S3_PREFIX = "plant_images/"
MIN_AREA_THRESHOLD = 500

# Initialize S3 client with credentials from environment variables
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)
BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

# ─────────────────────── S3 Utilities ───────────────────────

# Download file from S3 to local path
def download_from_s3(key, local_path):
    s3.download_file(BUCKET_NAME, key, local_path)

# Upload local file to S3
def upload_to_s3(local_path, key):
    s3.upload_file(local_path, BUCKET_NAME, key)

# Download and parse JSON from S3. If it fails, initialize an empty dict
def download_json(key, local_path):
    try:
        download_from_s3(key, local_path)
        with open(local_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        with open(local_path, "w") as f:
            json.dump({}, f, indent=2)
        return {}

# Download model before loading if not downloaded
# download_from_s3(MODEL_S3_KEY, MODEL_PATH)

# Load trained model and class labels
model = tf.keras.models.load_model(MODEL_PATH)
ds_info = tfds.builder('plant_village').info
class_names = ds_info.features['label'].names

# ─────────────────────── Image Processing ───────────────────────

# Extract the largest detected object from the image using contours
def extract_largest_object(image, min_area_threshold=500):
    height, width = image.shape[:2]
    total_area = height * width

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Invert threshold if needed (foreground should be darker than background)
    if np.mean(gray[thresh == 255]) > np.mean(gray[thresh == 0]):
        thresh = cv2.bitwise_not(thresh)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = max(contours, key=cv2.contourArea, default=None)

    if largest is not None:
        area = cv2.contourArea(largest)
        if area >= min_area_threshold:
            return int(area), total_area

    return 0, total_area

# Compare two images to determine pixel area change of largest object
def compare_images(image1_path, image2_path, min_area_threshold=500):
    img1 = cv2.imread(image1_path)
    img2 = cv2.imread(image2_path)

    area1, total1 = extract_largest_object(img1, min_area_threshold)
    area2, total2 = extract_largest_object(img2, min_area_threshold)

    ratio1 = (area1 / total1) * 100 if total1 else 0
    ratio2 = (area2 / total2) * 100 if total2 else 0

    growth = 1 if ratio1 > ratio2 else -1 if ratio2 > ratio1 else 0

    return {
        "current_day_px": area1,
        "growth": growth
    }

# ─────────────────────── Image Classification ───────────────────────

# Classify image using trained CNN model
def classify_image(image_path):
    img = keras_image.load_img(image_path, target_size=(128, 128))
    img_array = keras_image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) / 255.0

    predictions = model.predict(img_array, verbose=0)
    predicted_index = int(np.argmax(predictions, axis=1)[0])
    predicted_name = class_names[predicted_index]

    # Return class index and plant name (extracted from class label)
    return {
        "id": predicted_index,
        "name": predicted_name
    }, predicted_name.split("___")[0]

# ─────────────────────── S3 Image Management ───────────────────────

# Find the latest image file in S3 by modification date
def find_latest_image_in_s3(prefix=IMAGE_S3_PREFIX):
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    if "Contents" not in response:
        return None

    image_keys = [
        obj["Key"] for obj in response["Contents"]
        if obj["Key"].lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    if not image_keys:
        return None

    # Sort by latest modification date
    image_keys.sort(
        key=lambda key: s3.head_object(Bucket=BUCKET_NAME, Key=key)["LastModified"],
        reverse=True
    )
    return image_keys[0]

# ─────────────────────── MQTT Messaging ───────────────────────

# Send a message with image analysis result via MQTT to broker
def send_mqtt_message(entry, plant_name):
    message = {
        "plant_name": plant_name,
        "date": entry["date"],
        "file_name_image": entry["file_name_image"],
        "size_compare": entry["size_compare"],
        "disease_class": entry["disease_class"]
    }

    HOST = "33ea71e0e0034036b86bee133525b810.s1.eu.hivemq.cloud"
    PORT = 8883
    USERNAME = "SmartGreenHouse"
    PASSWORD = "SmartGreenHouse2025"

    try:
        client = mqtt.Client(protocol=mqtt.MQTTv311)
        client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        client.username_pw_set(USERNAME, PASSWORD)
        client.connect(HOST, PORT)
        client.loop_start()
        time.sleep(2)
        client.publish("test/plant_growth", json.dumps(message), qos=1, retain=True)
        client.loop_stop()
        client.disconnect()
        print("[MQTT] Message successfully published.")
    except Exception as e:
        print(f"[MQTT] Error sending message: {e}")

# ─────────────────────── Main Processing Function ───────────────────────

# Process the most recent image from S3:
# - deduplicate
# - classify
# - compare to previous
# - save result
# - send MQTT message
def process_latest_image():
    history = download_json(JSON_S3_KEY, LOCAL_JSON)
    latest_key = find_latest_image_in_s3()
    if not latest_key:
        raise FileNotFoundError("No image found in S3")

    # Deduplication: check if already processed
    for plant_entries in history.values():
        for e in plant_entries:
            file_name = e.get("file_name_image")
            if file_name and os.path.basename(file_name) == os.path.basename(latest_key):
                print("[INFO] Image already processed:", latest_key)
                return e, latest_key

    # Process new image
    download_from_s3(latest_key, LATEST_IMAGE_NAME)
    disease_class, plant_name = classify_image(LATEST_IMAGE_NAME)

    if not plant_name:
        raise ValueError("Could not classify the plant name from the image.")

    previous_entry = history.get(plant_name, [])[-1] if plant_name in history else None

    if previous_entry:
        previous_file = previous_entry.get("file_name_image")
        if previous_file:
            download_from_s3(previous_file, PREVIOUS_IMAGE_NAME)
            compare_data = compare_images(LATEST_IMAGE_NAME, PREVIOUS_IMAGE_NAME, MIN_AREA_THRESHOLD)
        else:
            compare_data = {"current_day_px": 0, "growth": 0}
    else:
        area, _ = extract_largest_object(cv2.imread(LATEST_IMAGE_NAME), MIN_AREA_THRESHOLD)
        compare_data = {"current_day_px": area, "growth": 0}

    new_entry = {
        "date": datetime.utcnow().isoformat(),
        "file_name_image": latest_key,
        "size_compare": compare_data,
        "disease_class": disease_class
    }

    # Append to history and save locally and on S3
    history.setdefault(plant_name, []).append(new_entry)
    with open(LOCAL_JSON, "w") as f:
        json.dump(history, f, indent=2)
    upload_to_s3(LOCAL_JSON, JSON_S3_KEY)

    # Send to MQTT
    send_mqtt_message(new_entry, plant_name)

    return new_entry, latest_key

# ─────────────────────── Growth History ───────────────────────

# Return growth series for a plant: size and daily delta over time
def get_growth_series(plant_name: str, limit: int = 30, json_key: str = JSON_S3_KEY) -> list[dict]:
    local_path = LOCAL_JSON
    download_json(json_key, local_path)

    with open(local_path, "r") as f:
        history = json.load(f)

    if plant_name not in history:
        return []

    sorted_entries = sorted(history[plant_name], key=lambda e: e["date"])
    series = []
    previous_px = None

    for entry in sorted_entries[-limit:]:
        current_px = entry["size_compare"]["current_day_px"]
        growth = 0 if previous_px is None else current_px - previous_px
        series.append({
            "timestamp": entry["date"],
            "current_px": current_px,
            "growth_px": growth
        })
        previous_px = current_px

    return series