import os
import json
import cv2
from datetime import datetime
from tensorflow.keras.preprocessing import image as keras_image
import numpy as np
import tensorflow as tf
import tensorflow_datasets as tfds
import boto3

# Configuration
IMAGE_FOLDER = "/Users/melissagabay/Documents/Final/plant image"
JSON_PATH = "/Users/melissagabay/Documents/Final/python/plant_data.json"
MIN_AREA_THRESHOLD = 500  # toujours respecté

# Modèle
model = tf.keras.models.load_model('../smart-greenhouse-login/plant_village_CNN.h5')
ds_info = tfds.builder('plant_village').info
class_names = ds_info.features['label'].names

# JSON existant
if os.path.exists(JSON_PATH):
    with open(JSON_PATH, "r") as f:
        history = json.load(f)
else:
    history = {}

# Client S3
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

def upload_json_to_s3(local_path, s3_key, bucket_name):
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"S3 upload successful → s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print("❌ Failed to upload to S3:", e)

# Extraction
def extract_largest_object(image, min_area_threshold=500):
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

def compare_images(current_path, previous_path, min_area_threshold=500):
    img1 = cv2.imread(current_path)
    img2 = cv2.imread(previous_path)

    area1, total1 = extract_largest_object(img1, min_area_threshold)
    area2, total2 = extract_largest_object(img2, min_area_threshold)

    ratio1 = (area1 / total1) * 100 if total1 else 0
    ratio2 = (area2 / total2) * 100 if total2 else 0

    growth = 1 if ratio1 > ratio2 else -1 if ratio2 > ratio1 else 0

    return {
        "current_day_px": area1,
        "growth": growth
    }

def analyze_image(image_path):
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

# Traitement des images
for filename in sorted(os.listdir(IMAGE_FOLDER)):
    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        image_path = os.path.join(IMAGE_FOLDER, filename)

        try:
            disease_class, plant_name = analyze_image(image_path)

            # Vérifier si déjà analysé
            already_logged = any(entry["file_name_image"] == image_path for entry in history.get(plant_name, []))
            if already_logged:
                print(f"⏭️ {filename} déjà présent, ignoré.")
                continue

            previous_entry = history.get(plant_name, [])[-1] if history.get(plant_name) else None

            if previous_entry:
                prev_path = os.path.join(IMAGE_FOLDER, os.path.basename(previous_entry["file_name_image"]))
                compare_data = compare_images(image_path, prev_path, MIN_AREA_THRESHOLD)
            else:
                area, _ = extract_largest_object(cv2.imread(image_path), MIN_AREA_THRESHOLD)
                compare_data = {"current_day_px": area, "growth": 0}

            entry = {
                "date": datetime.utcnow().isoformat(),
                "file_name_image": image_path,
                "size_compare": compare_data,
                "disease_class": disease_class
            }

            if plant_name not in history:
                history[plant_name] = []
            history[plant_name].append(entry)

            print(f"✅ {filename} analysé → {plant_name} ({disease_class['name']})")

        except Exception as e:
            print(f"❌ Erreur avec {filename}:", e)

# Tri final par date pour chaque plante
for plant_name, entries in history.items():
    history[plant_name] = sorted(
        entries,
        key=lambda x: x["date"]
    )

# Enregistrement JSON
with open(JSON_PATH, "w") as f:
    json.dump(history, f, indent=2)
print(f"\n💾 Analyse terminée. Données enregistrées dans: {JSON_PATH}")

# ✅ Upload vers S3 juste après
upload_json_to_s3(
    local_path=JSON_PATH,
    s3_key="plant_data.json",
    bucket_name=os.getenv("AWS_BUCKET_NAME")
)