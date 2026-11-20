"""
IndianPaperTrader: Interactive Web GUI & Quantitative ML Command Center.

Launches a local HTTP dashboard at http://127.0.0.1:8765 displaying:
  - Portfolio Clearinghouse Ledger (Cash, Realized/Unrealized P&L, Brokerage, Open Positions)
  - Today's ML Predictions for Tomorrow's Session + Next-Day Outcome Verification Scorecard
  - Chronological ML Model Comparison (Naive Drift vs L2 Ridge vs Gradient Boosted Stumps)
  - Live Nifty 50 Technical Watchlist Matrix (RSI_14, EMA_9, EMA_21, Session VWAP, ATR_14)
  - Strategy Config & Post-Trade Memory Evolution (MEMORY.md)
  - Real-Time Persistent Log Stream (logs/indian_paper_trader.log & JSONL audit files)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import urllib.request
import webbrowser
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import autonomous_runner as runner
import export_realtime_static as rt_export
import indian_paper_mcp as ipt
import ml_predictor as mlp

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>IndianPaperTrader — NSE/BSE Quant & ML Command Center</title>
<style>
  :root {
    --bg: #0b0f19;
    --panel: #131a2a;
    --panel-alt: #182136;
    --border: #26324d;
    --text: #e6edf7;
    --muted: #93a4c3;
    --accent: #38bdf8;
    --green: #22c55e;
    --red: #ef4444;
    --amber: #f59e0b;
    --purple: #a855f7;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: 'Segoe UI', Inter, system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.45;
  }
  header {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    background: linear-gradient(90deg, #0f172a, #172554);
    border-bottom: 1px solid var(--border);
    gap: 12px;
  }
  .brand h1 {
    margin: 0;
    font-size: 1.25rem;
    letter-spacing: 0.3px;
  }
  .brand p {
    margin: 2px 0 0;
    font-size: 0.82rem;
    color: var(--muted);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
  button {
    background: var(--panel-alt);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 9px 15px;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.84rem;
    transition: all 0.15s ease;
  }
  button:hover { border-color: var(--accent); background: #1e293b; }
  button.primary {
    background: linear-gradient(135deg, #0284c7, #2563eb);
    border-color: #38bdf8;
  }
  button.ml-btn {
    background: linear-gradient(135deg, #7e22ce, #4f46e5);
    border-color: #c084fc;
  }
  button.verify-btn {
    background: linear-gradient(135deg, #059669, #0d9488);
    border-color: #34d399;
  }
  button:disabled { opacity: 0.55; cursor: wait; }
  main {
    max-width: 1500px;
    margin: 0 auto;
    padding: 20px 24px 40px;
    display: grid;
    gap: 20px;
  }
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
    gap: 14px;
  }
  .kpi {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
  }
  .kpi .label {
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--muted);
  }
  .kpi .val {
    font-size: 1.35rem;
    font-weight: 700;
    margin-top: 4px;
  }
  .kpi .sub {
    font-size: 0.76rem;
    color: var(--muted);
    margin-top: 2px;
  }
  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 18px;
    overflow-x: auto;
  }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    gap: 10px;
  }
  .card-header h2 {
    margin: 0;
    font-size: 1.02rem;
    color: #f8fafc;
  }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
  }
  .badge.up, .badge.buy { background: rgba(34,197,94,0.16); color: #4ade80; border: 1px solid rgba(34,197,94,0.4); }
  .badge.down, .badge.sell { background: rgba(239,68,68,0.16); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
  .badge.neutral, .badge.hold { background: rgba(148,163,184,0.16); color: #cbd5e1; border: 1px solid rgba(148,163,184,0.35); }
  .badge.model { background: rgba(168,85,247,0.16); color: #d8b4fe; border: 1px solid rgba(168,85,247,0.4); }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.84rem;
  }
  th, td {
    padding: 9px 10px;
    text-align: left;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  th {
    color: var(--muted);
    font-weight: 600;
    font-size: 0.76rem;
    text-transform: uppercase;
    background: rgba(255,255,255,0.02);
  }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .pos { color: var(--green); font-weight: 600; }
  .neg { color: var(--red); font-weight: 600; }
  .two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }
  @media (max-width: 1100px) { .two-col { grid-template-columns: 1fr; } }
  pre.log-box {
    background: #070a12;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    font-family: Consolas, 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    max-height: 290px;
    overflow-y: auto;
    color: #cbd5e1;
    margin: 0;
    white-space: pre-wrap;
  }
  #status-banner {
    padding: 8px 14px;
    border-radius: 8px;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.35);
    font-size: 0.84rem;
    display: none;
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    <h1>IndianPaperTrader — Autonomous NSE/BSE Quant & ML Command Center</h1>
    <p>100% Air-Gapped SQLite Clearinghouse (0.05% Slippage + ₹20/leg Brokerage) • Chronological ML Forecaster & Next-Day Verification</p>
  </div>
  <div class="actions">
    <button class="primary" onclick="triggerAction('/api/run-cycle', 'Running 4-Phase COOK Cycle + ML Prediction...')">⚡ Run COOK Cycle + Predict</button>
    <button class="ml-btn" onclick="triggerAction('/api/train-predict', 'Training Chronological ML Models & Saving Today\'s Prediction...')">🧠 Train ML & Save Today's Prediction</button>
    <button class="verify-btn" onclick="triggerAction('/api/verify-predictions', 'Scoring Saved Predictions Against Market LTP...')">✅ Check Tomorrow's Outcome / Score</button>
    <button onclick="loadDashboard()">🔄 Refresh Telemetry</button>
  </div>
</header>

<main>
  <div id="status-banner"></div>

  <div class="kpi-grid" id="kpi-grid"></div>

  <div class="card">
    <div class="card-header">
      <h2>🔮 Today's ML Predictions for Next Trading Session & Outcome Verification Scorecard</h2>
      <span id="pred-meta" style="font-size:0.8rem;color:var(--muted);"></span>
    </div>
    <table>
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Pred Date</th>
          <th>Target Session</th>
          <th class="num">Today Close (₹)</th>
          <th class="num">Pred Next Close (₹)</th>
          <th class="num">Pred Return</th>
          <th>Direction</th>
          <th class="num">Conf %</th>
          <th>Action</th>
          <th class="num">Target / SL (₹)</th>
          <th>Winning Model</th>
          <th class="num">Actual / MTM (₹)</th>
          <th class="num">Abs Error</th>
          <th>Verification Status</th>
        </tr>
      </thead>
      <tbody id="predictions-tbody"></tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-header">
      <h2>📊 Chronological ML Model Comparison & Data Hygiene Audit (Train 60% / Val 20% / Test 20%)</h2>
      <span style="font-size:0.8rem;color:var(--muted);">Strict train-only standardization • Stationarity verified on % returns</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Chronological Split (Train / Val / Test)</th>
          <th>Nulls (Before → After)</th>
          <th>Lag-1 Autocorr (Close → Ret%)</th>
          <th class="num">Naive Test MAE</th>
          <th class="num">Ridge Test MAE (Dir%)</th>
          <th class="num">GBStumps Test MAE (Dir%)</th>
          <th>Selected Model</th>
          <th class="num">95% Bootstrap CI (Test MAE)</th>
        </tr>
      </thead>
      <tbody id="ml-audit-tbody"></tbody>
    </table>
  </div>

  <div class="two-col">
    <div class="card">
      <div class="card-header">
        <h2>💼 Open Portfolio Positions (paper_ledger.db)</h2>
        <span id="open-pos-count" style="font-size:0.8rem;color:var(--muted);"></span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Side</th>
            <th class="num">Qty</th>
            <th class="num">Entry (₹)</th>
            <th class="num">Current LTP (₹)</th>
            <th class="num">Stop-Loss (₹)</th>
            <th class="num">Take-Profit (₹)</th>
            <th class="num">Unrealized P&L</th>
          </tr>
        </thead>
        <tbody id="open-pos-tbody"></tbody>
      </table>
    </div>

    <div class="card">
      <div class="card-header">
        <h2>📡 Nifty 50 Technical Watchlist Matrix (5-Minute Bars)</h2>
        <span id="watchlist-ts" style="font-size:0.8rem;color:var(--muted);"></span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th class="num">LTP (₹)</th>
            <th class="num">RSI_14</th>
            <th class="num">EMA_9</th>
            <th class="num">EMA_21</th>
            <th class="num">VWAP (₹)</th>
            <th class="num">ATR_14</th>
            <th>Signal</th>
          </tr>
        </thead>
        <tbody id="watchlist-tbody"></tbody>
      </table>
    </div>
  </div>

  <div class="two-col">
    <div class="card">
      <div class="card-header">
        <h2>⚙️ Active Strategy Thresholds (strategy_config.json) & Self-Reflection Memory</h2>
      </div>
      <div id="strategy-cfg-box" style="margin-bottom:10px;font-size:0.84rem;"></div>
      <pre class="log-box" id="memory-box"></pre>
    </div>

    <div class="card">
      <div class="card-header">
        <h2>📜 Live Persistent System & Prediction Logs (logs/)</h2>
        <span style="font-size:0.78rem;color:var(--muted);">indian_paper_trader.log • predictions_history.jsonl</span>
      </div>
      <pre class="log-box" id="logs-box"></pre>
    </div>
  </div>
</main>

<script>
function fmtInr(v) {
  return '₹' + Number(v || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function setBanner(msg, show=true) {
  const el = document.getElementById('status-banner');
  el.textContent = msg;
  el.style.display = show ? 'block' : 'none';
}

async function triggerAction(endpoint, msg) {
  const btns = document.querySelectorAll('button');
  btns.forEach(b => b.disabled = true);
  setBanner('⏳ ' + msg, true);
  try {
    const resp = await fetch(endpoint, {method: 'POST'});
    const data = await resp.json();
    setBanner('✅ Action completed at ' + new Date().toLocaleTimeString(), true);
    await loadDashboard();
  } catch (err) {
    setBanner('❌ Error: ' + err, true);
  } finally {
    btns.forEach(b => b.disabled = false);
  }
}

async function loadDashboard() {
  const resp = await fetch('/api/dashboard');
  const d = await resp.json();
  const ledger = d.ledger || {};
  const preds = d.saved_predictions || [];
  const latestMl = (d.latest_ml_file && d.latest_ml_file.predictions) ? d.latest_ml_file.predictions : [];

  const avgDirAcc = latestMl.length
    ? (latestMl.reduce((a, b) => a + Number(b.test_dir_acc_pct || 0), 0) / latestMl.length).toFixed(2)
    : '0.00';

  document.getElementById('kpi-grid').innerHTML = `
    <div class="kpi"><div class="label">Virtual Cash</div><div class="val">${fmtInr(ledger.virtual_cash)}</div><div class="sub">Initial: ₹1,00,000.00</div></div>
    <div class="kpi"><div class="label">Total Equity</div><div class="val">${fmtInr(ledger.total_equity)}</div><div class="sub">Open Positions: ${(ledger.open_positions||[]).length}</div></div>
    <div class="kpi"><div class="label">Unrealized P&L</div><div class="val ${ledger.unrealized_pnl >= 0 ? 'pos' : 'neg'}">${fmtInr(ledger.unrealized_pnl)}</div><div class="sub">Realized: ${fmtInr(ledger.realized_pnl)}</div></div>
    <div class="kpi"><div class="label">Brokerage Paid</div><div class="val">${fmtInr(ledger.total_brokerage_paid)}</div><div class="sub">₹20/leg + 0.05% slip</div></div>
    <div class="kpi"><div class="label">Saved Predictions</div><div class="val">${preds.length}</div><div class="sub">Target: ${preds[0] ? preds[0].target_session_date : 'Next Session'}</div></div>
    <div class="kpi"><div class="label">ML Test Dir Accuracy</div><div class="val" style="color:var(--accent)">${avgDirAcc}%</div><div class="sub">Out-of-sample Test Split</div></div>
  `;

  document.getElementById('pred-meta').textContent =
    d.latest_ml_file && d.latest_ml_file.generated_at
      ? `Saved at ${d.latest_ml_file.generated_at} • File: predictions/predictions_today.json`
      : 'Click "Train ML & Save Today\'s Prediction" to generate';

  document.getElementById('predictions-tbody').innerHTML = preds.map(p => {
    const dirClass = p.predicted_direction === 'UP' ? 'up' : (p.predicted_direction === 'DOWN' ? 'down' : 'neutral');
    const retClass = p.predicted_return_pct >= 0 ? 'pos' : 'neg';
    const actClose = p.actual_next_close != null ? fmtInr(p.actual_next_close) : '—';
    const absErr = p.abs_error_inr != null ? `${fmtInr(p.abs_error_inr)} (${Number(p.abs_error_pct).toFixed(3)}%)` : '—';
    const statusLabel = p.status === 'EVALUATED'
      ? `<span class="badge up">EVALUATED (${p.direction_correct ? 'HIT' : 'MISS'})</span>`
      : `<span class="badge model">SAVED FOR ${p.target_session_date} (MTM Ready)</span>`;
    return `
      <tr>
        <td><strong>${p.symbol}</strong></td>
        <td>${p.prediction_date}</td>
        <td><strong>${p.target_session_date}</strong></td>
        <td class="num">${fmtInr(p.base_close)}</td>
        <td class="num"><strong>${fmtInr(p.predicted_next_close)}</strong></td>
        <td class="num ${retClass}">${Number(p.predicted_return_pct) >= 0 ? '+' : ''}${Number(p.predicted_return_pct).toFixed(3)}%</td>
        <td><span class="badge ${dirClass}">${p.predicted_direction}</span></td>
        <td class="num">${Number(p.confidence_pct).toFixed(1)}%</td>
        <td><code>${p.recommended_action}</code></td>
        <td class="num">${fmtInr(p.predicted_take_profit)} / ${fmtInr(p.predicted_stop_loss)}</td>
        <td><span class="badge model">${p.selected_model}</span></td>
        <td class="num">${actClose}</td>
        <td class="num">${absErr}</td>
        <td>${statusLabel}</td>
      </tr>
    `;
  }).join('') || '<tr><td colspan="14">No predictions saved yet.</td></tr>';

  document.getElementById('ml-audit-tbody').innerHTML = latestMl.map(m => {
    const comp = m.model_comparison || {};
    const split = comp.chronological_split || {};
    const tm = comp.test_metrics || {};
    const audit = m.data_audit || {};
    const st = audit.stationarity_audit || {};
    const ci = m.test_mae_ci95 || {low_pct: 0, high_pct: 0};

    const naiveKey = Object.keys(tm).find(k => k.startsWith('Naive')) || '';
    const ridgeKey = Object.keys(tm).find(k => k.startsWith('Ridge')) || '';
    const gbKey = Object.keys(tm).find(k => k.startsWith('Gradient')) || '';

    const naiveM = tm[naiveKey] || {};
    const ridgeM = tm[ridgeKey] || {};
    const gbM = tm[gbKey] || {};

    const nullsBefore = Object.values(audit.null_frequency_before_handling || {}).reduce((a, b) => a + b, 0);
    const nullsAfter = Object.values(audit.null_frequency_after_handling || {}).reduce((a, b) => a + b, 0);

    return `
      <tr>
        <td><strong>${m.symbol}</strong></td>
        <td>${split.train_rows || 0} / ${split.val_rows || 0} / ${split.test_rows || 0}</td>
        <td>${nullsBefore} → ${nullsAfter}</td>
        <td>${st.raw_close_lag1_autocorr} → <strong>${st.return_pct_lag1_autocorr}</strong></td>
        <td class="num">${Number(naiveM.mae_pct || 0).toFixed(3)}%</td>
        <td class="num">${Number(ridgeM.mae_pct || 0).toFixed(3)}% (${Number(ridgeM.directional_accuracy_pct || 0).toFixed(1)}%)</td>
        <td class="num">${Number(gbM.mae_pct || 0).toFixed(3)}% (${Number(gbM.directional_accuracy_pct || 0).toFixed(1)}%)</td>
        <td><span class="badge model">${m.selected_model}</span></td>
        <td class="num">[${Number(ci.low_pct).toFixed(3)}%, ${Number(ci.high_pct).toFixed(3)}%]</td>
      </tr>
    `;
  }).join('') || '<tr><td colspan="9">Run ML training to populate model comparison metrics.</td></tr>';

  const openPos = ledger.open_positions || [];
  document.getElementById('open-pos-count').textContent = `${openPos.length} active position(s)`;
  document.getElementById('open-pos-tbody').innerHTML = openPos.map(p => `
    <tr>
      <td><strong>${p.symbol}</strong></td>
      <td><span class="badge buy">${p.side}</span></td>
      <td class="num">${p.quantity}</td>
      <td class="num">${fmtInr(p.entry_price)}</td>
      <td class="num">${fmtInr(p.current_ltp)}</td>
      <td class="num">${fmtInr(p.stop_loss)}</td>
      <td class="num">${fmtInr(p.take_profit)}</td>
      <td class="num ${p.unrealized_pnl >= 0 ? 'pos' : 'neg'}">${fmtInr(p.unrealized_pnl)}</td>
    </tr>
  `).join('') || '<tr><td colspan="8">No open positions.</td></tr>';

  const snaps = d.watchlist || [];
  if (snaps[0]) document.getElementById('watchlist-ts').textContent = `Latest Bar: ${snaps[0].timestamp}`;
  document.getElementById('watchlist-tbody').innerHTML = snaps.map(s => {
    const ind = s.indicators || {};
    const sig = (s.signal_evaluation || {}).signal || 'HOLD';
    return `
      <tr>
        <td><strong>${s.symbol}</strong></td>
        <td class="num">${fmtInr(s.ltp)}</td>
        <td class="num">${Number(ind.RSI_14).toFixed(2)}</td>
        <td class="num">${Number(ind.EMA_9).toFixed(2)}</td>
        <td class="num">${Number(ind.EMA_21).toFixed(2)}</td>
        <td class="num">${fmtInr(ind.VWAP)}</td>
        <td class="num">${Number(ind.ATR_14).toFixed(2)}</td>
        <td><span class="badge ${sig === 'BUY' ? 'buy' : 'hold'}">${sig}</span></td>
      </tr>
    `;
  }).join('');

  const cfg = d.strategy_config || {};
  document.getElementById('strategy-cfg-box').innerHTML =
    `<code>rsi_buy_threshold=${cfg.rsi_buy_threshold}</code> • ` +
    `<code>rsi_sell_threshold=${cfg.rsi_sell_threshold}</code> • ` +
    `<code>risk_per_trade_pct=${cfg.risk_per_trade_pct}%</code> • ` +
    `<code>stop_loss_pct=${cfg.stop_loss_pct}%</code> • ` +
    `<code>take_profit_pct=${cfg.take_profit_pct}%</code>`;

  document.getElementById('memory-box').textContent = d.memory_md || '';
  document.getElementById('logs-box').textContent = (d.logs && d.logs.system_log ? d.logs.system_log.join('\n') : 'No logs yet.');
}

loadDashboard();
</script>
</body>
</html>
"""


