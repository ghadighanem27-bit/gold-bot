import time
from lib.market_data import get_data, get_price
from lib.indicators import technical_score
from lib.signals import signals
from lib.position_manager import PositionManager
from lib.vars import symbol, loop_interval, trade_amount, take_profit, stop_loss


def trading_loop():
    """Main trading loop that runs continuously in a background thread."""
    pm = PositionManager()
    print("🌀 Trading loop started...")

    while True:

        # ---------------------------------------------------------
        # 🔥 1) If a position is OPEN → check TP/SL every 1 second
        # ---------------------------------------------------------
        if pm.position:
            try:
                price = get_price(symbol)  # fast price lookup
                pm.check_auto_close(price)  # no need to pass symbol anymore
            except Exception as e:
                print(f"⚠️ Error during active trade price update: {e}")

            time.sleep(5)  # shorter sleep when position is open
            continue  # skip the rest of the loop

        # ---------------------------------------------------------
        # 🟢 2) If NO position → run normal logic each loop
        # ---------------------------------------------------------
        try:
            df = get_data(symbol)
            price = df['c'].iloc[-1]

            # Indicator calculations
            score = technical_score(df)

            # Signal logic
            signals(df, price, symbol, pm, trade_amount, take_profit, stop_loss)

        except Exception as e:
            print(f"⚠️ Error in trading loop: {e}")

        # Normal sleep between cycles
        time.sleep(loop_interval)