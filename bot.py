import time
import datetime
import os
import sys
import yaml
from threading import Thread

# Internal imports
from lib.market_data import get_data
from lib.indicators import technical_score
from lib.signals import log_signal, signals
from lib.position_manager import PositionManager
from lib.database_manager import record_trade
from lib.vars import symbol, loop_interval, trade_amount, take_profit, stop_loss
from telegram_bot import start_telegram_listener

# Allow emojis in console
sys.stdout.reconfigure(encoding='utf-8')

print(f"🚀 Starting trading bot for {symbol}")

# ✅ Start Telegram listener in a background thread
Thread(target=start_telegram_listener, daemon=True).start()

# Initialize position manager
pm = PositionManager()

while True:
    # 1️⃣ Fetch latest data
    df = get_data(symbol)
    price = df['c'].iloc[-1]
    score = technical_score(df)

    # 2️⃣ Check open position (for TP/SL auto close)
    pm.check_auto_close(price)

    # 3️⃣ Evaluate signals
    signals(score, price, symbol, pm, trade_amount, take_profit, stop_loss)

    # 4️⃣ Wait until next iteration
    time.sleep(loop_interval)
