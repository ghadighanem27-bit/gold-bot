import numpy as np
import talib
import ta
import datetime

# --- RSI ---
def get_rsi(df):
    rsi = ta.momentum.RSIIndicator(df["c"], window=14).rsi().iloc[-1]
    price = df["c"].iloc[-1]

    atr = ta.volatility.AverageTrueRange(high=df["h"], low=df["l"], close=df["c"],window=14).average_true_range().iloc[-1]

    atr_ratio = (atr / price)*100 #ATR as % of price

    atr_min = 0.01 #calm
    atr_max = 2 #volatile

    #linear scaling
    rsi_power = 1.4 + ((atr_ratio - atr_min) / (atr_max-atr_min)) * (1.6 - 1.4)
    
    #clamp
    rsi_power = max(min(rsi_power, 1.6), 1.4)

    score = 1 - (rsi / 100) ** rsi_power
    print(f" RSI | power {rsi_power:.2f} |  score {score:.2f}")

    return score

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

    score = score / 10  # Normalize to 0-1
    print(f" MACD | score {score:.2f}")
    
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
    # Normalize to 0–1
    score /= 10
    print(f" Volume | score {score:.2f}")
    return score

# --- Candlestick Patterns ---
def candlestick_score(opens, highs, lows, closes):
    """
    Analyze candlestick patterns and return a score from 0 to 1.
    SAFE VERSION — prevents uninitialized variables.
    """
    max_score = 8

    o = np.array(opens, dtype=float)
    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    c = np.array(closes, dtype=float)

    # Initialize safely
    bull_score = 0.0
    bear_score = 0.0

    try:
        bullish = [
            talib.CDLHAMMER(o, h, l, c),
            talib.CDLENGULFING(o, h, l, c),
            talib.CDLMORNINGSTAR(o, h, l, c),
            talib.CDLPIERCING(o, h, l, c),
            talib.CDLDRAGONFLYDOJI(o, h, l, c),
        ]

        bearish = [
            talib.CDLHANGINGMAN(o, h, l, c),
            talib.CDLEVENINGSTAR(o, h, l, c),
            talib.CDLDARKCLOUDCOVER(o, h, l, c),
            talib.CDLGRAVESTONEDOJI(o, h, l, c),
        ]

        bull_score = sum(b[-1] for b in bullish if b[-1] > 0)
        bear_score = sum(b[-1] for b in bearish if b[-1] < 0)

    except Exception as e:
        print(f"⚠️ TA-Lib candlestick error: {e}")
        return 0.5  # neutral fallback

    total = bull_score + abs(bear_score)

    if total == 0:
        return 0.5  # neutral when no patterns found

    # Normalize to 0–1
    score = bull_score / total

    score = max(0, min(score, 1))
    print(f" Candle Stick | score {score:.2f}")
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
    # Normalize to 0–1
    score /= max_score
    print(f" Bollinger | score {score:.2f}")
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
    score /= max_score  # Normalize to 0-1
    print(f" MACD Divergence | score {score:.2f}")
    return score


def ma_confluence_score(prices):
    closes = np.array(prices, dtype=float)
    ma_fast_series = talib.SMA(closes, timeperiod=10)
    ma_med_series = talib.SMA(closes, timeperiod=20)
    ma_slow_series = talib.SMA(closes, timeperiod=50)

    ma_fast = ma_fast_series[-1]
    ma_medium = ma_med_series[-1]
    ma_slow = ma_slow_series[-1]

    score = 0.5  # default neutral in [0,1] terms

    # ensure we have valid values
    if np.isnan(ma_fast) or np.isnan(ma_medium) or np.isnan(ma_slow):
        print(f" MA Confluence | score {score:.2f}")
        return score

    # distance-based trend strength
    # normalize by price to avoid instrument bias
    price = closes[-1]
    dist_fast_med = (ma_fast - ma_medium) / price
    dist_med_slow = (ma_medium - ma_slow) / price

    bullish_strength = 0
    bearish_strength = 0

    # Bullish stacking
    if ma_fast > ma_medium > ma_slow:
        bullish_strength = max(0, dist_fast_med) + max(0, dist_med_slow)
    # Bearish stacking
    elif ma_slow > ma_medium > ma_fast:
        bearish_strength = max(0, -dist_fast_med) + max(0, -dist_med_slow)

    # Convert to score 0–1 with a soft cap
    scale = 0.05  # sensitivity
    trend_score = np.tanh((bullish_strength - bearish_strength) / scale)

    # trend_score in [-1,1] → map to [0,1]
    score = 0.5 + 0.5 * trend_score

    print(f" MA Confluence | score {score:.2f}")
    return float(score)

