from binance.client import Client
import pandas as pd
from lib.vars import client

def get_data(symbol, interval="5m", limit=200):
    """Fetch recent candles for a given symbol."""
    symbol = cfg["symbol"].strip().upper().replace("/", "")
    candles = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(candles, columns=[
        "t","o","h","l","c","v","ct","qv","n","tb","tbv","ig"
    ])
    df["o"] = df["o"].astype(float)
    df["h"] = df["h"].astype(float)
    df["l"] = df["l"].astype(float)
    df["c"] = df["c"].astype(float)
    df["v"] = df["v"].astype(float)
    return df
