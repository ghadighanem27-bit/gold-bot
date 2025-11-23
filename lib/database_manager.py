import psycopg2
from lib.vars import cfg

def get_conn():
    return psycopg2.connect(cfg["database"]["url"])


# ----------------------------------------------------------
# INSERT NEW SCORE ROW
# ----------------------------------------------------------
def record_score(
    symbol,
    ltf_score,
    htf_score,
    reinforced_score,
    decision,
    regime,
    entry_volatility,
    entry_time,
    trade_id=None
):
    """
    Creates a new MTF score row (one per cycle).
    """
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO mtf_scores (
                symbol,
                ltf_score,
                htf_score,
                reinforced_score,
                decision,
                regime,
                entry_volatility,
                entry_time,
                trade_id
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            symbol,
            ltf_score,
            htf_score,
            reinforced_score,
            decision,
            regime,
            entry_volatility,
            entry_time,
            trade_id
        ))

        score_id = cur.fetchone()[0]
        conn.commit()

        cur.close()
        conn.close()
        return score_id

    except Exception as e:
        print(f"⚠️ Failed to insert score: {e}")
        return None


# ----------------------------------------------------------
# ATTACH TRADE ID TO SPECIFIC SCORE ID
# ----------------------------------------------------------
def attach_trade_id_to_score_id(score_id, trade_id):
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE mtf_scores
            SET trade_id = %s
            WHERE id = %s
        """, (trade_id, score_id))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print(f"⚠️ Failed to attach trade id to score {score_id}: {e}")


# ----------------------------------------------------------
# UPDATE RESULT WHEN TRADE CLOSES
# ----------------------------------------------------------
def update_score_with_result(
    score_id,
    pnl,
    exit_time,
    exit_volatility,
    duration_seconds
):
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE mtf_scores
            SET trade_result = %s,
                exit_time = %s,
                exit_volatility = %s,
                duration_seconds = %s
            WHERE id = %s
        """, (
            pnl,
            exit_time,
            exit_volatility,
            duration_seconds,
            score_id
        ))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print(f"⚠️ Failed to update score result: {e}")