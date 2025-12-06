
import requests
from io import BytesIO
from PIL import Image
import os

url = "https://www.mi.fu-berlin.de/assets/default2/favicon-12a6f1b0e53f527326498a6bfd4c3abd.ico"
output_path = "c:\\Users\\rharv\\Desktop\\Programming\\fu-info-ubersicht\\assets\\fu-berlin-icon.png"

try:
    print(f"Downloading from {url}...")
    response = requests.get(url)
    response.raise_for_status()
    
    print("Download successful. Converting to PNG...")
    img = Image.open(BytesIO(response.content))
    img.save(output_path, "PNG")
    print(f"Successfully saved to {output_path}")

except ImportError:
    print("PIL/Pillow not installed. Creating a dummy placeholder or checking if we can save directly.")
    # Fallback if PIL is missing: just save raw bytes if it was a PNG, but it's an ICO.
    # We really need PIL for ICO -> PNG.
    print("Please install Pillow: pip install Pillow")
except Exception as e:
    print(f"Error: {e}")
