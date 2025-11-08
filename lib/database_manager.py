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

    # ✅ Convert to native Python types
    entry_price = float(entry_price)
    exit_price = float(exit_price)
    pnl_percent = float(pnl_percent)

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

    try:
        # Total trades + avg pnl
        cur.execute("SELECT COUNT(*) AS total, COALESCE(AVG(pnl_percent), 0) AS avg_pnl FROM trades")
        totals = cur.fetchone() or {"total": 0, "avg_pnl": 0}
        total_trades = totals.get("total", 0)
        avg_pnl = totals.get("avg_pnl", 0)

        # Winrate
        cur.execute("SELECT COUNT(*) AS wins FROM trades WHERE pnl_percent > 0")
        wins = cur.fetchone() or {"wins": 0}
        winrate = (wins.get("wins", 0) / total_trades * 100) if total_trades > 0 else 0

    except Exception as e:
        print(f"⚠️ Database error in get_stats(): {e}")
        total_trades, avg_pnl, winrate = 0, 0, 0

    finally:
        cur.close()
        conn.close()

    return {
        "total_trades": total_trades,
        "avg_pnl": avg_pnl,
        "winrate": winrate
    }

