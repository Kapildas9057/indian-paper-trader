# IndianPaperTrader — Autonomous Cycle & ML Prediction Dashboard
- **Run Timestamp (IST):** `2026-11-20T17:59:05+05:30`
- **NSE Live Market Hours:** `CLOSED (Off-Hours Fallback & 15-Day Replay Active)`

## 1. Portfolio Ledger
- **Virtual Cash:** `₹71,781.18`
- **Realized P&L:** `₹0.00`
- **Unrealized P&L:** `₹-27.22`
- **Total Brokerage Paid:** `₹60.00`
- **Total Equity:** `₹99,912.78`
- **Total Closed Trades:** `0`
- **Open Positions:** `3`

| Symbol | Side | Qty | Entry (₹) | Current LTP (₹) | Stop-Loss (₹) | Take-Profit (₹) | Unrealized P&L (₹) |
|---|---|---:|---:|---:|---:|---:|---:|
| TCS-EQ | BUY | 4 | 2380.69 | 2376.20 | 2350.95 | 2438.99 | -17.96 |
| HDFCBANK-EQ | BUY | 11 | 846.42 | 846.00 | 835.85 | 867.15 | -4.62 |
| SBIN-EQ | BUY | 8 | 1165.68 | 1165.10 | 1151.12 | 1194.23 | -4.64 |

## 2. Watchlist Technical Matrix
| Symbol | Token | LTP (₹) | RSI_14 | EMA_9 | EMA_21 | VWAP (₹) | ATR_14 | Signal / Setup | Source |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| RELIANCE-EQ | 2885 | 1377.50 | 67.85 | 1373.96 | 1370.13 | 1366.94 | 2.97 | HOLD (NONE) | yfinance:RELIANCE.NS |
| TCS-EQ | 11536 | 2376.20 | 37.13 | 2378.45 | 2380.82 | 2391.01 | 3.44 | HOLD (NONE) | yfinance:TCS.NS |
| HDFCBANK-EQ | 1333 | 846.00 | 49.67 | 848.15 | 847.00 | 837.85 | 1.85 | BUY (MOMENTUM_BUY) | yfinance:HDFCBANK.NS |
| INFY-EQ | 1594 | 1098.00 | 53.36 | 1094.24 | 1095.88 | 1103.01 | 2.20 | HOLD (NONE) | yfinance:INFY.NS |
| ICICIBANK-EQ | 4963 | 1640.00 | 57.74 | 1639.70 | 1637.59 | 1628.68 | 3.03 | HOLD (NONE) | yfinance:ICICIBANK.NS |
| SBIN-EQ | 3045 | 1165.10 | 47.30 | 1169.59 | 1167.80 | 1159.81 | 3.15 | BUY (MOMENTUM_BUY) | yfinance:SBIN.NS |

## 3. Paper Order Execution & 15-Day Intraday Replay Metrics
- **Paper Orders Placed:** None (zero qualifying setups or already open).

### 15-Day Intraday Replay Benchmark
| Symbol | Days | Bars | Trades | Win Rate % | Gross P&L (₹) | Brokerage (₹) | Net P&L (₹) | Max Drawdown % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RELIANCE-EQ | 15 | 1108 | 9 | 66.67% | 1031.68 | 360.00 | 671.68 | 0.13% |
| TCS-EQ | 15 | 1106 | 9 | 11.11% | -590.64 | 360.00 | -950.64 | 0.97% |
| HDFCBANK-EQ | 15 | 1109 | 10 | 60.00% | 519.64 | 400.00 | 119.64 | 0.35% |
| INFY-EQ | 15 | 1107 | 11 | 18.18% | -301.20 | 440.00 | -741.20 | 0.97% |

## 4. Self-Improvement Reflection & `strategy_config.json` Diff
- **Trailing Trades Reviewed:** `0`
- **Updated At:** `2026-11-20T17:59:13+05:30`
| Parameter | Previous | Updated |
|---|---:|---:|
| `rsi_buy_threshold` | `27` | `26` |
| `rsi_sell_threshold` | `61` | `60` |

## 5. Today's ML Predictions for Next Session (`2026-11-23`)
- **Saved Snapshot:** `D:\trading bot for skl\predictions\predictions_2026-11-20.json`
- **Average Out-of-Sample Test Directional Accuracy:** `54.08%`
- **Average Out-of-Sample Test MAE:** `1.3433%`

| Symbol | Today Close (₹) | Predicted Next Close (₹) | Pred Return % | Direction | Conf % | Action | Target (₹) | Stop-Loss (₹) | Winning Model | Test MAE % (95% CI) | Test Dir Acc % |
|---|---:|---:|---:|---|---:|---|---:|---:|---|---:|---:|
| RELIANCE-EQ | 1377.50 | 1376.09 | -0.102% | **NEUTRAL** | 66.1% | `WAIT_FOR_VWAP_BREAKOUT` | 1429.07 | 1343.12 | `GradientBoostedStumps(n=25, lr=0.07)` | 1.270% [0.902, 1.878] | 48.98% |
| TCS-EQ | 2376.20 | 2372.02 | -0.176% | **DOWN** | 70.2% | `AVOID_LONG_OR_SHORT_INTRADAY` | 2244.76 | 2474.78 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.374% [1.010, 1.803] | 59.18% |
| HDFCBANK-EQ | 846.00 | 847.40 | +0.165% | **UP** | 65.8% | `BUY_ON_OPEN_OR_HOLD` | 881.46 | 819.40 | `GradientBoostedStumps(n=60, lr=0.07)` | 1.458% [1.215, 1.741] | 46.94% |
| INFY-EQ | 1098.00 | 1095.06 | -0.268% | **DOWN** | 68.5% | `AVOID_LONG_OR_SHORT_INTRADAY` | 1030.16 | 1148.88 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.635% [1.318, 2.045] | 53.06% |
| ICICIBANK-EQ | 1640.00 | 1645.20 | +0.317% | **UP** | 75.8% | `BUY_ON_OPEN_OR_HOLD` | 1702.12 | 1593.41 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.081% [0.850, 1.417] | 69.39% |
| SBIN-EQ | 1165.10 | 1167.13 | +0.174% | **UP** | 66.1% | `BUY_ON_OPEN_OR_HOLD` | 1214.12 | 1128.33 | `GradientBoostedStumps(n=15, lr=0.07)` | 1.242% [1.003, 1.425] | 46.94% |