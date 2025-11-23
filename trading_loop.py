import time
import datetime

from lib.vars import (
    symbol,
    trade_amount,
    take_profit,
    stop_loss,
    loop_interval,
)

from lib.risk import compute_winrate_last20, compute_drawdown, adaptive_position_size
from lib.market_data import get_futures_price, get_data
from lib.indicators import technical_score
from lib.database_manager import record_score
from lib.telegram_bot import send_message_sync
from lib.position_manager import PositionManager
from lib.signals import signals

LTF_TIMEFRAME = "5m"
HTF_TIMEFRAME = "15m"

score_update_interval = 300  # 5 minutes
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
            # ================= PRICE =================
            price = get_futures_price(symbol)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Mark Price: {price}")

            if price is None:
                time.sleep(loop_interval)
                continue

            # ================= COOLDOWN =================
            if pm.cooldown_until:
                now = datetime.datetime.utcnow()
                if now < pm.cooldown_until:
                    remain = int((pm.cooldown_until - now).total_seconds())
                    print(f"⏳ Cooldown active ({remain}s). Skipping.")
                    time.sleep(loop_interval)
                    continue

            # ================= SCORE UPDATE =================
            now_ts = time.time()

            if now_ts - last_score_time >= score_update_interval:
                print("🧮 Updating technical score...")

                df_ltf = get_data(symbol, interval=LTF_TIMEFRAME)
                time.sleep(0.5)

                df_htf = get_data(symbol, interval=HTF_TIMEFRAME)
                time.sleep(0.5)

                last_ltf_df = df_ltf

                ltf_score = technical_score(df_ltf, symbol)
                htf_score = technical_score(df_htf, symbol)

                blended_score = (0.65 * ltf_score) + (0.35 * htf_score)

                last_score = float(blended_score)
                last_score_time = now_ts

                print(f"📊 LTF={ltf_score:.2f} | HTF={htf_score:.2f} | FINAL={blended_score:.2f}")

            # ================= POSITION MANAGEMENT =================
            pm.check_auto_close(price)

            if last_score is not None:
                pm.check_progressive_tp(price, current_score=last_score)

            # ================= SIGNAL ENGINE =================
            if last_ltf_df is None or last_score is None:
                time.sleep(loop_interval)
                continue

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

            # ================= ENTRY HANDLER =================
            if pm.position is None and decision in ["LONG", "SHORT"]:

                winrate_last20 = compute_winrate_last20(pm.pnl_history)
                drawdown = compute_drawdown(pm.pnl_history)

                size = adaptive_position_size(
                    base_amount=trade_amount,
                    reinforced_score=last_score,
                    position_type=decision,
                    winrate_last20=winrate_last20,
                    drawdown=drawdown
                )

                print(f"📐 Adaptive Size: {size}")

                pm.open_position(
                    side=decision,
                    price=price,
                    quantity=size,
                    take_profit=take_profit,
                    stop_loss=stop_loss
                )

            time.sleep(loop_interval)

        except Exception as e:
            print(f"⚠️ Error in trading_loop: {e}")
            send_message_sync(f"⚠️ Error in trading_loop: {e}")
            time.sleep(loop_interval)