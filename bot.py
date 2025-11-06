
import datetime
import os
import sys
import yaml
from threading import Thread

# Internal imports
from lib.vars import cfg
from trading_loop import trading_loop
from telegram_bot import start_telegram_listener

# Allow emojis in console
sys.stdout.reconfigure(encoding='utf-8')
print(f"🚀 Starting trading bot for {cfg["symbol"]}")

# ✅ Start Telegram listener in a background thread
Thread(target=start_telegram_listener, daemon=True).start()