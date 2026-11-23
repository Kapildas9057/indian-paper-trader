# IndianPaperTrader — Autonomous Cycle & ML Prediction Dashboard
- **Run Timestamp (IST):** `2026-11-23T17:20:11+05:30`
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
| RELIANCE-EQ | 2885 | 1351.00 | 43.31 | 1351.91 | 1352.39 | 1357.80 | 2.30 | HOLD (NONE) | yfinance:RELIANCE.NS |
| TCS-EQ | 11536 | 2460.00 | 52.75 | 2456.88 | 2457.23 | 2464.39 | 5.92 | HOLD (NONE) | yfinance:TCS.NS |
| HDFCBANK-EQ | 1333 | 817.80 | 31.80 | 818.65 | 820.68 | 828.93 | 1.57 | HOLD (NONE) | yfinance:HDFCBANK.NS |
| INFY-EQ | 1594 | 1103.40 | 41.90 | 1105.72 | 1106.16 | 1113.53 | 2.13 | HOLD (NONE) | yfinance:INFY.NS |
| ICICIBANK-EQ | 4963 | 1585.50 | 20.19 | 1590.01 | 1593.31 | 1602.24 | 2.34 | HOLD (NONE) | yfinance:ICICIBANK.NS |
| SBIN-EQ | 3045 | 1132.65 | 37.64 | 1133.08 | 1135.55 | 1144.51 | 2.22 | HOLD (NONE) | yfinance:SBIN.NS |

## 3. Paper Order Execution & 15-Day Intraday Replay Metrics
- **Paper Orders Placed:** None (zero qualifying setups or already open).

### 15-Day Intraday Replay Benchmark
| Symbol | Days | Bars | Trades | Win Rate % | Gross P&L (₹) | Brokerage (₹) | Net P&L (₹) | Max Drawdown % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RELIANCE-EQ | 15 | 1108 | 9 | 66.67% | 1051.76 | 360.00 | 691.76 | 0.12% |
| TCS-EQ | 15 | 1107 | 8 | 12.50% | -542.84 | 320.00 | -862.84 | 0.89% |
| HDFCBANK-EQ | 15 | 1109 | 8 | 62.50% | 512.42 | 320.00 | 192.42 | 0.19% |
| INFY-EQ | 15 | 1107 | 10 | 10.00% | -407.58 | 400.00 | -807.58 | 0.96% |

## 4. Self-Improvement Reflection & `strategy_config.json` Diff
- **Trailing Trades Reviewed:** `3`
- **Updated At:** `2026-11-23T17:20:12+05:30`
| Parameter | Previous | Updated |
|---|---:|---:|
| `rsi_buy_threshold` | `26` | `25` |

## 5. Today's ML Predictions for Next Session (`2026-11-24`)
- **Saved Snapshot:** `/home/runner/work/indian-paper-trader/indian-paper-trader/predictions/predictions_2026-11-23.json`
- **Average Out-of-Sample Test Directional Accuracy:** `50.34%`
- **Average Out-of-Sample Test MAE:** `1.3822%`

| Symbol | Today Close (₹) | Predicted Next Close (₹) | Pred Return % | Direction | Conf % | Action | Target (₹) | Stop-Loss (₹) | Winning Model | Test MAE % (95% CI) | Test Dir Acc % |
|---|---:|---:|---:|---|---:|---|---:|---:|---|---:|---:|
| RELIANCE-EQ | 1351.00 | 1350.04 | -0.071% | **NEUTRAL** | 67.2% | `WAIT_FOR_VWAP_BREAKOUT` | 1404.42 | 1315.38 | `RidgeRegression(alpha=40.0)` | 1.400% [1.020, 1.909] | 53.06% |
| TCS-EQ | 2460.00 | 2458.75 | -0.051% | **NEUTRAL** | 68.4% | `WAIT_FOR_VWAP_BREAKOUT` | 2586.00 | 2376.00 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.399% [1.046, 1.847] | 57.14% |
| HDFCBANK-EQ | 817.80 | 819.12 | +0.161% | **UP** | 66.4% | `BUY_ON_OPEN_OR_HOLD` | 857.26 | 788.20 | `GradientBoostedStumps(n=60, lr=0.07)` | 1.495% [1.221, 1.811] | 48.98% |
| INFY-EQ | 1103.40 | 1102.22 | -0.107% | **NEUTRAL** | 67.4% | `WAIT_FOR_VWAP_BREAKOUT` | 1164.51 | 1062.66 | `GradientBoostedStumps(n=25, lr=0.07)` | 1.573% [1.256, 1.937] | 53.06% |
| ICICIBANK-EQ | 1585.50 | 1588.61 | +0.196% | **UP** | 70.1% | `BUY_ON_OPEN_OR_HOLD` | 1651.66 | 1535.88 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.142% [0.845, 1.546] | 57.14% |
| SBIN-EQ | 1132.65 | 1134.62 | +0.174% | **UP** | 61.1% | `BUY_ON_OPEN_OR_HOLD` | 1185.83 | 1092.77 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.284% [1.053, 1.523] | 32.65% |