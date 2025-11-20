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
            # ---------------- PRICE ----------------
            price = get_futures_price(symbol)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Mark Price: {price}")

            if price is None:
                time.sleep(loop_interval)
                continue

            pm.check_auto_close(price)

            # ---------------- COOLDOWN ----------------
            if pm.cooldown_until:
                now = datetime.datetime.utcnow()
                if now < pm.cooldown_until:
                    remain = int((pm.cooldown_until - now).total_seconds())
                    print(f"⏳ Cooldown active ({remain}s).")
                    time.sleep(loop_interval)
                    continue

            # -------------------------------------------------------
            # 5-MINUTE TECHNICAL SCORE FETCH (IMPORTANT)
            # -------------------------------------------------------

            now_ts = time.time()
            if now_ts - last_score_time >= score_update_interval:

                print("🧮 Updating technical score on both LTF + HTF...")

                # Sleep BEFORE the DF fetch to avoid rate limits
                time.sleep(1.0)

                df_ltf = get_data(symbol, interval=LTF_TIMEFRAME)
                time.sleep(1.0)

                df_htf = get_data(symbol, interval=HTF_TIMEFRAME)
                time.sleep(1.0)

                # Compute your new 0–100 score
                ltf_score = technical_score(df_ltf, symbol)
                htf_score = technical_score(df_htf, symbol)

                blended_score = (0.65 * ltf_score) + (0.35 * htf_score)
                last_score = blended_score
                last_score_time = now_ts

                # Save
                try:
                    record_score(
                        symbol=symbol,
                        ltf_score=float(ltf_score),
                        htf_score=float(htf_score),
                        reinforced_score=float(blended_score),
                        decision=None,
                        trade_id=None
                    )
                    print("✅ Score saved to DB.")
                except Exception as e:
                    print(f"⚠️ Failed to save score: {e}")

                print(f"📊 Scores → LTF={ltf_score:.2f} | HTF={htf_score:.2f} | FINAL={blended_score:.2f}")

            # If score not updated yet → skip trading
            if last_score is None:
                time.sleep(loop_interval)
                continue

            # ---------------- SIGNAL LOGIC ----------------
            decision = signals(
                df_ltf,
                price,
                symbol,
                pm,
                trade_amount,
                take_profit,
                stop_loss
            )

            print(f"➡️ Signal = {decision}")

            # -------------------------------------------------------
            # END LOOP DELAY
            # -------------------------------------------------------
            time.sleep(loop_interval)

        except Exception as e:
            print(f"⚠️ Error: {e}")
            send_message_sync(f"⚠️ Error in trading_loop: {e}")
            time.sleep(loop_interval)
