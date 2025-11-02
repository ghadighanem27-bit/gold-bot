import numpy as np
import talib
import ta
from lib.signals import log_signal

# --- RSI ---
def get_rsi(df):
    rsi = ta.momentum.RSIIndicator(df["c"], window=14).rsi().iloc[-1]
    price = df["c"].iloc[-1]

    if rsi < 30:
        return 15
    elif rsi > 70:
        return 0
    else:
        return 7.5

# --- MACD ---
def get_macd(prices, fastperiod=12, slowperiod=26, signalperiod=9):
    macd, signal, hist = talib.MACD(
        np.array(prices, dtype=float),
        fastperiod=fastperiod,
        slowperiod=slowperiod,
        signalperiod=signalperiod
    )
    macd_val, signal_val, hist_val = macd[-1], signal[-1], hist[-1]
    if macd_val > signal_val and hist_val > 0:
        return 10
    elif macd_val < signal_val and hist_val < 0:
        return 0
    else:
        return 5

# --- Volume ---
def volume_score(volumes, spike_ratio=1.5):
    vols = np.array(volumes, dtype=float)
    if len(vols) < 5:
        return 5
    current, avg_vol = vols[-1], np.mean(vols[-20:])
    if current > avg_vol * spike_ratio:
        return 10
    elif current < avg_vol * 0.7:
        return 0
    else:
        return 5

# --- Candlestick Patterns ---
def candlestick_score(opens, highs, lows, closes):
    """
    Analyze candlestick patterns and return a score out of 8:
      8 = strong bullish pattern
      4 = neutral / indecisive
      0 = strong bearish pattern
    """
    o = np.array(opens, dtype=float)
    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    c = np.array(closes, dtype=float)

    # --- Common bullish & bearish patterns ---
    bullish = [
        talib.CDLHAMMER(o, h, l, c),
        talib.CDLENGULFING(o, h, l, c),
        talib.CDLMORNINGSTAR(o, h, l, c),
        talib.CDLPIERCING(o, h, l, c),
        talib.CDLDRAGONFLYDOJI(o, h, l, c)
    ]

    bearish = [
        talib.CDLHANGINGMAN(o, h, l, c),
        talib.CDLENGULFING(o, h, l, c),  # same function, negative values = bearish
        talib.CDLEVENINGSTAR(o, h, l, c),
        talib.CDLDARKCLOUDCOVER(o, h, l, c),
        talib.CDLGRAVESTONEDOJI(o, h, l, c)
    ]

    bull_score = sum([b[-1] for b in bullish if b[-1] > 0])
    bear_score = sum([b[-1] for b in bearish if b[-1] < 0])

    if bull_score > abs(bear_score) and bull_score > 0:
        return 8
    elif bear_score < 0 and abs(bear_score) > bull_score:
        return 0
    else:
        return 4

# --- Bollinger Bands ---
def bollinger_score(prices, period=20, nbdev=2):
    closes = np.array(prices, dtype=float)
    upper, middle, lower = talib.BBANDS(closes, timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev)
    cur = closes[-1]
    band_pos = (upper[-1] - cur) / (upper[-1] - lower[-1])
    if band_pos > 0.8:
        return 5
    elif band_pos < 0.2:
        return 0
    else:
        return 3

# --- MACD Divergence ---
def macd_divergence_score(prices, lookback=5):
    closes = np.array(prices, dtype=float)
    macd, signal, _ = talib.MACD(closes)
    price_diff = closes[-1] - closes[-lookback]
    macd_diff = macd[-1] - macd[-lookback]
    if price_diff < 0 and macd_diff > 0:
        return 5
    elif price_diff > 0 and macd_diff < 0:
        return 0
    else:
        return 3

# --- Moving Average Confluence ---
def ma_confluence_score(prices):
    closes = np.array(prices, dtype=float)
    short = talib.SMA(closes, 20)
    mid = talib.SMA(closes, 50)
    long = talib.SMA(closes, 200)
    if short[-1] > mid[-1] > long[-1] or short[-1] < mid[-1] < long[-1]:
        return 2
    else:
        return 1

# --- Combined technical score ---
def technical_score(df):
    prices = df["c"].astype(float).values
    volumes = df["v"].astype(float).values
    opens = df["o"].astype(float).values
    highs = df["h"].astype(float).values
    lows = df["l"].astype(float).values

    total = (
        get_rsi(df)
        + get_macd(prices)
        + volume_score(volumes)
        + candlestick_score(opens, highs, lows, prices)
        + bollinger_score(prices)
        + macd_divergence_score(prices)
        + ma_confluence_score(prices)
    )
    return total
