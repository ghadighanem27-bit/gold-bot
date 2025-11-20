import datetime
from lib.telegram_bot import send_message_sync
from lib.indicators import technical_score


def log_signal(action, score, price):
    """Log signals to a UTF-8 text file."""
    with open("trade_log.txt", "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{timestamp} | {action} | Score={score:.2f} | Price={price}\n")


def signals(df, price, symbol, pm, trade_amount=None, take_profit=None, stop_loss=None):
    symbol = symbol.upper()

    # -----------------------------------------
    # COOLDOWN CHECK
    # -----------------------------------------
    if pm.cooldown_until is not None:
        if datetime.datetime.utcnow() < pm.cooldown_until:
            print("⏳ Cooldown active: skipping trade...")
            return
        else:
            pm.cooldown_until = None

    # -----------------------------------------
    # GET TECHNICAL SCORE
    # -----------------------------------------
    score = technical_score(df, symbol=symbol)
    weighted_score = score    # convert to 0–100 scale

    BUY_THRESHOLD = 65
    SELL_THRESHOLD = 35

    print(f"📊 Score={weighted_score:.2f} | Price={price:.2f}")

    # -----------------------------------------
    # EXIT LOGIC  (IMPORTANT!)
    # -----------------------------------------

    # Close LONG → If score goes bearish
    if pm.position == "BUY" and weighted_score <= SELL_THRESHOLD:
        print("🔴 EXIT LONG SIGNAL DETECTED")
        log_signal("EXIT LONG", weighted_score, price)
        send_message_sync(f"🔴 EXIT LONG\nPrice: {price:.2f}\nScore: {weighted_score:.2f}")
        pm.close_position(price, symbol)
        return

    # Close SHORT → If score goes bullish
    if pm.position == "SELL" and weighted_score >= BUY_THRESHOLD:
        print("🟢 EXIT SHORT SIGNAL DETECTED")
        log_signal("EXIT SHORT", weighted_score, price)
        send_message_sync(f"🟢 EXIT SHORT\nPrice: {price:.2f}\nScore: {weighted_score:.2f}")
        pm.close_position(price, symbol)
        return

    # -----------------------------------------
    # LONG ENTRY
    # -----------------------------------------
    if weighted_score >= BUY_THRESHOLD:
        if pm.position != "BUY":
            print(f"🟢 LONG ENTRY | Score {weighted_score:.2f} ≥ {BUY_THRESHOLD}")
            log_signal("LONG ENTRY", weighted_score, price)
            send_message_sync(f"🟢 LONG ENTRY\nPrice: {price:.2f}\nScore: {weighted_score:.2f}")

            pm.open_position(
                side="BUY",
                price=price,
                quantity=trade_amount,
                take_profit=take_profit,
                stop_loss=stop_loss
            )
        return

    # -----------------------------------------
    # SHORT ENTRY
    # -----------------------------------------
    if weighted_score <= SELL_THRESHOLD:
        if pm.position != "SELL":
            print(f"🔴 SHORT ENTRY | Score {weighted_score:.2f} ≤ {SELL_THRESHOLD}")
            log_signal("SHORT ENTRY", weighted_score, price)
            send_message_sync(f"🔴 SHORT ENTRY\nPrice: {price:.2f}\nScore: {weighted_score:.2f}")

            pm.open_position(
                side="SELL",
                price=price,
                quantity=trade_amount,
                take_profit=take_profit,
                stop_loss=stop_loss
            )
        return

    # -----------------------------------------
    # HOLD
    # -----------------------------------------
    print(f"⚪ HOLD | Price {price:.2f} | Score {weighted_score:.2f}")
    log_signal("HOLD", weighted_score, price)
