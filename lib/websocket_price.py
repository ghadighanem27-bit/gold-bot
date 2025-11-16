# lib/websocket_price.py
from binance.websocket.futures.websocket_client import FuturesWebsocketClient
from lib.vars import cfg
import threading

# Shared state for your bot to read the latest price
LATEST_MARK_PRICE = {}

def start_websocket(symbol):
    """
    Starts a websocket stream for the futures mark price of a symbol.
    Updates LATEST_MARK_PRICE[symbol] continuously.
    """

    def handle_message(msg):
        try:
            price = float(msg["p"])
            LATEST_MARK_PRICE[symbol] = price
        except:
            pass

    ws = FuturesWebsocketClient()

    # Select environment (real vs testnet)
    if cfg["binance"]["futures_env"] == "testnet":
        ws.FUTURES_URL = "wss://stream.binancefuture.com/ws"
    else:
        ws.FUTURES_URL = "wss://fstream.binance.com/ws"

    # Start websocket client
    ws.start()
    ws.mark_price(symbol=symbol, id=1, callback=handle_message)

    print(f"📡 WebSocket started for {symbol}")

    return ws


def get_ws_price(symbol):
    """
    Safely return the latest websocket mark price,
    or None if not yet received.
    """
    return LATEST_MARK_PRICE.get(symbol)
