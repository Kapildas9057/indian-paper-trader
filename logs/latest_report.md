# IndianPaperTrader — Autonomous Cycle & ML Prediction Dashboard
- **Run Timestamp (IST):** `2026-11-26T17:25:24+05:30`
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
| RELIANCE-EQ | 2885 | 1396.20 | 64.77 | 1395.17 | 1390.22 | 1383.43 | 3.62 | HOLD (NONE) | yfinance:RELIANCE.NS |
| TCS-EQ | 11536 | 2640.30 | 89.01 | 2617.53 | 2601.18 | 2583.55 | 7.41 | HOLD (NONE) | yfinance:TCS.NS |
| HDFCBANK-EQ | 1333 | 862.00 | 47.18 | 861.71 | 862.20 | 862.51 | 1.56 | HOLD (NONE) | yfinance:HDFCBANK.NS |
| INFY-EQ | 1594 | 1183.00 | 80.28 | 1177.86 | 1172.78 | 1166.31 | 2.80 | HOLD (NONE) | yfinance:INFY.NS |
| ICICIBANK-EQ | 4963 | 1611.00 | 41.98 | 1613.27 | 1614.13 | 1620.07 | 2.97 | HOLD (NONE) | yfinance:ICICIBANK.NS |
| SBIN-EQ | 3045 | 1136.65 | 36.28 | 1139.67 | 1140.77 | 1142.06 | 2.21 | HOLD (NONE) | yfinance:SBIN.NS |

## 3. Paper Order Execution & 15-Day Intraday Replay Metrics
- **Paper Orders Placed:** None (zero qualifying setups or already open).

### 15-Day Intraday Replay Benchmark
| Symbol | Days | Bars | Trades | Win Rate % | Gross P&L (₹) | Brokerage (₹) | Net P&L (₹) | Max Drawdown % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RELIANCE-EQ | 15 | 1108 | 9 | 66.67% | 856.48 | 360.00 | 496.48 | 0.14% |
| TCS-EQ | 15 | 1106 | 9 | 11.11% | -531.32 | 360.00 | -891.32 | 1.00% |
| HDFCBANK-EQ | 15 | 1109 | 8 | 50.00% | 337.10 | 320.00 | 17.10 | 0.21% |
| INFY-EQ | 15 | 1106 | 9 | 22.22% | -264.48 | 360.00 | -624.48 | 0.80% |

## 4. Self-Improvement Reflection & `strategy_config.json` Diff
- **Trailing Trades Reviewed:** `3`
- **Updated At:** `2026-11-26T17:25:26+05:30`
| Parameter | Previous | Updated |
|---|---:|---:|
| *(no parameter changes)* | - | - |

## 5. Today's ML Predictions for Next Session (`2026-11-27`)
- **Saved Snapshot:** `/home/runner/work/indian-paper-trader/indian-paper-trader/predictions/predictions_2026-11-26.json`
- **Average Out-of-Sample Test Directional Accuracy:** `48.30%`
- **Average Out-of-Sample Test MAE:** `1.4481%`

| Symbol | Today Close (₹) | Predicted Next Close (₹) | Pred Return % | Direction | Conf % | Action | Target (₹) | Stop-Loss (₹) | Winning Model | Test MAE % (95% CI) | Test Dir Acc % |
|---|---:|---:|---:|---|---:|---|---:|---:|---|---:|---:|
| RELIANCE-EQ | 1396.20 | 1401.59 | +0.386% | **UP** | 67.2% | `BUY_ON_OPEN_OR_HOLD` | 1458.82 | 1349.24 | `GradientBoostedStumps(n=40, lr=0.07)` | 1.333% [1.010, 1.824] | 44.90% |
| TCS-EQ | 2640.30 | 2642.17 | +0.071% | **NEUTRAL** | 67.8% | `WAIT_FOR_VWAP_BREAKOUT` | 2773.59 | 2551.44 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.543% [1.131, 1.968] | 55.10% |
| HDFCBANK-EQ | 862.00 | 863.70 | +0.197% | **UP** | 64.5% | `BUY_ON_OPEN_OR_HOLD` | 904.26 | 830.30 | `GradientBoostedStumps(n=60, lr=0.07)` | 1.549% [1.275, 1.843] | 42.86% |
| INFY-EQ | 1183.00 | 1184.46 | +0.123% | **NEUTRAL** | 66.0% | `WAIT_FOR_VWAP_BREAKOUT` | 1248.56 | 1139.30 | `RidgeRegression(alpha=40.0)` | 1.780% [1.424, 2.178] | 48.98% |
| ICICIBANK-EQ | 1611.00 | 1615.09 | +0.254% | **UP** | 71.2% | `BUY_ON_OPEN_OR_HOLD` | 1683.40 | 1556.70 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.240% [0.951, 1.623] | 59.18% |
| SBIN-EQ | 1136.65 | 1138.33 | +0.148% | **NEUTRAL** | 63.0% | `WAIT_FOR_VWAP_BREAKOUT` | 1182.95 | 1105.79 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.242% [1.011, 1.466] | 38.78% |