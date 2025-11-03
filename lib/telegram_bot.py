from telegram import Bot
from lib.vars import cfg
import asyncio

bot = Bot(token=cfg["telegram_bot_token"])

async def send_telegram_message(text):
    chat_id = cfg["telegram_chat_id"]
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")

def send_message_sync(text):
    asyncio.run(send_telegram_message(text))