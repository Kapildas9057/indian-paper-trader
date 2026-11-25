# IndianPaperTrader — Autonomous Cycle & ML Prediction Dashboard
- **Run Timestamp (IST):** `2026-11-25T17:38:59+05:30`
- **NSE Live Market Hours:** `CLOSED (Off-Hours Fallback & 15-Day Replay Active)`

## 1. Portfolio Ledger
- **Virtual Cash:** `₹99,604.19`
- **Realized P&L:** `₹-395.81`
- **Unrealized P&L:** `₹0.00`
- **Total Brokerage Paid:** `₹120.00`
- **Total Equity:** `₹99,604.19`
- **Total Closed Trades:** `3`
- **Open Positions:** `0`

## 2. Watchlist Technical Matrix
| Symbol | Token | LTP (₹) | RSI_14 | EMA_9 | EMA_21 | VWAP (₹) | ATR_14 | Signal / Setup | Source |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| RELIANCE-EQ | 2885 | 1373.90 | 59.09 | 1372.00 | 1371.10 | 1376.83 | 2.60 | HOLD (NONE) | yfinance:RELIANCE.NS |
| TCS-EQ | 11536 | 2517.30 | 73.96 | 2505.72 | 2502.53 | 2508.26 | 4.25 | HOLD (NONE) | yfinance:TCS.NS |
| HDFCBANK-EQ | 1333 | 846.20 | 63.76 | 843.59 | 843.15 | 844.71 | 1.57 | HOLD (NONE) | yfinance:HDFCBANK.NS |
| INFY-EQ | 1594 | 1130.00 | 61.07 | 1128.05 | 1127.35 | 1134.79 | 2.00 | HOLD (NONE) | yfinance:INFY.NS |
| ICICIBANK-EQ | 4963 | 1640.00 | 64.55 | 1637.36 | 1636.02 | 1638.64 | 2.85 | HOLD (NONE) | yfinance:ICICIBANK.NS |
| SBIN-EQ | 3045 | 1138.15 | 48.40 | 1138.36 | 1138.34 | 1140.73 | 2.20 | HOLD (NONE) | yfinance:SBIN.NS |

## 3. Paper Order Execution & 15-Day Intraday Replay Metrics
- **Paper Orders Placed:** None (zero qualifying setups or already open).

### 15-Day Intraday Replay Benchmark
| Symbol | Days | Bars | Trades | Win Rate % | Gross P&L (₹) | Brokerage (₹) | Net P&L (₹) | Max Drawdown % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RELIANCE-EQ | 15 | 1108 | 8 | 62.50% | 641.12 | 320.00 | 321.12 | 0.12% |
| TCS-EQ | 15 | 1106 | 9 | 11.11% | -531.32 | 360.00 | -891.32 | 1.00% |
| HDFCBANK-EQ | 15 | 1109 | 8 | 62.50% | 512.42 | 320.00 | 192.42 | 0.19% |
| INFY-EQ | 15 | 1106 | 10 | 20.00% | -399.30 | 400.00 | -799.30 | 0.95% |

## 4. Self-Improvement Reflection & `strategy_config.json` Diff
- **Trailing Trades Reviewed:** `3`
- **Updated At:** `2026-11-25T17:39:01+05:30`
| Parameter | Previous | Updated |
|---|---:|---:|
| *(no parameter changes)* | - | - |

## 5. Today's ML Predictions for Next Session (`2026-11-26`)
- **Saved Snapshot:** `/home/runner/work/indian-paper-trader/indian-paper-trader/predictions/predictions_2026-11-25.json`
- **Average Out-of-Sample Test Directional Accuracy:** `48.30%`
- **Average Out-of-Sample Test MAE:** `1.4050%`

| Symbol | Today Close (₹) | Predicted Next Close (₹) | Pred Return % | Direction | Conf % | Action | Target (₹) | Stop-Loss (₹) | Winning Model | Test MAE % (95% CI) | Test Dir Acc % |
|---|---:|---:|---:|---|---:|---|---:|---:|---|---:|---:|
| RELIANCE-EQ | 1373.90 | 1380.37 | +0.471% | **UP** | 65.1% | `BUY_ON_OPEN_OR_HOLD` | 1435.20 | 1327.93 | `GradientBoostedStumps(n=60, lr=0.07)` | 1.347% [0.956, 1.861] | 36.73% |
| TCS-EQ | 2517.30 | 2515.11 | -0.087% | **NEUTRAL** | 68.7% | `WAIT_FOR_VWAP_BREAKOUT` | 2643.82 | 2432.95 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.438% [1.129, 1.935] | 57.14% |
| HDFCBANK-EQ | 846.20 | 846.45 | +0.030% | **NEUTRAL** | 64.7% | `WAIT_FOR_VWAP_BREAKOUT` | 883.39 | 821.41 | `GradientBoostedStumps(n=60, lr=0.07)` | 1.544% [1.238, 1.850] | 46.94% |
| INFY-EQ | 1130.00 | 1131.31 | +0.116% | **NEUTRAL** | 67.4% | `WAIT_FOR_VWAP_BREAKOUT` | 1192.98 | 1088.01 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.612% [1.256, 1.975] | 53.06% |
| ICICIBANK-EQ | 1640.00 | 1642.16 | +0.132% | **NEUTRAL** | 72.9% | `WAIT_FOR_VWAP_BREAKOUT` | 1703.58 | 1597.62 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.204% [0.916, 1.558] | 67.35% |
| SBIN-EQ | 1138.15 | 1139.49 | +0.118% | **NEUTRAL** | 59.1% | `WAIT_FOR_VWAP_BREAKOUT` | 1185.40 | 1106.65 | `GradientBoostedStumps(n=25, lr=0.07)` | 1.286% [1.048, 1.485] | 28.57% |