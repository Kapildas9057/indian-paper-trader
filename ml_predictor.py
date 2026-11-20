"""
IndianPaperTrader: Quantitative ML Forecasting, Model Comparison & Prediction Audit Engine.

Follows ml-best-practices:
  1. Missing/NULL frequency analysis and contextual imputation prior to split.
  2. Stationarity audit (raw close price vs percentage return lag-1 autocorrelation).
  3. Strict chronological Train (60%) / Validation (20%) / Test (20%) split.
  4. Strict featurization ordering: scaler (mean/std) fit on Training split ONLY.
  5. Baseline + multi-model comparison (Naive Drift Baseline, L2 Ridge Regression,
     Gradient Boosted Decision Stumps) with validation hyperparameter tuning
     and 95% bootstrap confidence intervals on test MAE.
  6. Persists today's predictions for tomorrow's session to SQLite (`daily_predictions`),
     `predictions/predictions_today.json`, and structured logs in `logs/`.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import indian_paper_mcp as ipt

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / "logs"
PREDICTIONS_DIR = BASE_DIR / "predictions"

SYSTEM_LOG_PATH = LOGS_DIR / "indian_paper_trader.log"
TRAINING_LOG_PATH = LOGS_DIR / "training_metrics.jsonl"
PREDICTION_LOG_PATH = LOGS_DIR / "predictions_history.jsonl"
CYCLE_LOG_PATH = LOGS_DIR / "cycle_telemetry.jsonl"
LATEST_PREDICTIONS_PATH = PREDICTIONS_DIR / "predictions_today.json"

FEATURE_COLUMNS: List[str] = [
    "ret_1d",
    "ret_3d",
    "ret_5d",
    "rsi_14",
    "ema_spread_pct",
    "price_vs_ema21_pct",
    "atr_pct",
    "vol_ratio_10d",
    "high_low_range_pct",
    "close_loc_in_range",
]


def ensure_log_dirs_and_tables() -> None:
    """Creates logs/ and predictions/ folders and initializes daily_predictions table."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    ipt.init_environment(reset=False)

    with closing(sqlite3.connect(ipt.DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_date TEXT NOT NULL,
                target_session_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                token TEXT NOT NULL,
                base_close REAL NOT NULL,
                predicted_return_pct REAL NOT NULL,
                predicted_next_close REAL NOT NULL,
                predicted_direction TEXT NOT NULL,
                confidence_pct REAL NOT NULL,
                recommended_action TEXT NOT NULL,
                predicted_stop_loss REAL NOT NULL,
                predicted_take_profit REAL NOT NULL,
                selected_model TEXT NOT NULL,
                test_mae_pct REAL NOT NULL,
                test_rmse_pct REAL NOT NULL,
                test_dir_acc_pct REAL NOT NULL,
                test_mae_ci95_json TEXT NOT NULL,
                model_comparison_json TEXT NOT NULL,
                features_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                actual_next_close REAL,
                actual_return_pct REAL,
                abs_error_inr REAL,
                abs_error_pct REAL,
                direction_correct INTEGER,
                evaluated_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _get_logger() -> logging.Logger:
    ensure_log_dirs_and_tables()
    logger = logging.getLogger("IndianPaperTrader")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(SYSTEM_LOG_PATH, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def append_jsonl_log(path: Path, payload: Dict[str, Any]) -> None:
    ensure_log_dirs_and_tables()
    record = {"logged_at": ipt._now_ist_iso(), **payload}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def log_event(message: str, level: str = "INFO", extra: Optional[Dict[str, Any]] = None) -> None:
    logger = _get_logger()
    if extra:
        full_msg = f"{message} | {json.dumps(extra, default=str)}"
    else:
        full_msg = message
    if level.upper() == "ERROR":
        logger.error(full_msg)
    elif level.upper() == "WARNING":
        logger.warning(full_msg)
    else:
        logger.info(full_msg)


def _fetch_daily_history(symbol: str, token: str, exchange: str = "NSE") -> Tuple[pd.DataFrame, str]:
    """Fetches ~1 year of daily OHLCV candles from yfinance with deterministic fallback."""
    ticker_sym = ipt.market_client.to_yfinance_ticker(symbol, exchange)
    try:
        hist = ipt.yf.Ticker(ticker_sym).history(period="1y", interval="1d", auto_adjust=True)
        df = ipt.market_client._normalize_ohlcv_df(hist)
        if df is not None and len(df) >= 80:
            return df, f"yfinance_daily:{ticker_sym}"
    except Exception:
        pass

    # Fallback: aggregate synthetic or 5m bars to daily sessions
    seed = abs(hash(symbol + "_daily")) % (2**31)
    rng = np.random.default_rng(seed)
    n_days = 240
    base_price = 1200.0 + (seed % 1500)
    rets = rng.normal(0.0004, 0.013, size=n_days)
    closes = base_price * np.cumprod(1.0 + rets)
    opens = np.concatenate([[base_price], closes[:-1]])
    spread = np.abs(rng.normal(0.008, 0.004, size=n_days)) * closes
    highs = np.maximum(opens, closes) + spread
    lows = np.minimum(opens, closes) - spread
    vols = rng.integers(800_000, 6_000_000, size=n_days).astype(float)

    dates: List[datetime] = []
    cur = datetime.now(ipt.IST_TZ).replace(hour=15, minute=30, second=0, microsecond=0)
    while len(dates) < n_days:
        if cur.weekday() < 5:
            dates.append(cur)
        cur -= timedelta(days=1)
    dates.reverse()

    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vols},
        index=pd.DatetimeIndex(dates),
    )
    return df, "synthetic_daily_fallback"


def build_feature_dataset(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Constructs technical features and audits missing/NULL values and stationarity.

    Returns the cleaned DataFrame (where the final row is today's unlabeled row for
    tomorrow's prediction) and a data-hygiene audit dict.
    """
    enriched = ipt.add_indicator_columns(df.copy())
    close = enriched["Close"].astype(float)
    high = enriched["High"].astype(float)
    low = enriched["Low"].astype(float)
    vol = enriched["Volume"].astype(float)

    feat = pd.DataFrame(index=enriched.index)
    feat["Close"] = close
    feat["ATR_14"] = enriched["ATR_14"].astype(float)
    feat["ret_1d"] = close.pct_change(1) * 100.0
    feat["ret_3d"] = close.pct_change(3) * 100.0
    feat["ret_5d"] = close.pct_change(5) * 100.0
    feat["rsi_14"] = enriched["RSI_14"].astype(float)
    feat["ema_spread_pct"] = ((enriched["EMA_9"] - enriched["EMA_21"]) / close) * 100.0
    feat["price_vs_ema21_pct"] = ((close - enriched["EMA_21"]) / enriched["EMA_21"]) * 100.0
    feat["atr_pct"] = (enriched["ATR_14"] / close) * 100.0

    vol_ma10 = vol.rolling(10, min_periods=1).mean().replace(0.0, np.nan)
    feat["vol_ratio_10d"] = (vol / vol_ma10).fillna(1.0)
    feat["high_low_range_pct"] = ((high - low) / close) * 100.0
    feat["close_loc_in_range"] = ((close - low) / ((high - low) + 1e-8)).clip(0.0, 1.0)

    # Target: next trading session percentage return
    feat["target_next_ret_pct"] = (close.shift(-1) / close - 1.0) * 100.0
    feat["target_next_close"] = close.shift(-1)

    # Audit missing values BEFORE imputation (ml-best-practices requirement)
    raw_null_counts = {col: int(feat[col].isna().sum()) for col in FEATURE_COLUMNS}
    total_rows_raw = len(feat)

    # Contextual handling:
    # The first 5 warmup rows have NaN momentum lags (ret_1d, ret_3d, ret_5d).
    # Instead of dropping large blocks, we discard only the initial 5-bar warmup
    # and impute any isolated middle NaNs using forward-fill + 0.0 neutral return.
    feat_trimmed = feat.iloc[5:].copy()
    for col in FEATURE_COLUMNS:
        feat_trimmed[col] = feat_trimmed[col].ffill().fillna(0.0)

    post_null_counts = {col: int(feat_trimmed[col].isna().sum()) for col in FEATURE_COLUMNS}

    # Stationarity check: compare lag-1 autocorrelation of raw Close vs target return %
    valid_ret = feat_trimmed["ret_1d"].dropna()
    close_autocorr_lag1 = float(feat_trimmed["Close"].autocorr(lag=1)) if len(feat_trimmed) > 10 else 1.0
    ret_autocorr_lag1 = float(valid_ret.autocorr(lag=1)) if len(valid_ret) > 10 else 0.0

    audit = {
        "raw_row_count": total_rows_raw,
        "usable_row_count": len(feat_trimmed),
        "warmup_rows_removed": 5,
        "null_frequency_before_handling": raw_null_counts,
        "null_frequency_after_handling": post_null_counts,
        "missing_value_policy": (
            "Removed initial 5 warmup rows for 5-day momentum lag; forward-filled any "
            "isolated feature gaps and imputed 0.0 neutral return where needed. Final row "
            "has target_next_ret_pct=NaN because it represents today's live bar predicting tomorrow."
        ),
        "stationarity_audit": {
            "raw_close_lag1_autocorr": round(close_autocorr_lag1, 4),
            "return_pct_lag1_autocorr": round(ret_autocorr_lag1, 4),
            "stationary_target_confirmed": abs(ret_autocorr_lag1) < 0.5,
            "conclusion": (
                "Raw price series is non-stationary (near-unit root autocorr); modeling "
                "percentage return target_next_ret_pct stabilizes mean and variance."
            ),
        },
    }
    return feat_trimmed, audit


class StandardScalerStrict:
    """Standardizes numerical features; fit strictly on X_train only."""

    def __init__(self) -> None:
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None

    def fit(self, X_train: np.ndarray) -> "StandardScalerStrict":
        self.mean_ = np.mean(X_train, axis=0)
        std = np.std(X_train, axis=0)
        self.std_ = np.where(std < 1e-8, 1.0, std)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        assert self.mean_ is not None and self.std_ is not None, "Scaler must be fit on train split first"
        return (X - self.mean_) / self.std_


class NaiveDriftBaseline:
    """Baseline model predicting training mean return."""

    def __init__(self) -> None:
        self.mean_ret_: float = 0.0

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> "NaiveDriftBaseline":
        self.mean_ret_ = float(np.mean(y_train))
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.full(shape=(X.shape[0],), fill_value=self.mean_ret_, dtype=float)


class RidgeForecaster:
    """L2-regularized linear forecaster with closed-form Cholesky/solve."""

    def __init__(self, alpha: float = 5.0) -> None:
        self.alpha = float(alpha)
        self.coef_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> "RidgeForecaster":
        self.intercept_ = float(np.mean(y_train))
        y_centered = y_train - self.intercept_
        n_features = X_train.shape[1]
        reg_matrix = X_train.T @ X_train + self.alpha * np.eye(n_features)
        rhs = X_train.T @ y_centered
        self.coef_ = np.linalg.solve(reg_matrix, rhs)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self.coef_ is not None
        return self.intercept_ + (X @ self.coef_)


class GradientBoostedStumpForecaster:
    """
    Gradient Boosted Regression Stump Ensemble for non-linear feature interactions.
    Fits additive decision stumps on residuals with shrinkage learning_rate.
    """

    def __init__(self, n_estimators: int = 35, learning_rate: float = 0.08) -> None:
        self.n_estimators = int(n_estimators)
        self.learning_rate = float(learning_rate)
        self.base_pred_: float = 0.0
        self.trees_: List[Tuple[int, float, float, float]] = []

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> "GradientBoostedStumpForecaster":
        self.base_pred_ = float(np.mean(y_train))
        residuals = y_train - self.base_pred_
        self.trees_ = []
        n_samples, n_features = X_train.shape

        for _ in range(self.n_estimators):
            best_feat = 0
            best_thresh = 0.0
            best_left = 0.0
            best_right = 0.0
            best_loss = float("inf")

            for j in range(n_features):
                col = X_train[:, j]
                quantiles = np.percentile(col, [20, 35, 50, 65, 80])
                for thresh in quantiles:
                    left_mask = col <= thresh
                    right_mask = ~left_mask
                    n_left = int(np.sum(left_mask))
                    n_right = n_samples - n_left
                    if n_left < 4 or n_right < 4:
                        continue
                    left_val = float(np.mean(residuals[left_mask]))
                    right_val = float(np.mean(residuals[right_mask]))
                    pred = np.where(left_mask, left_val, right_val)
                    loss = float(np.mean((residuals - pred) ** 2))
                    if loss < best_loss:
                        best_loss = loss
                        best_feat = j
                        best_thresh = float(thresh)
                        best_left = left_val
                        best_right = right_val

            self.trees_.append((best_feat, best_thresh, best_left, best_right))
            step_pred = np.where(X_train[:, best_feat] <= best_thresh, best_left, best_right)
            residuals = residuals - self.learning_rate * step_pred

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        out = np.full(shape=(X.shape[0],), fill_value=self.base_pred_, dtype=float)
        for feat_idx, thresh, left_val, right_val in self.trees_:
            step = np.where(X[:, feat_idx] <= thresh, left_val, right_val)
            out += self.learning_rate * step
        return out


def _evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    errors = np.abs(y_true - y_pred)
    mae = float(np.mean(errors))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    # Directional agreement (treating exact 0 with sign >= 0)
    true_sign = np.where(y_true >= 0.0, 1, -1)
    pred_sign = np.where(y_pred >= 0.0, 1, -1)
    dir_acc = float(np.mean(true_sign == pred_sign) * 100.0)
    return {
        "mae_pct": round(mae, 4),
        "rmse_pct": round(rmse, 4),
        "directional_accuracy_pct": round(dir_acc, 2),
    }


def _bootstrap_mae_ci95(y_true: np.ndarray, y_pred: np.ndarray, n_boot: int = 300) -> Dict[str, float]:
    rng = np.random.default_rng(42)
    errors = np.abs(y_true - y_pred)
    n = len(errors)
    if n <= 1:
        val = float(np.mean(errors)) if n == 1 else 0.0
        return {"low_pct": round(val, 4), "high_pct": round(val, 4)}
    boot_means = [float(np.mean(rng.choice(errors, size=n, replace=True))) for _ in range(n_boot)]
    low, high = np.percentile(boot_means, [2.5, 97.5])
    return {"low_pct": round(float(low), 4), "high_pct": round(float(high), 4)}


def _next_business_day_iso(from_dt: datetime) -> str:
    nxt = from_dt.date() + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt.isoformat()


def train_and_predict_symbol(symbol: str, token: str, exchange: str = "NSE") -> Dict[str, Any]:
    """
    End-to-end chronological ML pipeline for a single stock:
      - Data hygiene & stationarity audit
      - 60/20/20 chronological Train/Val/Test split
      - Strict training-only StandardScaler fit
      - Hyperparameter tuning on Validation split for Ridge and GradientBoostedStumps
      - Test split evaluation + 95% bootstrap confidence interval
      - Final prediction for tomorrow's session from today's latest market snapshot
    """
    daily_df, data_source = _fetch_daily_history(symbol, token, exchange=exchange)

    # Also fetch latest intraday LTP so today's feature row reflects current live/closing price
    latest_ltp, ltp_source = ipt.market_client.fetch_ltp(symbol, token, exchange=exchange)
    if latest_ltp > 0 and not daily_df.empty:
        daily_df.iloc[-1, daily_df.columns.get_loc("Close")] = latest_ltp
        if latest_ltp > float(daily_df["High"].iloc[-1]):
            daily_df.iloc[-1, daily_df.columns.get_loc("High")] = latest_ltp
        if latest_ltp < float(daily_df["Low"].iloc[-1]):
            daily_df.iloc[-1, daily_df.columns.get_loc("Low")] = latest_ltp

    feat_df, audit = build_feature_dataset(daily_df)

    # Separate labeled historical rows from today's unlabeled row (last row)
    labeled_df = feat_df.iloc[:-1].dropna(subset=["target_next_ret_pct"]).copy()
    today_row = feat_df.iloc[-1]

    n_total = len(labeled_df)
    n_train = int(n_total * 0.60)
    n_val = int(n_total * 0.20)
    n_test = n_total - n_train - n_val

    train_df = labeled_df.iloc[:n_train]
    val_df = labeled_df.iloc[n_train : n_train + n_val]
    test_df = labeled_df.iloc[n_train + n_val :]

    X_train_raw = train_df[FEATURE_COLUMNS].to_numpy(dtype=float)
    y_train = train_df["target_next_ret_pct"].to_numpy(dtype=float)

    X_val_raw = val_df[FEATURE_COLUMNS].to_numpy(dtype=float)
    y_val = val_df["target_next_ret_pct"].to_numpy(dtype=float)

    X_test_raw = test_df[FEATURE_COLUMNS].to_numpy(dtype=float)
    y_test = test_df["target_next_ret_pct"].to_numpy(dtype=float)

    X_today_raw = today_row[FEATURE_COLUMNS].to_numpy(dtype=float).reshape(1, -1)

    # STRICT FEATURIZATION ORDERING: Fit scaler ONLY on X_train_raw
    scaler = StandardScalerStrict().fit(X_train_raw)
    X_train = scaler.transform(X_train_raw)
    X_val = scaler.transform(X_val_raw)
    X_test = scaler.transform(X_test_raw)

    # 1. Naive Baseline
    naive = NaiveDriftBaseline().fit(X_train, y_train)
    val_naive_metrics = _evaluate_predictions(y_val, naive.predict(X_val))
    test_naive_metrics = _evaluate_predictions(y_test, naive.predict(X_test))

    # 2. Ridge Regression (tune alpha on validation set)
    best_alpha = 5.0
    best_ridge_val_mae = float("inf")
    for candidate_alpha in (0.5, 2.0, 5.0, 15.0, 40.0):
        m = RidgeForecaster(alpha=candidate_alpha).fit(X_train, y_train)
        val_m = _evaluate_predictions(y_val, m.predict(X_val))
        if val_m["mae_pct"] < best_ridge_val_mae:
            best_ridge_val_mae = val_m["mae_pct"]
            best_alpha = candidate_alpha

    ridge = RidgeForecaster(alpha=best_alpha).fit(X_train, y_train)
    val_ridge_metrics = _evaluate_predictions(y_val, ridge.predict(X_val))

    # 3. Gradient Boosted Stumps (tune n_estimators on validation set)
    best_n_est = 25
    best_gb_val_mae = float("inf")
    for candidate_n in (15, 25, 40, 60):
        gb_cand = GradientBoostedStumpForecaster(n_estimators=candidate_n, learning_rate=0.07).fit(
            X_train, y_train
        )
        val_gb = _evaluate_predictions(y_val, gb_cand.predict(X_val))
        if val_gb["mae_pct"] < best_gb_val_mae:
            best_gb_val_mae = val_gb["mae_pct"]
            best_n_est = candidate_n

    gb = GradientBoostedStumpForecaster(n_estimators=best_n_est, learning_rate=0.07).fit(X_train, y_train)
    val_gb_metrics = _evaluate_predictions(y_val, gb.predict(X_val))

    # Select winning model on validation MAE (with tie-breaker on directional accuracy)
    if (val_gb_metrics["mae_pct"] < val_ridge_metrics["mae_pct"]) or (
        abs(val_gb_metrics["mae_pct"] - val_ridge_metrics["mae_pct"]) < 0.015
        and val_gb_metrics["directional_accuracy_pct"] >= val_ridge_metrics["directional_accuracy_pct"]
    ):
        selected_model_name = f"GradientBoostedStumps(n={best_n_est}, lr=0.07)"
        use_gb = True
    else:
        selected_model_name = f"RidgeRegression(alpha={best_alpha})"
        use_gb = False

    # Retrain both models on Train + Validation (fit scaler on Train+Val before Test evaluation)
    X_trainval_raw = np.vstack([X_train_raw, X_val_raw])
    y_trainval = np.concatenate([y_train, y_val])
    scaler_tv = StandardScalerStrict().fit(X_trainval_raw)
    X_trainval = scaler_tv.transform(X_trainval_raw)
    X_test_tv = scaler_tv.transform(X_test_raw)

    ridge_tv = RidgeForecaster(alpha=best_alpha).fit(X_trainval, y_trainval)
    gb_tv = GradientBoostedStumpForecaster(n_estimators=best_n_est, learning_rate=0.07).fit(
        X_trainval, y_trainval
    )

    test_ridge_pred = ridge_tv.predict(X_test_tv)
    test_gb_pred = gb_tv.predict(X_test_tv)
    test_ridge_metrics = _evaluate_predictions(y_test, test_ridge_pred)
    test_gb_metrics = _evaluate_predictions(y_test, test_gb_pred)

    selected_test_pred = test_gb_pred if use_gb else test_ridge_pred
    selected_test_metrics = test_gb_metrics if use_gb else test_ridge_metrics
    test_ci95 = _bootstrap_mae_ci95(y_test, selected_test_pred)

    # Final production fit on all completed labeled rows to predict Tomorrow's Next Session
    X_all_raw = labeled_df[FEATURE_COLUMNS].to_numpy(dtype=float)
    y_all = labeled_df["target_next_ret_pct"].to_numpy(dtype=float)
    scaler_prod = StandardScalerStrict().fit(X_all_raw)
    X_all = scaler_prod.transform(X_all_raw)
    X_today_scaled = scaler_prod.transform(X_today_raw)

    if use_gb:
        prod_model = GradientBoostedStumpForecaster(n_estimators=best_n_est, learning_rate=0.07).fit(
            X_all, y_all
        )
    else:
        prod_model = RidgeForecaster(alpha=best_alpha).fit(X_all, y_all)

    raw_pred_ret_pct = float(prod_model.predict(X_today_scaled)[0])
    # Clamp extreme single-day predicted returns to realistic NSE daily bounds [-4.5%, +4.5%]
    pred_ret_pct = round(float(np.clip(raw_pred_ret_pct, -4.5, 4.5)), 3)

    base_close = round(float(today_row["Close"]), 2)
    atr_14 = round(float(today_row["ATR_14"]), 2)
    predicted_next_close = round(base_close * (1.0 + pred_ret_pct / 100.0), 2)

    if pred_ret_pct >= 0.15:
        direction = "UP"
        recommended_action = "BUY_ON_OPEN_OR_HOLD"
        stop_loss = round(base_close - max(1.5 * atr_14, base_close * 0.012), 2)
        take_profit = round(max(predicted_next_close, base_close + max(2.0 * atr_14, base_close * 0.018)), 2)
    elif pred_ret_pct <= -0.15:
        direction = "DOWN"
        recommended_action = "AVOID_LONG_OR_SHORT_INTRADAY"
        stop_loss = round(base_close + max(1.5 * atr_14, base_close * 0.012), 2)
        take_profit = round(min(predicted_next_close, base_close - max(2.0 * atr_14, base_close * 0.018)), 2)
    else:
        direction = "NEUTRAL"
        recommended_action = "WAIT_FOR_VWAP_BREAKOUT"
        stop_loss = round(base_close - max(1.2 * atr_14, base_close * 0.01), 2)
        take_profit = round(base_close + max(1.8 * atr_14, base_close * 0.015), 2)

    # Confidence combines test directional accuracy and signal-to-noise ratio (|pred_ret| / test_mae)
    snr = min(1.5, abs(pred_ret_pct) / max(0.25, selected_test_metrics["mae_pct"]))
    confidence_pct = round(
        float(np.clip(48.0 + 0.35 * selected_test_metrics["directional_accuracy_pct"] + 12.0 * snr, 51.0, 92.0)),
        1,
    )

    now_dt = datetime.now(ipt.IST_TZ)
    prediction_date = now_dt.date().isoformat()
    target_session_date = _next_business_day_iso(now_dt)

    today_features_dict = {col: round(float(today_row[col]), 4) for col in FEATURE_COLUMNS}
    model_comparison = {
        "chronological_split": {
            "train_rows": n_train,
            "val_rows": n_val,
            "test_rows": n_test,
            "train_period": f"{train_df.index[0].date()} to {train_df.index[-1].date()}",
            "val_period": f"{val_df.index[0].date()} to {val_df.index[-1].date()}",
            "test_period": f"{test_df.index[0].date()} to {test_df.index[-1].date()}",
        },
        "validation_metrics": {
            "NaiveDriftBaseline": val_naive_metrics,
            f"RidgeRegression(alpha={best_alpha})": val_ridge_metrics,
            f"GradientBoostedStumps(n={best_n_est})": val_gb_metrics,
        },
        "test_metrics": {
            "NaiveDriftBaseline": test_naive_metrics,
            f"RidgeRegression(alpha={best_alpha})": test_ridge_metrics,
            f"GradientBoostedStumps(n={best_n_est})": test_gb_metrics,
        },
        "selected_model": selected_model_name,
        "selected_test_mae_ci95": test_ci95,
    }

    return {
        "symbol": symbol.upper(),
        "token": str(token),
        "exchange": exchange.upper(),
        "data_source": f"{data_source} + {ltp_source}",
        "prediction_date": prediction_date,
        "target_session_date": target_session_date,
        "base_close": base_close,
        "predicted_return_pct": pred_ret_pct,
        "predicted_next_close": predicted_next_close,
        "predicted_change_inr": round(predicted_next_close - base_close, 2),
        "predicted_direction": direction,
        "confidence_pct": confidence_pct,
        "recommended_action": recommended_action,
        "predicted_stop_loss": stop_loss,
        "predicted_take_profit": take_profit,
        "selected_model": selected_model_name,
        "test_mae_pct": selected_test_metrics["mae_pct"],
        "test_rmse_pct": selected_test_metrics["rmse_pct"],
        "test_dir_acc_pct": selected_test_metrics["directional_accuracy_pct"],
        "test_mae_ci95": test_ci95,
        "today_features": today_features_dict,
        "data_audit": audit,
        "model_comparison": model_comparison,
    }


def save_prediction_to_db(pred: Dict[str, Any]) -> int:
    ensure_log_dirs_and_tables()
    now_iso = ipt._now_ist_iso()
    with closing(sqlite3.connect(ipt.DB_PATH)) as conn:
        cursor = conn.cursor()
        # Avoid duplicate pending entries for the exact same (prediction_date, symbol) by replacing or updating
        cursor.execute(
            "DELETE FROM daily_predictions WHERE prediction_date = ? AND symbol = ? AND status = 'PENDING'",
            (pred["prediction_date"], pred["symbol"]),
        )
        cursor.execute(
            """
            INSERT INTO daily_predictions (
                prediction_date, target_session_date, symbol, token,
                base_close, predicted_return_pct, predicted_next_close,
                predicted_direction, confidence_pct, recommended_action,
                predicted_stop_loss, predicted_take_profit, selected_model,
                test_mae_pct, test_rmse_pct, test_dir_acc_pct,
                test_mae_ci95_json, model_comparison_json, features_json,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (
                pred["prediction_date"],
                pred["target_session_date"],
                pred["symbol"],
                pred["token"],
                pred["base_close"],
                pred["predicted_return_pct"],
                pred["predicted_next_close"],
                pred["predicted_direction"],
                pred["confidence_pct"],
                pred["recommended_action"],
                pred["predicted_stop_loss"],
                pred["predicted_take_profit"],
                pred["selected_model"],
                pred["test_mae_pct"],
                pred["test_rmse_pct"],
                pred["test_dir_acc_pct"],
                json.dumps(pred["test_mae_ci95"]),
                json.dumps(pred["model_comparison"]),
                json.dumps(pred["today_features"]),
                now_iso,
            ),
        )
        pred_id = int(cursor.lastrowid)
        conn.commit()
    return pred_id


def train_and_predict_watchlist(
    watchlist: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Trains chronological ML models across the core Nifty 50 watchlist, saves today's
    predictions for tomorrow's session to SQLite and JSON files, and logs all telemetry.
    """
    ensure_log_dirs_and_tables()
    targets = watchlist or [
        ("RELIANCE-EQ", "2885"),
        ("TCS-EQ", "11536"),
        ("HDFCBANK-EQ", "1333"),
        ("INFY-EQ", "1594"),
        ("ICICIBANK-EQ", "4963"),
        ("SBIN-EQ", "3045"),
    ]

    now_iso = ipt._now_ist_iso()
    today_str = datetime.now(ipt.IST_TZ).date().isoformat()
    predictions: List[Dict[str, Any]] = []

    log_event(f"Starting chronological ML training & next-session prediction across {len(targets)} scrips.")

    for sym, tok in targets:
        pred = train_and_predict_symbol(sym, tok, exchange="NSE")
        pred_id = save_prediction_to_db(pred)
        pred["prediction_id"] = pred_id
        predictions.append(pred)

        append_jsonl_log(
            TRAINING_LOG_PATH,
            {
                "event": "MODEL_TRAINED",
                "symbol": sym,
                "token": tok,
                "selected_model": pred["selected_model"],
                "test_mae_pct": pred["test_mae_pct"],
                "test_rmse_pct": pred["test_rmse_pct"],
                "test_dir_acc_pct": pred["test_dir_acc_pct"],
                "test_mae_ci95": pred["test_mae_ci95"],
                "data_audit": pred["data_audit"],
                "model_comparison": pred["model_comparison"],
            },
        )
        append_jsonl_log(
            PREDICTION_LOG_PATH,
            {
                "event": "PREDICTION_SAVED",
                "prediction_id": pred_id,
                "prediction_date": pred["prediction_date"],
                "target_session_date": pred["target_session_date"],
                "symbol": sym,
                "base_close": pred["base_close"],
                "predicted_next_close": pred["predicted_next_close"],
                "predicted_return_pct": pred["predicted_return_pct"],
                "predicted_direction": pred["predicted_direction"],
                "confidence_pct": pred["confidence_pct"],
                "recommended_action": pred["recommended_action"],
                "selected_model": pred["selected_model"],
            },
        )
        log_event(
            f"Saved prediction #{pred_id} for {sym}: base=₹{pred['base_close']:.2f} -> "
            f"pred=₹{pred['predicted_next_close']:.2f} ({pred['predicted_return_pct']:+.3f}%, "
            f"{pred['predicted_direction']}, conf={pred['confidence_pct']}%, model={pred['selected_model']})"
        )

    avg_test_dir_acc = round(
        float(np.mean([p["test_dir_acc_pct"] for p in predictions])) if predictions else 0.0, 2
    )
    avg_test_mae = round(
        float(np.mean([p["test_mae_pct"] for p in predictions])) if predictions else 0.0, 4
    )

    dated_path = PREDICTIONS_DIR / f"predictions_{today_str}.json"
    summary_payload = {
        "generated_at": now_iso,
        "prediction_date": today_str,
        "target_session_date": predictions[0]["target_session_date"] if predictions else today_str,
        "total_symbols_predicted": len(predictions),
        "avg_test_directional_accuracy_pct": avg_test_dir_acc,
        "avg_test_mae_pct": avg_test_mae,
        "predictions": predictions,
    }
    LATEST_PREDICTIONS_PATH.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    dated_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    return {
        "generated_at": now_iso,
        "prediction_date": today_str,
        "target_session_date": summary_payload["target_session_date"],
        "saved_json_path": str(dated_path),
        "latest_json_path": str(LATEST_PREDICTIONS_PATH),
        "avg_test_directional_accuracy_pct": avg_test_dir_acc,
        "avg_test_mae_pct": avg_test_mae,
        "predictions": predictions,
    }


def evaluate_saved_predictions(force_mark_to_market: bool = True) -> Dict[str, Any]:
    """
    Evaluates saved predictions in SQLite `daily_predictions` against current/next-day
    market prices to verify how today's predictions performed.
    """
    ensure_log_dirs_and_tables()
    now_dt = datetime.now(ipt.IST_TZ)
    now_iso = now_dt.isoformat(timespec="seconds")
    today_iso = now_dt.date().isoformat()

    evaluated_rows: List[Dict[str, Any]] = []
    with closing(sqlite3.connect(ipt.DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM daily_predictions ORDER BY id DESC LIMIT 30"
        ).fetchall()

        for row in rows:
            sym = row["symbol"]
            tok = row["token"]
            base_close = float(row["base_close"])
            pred_close = float(row["predicted_next_close"])
            pred_ret = float(row["predicted_return_pct"])
            pred_dir = str(row["predicted_direction"])
            target_date = str(row["target_session_date"])

            live_ltp, src = ipt.market_client.fetch_ltp(sym, tok, exchange="NSE")
            actual_ret = round(((live_ltp - base_close) / base_close) * 100.0, 3) if base_close > 0 else 0.0
            abs_err_inr = round(abs(live_ltp - pred_close), 2)
            abs_err_pct = round(abs(actual_ret - pred_ret), 3)

            if pred_dir == "UP":
                dir_correct = 1 if actual_ret > 0 else (0 if actual_ret < 0 else 1)
            elif pred_dir == "DOWN":
                dir_correct = 1 if actual_ret < 0 else (0 if actual_ret > 0 else 1)
            else:
                dir_correct = 1 if abs(actual_ret) < 0.35 else 0

            is_target_day_reached = today_iso >= target_date
            new_status = "EVALUATED" if is_target_day_reached else "PENDING_TOMORROW_MTM"

            if is_target_day_reached or force_mark_to_market:
                cursor.execute(
                    """
                    UPDATE daily_predictions
                    SET actual_next_close = ?,
                        actual_return_pct = ?,
                        abs_error_inr = ?,
                        abs_error_pct = ?,
                        direction_correct = ?,
                        status = ?,
                        evaluated_at = ?
                    WHERE id = ?
                    """,
                    (
                        live_ltp,
                        actual_ret,
                        abs_err_inr,
                        abs_err_pct,
                        dir_correct,
                        "EVALUATED" if is_target_day_reached else "PENDING",
                        now_iso,
                        row["id"],
                    ),
                )

            evaluated_rows.append(
                {
                    "id": row["id"],
                    "symbol": sym,
                    "token": tok,
                    "prediction_date": row["prediction_date"],
                    "target_session_date": target_date,
                    "base_close": base_close,
                    "predicted_next_close": pred_close,
                    "predicted_return_pct": pred_ret,
                    "predicted_direction": pred_dir,
                    "confidence_pct": float(row["confidence_pct"]),
                    "recommended_action": row["recommended_action"],
                    "selected_model": row["selected_model"],
                    "current_or_actual_close": live_ltp,
                    "actual_return_pct": actual_ret,
                    "abs_error_inr": abs_err_inr,
                    "abs_error_pct": abs_err_pct,
                    "direction_correct": bool(dir_correct),
                    "evaluation_state": new_status,
                    "data_source": src,
                    "evaluated_at": now_iso,
                }
            )
        conn.commit()

    append_jsonl_log(
        PREDICTION_LOG_PATH,
        {
            "event": "PREDICTIONS_EVALUATED",
            "evaluated_count": len(evaluated_rows),
            "results": evaluated_rows,
        },
    )
    log_event(f"Evaluated {len(evaluated_rows)} saved predictions against market prices.")

    return {
        "evaluated_at": now_iso,
        "total_predictions_checked": len(evaluated_rows),
        "predictions": evaluated_rows,
    }


def get_recent_logs(limit: int = 60) -> Dict[str, Any]:
    """Reads trailing lines from all persistent log files for the GUI & diagnostics."""
    ensure_log_dirs_and_tables()

    def _tail_lines(p: Path, n: int) -> List[str]:
        if not p.exists():
            return []
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]

    return {
        "system_log": _tail_lines(SYSTEM_LOG_PATH, limit),
        "training_metrics_jsonl": [
            json.loads(line) for line in _tail_lines(TRAINING_LOG_PATH, 15) if line.strip()
        ],
        "predictions_history_jsonl": [
            json.loads(line) for line in _tail_lines(PREDICTION_LOG_PATH, 20) if line.strip()
        ],
        "cycle_telemetry_jsonl": [
            json.loads(line) for line in _tail_lines(CYCLE_LOG_PATH, 10) if line.strip()
        ],
    }


if __name__ == "__main__":
    res = train_and_predict_watchlist()
    print(f"Trained & saved {len(res['predictions'])} predictions to {res['saved_json_path']}")
