# lib/telegram_bot.py
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from lib.database_manager import get_stats
from lib.vars import cfg
import asyncio

# --- Command: /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Hello! I'm your trading bot.\n"
        "Type /stats to see performance metrics 📊"
    )

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

# --- Function to start Telegram listener ---
def start_telegram_listener():
    print("🤖 Telegram listener started...")

    async def main():
        app = Application.builder().token(cfg["telegram_bot_token"]).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("stats", stats_command))
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        # Keep bot alive
        await asyncio.Event().wait()

    asyncio.run(main())
