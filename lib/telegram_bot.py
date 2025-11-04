from telegram import Bot
from lib.vars import cfg
import asyncio

bot = Bot(token=cfg["telegram_bot_token"])

# Create one persistent loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

async def send_telegram_message(text):
    chat_id = cfg["telegram_chat_id"]
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")

def send_message_sync(text):
    """Safe synchronous wrapper for Telegram send."""
    try:
        loop.create_task(send_telegram_message(text))
    except RuntimeError as e:
        print(f"⚠️ Telegram loop error: {e}")