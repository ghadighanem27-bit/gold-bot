import time
from lib.market_data import get_data
from lib.indicators import technical_score
from lib.signals import signals
from lib.position_manager import PositionManager
from lib.vars import symbol, loop_interval, trade_amount, take_profit, stop_loss

def trading_loop():
    """Main trading loop that runs continuously in a background thread."""
    pm = PositionManager()
    print("🌀 Trading loop started...")

    while True:
        # 1️⃣ Fetch latest data
        df = get_data(symbol)
        price = df['c'].iloc[-1]
        score = technical_score(df)

        # 2️⃣ Check open position (for TP/SL auto close)
        pm.check_auto_close(price)

        # 3️⃣ Evaluate signals
        signals(score, price, symbol, pm, trade_amount, take_profit, stop_loss)

        # 4️⃣ Wait until next iteration
        time.sleep(loop_interval)