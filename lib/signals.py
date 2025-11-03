import datetime
from telegram import Bot
from lib.telegram_bot import send_message_sync


def log_signal(action, rsi, price):
    """Save each BUY/SELL signal to a text file (UTF-8 safe)."""
    with open("trade_log.txt", "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{timestamp} | {action} | RSI={rsi:.2f} | Price={price}\n")

position = None  # Global or tracked position state

def signals(score, price, symbol):
    global position

    if score >= 30:
        if position != "BUY":
            
            message =  ("📊 TRADE SIGNAL\n"
            "-----------------------------\n"
            "Action     |    🟢 BUY\n"
            f"Symbol    |    {symbol}\n"
            f"Price     |    {price:.2f}\n"
            f"Score     |    {score}\n"
            "-----------------------------")
            print(message)
            log_signal("🟢 BUY", score, price)
            send_message_sync(message)
            position = "BUY"

    elif score <= 20:
        if position != "SELL":
            message =  ("📊 TRADE SIGNAL\n"
            "-----------------------------\n"
            "Action     |    🔴 SELL\n"
            f"Symbol    |    {symbol}\n"
            f"Price     |    {price:.2f}\n"
            f"Score     |    {score}\n"
            "-----------------------------")
            print(message)
            log_signal("🔴 SELL", score, price)
            send_message_sync(message)
            position = "SELL"

    else:
        print("⚪ HOLD | Price:{price} | score: {score:.2f}" )
        log_signal("⚪ HOLD", score, price)
