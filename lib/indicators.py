import numpy as np
import talib
import ta
import datetime


# Small helper
def _clamp_0_100(x):
    return float(max(0.0, min(100.0, x)))


# ---------------------------------------------------------------------------
# 1) MACD MOMENTUM (signal-line slope)
# ---------------------------------------------------------------------------
def macd_momentum_score(prices, fast=12, slow=26, signalperiod=9, lookback=5):
    closes = np.asarray(prices, dtype=float)
    macd, signal, hist = talib.MACD(closes, fastperiod=fast,
                                    slowperiod=slow, signalperiod=signalperiod)

    sig = signal[-lookback:]
    x = np.arange(len(sig))
    # simple linear regression slope of the signal line
    slope, _ = np.polyfit(x, sig, 1)

    # normalize slope relative to price level
    price = closes[-1]
    norm = slope / (price + 1e-9)

    # scale & squash into 0–100
    raw = norm * 3_000     # sensitivity factor
    score = 50.0 + 50.0 * np.tanh(raw)
    score = _clamp_0_100(score)

    print(f" MACD Momentum | score {score:.1f}")
    return score


# ---------------------------------------------------------------------------
# 2) PRICE / VOLUME DIVERGENCE (OBV divergence)
# ---------------------------------------------------------------------------
def obv_divergence_score(df, lookback=20):
    closes = df["c"].astype(float).values
    vols = df["v"].astype(float).values

    obv = talib.OBV(closes, vols)

    p_ret = (closes[-1] - closes[-lookback]) / (closes[-lookback] + 1e-9)
    v_ret = (obv[-1] - obv[-lookback]) / (abs(obv[-lookback]) + 1e-9)

    # Divergence: OBV up while price flat/down → bullish
    div = v_ret - p_ret

    raw = div * 10      # sensitivity
    score = 50.0 + 50.0 * np.tanh(raw)
    score = _clamp_0_100(score)

    print(f" OBV Divergence | score {score:.1f}")
    return score


# ---------------------------------------------------------------------------
# 3) MARKET STRUCTURE (HH/HL/LH/LL)
# ---------------------------------------------------------------------------
def market_structure_score(df, swing_lookback=5):
    closes = df["c"].astype(float).values

    recent = closes[-(swing_lookback + 1):]
    prev_max = recent[:-1].max()
    prev_min = recent[:-1].min()
    last = recent[-1]

    # Simple classification
    if last > prev_max:
        # fresh breakout higher → very bullish
        score = 80.0
    elif last < prev_min:
        # fresh breakdown → very bearish
        score = 20.0
    else:
        # inside range → map relative position
        pos = (last - prev_min) / (prev_max - prev_min + 1e-9)  # 0–1
        score = 20.0 + 60.0 * pos  # 20–80 band

    score = _clamp_0_100(score)
    print(f" Market Structure | score {score:.1f}")
    return score


# ---------------------------------------------------------------------------
# 4) RELATIVE VOLUME + OBV DELTA
# ---------------------------------------------------------------------------
def rvol_obv_score(df, lookback=20):
    closes = df["c"].astype(float).values
    vols = df["v"].astype(float).values

    # Relative volume
    avg_vol = vols[-lookback:-1].mean()
    rvol = vols[-1] / (avg_vol + 1e-9)

    # OBV slope
    obv = talib.OBV(closes, vols)
    obv_slope = (obv[-1] - obv[-5]) / (abs(obv[-5]) + 1e-9)

    # clamp rvol to reasonable range
    rvol_norm = np.clip((rvol - 0.5) / 1.5, -1, 2)  # typical 0–2+
    raw = 0.6 * rvol_norm + 0.4 * obv_slope * 10

    score = 50.0 + 50.0 * np.tanh(raw)
    score = _clamp_0_100(score)

    print(f" RVOL + OBV | score {score:.1f}")
    return score


# ---------------------------------------------------------------------------
# 5) BB SQUEEZE + EXPANSION
# ---------------------------------------------------------------------------
def bb_squeeze_score(prices, period=20, nbdev=2):
    closes = np.asarray(prices, dtype=float)
    upper, middle, lower = talib.BBANDS(closes, timeperiod=period,
                                        nbdevup=nbdev, nbdevdn=nbdev, matype=0)

    cur = closes[-1]
    upper_val, mid_val, lower_val = upper[-1], middle[-1], lower[-1]

    # Bandwidth as % of price
    width = (upper_val - lower_val) / (mid_val + 1e-9)

    recent_width = (upper - lower) / (middle + 1e-9)
    ref = np.percentile(recent_width[-50:], 50)  # median

    # squeeze is when width << median
    squeeze = np.clip((ref - width) / (ref + 1e-9), -1, 1)
    # price position inside bands (0 = upper, 1 = lower)
    band_pos = (upper_val - cur) / (upper_val - lower_val + 1e-9)

    raw = 1.2 * squeeze + 0.8 * (0.5 - band_pos)  # higher when squeeze + near lower/mid
    score = 50.0 + 50.0 * np.tanh(raw)

    score = _clamp_0_100(score)
    print(f" BB Squeeze/Expansion | score {score:.1f}")
    return score


