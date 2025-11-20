# ==========================================
# signals.py — CLEAN VERSION (final)
# ==========================================

from lib.indicators import technical_score
from lib.telegram_bot import send_message_sync


BUY_THRESHOLD = 70
SELL_THRESHOLD = 25


def signals(df, price, symbol, pm, trade_amount=None, take_profit=None, stop_loss=None):
    """
    Main signal engine for entries/exits.
    This is the ONLY place where BUY/SELL decision is made.
    """

    # ---------------------------------------------------------
    # 1. Compute score (already 0–100 scale)
    # ---------------------------------------------------------
    score = technical_score(df, symbol=symbol)
    weighted_score = score

    print(f"🔵 Score={weighted_score:.2f} | Price={price:.2f}")

    # ---------------------------------------------------------
    # 2. EXIT LOGIC (always runs BEFORE entries)
    # ---------------------------------------------------------

    # ---- EXIT LONG ----
    if pm.position == "BUY" and weighted_score <= SELL_THRESHOLD:
        print("🔻 EXIT LONG SIGNAL DETECTED")
        send_message_sync(f"🔻 EXIT LONG\nPrice: {price:.2f}\nScore: {weighted_score:.2f}")
        pm.close_position(price, symbol)
        return "EXIT_LONG"

    # ---- EXIT SHORT ----
    if pm.position == "SELL" and weighted_score >= BUY_THRESHOLD:
        print("🔺 EXIT SHORT SIGNAL DETECTED")
        send_message_sync(f"🔺 EXIT SHORT\nPrice: {price:.2f}\nScore: {weighted_score:.2f}")
        pm.close_position(price, symbol)
        return "EXIT_SHORT"

    # ---------------------------------------------------------
    # 3. ENTRY LOGIC (only if NO position)
    # ---------------------------------------------------------
    if pm.position is None:

        # ---- LONG ENTRY ----
        if weighted_score >= BUY_THRESHOLD:
            print(f"🟢 LONG ENTRY | Score {weighted_score:.2f} ≥ {BUY_THRESHOLD}")

            send_message_sync(
                f"🟢 LONG ENTRY\nPrice: {price:.2f}\nScore: {weighted_score:.2f}"
            )

            pm.open_position(
                side="BUY",
                price=price,
                quantity=trade_amount,
                take_profit=take_profit,
                stop_loss=stop_loss,
            )
            return "LONG"

        # ---- SHORT ENTRY ----
        if weighted_score <= SELL_THRESHOLD:
            print(f"🔴 SHORT ENTRY | Score {weighted_score:.2f} ≤ {SELL_THRESHOLD}")

            send_message_sync(
                f"🔴 SHORT ENTRY\nPrice: {price:.2f}\nScore: {weighted_score:.2f}"
            )

            pm.open_position(
                side="SELL",
                price=price,
                quantity=trade_amount,
                take_profit=take_profit,
                stop_loss=stop_loss,
            )
            return "SHORT"

    # ---------------------------------------------------------
    # 4. NO TRADE
    # ---------------------------------------------------------
    return "NO_SIGNAL"
