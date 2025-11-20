import time
import datetime

from lib.vars import (
    symbol,
    trade_amount,
    take_profit,
    stop_loss,
    loop_interval,
)

from lib.market_data import get_futures_price, get_data
from lib.database_manager import record_score
from lib.telegram_bot import send_message_sync
from lib.position_manager import PositionManager
from lib.indicators import technical_score
from lib.signals import signals

# Timeframes
LTF_TIMEFRAME = "5m"
HTF_TIMEFRAME = "15m"

# Only update score every 5 minutes
score_update_interval = 300

last_score_time = 0
last_score = None

pm = PositionManager()


def trading_loop():
    send_message_sync(f"🚀 Trading loop started for <b>{symbol}</b>")
    print(f"🚀 Trading loop started for {symbol}")

    global last_score_time
    global last_score

    while True:
        try:
            # ------------------- PRICE -------------------
            price = get_futures_price(symbol)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Mark Price: {price}")

            if price is None:
                time.sleep(loop_interval)
                continue

            # Auto TP/SL checks
            pm.check_auto_close(price)

            # Cooldown check
            if pm.cooldown_until:
                now = datetime.datetime.utcnow()
                if now < pm.cooldown_until:
                    remaining = int((pm.cooldown_until - now).total_seconds())
                    print(f"⏳ Cooldown active ({remaining}s left)")
                    time.sleep(loop_interval)
                    continue

            # ------------------- SCORE UPDATE -------------------
            now_ts = time.time()

            if now_ts - last_score_time >= score_update_interval:

                print("🧮 Updating LTF + HTF scores...")

                df_ltf = get_data(symbol, interval=LTF_TIMEFRAME)
                df_htf = get_data(symbol, interval=HTF_TIMEFRAME)

                # Use your NEW scoring model (0–100)
                ltf_score = technical_score(df_ltf, symbol=symbol)
                htf_score = technical_score(df_htf, symbol=symbol)

                # MTF Blend (65% fast + 35% trend)
                blended = (0.65 * ltf_score) + (0.35 * htf_score)

                last_score = blended
                last_score_time = now_ts

                # Save in DB
                try:
                    record_score(
                        symbol=symbol,
                        ltf_score=float(ltf_score),
                        htf_score=float(htf_score),
                        reinforced_score=float(blended),
                        decision=None,
                        trade_id=None
                    )
                    print("✅ Score saved to DB.")
                except Exception as e:
                    print(f"⚠️ Failed to save score: {e}")

                print(f"📊 LTF={ltf_score:.2f} | HTF={htf_score:.2f} | Final Score={blended:.2f}")

            # If score not updated yet, skip
            if last_score is None:
                time.sleep(loop_interval)
                continue

            # ------------------- SIGNAL ROUTING -------------------
            decision = signals(
                df_ltf,         # send LTF dataframe
                price,
                symbol,
                pm,
                trade_amount,
                take_profit,
                stop_loss
            )

            print(f"➡️ Signal Result: {decision}")

            time.sleep(loop_interval)

        except Exception as e:
            print(f"⚠️ Error in trading_loop: {e}")
            send_message_sync(f"⚠️ Error in trading_loop: {e}")
            time.sleep(loop_interval)