# ---------------------------------------------------------------------------
# 6) RSI SYSTEM (value + slope + compression)
# ---------------------------------------------------------------------------
def rsi_system_score(df, period=14, slope_lookback=5):
    closes = df["c"].astype(float).values
    rsi = ta.momentum.RSIIndicator(pd_series := df["c"].astype(float), window=period).rsi().values

    r = rsi[-1]
    prev = rsi[-slope_lookback]
    slope = (r - prev) / slope_lookback

    # compression = how tight RSI has been (low std means compression)
    window = rsi[-period:]
    compression = 1.0 / (np.std(window) + 1e-6)  # bigger when squeezed

    # base: prefer RSI between 50–65 with positive slope
    center = 57.5
    spread = 20.0
    val_component = 1.0 - abs(r - center) / spread  # ~1 near center, <0 far
    val_component = np.clip(val_component, -1, 1)

    raw = 0.6 * val_component + 0.3 * (slope / 2.0) + 0.1 * np.tanh(compression / 5.0)
    score = 50.0 + 50.0 * np.tanh(raw)

    score = _clamp_0_100(score)
    print(f" RSI System | score {score:.1f}")
    return score


# ---------------------------------------------------------------------------
# 7) MA SLOPE + MULTI-TF ALIGNMENT
# ---------------------------------------------------------------------------
def ma_system_score(prices):
    closes = np.asarray(prices, dtype=float)

    ma_fast = talib.SMA(closes, timeperiod=10)
    ma_med = talib.SMA(closes, timeperiod=20)
    ma_slow = talib.SMA(closes, timeperiod=50)

    f, m, s = ma_fast[-1], ma_med[-1], ma_slow[-1]
    price = closes[-1]

    # slopes
    f_slope = (ma_fast[-1] - ma_fast[-5]) / (price + 1e-9)
    m_slope = (ma_med[-1] - ma_med[-5]) / (price + 1e-9)

    # alignment bonus
    align = 0.0
    if f > m > s:
        align = 1.0        # bullish stacked
    elif s > m > f:
        align = -1.0       # bearish stacked

    raw = 1.5 * f_slope * 20 + 1.0 * m_slope * 10 + 1.2 * align
    score = 50.0 + 50.0 * np.tanh(raw)

    score = _clamp_0_100(score)
    print(f" MA System | score {score:.1f}")
    return score


# ---------------------------------------------------------------------------
# 8) VOLATILITY REGIME (ATR change + ADX slope)
# ---------------------------------------------------------------------------
def volatility_regime_score(df, atr_period=14, adx_period=14):
    closes = df["c"].astype(float).values
    highs = df["h"].astype(float).values
    lows = df["l"].astype(float).values

    atr = talib.ATR(highs, lows, closes, timeperiod=atr_period)
    adx = talib.ADX(highs, lows, closes, timeperiod=adx_period)

    atr_change = (atr[-1] - atr[-5]) / (atr[-5] + 1e-9)
    adx_slope = (adx[-1] - adx[-5]) / 20.0  # ADX is in 0–100

    # trend-friendly regime: rising ATR + rising ADX
    raw = 0.7 * atr_change * 5 + 0.9 * adx_slope
    score = 50.0 + 50.0 * np.tanh(raw)

    score = _clamp_0_100(score)
    print(f" Volatility Regime | score {score:.1f}")
    return score


# ---------------------------------------------------------------------------
# MASTER TECHNICAL SCORE (0–100)
# ---------------------------------------------------------------------------
def technical_score(df, symbol=None):
    """
    Returns a single technical score in the range [0, 100].

    Higher → more bullish / higher probability to go long.
    Lower  → more bearish / more short / avoid-long.
    """

    prices = df["c"].astype(float).values

    scores = {
        "macd_mom":        macd_momentum_score(prices),
        "obv_div":         obv_divergence_score(df),
        "market_struct":   market_structure_score(df),
        "rvol_obv":        rvol_obv_score(df),
        "bb_squeeze":      bb_squeeze_score(prices),
        "rsi_system":      rsi_system_score(df),
        "ma_system":       ma_system_score(prices),
        "vol_regime":      volatility_regime_score(df),
    }

    # weights must sum to 1.0
    weights = {
        "macd_mom":      0.15,
        "obv_div":       0.12,
        "market_struct": 0.10,
        "rvol_obv":      0.12,
        "bb_squeeze":    0.14,
        "rsi_system":    0.13,
        "ma_system":     0.14,
        "vol_regime":    0.10,
    }

    total = 0.0
    for k, w in weights.items():
        total += scores[k] * w

    total = _clamp_0_100(total)

    print(f" TOTAL TECHNICAL SCORE | {total:.1f}")

    return total
