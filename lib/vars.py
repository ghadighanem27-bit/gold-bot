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

# Désactive le ping automatique
try:
    client.ping()
except Exception as e:
    print(f"⚠️ Binance Testnet ping failed: {e}")

# --- Trading parameters ---
symbol = cfg["symbol"]
trade_amount = cfg["trade_amount"]
timeframe = cfg["timeframe"]
trade_amount = cfg["trade_amount"]

# --- Bot runtime config ---
loop_interval = cfg.get("loop_interval", 300)
