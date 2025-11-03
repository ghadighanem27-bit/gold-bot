# lib/telegram_bot.py
import requests
from lib.vars import cfg

def send_telegram_message(text):
    """Send a message via your Telegram bot."""
    token = cfg["telegram_bot_token"]
    chat_id = cfg["telegram_chat_id"]

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    try:
        r = requests.post(url, data=payload)
        if r.status_code != 200:
            print(f"⚠️ Telegram error: {r.text}")
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")