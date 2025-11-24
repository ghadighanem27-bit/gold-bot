import time
import datetime
import json
import os
from datetime import timedelta

from lib.telegram_bot import send_message_sync
from lib.vars import client, symbol as BOT_SYMBOL
from lib.vars import cfg, symbol
from lib.database_manager import update_score_with_result, record_score, attach_trade_id_to_score_id
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
        self.pnl_history = []

        self.break_even_triggered = False
        self.exit_confirmation = 0


        # --- Break-even config ---
        self.break_even_enabled = True
        self.break_even_trigger_pct = 0.4   # Activate BE at +0.4%
        self.break_even_activated = False

        self.load_state()
    
    def save_state(self):
        """
        Saves the current position details to a JSON file.
        """
        data = {
            "position": self.position,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "quantity": self.quantity,
            "take_profit_pct": getattr(self, "take_profit_pct", 0.0),
            "stop_loss_pct": getattr(self, "stop_loss_pct", 0.0),
            "trade_id": getattr(self, "trade_id", None),
            "tp_steps_done": getattr(self, "tp_steps_done", []),
            "trailing_active": getattr(self, "trailing_active", False),
            "trailing_peak_pnl": getattr(self, "trailing_peak_pnl", 0.0),
            # New variables for the recent fixes
            "break_even_triggered": getattr(self, "break_even_triggered", False),
            "exit_confirmation": getattr(self, "exit_confirmation", 0)
        }
        
        try:
            with open(self.save_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"⚠️ Failed to save position state: {e}")

    # ----------------------------------------------------
    # OPEN FUTURES POSITION (LONG or SHORT)
    # ----------------------------------------------------
    def open_position(self, position: str, price: float, trade_amount: float, take_profit: float, stop_loss: float):
        """
        Executes a market order and robustly links the resulting trade to the 
        currently stored last_score_id.
        """
        if self.position is not None:
            print("❌ Already in a position. Cannot open a new one.")
            return

        # 1. PREPARE DATA
        side = "BUY" if position == "BUY" else "SELL"
        
        # Fix: Define 'quantity' explicitly (was 'qty' before)
        quantity = format_quantity(trade_amount)

        # 2. GENERATE UNIQUE TRADE ID (Internal Linkage)
        # This ID is used to link the Postgres score row to this trade.
        if not hasattr(self, 'last_score_id') or self.last_score_id is None:
            print("⚠️ Cannot open position: last_score_id is missing.")
            return

        # Create a unique custom ID for DB linkage
        trade_id = f"{BOT_SYMBOL}_{side}_{int(time.time())}_{self.last_score_id}"

        # 3. EXECUTE ORDER ON BINANCE
        try:
            # Note: For real trading, you might need clientOrderId or other fields
            order = client.futures_create_order(
                symbol=BOT_SYMBOL,
                side=side,
                type='MARKET',
                quantity=quantity,
            )
            
            # Fix: Define 'order_id' explicitly from the response
            order_id = order['orderId']
            print(f"✅ Binance Order Sent. ID: {order_id}")
        
        except Exception as e:
            send_message_sync(f"❌ Failed to open position on Binance: {e}")
            print(f"❌ Failed to open position on Binance: {e}")
            return # Abort if order fails

        # 4. ROBUSTLY LINK TRADE ID TO MTF_SCORES
        # Use the new function for guaranteed linkage using the unique trade_id
        attach_trade_id_to_score_id(self.last_score_id, trade_id)
        
        # 5. UPDATE POSITION MANAGER STATE
        self.position = position
        self.entry_price = price
        self.entry_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.quantity = quantity
        self.take_profit_pct = take_profit
        self.stop_loss_pct = stop_loss
        self.trade_id = trade_id            # Store the internal trade_id for DB updates
        self.tp_steps_done = []             # Reset take profit steps
        self.trailing_active = False 
        
        # RESET NEW VARIABLES
        self.break_even_triggered = False
        self.exit_confirmation = 0       # Reset trailing stop

        self.save_state()
            
        print(f"✅ Position State Updated: {side} {quantity} @ {price:.2f} | Linked Score ID: {self.last_score_id}")




    # ----------------------------------------------------
    # AUTO CLOSE (TP/SL + BREAK-EVEN)
    # ----------------------------------------------------
    def check_auto_close(self, current_price, symbol=BOT_SYMBOL):
        """
        Checks TP, SL, and Break-Even logic.
        current_price: MUST be futures MARK price.
        """
        if not self.position:
            return

        # 1. Calculate PnL %
        pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        # 2. Check Break-Even Trigger
        if self.break_even_enabled and not self.break_even_activated:
            if pnl_percent >= self.break_even_trigger_pct:
                
                # --- THE FIX: COVER FEES ---
                # If we set stop_loss to 0, we lose money on fees (~0.1%).
                # We set stop_loss to -0.15 (Negative stop_loss = PROFIT).
                # Logic below checks: if pnl <= -stop_loss
                # So: if pnl <= -(-0.15)  --> if pnl <= +0.15%
                
                self.stop_loss = -0.15 
                self.break_even_activated = True
                self.save_state() # Save immediately so we don't lose this protection

                msg = (
                    f"🛡️ FEES COVERED (Break-Even)\n"
                    f"{symbol}\n"
                    f"Triggered at: {pnl_percent:.2f}%\n"
                    f"Stop moved to: +0.15% (Locks fees)"
                )
                send_message_sync(msg)
                print(msg)

        # 3. Check Take Profit
        if self.take_profit is not None and pnl_percent >= float(self.take_profit):
            send_message_sync(f"🎯 Take Profit hit! +{pnl_percent:.2f}%\n{symbol}")
            self.close_position(current_price, symbol)
            return

        # 4. Check Stop Loss (Or Trailing/BE Stop)
        # Note: If self.stop_loss is -0.15, this checks: pnl <= 0.15
        if self.stop_loss is not None and pnl_percent <= -float(self.stop_loss):
            
            # Distinguish between a real loss and a break-even exit
            if self.stop_loss < 0:
                # This is actually a profit exit (stopped out at +0.15%)
                log_msg = f"🛡️ Break-Even Exit (+0.15% locked)\n{symbol}"
            else:
                log_msg = f"⛔ Stop Loss hit! {pnl_percent:.2f}%\n{symbol}"

            send_message_sync(log_msg)
            self.close_position(current_price, symbol)
            return

    # ----------------------------------------------------
    # CLOSE FUTURES POSITION
    # ----------------------------------------------------
    def close_position(self, price, symbol=BOT_SYMBOL, df=None):
        if not self.position:
            print("⚠️ No open position to close.")
            return None

        # -------- PNL % ----------
        pnl_percent = ((price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        exit_time = datetime.datetime.utcnow()

        # Volatility at exit (safe fallback)
        exit_volatility = None
        if df is not None:
            try:
                exit_volatility = df["c"].pct_change().std() * 100
            except:
                exit_volatility = None

        # Duration from entry → exit
        try:
            entry_dt = datetime.datetime.fromisoformat(self.entry_time)
            duration_seconds = (exit_time - entry_dt).total_seconds()
        except:
            duration_seconds = None

        # -------- UPDATE SCORE RESULT --------
        from lib.database_manager import update_score_with_result

        if self.last_score_id:
            update_score_with_result(
                self.last_score_id,
                pnl=pnl_percent,
                exit_time=exit_time,
                exit_volatility=exit_volatility,
                duration_seconds=duration_seconds
            )
            print(f"📊 Score #{self.last_score_id} updated with result")

        # -------- Update state --------
        self.pnl = pnl_percent
        was_win = pnl_percent >= 0
        self.last_trade_was_win = was_win
        self.pnl_history.append(pnl_percent)


        # -------- COOLDOWN --------
        if not was_win:
            self.cooldown_until = datetime.datetime.utcnow() + timedelta(minutes=10)
            print(f"⏳ Cooldown triggered until {self.cooldown_until}")
        else:
            self.cooldown_until = None

        # -------- Telegram --------
        send_message_sync(
            f"💰 Closed {self.position}\nPnL: {pnl_percent:.2f}% "
            f"{symbol}\n"
            f"(TP={self.take_profit}%, SL={self.stop_loss}%)"
        )
        print(f"💰 Closed {self.position} at {price:.2f} | PnL={pnl_percent:.2f}%")

        # -------- Close Binance position --------
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

        self.reset()
        return pnl_percent


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

    def check_progressive_tp(self, price, current_score=None):
        """
        Progressive TP v3 (Score-aware):
        - Partial take profits at defined levels
        - Breakeven after first TP
        - Trailing stop after final TP
        - Early exit if score momentum weakens
        """
        if current_score is None:
            return # Score is required for this logic

        if not self.position:
            return

        if self.entry_price is None or self.quantity is None:
            return

        # Calculate PNL %
        pnl_percent = ((price - self.entry_price) / self.entry_price) * 100
        if self.position == "SELL":
            pnl_percent = -pnl_percent

        # ============================================================
        # SCORE-AWARE EARLY EXIT (momentum weakening protection)
        # ============================================================
        if current_score is not None:
            from lib.risk import should_secure_profit

            if should_secure_profit(self.position, pnl_percent, current_score):
                print("📉 Score weakening → securing profit early.")
                send_message_sync(
                    f"📉 Momentum weakening\nPNL: {pnl_percent:.2f}%\nScore: {current_score:.2f}\nPosition closed safely."
                )
                self.close_position(price)
                return

        # ============================================================
        # STEP 1 — PARTIAL TAKE PROFITS
        # ============================================================

        steps = [
            (0.40, 0.25),
            (0.70, 0.25),
            (1.00, 0.25),
            (1.50, 0.25),
        ]

        if (not hasattr(self, "tp_steps_done") or not
            isinstance(self.tp_steps_done, set)):
                self.tp_steps_done = set()

        for level, portion in steps:

            if pnl_percent >= level and level not in self.tp_steps_done:

                qty_to_close = float(self.quantity) * portion
                qty_to_close = format_quantity(qty_to_close)

                try:
                    order = client.futures_create_order(
                        symbol=BOT_SYMBOL,
                        side="SELL" if self.position == "BUY" else "BUY",
                        type="MARKET",
                        quantity=qty_to_close,
                        reduceOnly=True
                    )

                    print(f"🎯 Partial TP hit @ {level}%\nClosed {portion*100:.0f}%\n{symbol}")
                    send_message_sync(
                        f"🎯 Partial TP hit at {level}%\nClosed {portion*100:.0f}% of position.\n{symbol}"
                 )

                except Exception as e:
                    print(f"❌ Progressive TP error: {e}")
                    continue

                self.tp_steps_done.add(level)
                self.quantity = float(self.quantity) - float(qty_to_close)

                # Activate breakeven after first TP
                if not self.break_even_activated:
                    self.break_even_activated = True
                    self.stop_loss = 0.0
                    print("🟩 Breakeven activated.\n {symbol}")
                    send_message_sync("🟩 Stop-loss moved to breakeven.")

                # Activate trailing after last TP
                if len(self.tp_steps_done) == len(steps):
                    self.trailing_active = True
                    self.trailing_peak_pnl = pnl_percent
                    print("📈 Trailing stop ACTIVATED.")
                    send_message_sync("📈 Trailing stop ACTIVATED after final TP.")

                return  # Only one TP per tick

        # ============================================================
        # STEP 2 — TRAILING STOP
        # ============================================================

        if hasattr(self, "trailing_active") and self.trailing_active:

            if pnl_percent > getattr(self, "trailing_peak_pnl", 0):
                self.trailing_peak_pnl = pnl_percent

            trailing_distance = 0.30  # 0.30% behind peak

            if pnl_percent <= self.trailing_peak_pnl - trailing_distance:

                print(f"🏁 Trailing stop triggered at {pnl_percent:.2f}%")
                send_message_sync(
                    f"🏁 Trailing stop triggered\nPeak={self.trailing_peak_pnl:.2f}%\nExit={pnl_percent:.2f}%"
                )

                self.close_position(price)

            
    def reset(self):
        self.position = None
        self.entry_price = None
        self.entry_time = None
        self.quantity = 0
        self.pnl = 0.0
        self.break_even_activated = False
        self.take_profit = None
        self.stop_loss = None
