from binance.client import Client
import pandas as pd
from lib.vars import client
from lib.vars import cfg
from lib.vars import client

def get_data(symbol, interval="5m", limit=200):
    """Fetch recent candles for a given symbol."""
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

def get_price(symbol):
    df = get_data(symbol)
    try:
        return float(df["c"].iloc[-1])
    except:
        raise ValueError("Could not fetch latest price")
    
def get_usdt_balance():
    balance = client.futures_account_balance()

    for item in balance:
        if item["asset"] == "USDT":
            return float(item["balance"])

    return 0.0

def get_futures_price(symbol):
    try:
        data = client.futures_mark_price(symbol=symbol)
        return float(data["markPrice"])
    except Exception as e:
        print(f"⚠️ Futures mark price error: {e}")
        return None