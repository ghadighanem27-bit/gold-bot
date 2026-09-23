# Gold Bot — Automated Binance Futures Trading Engine

**A multi-indicator, score-driven trading bot for Binance USDT-M Futures, with adaptive exits, Telegram alerts, and Postgres trade logging.**

[Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge\&logo=python\&logoColor=white)
[Binance](https://img.shields.io/badge/Binance-Futures-F0B90B?style=for-the-badge\&logo=binance\&logoColor=black)
[Telegram](https://img.shields.io/badge/Alerts-Telegram-26A5E4?style=for-the-badge\&logo=telegram\&logoColor=white)
[PostgreSQL](https://img.shields.io/badge/Storage-PostgreSQL-4169E1?style=for-the-badge\&logo=postgresql\&logoColor=white)
[License](https://img.shields.io/badge/status-personal%20project-lightgrey?style=for-the-badge)

---

> **Project Status and Risk Notice**
> This bot was developed and tested **exclusively on Binance Futures Testnet** with the help of AI.
> **It was never used with real money and was never deployed for real-money trading.**
>
> The repository contains code for Binance Futures order execution because exchange integration is part of the system design. That code should not be interpreted as evidence of live deployment.
>
> This project is provided for educational and research purposes. It is not financial advice, and there is no guarantee of profitability, uptime, or correctness. Leveraged futures trading involves substantial risk of loss.

---

## Table of Contents
- [Overview](#overview)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [The Scoring Engine](#the-scoring-engine)
- [Signal Thresholds](#signal-thresholds)
- [Position & Risk Management](#position--risk-management)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Bot](#running-the-bot)
- [Database Schema](#database-schema)
- [Telegram Notifications](#telegram-notifications)
- [Roadmap / Known Limitations](#roadmap--known-limitations)
- [Disclaimer](#disclaimer)

---

## Overview

**Gold Bot** is a self-contained algorithmic trading bot that trades a single symbol (default `ETHUSDT`, despite the project name) on **Binance USDT-M Futures**. It doesn't rely on one indicator — instead it blends **8 independent technical sub-scores** across **two timeframes** into a single 0–100 "confidence score," and uses that score to open, manage, and close positions automatically.

### Project Status

Gold Bot is a personal project and experimental trading system. It was **only run against Binance Futures Testnet** during development and testing and **was never used with real funds**.

Although the configuration includes an environment setting for Binance Futures, the project documented here was never used for real-money trading.

**Key capabilities:**

| Capability | Description |
| --- | --- |
| **Multi-indicator scoring** | 8 weighted technical signals combined into one score (0–100) |
| **Multi-timeframe blending** | Combines a 5m ("LTF") and 15m ("HTF") score for confirmation |
| **Tiered entries** | `STRONG_BUY` / `SOFT_BUY` / `SOFT_SELL` / `STRONG_SELL` zones with different TP/SL profiles |
| **Progressive take-profit** | Scales out of winning positions in 4 steps (40% / 70% / 100% / 150% PnL) |
| **Break-even and trailing stops** | Protects profit once a trade moves in its favor |
| **Score-aware exits** | Closes early if momentum reverses before hitting a hard stop |
| **Loss cooldown** | Pauses new entries for 10 minutes after a losing trade |
| **Real-time pricing** | Uses a Binance mark-price WebSocket instead of polling the REST API |
| **Telegram alerts** | Sends entries, exits, partial TPs, and errors to Telegram |
| **Trade and score logging** | Persists every score and trade outcome to PostgreSQL for later analysis |

---

## How It Works

At a high level, the bot loops continuously and, every cycle:

1. Reads the **latest live price** from the WebSocket mark-price stream.
2. Manages any **open position** — checks stop-loss, take-profit, break-even, progressive TP, and trailing stop.
3. Every 5 minutes, recomputes the **technical score** from fresh candle data (on both the 5m and 15m timeframes) and blends them.
4. Feeds the current score into the **signal engine**, which decides whether to open, hold, or exit a position.
5. Sends a **Telegram message** for every meaningful event (entry, exit, partial TP, error).
6. Logs the score (and, once a trade closes, its outcome) to **PostgreSQL**.

---

## Architecture
```mermaid
flowchart TD
    A["bot.py<br/>(entrypoint)"] --> B["websocket_price.py<br/>Binance mark-price stream"]
    A --> C["trading_loop.py<br/>(background thread)"]

    C --> D["market_data.py<br/>REST candles + price"]
    C --> E["indicators.py<br/>technical_score()"]
    C --> F["signals.py<br/>entry / exit decisions"]
    C --> G["position_manager.py<br/>PositionManager"]
    C --> H["database_manager.py<br/>Postgres logging"]

    E -->|"5m score"| F
    E -->|"15m score"| F
    F -->|"open / close orders"| G
    G -->|"Binance REST orders"| I[("Binance Futures API")]
    G -->|"state persistence"| J[("position_state.json")]
    B -->|"live mark price"| D

    F --> K["telegram_bot.py"]
    G --> K
    C --> K
    K --> L[("Telegram Chat")]

    H --> M[("PostgreSQL<br/>mtf_scores table")]

```

**Threading model:** `bot.py` starts the WebSocket client on a background thread, then runs the main `trading_loop` on a second thread. Telegram messages are dispatched asynchronously on their own persistent event loop so they never block trading logic.

---

## Project Structure
```
gold-bot-main/
├── bot.py                     # Entry point — starts WebSocket + trading loop
├── trading_loop.py            # Main loop: price polling, score updates, signal dispatch
├── config.yaml                # All bot configuration (symbol, risk, timing, secrets refs)
├── requirements.txt           # Python dependencies
├── trade_log.txt              # Plain-text trade log output
│
└── lib/
    ├── vars.py                # Loads config.yaml, initializes the Binance client
    ├── market_data.py         # REST candle fetching + price helpers
    ├── websocket_price.py     # Live mark-price WebSocket listener
    ├── indicators.py          # 8 sub-indicators + master technical_score()
    ├── signals.py             # Entry/exit decision logic based on score thresholds
    ├── position_manager.py    # Order execution, TP/SL, break-even, trailing stop
    ├── risk.py                # Win-rate, drawdown, adaptive position sizing
    ├── telegram_bot.py        # Telegram alerting (async, fire-and-forget)
    └── database_manager.py    # PostgreSQL score/trade persistence

```

---

## The Scoring Engine

Every cycle, `indicators.technical_score(df)` computes a single **0–100 score** — higher values indicate more bullish conditions, while lower values indicate more bearish conditions — from **8 sub-indicators**, each independently normalized to 0–100 and then combined with fixed weights:

| # | Sub-indicator | Weight | What it measures |
| --- | --- | ---: | --- |
| 1 | **MACD Momentum** | 15% | Slope of the MACD signal line (regression over last 5 candles) |
| 2 | **OBV Divergence** | 12% | Divergence between price return and On-Balance-Volume return |
| 3 | **Market Structure** | 10% | Fresh breakout / breakdown vs. recent swing high/low |
| 4 | **RVOL + OBV** | 12% | Relative volume vs. average, blended with OBV slope |
| 5 | **Bollinger Squeeze** | 14% | Band-width compression/expansion + price position within bands |
| 6 | **RSI Adaptive System** | 13% | RSI distance from a trend-aware target zone, plus slope & compression |
| 7 | **MA System** | 14% | Slope of fast/medium MAs + bullish/bearish stacking (10/20/50 SMA) |
| 8 | **Volatility Regime** | 10% | ATR expansion combined with ADX slope (trending vs. choppy) |

```
technical_score = Σ (sub_score_i × weight_i)   for i in 1..8

```

The bot then computes this score on **two timeframes** and blends them:

```
blended_score = 0.65 × score(5m)  +  0.35 × score(15m)

```

This blend is recalculated every **5 minutes** (`score_update_interval = 300s`) and cached — the trading loop checks price and manages positions every `loop_interval` seconds (default: 5s) without necessarily recomputing the full score.

---

## Signal Thresholds
`lib/signals.py` maps the blended score onto four action zones:

| Score range | Zone | Action (no open position) |
| --- | --- | --- |
| **≥ 75** | Strong Buy | Open LONG — TP 2.0% / SL 1.0% |
| **55–74** | Soft Buy | Open LONG — TP 1.2% / SL 0.8% |
| **26–54** | Neutral | Hold, no action |
| **16–25** | Soft Sell | Open SHORT — TP 1.2% / SL 0.8% |
| **≤ 15** | Strong Sell | Open SHORT — TP 2.0% / SL 1.0% |

**Exit confirmation:** while a position is open, an opposing signal must appear on **two consecutive score checks** before the bot exits — this avoids closing a trade on a single noisy reading.

```mermaid
graph LR
    subgraph Score axis
    A["0"] --- B["15<br/>STRONG_SELL"] --- C["25<br/>SOFT_SELL"] --- D["55<br/>SOFT_BUY"] --- E["75<br/>STRONG_BUY"] --- F["100"]
    end
    style B fill:#8B0000,color:#fff
    style C fill:#B22222,color:#fff
    style D fill:#2E8B57,color:#fff
    style E fill:#006400,color:#fff

```

---

## Position & Risk Management
`PositionManager` (in `lib/position_manager.py`) owns the full lifecycle of a trade and persists its state to `position_state.json` so the bot can resume safely after a restart.

**Per-tick protections, checked in this order:**

1. **Break-even activation** — once PnL reaches `break_even_trigger_pct` (default `0.4%`), stop-loss is moved to `-0.15%` (i.e., a guaranteed small profit that covers fees).
2. **Take-profit / stop-loss** — hard exit if PnL crosses the configured TP or SL level.
3. **Progressive take-profit** — scales out in 4 steps as PnL climbs:
   | PnL trigger Portion closed  |             |
   | --------------------------- | ----------- |
   | +0.40%                      | 25%         |
   | +0.70%                      | 25%         |
   | +1.00%                      | 25%         |
   | +1.50%                      | 25% (final) |
   Breakeven is auto-armed after the **first** partial TP; a **trailing stop** (0.20% behind the peak PnL) is armed after the **final** partial TP.
4. **Score-aware early exit** — if PnL is already ≥ 0.6% but the score starts reversing against the position (`should_secure_profit` in `lib/risk.py`), the bot closes the trade early rather than waiting for a hard stop.
5. **Loss cooldown** — after any losing trade, new entries are paused for **10 minutes**.

**Adaptive position sizing** (`lib/risk.py`) can scale the base trade size using:

- The strength of the current score (further from 50 → larger size)
- Recent win rate over the last 20 trades
- Recent drawdown

>  Note: `adaptive_position_size` and `compute_winrate_last20` / `compute_drawdown` are defined but not yet wired into `trading_loop.py` — the bot currently trades a **fixed** `trade_amount` from `config.yaml`. See [Roadmap](#roadmap--known-limitations).

---

## Installation
### Prerequisites

- **Python 3.11+**
- A **Binance Futures Testnet account** for development and testing — [testnet.binancefuture.com](https://testnet.binancefuture.com/)
- A **Telegram bot token** ([@BotFather](https://t.me/BotFather)) and your chat ID
- A **PostgreSQL** database (for score/trade logging)
- The **TA-Lib** C library installed on your system (required by the `TA-Lib` Python package)

### Steps

```bash
# 1. Clone the repository

git clone <your-repo-url>
cd gold-bot-main

# 2. Create a virtual environment

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install TA-Lib's C library first (varies by OS), then:

pip install -r requirements.txt

# 4. Create your config

cp config.yaml config.local.yaml   # or edit config.yaml directly

# 5. Set your secrets as environment variables (recommended over editing config.yaml)

export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"

```

>  **TA-Lib install tip:** the `TA-Lib` PyPI package is a wrapper around a compiled C library. On macOS: `brew install ta-lib`. On Ubuntu/Debian: build from source or use a prebuilt wheel. On Windows: use an unofficial prebuilt `.whl`. Install the C library **before** `pip install -r requirements.txt`, or the `TA-Lib` line will fail to build.

### Database setup

The bot expects a table named `mtf_scores`. Create it (adjust types as needed) before running:

```sql
CREATE TABLE mtf_scores (
    id                SERIAL PRIMARY KEY,
    symbol            TEXT,
    ltf_score         DOUBLE PRECISION,
    htf_score         DOUBLE PRECISION,
    reinforced_score  DOUBLE PRECISION,
    decision          TEXT,
    regime            TEXT,
    entry_volatility  DOUBLE PRECISION,
    entry_time        TIMESTAMP,
    exit_time         TIMESTAMP,
    exit_volatility   DOUBLE PRECISION,
    duration_seconds  DOUBLE PRECISION,
    trade_result      DOUBLE PRECISION,
    trade_id          TEXT
);

```

---

## Configuration

All runtime behavior is controlled by **`config.yaml`**:

```yaml
binance:
  api_key: "${BINANCE_API_KEY}"      # Read from env var if set, else this literal value
  api_secret: "${BINANCE_API_SECRET}"
  futures_env: "testnet"             # "testnet" or "real"

telegram:
  bot_token: ""                      # From @BotFather
  chat_id: ""                        # Your numeric Telegram chat ID

trading:
  symbol: "ETHUSDT"
  trade_amount: 0.1                  # Fixed order size, in base asset units
  risk_percentage: 0.01              # Reserved for future dynamic sizing
  timeframe: "5m"
  take_profit: 1.5                   # % — informational default
  stop_loss: 0.6                     # % — informational default
  break_even_enabled: true
  break_even_trigger_pct: 0.4        # % PnL that arms break-even
  position_file: "position_eth.json" # Where live position state is persisted

timing:
  price_interval_seconds: 5          # (reserved)
  indicator_interval_seconds: 300    # How often the score recalculates
  loop_interval: 5                   # Main loop tick rate, in seconds

database:
  url: ""                            # PostgreSQL connection string

```

| Setting | Recommendation |
| --- | --- |
| `futures_env` | Use `"testnet"` for development and testing. The project described in this README was never used with real funds.                                                      |
| `trade_amount` | This is a **fixed quantity in the base asset** (e.g. ETH), not a USD/margin amount — size accordingly.                |
| `api_key` / `api_secret` | Prefer environment variables over hardcoding secrets in `config.yaml`, especially if this repo is version-controlled. |
| `database.url` | A standard Postgres DSN, e.g. `postgresql://user:pass@host:5432/dbname`.                                              |

---

## Running the Bot
```bash
python bot.py

```

On startup you should see:

```text
Connected to Binance Futures Testnet
Starting trading bot for ETHUSDT
WebSocket thread started for ETHUSDT
WebSocket running for ETHUSDT
Trading loop started for ETHUSDT
```

...and a matching "Trading loop started" message on Telegram. From here the bot runs unattended, printing per-indicator scores to the console every 5 minutes and pushing all trade events to Telegram.

>  **Stopping the bot does not close open positions.** `PositionManager` persists state to disk so it can resume management on restart — but if you kill the process and don't restart it, any open position will sit unmanaged on the exchange until you close it manually.

---

## Database Schema

Every score cycle inserts one row into `mtf_scores` (even if no trade is taken); when a trade eventually opens, its `trade_id` is attached to that row, and when it closes, the row is updated with the outcome:

```mermaid
sequenceDiagram
    participant L as trading_loop
    participant DB as database_manager
    participant PM as PositionManager

    L->>DB: record_score(ltf, htf, blended) -> returns score_id
    Note over L: signal engine evaluates score
    L->>PM: signals() opens a position
    PM->>DB: attach_trade_id_to_score_id(score_id, trade_id)
    Note over PM: position managed (TP/SL/BE/trailing)
    PM->>DB: update_score_with_result(pnl, exit_time, duration)

```

This structure makes it possible to analyze **which indicator conditions actually preceded winning vs. losing trades**.

---

## Telegram Notifications

The bot sends a message for every significant event, including:

- Trading loop started
- Strong or soft entries
- Confirmed exits
- Partial take-profit hits
- Break-even activation / break-even exits
- Early "momentum weakening" exits
- Trailing-stop triggers
- Final position close with PnL
- Runtime errors in the trading loop

The `/start` and `/stats` command handlers exist in `telegram_bot.py` but the polling listener that would serve them is currently **commented out** — Telegram is used as an outbound alert channel only, not an interactive control surface.

---

## Roadmap / Known Limitations
- [ ] Wire `adaptive_position_size`, `compute_winrate_last20`, and `compute_drawdown` (in `lib/risk.py`) into `trading_loop.py` — they're implemented but currently unused, so position size is always the fixed `trade_amount`.
- [ ] Re-enable the Telegram `/stats` command with real performance data pulled from `mtf_scores`.
- [ ] `regime` and `decision` columns in `mtf_scores` are always inserted as `NULL` — not currently populated.
- [ ] `risk_percentage` in `config.yaml` is not yet used anywhere in the codebase.
- [ ] No automated tests currently cover the indicator math or signal thresholds.
- [ ] Trailing-stop distance (0.20%) and cooldown duration (10 min) are hardcoded in `position_manager.py` rather than configurable.

---

## Disclaimer

This software is an experimental cryptocurrency futures trading project. It was **tested only on Binance Futures Testnet and was never used with real money**. The repository contains exchange-order execution code because exchange integration is part of the intended system design, but no real-money trading is claimed or documented here.

The authors provide no guarantee of profitability, uptime, or correctness. Futures trading and leverage can result in significant losses. Review the code and configuration carefully before connecting any exchange credentials, and use Testnet for development and testing.
