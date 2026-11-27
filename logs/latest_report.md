# IndianPaperTrader — Autonomous Cycle & ML Prediction Dashboard
- **Run Timestamp (IST):** `2026-11-27T17:16:49+05:30`
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
| RELIANCE-EQ | 2885 | 1382.60 | 56.61 | 1377.91 | 1378.96 | 1381.57 | 3.04 | HOLD (NONE) | yfinance:RELIANCE.NS |
| TCS-EQ | 11536 | 2572.50 | 30.97 | 2580.95 | 2585.55 | 2582.46 | 4.55 | HOLD (NONE) | yfinance:TCS.NS |
| HDFCBANK-EQ | 1333 | 857.25 | 29.99 | 859.39 | 860.86 | 862.07 | 1.38 | HOLD (NONE) | yfinance:HDFCBANK.NS |
| INFY-EQ | 1594 | 1151.30 | 31.80 | 1154.87 | 1156.90 | 1157.70 | 2.04 | HOLD (NONE) | yfinance:INFY.NS |
| ICICIBANK-EQ | 4963 | 1593.40 | 50.08 | 1592.59 | 1592.96 | 1597.00 | 2.46 | HOLD (NONE) | yfinance:ICICIBANK.NS |
| SBIN-EQ | 3045 | 1123.90 | 36.64 | 1125.58 | 1126.75 | 1131.37 | 1.85 | HOLD (NONE) | yfinance:SBIN.NS |

## 3. Paper Order Execution & 15-Day Intraday Replay Metrics
- **Paper Orders Placed:** None (zero qualifying setups or already open).

### 15-Day Intraday Replay Benchmark
| Symbol | Days | Bars | Trades | Win Rate % | Gross P&L (₹) | Brokerage (₹) | Net P&L (₹) | Max Drawdown % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RELIANCE-EQ | 15 | 1108 | 10 | 60.00% | 800.62 | 400.00 | 400.62 | 0.18% |
| TCS-EQ | 15 | 1105 | 10 | 10.00% | -616.48 | 400.00 | -1016.48 | 1.05% |
| HDFCBANK-EQ | 15 | 1109 | 9 | 44.44% | 257.78 | 360.00 | -102.22 | 0.33% |
| INFY-EQ | 15 | 1106 | 9 | 22.22% | -196.62 | 360.00 | -556.62 | 0.63% |

## 4. Self-Improvement Reflection & `strategy_config.json` Diff
- **Trailing Trades Reviewed:** `3`
- **Updated At:** `2026-11-27T17:16:52+05:30`
| Parameter | Previous | Updated |
|---|---:|---:|
| *(no parameter changes)* | - | - |

## 5. Today's ML Predictions for Next Session (`2026-11-30`)
- **Saved Snapshot:** `/home/runner/work/indian-paper-trader/indian-paper-trader/predictions/predictions_2026-11-27.json`
- **Average Out-of-Sample Test Directional Accuracy:** `47.96%`
- **Average Out-of-Sample Test MAE:** `1.4204%`

| Symbol | Today Close (₹) | Predicted Next Close (₹) | Pred Return % | Direction | Conf % | Action | Target (₹) | Stop-Loss (₹) | Winning Model | Test MAE % (95% CI) | Test Dir Acc % |
|---|---:|---:|---:|---|---:|---|---:|---:|---|---:|---:|
| RELIANCE-EQ | 1382.60 | 1381.31 | -0.093% | **NEUTRAL** | 64.6% | `WAIT_FOR_VWAP_BREAKOUT` | 1438.13 | 1345.58 | `GradientBoostedStumps(n=40, lr=0.07)` | 1.314% [0.960, 1.806] | 44.90% |
| TCS-EQ | 2572.50 | 2570.13 | -0.092% | **NEUTRAL** | 68.0% | `WAIT_FOR_VWAP_BREAKOUT` | 2706.20 | 2483.36 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.548% [1.172, 1.970] | 55.10% |
| HDFCBANK-EQ | 857.25 | 859.79 | +0.296% | **UP** | 65.3% | `BUY_ON_OPEN_OR_HOLD` | 898.05 | 826.65 | `GradientBoostedStumps(n=60, lr=0.07)` | 1.541% [1.213, 1.830] | 42.86% |
| INFY-EQ | 1151.30 | 1151.46 | +0.014% | **NEUTRAL** | 66.7% | `WAIT_FOR_VWAP_BREAKOUT` | 1216.24 | 1108.00 | `GradientBoostedStumps(n=40, lr=0.07)` | 1.673% [1.323, 2.029] | 53.06% |
| ICICIBANK-EQ | 1593.40 | 1595.55 | +0.135% | **NEUTRAL** | 66.5% | `WAIT_FOR_VWAP_BREAKOUT` | 1657.91 | 1550.39 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.225% [0.893, 1.573] | 48.98% |
| SBIN-EQ | 1123.90 | 1125.60 | +0.151% | **UP** | 64.5% | `BUY_ON_OPEN_OR_HOLD` | 1175.16 | 1085.46 | `GradientBoostedStumps(n=25, lr=0.07)` | 1.221% [1.004, 1.444] | 42.86% |