import time
from datetime import datetime, timedelta

from lib.market_data import get_data, get_price
from lib.indicators import technical_score
from lib.signals import signals
from lib.position_manager import PositionManager
from lib.market_data import get_usdt_balance
from lib.vars import cfg

from lib.vars import (
    symbol,
    take_profit,
    stop_loss,
    price_interval,        # e.g., 5 seconds
    indicator_interval,    # e.g., 300 seconds
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
            pm.check_auto_close(price, symbol)
        except Exception as e:
            print(f"⚠️ Price update error: {e}")
            time.sleep(price_interval)
            continue

        # ---------------------------------------------------------
        # 2) SLOW LOOP → Indicators + signal evaluations (5 min)
        # ---------------------------------------------------------
        now = datetime.utcnow()

        if now - last_indicator_update >= timedelta(seconds=indicator_interval):

            try:
                df = get_data(symbol)

                # Recalculate technical indicators
                score = technical_score(df)

                # -----------------------------------------
                # 💰 COMPOUNDING → recalculate trade size
                # -----------------------------------------
                balance = get_usdt_balance()
                risk_pct = cfg.get("risk_percentage", 0.01)  # default 1% risk
                trade_value_usdt = balance * risk_pct

                # Convert USDT → ETH amount
                trade_amount = trade_value_usdt / price

                print(f"💰 Dynamic trade amount: {trade_amount:.6f} ETH "
                      f"(Balance={balance:.2f} USDT, Risk={risk_pct*100:.1f}%)")

                # Run BUY/SELL logic
                signals(df, price, symbol, pm, trade_amount, take_profit, stop_loss)

                print(f"📊 Indicators + signals updated at {now}")

            except Exception as e:
                print(f"⚠️ Indicator update error: {e}")

            last_indicator_update = now

        # ---------------------------------------------------------
        # 3) Wait for next 5-second tick
        # ---------------------------------------------------------
        time.sleep(price_interval)
