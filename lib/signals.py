import datetime
from lib.telegram_bot import send_message_sync
from lib.position_manager import pm
"""from lib.indicators import get_rsi, get_macd, volume_score
from lib.vars import symbol"""


def log_signal(action, rsi, price):
    """Save each BUY/SELL signal to a text file (UTF-8 safe)."""
    with open("trade_log.txt", "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{timestamp} | {action} | RSI={rsi:.2f} | Price={price}\n")

position = "NULL"  # Global or tracked position state

def signals(score, price, symbol):
    
    global position
    symbol = symbol.strip().upper()

    # --- BUY logic ---
    if score >= 38:
        if pm.position != "BUY":
            print(f"🟢 BUY | Price:{price} | Score: {score:.2f}")
            message = (
                "📊 TRADE SIGNAL\n"
                "-----------------------------\n"
                "Action      |    🟢 BUY\n"
                f"Symbol    |    {symbol}\n"
                f"Price        |    {price:.2f}\n"
                f"Score       |    {score:.2f}\n"
                "-----------------------------"
            )
            log_signal("🟢 BUY", score, price)
            send_message_sync(message)

    # --- SELL logic ---
    elif score <= 25:
        if pm.position == "BUY":             # Only close if a buy exists
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


    else:
        print(f"⚪ HOLD | Price:{price} | score: {score:.2f}")
        log_signal("⚪ HOLD", score, price)
"""
def scores(score):
    score_rsi, rsi_power = get_rsi(df)
    score_macd = get_macd(prices, fastperiod=12, slowperiod=26, signalperiod=9, lookback=20)
    score_volume = volume_score(volumes, spike_ratio=1.5)

    message = ("⭕ TRADE SCORING\n"
            "-----------------------------\n"
            f"Total     |    {score:.2f}\n"
            f"RSI Score/Power |  {score_rsi:.2f} | {rsi_power:.2f}\n"
            f"MACD Score  |    {score_macd:.2f}\n"
            f"Score       |    {score_volume:.2f}\n"
            "-----------------------------")
"""



