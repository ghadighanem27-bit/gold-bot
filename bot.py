import threading
from lib.vars import cfg, symbol
from trading_loop import trading_loop
from lib.telegram_bot import start_telegram_listener
from lib.websocket_price import start_websocket

if __name__ == "__main__":
    print(f"🚀 Starting trading bot for {symbol}")

    # Start websocket first
    start_websocket(symbol)

    # Start trading loop in a background thread
    t1 = threading.Thread(target=trading_loop, daemon=True)
    t1.start()

    t1.join()