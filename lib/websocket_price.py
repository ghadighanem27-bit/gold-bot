# lib/websocket_price.py
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
from lib.vars import cfg
import threading

# Shared dictionary storing all symbol prices
LATEST_MARK_PRICE = {}

def start_websocket(symbol):
    """
    Starts a websocket stream for Binance USDT-M Futures mark price.
    Updates LATEST_MARK_PRICE[symbol] with real-time prices.
    """

    def handle_message(_, msg):
        try:
            price = float(msg["p"])
            LATEST_MARK_PRICE[symbol] = price
        except:
            pass

    ws = UMFuturesWebsocketClient()

    # Choose correct environment
    if cfg["binance"]["futures_env"] == "testnet":
        ws.API_URL = "wss://stream.binancefuture.com"
    else:
        ws.API_URL = "wss://fstream.binance.com"

    ws.start()

    # Subscribe to mark price stream
    ws.mark_price(
        symbol=symbol.lower(),  # lowercase required for this client
        id=1,
        callback=handle_message
    )

    print(f"📡 WebSocket started for {symbol}")
    return ws


def get_ws_price(symbol):
    """Return latest streamed price or None if no data yet."""
    return LATEST_MARK_PRICE.get(symbol)