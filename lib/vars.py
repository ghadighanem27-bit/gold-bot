import os
import yaml
from binance.client import Client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

with open(CONFIG_PATH, "r") as f:
    cfg = yaml.safe_load(f)

# --- Binance Testnet client setup ---
client = Client(cfg["api_key"], cfg["api_secret"], testnet=True)
client.API_URL = cfg["base_url"]

try:
    client.ping()
except Exception as e:
    print(f"⚠️ Binance Testnet ping failed: {e}")

# --- Trading parameters ---
symbol = cfg["symbol"]
trade_amount = cfg["trade_amount"]
timeframe = cfg["timeframe"]
take_profit = cfg["take_profit"]
stop_loss = cfg["stop_loss"]

# --- Timing parameters (NEW) ---
price_interval = cfg.get("price_interval_seconds", 5)         # default 5 sec
indicator_interval = cfg.get("indicator_interval_seconds", 300)  # default 5 min
