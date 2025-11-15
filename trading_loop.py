import time
import datetime
from binance.exceptions import BinanceAPIException  # kept in case you use later

from lib.vars import (
    symbol,
    trade_amount,
    take_profit,
    stop_loss,
    loop_interval,
)
from lib.market_data import get_futures_price, get_data
from lib.telegram_bot import send_message_sync
from lib.signals import signals
from lib.position_manager import PositionManager

LTF_TIMEFRAME = "5m"    # your trading timeframe
HTF_TIMEFRAME = "15m"   # higher timeframe (4x higher recommended)

last_score_time = 0
cached_signal = None
score_update_interval = 300   # 5 minutes

# Use your advanced PositionManager
pm = PositionManager()

def confirm_signal_performance(ltf_score, htf_score):
    """
    Highest winrate MTF confirmation method.
    
    Combines lower timeframe (fast signals)
    with higher timeframe (trend stability).
    """

    # Reinforced Score: 65% LTF + 35% HTF
    reinforced = (0.65 * ltf_score) + (0.35 * htf_score)

    print(f"🔁 Reinforced Score = {reinforced:.3f}")

    # Optimized thresholds
    if reinforced >= 0.64:
        return "BUY"
    elif reinforced <= 0.36:
        return "SELL"
    else:
        return None  # No trade

def trading_loop():
    send_message_sync(f"🚀 Trading loop started for <b>{symbol}</b> (Futures)")
    print(f"🚀 Trading loop started for {symbol}")

    global last_score_time
    global cached_signal

    while True:
        try:
            # ------------------ PRICE ------------------
            mark_price = get_futures_price(symbol)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Mark Price: {mark_price}")

            if mark_price is None:
                time.sleep(loop_interval)
                continue

            # ------------------ AUTO TP/SL / BE ------------------
            pm.check_auto_close(mark_price)

            # ------------------ COOLDOWN CHECK ------------------
            if pm.cooldown_until is not None:
                now = datetime.datetime.utcnow()
                if now < pm.cooldown_until:
                    remaining = int((pm.cooldown_until - now).total_seconds())
                    print(f"⏳ Cooldown active ({remaining}s left). Skipping new entries.")
                    time.sleep(loop_interval)
                    continue

            # ------------------ MTF SCORE UPDATE (EVERY 5 MIN) ------------------
            current_ts = time.time()

            if current_ts - last_score_time >= score_update_interval:

                print("🧮 Updating LTF + HTF scores...")

                df_ltf = get_data(symbol, timeframe=LTF_TIMEFRAME)
                df_htf = get_data(symbol, timeframe=HTF_TIMEFRAME)

                ltf_score = technical_score(df_ltf, symbol)
                htf_score = technical_score(df_htf, symbol)

                cached_signal = confirm_signal_performance(ltf_score, htf_score)

                last_score_time = current_ts

                print(f"📊 LTF={ltf_score:.3f}, HTF={htf_score:.3f} → Final={cached_signal}")

            # Always use the last known signal
            signal = cached_signal
            print(f"➡️ Reinforced Signal: {signal}")

            # ------------------ ENTRY / EXIT ------------------
            if pm.position is None:
                if signal == "BUY":
                    pm.open_position("BUY", mark_price, trade_amount, take_profit, stop_loss)

                elif signal == "SELL":
                    pm.open_position("SELL", mark_price, trade_amount, take_profit, stop_loss)

            else:
                if signal == "CLOSE":
                    pm.close_position(price=mark_price)

            time.sleep(loop_interval)

        except KeyboardInterrupt:
            print("🛑 Trading loop stopped by user.")
            break

        except Exception as e:
            print(f"⚠️ Error in trading_loop: {e}")
            send_message_sync(f"⚠️ Error in trading_loop: {e}")
            time.sleep(loop_interval)
