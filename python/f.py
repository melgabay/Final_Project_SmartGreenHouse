import tensorflow as tf
import os

# Load the original model
model = tf.keras.models.load_model("plant_village_CNN.h5")

# Create a "light" version without the optimizer
model.save("plant_village_CNN_light.h5", include_optimizer=False)

# Convert the model to TensorFlow Lite format
converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()
with open("plant_village_CNN.tflite", "wb") as f:
    f.write(tflite_model)

# Print the file sizes
print("Original size:", os.path.getsize("plant_village_CNN.h5") / (1024 * 1024), "MB")
print("Light version:", os.path.getsize("plant_village_CNN_light.h5") / (1024 * 1024), "MB")
print("TFLite version:", os.path.getsize("plant_village_CNN.tflite") / (1024 * 1024), "MB")