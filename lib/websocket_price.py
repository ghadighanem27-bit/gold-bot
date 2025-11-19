# lib/websocket_price.py
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
from lib.vars import cfg
import threading

# Store latest streamed prices
LATEST_MARK_PRICE = {}

def _ws_thread(symbol):
    """Internal thread target → runs blocking websocket loop."""
    
    def handle(msg):
        try:
            price = float(msg["p"])
            LATEST_MARK_PRICE[symbol] = price
            # print(f"{symbol} = {price}")  # Debug
        except:
            pass

    # Create websocket client
    ws = UMFuturesWebsocketClient()

    # Select wss endpoint manually
    if cfg["binance"]["futures_env"] == "testnet":
        ws._url = "wss://stream.binancefuture.com/ws"
    else:
        ws._url = "wss://fstream.binance.com/ws"

    # Subscribe to MARK PRICE stream
    ws.mark_price(
        symbol.lower(),
        "1s",         # required speed argument
        callback=handle
    )


    print(f"📡 WebSocket running for {symbol}")

    # This blocks forever — that's why it's inside a thread
    ws.run()


def start_websocket(symbol):
    """Starts websocket listener on a background thread."""
    t = threading.Thread(target=_ws_thread, args=(symbol,), daemon=True)
    t.start()
    print(f"▶️ WebSocket thread started for {symbol}")


def get_ws_price(symbol):
    """Return last streamed mark price or None."""
    return LATEST_MARK_PRICE.get(symbol)
