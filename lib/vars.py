import os
import yaml
from binance.client import Client

# ------------------------------------------------------------
# Load config
# ------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

with open(CONFIG_PATH, "r") as f:
    cfg = yaml.safe_load(f)

api_key = os.getenv("BINANCE_API_KEY", cfg["binance"]["api_key"])
api_secret = os.getenv("BINANCE_API_SECRET", cfg["binance"]["api_secret"])
futures_env = cfg["binance"].get("futures_env", "testnet").lower()

# ------------------------------------------------------------
# Create Binance client (REAL or TESTNET)
# ------------------------------------------------------------
if futures_env == "testnet":
    # Testnet client
    client = Client(api_key, api_secret, testnet=True)

    # Force Futures Testnet endpoints
    client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"
    client.FUTURES_DATA_URL = "https://testnet.binancefuture.com"

    print("🔗 Connected to Binance FUTURES TESTNET")

else:
    # Real Futures
    client = Client(api_key, api_secret)
    print("🔗 Connected to Binance FUTURES REAL")

# ------------------------------------------------------------
# Trading parameters
# ------------------------------------------------------------
symbol = cfg["trading"]["symbol"]
trade_amount = cfg["trading"]["trade_amount"]
timeframe = cfg["trading"]["timeframe"]
take_profit = cfg["trading"]["take_profit"]
stop_loss = cfg["trading"]["stop_loss"]

# Timing parameters
price_interval = cfg["trading"].get("price_interval_seconds", 5)
indicator_interval = cfg["trading"].get("indicator_interval_seconds", 300)
