import psycopg2
from psycopg2.extras import RealDictCursor
import datetime
from lib.vars import cfg  # still okay to load YAML

# --- Connect using full DATABASE_URL ---
def get_connection():
    return psycopg2.connect(
        cfg["DATABASE_URL"],
        cursor_factory=RealDictCursor
    )


# --- Record a trade ---
def record_trade(symbol, side, entry_price, exit_price, pnl_percent, tp_hit=False, sl_hit=False):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO trades (
            timestamp_open, timestamp_close, symbol, side,
            entry_price, exit_price, pnl_percent, take_profit_hit, stop_loss_hit
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        datetime.datetime.utcnow(),
        datetime.datetime.utcnow(),
        symbol,
        side,
        entry_price,
        exit_price,
        pnl_percent,
        tp_hit,
        sl_hit
    ))
    conn.commit()
    cur.close()
    conn.close()


# --- Get stats ---
def get_stats():
    conn = get_connection()
    cur = conn.cursor()

    # Total trades + average pnl
    cur.execute("SELECT COUNT(*) AS total, AVG(pnl_percent) AS avg_pnl FROM trades")
    totals = cur.fetchone() or {"total": 0, "avg_pnl": 0}
    total_trades = totals["total"] or 0
    avg_pnl = totals["avg_pnl"] or 0

    # Winrate
    cur.execute("SELECT COUNT(*) AS wins FROM trades WHERE pnl_percent > 0")
    wins = cur.fetchone() or {"wins": 0}
    winrate = (wins["wins"] / total_trades * 100) if total_trades > 0 else 0

    cur.close()
    conn.close()

    return {
        "total_trades": total_trades,
    }