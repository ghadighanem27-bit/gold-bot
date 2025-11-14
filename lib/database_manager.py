import psycopg2
from psycopg2.extras import RealDictCursor
import datetime
from lib.vars import cfg


# ---------------------------------------------
#  DB CONNECTION
# ---------------------------------------------
def get_connection():
    return psycopg2.connect(
        cfg["DATABASE_URL"],
        cursor_factory=RealDictCursor
    )


# ---------------------------------------------
#  RECORD TRADE
# ---------------------------------------------
def record_trade(symbol, side, entry_price, exit_price, pnl_percent, tp_hit=False, sl_hit=False):
    if not symbol:
        print("⚠️ No symbol provided, skipping database insert.")
        return None

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Convert all types to safe Python primitives
        entry_price = float(entry_price)
        exit_price = float(exit_price)
        pnl_percent = float(pnl_percent)

        # Postgres wants integers for booleans (TRUE/FALSE also work)
        tp_hit = int(bool(tp_hit))
        sl_hit = int(bool(sl_hit))

        cur.execute("""
            INSERT INTO trades (
                timestamp_open,
                timestamp_close,
                symbol,
                side,
                entry_price,
                exit_price,
                pnl_percent,
                take_profit_hit,
                stop_loss_hit
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
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

        trade_id = cur.fetchone()["id"]  # SAFE fetch

        conn.commit()
        return trade_id

    except Exception as e:
        print(f"❌ Database error in record_trade(): {e}")
        return None

    finally:
        cur.close()
        conn.close()


# ---------------------------------------------
#  GET STATS
# ---------------------------------------------
def get_stats():
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) AS total, COALESCE(AVG(pnl_percent), 0) AS avg_pnl FROM trades")
        totals = cur.fetchone() or {"total": 0, "avg_pnl": 0}

        total_trades = totals.get("total", 0)
        avg_pnl = totals.get("avg_pnl", 0)

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


# ---------------------------------------------
#  RECORD INDICATOR SCORES
# ---------------------------------------------
def record_scores(timestamp, symbol, scores, trade_id=None):
    if not symbol:
        print("⚠️ No symbol provided to record_scores(). Skipping.")
        return
    
    # Convert sets inside 'scores' to integers
    for key, value in scores.items():
        if isinstance(value, set):
            scores[key] = sum(value)  # or int(max(value))

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO indicator_scores (
                timestamp, symbol,
                rsi, volume, macd, candlestick,
                bollinger, macd_divergence, ma_confluence,
                total, trade_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            timestamp,
            symbol,
            scores.get("rsi", 0),
            scores.get("volume", 0),
            scores.get("macd", 0),
            scores.get("candlestick", 0),
            scores.get("bollinger", 0),
            scores.get("macd_divergence", 0),
            scores.get("ma_confluence", 0),
            scores.get("total", 0),
            trade_id
        ))

        conn.commit()

    except Exception as e:
        print(f"⚠️ Database error in record_scores(): {e}")

    finally:
        cur.close()
        conn.close()