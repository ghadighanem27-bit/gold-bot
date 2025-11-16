import threading
from lib.vars import cfg, symbol
from trading_loop import trading_loop
from lib.telegram_bot import send_message_sync

if __name__ == "__main__":
    print(f"🚀 Starting trading bot for {symbol}")

    # Start trading loop in a background thread
    t1 = threading.Thread(target=trading_loop, daemon=True)
    t1.start()

    send_message_sync(f"🚀 Starting trading bot for {symbol}")