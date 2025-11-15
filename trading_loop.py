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


# Use your advanced PositionManager
pm = PositionManager()


def trading_loop():
    send_message_sync(f"🚀 Trading loop started for <b>{symbol}</b> (Futures)")
    print(f"🚀 Trading loop started for {symbol}")

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
            # Let PositionManager handle TP/SL/Breakeven and close if needed
            pm.check_auto_close(mark_price)

            # ------------------ COOLDOWN CHECK ------------------
            if pm.cooldown_until is not None:
                now = datetime.datetime.utcnow()
                if now < pm.cooldown_until:
                    remaining = int((pm.cooldown_until - now).total_seconds())
                    print(f"⏳ Cooldown active ({remaining}s left). Skipping new entries.")
                    time.sleep(loop_interval)
                    continue

            # ------------------ FETCH CANDLES FOR SIGNALS ------------------
            try:
                df = get_data(symbol)
            except Exception as e:
                print(f"⚠️ Failed to fetch candles: {e}")
                df = None

            # ------------------ CALL signals() ------------------
            try:
                signal = signals(
                    df=df,
                    price=mark_price,
                    symbol=symbol,
                    pm=pm,
                    trade_amount=trade_amount,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            except Exception as e:
                print(f"⚠️ Error calling signals(): {e}")
                signal = None

            print(f"➡️ Signal: {signal}")

            # ------------------ ENTRY / MANUAL EXIT LOGIC ------------------
            if pm.position is None:
                # No open position → only react to new entry signals
                if signal == "BUY":
                    pm.open_position(
                        side="BUY",
                        price=mark_price,
                        quantity=trade_amount,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )

                elif signal == "SELL":
                    pm.open_position(
                        side="SELL",
                        price=mark_price,
                        quantity=trade_amount,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )

            else:
                # Optional: allow your signals to explicitly request a manual close
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
