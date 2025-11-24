import os
import requests

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
PHOTO_PATH = "logo_mbb.jpg"  # مسیر عکس
CAPTION = "پیام انگیزشی امروز 🌟"

url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
with open(PHOTO_PATH, "rb") as photo:
    requests.post(url, data={"chat_id": CHANNEL_ID, "caption": CAPTION}, files={"photo": photo})
