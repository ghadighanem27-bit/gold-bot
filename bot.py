import time
import datetime
import os
import sys
import yaml

# Internal imports
from lib.market_data import get_data
from lib.indicators import technical_score
from lib.signals import log_signal
from lib.vars import client, symbol, loop_interval

# Allow emojis in console
sys.stdout.reconfigure(encoding='utf-8')

def market_is_closed():
    """Return True if it's Saturday or Sunday (UTC)."""
    today = datetime.datetime.utcnow().weekday()  # Monday=0 ... Sunday=6
    return today in [5, 6]

print(f"🚀 Starting trading bot for {symbol}")

while True:
    """
    if market_is_closed():
        print("🕒 Market closed (weekend). Sleeping 1 hour...")
        time.sleep(3600)
        continue
        """

    df = get_data(symbol)
    price = df['c'].iloc[-1]
    score = technical_score(df)
    print(f"📊 Total technical score: {score:.2f}")

    # Simple example of acting on score
    if score >= 40:
        print("🟢 BUY | Price: {price:.2f}")
        log_signal("🟢 BUY", score, price)
    elif score <= 25:
        print("🔴 SELL | Price: {price:.2f}")
        log_signal("🔴 SELL", score, price)
    else:
        print("⚪ HOLD | Price: {price:.2f}")

    time.sleep(loop_interval)





