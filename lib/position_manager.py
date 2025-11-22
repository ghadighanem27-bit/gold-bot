import time
import datetime
import json
import os
from datetime import timedelta

from lib.telegram_bot import send_message_sync
from lib.vars import client, symbol as BOT_SYMBOL
from lib.vars import cfg
from lib.database_manager import update_score_with_result, record_score,attach_trade_id_to_last_score
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
        side: "BUY" or "SELL"
        price: mark price
        quantity: coin quantity (NOT USDT)
        """

        # 1) Validate quantity
        try:
            quantity = format_quantity(quantity)
        except Exception as e:
            print(e)
            return

        # 2) Send MARKET order
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

        # 3) Ensure order is FILLED
        try:
            order_id = order.get("orderId")
            status = order.get("status")

            retries = 5
            while status == "NEW" and retries > 0:
                time.sleep(0.3)
                fresh = client.futures_get_order(symbol=BOT_SYMBOL, orderId=order_id)
                status = fresh.get("status")
                order = fresh
                retries -= 1

            if status not in ("FILLED", "PARTIALLY_FILLED"):
                print(f"❌ Order not filled after retries: {order}")
                return

        except Exception as e:
            print(f"⚠️ Error checking order fill status: {e}")
            return
        

       

        # attach trade id to the score row associated
        from lib.database_manager import attach_trade_id_to_last_score
        attach_trade_id_to_last_score(self.last_score_id)

        # after order is confirmed FILLED
        self.last_trade_id = order_id

        # 5) ATTACH this trade ID to the latest technical score record
        try:
            from lib.database_manager import attach_trade_id_to_last_score
            attach_trade_id_to_last_score(order_id)
            print(f"🔗 Attached trade ID {order_id} to last score entry")
        except Exception as e:
            print(f"⚠️ Failed to attach trade ID: {e}")

        # 6) Register position locally
        avg_price = order.get("avgPrice")
        if avg_price in (None, "0.0", "0.00"):
            self.entry_price = float(price)
        else:
            self.entry_price = float(avg_price)

        self.entry_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.position = side
        self.quantity = quantity
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.pnl = 0.0
        self.break_even_activated = False




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

        if not hasattr(self, "tp_steps_done"):
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

                    print(f"🎯 Partial TP hit @ {level}% | Closed {portion*100:.0f}%")
                    send_message_sync(
                        f"🎯 Partial TP hit at {level}%\nClosed {portion*100:.0f}% of position."
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
                    print("🟩 Breakeven activated.")
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
