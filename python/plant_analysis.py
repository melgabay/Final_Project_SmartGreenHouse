import os
import json
import cv2
import numpy as np
from datetime import datetime
import boto3
from tensorflow.keras.preprocessing import image as keras_image
import tensorflow as tf
import tensorflow_datasets as tfds

# ─────────────── Configuration ───────────────
MODEL_PATH = "plant_village_CNN.h5"
LOCAL_JSON = "plant_data.json"
LATEST_IMAGE_NAME = "latest_plant.jpg"
PREVIOUS_IMAGE_NAME = "previous_plant.jpg"
JSON_S3_KEY = "plant_data.json"
IMAGE_S3_PREFIX = "plant_images/"
MIN_AREA_THRESHOLD = 500

# ─────────────── Load CNN Model and Class Names ───────────────
model = tf.keras.models.load_model(MODEL_PATH)
ds_info = tfds.builder('plant_village').info
class_names = ds_info.features['label'].names

# ─────────────── AWS S3 Client ───────────────
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)
BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

# ─────────────── S3 Helpers ───────────────
def download_from_s3(key, local_path):
    s3.download_file(BUCKET_NAME, key, local_path)

def upload_to_s3(local_path, key):
    s3.upload_file(local_path, BUCKET_NAME, key)

def download_json(key, local_path):
    try:
        download_from_s3(key, local_path)
        with open(local_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        with open(local_path, "w") as f:
            json.dump({}, f, indent=2)
        return {}

# ─────────────── Image Processing ───────────────
def extract_largest_object(image, min_area_threshold=500):
    height, width = image.shape[:2]
    total_area = height * width

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if np.mean(gray[thresh == 255]) > np.mean(gray[thresh == 0]):
        thresh = cv2.bitwise_not(thresh)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = max(contours, key=cv2.contourArea, default=None)

    if largest is not None:
        area = cv2.contourArea(largest)
        if area >= min_area_threshold:
            return int(area), total_area

    return 0, total_area

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

# ─────────────── Classification ───────────────
def classify_image(image_path):
    img = keras_image.load_img(image_path, target_size=(128, 128))
    img_array = keras_image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) / 255.0

    predictions = model.predict(img_array, verbose=0)
    predicted_index = int(np.argmax(predictions, axis=1)[0])
    predicted_name = class_names[predicted_index]

    return {
        "id": predicted_index,
        "name": predicted_name
    }, predicted_name.split("___")[0]

# ─────────────── S3 Image Lookup ───────────────
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

    image_keys.sort(
        key=lambda key: s3.head_object(Bucket=BUCKET_NAME, Key=key)["LastModified"],
        reverse=True
    )
    return image_keys[0]

# ─────────────── Process Latest Image ───────────────
def process_latest_image():
    history = download_json(JSON_S3_KEY, LOCAL_JSON)
    latest_key = find_latest_image_in_s3()
    if not latest_key:
        raise FileNotFoundError("No image found in S3")

    # Check if image was already processed (deduplication)
    for plant_entries in history.values():
        for e in plant_entries:
            if os.path.basename(e["file_name_image"]) == os.path.basename(latest_key):
                print("[INFO] Image already processed:", latest_key)
                return e, latest_key

    download_from_s3(latest_key, LATEST_IMAGE_NAME)
    disease_class, plant_name = classify_image(LATEST_IMAGE_NAME)

    previous_entry = history.get(plant_name, [])[-1] if plant_name in history else None

    if previous_entry:
        previous_key = previous_entry["file_name_image"]
        download_from_s3(previous_key, PREVIOUS_IMAGE_NAME)
        compare_data = compare_images(LATEST_IMAGE_NAME, PREVIOUS_IMAGE_NAME, MIN_AREA_THRESHOLD)
    else:
        area, _ = extract_largest_object(cv2.imread(LATEST_IMAGE_NAME), MIN_AREA_THRESHOLD)
        compare_data = {"current_day_px": area, "growth": 0}

    new_entry = {
        "date": datetime.utcnow().isoformat(),
        "file_name_image": latest_key,
        "size_compare": compare_data,
        "disease_class": disease_class
    }

    history.setdefault(plant_name, []).append(new_entry)

    with open(LOCAL_JSON, "w") as f:
        json.dump(history, f, indent=2)

    upload_to_s3(LOCAL_JSON, JSON_S3_KEY)

    return new_entry, latest_key

# ─────────────── Growth Series Helper ───────────────
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