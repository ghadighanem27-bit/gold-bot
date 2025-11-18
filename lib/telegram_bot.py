from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from lib.vars import cfg
import threading

# -------------------------------------------------------------
# Telegram config
# -------------------------------------------------------------
bot_token = cfg["telegram"]["bot_token"]
chat_id = cfg["telegram"]["chat_id"]

bot = Bot(token=bot_token)

# -------------------------------------------------------------
# Persistent event loop for async sending
# -------------------------------------------------------------
loop = asyncio.new_event_loop()

def _start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=_start_loop, daemon=True).start()

# -------------------------------------------------------------
# Async send function
# -------------------------------------------------------------
async def send_telegram_message(text: str):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")

# -------------------------------------------------------------
# Sync wrapper used by trading logic
# -------------------------------------------------------------
def send_message_sync(text: str):
    try:
        asyncio.run_coroutine_threadsafe(send_telegram_message(text), loop)
    except RuntimeError as e:
        print(f"⚠️ Telegram loop error: {e}")

# -------------------------------------------------------------
# /start command
# -------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Hello! I'm your trading bot.\n"
        "Use /stats to see performance."
    )

# -------------------------------------------------------------
# /stats command
# -------------------------------------------------------------
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Stats feature is disabled temporarily.")

# -------------------------------------------------------------
# Telegram listener (for bot.py)
# -------------------------------------------------------------
"""
def start_telegram_listener():
    if not bot_token:
        print("⚠️ No Telegram bot token configured, listener not started.")
        return

    app = Application.builder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))

    print("🤖 Telegram listener started...")
    app.run_polling(stop_signals=None, drop_pending_updates=True)

# Standalone run (optional)
if __name__ == "__main__":
    start_telegram_listener()
"""
