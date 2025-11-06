import datetime
import json
import os
from telegram_bot import send_message_sync
from lib.vars import trade_amount

class PositionManager:
    """
    Handles tracking of the current open position (long/short/none),
    entry price, size, and profit/loss logic.
    """

    def __init__(self, save_file="position_state.json"):
        self.save_file = save_file
        self.position = None       # "BUY", "SELL", or None
        self.entry_price = 0.0
        self.entry_time = None
        self.quantity = 0.0
        self.pnl = 0.0

        # Try to load last saved state (for persistence)
        self.load_state()

    # ---------- Position management ----------

    def open_position(self, side, price, quantity = trade_amount, take_profit=1.0, stop_loss=0.5):
        self.position = side
        self.entry_price = price
        self.entry_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.quantity = quantity
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.pnl = 0.0
        self.save_state()

        message = (f"✅ Opened {side} at {price:.2f} (qty: {quantity} )\n"
                   f"TP: {take_profit * 100}%      |         SL: {stop_loss * 100}%\n")
        send_message_sync(message)
        print(message)


    def check_auto_close(self, current_price):
        if not self.position:
            return

        pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        # --- Auto close conditions ---
        if pnl_percent >= self.take_profit:
            message = (f"🎯 Take Profit hit! +{pnl_percent:.2f}%\n")
            self.close_position(current_price)
            send_message_sync(message)

        elif pnl_percent <= -self.stop_loss:
            message = (f"⛔ Stop Loss hit! {pnl_percent:.2f}%\n")
            self.close_position(current_price)
            send_message_sync(message)


    def close_position(self, price):
        if not self.position:
            print("⚠️ No open position to close.\n")
            return None

        pnl_percent = ((price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        self.pnl = pnl_percent
        message = (f"💰 Closed {self.position} at {price:.2f}\n"
                   f" PnL: {pnl_percent:.2f}% (TP={self.take_profit * 100}%, SL={self.stop_loss * 100}%)")
        send_message_sync(message)

        # Reset position after close
        self.reset()
        return pnl_percent

    def reset(self):
        """Clear all position data (after closing)."""
        self.position = None
        self.entry_price = 0.0
        self.entry_time = None
        self.quantity = 0.0
        self.pnl = 0.0
        self.save_state()

    # ---------- Persistence ----------

    def save_state(self):
        """Save current position state to disk (so it survives restarts)."""
        state = {
            "position": self.position,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "quantity": self.quantity,
            "pnl": self.pnl,
        }
        with open(self.save_file, "w") as f:
            json.dump(state, f)

    def load_state(self):
        """Load last saved position from file (if exists)."""
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, "r") as f:
                    state = json.load(f)
                    self.position = state.get("position")
                    self.entry_price = state.get("entry_price", 0.0)
                    self.entry_time = state.get("entry_time")
                    self.quantity = state.get("quantity", 0.0)
                    self.pnl = state.get("pnl", 0.0)
            except Exception as e:
                print(f"⚠️ Could not load position file: {e}")
