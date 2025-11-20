# lib/risk.py

import numpy as np

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


def adaptive_position_size(
    base_amount,
    reinforced_score,
    position_type,  # "LONG" or "SHORT"
    winrate_last20,
    drawdown
):
    """
    Returns the adaptive position size **in the same units as base_amount**.
    """

    # ----- LONG SIZING -----
    if position_type == "LONG":
        score_factor = 0.5 + (reinforced_score - 50) / 100
        score_factor = max(0.5, min(score_factor, 1.0))

    # ----- SHORT SIZING -----
    else:
        short_strength = 100 - reinforced_score
        score_factor = 0.5 + (short_strength / 200)
        score_factor = max(0.5, min(score_factor, 1.0))

    # ----- PERFORMANCE FACTOR -----
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

    # ----- DRAWDOWN FACTOR -----
    if drawdown < -0.05:
        dd_factor = 0.60
    elif drawdown < -0.03:
        dd_factor = 0.80
    else:
        dd_factor = 1.00

    # ----- FINAL SIZE -----
    size = base_amount * score_factor * performance_factor * dd_factor

    # Safety bounds
    size = max(0.008, min(size, 0.30))

    return round(size, 3)
