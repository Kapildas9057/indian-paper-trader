"""
IndianPaperTrader: Multi-Mode Autonomous Orchestrator (--mode direct | agy | hermes).

Executes the 4-phase "COOK" Protocol end-to-end + Phase 5 ML Training, Next-Session
Prediction & Tomorrow Verification Loop, persisting all logs to `logs/` and `predictions/`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import indian_paper_mcp as ipt
import ml_predictor as mlp

CORE_WATCHLIST: List[Tuple[str, str]] = [
    ("RELIANCE-EQ", "2885"),
    ("TCS-EQ", "11536"),
    ("HDFCBANK-EQ", "1333"),
    ("INFY-EQ", "1594"),
    ("ICICIBANK-EQ", "4963"),
    ("SBIN-EQ", "3045"),
]

REPLAY_WATCHLIST: List[Tuple[str, str]] = [
    ("RELIANCE-EQ", "2885"),
    ("TCS-EQ", "11536"),
    ("HDFCBANK-EQ", "1333"),
    ("INFY-EQ", "1594"),
]


def _configure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _compute_adaptive_tuning(
    cfg: Dict[str, Any],
    replay_results: List[Dict[str, Any]],
    stop_loss_hit: bool,
) -> Dict[str, Any]:
    total_trades = sum(r["total_trades"] for r in replay_results)
    total_wins = sum(r["winning_trades"] for r in replay_results)
    agg_win_rate = round((total_wins / total_trades) * 100.0, 2) if total_trades > 0 else 0.0
    agg_net_pnl = round(sum(r["net_pnl_inr"] for r in replay_results), 2)
    worst_dd = round(max((r["max_drawdown_pct"] for r in replay_results), default=0.0), 2)

    old_rsi_buy = int(cfg.get("rsi_buy_threshold", 35))
    old_rsi_sell = int(cfg.get("rsi_sell_threshold", 68))
    old_risk = float(cfg.get("risk_per_trade_pct", 10.0))

    new_rsi_buy = old_rsi_buy
    new_rsi_sell = old_rsi_sell
    new_risk = old_risk

    if stop_loss_hit or agg_win_rate < 52.0 or agg_net_pnl < 0:
        new_rsi_buy = max(25, old_rsi_buy - 1)
        new_rsi_sell = max(60, old_rsi_sell - 1)
        # Keep risk allocation >= 10% so winning trades clear the INR 40 flat round-trip brokerage
        new_risk = max(10.0, min(15.0, round(old_risk, 2)))
        diagnosis = (
            f"Selectivity tightening triggered (win_rate={agg_win_rate}%, "
            f"agg_net_pnl=₹{agg_net_pnl:.2f}, max_dd={worst_dd}%, stop_loss_hit={stop_loss_hit}). "
            f"Tuned RSI buy floor to {new_rsi_buy}, RSI momentum cap to {new_rsi_sell}, "
            f"and maintained {new_risk}% risk sizing so winning moves overcome ₹40.00 flat brokerage."
        )
    elif agg_win_rate > 60.0 and worst_dd < 2.0 and agg_net_pnl > 0:
        new_risk = min(15.0, round(old_risk + 1.5, 2))
        diagnosis = (
            f"Positive edge confirmed (win_rate={agg_win_rate}%, agg_net_pnl=₹{agg_net_pnl:.2f}, "
            f"max_dd={worst_dd}%). Scaled per-trade risk allocation to {new_risk}% within 15.0% safety cap."
        )
    else:
        new_rsi_sell = max(60, old_rsi_sell - 1)
        diagnosis = (
            f"Moderate replay edge (win_rate={agg_win_rate}%, agg_net_pnl=₹{agg_net_pnl:.2f}, "
            f"max_dd={worst_dd}%). Tightened RSI momentum exit ceiling to {new_rsi_sell} while preserving {new_risk}% risk sizing."
        )

    return {
        "agg_win_rate_pct": agg_win_rate,
        "agg_net_pnl_inr": agg_net_pnl,
        "worst_drawdown_pct": worst_dd,
        "lesson_learned": diagnosis,
        "new_rsi_buy": new_rsi_buy,
        "new_rsi_sell": new_rsi_sell,
        "new_risk_per_trade_pct": new_risk,
    }


def run_direct_cook_cycle(run_ml: bool = True) -> Dict[str, Any]:
    mlp.ensure_log_dirs_and_tables()
    now_ist = datetime.now(ipt.IST_TZ)
    market_open = (
        now_ist.weekday() < 5
        and ((now_ist.hour > 9 or (now_ist.hour == 9 and now_ist.minute >= 15))
             and (now_ist.hour < 15 or (now_ist.hour == 15 and now_ist.minute <= 30)))
    )

    mlp.log_event("Starting 4-Phase COOK cycle", extra={"market_open": market_open})

    # PHASE 1: Mark-to-Market Sweep
    phase1_ledger = ipt.evaluate_open_positions()
    open_symbols = {pos["symbol"] for pos in phase1_ledger["open_positions"]}
    stop_loss_hit = any(
        t.get("exit_reason") == "STOP_LOSS_HIT" for t in phase1_ledger.get("auto_closed", [])
    )

    # PHASE 2: Nifty 50 Technical Scan
    snapshots: List[Dict[str, Any]] = []
    for sym, tok in CORE_WATCHLIST:
        snapshots.append(ipt.get_market_snapshot(symbol=sym, token=tok, exchange="NSE", interval="FIVE_MINUTE"))

    # PHASE 3: Friction-Aware Paper Execution & 15-Day Replay Simulation
    placed_orders: List[Dict[str, Any]] = []
    skipped_signals: List[Dict[str, Any]] = []
    for snap in snapshots:
        sig = snap["signal_evaluation"]
        sym = snap["symbol"]
        if sig["signal"] == "BUY":
            if sym in open_symbols:
                skipped_signals.append({"symbol": sym, "reason": "Position already open"})
                continue
            ind = snap["indicators"]
            rationale = (
                f"{sig['setup_type']}: LTP={snap['ltp']}, RSI_14={ind['RSI_14']}, "
                f"EMA_9={ind['EMA_9']}, EMA_21={ind['EMA_21']}, VWAP={ind['VWAP']}, ATR_14={ind['ATR_14']}"
            )
            order_res = ipt.place_paper_order(
                symbol=sym,
                token=snap["token"],
                side="BUY",
                quantity=sig["suggested_quantity"],
                ltp=snap["ltp"],
                stop_loss=sig["suggested_stop_loss"],
                take_profit=sig["suggested_take_profit"],
                rationale=rationale,
                exchange="NSE",
            )
            placed_orders.append(order_res)
            mlp.log_event(f"Paper order result for {sym}", extra=order_res)
            if order_res.get("status") == "FILLED":
                open_symbols.add(sym)

    replay_results: List[Dict[str, Any]] = []
    for sym, tok in REPLAY_WATCHLIST:
        replay_results.append(ipt.run_historical_replay_sim(symbol=sym, token=tok, days=15, exchange="NSE"))

    # PHASE 4: Self-Reflection & Strategy Parameter Tuning
    cfg_before = json.loads(ipt.STRATEGY_CONFIG_PATH.read_text(encoding="utf-8"))
    tuning = _compute_adaptive_tuning(cfg_before, replay_results, stop_loss_hit)
    reflection_result = ipt.reflect_and_update_strategy(
        lesson_learned=tuning["lesson_learned"],
        new_rsi_buy=tuning["new_rsi_buy"],
        new_rsi_sell=tuning["new_rsi_sell"],
        new_risk_per_trade_pct=tuning["new_risk_per_trade_pct"],
    )

    # PHASE 5: Chronological ML Training, Next-Session Prediction & Verification
    ml_predictions: Dict[str, Any] = {}
    prediction_verification: Dict[str, Any] = {}
    if run_ml:
        ml_predictions = mlp.train_and_predict_watchlist(CORE_WATCHLIST)
        prediction_verification = mlp.evaluate_saved_predictions(force_mark_to_market=True)

    final_ledger = ipt.evaluate_open_positions()
    result = {
        "timestamp_ist": now_ist.isoformat(timespec="seconds"),
        "nse_market_open": market_open,
        "phase1_ledger": phase1_ledger,
        "snapshots": snapshots,
        "placed_orders": placed_orders,
        "skipped_signals": skipped_signals,
        "replay_results": replay_results,
        "reflection_result": reflection_result,
        "ml_predictions": ml_predictions,
        "prediction_verification": prediction_verification,
        "final_ledger": final_ledger,
    }

    mlp.append_jsonl_log(
        mlp.CYCLE_LOG_PATH,
        {
            "event": "COOK_CYCLE_COMPLETED",
            "timestamp_ist": result["timestamp_ist"],
            "virtual_cash": final_ledger["virtual_cash"],
            "total_equity": final_ledger["total_equity"],
            "open_positions_count": len(final_ledger["open_positions"]),
            "placed_orders_count": len(placed_orders),
            "strategy_diff": reflection_result["diff"],
            "predictions_saved": len(ml_predictions.get("predictions", [])),
        },
    )
    report_md = render_markdown_dashboard(result)
    (mlp.LOGS_DIR / "latest_report.md").write_text(report_md, encoding="utf-8")
    mlp.log_event("Completed 4-Phase COOK cycle + ML Prediction save; wrote logs/latest_report.md")
    return result


def render_markdown_dashboard(res: Dict[str, Any]) -> str:
    ledger = res["final_ledger"]
    lines: List[str] = [
        "# IndianPaperTrader — Autonomous Cycle & ML Prediction Dashboard",
        f"- **Run Timestamp (IST):** `{res['timestamp_ist']}`",
        f"- **NSE Live Market Hours:** `{'OPEN' if res['nse_market_open'] else 'CLOSED (Off-Hours Fallback & 15-Day Replay Active)'}`",
        "",
        "## 1. Portfolio Ledger",
        f"- **Virtual Cash:** `₹{ledger['virtual_cash']:,.2f}`",
        f"- **Realized P&L:** `₹{ledger['realized_pnl']:,.2f}`",
        f"- **Unrealized P&L:** `₹{ledger['unrealized_pnl']:,.2f}`",
        f"- **Total Brokerage Paid:** `₹{ledger['total_brokerage_paid']:,.2f}`",
        f"- **Total Equity:** `₹{ledger['total_equity']:,.2f}`",
        f"- **Total Closed Trades:** `{ledger['total_closed_trades']}`",
        f"- **Open Positions:** `{len(ledger['open_positions'])}`",
    ]
    if ledger["open_positions"]:
        lines.extend(
            [
                "",
                "| Symbol | Side | Qty | Entry (₹) | Current LTP (₹) | Stop-Loss (₹) | Take-Profit (₹) | Unrealized P&L (₹) |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for p in ledger["open_positions"]:
            lines.append(
                f"| {p['symbol']} | {p['side']} | {p['quantity']} | {p['entry_price']:.2f} | "
                f"{p['current_ltp']:.2f} | {p['stop_loss']:.2f} | {p['take_profit']:.2f} | {p['unrealized_pnl']:.2f} |"
            )

    lines.extend(
        [
            "",
            "## 2. Watchlist Technical Matrix",
            "| Symbol | Token | LTP (₹) | RSI_14 | EMA_9 | EMA_21 | VWAP (₹) | ATR_14 | Signal / Setup | Source |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for s in res["snapshots"]:
        ind = s["indicators"]
        sig = s["signal_evaluation"]
        lines.append(
            f"| {s['symbol']} | {s['token']} | {s['ltp']:.2f} | {ind['RSI_14']:.2f} | "
            f"{ind['EMA_9']:.2f} | {ind['EMA_21']:.2f} | {ind['VWAP']:.2f} | {ind['ATR_14']:.2f} | "
            f"{sig['signal']} ({sig['setup_type']}) | {s['data_source']} |"
        )

    lines.extend(["", "## 3. Paper Order Execution & 15-Day Intraday Replay Metrics"])
    if res["placed_orders"]:
        lines.append("### Paper Orders Placed")
        for o in res["placed_orders"]:
            if o.get("status") == "FILLED":
                lines.append(
                    f"- **FILLED** `{o['symbol']}` BUY {o['quantity']} @ ₹{o['fill_price']:.2f} "
                    f"(SL ₹{o['stop_loss']:.2f} | TP ₹{o['take_profit']:.2f} | Brokerage ₹{o['brokerage_inr']:.2f})"
                )
            else:
                lines.append(f"- **{o.get('status')}** `{o.get('symbol', '')}`: {o.get('reason')}")
    else:
        lines.append("- **Paper Orders Placed:** None (zero qualifying setups or already open).")

    lines.extend(
        [
            "",
            "### 15-Day Intraday Replay Benchmark",
            "| Symbol | Days | Bars | Trades | Win Rate % | Gross P&L (₹) | Brokerage (₹) | Net P&L (₹) | Max Drawdown % |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for r in res["replay_results"]:
        lines.append(
            f"| {r['symbol']} | {r['days_simulated']} | {r['bars_tested']} | {r['total_trades']} | "
            f"{r['win_rate_pct']:.2f}% | {r['gross_pnl_inr']:.2f} | {r['total_brokerage_inr']:.2f} | "
            f"{r['net_pnl_inr']:.2f} | {r['max_drawdown_pct']:.2f}% |"
        )

    refl = res["reflection_result"]
    lines.extend(
        [
            "",
            "## 4. Self-Improvement Reflection & `strategy_config.json` Diff",
            f"- **Trailing Trades Reviewed:** `{refl['trailing_trades_reviewed']}`",
            f"- **Updated At:** `{refl['timestamp']}`",
            "| Parameter | Previous | Updated |",
            "|---|---:|---:|",
        ]
    )
    if refl["diff"]:
        for k, v in refl["diff"].items():
            lines.append(f"| `{k}` | `{v['old']}` | `{v['new']}` |")
    else:
        lines.append("| *(no parameter changes)* | - | - |")

    ml_data = res.get("ml_predictions", {})
    if ml_data and ml_data.get("predictions"):
        lines.extend(
            [
                "",
                f"## 5. Today's ML Predictions for Next Session (`{ml_data['target_session_date']}`)",
                f"- **Saved Snapshot:** `{ml_data['saved_json_path']}`",
                f"- **Average Out-of-Sample Test Directional Accuracy:** `{ml_data['avg_test_directional_accuracy_pct']:.2f}%`",
                f"- **Average Out-of-Sample Test MAE:** `{ml_data['avg_test_mae_pct']:.4f}%`",
                "",
                "| Symbol | Today Close (₹) | Predicted Next Close (₹) | Pred Return % | Direction | Conf % | Action | Target (₹) | Stop-Loss (₹) | Winning Model | Test MAE % (95% CI) | Test Dir Acc % |",
                "|---|---:|---:|---:|---|---:|---|---:|---:|---|---:|---:|",
            ]
        )
        for p in ml_data["predictions"]:
            ci = p["test_mae_ci95"]
            lines.append(
                f"| {p['symbol']} | {p['base_close']:.2f} | {p['predicted_next_close']:.2f} | "
                f"{p['predicted_return_pct']:+.3f}% | **{p['predicted_direction']}** | {p['confidence_pct']:.1f}% | "
                f"`{p['recommended_action']}` | {p['predicted_take_profit']:.2f} | {p['predicted_stop_loss']:.2f} | "
                f"`{p['selected_model']}` | {p['test_mae_pct']:.3f}% [{ci['low_pct']:.3f}, {ci['high_pct']:.3f}] | "
                f"{p['test_dir_acc_pct']:.2f}% |"
            )

    return "\n".join(lines)


def main() -> int:
    _configure_utf8_stdout()
    parser = argparse.ArgumentParser(description="IndianPaperTrader Autonomous Orchestrator")
    parser.add_argument("--mode", choices=["direct", "agy", "hermes"], default="direct")
    parser.add_argument("--verify-predictions", action="store_true", help="Evaluate saved predictions against market LTP.")
    parser.add_argument("--json", action="store_true", help="Also emit raw JSON telemetry.")
    args = parser.parse_args()

    if args.verify_predictions:
        ver = mlp.evaluate_saved_predictions(force_mark_to_market=True)
        print(json.dumps(ver, indent=2))
        return 0

    if args.mode in ("agy", "hermes"):
        cli_bin = shutil.which(args.mode)
        if not cli_bin:
            print(f"ERROR: '{args.mode}' CLI not found in PATH.", file=sys.stderr)
            return 1
        prompt_text = (BASE_DIR / "GEMINI.md").read_text(encoding="utf-8")
        proc = subprocess.run([cli_bin, "-p", prompt_text], cwd=str(BASE_DIR), check=False)
        return proc.returncode

    result = run_direct_cook_cycle(run_ml=True)
    print(render_markdown_dashboard(result))
    if args.json:
        print("\n```json")
        print(json.dumps(result, indent=2, default=str))
        print("```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
