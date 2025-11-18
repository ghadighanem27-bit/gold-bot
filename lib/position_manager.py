import time
import datetime
import json
import os
from datetime import timedelta

from lib.telegram_bot import send_message_sync
from lib.vars import client, symbol as BOT_SYMBOL
from lib.vars import cfg
from lib.database_manager import update_score_with_result, record_score
from lib.indicators import technical_score  # kept in case you use it later


# ----------------------------------------------------
# QUANTITY VALIDATOR (Mandatory for Binance Futures)
# ----------------------------------------------------
def format_quantity(qty):
    qty = float(qty)

    # Binance ETHUSDT Futures → max 3 decimals, min 0.001
    qty = round(qty, 3)

    if qty < 0.001:
        raise ValueError(f"❌ Quantity too small for Binance Futures: {qty}")

    return qty


class PositionManager:

    def __init__(self, save_file="position_state.json"):
        if save_file is None:
            save_file = cfg["trading"].get("position_file", "position_state.json")

        self.save_file = save_file
        self.position = None            # "BUY" or "SELL"
        self.entry_price = 0.0
        self.entry_time = None
        self.quantity = 0.0
        self.pnl = 0.0
        self.take_profit = 1
        self.stop_loss = 0.5
        self.cooldown_until = None
        self.last_trade_was_win = None
        self.last_score_id = None

        # --- Break-even config ---
        self.break_even_enabled = True
        self.break_even_trigger_pct = 0.4   # Activate BE at +0.4%
        self.break_even_activated = False

        self.load_state()

    # ----------------------------------------------------
    # OPEN FUTURES POSITION (LONG or SHORT)
    # ----------------------------------------------------
    def open_position(self, side, price, quantity, take_profit=1, stop_loss=0.5):
        """
        side: "BUY" (long) or "SELL" (short)
        price: current mark price (passed from trading_loop)
        quantity: size in ETH (not USDT)
        """

        # 1) Validate quantity
        try:
            quantity = format_quantity(quantity)
        except Exception as e:
            print(e)
            return

        # 2) Send futures MARKET order
        try:
            order = client.futures_create_order(
                symbol=BOT_SYMBOL,
                side="BUY" if side == "BUY" else "SELL",
                type="MARKET",
                quantity=quantity,
            )
            print(f"📌 Futures Order Sent: {order}")
        except Exception as e:
            print(f"❌ Binance Futures order error: {e}")
            return

        # 3) Ensure it actually gets filled (status may be NEW at first)
        try:
            order_id = order.get("orderId")
            status = order.get("status")

            # Poll a few times if still NEW
            retries = 5
            while status == "NEW" and retries > 0:
                time.sleep(0.3)
                fresh = client.futures_get_order(symbol=BOT_SYMBOL, orderId=order_id)
                status = fresh.get("status")
                order = fresh
                retries -= 1

            if status not in ("FILLED", "PARTIALLY_FILLED"):
                print(f"❌ Order not filled after retries, aborting position open: {order}")
                return

        except Exception as e:
            print(f"⚠️ Error while checking order fill status: {e}")
            # Be safe: do NOT register position if we're not sure it filled
            return

        # 4) At this point, order is filled → register position locally
        self.position = side
        # Use avgPrice from order if available, otherwise passed price
        avg_price = order.get("avgPrice")
        self.entry_price = float(avg_price) if avg_price not in (None, "0.0", "0.00") else float(price)
        self.entry_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.quantity = quantity
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.pnl = 0.0
        self.break_even_activated = False

        self.save_state()

        msg = (
            f"✅ Opened {side} (Futures)\n"
            f"Entry: {self.entry_price:.2f}\n"
            f"Qty: {quantity}\n"
            f"TP: {take_profit}% | SL: {stop_loss}%"
        )
        send_message_sync(msg)
        print(msg)

    # ----------------------------------------------------
    # AUTO CLOSE (TP/SL + BREAK-EVEN)
    # ----------------------------------------------------
    def check_auto_close(self, current_price, symbol=BOT_SYMBOL):
        """
        current_price: MUST be futures MARK price (from trading_loop)
        """
        if not self.position:
            return

        pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        # --- Break-even logic ---
        if self.break_even_enabled and not self.break_even_activated:
            if pnl_percent >= self.break_even_trigger_pct:
                # Move SL to entry (0% loss)
                self.stop_loss = 0
                self.break_even_activated = True

                msg = (
                    f"🟦 BREAK-EVEN ACTIVATED\n"
                    f"Trade protected at entry.\n"
                    f"PnL: {pnl_percent:.2f}%"
                )
                send_message_sync(msg)
                print(msg)

        # --- Take Profit ---
        if pnl_percent >= self.take_profit:
            send_message_sync(f"🎯 Take Profit hit! +{pnl_percent:.2f}%")
            self.close_position(current_price, symbol)
            return

        # --- Stop Loss (including BE at 0%) ---
        if pnl_percent <= -self.stop_loss:
            send_message_sync(f"⛔ Stop Loss hit! {pnl_percent:.2f}%")
            self.close_position(current_price, symbol)
            return

    # ----------------------------------------------------
    # CLOSE FUTURES POSITION
    # ----------------------------------------------------
    def close_position(self, price, symbol=BOT_SYMBOL, df=None):
        if not self.position:
            print("⚠️ No open position to close.")
            return None

        # --- Compute PNL % ---
        pnl_percent = ((price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        self.pnl = pnl_percent
        was_win = pnl_percent >= 0
        self.last_trade_was_win = was_win

        # --- Update score AFTER pnl is final ---
        try:
            if self.last_score_id is not None:
                update_score_with_result(self.last_score_id, pnl_percent)
                print(f"📊 Score updated with trade result: {pnl_percent:.2f}%")
        except Exception as e:
            print(f"⚠️ Score update failed: {e}")

        # --- Cooldown after loss ---
        if not was_win:
            self.cooldown_until = datetime.datetime.utcnow() + timedelta(minutes=10)
            print(f"⏳ Cooldown triggered until {self.cooldown_until}")
        else:
            self.cooldown_until = None

        send_message_sync(
            f"💰 Closed {self.position}\nPnL: {pnl_percent:.2f}% "
            f"(TP={self.take_profit}%, SL={self.stop_loss}%)"
        )
        print(f"💰 Closed {self.position} at {price:.2f} | PnL: {pnl_percent:.2f}%")

        # --- Close Binance Futures Order ---
        try:
            close_qty = format_quantity(self.quantity)
            close_order = client.futures_create_order(
                symbol=symbol,
                side="SELL" if self.position == "BUY" else "BUY",
                type="MARKET",
                quantity=close_qty,
                reduceOnly=True
            )
            print(f"📌 Futures Close Executed: {close_order}")
        except Exception as e:
            print(f"❌ Binance Futures close error: {e}")

        if self.last_score_id is not None:
            update_score_with_result(self.last_score_id, pnl_percent)

        self.reset()
        return pnl_percent


    # ----------------------------------------------------
    def reset(self):
        self.position = None
        self.entry_price = 0.0
        self.entry_time = None
        self.quantity = 0.0
        self.pnl = 0.0
        self.break_even_activated = False
        self.save_state()

    # ----------------------------------------------------
    def save_state(self):
        state = {
            "position": self.position,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "quantity": self.quantity,
            "pnl": self.pnl,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "break_even_activated": self.break_even_activated,
        }
        with open(self.save_file, "w") as f:
            json.dump(state, f)

    # ----------------------------------------------------
    def load_state(self):
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, "r") as f:
                    state = json.load(f)
                self.position = state.get("position")
                self.entry_price = state.get("entry_price", 0.0)
                self.entry_time = state.get("entry_time")
                self.quantity = state.get("quantity", 0.0)
                self.pnl = state.get("pnl", 0.0)
                self.take_profit = state.get("take_profit", 1)
                self.stop_loss = state.get("stop_loss", 0.5)
                self.break_even_activated = state.get("break_even_activated", False)

            except Exception as e:
                print(f"⚠️ Could not load position file: {e}")
