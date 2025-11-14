import time
from datetime import datetime, timedelta

from lib.market_data import get_data, get_price
from lib.indicators import technical_score
from lib.signals import signals
from lib.position_manager import PositionManager

from lib.vars import (
    symbol,
    trade_amount,
    take_profit,
    stop_loss,
    price_interval,        # from YAML (e.g. 5)
    indicator_interval,    # from YAML (e.g. 300 = 5 min)
)


def trading_loop():
    pm = PositionManager()
    print("🌀 Trading loop started...")

    last_indicator_update = datetime.utcnow()

    while True:

        # ---------------------------------------------------------
        # 1) FAST LOOP  → Price update every 5 seconds
        # ---------------------------------------------------------
        try:
            price = get_price(symbol)
            pm.check_auto_close(price)     # TP/SL always checked
        except Exception as e:
            print(f"⚠️ Price update error: {e}")

        # ---------------------------------------------------------
        # 2) SLOW LOOP → Indicators/signals every 5 minutes
        #   (EVEN IF A TRADE IS OPEN)
        # ---------------------------------------------------------
        now = datetime.utcnow()

        if now - last_indicator_update >= timedelta(seconds=indicator_interval):

            try:
                df = get_data(symbol)

                # Recalculate technical indicators
                score = technical_score(df)

                # Run BUY/SELL logic every 5 min
                signals(df, price, symbol, pm, trade_amount, take_profit, stop_loss)

                print(f"📊 Indicators + signals updated at {now}")

            except Exception as e:
                print(f"⚠️ Indicator update error: {e}")

            last_indicator_update = now

        # ---------------------------------------------------------
        # 3) Wait for next 5-second tick
        # ---------------------------------------------------------
        time.sleep(price_interval)