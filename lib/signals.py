import datetime
from telegram import Bot


def log_signal(action, rsi, price):
    """Save each BUY/SELL signal to a text file (UTF-8 safe)."""
    with open("trade_log.txt", "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{timestamp} | {action} | RSI={rsi:.2f} | Price={price}\n")

position = None  # Global or tracked position state

def signals(score, price):
    global position

    if score >= 30:
        if position != "BUY":
            print("🟢 BUY | Price:{price} | score: {score}")
            log_signal("🟢 BUY", score, price)
            send_telegram_message(message)
            position = "BUY"

    elif score <= 20:
        if position != "SELL":
            print("🔴 SELL | Price:{price} | score: {score}")
            log_signal("🔴 SELL", score, price)
            send_telegram_message(message)
            position = "SELL"

    else:
        print("⚪ HOLD | Price:{price} | score: {score}" )
        log_signal("⚪ HOLD", score, price)
