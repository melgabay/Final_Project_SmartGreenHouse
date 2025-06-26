import tkinter as tk
from PIL import Image, ImageTk
import os

def on_image_click(event):
    """
    Called when the image is clicked.
    Displays the (x, y) coordinates of the click.
    """
    x, y = event.x, event.y
    print(f"Click detected at position: (x={x}, y={y})")
    # You can expand this function to:
    # - Store the coordinates in a list
    # - Update a label in the GUI
    # - Pass the coordinates to another function

def open_image_and_capture_click(image_path):
    """
    Opens a Tkinter window to display an image and capture mouse clicks.

    Args:
        image_path (str): Path to the image file.
    """
    if not os.path.exists(image_path):
        print(f"Error: The image file '{image_path}' was not found.")
        return

    try:
        # 1. Create the main window
        root = tk.Tk()
        root.title("Click on the image to get coordinates")

        # 2. Load the image using Pillow
        original_image = Image.open(image_path)
        photo = ImageTk.PhotoImage(original_image)

        # 3. Create a Canvas to display the image
        canvas = tk.Canvas(root, width=photo.width(), height=photo.height())
        canvas.pack()

        # 4. Show the image in the Canvas
        canvas.create_image(0, 0, image=photo, anchor=tk.NW)

        # 5. Bind mouse click event to the handler function
        canvas.bind("<Button-1>", on_image_click)

        # Keep a reference to the image to avoid garbage collection
        canvas.image = photo

        # 6. Start the Tkinter main loop
        root.mainloop()

    except Exception as e:
        print(f"An error occurred while loading the image or initializing Tkinter: {e}")

# --- Example usage ---
test_image_file = "image_c0_2025-06-17_18-37-54.jpg"

if os.path.exists(test_image_file):
    open_image_and_capture_click(test_image_file)
else:
    print(f"Test image '{test_image_file}' not found.")