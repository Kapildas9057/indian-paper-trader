# Autonomous Quantitative Strategy Memory

## Post-Trade Reflections & Parameter Updates

### [2026-11-18T21:23:09+05:30] Quantitative Post-Mortem
- **Lesson:** Defensive tightening triggered (win_rate=38.46%, agg_net_pnl=₹-1352.76, max_dd=0.89%, stop_loss_hit=False). Lowered RSI buy floor to 32, tightened RSI momentum cap to 66, and reduced per-trade risk allocation to 7.5% to filter choppy reversals and fee drag.
- **Trailing Ledger:** 0 closed trades reviewed (Win Rate: 0.0%)
- **Parameter Diff:** rsi_buy_threshold: 35 -> 32, rsi_sell_threshold: 68 -> 66, risk_per_trade_pct: 10.0 -> 7.5

### [2026-11-18T21:35:08+05:30] Quantitative Post-Mortem
- **Lesson:** Defensive tightening triggered (win_rate=28.85%, agg_net_pnl=₹-1811.60, max_dd=0.93%, stop_loss_hit=False). Lowered RSI buy floor to 29, tightened RSI momentum cap to 64, and reduced per-trade risk allocation to 5.0% to filter choppy reversals and fee drag.
- **Trailing Ledger:** 0 closed trades reviewed (Win Rate: 0.0%)
- **Parameter Diff:** rsi_buy_threshold: 32 -> 29, rsi_sell_threshold: 66 -> 64, risk_per_trade_pct: 7.5 -> 5.0

### [2026-11-18T21:37:44+05:30] Quantitative Post-Mortem
- **Lesson:** At 5.0% risk allocation, RELIANCE-EQ hit 100.0% win rate (+₹160.92 net P&L, 0.02% max DD), but small 2-share TCS-EQ winners (+₹14.28 and +₹32.46 gross) turned negative after ₹40.00 flat round-trip brokerage. Tightening entry selectivity (rsi_buy_threshold 29 -> 28, rsi_sell_threshold 64 -> 62) while restoring position sizing to 11.0% so winning moves clear fixed ₹40.00 fee drag.
- **Trailing Ledger:** 0 closed trades reviewed (Win Rate: 0.0%)
- **Parameter Diff:** rsi_buy_threshold: 29 -> 28, rsi_sell_threshold: 64 -> 62, risk_per_trade_pct: 5.0 -> 11.0

### [2026-11-20T17:25:18+05:30] Quantitative Post-Mortem
- **Lesson:** Selectivity tightening triggered (win_rate=35.56%, agg_net_pnl=₹-1300.25, max_dd=1.15%, stop_loss_hit=False). Tuned RSI buy floor to 27, RSI momentum cap to 61, and maintained 11.0% risk sizing so winning moves overcome ₹40.00 flat brokerage.
- **Trailing Ledger:** 0 closed trades reviewed (Win Rate: 0.0%)
- **Parameter Diff:** rsi_buy_threshold: 28 -> 27, rsi_sell_threshold: 62 -> 61

### [2026-11-20T17:59:13+05:30] Quantitative Post-Mortem
- **Lesson:** Selectivity tightening triggered (win_rate=38.46%, agg_net_pnl=₹-900.52, max_dd=0.97%, stop_loss_hit=False). Tuned RSI buy floor to 26, RSI momentum cap to 60, and maintained 11.0% risk sizing so winning moves overcome ₹40.00 flat brokerage.
- **Trailing Ledger:** 0 closed trades reviewed (Win Rate: 0.0%)
- **Parameter Diff:** rsi_buy_threshold: 27 -> 26, rsi_sell_threshold: 61 -> 60

### [2026-11-23T17:20:12+05:30] Quantitative Post-Mortem
- **Lesson:** Selectivity tightening triggered (win_rate=37.14%, agg_net_pnl=₹-786.24, max_dd=0.96%, stop_loss_hit=True). Tuned RSI buy floor to 25, RSI momentum cap to 60, and maintained 11.0% risk sizing so winning moves overcome ₹40.00 flat brokerage.
- **Trailing Ledger:** 3 closed trades reviewed (Win Rate: 33.33%)
- **Parameter Diff:** rsi_buy_threshold: 26 -> 25

### [2026-11-24T18:48:07+05:30] Quantitative Post-Mortem
- **Lesson:** Selectivity tightening triggered (win_rate=40.0%, agg_net_pnl=₹-786.76, max_dd=0.95%, stop_loss_hit=False). Tuned RSI buy floor to 25, RSI momentum cap to 60, and maintained 11.0% risk sizing so winning moves overcome ₹40.00 flat brokerage.
- **Trailing Ledger:** 3 closed trades reviewed (Win Rate: 33.33%)
- **Parameter Diff:** no threshold changes

### [2026-11-25T17:39:01+05:30] Quantitative Post-Mortem
- **Lesson:** Selectivity tightening triggered (win_rate=37.14%, agg_net_pnl=₹-1177.08, max_dd=1.0%, stop_loss_hit=False). Tuned RSI buy floor to 25, RSI momentum cap to 60, and maintained 11.0% risk sizing so winning moves overcome ₹40.00 flat brokerage.
- **Trailing Ledger:** 3 closed trades reviewed (Win Rate: 33.33%)
- **Parameter Diff:** no threshold changes

### [2026-11-26T17:25:26+05:30] Quantitative Post-Mortem
- **Lesson:** Selectivity tightening triggered (win_rate=37.14%, agg_net_pnl=₹-1002.22, max_dd=1.0%, stop_loss_hit=False). Tuned RSI buy floor to 25, RSI momentum cap to 60, and maintained 11.0% risk sizing so winning moves overcome ₹40.00 flat brokerage.
- **Trailing Ledger:** 3 closed trades reviewed (Win Rate: 33.33%)
- **Parameter Diff:** no threshold changes
