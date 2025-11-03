import time
import datetime
import os
import sys
import yaml

# Internal imports
from lib.market_data import get_data
from lib.indicators import technical_score
from lib.signals import log_signal, signals
from lib.vars import client, symbol, loop_interval

# Allow emojis in console
sys.stdout.reconfigure(encoding='utf-8')

print(f"🚀 Starting trading bot for {symbol}")
position = "NULL"

while True:
    df = get_data(symbol)
    price = df['c'].iloc[-1]
    score = technical_score(df)

    signals(score, price, symbol)

    


    time.sleep(loop_interval)









