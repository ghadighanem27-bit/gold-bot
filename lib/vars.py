import os
import yaml
from binance.client import Client

# ------------------------------------------------------------
# Load config.yaml from project root
# ------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.yaml")

with open(CONFIG_PATH, "r") as f:
    cfg = yaml.safe_load(f)

# ------------------------------------------------------------
# BINANCE CLIENT (REAL or TESTNET FUTURES)
# ------------------------------------------------------------
binance_cfg = cfg["binance"]

api_key = os.getenv("BINANCE_API_KEY", binance_cfg["api_key"])
api_secret = os.getenv("BINANCE_API_SECRET", binance_cfg["api_secret"])
futures_env = binance_cfg.get("futures_env", "testnet").lower()

if futures_env == "testnet":
    client = Client(api_key, api_secret, testnet=True)
    # Force Futures Testnet endpoints
    client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"
    client.FUTURES_DATA_URL = "https://testnet.binancefuture.com"
    print("🔗 Connected to Binance FUTURES TESTNET")
else:
    client = Client(api_key, api_secret)
    print("🔗 Connected to Binance FUTURES REAL")

# ------------------------------------------------------------
# TRADING PARAMETERS
# ------------------------------------------------------------
trading_cfg = cfg["trading"]
symbol = trading_cfg["symbol"]
trade_amount = trading_cfg["trade_amount"]
timeframe = trading_cfg["timeframe"]
take_profit = trading_cfg["take_profit"]
stop_loss = trading_cfg["stop_loss"]
break_even_enabled = trading_cfg.get("break_even_enabled", True)
break_even_trigger_pct = trading_cfg.get("break_even_trigger_pct", 0.4)

# ------------------------------------------------------------
# TIMING PARAMETERS
# ------------------------------------------------------------
timing_cfg = cfg["timing"]
price_interval = timing_cfg["price_interval_seconds"]
indicator_interval = timing_cfg["indicator_interval_seconds"]
loop_interval = timing_cfg["loop_interval"]