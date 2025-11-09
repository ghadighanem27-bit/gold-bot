import datetime
from lib.telegram_bot import send_message_sync
from lib.position_manager import PositionManager
from lib.database_manager import record_trade  # ✅ import correct recorder

def log_signal(action, score, price):
    """Save each BUY/SELL signal to a text file (UTF-8 safe)."""
    with open("trade_log.txt", "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{timestamp} | {action} | Score={score:.2f} | Price={price}\n")

def signals(score, price, symbol, pm, trade_amount=None, take_profit=None, stop_loss=None):
    symbol = symbol.strip().upper()

    # --- BUY logic ---
    if score >= 36:
        if pm.position != "BUY":
            print(f"🟢 BUY | Price:{price} | Score: {score:.2f}")
            log_signal("🟢 BUY", score, price) 

            # ✅ Open position
            pm.open_position(
                side="BUY",
                price=price,
                quantity=trade_amount,
                take_profit=take_profit,
                stop_loss=stop_loss
            )

    # --- SELL logic ---
    elif score <= 25:
        if pm.position == "BUY":  # Only close if a buy exists
            print(f"🔴 SELL | Price:{price} | Score: {score:.2f}")
            message = (
                "📊 TRADE SIGNAL\n"
                "-----------------------------\n"
                "Action      |    🔴 SELL\n"
                f"Symbol    |    {symbol}\n"
                f"Price        |    {price:.2f}\n"
                f"Score       |    {score:.2f}\n"
                "-----------------------------"
            )
            log_signal("🔴 SELL", score, price)
            send_message_sync(message)

            # ✅ Close position and get PnL %
            pnl_percent = pm.close_position(price)

    # --- HOLD logic ---
    else:
        print(f"⚪ HOLD | Price:{price} | Score: {score:.2f}")
        log_signal("⚪ HOLD", score, price)
