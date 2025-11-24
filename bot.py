import os
import requests

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # مثلا "@YourChannelUsername"
MESSAGE = "سلام! پیام انگیزشی امروز شما 🌟"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
requests.post(url, data={"chat_id": CHANNEL_ID, "text": MESSAGE})
