# ==============================================================================
# lib/signals.py — REFINED VERSION (Wider Zones + Exit Confirmation)
# ==============================================================================

from lib.indicators import technical_score
from lib.telegram_bot import send_message_sync

# --- RECOMMENDATION C: WIDEN NEUTRAL ZONE ---
# We lowered SOFT_SELL from 40 to 30.
# This gives the trade more "room to breathe" before exiting.
STRONG_BUY = 75
SOFT_BUY   = 60
SOFT_SELL  = 30  # Was 40
STRONG_SELL = 25

def signals(df, price, symbol, pm, trade_amount=None, take_profit=None, stop_loss=None):

    score = technical_score(df, symbol=symbol)
    print(f"🔵 Score={score:.2f} | Price={price:.2f}")

    # ========================================================
    # EXIT LOGIC (WITH CONFIRMATION - RECOMMENDATION A)
    # ========================================================
    
    # We use a counter in 'pm' to ensure we don't exit on a single fleeting spike.
    # We require 2 consecutive 'bad' scores to trigger an exit.

    # --- EXIT LONG ---
    if pm.position == "BUY":
        if score <= SOFT_SELL:
            pm.exit_confirmation += 1
            print(f"⚠️ Exit Long Signal Detected ({pm.exit_confirmation}/2) | Score: {score:.2f}")
            
            if pm.exit_confirmation >= 2:
                send_message_sync(f"🔻 EXIT LONG (Confirmed)\nPrice: {price:.2f}\nScore: {score:.2f}\n{symbol}")
                pm.close_position(price, symbol)
                pm.exit_confirmation = 0 # Reset
                return "EXIT_LONG"
        else:
            # Reset counter if score recovers
            if pm.exit_confirmation > 0:
                print("✅ Score recovered. Exit cancelled.")
            pm.exit_confirmation = 0

    # --- EXIT SHORT ---
    if pm.position == "SELL":
        # For shorts, we exit if the score gets too bullish (>= SOFT_BUY)
        if score >= SOFT_BUY:
            pm.exit_confirmation += 1
            print(f"⚠️ Exit Short Signal Detected ({pm.exit_confirmation}/2) | Score: {score:.2f}")
            
            if pm.exit_confirmation >= 2:
                send_message_sync(f"🔺 EXIT SHORT (Confirmed)\nPrice: {price:.2f}\nScore: {score:.2f}\n{symbol}")
                pm.close_position(price, symbol)
                pm.exit_confirmation = 0 # Reset
                return "EXIT_SHORT"
        else:
            pm.exit_confirmation = 0


    # ========================================================
    # ENTRY LOGIC (UNCHANGED)
    # ========================================================

    if pm.position is None:

        # -------- STRONG BUY --------
        if score >= STRONG_BUY:
            pm.open_position("BUY", price, trade_amount, take_profit=2.0, stop_loss=1.0)
            send_message_sync(f"🔥 STRONG BUY\nScore: {score:.2f}\n{symbol}\n{price}")
            return "STRONG_BUY"

        # -------- SOFT BUY --------
        if score >= SOFT_BUY:
            # Slightly wider SL/TP can be handled here if desired
            pm.open_position("BUY", price, trade_amount, take_profit=1.2, stop_loss=0.8)
            send_message_sync(f"🟢 SOFT BUY\nScore: {score:.2f}\n{symbol}\n{price}")
            return "SOFT_BUY"


        # -------- STRONG SELL --------
        if score <= STRONG_SELL:
            pm.open_position("SELL", price, trade_amount, take_profit=2.0, stop_loss=1.0)
            send_message_sync(f"🔥 STRONG SELL\nScore: {score:.2f}\n{symbol}\n{price}")
            return "STRONG_SELL"

        # -------- SOFT SELL --------
        if score <= SOFT_SELL: # Note: Entry condition matches exit threshold
            pm.open_position("SELL", price, trade_amount, take_profit=1.2, stop_loss=0.8)
            send_message_sync(f"🔴 SOFT SELL\nScore: {score:.2f}\n{symbol}\n{price}")
            return "SOFT_SELL"

    return "HOLD"