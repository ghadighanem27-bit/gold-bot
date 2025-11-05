# lib/telegram_bot.py
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from lib.vars import cfg
from lib.database_manager import get_stats
import asyncio, threading

bot = Bot(token=cfg["telegram_bot_token"])

# --- Create and start a persistent event loop in a background thread ---
loop = asyncio.new_event_loop()
def start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

# --- Async send function ---
async def send_telegram_message(text):
    chat_id = cfg["telegram_chat_id"]
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")

# --- Sync wrapper ---
def send_message_sync(text):
    """Schedules Telegram send safely."""
    try:
        asyncio.run_coroutine_threadsafe(send_telegram_message(text), loop)
    except RuntimeError as e:
        print(f"⚠️ Telegram loop error: {e}")


# --- Command: /stats ---
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

# --- Run the command listener ---
def start_telegram_listener():
    app = Application.builder().token(bot).build()
    app.add_handler(CommandHandler("stats", stats_command))
    print("🤖 Telegram listener started...")
    app.run_polling()