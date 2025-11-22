# ==========================================
# signals.py — CLEAN + FIXED VERSION
# ==========================================

from lib.indicators import technical_score
from lib.telegram_bot import send_message_sync


STRONG_BUY = 75
SOFT_BUY   = 60
SOFT_SELL  = 40
STRONG_SELL = 25


def signals(df, price, symbol, pm, trade_amount=None, take_profit=None, stop_loss=None):

    score = technical_score(df, symbol=symbol)
    print(f"🔵 Score={score:.2f} | Price={price:.2f}")

    # ============================
    # EXIT LOGIC
    # ============================

    if pm.position == "BUY" and score <= SOFT_SELL:
        send_message_sync(f"🔻 EXIT LONG\nPrice: {price:.2f}\nScore: {score:.2f}")
        pm.close_position(price, symbol)
        return "EXIT_LONG"

    if pm.position == "SELL" and score >= SOFT_BUY:
        send_message_sync(f"🔺 EXIT SHORT\nPrice: {price:.2f}\nScore: {score:.2f}")
        pm.close_position(price, symbol)
        return "EXIT_SHORT"


    # ============================
    # ENTRY LOGIC
    # ============================

    if pm.position is None:

        # -------- STRONG BUY --------
        if score >= STRONG_BUY:
            pm.open_position("BUY", price, trade_amount, take_profit=2.0, stop_loss=1.0)
            send_message_sync(f"🔥 STRONG BUY\nScore: {score:.2f}")
            return "STRONG_BUY"

        # -------- SOFT BUY --------
        if score >= SOFT_BUY:
            pm.open_position("BUY", price, trade_amount, take_profit=1.2, stop_loss=0.8)
            send_message_sync(f"🟢 SOFT BUY\nScore: {score:.2f}")
            return "SOFT_BUY"


        # -------- STRONG SELL --------
        if score <= STRONG_SELL:
            pm.open_position("SELL", price, trade_amount, take_profit=2.0, stop_loss=1.0)
            send_message_sync(f"🔥 STRONG SELL\nScore: {score:.2f}")
            return "STRONG_SELL"

        # -------- SOFT SELL --------
        if score <= SOFT_SELL:
            pm.open_position("SELL", price, trade_amount, take_profit=1.2, stop_loss=0.8)
            send_message_sync(f"🔴 SOFT SELL\nScore: {score:.2f}")
            return "SOFT_SELL"

    return "NO_SIGNAL"
