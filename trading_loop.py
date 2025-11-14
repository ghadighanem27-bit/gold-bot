import time
from datetime import datetime, timedelta

from lib.market_data import get_data, get_price, get_usdt_balance
from lib.indicators import technical_score
from lib.signals import signals
from lib.position_manager import PositionManager
from lib.vars import (
    cfg,
    symbol,
    take_profit,
    stop_loss,
    price_interval,
    indicator_interval
)

def trading_loop():
    pm = PositionManager()
    print("🌀 Trading loop started...")

    last_indicator_update = datetime.utcnow()

    while True:

        # ---------------------------------------------------------
        # FAST LOOP — Price update every X seconds
        # ---------------------------------------------------------
        try:
            price = get_price(symbol)
            pm.check_auto_close(price, symbol)

            # Heartbeat (optional)
            print(f"[{datetime.utcnow()}] Price: {price}")

        except Exception as e:
            print(f"⚠️ Price update error: {e}")

        # Recalculate dynamic trade size
        balance = get_usdt_balance()
        risk_pct = cfg.get("risk_percentage", 0.01)
        trade_value_usdt = balance * risk_pct
        trade_amount = trade_value_usdt / price


        # ---------------------------------------------------------
        # SLOW LOOP — Indicators every Y seconds
        # ---------------------------------------------------------
        now = datetime.utcnow()

        if now - last_indicator_update >= timedelta(seconds=indicator_interval):

            try:
                print("📡 Updating indicators + running signals...")
                df = get_data(symbol)
                signals(df, price, symbol, pm, trade_amount, take_profit, stop_loss)

            except Exception as e:
                print(f"⚠️ Indicator update error: {e}")

            last_indicator_update = now


        # ---------------------------------------------------------
        # Sleep until next price check
        # ---------------------------------------------------------
        time.sleep(price_interval)
