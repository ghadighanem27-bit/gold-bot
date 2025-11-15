import time
from datetime import datetime
from binance.exceptions import BinanceAPIException

from lib.vars import (
    client,
    symbol,
    trade_amount,
    loop_interval,
)
from lib.market_data import get_futures_price, get_usdt_balance
from lib.telegram_bot import send_message_sync
from lib.signals import signals  # you should already have this

class PositionManager:
    def __init__(self):
        self.position_side = None  # "LONG", "SHORT", or None
        self.entry_price = None
        self.qty = 0.0

    def open_position(self, side: str, price: float):
        self.position_side = side
        self.entry_price = price
        self.qty = trade_amount

    def close_position(self):
        self.position_side = None
        self.entry_price = None
        self.qty = 0.0


pm = PositionManager()

def place_futures_order(side: str, quantity: float):
    """Market order on Futures USDT-M."""
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
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

def trading_loop():
    """Main infinite trading loop."""
    send_message_sync(f"🚀 Trading loop started for <b>{symbol}</b> (Futures)")

    while True:
        try:
            mark_price = get_futures_price(symbol)
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Mark Price: {mark_price}")

            if mark_price is None:
                time.sleep(loop_interval)
                continue

            # Get signal from your strategy
            signal = signals(symbol, mark_price)  # implement in lib/signals.py

            # --- Position logic ---
            if pm.position_side is None:
                # No open position → only react to new entry signals
                if signal == "BUY":
                    order = place_futures_order("BUY", trade_amount)
                    if order:
                        pm.open_position("LONG", mark_price)
                        send_message_sync(f"✅ Opened <b>LONG</b> at {mark_price}")
                elif signal == "SELL":
                    order = place_futures_order("SELL", trade_amount)
                    if order:
                        pm.open_position("SHORT", mark_price)
                        send_message_sync(f"✅ Opened <b>SHORT</b> at {mark_price}")

            else:
                # Position already open → allow exit or reverse signals
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

            time.sleep(loop_interval)

        except KeyboardInterrupt:
            print("🛑 Trading loop stopped by user.")
            break
        except Exception as e:
            print(f"⚠️ Error in trading_loop: {e}")
            time.sleep(loop_interval)
