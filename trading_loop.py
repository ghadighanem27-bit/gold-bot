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
from lib.indicators import technical_score
from lib.database_manager import record_score
from lib.telegram_bot import send_message_sync
from lib.position_manager import PositionManager
from lib.signals import signals

LTF_TIMEFRAME = "5m"
HTF_TIMEFRAME = "15m"

score_update_interval = 300  # 5 minutes
last_score_time = 0
last_score = None
last_ltf_df = None

pm = PositionManager()


def trading_loop():
    send_message_sync(f"🚀 Trading loop started for <b>{symbol}</b>")
    print(f"🚀 Trading loop started for {symbol}")

    global last_score_time, last_score, last_ltf_df

    while True:
        try:
            # ------------------- PRICE -------------------
            price = get_futures_price(symbol)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Mark Price: {price}")

            if price is None:
                time.sleep(loop_interval)
                continue

            # AUTO TP/SL
            pm.check_auto_close(price)
            pm.check_progressive_tp(price)

            # ------------------- COOLDOWN -------------------
            if pm.cooldown_until:
                now = datetime.datetime.utcnow()
                if now < pm.cooldown_until:
                    remain = int((pm.cooldown_until - now).total_seconds())
                    print(f"⏳ Cooldown active ({remain}s). Skipping.")
                    time.sleep(loop_interval)
                    continue

            # ---------------------------------------------------
            # UPDATE SCORE EVERY 5 MINUTES
            # ---------------------------------------------------
            now_ts = time.time()
            if now_ts - last_score_time >= score_update_interval:

                print("🧮 Updating technical score...")

                df_ltf = get_data(symbol, interval=LTF_TIMEFRAME)
                time.sleep(0.5)

                df_htf = get_data(symbol, interval=HTF_TIMEFRAME)
                time.sleep(0.5)

                last_ltf_df = df_ltf

                ltf_score = technical_score(df_ltf, symbol)
                htf_score = technical_score(df_htf, symbol)

                blended_score = (0.65 * ltf_score) + (0.35 * htf_score)
                last_score = blended_score
                last_score_time = now_ts

                entry_volatility = df_ltf["c"].pct_change().std() * 100
                entry_time = datetime.datetime.utcnow()

                try:
                    pm.last_score_id = record_score(
                        symbol=symbol,
                        ltf_score=float(ltf_score),
                        htf_score=float(htf_score),
                        reinforced_score=float(blended_score),
                        decision=None,
                        regime=None,
                        entry_volatility=float(entry_volatility),
                        entry_time=entry_time,
                        trade_id=None
                    )
                    print(f"✅ Score saved (ID={pm.last_score_id})")
                except Exception as e:
                    print(f"⚠️ Failed to save score: {e}")

                print(f"📊 LTF={ltf_score:.2f} | HTF={htf_score:.2f} | FINAL={blended_score:.2f}")

            if last_score is None:
                time.sleep(loop_interval)
                continue

            # ---------------------------------------------------
            # ✅ SIGNAL ENGINE (SOLE DECISION MAKER)
            # ---------------------------------------------------
            decision = signals(
                last_ltf_df,
                price,
                symbol,
                pm,
                trade_amount,
                take_profit,
                stop_loss
            )

            print(f"➡️ Signal = {decision}")

            time.sleep(loop_interval)

        except Exception as e:
            print(f"⚠️ Error in loop: {e}")
            send_message_sync(f"⚠️ Error in trading loop: {e}")
            time.sleep(loop_interval)
