import datetime
from datetime import timedelta
import json
import os

from lib.telegram_bot import send_message_sync
from lib.vars import trade_amount, symbol as BOT_SYMBOL
from lib.database_manager import record_trade
from lib.indicators import technical_score


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
        self.take_profit = 1   # as % (example: 1 = 1%)
        self.stop_loss = 0.5   # as % (example: 0.5 = 0.5%)
        self.cooldown_until = None
        self.last_trade_was_win = None


        # Load last saved state
        self.load_state()

    # ---------- Position management ----------

    def open_position(self, side, price, quantity=trade_amount, take_profit=1, stop_loss=0.5):
        self.position = side
        self.entry_price = price
        self.entry_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.quantity = quantity
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.pnl = 0.0
        self.save_state()

        message = (
            f"✅ Opened {side} at {price:.2f} (qty: {quantity})\n"
            f"TP: {take_profit}%      |         SL: {stop_loss}%\n"
        )
        send_message_sync(message)
        print(message)

    def check_auto_close(self, current_price, symbol=BOT_SYMBOL):
        """Checks if TP or SL has been hit and closes the position automatically."""
        if not self.position:
            return

        # Calculate PnL %
        pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        # --- TAKE PROFIT ---
        if pnl_percent >= self.take_profit:
            message = f"🎯 Take Profit hit! +{pnl_percent:.2f}%"
            send_message_sync(message)
            self.close_position(current_price, symbol)
            return

        # --- STOP LOSS ---
        if pnl_percent <= -self.stop_loss:
            message = f"⛔ Stop Loss hit! {pnl_percent:.2f}%"
            send_message_sync(message)
            self.close_position(current_price, symbol)
            return


    def close_position(self, price, symbol=BOT_SYMBOL, df=None):
        if not self.position:
            print("⚠️ No open position to close.\n")
            return None

        # Always enforce symbol
        if not symbol:
            symbol = BOT_SYMBOL

        pnl_percent = ((price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        self.pnl = pnl_percent

        # Determine if trade was a win or loss
        was_win = pnl_percent >= 0
        self.last_trade_was_win = was_win

        # Apply 10 min cooldown if loss
        if not was_win:
            self.cooldown_until = datetime.utcnow() + timedelta(minutes=10)
            print(f"⏳ Cooldown triggered until {self.cooldown_until}")
        else:
            self.cooldown_until = None

        message = (
            f"💰 Closed {self.position} at {price:.2f}\n"
            f"PnL: {pnl_percent:.2f}% (TP={self.take_profit}%, SL={self.stop_loss}%)"
        )
        print(message)
        send_message_sync(message)

        # --- Save trade to DB ---
        trade_id = None
        try:
            print(f"🧾 Saving trade to DB: {symbol} | {self.position} | {pnl_percent:.2f}%")

            trade_id = record_trade(
                symbol=symbol,
                side=self.position,
                entry_price=float(self.entry_price),
                exit_price=float(price),
                pnl_percent=float(pnl_percent),
                tp_hit=1 if pnl_percent >= self.take_profit else 0,
                sl_hit=1 if pnl_percent <= -self.stop_loss else 0
            )

            print(f"✅ Trade saved successfully. Trade ID = {trade_id}")

        except Exception as e:
            print(f"❌ DB Error while saving trade: {e}")

        # --- Record exit indicators ---
        if df is not None and trade_id is not None:
            try:
                print("📊 Recording exit indicator snapshot...")
                total_score = technical_score(df, symbol=symbol)
                technical_score(
                    datetime.datetime.utcnow(),
                    symbol,
                    {"total": total_score},
                    trade_id=trade_id
                )
            except Exception as e:
                print(f"⚠️ Could not record exit indicators: {e}")

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
        state = {
            "position": self.position,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "quantity": self.quantity,
            "pnl": self.pnl,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
        }
        with open(self.save_file, "w") as f:
            json.dump(state, f)

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

            except Exception as e:
                print(f"⚠️ Could not load position file: {e}")