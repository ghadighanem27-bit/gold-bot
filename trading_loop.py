import time
import datetime

from lib.vars import (
    symbol,
    trade_amount,
    take_profit,
    stop_loss,
    loop_interval,
)

from lib.market_data import get_futures_price, get_data
from lib.indicators import technical_score, market_regime
from lib.database_manager import record_score
from lib.telegram_bot import send_message_sync
from lib.position_manager import PositionManager
from lib.signals import signals
from lib.risk import (
    compute_winrate_last20,
    compute_drawdown,
    adaptive_position_size
)


LTF_TIMEFRAME = "5m"
HTF_TIMEFRAME = "15m"

score_update_interval = 300  # 5 min
last_score_time = 0
last_score = None
last_ltf_df = None

pm = PositionManager()


def trading_loop():
    send_message_sync(f"🚀 Trading loop started for <b>{symbol}</b>")
    print(f"🚀 Trading loop started for {symbol}")

    global last_score_time, last_score, last_ltf_df

    while True:
        try:
            # ------------------- PRICE -------------------
            price = get_futures_price(symbol)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Mark Price: {price}")

            if price is None:
                time.sleep(loop_interval)
                continue

            # AUTO TP/SL
            pm.check_auto_close(price)
            pm.check_progressive_tp(price)


            # ------------------- COOLDOWN -------------------
            if pm.cooldown_until:
                now = datetime.datetime.utcnow()
                if now < pm.cooldown_until:
                    remain = int((pm.cooldown_until - now).total_seconds())
                    print(f"⏳ Cooldown active ({remain}s). Skipping entries.")
                    time.sleep(loop_interval)
                    continue

            # ---------------------------------------------------
            # UPDATE SCORE EVERY 5 MINUTES
            # ---------------------------------------------------
            now_ts = time.time()
            if now_ts - last_score_time >= score_update_interval:

                print("🧮 Updating technical score on LTF + HTF...")

                # Fetch LTF dataframe
                df_ltf = get_data(symbol, interval=LTF_TIMEFRAME)
                time.sleep(0.8)

                # Fetch HTF dataframe
                df_htf = get_data(symbol, interval=HTF_TIMEFRAME)
                time.sleep(0.8)

                last_ltf_df = df_ltf  # Store for volatility calculations

                # Compute final score (0–100)
                ltf_score = technical_score(df_ltf, symbol)
                htf_score = technical_score(df_htf, symbol)

                blended_score = (0.65 * ltf_score) + (0.35 * htf_score)
                last_score = blended_score
                last_score_time = now_ts

                # Compute regime + volatility
                regime, _ = market_regime(df_ltf)
                entry_volatility = df_ltf["c"].pct_change().std() * 100
                entry_time = datetime.datetime.utcnow()

                # ------------------- STORE SCORE -------------------
                try:
                    pm.last_score_id = record_score(
                        symbol=symbol,
                        ltf_score=float(ltf_score),
                        htf_score=float(htf_score),
                        reinforced_score=float(blended_score),
                        decision=None,
                        regime=regime,
                        entry_volatility=float(entry_volatility),
                        entry_time=entry_time,
                        trade_id=None
                    )
                    print(f"✅ Score saved (ID={pm.last_score_id})")
                except Exception as e:
                    print(f"⚠️ Failed to save score: {e}")

                print(f"📊 LTF={ltf_score:.2f} | HTF={htf_score:.2f} | FINAL={blended_score:.2f}")

            # If score not updated yet, skip entries
            if last_score is None:
                time.sleep(loop_interval)
                continue

            # ------------------- SIGNAL ENGINE -------------------
            decision = signals(
                last_ltf_df,
                price,
                symbol,
                pm,
                trade_amount,
                take_profit,
                stop_loss
            )
            print(f"➡️ Signal = {decision}")

            # ------------------- ENTRY -------------------
            if pm.position is None:
                # --- Compute risk parameters ---
                winrate_last20 = compute_winrate_last20(pm.pnl_history)
                drawdown = compute_drawdown(pm.pnl_history)

                # LONG or SHORT side
                if decision== "BUY":
                    pos_type = "LONG"
                elif decision == "SELL":
                    pos_type = "SHORT"
                else:
                    pos_type = None

                if pos_type:
                    # Adaptive amount (USDT fraction OR quantity depending on your system)
                    size = adaptive_position_size(
                        base_amount=trade_amount,
                        reinforced_score=last_score,
                        position_type=pos_type,
                        winrate_last20=winrate_last20,
                        drawdown=drawdown
                    )

                    print(f"📐 Adaptive Size: {size}")

                    pm.open_position(pos_type, price, size, take_profit, stop_loss)


            time.sleep(loop_interval)

        except Exception as e:
            print(f"⚠️ Error in loop: {e}")
            send_message_sync(f"⚠️ Error in trading_loop: {e}")
            time.sleep(loop_interval)
