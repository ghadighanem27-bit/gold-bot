# lib/risk.py

import numpy as np

# ==========================================================
# PERFORMANCE METRICS
# ==========================================================

def compute_winrate_last20(pnls):
    """pnls: list of last closed trade PNLs (positive or negative %)."""
    if len(pnls) == 0:
        return 0.50  # neutral baseline

    last20 = pnls[-20:]
    wins = [p for p in last20 if p > 0]
    return len(wins) / len(last20)


def compute_drawdown(pnls):
    """Compute equity drawdown based on PNL history."""
    if len(pnls) == 0:
        return 0.0

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    return float(dd.min())  # negative number


# ==========================================================
# ADAPTIVE POSITION SIZE (Score-Based)
# ==========================================================

def adaptive_position_size(
    base_amount,
    reinforced_score,
    position_type,  # "LONG" or "SHORT"
    winrate_last20,
    drawdown
):
    """
    Returns adaptive position size using:
    - Trade score (0-100)
    - Winrate
    - Drawdown
    """

    # ---- SCORE FACTOR ----
    if position_type == "LONG":
        score_factor = 0.5 + (reinforced_score - 50) / 100
    else:
        short_strength = 100 - reinforced_score
        score_factor = 0.5 + (short_strength / 200)

    score_factor = max(0.5, min(score_factor, 1.0))

    # ---- PERFORMANCE FACTOR ----
    if winrate_last20 > 0.70:
        performance_factor = 1.30
    elif winrate_last20 > 0.60:
        performance_factor = 1.15
    elif winrate_last20 > 0.50:
        performance_factor = 1.00
    elif winrate_last20 > 0.40:
        performance_factor = 0.80
    else:
        performance_factor = 0.60

    # ---- DRAWDOWN FACTOR ----
    if drawdown < -0.05:
        dd_factor = 0.60
    elif drawdown < -0.03:
        dd_factor = 0.80
    else:
        dd_factor = 1.00

    size = base_amount * score_factor * performance_factor * dd_factor
    size = max(0.008, min(size, 0.30))

    return round(size, 3)


# ==========================================================
# SCORE-AWARE EXIT PROTECTION
# ==========================================================

def should_secure_profit(position, pnl_percent, current_score):
    """
    Determines if profit should be locked based on score decay.
    """

    if pnl_percent < 0.6:
        return False

    # Weakening long
    if position == "BUY" and current_score < 55:
        return True

    # Weakening short
    if position == "SELL" and current_score > 45:
        return True

    return False
# ==========================================================