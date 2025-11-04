import numpy as np
import talib
import ta
from .signals import log_signal

# --- RSI ---
def get_rsi(df):
    rsi = ta.momentum.RSIIndicator(df["c"], window=14).rsi().iloc[-1]
    price = df["c"].iloc[-1]

    atr = ta.volatility.AverageTrueRange(high=df["h"], low=df["l"], close=df["c"],window=14).average_true_range().iloc[-1]

    rsi_power = 1.4 + ((atr - 5) / (20-5)) * (1.6-1.4)
    

    score = 15 * (1 - (rsi / 100) ** rsi_power)
    print(f" rsi power {rsi_power:.2f} | rsi score {score:.2f}")
    return score, rsi_power

# --- MACD ---
def get_macd(prices, fastperiod=12, slowperiod=26, signalperiod=9, lookback=20):
    macd, signal, hist = talib.MACD(
        np.array(prices, dtype=float),
        fastperiod=fastperiod,
        slowperiod=slowperiod,
        signalperiod=signalperiod
    )
    macd_val, signal_val, hist_val = macd[-1], signal[-1], hist[-1]
    diff = macd_val - signal_val

    # Define max_diff and max_hist over recent 'lookback' bars
    max_diff = np.max(np.abs(macd[-lookback:] - signal[-lookback:]))
    max_hist = np.max(np.abs(hist[-lookback:]))
    
    # Compute continuous score
    score = 5 + 5 * (diff / max_diff) + 5 * (hist_val / max_hist)
    
    # Clamp score between 0 and 10
    score = max(0, min(10, score))
    
    return score

# --- Volume ---
def volume_score(volumes, spike_ratio=1.5):

    
    low_ratio = 0.7
    vols = np.array(volumes, dtype=float)
    avg_vol = np.mean(vols[-20:])
    current = vols[-1]
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
    max_score = 8
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
    max_score = 5
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
    max_score = 5

    
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


def ma_confluence_score(prices):
    closes = np.array(prices, dtype=float)
    ma_fast = talib.SMA(closes, timeperiod=10)[-1]
    ma_medium = talib.SMA(closes, timeperiod=20)[-1]
    ma_slow = talib.SMA(closes, timeperiod=50)[-1]

    score = 0

    # Si MA rapide > MA moyenne > MA lente → tendance haussière forte
    if ma_fast > ma_medium > ma_slow:
        score = 10
    # Si MA lente > MA moyenne > MA rapide → tendance baissière forte
    elif ma_slow > ma_medium > ma_fast:
        score = 0
    else:
        score = 5  # neutre ou tendance incertaine

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

