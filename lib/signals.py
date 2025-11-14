import datetime
from lib.telegram_bot import send_message_sync
from lib.position_manager import PositionManager
from lib.database_manager import record_trade
from lib.indicators import technical_score

def log_signal(action, score, price):
    """Save each BUY/SELL signal to a text file (UTF-8 safe)."""
    with open("trade_log.txt", "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{timestamp} | {action} | Score={score:.2f} | Price={price}\n")

def signals(df, price, symbol, pm, trade_amount=None, take_profit=None, stop_loss=None):
    symbol = symbol.strip().upper()

    # Cooldown check
    if pm.cooldown_until is not None:
        if datetime.utcnow() < pm.cooldown_until:
            print("⏳ Cooldown active: skipping trade signal...")
            return
        else:
            # Cooldown expired
            pm.cooldown_until = None

    # --- Compute and record indicator scores ---
    score = technical_score(df, symbol={symbol})   # Automatically records to DB
    weighted_score = score * 100  # scale to 0–100 if you use thresholds 25–36

    # --- BUY logic ---
    if weighted_score >= 36:
        if pm.position != "BUY":
            print(f"🟢 BUY | Price:{price:.2f} | Score: {weighted_score:.2f}")
            log_signal("🟢 BUY", weighted_score, price)

            pm.open_position(
                side="BUY",
                price=price,
                quantity=trade_amount,
                take_profit=take_profit,
                stop_loss=stop_loss
            )

    # --- SELL logic ---
    elif weighted_score <= 25:
        if pm.position == "BUY":
            print(f"🔴 SELL | Price:{price:.2f} | Score: {weighted_score:.2f}")
            message = (
                "📊 TRADE SIGNAL\n"
                "-----------------------------\n"
                "Action      |    🔴 SELL\n"
                f"Symbol    |    {symbol}\n"
                f"Price        |    {price:.2f}\n"
                f"Score       |    {weighted_score:.2f}\n"
                "-----------------------------"
            )
            log_signal("🔴 SELL", weighted_score, price)
            send_message_sync(message)
            pm.close_position(price, symbol)

    # --- HOLD logic ---
    else:
        print(f"⚪ HOLD | Price:{price:.2f} | Score: {weighted_score:.2f}")
        log_signal("⚪ HOLD", weighted_score, price)