def build_dashboard_payload() -> Dict[str, Any]:
    mlp.ensure_log_dirs_and_tables()
    ledger = ipt.evaluate_open_positions()
    watchlist = [
        ipt.get_market_snapshot(symbol=sym, token=tok, exchange="NSE", interval="FIVE_MINUTE")
        for sym, tok in runner.CORE_WATCHLIST
    ]

    with closing(sqlite3.connect(ipt.DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM daily_predictions ORDER BY id DESC LIMIT 18").fetchall()
        saved_predictions = [dict(r) for r in rows]

    latest_ml_file: Dict[str, Any] = {}
    if mlp.LATEST_PREDICTIONS_PATH.exists():
        try:
            latest_ml_file = json.loads(mlp.LATEST_PREDICTIONS_PATH.read_text(encoding="utf-8"))
        except Exception:
            latest_ml_file = {}

    strategy_cfg = ipt._load_strategy_config()
    memory_md = ipt.MEMORY_MD_PATH.read_text(encoding="utf-8") if ipt.MEMORY_MD_PATH.exists() else ""
    logs = mlp.get_recent_logs(limit=80)

    return {
        "timestamp_ist": ipt._now_ist_iso(),
        "ledger": ledger,
        "watchlist": watchlist,
        "saved_predictions": saved_predictions,
        "latest_ml_file": latest_ml_file,
        "strategy_config": strategy_cfg,
        "memory_md": memory_md,
        "logs": logs,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            index_file = BASE_DIR / "public" / "index.html"
            if index_file.exists():
                body = index_file.read_bytes()
            else:
                body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/admin"):
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/realtime") or self.path.startswith("/live_data.json"):
            self._send_json(rt_export.generate_realtime_payload())
        elif self.path.startswith("/api/dashboard"):
            self._send_json(build_dashboard_payload())
        elif self.path.startswith("/api/logs"):
            self._send_json(mlp.get_recent_logs(limit=120))
        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        if self.path == "/api/run-cycle":
            res = runner.run_direct_cook_cycle(run_ml=True)
            self._send_json({"status": "ok", "result": res})
        elif self.path == "/api/train-predict":
            res = mlp.train_and_predict_watchlist(runner.CORE_WATCHLIST)
            mlp.evaluate_saved_predictions(force_mark_to_market=True)
            self._send_json({"status": "ok", "result": res})
        elif self.path == "/api/verify-predictions":
            res = mlp.evaluate_saved_predictions(force_mark_to_market=True)
            self._send_json({"status": "ok", "result": res})
        else:
            self._send_json({"error": "Unknown endpoint"}, status=404)


def run_smoke_test() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=15) as r_html:
            html_text = r_html.read().decode("utf-8")
            assert r_html.status == 200 and "IndianPaperTrader" in html_text

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/dashboard", timeout=30) as r_api:
            data = json.loads(r_api.read().decode("utf-8"))
            assert r_api.status == 200 and "ledger" in data and "saved_predictions" in data

        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/verify-predictions", method="POST")
        with urllib.request.urlopen(req, timeout=30) as r_ver:
            ver_data = json.loads(r_ver.read().decode("utf-8"))
            assert r_ver.status == 200 and ver_data.get("status") == "ok"

        print(
            f"GUI_SMOKE_TEST_PASS: port={port}, saved_predictions={len(data['saved_predictions'])}, "
            f"verified={ver_data['result']['total_predictions_checked']}"
        )
        return 0
    finally:
        server.shutdown()
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="IndianPaperTrader Web GUI Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser tab.")
    parser.add_argument("--smoke-test", action="store_true", help="Run automated GUI endpoint test and exit.")
    args = parser.parse_args()

    if args.smoke_test:
        return run_smoke_test()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = f"http://{args.host}:{args.port}"
    mlp.log_event(f"GUI Dashboard server listening at {url}")
    print(f"IndianPaperTrader GUI running at {url}")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
