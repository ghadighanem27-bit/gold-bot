import numpy as np
import talib
import ta
from lib.signals import log_signal

# --- RSI ---
def get_rsi(df):
    rsi = ta.momentum.RSIIndicator(df["c"], window=14).rsi().iloc[-1]
    price = df["c"].iloc[-1]

    score = 15 * (1 - (rsi / 100) ** 2)
    return score

# --- MACD ---
def get_macd(prices, fastperiod=12, slowperiod=26, signalperiod=9):
    macd, signal, hist = talib.MACD(
        np.array(prices, dtype=float),
        fastperiod=fastperiod,
        slowperiod=slowperiod,
        signalperiod=signalperiod
    )
    macd_val, signal_val, hist_val = macd[-1], signal[-1], hist[-1]
    diff = macd_val - signal_val
    
    # Compute continuous score
    score = 5 + 5 * (diff / max_diff) + 5 * (hist_val / max_hist)
    
    # Clamp score between 0 and 10
    score = max(0, min(10, score))
    
    return score

# --- Volume ---
def volume_score(volumes, spike_ratio=1.5):
    vols = np.array(volumes, dtype=float)
        # Continuous scoring
    ratio = current / avg_vol
    
    if ratio > spike_ratio:
        # Scale from spike_ratio → 2*spike_ratio → 5–10
        score = 5 + 5 * min((ratio - spike_ratio) / spike_ratio, 1)
    elif ratio < low_ratio:
        # Scale from 0 → low_ratio → 0–5
        score = 5 * min(ratio / low_ratio, 1)
    else:
        # Neutral
        score = 5
    
    # Clamp to 0–10
    score = max(0, min(10, score))
    return score

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

    # Avoid division by zero
    total = bull_score + bear_score
    if total == 0:
        return max_score / 2  # Neutral

    # Continuous score formula: weighted proportion of bullishness
    score = max_score * (bull_score / total)

    # Clamp between 0 and max_score
    score = max(0, min(max_score, score))

    return score

# --- Bollinger Bands ---
def bollinger_score(prices, period=20, nbdev=2):
    """
    Calculate Bollinger Bands and return a score out of 5:
      5 = strong buy (price near lower band)
      3 = hold (price near middle band)
      0 = sell (price near upper band)
    """
    closes = np.array(prices, dtype=float)
    upper, middle, lower = talib.BBANDS(
        closes, timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev, matype=0
    )
    cur = closes[-1]
    upper_val, lower_val = upper[-1], lower[-1]

  # Prevent divide-by-zero
    if (upper_val - lower_val) == 0:
        return max_score / 2  # neutral

    # Position within the band: 0 → at upper band, 1 → at lower band
    band_pos = (upper_val - cur) / (upper_val - lower_val)
    
    # Continuous score
    score = max_score * band_pos

    # Clamp between 0 and max_score
    score = max(0, min(max_score, score))

    return score

# --- MACD Divergence ---
def macd_divergence_score(prices, lookback=5):
    closes = np.array(prices, dtype=float)
    macd, signal, _ = talib.MACD(closes)
    price_diff = closes[-1] - closes[-lookback]
    macd_diff = macd[-1] - macd[-lookback]
    
    # Compute divergence strength
    divergence = -price_diff * macd_diff  # negative * positive → bullish, etc.
    
    # Scale score proportionally
    # We'll normalize by the largest magnitude over lookback
    price_range = np.max(closes[-lookback:]) - np.min(closes[-lookback:])
    macd_range = np.max(macd[-lookback:]) - np.min(macd[-lookback:])
    if price_range == 0 or macd_range == 0:
        return max_score / 2  # neutral
    
    # Normalized divergence [-1, 1]
    norm_div = divergence / (price_range * macd_range)
    
    # Convert to 0 → max_score
    score = max_score * (0.5 + 0.5 * norm_div)  # 0.5 = neutral
    
    # Clamp between 0 and max_score
    score = max(0, min(max_score, score))
    
    return score

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

