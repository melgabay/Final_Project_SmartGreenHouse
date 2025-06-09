import os
import json
import cv2
import numpy as np
from datetime import datetime
import boto3
from tensorflow.keras.preprocessing import image as keras_image
import tensorflow as tf
import tensorflow_datasets as tfds
from matplotlib import pyplot as plt

# Load Trained CNN Model
model = tf.keras.models.load_model('../smart-greenhouse-login/plant_village_CNN.h5')
ds_info = tfds.builder('plant_village').info
class_names = ds_info.features['label'].names

# AWS S3 Setup
BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

#  Helper: Download from S3
def download_from_s3(key, local_path):
    s3.download_file(BUCKET_NAME, key, local_path)

#  Load or Initialize JSON Data
def download_json(json_key, local_path):
    try:
        download_from_s3(json_key, local_path)
        with open(local_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error downloading or loading JSON: {e}")
        data = {}
        with open(local_path, "w") as f:
            json.dump(data, f, indent=2)
    return data

#  Upload JSON Back to S3
def upload_json(local_path, json_key):
    s3.upload_file(local_path, BUCKET_NAME, json_key)

# Get Latest Image Key in S3
def find_last_image_in_s3(prefix="plant_images/"):
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    if "Contents" not in response:
        return None

    all_files = [
        obj["Key"]
        for obj in response["Contents"]
        if obj["Key"].lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    if not all_files:
        return None

    all_files.sort(key=lambda x: s3.head_object(Bucket=BUCKET_NAME, Key=x)["LastModified"], reverse=True)
    return all_files[0]

# Extract Object Area in Image
def extract_largest_object(image, opacity=0.3, min_area_threshold=500):
    height, width = image.shape[:2]
    total_area = height * width

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if np.mean(gray[thresh == 255]) > np.mean(gray[thresh == 0]):
        thresh = cv2.bitwise_not(thresh)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest_contour = max(contours, key=cv2.contourArea, default=None)

    object_area = 0
    if largest_contour is not None:
        area = cv2.contourArea(largest_contour)
        if area >= min_area_threshold:
            object_area = int(area)

    return object_area, total_area

# Compare Two Images
def compare_images(image1_path, image2_path, min_area_threshold=500):
    img1 = cv2.imread(image1_path)
    img2 = cv2.imread(image2_path)

    area1, total1 = extract_largest_object(img1, min_area_threshold=min_area_threshold)
    area2, total2 = extract_largest_object(img2, min_area_threshold=min_area_threshold)

    ratio1 = (area1 / total1) * 100 if total1 else 0
    ratio2 = (area2 / total2) * 100 if total2 else 0

    growth = 0
    if area1 and area2:
        growth = 1 if ratio1 > ratio2 else -1 if ratio2 > ratio1 else 0

    return {
        "current_day_px": area1,
        "growth": growth
    }

# Growth-graph helper
def get_growth_series(plant_name: str, limit: int = 30,
                      json_key: str = "plant_data.json") -> list[dict]:
    local_json = "plant_data.json"
    download_json(json_key, local_json)

    with open(local_json) as f:
        history = json.load(f)

    if plant_name not in history:
        return []

    entries = sorted(history[plant_name], key=lambda e: e["date"])
    series = []
    prev_px = None

    for entry in entries[-limit:]:
        px = entry["size_compare"]["current_day_px"]
        growth = 0 if prev_px is None else px - prev_px
        series.append({
            "timestamp": entry["date"],
            "current_px": px,
            "growth_px": growth
        })
        prev_px = px

    return series

# Classify Image Using CNN Model
def analyse_image(image_path):
    img = keras_image.load_img(image_path, target_size=(128, 128))
    img_array = keras_image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) / 255.0

    predictions = model.predict(img_array)
    predicted_index = int(np.argmax(predictions, axis=1)[0])
    predicted_name = class_names[predicted_index]

    return {
        "id": predicted_index,
        "name": predicted_name
    }, predicted_name.split("___")[0]

# Main Processing Pipeline
def process_latest_image():
    json_key = "plant_data.json"
    local_json = "plant_data.json"

    history = download_json(json_key, local_json)
    last_image_key = find_last_image_in_s3()
    if not last_image_key:
        raise FileNotFoundError("No images found in S3 under 'plant_images/'")

    local_image = "latest_plant.jpg"
    download_from_s3(last_image_key, local_image)

    disease_class, plant_name = analyse_image(local_image)

    plant_data = history.get(plant_name, [])
    previous_entry = plant_data[-1] if plant_data else None

    compare_data = {"current_day_px": 0, "growth": 0}
    if previous_entry:
        prev_image_key = previous_entry["file_name_image"]
        local_prev_image = "previous_plant.jpg"
        download_from_s3(prev_image_key, local_prev_image)
        compare_data = compare_images(local_image, local_prev_image, min_area_threshold=500)
    else:
        area, _ = extract_largest_object(cv2.imread(local_image), min_area_threshold=500)
        compare_data["current_day_px"] = area
        compare_data["growth"] = 0

    new_entry = {
        "date": datetime.utcnow().isoformat(),
        "file_name_image": last_image_key,
        "size_compare": compare_data,
        "disease_class": disease_class
    }

    if plant_name not in history:
        history[plant_name] = []
    history[plant_name].append(new_entry)

    with open(local_json, "w") as f:
        json.dump(history, f, indent=2)

    upload_json(local_json, json_key)

    return new_entry, last_image_key