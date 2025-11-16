import pandas as pd
from lib.vars import client
from lib.websocket_price import get_ws_price

def get_data(symbol: str, interval: str = "5m", limit: int = 200) -> pd.DataFrame:
    """Fetch recent klines (candles) for a given symbol (Futures testnet/real-compatible)."""
    candles = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(candles, columns=[
        "t","o","h","l","c","v","ct","qv","n","tb","tbv","ig"
    ])
    df["o"] = df["o"].astype(float)
    df["h"] = df["h"].astype(float)
    df["l"] = df["l"].astype(float)
    df["c"] = df["c"].astype(float)
    df["v"] = df["v"].astype(float)
    return df

def get_price(symbol: str) -> float:
    df = get_data(symbol, limit=1)
    try:
        return float(df["c"].iloc[-1])
    except Exception:
        raise ValueError("Could not fetch latest price")

def get_futures_price(symbol):
    # Preferred: websocket real-time price
    price = get_ws_price(symbol)
    if price is not None:
        return price

    # Fallback to API (rare)
    try:
        data = client.futures_mark_price(symbol=symbol)
        return float(data["markPrice"])
    except:
        return None

def get_usdt_balance() -> float:
    """Return total USDT futures wallet balance."""
    try:
        balances = client.futures_account_balance()
    except Exception as e:
        print(f"⚠️ futures_account_balance error: {e}")
        return 0.0

    for item in balances:
        if item.get("asset") == "USDT":
            return float(item.get("balance", 0.0))

    return 0.0