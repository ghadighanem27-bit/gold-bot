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
#  RECORD TRADE (FINAL WORKING VERSION)
# ---------------------------------------------
def record_trade(symbol, side, entry_price, exit_price, pnl_percent, tp_hit=False, sl_hit=False):
    if not symbol:
        print("⚠️ No symbol provided, skipping database insert.")
        return None

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Convert values to safe formats
        entry_price = float(entry_price)
        exit_price = float(exit_price)
        pnl_percent = float(pnl_percent)

        # Postgres BOOLEAN expects True/False
        tp_hit = bool(tp_hit)
        sl_hit = bool(sl_hit)

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
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
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

        result = cur.fetchone()
        if not result:
            print("❌ ERROR: No trade ID returned by DB.")
            return None

        trade_id = result["id"]
        conn.commit()

        print(f"✅ Trade inserted into DB with ID {trade_id}")
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

    # Convert sets to integers if needed
    for key, value in scores.items():
        if isinstance(value, set):
            scores[key] = sum(value)

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO technical_scores (
                timestamp, symbol,
                rsi, volume, macd, candlestick,
                bollinger, macd_divergence, ma_confluence,
                total, trade_id
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            scores.get("rsi"),
            scores.get("volume"),
            scores.get("macd"),
            scores.get("candlestick"),
            scores.get("bollinger"),
            scores.get("macd_divergence"),
            scores.get("ma_confluence"),
            scores.get("total"),
            trade_id
        ))

        conn.commit()

    except Exception as e:
        print(f"⚠️ Database error in record_scores(): {e}")

    finally:
        cur.close()
        conn.close()
