import datetime
from lib.telegram_bot import send_message_sync
from lib.database_manager import record_trade
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
    weighted_score = score * 100     # convert to 0–100 scale

    # Thresholds
    BUY_THRESHOLD = 36
    SELL_THRESHOLD = 25

    print(f"📊 Score={weighted_score:.2f} | Price={price:.2f}")

    # -----------------------------------------
    # LONG ENTRY (BUY to OPEN)
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
        return  # do not process other logic in same candle

    # -----------------------------------------
    # SHORT ENTRY (SELL to OPEN)
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
    # HOLD SIGNAL
    # -----------------------------------------
    print(f"⚪ HOLD | Price {price:.2f} | Score {weighted_score:.2f}")
    log_signal("HOLD", weighted_score, price)
