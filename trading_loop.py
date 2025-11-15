import time
from datetime import datetime
from binance.exceptions import BinanceAPIException

from lib.vars import (
    client,
    symbol,
    trade_amount,
    take_profit,
    stop_loss,
    loop_interval,
)
from lib.market_data import get_futures_price, get_usdt_balance, get_data
from lib.telegram_bot import send_message_sync
from lib.signals import signals


# ================================================
# POSITION MANAGER
# ================================================
class PositionManager:
    def __init__(self):
        self.position_side = None  # "LONG", "SHORT", or None
        self.entry_price = None
        self.qty = 0.0

    def open_position(self, side: str, price: float):
        self.position_side = side  # LONG/SHORT
        self.entry_price = price
        self.qty = trade_amount

    def close_position(self):
        self.position_side = None
        self.entry_price = None
        self.qty = 0.0


pm = PositionManager()


# ================================================
# ORDER FUNCTION
# ================================================
def place_futures_order(side: str, quantity: float):
    """Place a MARKET futures order (TESTNET or LIVE depending on vars)."""
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity,
        )
        return order

    except BinanceAPIException as e:
        print(f"⚠️ Futures order error: {e}")
        send_message_sync(f"⚠️ Order error: {e}")
        return None

    except Exception as e:
        print(f"⚠️ Unknown order error: {e}")
        send_message_sync(f"⚠️ Unknown order error: {e}")
        return None


# ================================================
# MAIN LOOP
# ================================================
def trading_loop():
    send_message_sync(f"🚀 Trading loop started for <b>{symbol}</b> (Futures Testnet)")
    print(f"🚀 Trading loop started for {symbol}")

    while True:
        try:
            mark_price = get_futures_price(symbol)
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Mark Price: {mark_price}")

            if mark_price is None:
                time.sleep(loop_interval)
                continue

            # -------------------------------------------------------------
            # Fetch candles for strategy (df)
            # -------------------------------------------------------------
            try:
                df = get_data(symbol)
            except Exception as e:
                print(f"⚠️ Failed to fetch candles: {e}")
                df = None

            # -------------------------------------------------------------
            # CALL SIGNALS() WITH THE CORRECT PARAMETERS
            # -------------------------------------------------------------
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

            # Debug print
            print(f"➡️ Signal: {signal}")

            # ===============================================
            # ENTRY LOGIC
            # ===============================================
            
            # ---------------------------------------------------------
            #  COOLDOWN CHECK — Do not enter new trades during cooldown
            # ---------------------------------------------------------
            if pm.cooldown_until is not None:
                now = datetime.datetime.utcnow()
                if now < pm.cooldown_until:
                    remaining = int((pm.cooldown_until - now).total_seconds())
                    print(f"⏳ Cooldown active ({remaining}s left). Skipping entries.")
                    time.sleep(loop_interval)
                    continue


            if pm.position_side is None:

                if signal == "BUY":
                    order = place_futures_order("BUY", trade_amount)
                    if order:
                        pm.open_position("LONG", mark_price)
                        send_message_sync(f"🟩 Opened <b>LONG</b> at {mark_price}")

                elif signal == "SELL":
                    order = place_futures_order("SELL", trade_amount)
                    if order:
                        pm.open_position("SHORT", mark_price)
                        send_message_sync(f"🟥 Opened <b>SHORT</b> at {mark_price}")

            # ===============================================
            # EXIT / FLIP LOGIC
            # ===============================================
            else:
                if pm.position_side == "LONG" and signal == "SELL":
                    order = place_futures_order("SELL", pm.qty)
                    if order:
                        pnl_pct = (mark_price - pm.entry_price) / pm.entry_price * 100
                        send_message_sync(
                            f"🔻 Closed LONG at {mark_price} | PnL: {pnl_pct:.2f}%"
                        )
                        pm.close_position()

                elif pm.position_side == "SHORT" and signal == "BUY":
                    order = place_futures_order("BUY", pm.qty)
                    if order:
                        pnl_pct = (pm.entry_price - mark_price) / pm.entry_price * 100
                        send_message_sync(
                            f"🔺 Closed SHORT at {mark_price} | PnL: {pnl_pct:.2f}%"
                        )
                        pm.close_position()

            # LOOP SLEEP
            time.sleep(loop_interval)

        except KeyboardInterrupt:
            print("🛑 Trading loop stopped by user.")
            break

        except Exception as e:
            print(f"⚠️ Error in trading_loop: {e}")
            send_message_sync(f"⚠️ Error in trading_loop: {e}")
            time.sleep(loop_interval)
