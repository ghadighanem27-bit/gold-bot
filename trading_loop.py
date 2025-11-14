import time
from datetime import datetime, timedelta

from lib.market_data import (
    get_data,
    get_usdt_balance,
    get_futures_price   # NEW: correct Binance Futures mark price
)

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
    print("🌀 Trading loop started using MARK PRICE...")

    last_indicator_update = datetime.utcnow()

    while True:

        ###############################################
        # 1) FAST LOOP — MARK PRICE every X seconds
        ###############################################
        try:
            price = get_futures_price(symbol)

            if price is None:
                print("⚠️ Could not fetch mark price. Retrying...")
                time.sleep(price_interval)
                continue

            # Auto-close logic ALWAYS uses mark price
            pm.check_auto_close(price, symbol)

            print(f"[{datetime.utcnow()}] MARK PRICE: {price}")

        except Exception as e:
            print(f"⚠️ Price update error: {e}")

        ###############################################
        # 2) Dynamic position sizing (safe compounding)
        ###############################################
        try:
            balance = get_usdt_balance()
            risk_pct = cfg.get("risk_percentage", 0.01)

            trade_value_usdt = balance * risk_pct
            trade_amount = trade_value_usdt / price

        except Exception as e:
            print(f"⚠️ Balance/position sizing error: {e}")
            trade_amount = 0.01  # fail-safe

        ###############################################
        # 3) SLOW LOOP — Indicators every Y seconds
        ###############################################
        now = datetime.utcnow()

        if now - last_indicator_update >= timedelta(seconds=indicator_interval):

            try:
                print("\n📡 Updating indicators + running signals…")

                df = get_data(symbol)

                # ALWAYS pass mark price here
                signals(df, price, symbol, pm, trade_amount, take_profit, stop_loss)

            except Exception as e:
                print(f"⚠️ Indicator update error: {e}")

            last_indicator_update = now

        ###############################################
        # 4) Sleep until next tick
        ###############################################
        time.sleep(price_interval)
