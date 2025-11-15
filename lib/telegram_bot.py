# lib/telegram_bot.py

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from lib.vars import cfg
from lib.database_manager import get_stats
import asyncio, threading

# -------------------------------------------------------------
# Telegram config (NEW STRUCTURE)
# -------------------------------------------------------------
bot_token = cfg["telegram"]["bot_token"]
chat_id = cfg["telegram"]["chat_id"]

bot = Bot(token=bot_token)

# -------------------------------------------------------------
# Persistent event loop for async sending
# -------------------------------------------------------------
loop = asyncio.new_event_loop()

def start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

# -------------------------------------------------------------
# Async send function
# -------------------------------------------------------------
async def send_telegram_message(text):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")

# -------------------------------------------------------------
# Sync wrapper (for use inside bot logic)
# -------------------------------------------------------------
def send_message_sync(text):
    """Thread-safe scheduling of Telegram messages."""
    try:
        asyncio.run_coroutine_threadsafe(send_telegram_message(text), loop)
    except RuntimeError as e:
        print(f"⚠️ Telegram loop error: {e}")

# -------------------------------------------------------------
# /start command
# -------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Hello! I'm your trading bot interface.\n"
        "Use /stats to view performance."
    )

# -------------------------------------------------------------
# /stats command
# -------------------------------------------------------------
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_stats()
    message = (
        "📊 <b>BOT PERFORMANCE STATS</b>\n"
        "-----------------------------\n"
        f"🏆 Winrate: <b>{stats['winrate']:.2f}%</b>\n"
        f"📈 Average PnL: <b>{stats['avg_pnl']:.2f}%</b>\n"
        f"📊 Total Trades: <b>{stats['total_trades']}</b>\n"
        "-----------------------------"
    )
    await update.message.reply_text(message, parse_mode="HTML")

# -------------------------------------------------------------
# Telegram listener (polling)
# -------------------------------------------------------------
def start_telegram_listener():
    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))

    print("🤖 Telegram listener started...")
    app.run_polling(stop_signals=None, drop_pending_updates=True)

# -------------------------------------------------------------
# Standalone runner
# -------------------------------------------------------------
def main():
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN missing in config!")

    app = Application.builder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))

    print("🤖 Telegram bot server running...")
    app.run_polling()

if __name__ == "__main__":
    main()
