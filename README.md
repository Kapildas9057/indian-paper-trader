# IndianPaperTrader: Autonomous NSE/BSE Paper-Trading MCP Engine

**IndianPaperTrader** is an open-source, self-improving Model Context Protocol (MCP) trading engine and real-time portfolio tracker for the National Stock Exchange (NSE) and Bombay Stock Exchange (BSE). It lets AI agents (Google Antigravity, Gemini, and Hermes) trade live Angel One / Yahoo Finance market data against a friction-accurate ₹1,00,000.00 SQLite virtual clearinghouse—learning from its own stop-losses and generating chronological ML next-session forecasts without risking a single rupee of real capital.

---

## Live Static Web App & Portfolio Dashboard
- **Minimal Mobile-First Portfolio UI (`public/index.html`)** modeled on the **Figma E-Wallet Mobile App Design (`dvKdKNfU9XXIt6y6I09b9I`)** and **Angel One Portfolio**:
  - **Profit or Losses:** Live unrealized & realized P&L (in ₹ and %) net of `0.05%` slippage and `₹20.00`/leg flat brokerage.
  - **Invested & Returns:** Exact capital deployed across active NSE positions vs live mark-to-market returns.
  - **Expected Growth:** Target upside (₹ and %) and chronological ML next-session price forecasts.
  - **Stocks Invested In:** Real-time holdings cards (`TCS-EQ`, `HDFCBANK-EQ`, `SBIN-EQ`) with live LTP, Avg Entry, Stop-Loss, Take-Profit, and ML next-day forecast.
  - **Performance Graph:** Dual interactive view switching between the **Angel One Intraday MTM Equity Curve** and **Figma Statistic Stock Pillars** (`Invested` vs `Current Value` vs `Expected Target`).
  - **Detailed Summary:** Complete clearinghouse accounting and 6-stock Nifty 50 live watchlist matrix.

---

## Architecture Layers
| Layer | Module / File | Responsibility |
|---|---|---|
| **L1: Market Telemetry** | `ReadOnlyMarketClient` in `indian_paper_mcp.py` | Read-only Angel One SmartAPI (`pyotp` TOTP) with automatic `yfinance` (`.NS`/`.BO`) failover. Zero real-broker order endpoints (`NFR-01`). |
| **L2: Quant & ML Engine** | `indian_paper_mcp.py` & `ml_predictor.py` | Wilder's `RSI_14`, `EMA_9`, `EMA_21`, session-anchored `VWAP`, `ATR_14`, plus chronological 60/20/20 Train/Val/Test ML forecasting (`NaiveDriftBaseline`, `RidgeForecaster`, `GradientBoostedStumpForecaster`). |
| **L3: SQLite Clearinghouse** | `paper_ledger.db` | Tracks ₹1,00,000.00 virtual cash, `open_positions`, `closed_trades`, `daily_predictions`, `0.05%` slippage, and `₹20.00` flat brokerage per leg. |
| **L4: Meta-Cognitive Memory** | `MEMORY.md` & `strategy_config.json` | Post-trade quantitative reflections and self-tuning indicator thresholds (`risk_per_trade_pct` clamped `2.0%–15.0%`). |
| **L5: Static & Live GUI** | `public/index.html`, `export_realtime_static.py`, `gui_dashboard.py` | Firebase Hosting (`firebase.json`) & Render Static Site (`render.yaml`) bundle + local real-time HTTP server (`http://127.0.0.1:8765`). |

---

## Quick Start

```powershell
# 1. Create virtual environment & install dependencies
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt

# 2. Run the 4-Phase Autonomous Trading Cycle + ML Next-Session Prediction
.\.venv\Scripts\python.exe autonomous_runner.py --mode direct

# 3. Export real-time static payload & launch GUI server (http://127.0.0.1:8765)
.\.venv\Scripts\python.exe export_realtime_static.py
.\.venv\Scripts\python.exe gui_dashboard.py --port 8765
```