def market_regime(df):
    """
    Simple regime detector:
      returns ('trending', strength) or ('ranging', strength)
      strength in [0,1]
    """
    closes = df["c"].astype(float).values
    highs = df["h"].astype(float).values
    lows  = df["l"].astype(float).values

    # ADX for trend strength
    try:
        adx = talib.ADX(highs, lows, closes, timeperiod=14)
        adx_val = adx[-1]
    except Exception:
        adx_val = 20  # neutral-ish

    # Bollinger bandwidth as a proxy for volatility state
    upper, middle, lower = talib.BBANDS(closes, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    bb_width = (upper[-1] - lower[-1]) / middle[-1] if middle[-1] != 0 else 0

    # Simple logic:
    # ADX > 25 and bb_width reasonably high → trending
    trending_strength = 0.0
    ranging_strength = 0.0

    if adx_val > 25 and bb_width > 0.02:
        trending_strength = min(1.0, (adx_val - 25) / 15.0)  # ADX 25–40 → 0–1
    else:
        ranging_strength = 1.0 - min(1.0, max(0.0, (adx_val - 15) / 10.0))

    if trending_strength >= ranging_strength:
        return "trending", trending_strength
    else:
        return "ranging", ranging_strength

def technical_score(df, symbol=None):
    prices = df["c"].astype(float).values
    volumes = df["v"].astype(float).values
    opens = df["o"].astype(float).values
    highs = df["h"].astype(float).values
    lows = df["l"].astype(float).values

    # --- Individual indicator scores ---
    scores = {
        "rsi": float(get_rsi(df)),
        "macd": float(get_macd(prices)),
        "volume": float(volume_score(volumes)),
        "candlestick": float(candlestick_score(opens, highs, lows, prices)),
        "bollinger": float(bollinger_score(prices)),
        "macd_divergence": float(macd_divergence_score(prices)),
        "ma_confluence": float(ma_confluence_score(prices)),
    }

    regime, regime_strength = market_regime(df)
    print(f" REGIME | {regime} ({regime_strength:.2f})")

    # --- Weighted total ---
    weights = {
        "rsi": 0.15,
        "macd": 0.16,
        "volume": 0.10,
        "candlestick": 0.10,
        "bollinger": 0.18,
        "macd_divergence": 0.13,
        "ma_confluence": 0.18,
    }

      # Light regime-aware adjustments (no big surgery)
    if regime == "trending":
        factor = 0.1 * regime_strength  # up to ±10%
        weights["macd"] *= (1 + factor)
        weights["ma_confluence"] *= (1 + factor)
        weights["bollinger"] *= (1 - factor)
        weights["rsi"] *= (1 - factor)
    else:  # ranging
        factor = 0.1 * regime_strength
        weights["bollinger"] *= (1 + factor)
        weights["rsi"] *= (1 + factor)
        weights["macd"] *= (1 - factor)
        weights["ma_confluence"] *= (1 - factor)

    # optional: renormalize weights to sum to 1
    w_sum = sum(weights.values())
    weights = {k: v / w_sum for k, v in weights.items()}

    total = sum(scores[k] * weights[k] for k in scores)
    print(f" TOTAL TECHNICAL SCORE | {total:.2f}")

    # Add total to dict for DB insert
    scores["total"] = float(total)

    print(f"----- {total:.2f} -----\n")
    return total

