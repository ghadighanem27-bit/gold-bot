
import datetime
import os
import sys
import yaml
from threading import Thread

# Internal imports
from lib.vars import cfg
from trading_loop import trading_loop
from lib.telegram_bot import start_telegram_listener
from lib.database_manager import get_connection

# Allow emojis in console
sys.stdout.reconfigure(encoding='utf-8')

print(f"🚀 Starting trading bot for {cfg["symbol"]}")

#✅ Check connection with database
try:
    conn = get_connection()
    print("✅ Database connection successful")
    conn.close()
except Exception as e:
    print("❌ Database connection failed:", e)

# ✅ Start Telegram listener in a background thread
if __name__ == "__main__":
    # Start trading in background
    Thread(target=trading_loop, daemon=True).start()

    # Run Telegram polling in main thread (no loop errors)
    start_telegram_listener()   # normal app.run_polling()
