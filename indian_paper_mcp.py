"""
IndianPaperTrader: Zero-Risk FastMCP Server for NSE/BSE Paper Trading.

Structural air-gap guarantee: contains zero real-broker order execution calls.
All simulated executions settle in the local SQLite3 clearinghouse with
0.05% adverse slippage and INR 20.00 flat brokerage per leg.
"""

from __future__ import annotations

import json
import os
import site
import sqlite3
import sys
import time
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

BASE_DIR = Path(__file__).parent.resolve()

# Auto-bootstrap local .venv site-packages (including .pth files like pywin32.pth)
# so `python indian_paper_mcp.py` works even outside an activated virtual environment.
_VENV_DIR = BASE_DIR / ".venv"
if _VENV_DIR.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    _venv_sites = [_VENV_DIR / "Lib" / "site-packages"]
    if (_VENV_DIR / "lib").exists():
        _venv_sites.extend((_VENV_DIR / "lib").glob("python*/site-packages"))
    for _site_dir in _venv_sites:
        if _site_dir.exists():
            _before = set(sys.path)
            site.addsitedir(str(_site_dir))
            _added = [p for p in sys.path if p not in _before]
            if _added:
                sys.path[:] = _added + [p for p in sys.path if p not in _added]

import numpy as np
import pandas as pd
import pyotp
import requests
import yfinance as yf
try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer as FastMCP

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None

mcp = FastMCP("IndianPaperTrader")

DB_PATH = BASE_DIR / "paper_ledger.db"
SCRIP_MASTER_PATH = BASE_DIR / "OpenAPIScripMaster.json"
STRATEGY_CONFIG_PATH = BASE_DIR / "strategy_config.json"
MEMORY_MD_PATH = BASE_DIR / "MEMORY.md"

SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
INITIAL_VIRTUAL_CASH = 100000.00
SLIPPAGE_PCT = 0.0005  # 0.05% adverse execution slippage
FLAT_BROKERAGE = 20.00  # INR 20.00 flat virtual brokerage per leg
MIN_GROSS_PROFIT_HURDLE = 120.00  # 3x INR 40.00 round-trip brokerage (NFR-04)
MIN_RISK_PCT = 2.0  # NFR-03 lower bound
MAX_RISK_PCT = 15.0  # NFR-03 upper bound
IST_TZ = timezone(timedelta(hours=5, minutes=30))

DEFAULT_STRATEGY_CONFIG: Dict[str, Any] = {
    "rsi_buy_threshold": 35,
    "rsi_sell_threshold": 68,
    "ema_fast": 9,
    "ema_slow": 21,
    "stop_loss_pct": 1.2,
    "take_profit_pct": 2.5,
    "risk_per_trade_pct": 10.0,
    "updated_at": datetime.now(IST_TZ).isoformat(),
}

# Offline fallback master for core Nifty 50 liquid equities
CORE_NIFTY50_SCRIPS: List[Dict[str, str]] = [
    {"symbol": "RELIANCE-EQ", "name": "RELIANCE", "token": "2885", "exch_seg": "NSE"},
    {"symbol": "TCS-EQ", "name": "TCS", "token": "11536", "exch_seg": "NSE"},
    {"symbol": "HDFCBANK-EQ", "name": "HDFCBANK", "token": "1333", "exch_seg": "NSE"},
    {"symbol": "INFY-EQ", "name": "INFY", "token": "1594", "exch_seg": "NSE"},
    {"symbol": "ICICIBANK-EQ", "name": "ICICIBANK", "token": "4963", "exch_seg": "NSE"},
    {"symbol": "SBIN-EQ", "name": "SBIN", "token": "3045", "exch_seg": "NSE"},
    {"symbol": "BHARTIARTL-EQ", "name": "BHARTIARTL", "token": "10604", "exch_seg": "NSE"},
    {"symbol": "ITC-EQ", "name": "ITC", "token": "1660", "exch_seg": "NSE"},
    {"symbol": "LT-EQ", "name": "LT", "token": "11483", "exch_seg": "NSE"},
    {"symbol": "AXISBANK-EQ", "name": "AXISBANK", "token": "5900", "exch_seg": "NSE"},
    {"symbol": "KOTAKBANK-EQ", "name": "KOTAKBANK", "token": "1922", "exch_seg": "NSE"},
    {"symbol": "HINDUNILVR-EQ", "name": "HINDUNILVR", "token": "1394", "exch_seg": "NSE"},
    {"symbol": "SUNPHARMA-EQ", "name": "SUNPHARMA", "token": "3351", "exch_seg": "NSE"},
    {"symbol": "MARUTI-EQ", "name": "MARUTI", "token": "10999", "exch_seg": "NSE"},
    {"symbol": "NTPC-EQ", "name": "NTPC", "token": "11630", "exch_seg": "NSE"},
    {"symbol": "BAJFINANCE-EQ", "name": "BAJFINANCE", "token": "317", "exch_seg": "NSE"},
    {"symbol": "WIPRO-EQ", "name": "WIPRO", "token": "3787", "exch_seg": "NSE"},
    {"symbol": "ASIANPAINT-EQ", "name": "ASIANPAINT", "token": "236", "exch_seg": "NSE"},
    {"symbol": "TITAN-EQ", "name": "TITAN", "token": "3506", "exch_seg": "NSE"},
    {"symbol": "TATAMOTORS-EQ", "name": "TATAMOTORS", "token": "3456", "exch_seg": "NSE"},
]


def _now_ist_iso() -> str:
    return datetime.now(IST_TZ).isoformat(timespec="seconds")


