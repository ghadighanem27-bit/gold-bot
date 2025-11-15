import threading
from lib.vars import cfg, symbol
from trading_loop import trading_loop
from lib.telegram_bot import start_telegram_listener

if __name__ == "__main__":
    print(f"🚀 Starting trading bot for {symbol}")

    # Start trading loop in a background thread
    t1 = threading.Thread(target=trading_loop, daemon=True)
    t1.start()

    # Start Telegram listener (blocking)
    start_telegram_listener()