import psycopg2
import os
from lib.vars import cfg

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(cfg["database"]["url"])


def record_score(symbol, ltf_score, htf_score, reinforced_score, decision, trade_id=None):
    """
    Saves a score row. trade_id is optional (NULL = scoring cycle with no trade).
    """
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO mtf_scores (symbol, ltf_score, htf_score, reinforced_score, decision, trade_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (symbol, ltf_score, htf_score, reinforced_score, decision, trade_id))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print(f"⚠️ Failed to record score: {e}")


def update_score_with_result(score_id, pnl):
    """Called when a trade closes."""
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE mtf_scores
            SET trade_result = %s
            WHERE id = %s
        """, (pnl, score_id))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print(f"⚠️ Failed to update score result: {e}")
        
    return score_id

def attach_trade_id_to_last_score(trade_id):
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE mtf_scores
            SET trade_id = %s
            WHERE trade_id IS NULL
            ORDER BY id DESC
            LIMIT 1
        """, (trade_id,))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print(f"⚠️ Failed to attach trade id: {e}")
