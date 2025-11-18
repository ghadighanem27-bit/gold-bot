import psycopg2
import os

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)


def record_score(symbol, ltf_score, htf_score, reinforced_score, decision):
    """
    Insert a new MTF score row.
    trade_result stays NULL until trade closes.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO mtf_scores (symbol, ltf_score, htf_score, reinforced_score, decision)
            VALUES (%s, %s, %s, %s, %s)
        """, (symbol, ltf_score, htf_score, reinforced_score, decision))

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
