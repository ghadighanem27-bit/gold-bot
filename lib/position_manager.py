import datetime
import json
import os
from datetime import timedelta

from lib.telegram_bot import send_message_sync
from lib.vars import client, symbol as BOT_SYMBOL
from lib.database_manager import record_trade
from lib.indicators import technical_score


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

        # >>> BREAK-EVEN START
        self.break_even_enabled = True
        self.break_even_trigger_pct = 0.4   # Activate BE at +0.4%
        self.break_even_activated = False
        # >>> BREAK-EVEN END

        self.load_state()

    # ----------------------------------------------------
    # OPEN FUTURES POSITION (LONG or SHORT)
    # ----------------------------------------------------
    def open_position(self, side, price, quantity, take_profit=1, stop_loss=0.5):

        try:
            quantity = format_quantity(quantity)
        except Exception as e:
            print(e)
            return

        self.position = side
        self.entry_price = price
        self.entry_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.quantity = quantity
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.pnl = 0.0

        # Reset break-even flag on new trade
        self.break_even_activated = False

        self.save_state()

        # -------- SEND REAL FUTURES ORDER --------
        try:
            order = client.futures_create_order(
                symbol=BOT_SYMBOL,
                side="BUY" if side == "BUY" else "SELL",
                type="MARKET",
                quantity=quantity
            )

            if order.get("status") not in ("FILLED", "PARTIALLY_FILLED"):
                print(f"❌ Order not filled: {order}")
                return

            print(f"📌 Futures Order Executed: {order}")

        except Exception as e:
            print(f"❌ Binance Futures order error: {e}")
            return

        msg = (
            f"✅ Opened {side} (Futures)\n"
            f"Price: {price:.2f}\n"
            f"Qty: {quantity}\n"
            f"TP: {take_profit}% | SL: {stop_loss}%"
        )
        send_message_sync(msg)
        print(msg)

    # ----------------------------------------------------
    # AUTO CLOSE (TP/SL + BREAK-EVEN)
    # ----------------------------------------------------
    def check_auto_close(self, current_price, symbol=BOT_SYMBOL):

        if not self.position:
            return

        pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        # >>> BREAK-EVEN START
        if self.break_even_enabled and not self.break_even_activated:
            if pnl_percent >= self.break_even_trigger_pct:
                self.stop_loss = 0   # SL moves to entry
                self.break_even_activated = True

                msg = (
                    f"🟦 BREAK-EVEN ACTIVATED\n"
                    f"Trade protected at entry.\n"
                    f"PnL: {pnl_percent:.2f}%"
                )
                send_message_sync(msg)
                print(msg)
        # >>> BREAK-EVEN END

        # --- TAKE PROFIT ---
        if pnl_percent >= self.take_profit:
            send_message_sync(f"🎯 Take Profit hit! +{pnl_percent:.2f}%")
            self.close_position(current_price, symbol)
            return

        # --- STOP LOSS (including break-even) ---
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

        pnl_percent = ((price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        self.pnl = pnl_percent
        was_win = pnl_percent >= 0
        self.last_trade_was_win = was_win

        # Apply cooldown on loss
        if not was_win:
            self.cooldown_until = datetime.datetime.utcnow() + timedelta(minutes=10)
            print(f"⏳ Cooldown triggered until {self.cooldown_until}")
        else:
            self.cooldown_until = None

        send_message_sync(
            f"💰 Closed {self.position}\nPnL: {pnl_percent:.2f}% "
            f"(TP={self.take_profit}%, SL={self.stop_loss}%)"
        )

        try:
            close_qty = format_quantity(self.quantity)
        except Exception as e:
            print(e)
            return

        try:
            order = client.futures_create_order(
                symbol=symbol,
                side="SELL" if self.position == "BUY" else "BUY",
                type="MARKET",
                quantity=close_qty
            )

            print(f"📌 Futures Close Executed: {order}")

        except Exception as e:
            print(f"❌ Binance Futures close error: {e}")

        try:
            trade_id = record_trade(
                symbol=symbol,
                side=self.position,
                entry_price=float(self.entry_price),
                exit_price=float(price),
                pnl_percent=float(pnl_percent),
                tp_hit=pnl_percent >= self.take_profit,
                sl_hit=pnl_percent <= -self.stop_loss
            )
            print(f"✅ Trade saved to DB (ID: {trade_id})")

        except Exception as e:
            print(f"❌ DB Error while saving trade: {e}")

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
            "break_even_activated": self.break_even_activated
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
