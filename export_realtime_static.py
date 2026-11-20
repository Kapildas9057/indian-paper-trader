"""
Exports real-time portfolio, invested stocks, intraday equity performance curve,
and ML expected growth data from `paper_ledger.db` and live NSE market feeds
into `public/live_data.json` for Firebase Hosting and Render Static Site deployment.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import autonomous_runner as runner
import indian_paper_mcp as ipt
import ml_predictor as mlp

PUBLIC_DIR = BASE_DIR / "public"
LIVE_DATA_JSON_PATH = PUBLIC_DIR / "live_data.json"


def generate_realtime_payload() -> Dict[str, Any]:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    mlp.ensure_log_dirs_and_tables()

    # Sweep and fetch real-time mark-to-market ledger
    ledger = ipt.evaluate_open_positions()

    # Fetch real-time snapshots and intraday 5m series for all watchlist stocks
    watchlist_snapshots: Dict[str, Dict[str, Any]] = {}
    intraday_curves: Dict[str, List[Dict[str, Any]]] = {}

    for sym, tok in runner.CORE_WATCHLIST:
        snap = ipt.get_market_snapshot(symbol=sym, token=tok, exchange="NSE", interval="FIVE_MINUTE")
        watchlist_snapshots[sym] = snap
        df, _ = ipt.market_client.fetch_candles(
            symbol=sym, token=tok, exchange="NSE", interval="FIVE_MINUTE", days=5
        )
        tail_df = df.tail(36)
        intraday_curves[sym] = [
            {
                "time": idx.strftime("%d %b %H:%M"),
                "close": round(float(row["Close"]), 2),
            }
            for idx, row in tail_df.iterrows()
        ]

    # Load latest ML predictions per symbol
    with closing(sqlite3.connect(ipt.DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        pred_rows = conn.execute(
            "SELECT * FROM daily_predictions ORDER BY id DESC LIMIT 12"
        ).fetchall()
        closed_rows = conn.execute(
            "SELECT * FROM closed_trades ORDER BY id DESC LIMIT 20"
        ).fetchall()

    predictions_by_sym: Dict[str, Dict[str, Any]] = {}
    for r in pred_rows:
        s = r["symbol"]
        if s not in predictions_by_sym:
            predictions_by_sym[s] = dict(r)

    # Enrich each invested stock with real-time metrics + expected growth
    invested_stocks: List[Dict[str, Any]] = []
    total_invested = 0.0
    total_current_value = 0.0
    total_expected_next_value = 0.0
    total_target_value = 0.0

    for pos in ledger["open_positions"]:
        sym = pos["symbol"]
        qty = int(pos["quantity"])
        entry_price = float(pos["entry_price"])
        current_ltp = float(pos["current_ltp"])
        stop_loss = float(pos["stop_loss"])
        take_profit = float(pos["take_profit"])

        invested_amt = round(entry_price * qty, 2)
        current_val = round(current_ltp * qty, 2)
        pnl_inr = round(current_val - invested_amt, 2)
        pnl_pct = round((pnl_inr / invested_amt) * 100.0, 2) if invested_amt > 0 else 0.0

        pred = predictions_by_sym.get(sym, {})
        pred_next_close = float(pred.get("predicted_next_close", current_ltp))
        pred_ret_pct = float(pred.get("predicted_return_pct", 0.0))
        pred_dir = str(pred.get("predicted_direction", "NEUTRAL"))
        conf_pct = float(pred.get("confidence_pct", 65.0))

        # Expected value combines ML next-session forecast and strategy take-profit target
        expected_next_val = round(pred_next_close * qty, 2)
        target_val = round(take_profit * qty, 2)
        target_upside_inr = round(target_val - invested_amt, 2)
        target_upside_pct = round((target_upside_inr / invested_amt) * 100.0, 2) if invested_amt > 0 else 0.0
        next_session_change_inr = round(expected_next_val - current_val, 2)

        total_invested = round(total_invested + invested_amt, 2)
        total_current_value = round(total_current_value + current_val, 2)
        total_expected_next_value = round(total_expected_next_value + expected_next_val, 2)
        total_target_value = round(total_target_value + target_val, 2)

        snap = watchlist_snapshots.get(sym, {})
        ind = snap.get("indicators", {})
        yf_ticker = ipt.market_client.to_yfinance_ticker(sym, "NSE")

        invested_stocks.append(
            {
                "id": pos["id"],
                "symbol": sym,
                "short_name": sym.replace("-EQ", ""),
                "yf_ticker": yf_ticker,
                "token": pos["token"],
                "side": pos["side"],
                "quantity": qty,
                "entry_price": entry_price,
                "current_ltp": current_ltp,
                "invested_inr": invested_amt,
                "current_value_inr": current_val,
                "pnl_inr": pnl_inr,
                "pnl_pct": pnl_pct,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "target_value_inr": target_val,
                "target_upside_inr": target_upside_inr,
                "target_upside_pct": target_upside_pct,
                "ml_predicted_close": pred_next_close,
                "ml_predicted_return_pct": pred_ret_pct,
                "ml_direction": pred_dir,
                "ml_confidence_pct": conf_pct,
                "ml_next_session_change_inr": next_session_change_inr,
                "indicators": ind,
                "opened_at": pos["opened_at"],
                "sparkline": intraday_curves.get(sym, [])[-18:],
            }
        )

    # Build real-time intraday portfolio performance curve (Angel One style)
    # Using the actual 36 trailing 5-minute bars of the currently held shares + virtual cash
    sample_sym = invested_stocks[0]["symbol"] if invested_stocks else "RELIANCE-EQ"
    timeline_len = len(intraday_curves.get(sample_sym, []))
    performance_curve: List[Dict[str, Any]] = []

    for i in range(timeline_len):
        ts_label = intraday_curves[sample_sym][i]["time"]
        holdings_val_at_i = 0.0
        for st in invested_stocks:
            curve = intraday_curves.get(st["symbol"], [])
            px = curve[min(i, len(curve) - 1)]["close"] if curve else st["current_ltp"]
            holdings_val_at_i += px * st["quantity"]
        holdings_val_at_i = round(holdings_val_at_i, 2)
        total_eq_at_i = round(float(ledger["virtual_cash"]) + holdings_val_at_i, 2)
        pnl_at_i = round(holdings_val_at_i - total_invested, 2)
        performance_curve.append(
            {
                "time": ts_label,
                "holdings_value": holdings_val_at_i,
                "total_equity": total_eq_at_i,
                "invested": total_invested,
                "pnl_inr": pnl_at_i,
            }
        )

    unrealized_pnl = round(total_current_value - total_invested, 2)
    realized_pnl = round(float(ledger["realized_pnl"]), 2)
    total_pnl = round(unrealized_pnl + realized_pnl, 2)
    net_after_fees_pnl = round(total_pnl - float(ledger["total_brokerage_paid"]), 2)
    returns_pct = round((unrealized_pnl / total_invested) * 100.0, 2) if total_invested > 0 else 0.0

    expected_target_growth_inr = round(total_target_value - total_invested, 2)
    expected_target_growth_pct = (
        round((expected_target_growth_inr / total_invested) * 100.0, 2) if total_invested > 0 else 0.0
    )
    ml_next_session_growth_inr = round(total_expected_next_value - total_current_value, 2)
    ml_next_session_growth_pct = (
        round((ml_next_session_growth_inr / total_current_value) * 100.0, 2)
        if total_current_value > 0
        else 0.0
    )

    watchlist_summary: List[Dict[str, Any]] = []
    for sym, tok in runner.CORE_WATCHLIST:
        snap = watchlist_snapshots[sym]
        pred = predictions_by_sym.get(sym, {})
        watchlist_summary.append(
            {
                "symbol": sym,
                "short_name": sym.replace("-EQ", ""),
                "yf_ticker": ipt.market_client.to_yfinance_ticker(sym, "NSE"),
                "token": tok,
                "ltp": snap["ltp"],
                "timestamp": snap["timestamp"],
                "indicators": snap["indicators"],
                "signal": snap["signal_evaluation"]["signal"],
                "setup_type": snap["signal_evaluation"]["setup_type"],
                "ml_predicted_close": pred.get("predicted_next_close", snap["ltp"]),
                "ml_predicted_return_pct": pred.get("predicted_return_pct", 0.0),
                "ml_direction": pred.get("predicted_direction", "NEUTRAL"),
                "ml_confidence_pct": pred.get("confidence_pct", 65.0),
                "ml_target_session": pred.get("target_session_date", ""),
                "ml_model": pred.get("selected_model", ""),
                "test_dir_acc_pct": pred.get("test_dir_acc_pct", 0.0),
            }
        )

    payload = {
        "generated_at_ist": datetime.now(ipt.IST_TZ).isoformat(timespec="seconds"),
        "data_feed": "NSE Real-Time Market Feed (Angel One SmartAPI / Yahoo Finance .NS)",
        "portfolio": {
            "initial_capital_inr": ipt.INITIAL_VIRTUAL_CASH,
            "virtual_cash_inr": ledger["virtual_cash"],
            "invested_inr": total_invested,
            "current_returns_value_inr": total_current_value,
            "total_equity_inr": round(float(ledger["virtual_cash"]) + total_current_value, 2),
            "profit_or_loss_inr": total_pnl,
            "unrealized_pnl_inr": unrealized_pnl,
            "realized_pnl_inr": realized_pnl,
            "net_pnl_after_brokerage_inr": net_after_fees_pnl,
            "returns_pct": returns_pct,
            "brokerage_paid_inr": ledger["total_brokerage_paid"],
            "slippage_pct_per_leg": ipt.SLIPPAGE_PCT * 100.0,
            "expected_target_value_inr": total_target_value,
            "expected_growth_inr": expected_target_growth_inr,
            "expected_growth_pct": expected_target_growth_pct,
            "ml_next_session_expected_value_inr": total_expected_next_value,
            "ml_next_session_growth_inr": ml_next_session_growth_inr,
            "ml_next_session_growth_pct": ml_next_session_growth_pct,
            "open_positions_count": len(invested_stocks),
            "closed_trades_count": len(closed_rows),
        },
        "invested_stocks": invested_stocks,
        "performance_curve": performance_curve,
        "watchlist": watchlist_summary,
        "strategy_config": ipt._load_strategy_config(),
    }

    LIVE_DATA_JSON_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    data = generate_realtime_payload()
    p = data["portfolio"]
    print(
        f"EXPORTED live_data.json: Invested=₹{p['invested_inr']:,.2f} | "
        f"Current=₹{p['current_returns_value_inr']:,.2f} | "
        f"P&L=₹{p['profit_or_loss_inr']:+,.2f} ({p['returns_pct']:+.2f}%) | "
        f"Expected Growth=+₹{p['expected_growth_inr']:,.2f} (+{p['expected_growth_pct']:.2f}%)"
    )
