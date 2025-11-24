import os
import requests

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
VIDEO_PATH = "VID.mp4"  # مسیر ویدئو
CAPTION = "ویدئوی انگیزشی امروز 🎬"

url = f"https://api.telegram.org/bot{TOKEN}/sendVideo"
with open(VIDEO_PATH, "rb") as video:
    requests.post(url, data={"chat_id": CHANNEL_ID, "caption": CAPTION}, files={"video": video})
