import tensorflow as tf
import os

# Charger le modèle
model = tf.keras.models.load_model("plant_village_CNN.h5")

# 🔹 Version "light" sans optimiseur
model.save("plant_village_CNN_light.h5", include_optimizer=False)

# 🔹 Version TFLite
converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()
with open("plant_village_CNN.tflite", "wb") as f:
    f.write(tflite_model)

# 🔹 Affiche les tailles de fichiers
print("Taille originale :", os.path.getsize("plant_village_CNN.h5") / (1024 * 1024), "Mo")
print("Version light :", os.path.getsize("plant_village_CNN_light.h5") / (1024 * 1024), "Mo")
print("Version TFLite :", os.path.getsize("plant_village_CNN.tflite") / (1024 * 1024), "Mo")