def _load_strategy_config() -> Dict[str, Any]:
    if not STRATEGY_CONFIG_PATH.exists():
        cfg = dict(DEFAULT_STRATEGY_CONFIG)
        cfg["updated_at"] = _now_ist_iso()
        STRATEGY_CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return cfg

    try:
        raw = json.loads(STRATEGY_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raw = {}

    cfg = dict(DEFAULT_STRATEGY_CONFIG)
    cfg.update(raw)
    cfg["risk_per_trade_pct"] = float(
        min(MAX_RISK_PCT, max(MIN_RISK_PCT, float(cfg.get("risk_per_trade_pct", 10.0))))
    )
    return cfg


def init_environment(reset: bool = False) -> None:
    """Initializes SQLite tables, strategy_config.json, and MEMORY.md."""
    now_iso = _now_ist_iso()

    if reset or not STRATEGY_CONFIG_PATH.exists():
        cfg = dict(DEFAULT_STRATEGY_CONFIG)
        cfg["updated_at"] = now_iso
        STRATEGY_CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    else:
        cfg = _load_strategy_config()
        STRATEGY_CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    if reset or not MEMORY_MD_PATH.exists():
        MEMORY_MD_PATH.write_text(
            "# Autonomous Quantitative Strategy Memory\n\n"
            "## Post-Trade Reflections & Parameter Updates\n",
            encoding="utf-8",
        )

    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        if reset:
            for tbl in ("ledger", "open_positions", "closed_trades", "strategy_reflections", "account"):
                cursor.execute(f"DROP TABLE IF EXISTS {tbl}")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                virtual_cash REAL NOT NULL,
                realized_pnl REAL NOT NULL DEFAULT 0.0,
                total_brokerage_paid REAL NOT NULL DEFAULT 0.0,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS open_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                token TEXT NOT NULL,
                exchange TEXT NOT NULL DEFAULT 'NSE',
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                raw_ltp REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                entry_brokerage REAL NOT NULL,
                rationale TEXT,
                opened_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS closed_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER,
                symbol TEXT NOT NULL,
                token TEXT NOT NULL,
                exchange TEXT NOT NULL DEFAULT 'NSE',
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                gross_pnl REAL NOT NULL,
                total_brokerage REAL NOT NULL,
                net_pnl REAL NOT NULL,
                exit_reason TEXT NOT NULL,
                rationale TEXT,
                opened_at TEXT NOT NULL,
                closed_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_learned TEXT NOT NULL,
                old_config_json TEXT NOT NULL,
                new_config_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            INSERT OR IGNORE INTO account (id, virtual_cash, realized_pnl, total_brokerage_paid, updated_at)
            VALUES (1, ?, 0.0, 0.0, ?)
            """,
            (INITIAL_VIRTUAL_CASH, now_iso),
        )
        conn.commit()


@contextmanager
def _get_conn() -> Iterator[sqlite3.Connection]:
    init_environment(reset=False)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class ReadOnlyMarketClient:
    """
    L1 Telemetry Layer: Read-only market data client.

    Never imports or wraps real-broker order endpoints. Supports Angel One SmartAPI
    via dynamic pyotp TOTP authentication with automatic failover to yfinance (.NS/.BO).
    """

    def __init__(self) -> None:
        self._smart_api: Optional[Any] = None
        self._auth_attempted: bool = False
        self._scrip_records: Optional[List[Dict[str, str]]] = None
        self._bar_cache: Dict[Tuple[str, str, str, int], Tuple[float, pd.DataFrame, str]] = {}

    @staticmethod
    def _is_valid_env(val: Optional[str]) -> bool:
        return bool(val and not val.startswith("${") and val.strip())

    def _ensure_smartapi_session(self) -> Optional[Any]:
        if self._auth_attempted:
            return self._smart_api
        self._auth_attempted = True

        if SmartConnect is None:
            return None

        api_key = os.environ.get("ANGEL_API_KEY")
        client_id = os.environ.get("ANGEL_CLIENT_ID")
        pin = os.environ.get("ANGEL_PIN")
        totp_secret = os.environ.get("ANGEL_TOTP_SECRET")

        if not all(self._is_valid_env(v) for v in (api_key, client_id, pin, totp_secret)):
            return None

        try:
            client = SmartConnect(api_key=api_key)
            totp_code = pyotp.TOTP(totp_secret).now()
            resp = client.generateSession(client_id, pin, totp_code)
            if isinstance(resp, dict) and resp.get("status"):
                self._smart_api = client
        except Exception:
            self._smart_api = None
        return self._smart_api

    def _load_scrip_records(self) -> List[Dict[str, str]]:
        if self._scrip_records is not None:
            return self._scrip_records

        needs_refresh = True
        if SCRIP_MASTER_PATH.exists():
            age_secs = time.time() - SCRIP_MASTER_PATH.stat().st_mtime
            if age_secs < 86400:  # 24h TTL
                needs_refresh = False

        if needs_refresh:
            try:
                resp = requests.get(SCRIP_MASTER_URL, timeout=8)
                if resp.status_code == 200 and resp.text.strip().startswith("["):
                    SCRIP_MASTER_PATH.write_text(resp.text, encoding="utf-8")
            except Exception:
                pass

        records: List[Dict[str, str]] = []
        if SCRIP_MASTER_PATH.exists():
            try:
                raw_list = json.loads(SCRIP_MASTER_PATH.read_text(encoding="utf-8"))
                for item in raw_list:
                    exch = str(item.get("exch_seg", "")).upper()
                    sym = str(item.get("symbol", "")).upper()
                    if exch in ("NSE", "BSE") and (exch == "BSE" or sym.endswith("-EQ")):
                        records.append(
                            {
                                "symbol": sym,
                                "name": str(item.get("name", "")).upper(),
                                "token": str(item.get("token", "")),
                                "exch_seg": exch,
                            }
                        )
            except Exception:
                records = []

        if not records:
            records = list(CORE_NIFTY50_SCRIPS)

        self._scrip_records = records
        return self._scrip_records

    def search_scrip(self, query: str, exchange: str = "NSE", limit: int = 10) -> List[Dict[str, str]]:
        q = query.strip().upper()
        exch_filter = exchange.strip().upper() if exchange else ""
        if not q:
            return []

        records = self._load_scrip_records()
        exact_matches: List[Dict[str, str]] = []
        prefix_matches: List[Dict[str, str]] = []
        partial_matches: List[Dict[str, str]] = []

        q_eq = q if q.endswith("-EQ") else f"{q}-EQ"
        for rec in records:
            if exch_filter and rec["exch_seg"] != exch_filter:
                continue
            sym = rec["symbol"]
            name = rec["name"]
            if sym == q or sym == q_eq or name == q:
                exact_matches.append(rec)
            elif sym.startswith(q) or name.startswith(q):
                prefix_matches.append(rec)
            elif q in sym or q in name:
                partial_matches.append(rec)

        combined = exact_matches + prefix_matches + partial_matches
        return combined[:limit]

    @staticmethod
    def to_yfinance_ticker(symbol: str, exchange: str = "NSE") -> str:
        clean = symbol.strip().upper()
        for suffix in ("-EQ", "-BE", "-BL", "-SM", "-BZ"):
            if clean.endswith(suffix):
                clean = clean[: -len(suffix)]
                break
        if clean.endswith(".NS") or clean.endswith(".BO"):
            return clean
        ext = ".BO" if exchange.strip().upper() == "BSE" else ".NS"
        return f"{clean}{ext}"

    @staticmethod
    def _normalize_ohlcv_df(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        out = df.copy()
        if isinstance(out.columns, pd.MultiIndex):
            out.columns = out.columns.get_level_values(0)

        col_map = {str(c).lower(): c for c in out.columns}
        required = {}
        for target in ("open", "high", "low", "close", "volume"):
            if target in col_map:
                required[col_map[target]] = target.capitalize()
        if len(required) < 4:
            return pd.DataFrame()

        out = out[list(required.keys())].rename(columns=required)
        if "Volume" not in out.columns:
            out["Volume"] = 0.0

        for col in ("Open", "High", "Low", "Close", "Volume"):
            out[col] = pd.to_numeric(out[col], errors="coerce")
        out = out.dropna(subset=["Open", "High", "Low", "Close"])
        out["Volume"] = out["Volume"].fillna(0.0)

        if not isinstance(out.index, pd.DatetimeIndex):
            out.index = pd.to_datetime(out.index)
        if out.index.tz is None:
            out.index = out.index.tz_localize(IST_TZ)
        else:
            out.index = out.index.tz_convert(IST_TZ)
        return out.sort_index()

    def _fetch_smartapi_candles(
        self, token: str, exchange: str, interval: str, days: int
    ) -> Optional[pd.DataFrame]:
        api = self._ensure_smartapi_session()
        if api is None:
            return None

        now_ist = datetime.now(IST_TZ)
        from_ist = now_ist - timedelta(days=days)
        try:
            resp = api.getCandleData(
                {
                    "exchange": exchange.upper(),
                    "symboltoken": str(token),
                    "interval": interval,
                    "fromdate": from_ist.strftime("%Y-%m-%d 09:15"),
                    "todate": now_ist.strftime("%Y-%m-%d %H:%M"),
                }
            )
            if isinstance(resp, dict) and resp.get("status") and resp.get("data"):
                raw = pd.DataFrame(
                    resp["data"], columns=["Datetime", "Open", "High", "Low", "Close", "Volume"]
                )
                raw["Datetime"] = pd.to_datetime(raw["Datetime"])
                raw = raw.set_index("Datetime")
                df = self._normalize_ohlcv_df(raw)
                if not df.empty:
                    return df
        except Exception:
            return None
        return None

    def _fetch_yfinance_candles(
        self, symbol: str, exchange: str, interval: str, days: int
    ) -> Optional[pd.DataFrame]:
        yf_interval = "5m" if interval.upper() in ("FIVE_MINUTE", "5M", "5MIN") else "5m"
        period_days = min(max(int(days), 5), 59)
        ticker_sym = self.to_yfinance_ticker(symbol, exchange)
        try:
            hist = yf.Ticker(ticker_sym).history(
                period=f"{period_days}d", interval=yf_interval, auto_adjust=True
            )
            df = self._normalize_ohlcv_df(hist)
            if not df.empty:
                return df
        except Exception:
            return None
        return None

    @staticmethod
    def _synthetic_fallback_candles(symbol: str, days: int) -> pd.DataFrame:
        seed = abs(hash(symbol)) % (2**31)
        rng = np.random.default_rng(seed)
        bars_per_day = 75
        total_bars = max(days * bars_per_day, 100)
        base_price = 1000.0 + (seed % 2500)

        returns = rng.normal(loc=0.00005, scale=0.0022, size=total_bars)
        closes = base_price * np.cumprod(1.0 + returns)
        opens = np.concatenate([[base_price], closes[:-1]])
        spread = np.abs(rng.normal(0.0012, 0.0006, size=total_bars)) * closes
        highs = np.maximum(opens, closes) + spread
        lows = np.minimum(opens, closes) - spread
        volumes = rng.integers(15000, 120000, size=total_bars).astype(float)

        end_dt = datetime.now(IST_TZ).replace(hour=15, minute=25, second=0, microsecond=0)
        timestamps: List[datetime] = []
        cur_day = end_dt.date()
        while len(timestamps) < total_bars:
            if cur_day.weekday() < 5:
                day_start = datetime(cur_day.year, cur_day.month, cur_day.day, 9, 15, tzinfo=IST_TZ)
                day_bars = [day_start + timedelta(minutes=5 * i) for i in range(bars_per_day)]
                timestamps = day_bars + timestamps
            cur_day -= timedelta(days=1)
        timestamps = timestamps[-total_bars:]

        return pd.DataFrame(
            {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
            index=pd.DatetimeIndex(timestamps),
        )

    def fetch_candles(
        self,
        symbol: str,
        token: str,
        exchange: str = "NSE",
        interval: str = "FIVE_MINUTE",
        days: int = 5,
    ) -> Tuple[pd.DataFrame, str]:
        cache_key = (symbol.upper(), exchange.upper(), interval.upper(), int(days))
        cached = self._bar_cache.get(cache_key)
        if cached is not None:
            ts, df_cached, src_cached = cached
            if time.time() - ts < 60.0 and not df_cached.empty:
                return df_cached.copy(), src_cached

        df = self._fetch_smartapi_candles(token, exchange, interval, days)
        source = "angel_one_smartapi"
        if df is None or df.empty:
            df = self._fetch_yfinance_candles(symbol, exchange, interval, days)
            source = f"yfinance:{self.to_yfinance_ticker(symbol, exchange)}"
        if df is None or df.empty:
            df = self._synthetic_fallback_candles(symbol, days)
            source = "synthetic_offline_fallback"

        self._bar_cache[cache_key] = (time.time(), df.copy(), source)
        return df, source

    def fetch_ltp(self, symbol: str, token: str, exchange: str = "NSE") -> Tuple[float, str]:
        api = self._ensure_smartapi_session()
        if api is not None:
            try:
                resp = api.ltpData(exchange.upper(), symbol, str(token))
                if isinstance(resp, dict) and resp.get("status") and resp.get("data"):
                    ltp_val = float(resp["data"].get("ltp", 0.0))
                    if ltp_val > 0:
                        return round(ltp_val, 2), "angel_one_smartapi"
            except Exception:
                pass

        df, source = self.fetch_candles(symbol, token, exchange=exchange, interval="FIVE_MINUTE", days=5)
        return round(float(df["Close"].iloc[-1]), 2), source


market_client = ReadOnlyMarketClient()


def add_indicator_columns(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    L2 Quant Signal Engine: Vectorized technical indicator computation.

    Computes Wilder's RSI (14), EMA fast/slow (9 & 21), intraday session-anchored VWAP,
    and Wilder's ATR (14) cleanly without LLM arithmetic on raw arrays.
    """
    cfg = config or _load_strategy_config()
    ema_fast_span = int(cfg.get("ema_fast", 9))
    ema_slow_span = int(cfg.get("ema_slow", 21))

    out = df.copy()
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    volume = out["Volume"].astype(float)

    # Wilder's RSI (alpha = 1/14)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = np.where((avg_loss == 0.0) & (avg_gain > 0.0), 100.0, rsi)
    rsi = np.where((avg_loss == 0.0) & (avg_gain == 0.0), 50.0, rsi)
    out["RSI_14"] = pd.Series(rsi, index=out.index).bfill().fillna(50.0)

    # Fast and Slow EMAs
    out["EMA_9"] = close.ewm(span=ema_fast_span, adjust=False).mean()
    out["EMA_21"] = close.ewm(span=ema_slow_span, adjust=False).mean()

    # Session-anchored Intraday VWAP
    typical_price = (high + low + close) / 3.0
    session_dates = out.index.date
    tp_vol = (typical_price * volume).groupby(session_dates).cumsum()
    cum_vol = volume.groupby(session_dates).cumsum()
    out["VWAP"] = np.where(cum_vol > 0.0, tp_vol / cum_vol, typical_price)

    # Wilder's ATR (14)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["ATR_14"] = tr.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean().bfill()
    return out


def compute_indicators(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Computes latest RSI_14, EMA_9, EMA_21, session VWAP, and ATR_14 over trailing bars."""
    window = df.tail(max(50, len(df))) if len(df) <= 200 else df.tail(200)
    enriched = add_indicator_columns(window, config=config)
    latest = enriched.iloc[-1]
    return {
        "RSI_14": round(float(latest["RSI_14"]), 2),
        "EMA_9": round(float(latest["EMA_9"]), 2),
        "EMA_21": round(float(latest["EMA_21"]), 2),
        "VWAP": round(float(latest["VWAP"]), 2),
        "ATR_14": round(float(latest["ATR_14"]), 2),
    }


def evaluate_long_setup(
    ltp: float, indicators: Dict[str, float], cfg: Dict[str, Any], virtual_cash: float
) -> Dict[str, Any]:
    """Evaluates whether an equity snapshot satisfies active strategy entry & edge hurdle rules."""
    rsi = float(indicators["RSI_14"])
    ema_9 = float(indicators["EMA_9"])
    ema_21 = float(indicators["EMA_21"])
    vwap = float(indicators["VWAP"])
    atr = float(indicators["ATR_14"])

    rsi_buy = float(cfg.get("rsi_buy_threshold", 35))
    rsi_sell = float(cfg.get("rsi_sell_threshold", 68))
    sl_pct = float(cfg.get("stop_loss_pct", 1.2))
    tp_pct = float(cfg.get("take_profit_pct", 2.5))
    risk_pct = float(cfg.get("risk_per_trade_pct", 10.0))

    mean_reversion_trigger = rsi <= rsi_buy and ltp >= vwap * 0.995
    trend_momentum_trigger = ema_9 > ema_21 and ltp > vwap and rsi < (rsi_sell - 8.0)

    capital_to_deploy = virtual_cash * (risk_pct / 100.0)
    quantity = int(capital_to_deploy // ltp) if ltp > 0 else 0
    stop_loss = round(ltp - max(1.5 * atr, ltp * (sl_pct / 100.0)), 2)
    take_profit = round(ltp + max(2.5 * atr, ltp * (tp_pct / 100.0)), 2)

    est_fill = round(ltp * (1.0 + SLIPPAGE_PCT), 2)
    projected_gross_profit = round((take_profit - est_fill) * quantity, 2)
    meets_hurdle = quantity >= 1 and projected_gross_profit >= MIN_GROSS_PROFIT_HURDLE

    if mean_reversion_trigger:
        setup_type = "MEAN_REVERSION_BUY"
    elif trend_momentum_trigger:
        setup_type = "MOMENTUM_BUY"
    else:
        setup_type = "NONE"

    signal = "BUY" if (mean_reversion_trigger or trend_momentum_trigger) and meets_hurdle else "HOLD"
    return {
        "signal": signal,
        "setup_type": setup_type,
        "trigger_matched": bool(mean_reversion_trigger or trend_momentum_trigger),
        "meets_edge_hurdle": meets_hurdle,
        "suggested_quantity": quantity,
        "suggested_stop_loss": stop_loss,
        "suggested_take_profit": take_profit,
        "projected_gross_profit_inr": projected_gross_profit,
    }


def _apply_slippage(ltp: float, side: str, is_entry: bool) -> float:
    side_u = side.upper()
    if (side_u == "BUY" and is_entry) or (side_u == "SELL" and not is_entry):
        return round(ltp * (1.0 + SLIPPAGE_PCT), 2)
    return round(ltp * (1.0 - SLIPPAGE_PCT), 2)


def _close_position_in_db(
    cursor: sqlite3.Cursor, pos: sqlite3.Row, exit_ltp: float, exit_reason: str
) -> Dict[str, Any]:
    side = str(pos["side"]).upper()
    qty = int(pos["quantity"])
    entry_price = float(pos["entry_price"])
    entry_brok = float(pos["entry_brokerage"])
    exit_price = _apply_slippage(exit_ltp, side, is_entry=False)

    if side == "BUY":
        gross_pnl = round((exit_price - entry_price) * qty, 2)
        cash_credit = round(exit_price * qty - FLAT_BROKERAGE, 2)
    else:
        gross_pnl = round((entry_price - exit_price) * qty, 2)
        cash_credit = round(entry_price * qty + gross_pnl - FLAT_BROKERAGE, 2)

    total_brokerage = round(entry_brok + FLAT_BROKERAGE, 2)
    net_pnl = round(gross_pnl - total_brokerage, 2)
    closed_at = _now_ist_iso()

    cursor.execute(
        """
        INSERT INTO closed_trades (
            position_id, symbol, token, exchange, side, quantity,
            entry_price, exit_price, stop_loss, take_profit,
            gross_pnl, total_brokerage, net_pnl, exit_reason, rationale,
            opened_at, closed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pos["id"],
            pos["symbol"],
            pos["token"],
            pos["exchange"],
            side,
            qty,
            entry_price,
            exit_price,
            float(pos["stop_loss"]),
            float(pos["take_profit"]),
            gross_pnl,
            total_brokerage,
            net_pnl,
            exit_reason,
            pos["rationale"],
            pos["opened_at"],
            closed_at,
        ),
    )
    cursor.execute("DELETE FROM open_positions WHERE id = ?", (pos["id"],))
    cursor.execute(
        """
        UPDATE account
        SET virtual_cash = ROUND(virtual_cash + ?, 2),
            realized_pnl = ROUND(realized_pnl + ?, 2),
            total_brokerage_paid = ROUND(total_brokerage_paid + ?, 2),
            updated_at = ?
        WHERE id = 1
        """,
        (cash_credit, net_pnl, FLAT_BROKERAGE, closed_at),
    )
    return {
        "position_id": pos["id"],
        "symbol": pos["symbol"],
        "side": side,
        "quantity": qty,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "gross_pnl": gross_pnl,
        "total_brokerage": total_brokerage,
        "net_pnl": net_pnl,
        "exit_reason": exit_reason,
        "closed_at": closed_at,
    }


@mcp.tool()
def search_nse_bse_scrip(query: str, exchange: str = "NSE") -> List[Dict[str, str]]:
    """
    Search Angel One NSE/BSE instrument master (24h cached OpenAPIScripMaster.json
    with offline Nifty 50 fallback) and resolve trading symbol + token.
    """
    return market_client.search_scrip(query=query, exchange=exchange)


@mcp.tool()
def get_market_snapshot(
    symbol: str, token: str, exchange: str = "NSE", interval: str = "FIVE_MINUTE"
) -> Dict[str, Any]:
    """
    Fetch live or fallback 5-minute OHLCV candles, compute RSI_14, EMA_9, EMA_21,
    session VWAP, and ATR_14, and evaluate against active strategy thresholds.
    """
    df, data_source = market_client.fetch_candles(
        symbol=symbol, token=token, exchange=exchange, interval=interval, days=5
    )
    cfg = _load_strategy_config()
    indicators = compute_indicators(df, config=cfg)

    latest_bar = df.iloc[-1]
    ltp = round(float(latest_bar["Close"]), 2)

    with _get_conn() as conn:
        acct = conn.execute("SELECT virtual_cash FROM account WHERE id = 1").fetchone()
        virtual_cash = float(acct["virtual_cash"]) if acct else INITIAL_VIRTUAL_CASH

    setup = evaluate_long_setup(ltp=ltp, indicators=indicators, cfg=cfg, virtual_cash=virtual_cash)

    return {
        "symbol": symbol.upper(),
        "token": str(token),
        "exchange": exchange.upper(),
        "interval": interval,
        "data_source": data_source,
        "timestamp": df.index[-1].isoformat(),
        "ltp": ltp,
        "ohlcv": {
            "open": round(float(latest_bar["Open"]), 2),
            "high": round(float(latest_bar["High"]), 2),
            "low": round(float(latest_bar["Low"]), 2),
            "close": ltp,
            "volume": int(latest_bar["Volume"]),
        },
        "indicators": indicators,
        "active_strategy_thresholds": {
            "rsi_buy_threshold": cfg["rsi_buy_threshold"],
            "rsi_sell_threshold": cfg["rsi_sell_threshold"],
            "ema_fast": cfg["ema_fast"],
            "ema_slow": cfg["ema_slow"],
            "stop_loss_pct": cfg["stop_loss_pct"],
            "take_profit_pct": cfg["take_profit_pct"],
            "risk_per_trade_pct": cfg["risk_per_trade_pct"],
        },
        "signal_evaluation": setup,
    }


@mcp.tool()
def place_paper_order(
    symbol: str,
    token: str,
    side: str,
    quantity: int,
    ltp: float,
    stop_loss: float,
    take_profit: float,
    rationale: str = "",
    exchange: str = "NSE",
) -> Dict[str, Any]:
    """
    Execute a simulated paper order inside SQLite with 0.05% adverse slippage,
    INR 20.00 brokerage, strict SL/TP bounds validation, and INR 120.00 min edge hurdle.
    """
    side_u = side.strip().upper()
    if side_u not in ("BUY", "SELL"):
        return {"status": "REJECTED", "reason": f"Invalid side '{side}'. Must be BUY or SELL."}
    if int(quantity) < 1 or float(ltp) <= 0:
        return {"status": "REJECTED", "reason": "Quantity must be >= 1 and LTP must be > 0."}

    qty = int(quantity)
    raw_ltp = round(float(ltp), 2)
    sl = round(float(stop_loss), 2)
    tp = round(float(take_profit), 2)
    fill_price = _apply_slippage(raw_ltp, side_u, is_entry=True)

    if side_u == "BUY" and not (sl < fill_price < tp):
        return {
            "status": "REJECTED",
            "reason": f"Invalid BUY bounds: required stop_loss ({sl}) < fill ({fill_price}) < take_profit ({tp}).",
        }
    if side_u == "SELL" and not (tp < fill_price < sl):
        return {
            "status": "REJECTED",
            "reason": f"Invalid SELL bounds: required take_profit ({tp}) < fill ({fill_price}) < stop_loss ({sl}).",
        }

    projected_gross_profit = round(abs(tp - fill_price) * qty, 2)
    if projected_gross_profit < MIN_GROSS_PROFIT_HURDLE:
        return {
            "status": "REJECTED",
            "reason": (
                f"Projected gross profit ₹{projected_gross_profit:.2f} is below "
                f"minimum edge hurdle ₹{MIN_GROSS_PROFIT_HURDLE:.2f} (3x round-trip brokerage)."
            ),
        }

    required_cash = round(fill_price * qty + FLAT_BROKERAGE, 2)
    now_iso = _now_ist_iso()

    with _get_conn() as conn:
        cursor = conn.cursor()
        acct = cursor.execute("SELECT virtual_cash FROM account WHERE id = 1").fetchone()
        virtual_cash = float(acct["virtual_cash"])
        if required_cash > virtual_cash:
            return {
                "status": "REJECTED",
                "reason": f"Insufficient virtual cash: required ₹{required_cash:.2f}, available ₹{virtual_cash:.2f}.",
            }

        cursor.execute(
            """
            INSERT INTO open_positions (
                symbol, token, exchange, side, quantity, entry_price, raw_ltp,
                stop_loss, take_profit, entry_brokerage, rationale, opened_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol.upper(),
                str(token),
                exchange.upper(),
                side_u,
                qty,
                fill_price,
                raw_ltp,
                sl,
                tp,
                FLAT_BROKERAGE,
                rationale,
                now_iso,
            ),
        )
        pos_id = cursor.lastrowid
        cursor.execute(
            """
            UPDATE account
            SET virtual_cash = ROUND(virtual_cash - ?, 2),
                total_brokerage_paid = ROUND(total_brokerage_paid + ?, 2),
                updated_at = ?
            WHERE id = 1
            """,
            (required_cash, FLAT_BROKERAGE, now_iso),
        )
        conn.commit()
        new_cash = round(virtual_cash - required_cash, 2)

    return {
        "status": "FILLED",
        "position_id": pos_id,
        "symbol": symbol.upper(),
        "token": str(token),
        "exchange": exchange.upper(),
        "side": side_u,
        "quantity": qty,
        "raw_ltp": raw_ltp,
        "fill_price": fill_price,
        "slippage_pct": SLIPPAGE_PCT * 100.0,
        "brokerage_inr": FLAT_BROKERAGE,
        "stop_loss": sl,
        "take_profit": tp,
        "projected_gross_profit_inr": projected_gross_profit,
        "remaining_virtual_cash": new_cash,
        "opened_at": now_iso,
    }


@mcp.tool()
def evaluate_open_positions() -> Dict[str, Any]:
    """
    Sweep all open positions against live LTP, auto-close STOP_LOSS_HIT or
    TAKE_PROFIT_HIT positions, credit net proceeds, and return portfolio ledger state.
    """
    auto_closed: List[Dict[str, Any]] = []
    remaining_positions: List[Dict[str, Any]] = []
    total_unrealized = 0.0
    total_open_market_value = 0.0

    with _get_conn() as conn:
        cursor = conn.cursor()
        positions = cursor.execute("SELECT * FROM open_positions ORDER BY id ASC").fetchall()

        for pos in positions:
            ltp, src = market_client.fetch_ltp(pos["symbol"], pos["token"], pos["exchange"])
            side = str(pos["side"]).upper()
            sl = float(pos["stop_loss"])
            tp = float(pos["take_profit"])

            hit_reason: Optional[str] = None
            if side == "BUY":
                if ltp <= sl:
                    hit_reason = "STOP_LOSS_HIT"
                elif ltp >= tp:
                    hit_reason = "TAKE_PROFIT_HIT"
            else:
                if ltp >= sl:
                    hit_reason = "STOP_LOSS_HIT"
                elif ltp <= tp:
                    hit_reason = "TAKE_PROFIT_HIT"

            if hit_reason is not None:
                auto_closed.append(_close_position_in_db(cursor, pos, ltp, hit_reason))
            else:
                qty = int(pos["quantity"])
                entry = float(pos["entry_price"])
                unrealized = round((ltp - entry) * qty if side == "BUY" else (entry - ltp) * qty, 2)
                total_unrealized += unrealized
                total_open_market_value += round(ltp * qty, 2)
                remaining_positions.append(
                    {
                        "id": pos["id"],
                        "symbol": pos["symbol"],
                        "token": pos["token"],
                        "side": side,
                        "quantity": qty,
                        "entry_price": entry,
                        "current_ltp": ltp,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "unrealized_pnl": unrealized,
                        "data_source": src,
                        "opened_at": pos["opened_at"],
                    }
                )

        conn.commit()
        acct = cursor.execute("SELECT * FROM account WHERE id = 1").fetchone()
        closed_count = int(cursor.execute("SELECT COUNT(*) FROM closed_trades").fetchone()[0])

    virtual_cash = round(float(acct["virtual_cash"]), 2)
    realized_pnl = round(float(acct["realized_pnl"]), 2)
    total_brokerage_paid = round(float(acct["total_brokerage_paid"]), 2)
    total_unrealized = round(total_unrealized, 2)
    total_equity = round(virtual_cash + total_open_market_value, 2)

    return {
        "virtual_cash": virtual_cash,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": total_unrealized,
        "total_brokerage_paid": total_brokerage_paid,
        "total_equity": total_equity,
        "total_closed_trades": closed_count,
        "open_positions": remaining_positions,
        "auto_closed": auto_closed,
    }


@mcp.tool()
def run_historical_replay_sim(
    symbol: str, token: str, days: int = 15, exchange: str = "NSE"
) -> Dict[str, Any]:
    """
    Simulate active strategy_config.json rules across `days` (default 15) of
    5-minute historical bars with 0.05% slippage and INR 20.00 brokerage per leg.
    """
    cfg = _load_strategy_config()
    fetch_days = max(int(days) + 4, 20)
    raw_df, data_source = market_client.fetch_candles(
        symbol=symbol, token=token, exchange=exchange, interval="FIVE_MINUTE", days=fetch_days
    )
    enriched = add_indicator_columns(raw_df, config=cfg)

    unique_dates = sorted(set(enriched.index.date))
    target_dates = set(unique_dates[-int(days) :]) if len(unique_dates) > int(days) else set(unique_dates)
    sim_df = enriched[[d in target_dates for d in enriched.index.date]]
    if sim_df.empty:
        sim_df = enriched

    sim_cash = INITIAL_VIRTUAL_CASH
    peak_equity = INITIAL_VIRTUAL_CASH
    max_drawdown_pct = 0.0
    total_brokerage = 0.0
    trades: List[Dict[str, Any]] = []
    open_pos: Optional[Dict[str, Any]] = None

    sim_index = sim_df.index
    n_bars = len(sim_df)

    for i in range(n_bars):
        row = sim_df.iloc[i]
        ts = sim_index[i]
        bar_open = float(row["Open"])
        bar_high = float(row["High"])
        bar_low = float(row["Low"])
        bar_close = float(row["Close"])

        is_last_bar = i == n_bars - 1
        next_date = sim_index[i + 1].date() if not is_last_bar else None
        is_eod_bar = is_last_bar or (next_date != ts.date()) or (ts.hour == 15 and ts.minute >= 20)

        if open_pos is not None:
            exit_raw: Optional[float] = None
            exit_reason: Optional[str] = None

            if bar_low <= open_pos["stop_loss"]:
                exit_raw = min(bar_open, open_pos["stop_loss"])
                exit_reason = "STOP_LOSS_HIT"
            elif bar_high >= open_pos["take_profit"]:
                exit_raw = max(bar_open, open_pos["take_profit"])
                exit_reason = "TAKE_PROFIT_HIT"
            elif is_eod_bar:
                exit_raw = bar_close
                exit_reason = "EOD_SQUAREOFF"

            if exit_raw is not None and exit_reason is not None:
                qty = open_pos["quantity"]
                exit_fill = _apply_slippage(exit_raw, "BUY", is_entry=False)
                gross_pnl = round((exit_fill - open_pos["entry_price"]) * qty, 2)
                trade_brok = round(FLAT_BROKERAGE * 2.0, 2)
                net_pnl = round(gross_pnl - trade_brok, 2)
                sim_cash = round(sim_cash + (exit_fill * qty - FLAT_BROKERAGE), 2)
                total_brokerage = round(total_brokerage + FLAT_BROKERAGE, 2)

                trades.append(
                    {
                        "entry_time": open_pos["entry_time"],
                        "exit_time": ts.isoformat(),
                        "entry_price": open_pos["entry_price"],
                        "exit_price": exit_fill,
                        "quantity": qty,
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_pnl,
                        "exit_reason": exit_reason,
                    }
                )
                open_pos = None
        elif not is_eod_bar:
            indicators = {
                "RSI_14": round(float(row["RSI_14"]), 2),
                "EMA_9": round(float(row["EMA_9"]), 2),
                "EMA_21": round(float(row["EMA_21"]), 2),
                "VWAP": round(float(row["VWAP"]), 2),
                "ATR_14": round(float(row["ATR_14"]), 2),
            }
            setup = evaluate_long_setup(ltp=bar_close, indicators=indicators, cfg=cfg, virtual_cash=sim_cash)
            if setup["signal"] == "BUY":
                qty = setup["suggested_quantity"]
                entry_fill = _apply_slippage(bar_close, "BUY", is_entry=True)
                sl = setup["suggested_stop_loss"]
                tp = setup["suggested_take_profit"]
                cost = round(entry_fill * qty + FLAT_BROKERAGE, 2)
                if sl < entry_fill < tp and cost <= sim_cash:
                    sim_cash = round(sim_cash - cost, 2)
                    total_brokerage = round(total_brokerage + FLAT_BROKERAGE, 2)
                    open_pos = {
                        "entry_time": ts.isoformat(),
                        "entry_price": entry_fill,
                        "quantity": qty,
                        "stop_loss": sl,
                        "take_profit": tp,
                    }

        mtm_equity = sim_cash + (bar_close * open_pos["quantity"] if open_pos is not None else 0.0)
        if mtm_equity > peak_equity:
            peak_equity = mtm_equity
        if peak_equity > 0:
            dd_pct = ((peak_equity - mtm_equity) / peak_equity) * 100.0
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct

    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t["net_pnl"] > 0)
    losing_trades = sum(1 for t in trades if t["net_pnl"] <= 0)
    win_rate_pct = round((winning_trades / total_trades) * 100.0, 2) if total_trades > 0 else 0.0
    gross_pnl_inr = round(sum(t["gross_pnl"] for t in trades), 2)
    net_pnl_inr = round(sim_cash - INITIAL_VIRTUAL_CASH, 2)

    return {
        "symbol": symbol.upper(),
        "token": str(token),
        "exchange": exchange.upper(),
        "days_simulated": len(target_dates),
        "data_source": data_source,
        "bars_tested": n_bars,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate_pct": win_rate_pct,
        "gross_pnl_inr": gross_pnl_inr,
        "total_brokerage_inr": round(total_brokerage, 2),
        "net_pnl_inr": net_pnl_inr,
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "ending_equity_inr": round(sim_cash, 2),
        "recent_trades": trades[-5:],
    }


@mcp.tool()
def reflect_and_update_strategy(
    lesson_learned: str,
    new_rsi_buy: Optional[int] = None,
    new_rsi_sell: Optional[int] = None,
    new_risk_per_trade_pct: Optional[float] = None,
    new_stop_loss_pct: Optional[float] = None,
    new_take_profit_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Review trailing 10 closed trades, append a timestamped quantitative post-mortem
    to MEMORY.md & SQLite, and persist updated RSI & risk thresholds (clamped 2%-15%).
    """
    old_cfg = _load_strategy_config()
    new_cfg = dict(old_cfg)

    if new_rsi_buy is not None:
        new_cfg["rsi_buy_threshold"] = int(min(55, max(15, int(new_rsi_buy))))
    if new_rsi_sell is not None:
        new_cfg["rsi_sell_threshold"] = int(min(85, max(50, int(new_rsi_sell))))
    if new_risk_per_trade_pct is not None:
        new_cfg["risk_per_trade_pct"] = round(
            min(MAX_RISK_PCT, max(MIN_RISK_PCT, float(new_risk_per_trade_pct))), 2
        )
    if new_stop_loss_pct is not None:
        new_cfg["stop_loss_pct"] = round(min(5.0, max(0.4, float(new_stop_loss_pct))), 2)
    if new_take_profit_pct is not None:
        new_cfg["take_profit_pct"] = round(min(10.0, max(0.8, float(new_take_profit_pct))), 2)

    now_iso = _now_ist_iso()
    new_cfg["updated_at"] = now_iso

    diff: Dict[str, Dict[str, Any]] = {}
    for key in (
        "rsi_buy_threshold",
        "rsi_sell_threshold",
        "risk_per_trade_pct",
        "stop_loss_pct",
        "take_profit_pct",
    ):
        if old_cfg.get(key) != new_cfg.get(key):
            diff[key] = {"old": old_cfg.get(key), "new": new_cfg.get(key)}

    STRATEGY_CONFIG_PATH.write_text(json.dumps(new_cfg, indent=2), encoding="utf-8")

    with _get_conn() as conn:
        cursor = conn.cursor()
        trailing = cursor.execute(
            "SELECT symbol, net_pnl, exit_reason FROM closed_trades ORDER BY id DESC LIMIT 10"
        ).fetchall()
        trailing_count = len(trailing)
        trailing_wins = sum(1 for r in trailing if float(r["net_pnl"]) > 0)
        trailing_win_rate = round((trailing_wins / trailing_count) * 100.0, 2) if trailing_count > 0 else 0.0

        cursor.execute(
            """
            INSERT INTO strategy_reflections (lesson_learned, old_config_json, new_config_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (lesson_learned, json.dumps(old_cfg), json.dumps(new_cfg), now_iso),
        )
        conn.commit()

    diff_summary = ", ".join(f"{k}: {v['old']} -> {v['new']}" for k, v in diff.items()) or "no threshold changes"
    memory_entry = (
        f"\n### [{now_iso}] Quantitative Post-Mortem\n"
        f"- **Lesson:** {lesson_learned}\n"
        f"- **Trailing Ledger:** {trailing_count} closed trades reviewed (Win Rate: {trailing_win_rate}%)\n"
        f"- **Parameter Diff:** {diff_summary}\n"
    )
    with MEMORY_MD_PATH.open("a", encoding="utf-8") as f:
        f.write(memory_entry)

    return {
        "updated": True,
        "timestamp": now_iso,
        "trailing_trades_reviewed": trailing_count,
        "trailing_win_rate_pct": trailing_win_rate,
        "diff": diff,
        "old_config": old_cfg,
        "new_config": new_cfg,
    }


if __name__ == "__main__":
    init_environment(reset=False)
    mcp.run()
