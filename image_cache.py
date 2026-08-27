import os
import requests
from io import BytesIO
from PIL import Image
import customtkinter as ctk

def get_app_dir():
    # Находим системную папку AppData/Local
    base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    app_dir = os.path.join(base_dir, "SetCompleter")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

# Папка с кэшем изображений
CACHE_DIR = os.path.join(get_app_dir(), "images_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cached_image(part_num, color_id, img_url, size=(80, 80)):
    """Кэширует и возвращает картинку конкретной детали определенного цвета"""
    if not img_url:
        return None
        
    filename = f"{part_num}_{color_id}.png"
    filepath = os.path.join(CACHE_DIR, filename)

    if not os.path.exists(filepath):
        try:
            response = requests.get(img_url, timeout=5)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                image.thumbnail((160, 160)) 
                image.save(filepath, format="PNG")
        except Exception as e:
            print(f"Ошибка загрузки изображения: {e}")
            return None

    if os.path.exists(filepath):
        try:
            img = Image.open(filepath)
            return ctk.CTkImage(light_image=img, dark_image=img, size=size)
        except Exception as e:
            print(f"Ошибка чтения кэша изображения: {e}")
            
    return None

def get_cached_set_image(set_num, img_url, size=(80, 80)):
    """Кэширует и возвращает картинку целого набора"""
    if not img_url:
        return None
        
    # Имя файла для набора
    filename = f"set_{set_num}.png"
    filepath = os.path.join(CACHE_DIR, filename)

    if not os.path.exists(filepath):
        try:
            response = requests.get(img_url, timeout=5)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                image.thumbnail((160, 160)) 
                image.save(filepath, format="PNG")
        except Exception as e:
            print(f"Ошибка загрузки картинки набора: {e}")
            return None

    if os.path.exists(filepath):
        try:
            img = Image.open(filepath)
            return ctk.CTkImage(light_image=img, dark_image=img, size=size)
        except Exception as e:
            print(f"Ошибка чтения кэша картинки набора: {e}")
            
    return None