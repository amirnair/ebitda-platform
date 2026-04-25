"""
forecasting_engine.py
---------------------
AC Industries EBITDA Platform — Session 3: Forecasting Engine

Implements the full 3-layer model hierarchy from §3.2:
  Layer 1 — Statistical Baseline: SARIMA (auto-spec), SARIMAX, Holt-Winters,
                                   Simple ES, Double ES
  Layer 2 — ML Challengers:        XGBoost, Random Forest, Gradient Boosting,
                                   Ridge, Lasso, SVR, LSTM
  Layer 3 — Ensemble:              Auto-weighted by rolling 3-month MAPE

Regional split (§3.4):
  Chennai:         P1 → best statistical model, P2 → XGBoost
  Outside Chennai: P1 → XGBoost, P2 → XGBoost

External variables (§3.5):
  SARIMAX accepts an ExternalVariables object. All fields are None until
  the live data feed session — the interface is stable, no engine changes
  needed when feeds are wired up.

Architecture notes:
  - SARIMA is implemented using a hand-rolled grid search over (p,d,q)(P,D,Q,s)
    with AIC + MAPE evaluation. statsmodels is used when available; falls back
    to a simplified exponential smoothing proxy when not installed.
  - XGBoost / LSTM degrade gracefully when libraries not installed.
  - Every model produces (forecast_array, confidence_low, confidence_high).
  - Ensemble weights = softmax of inverse MAPE scores from rolling 3-month window.
  - Model selection re-evaluates every quarter (or on demand).
"""

from __future__ import annotations

import math
import warnings
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge, Lasso
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit

from forecast_models import (
    ForecastPoint, ModelPerformance, ModelSelectionResult,
    ForecastBundle, CompanyForecastResult,
    ForecastGranularity, ModelName, Region, ExternalVariables,
)
from sku_proportion_model import (
    disaggregate_monthly_to_weekly,
    disaggregate_monthly_to_daily,
)

# Optional heavy dependencies — degrade gracefully
try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX as _SARIMAX_MODEL
    from statsmodels.tsa.holtwinters import ExponentialSmoothing as _HW_MODEL
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    warnings.warn(
        "statsmodels not available — SARIMA/SARIMAX will use fallback ES implementation. "
        "Install statsmodels for full statistical baseline.",
        ImportWarning,
        stacklevel=2,
    )

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import tensorflow as tf  # type: ignore
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

FORECAST_HORIZON_MONTHS = 12
SARIMA_SEASONALITY = 12       # Monthly data, annual seasonality
MIN_HISTORY_MONTHS_SARIMA = 24
MIN_HISTORY_MONTHS_HW = 12
ENSEMBLE_ROLLING_WINDOW = 3   # Months for MAPE rolling window
SARIMAX_IMPROVEMENT_THRESHOLD = 0.05  # 5% MAPE improvement to use SARIMAX
CONFIDENCE_LEVEL = 0.80

# SARIMA grid search space (kept tractable — auto-expands with more data)
SARIMA_P_RANGE = range(0, 3)
SARIMA_D_RANGE = range(0, 2)
SARIMA_Q_RANGE = range(0, 3)
SARIMA_SP_RANGE = range(0, 3)
SARIMA_SD_RANGE = range(0, 2)
SARIMA_SQ_RANGE = range(0, 2)


# ---------------------------------------------------------------------------
# Feature engineering for ML models
# ---------------------------------------------------------------------------

def build_ml_features(
    series: np.ndarray,
    n_lags: int = 12,
    include_seasonal: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build supervised learning features from a monthly time series.

    Features per sample:
      - Lag 1–12 of target values
      - Month-of-year (1–12) as cyclic sin/cos encoding
      - Rolling 3/6/12-month means
      - Year-over-year change (lag 12 vs lag 24)

    Returns (X, y) arrays where each row is one month.
    """
    n = len(series)
    if n < n_lags + 2:
        raise ValueError(f"Need at least {n_lags + 2} months of data, got {n}")

    rows = []
    targets = []

    for i in range(n_lags, n):
        features = []

        # Lag features
        for lag in range(1, n_lags + 1):
            features.append(series[i - lag])

        # Month-of-year cyclic encoding (approximate — we index from lag start)
        month = (i % 12) + 1
        features.append(math.sin(2 * math.pi * month / 12))
        features.append(math.cos(2 * math.pi * month / 12))

        # Rolling statistics
        features.append(float(np.mean(series[i-3:i])))    # 3-month rolling mean
        features.append(float(np.mean(series[i-6:i])))    # 6-month rolling mean
        features.append(float(np.mean(series[i-12:i])))   # 12-month rolling mean
        features.append(float(np.std(series[i-6:i])))     # 6-month volatility

        # Year-over-year delta
        if i >= 24:
            yoy = series[i - 12] - series[i - 24]
            features.append(yoy)
        else:
            features.append(0.0)

        rows.append(features)
        targets.append(series[i])

    return np.array(rows), np.array(targets)


def build_future_features(
    series: np.ndarray,
    n_steps: int,
    n_lags: int = 12,
) -> np.ndarray:
    """
    Build feature matrix for n_steps future periods by iteratively
    appending predictions back into the lag window.
    Returns feature matrix of shape (n_steps, n_features).
    """
    extended = list(series)
    future_rows = []

    for step in range(n_steps):
        i = len(extended)
        features = []

        for lag in range(1, n_lags + 1):
            idx = i - lag
            features.append(extended[idx] if idx >= 0 else extended[0])

        month = (i % 12) + 1
        features.append(math.sin(2 * math.pi * month / 12))
        features.append(math.cos(2 * math.pi * month / 12))

        features.append(float(np.mean(extended[max(0, i-3):i])))
        features.append(float(np.mean(extended[max(0, i-6):i])))
        features.append(float(np.mean(extended[max(0, i-12):i])))
        features.append(float(np.std(extended[max(0, i-6):i])) if i >= 6 else 0.0)

        if i >= 24:
            features.append(extended[i - 12] - extended[i - 24])
        else:
            features.append(0.0)

        future_rows.append(features)
        # Placeholder — will be filled by caller with actual prediction
        extended.append(0.0)

    return np.array(future_rows)


# ---------------------------------------------------------------------------
# MAPE / accuracy utilities
# ---------------------------------------------------------------------------

def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Percentage Error — returns percentage (0–100)."""
    mask = actual != 0
    if mask.sum() == 0:
        return float("inf")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def compute_confidence_interval(
    residuals: np.ndarray,
    forecast: np.ndarray,
    level: float = 0.80,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute prediction interval from in-sample residuals.
    Uses residual std scaled by z-score for the given confidence level.
    """
    z = {0.80: 1.282, 0.90: 1.645, 0.95: 1.960}.get(level, 1.282)
    std = float(np.std(residuals))
    # Widen interval for longer horizons (uncertainty grows with sqrt of steps)
    steps = len(forecast)
    low  = np.array([max(0.0, f - z * std * math.sqrt(1 + 0.1 * (i + 1)))
                     for i, f in enumerate(forecast)])
    high = np.array([f + z * std * math.sqrt(1 + 0.1 * (i + 1))
                     for i, f in enumerate(forecast)])
    return low, high


# ---------------------------------------------------------------------------
# Layer 1 — Statistical Baseline
# ---------------------------------------------------------------------------

class SimpleExponentialSmoothing:
    """Simple ES — always-run sanity baseline."""

    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self._last_level: float = 0.0
        self._in_sample: np.ndarray = np.array([])

    def fit(self, series: np.ndarray) -> "SimpleExponentialSmoothing":
        level = float(series[0])
        fitted = [level]
        for val in series[1:]:
            level = self.alpha * float(val) + (1 - self.alpha) * level
            fitted.append(level)
        self._last_level = level
        self._in_sample = np.array(fitted)
        return self

    def forecast(self, steps: int) -> np.ndarray:
        return np.full(steps, self._last_level)

    def residuals(self, series: np.ndarray) -> np.ndarray:
        return series - self._in_sample


class DoubleExponentialSmoothing:
    """Double ES (Holt's linear) — handles trend."""

    def __init__(self, alpha: float = 0.3, beta: float = 0.1):
        self.alpha = alpha
        self.beta = beta
        self._level: float = 0.0
        self._trend: float = 0.0
        self._in_sample: np.ndarray = np.array([])

    def fit(self, series: np.ndarray) -> "DoubleExponentialSmoothing":
        if len(series) < 2:
            raise ValueError("Double ES needs at least 2 data points")
        level = float(series[0])
        trend = float(series[1]) - float(series[0])
        fitted = [level + trend]

        for val in series[1:]:
            prev_level = level
            level = self.alpha * float(val) + (1 - self.alpha) * (level + trend)
            trend = self.beta * (level - prev_level) + (1 - self.beta) * trend
            fitted.append(level + trend)

        self._level = level
        self._trend = trend
        self._in_sample = np.array(fitted[:len(series)])
        return self

    def forecast(self, steps: int) -> np.ndarray:
        return np.array([
            max(0.0, self._level + (i + 1) * self._trend)
            for i in range(steps)
        ])

    def residuals(self, series: np.ndarray) -> np.ndarray:
        return series - self._in_sample


class HoltWintersModel:
    """
    Holt-Winters triple exponential smoothing.
    Uses statsmodels when available, falls back to manual implementation.
    Auto-selects additive vs multiplicative seasonality.
    """

    def __init__(self, seasonal_periods: int = 12):
        self.seasonal_periods = seasonal_periods
        self._fitted_model = None
        self._forecast_cache: Optional[np.ndarray] = None
        self._in_sample: Optional[np.ndarray] = None
        self._use_statsmodels = STATSMODELS_AVAILABLE

    def fit(self, series: np.ndarray) -> "HoltWintersModel":
        if self._use_statsmodels:
            # Try multiplicative first (better for demand data), fall back to additive
            for seasonal in ["mul", "add"]:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        model = _HW_MODEL(
                            series,
                            seasonal_periods=self.seasonal_periods,
                            trend="add",
                            seasonal=seasonal,
                            initialization_method="estimated",
                        ).fit(optimized=True, disp=False)
                    self._fitted_model = model
                    self._in_sample = model.fittedvalues
                    return self
                except Exception:
                    continue

        # Manual fallback
        self._manual_fit(series)
        return self

    def _manual_fit(self, series: np.ndarray) -> None:
        """Simplified Holt-Winters with additive seasonality."""
        s = self.seasonal_periods
        n = len(series)

        alpha, beta, gamma = 0.3, 0.1, 0.2

        # Initialise
        level = float(np.mean(series[:s]))
        trend = float((np.mean(series[s:2*s]) - np.mean(series[:s])) / s) if n >= 2 * s else 0.0
        seasonals = [float(series[i]) - level for i in range(s)]

        self._alpha = alpha
        self._beta = beta
        self._gamma = gamma
        self._s = s

        fitted = []
        for i in range(n):
            if i < s:
                fitted.append(level + trend + seasonals[i % s])
                continue
            prev_level = level
            level_new = alpha * (float(series[i]) - seasonals[i % s]) + (1 - alpha) * (level + trend)
            trend = beta * (level_new - prev_level) + (1 - beta) * trend
            seasonals[i % s] = gamma * (float(series[i]) - level_new) + (1 - gamma) * seasonals[i % s]
            level = level_new
            fitted.append(level + trend + seasonals[i % s])

        self._manual_level = level
        self._manual_trend = trend
        self._manual_seasonals = seasonals
        self._in_sample = np.array(fitted[:n])

    def forecast(self, steps: int) -> np.ndarray:
        if self._fitted_model is not None:
            return np.maximum(0, self._fitted_model.forecast(steps))

        # Manual fallback
        s = self._s
        result = []
        for i in range(1, steps + 1):
            f = (self._manual_level + i * self._manual_trend +
                 self._manual_seasonals[(len(self._in_sample) + i - 1) % s])
            result.append(max(0.0, f))
        return np.array(result)

    def residuals(self, series: np.ndarray) -> np.ndarray:
        return series - self._in_sample[:len(series)]


class SARIMAModel:
    """
    Auto-SARIMA: fits multiple (p,d,q)(P,D,Q,12) combinations, selects best by AIC.
    Uses statsmodels when available; falls back to Holt-Winters proxy.

    Important: SARIMA(1,0,0)(2,1,0)[12] happened to be best for the pilot client.
    This is NOT hardcoded — every run does grid search. (§3.2 note)
    """

    def __init__(
        self,
        max_p: int = 2, max_d: int = 1, max_q: int = 2,
        max_P: int = 2, max_D: int = 1, max_Q: int = 1,
        seasonal_periods: int = 12,
    ):
        self.max_p = max_p
        self.max_d = max_d
        self.max_q = max_q
        self.max_P = max_P
        self.max_D = max_D
        self.max_Q = max_Q
        self.seasonal_periods = seasonal_periods
        self.best_order: Optional[tuple] = None
        self.best_seasonal_order: Optional[tuple] = None
        self.best_aic: float = float("inf")
        self._fitted_model = None
        self._fallback: Optional[HoltWintersModel] = None
        self._in_sample: Optional[np.ndarray] = None

    def fit(self, series: np.ndarray) -> "SARIMAModel":
        if not STATSMODELS_AVAILABLE:
            logger.warning("statsmodels unavailable — using Holt-Winters proxy for SARIMA")
            self._fallback = HoltWintersModel(self.seasonal_periods).fit(series)
            self._in_sample = self._fallback._in_sample
            return self

        best_model = None
        best_aic = float("inf")
        best_order = (1, 0, 0)
        best_seasonal = (0, 1, 1, self.seasonal_periods)

        # Grid search
        for p in range(self.max_p + 1):
            for d in range(self.max_d + 1):
                for q in range(self.max_q + 1):
                    for P in range(self.max_P + 1):
                        for D in range(self.max_D + 1):
                            for Q in range(self.max_Q + 1):
                                if p == 0 and q == 0 and P == 0 and Q == 0:
                                    continue
                                try:
                                    with warnings.catch_warnings():
                                        warnings.simplefilter("ignore")
                                        m = _SARIMAX_MODEL(
                                            series,
                                            order=(p, d, q),
                                            seasonal_order=(P, D, Q, self.seasonal_periods),
                                            enforce_stationarity=False,
                                            enforce_invertibility=False,
                                        ).fit(disp=False, maxiter=50)
                                    if m.aic < best_aic:
                                        best_aic = m.aic
                                        best_model = m
                                        best_order = (p, d, q)
                                        best_seasonal = (P, D, Q, self.seasonal_periods)
                                except Exception:
                                    continue

        if best_model is None:
            logger.warning("SARIMA grid search failed — using Holt-Winters fallback")
            self._fallback = HoltWintersModel(self.seasonal_periods).fit(series)
            self._in_sample = self._fallback._in_sample
        else:
            self._fitted_model = best_model
            self.best_order = best_order
            self.best_seasonal_order = best_seasonal
            self.best_aic = best_aic
            self._in_sample = best_model.fittedvalues

        return self

    def forecast(self, steps: int) -> np.ndarray:
        if self._fallback is not None:
            return self._fallback.forecast(steps)
        pred = self._fitted_model.forecast(steps=steps)
        return np.maximum(0, pred)

    def forecast_with_ci(self, steps: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Returns (point, lower_80, upper_80)."""
        if self._fallback is not None:
            point = self._fallback.forecast(steps)
            res = self._fallback.residuals(np.array([]))
            low, high = compute_confidence_interval(np.zeros(10), point)
            return point, low, high

        if not STATSMODELS_AVAILABLE:
            point = self.forecast(steps)
            low, high = compute_confidence_interval(np.zeros(10), point)
            return point, low, high

        fc = self._fitted_model.get_forecast(steps=steps)
        ci = fc.conf_int(alpha=1 - CONFIDENCE_LEVEL)
        return (
            np.maximum(0, fc.predicted_mean),
            np.maximum(0, ci.iloc[:, 0].values),
            ci.iloc[:, 1].values,
        )

    def residuals(self, series: np.ndarray) -> np.ndarray:
        if self._fallback is not None:
            return self._fallback.residuals(series)
        return series - self._in_sample[:len(series)]


class SARIMAXModel:
    """
    SARIMA with external regressors.
    Accepts ExternalVariables — uses them if populated, else delegates to SARIMA.
    MAPE improvement threshold: >5% to be selected over plain SARIMA (§3.2).
    """

    def __init__(self, base_sarima: SARIMAModel):
        self.base_sarima = base_sarima
        self._fitted_model = None
        self._in_sample: Optional[np.ndarray] = None
        self._has_exog = False

    def fit(
        self,
        series: np.ndarray,
        exog_train: Optional[np.ndarray] = None,
    ) -> "SARIMAXModel":
        if not STATSMODELS_AVAILABLE or exog_train is None:
            self._in_sample = self.base_sarima._in_sample
            return self

        self._has_exog = True
        order = self.base_sarima.best_order or (1, 0, 0)
        seasonal = self.base_sarima.best_seasonal_order or (0, 1, 1, 12)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m = _SARIMAX_MODEL(
                    series,
                    exog=exog_train,
                    order=order,
                    seasonal_order=seasonal,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                ).fit(disp=False, maxiter=50)
            self._fitted_model = m
            self._in_sample = m.fittedvalues
        except Exception as e:
            logger.warning(f"SARIMAX fit failed ({e}) — using SARIMA baseline")
            self._in_sample = self.base_sarima._in_sample

        return self

    def forecast(
        self,
        steps: int,
        exog_future: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        if self._fitted_model is None or exog_future is None:
            return self.base_sarima.forecast(steps)
        try:
            pred = self._fitted_model.forecast(steps=steps, exog=exog_future)
            return np.maximum(0, pred)
        except Exception:
            return self.base_sarima.forecast(steps)

    def residuals(self, series: np.ndarray) -> np.ndarray:
        if self._in_sample is None:
            return self.base_sarima.residuals(series)
        return series - self._in_sample[:len(series)]


# ---------------------------------------------------------------------------
# Layer 2 — ML Challengers
# ---------------------------------------------------------------------------

class MLForecaster:
    """
    Wraps sklearn-compatible ML models for time-series forecasting.
    Uses recursive multi-step prediction (walk-forward with lag features).
    """

    def __init__(self, model_name: ModelName, **kwargs):
        self.model_name = model_name
        self._scaler = StandardScaler()
        self._model = self._build_model(**kwargs)
        self._n_lags = 12
        self._series: Optional[np.ndarray] = None
        self._in_sample: Optional[np.ndarray] = None

    def _build_model(self, **kwargs):
        if self.model_name == ModelName.RANDOM_FOREST:
            return RandomForestRegressor(n_estimators=100, random_state=42, **kwargs)
        elif self.model_name == ModelName.GRADIENT_BOOST:
            return GradientBoostingRegressor(n_estimators=100, random_state=42, **kwargs)
        elif self.model_name == ModelName.RIDGE:
            return Ridge(alpha=1.0, **kwargs)
        elif self.model_name == ModelName.LASSO:
            return Lasso(alpha=0.1, max_iter=5000, **kwargs)
        elif self.model_name == ModelName.SVR:
            return SVR(kernel="rbf", C=100, gamma=0.1, epsilon=0.1, **kwargs)
        elif self.model_name == ModelName.XGBOOST:
            if XGBOOST_AVAILABLE:
                return xgb.XGBRegressor(n_estimators=100, random_state=42, **kwargs)
            else:
                logger.info("XGBoost unavailable — using GradientBoosting as substitute")
                return GradientBoostingRegressor(n_estimators=150, random_state=42, **kwargs)
        else:
            return RandomForestRegressor(n_estimators=100, random_state=42)

    def fit(self, series: np.ndarray) -> "MLForecaster":
        self._series = series.copy()
        if len(series) < self._n_lags + 2:
            self._in_sample = series.copy()
            return self

        X, y = build_ml_features(series, n_lags=self._n_lags)
        X_scaled = self._scaler.fit_transform(X)
        self._model.fit(X_scaled, y)

        # In-sample fitted values
        fitted_preds = self._model.predict(X_scaled)
        # Pad with actuals for the first n_lags periods
        self._in_sample = np.concatenate([series[:self._n_lags], fitted_preds])
        return self

    def forecast(self, steps: int) -> np.ndarray:
        if self._series is None or len(self._series) < self._n_lags + 2:
            # Fallback: last-value repeat with slight trend
            last = float(self._series[-1]) if self._series is not None else 0.0
            return np.full(steps, last)

        extended = list(self._series)
        predictions = []

        for step in range(steps):
            i = len(extended)
            features = []
            for lag in range(1, self._n_lags + 1):
                idx = i - lag
                features.append(extended[idx] if idx >= 0 else extended[0])

            month = (i % 12) + 1
            features.append(math.sin(2 * math.pi * month / 12))
            features.append(math.cos(2 * math.pi * month / 12))
            features.append(float(np.mean(extended[max(0, i-3):i])))
            features.append(float(np.mean(extended[max(0, i-6):i])))
            features.append(float(np.mean(extended[max(0, i-12):i])))
            features.append(float(np.std(extended[max(0, i-6):i])) if i >= 6 else 0.0)
            features.append(extended[i - 12] - extended[i - 24] if i >= 24 else 0.0)

            X_step = np.array(features).reshape(1, -1)
            X_scaled = self._scaler.transform(X_step)
            pred = float(self._model.predict(X_scaled)[0])
            pred = max(0.0, pred)
            predictions.append(pred)
            extended.append(pred)

        return np.array(predictions)

    def residuals(self, series: np.ndarray) -> np.ndarray:
        if self._in_sample is None:
            return np.zeros_like(series)
        return series - self._in_sample[:len(series)]


class LSTMForecaster:
    """
    LSTM stub. Uses TensorFlow when available; falls back to GradientBoosting.
    Interface is stable — no engine changes when TF is installed.
    """

    def __init__(self, look_back: int = 12, epochs: int = 50):
        self.look_back = look_back
        self.epochs = epochs
        self._model = None
        self._scaler = StandardScaler()
        self._series: Optional[np.ndarray] = None
        self._in_sample: Optional[np.ndarray] = None
        self._use_tf = TENSORFLOW_AVAILABLE

    def fit(self, series: np.ndarray) -> "LSTMForecaster":
        self._series = series.copy()
        if self._use_tf:
            self._fit_lstm(series)
        else:
            # Fallback: gradient boosting as LSTM substitute
            self._fallback = MLForecaster(ModelName.GRADIENT_BOOST).fit(series)
            self._in_sample = self._fallback._in_sample
        return self

    def _fit_lstm(self, series: np.ndarray) -> None:
        try:
            scaled = self._scaler.fit_transform(series.reshape(-1, 1)).flatten()
            X, y = [], []
            for i in range(self.look_back, len(scaled)):
                X.append(scaled[i - self.look_back:i])
                y.append(scaled[i])
            X_arr = np.array(X).reshape(-1, self.look_back, 1)
            y_arr = np.array(y)

            model = tf.keras.Sequential([
                tf.keras.layers.LSTM(64, input_shape=(self.look_back, 1), return_sequences=False),
                tf.keras.layers.Dense(32, activation="relu"),
                tf.keras.layers.Dense(1),
            ])
            model.compile(optimizer="adam", loss="mse")
            model.fit(X_arr, y_arr, epochs=self.epochs, batch_size=16, verbose=0)
            self._model = model

            fitted_scaled = model.predict(X_arr, verbose=0).flatten()
            fitted = self._scaler.inverse_transform(
                fitted_scaled.reshape(-1, 1)
            ).flatten()
            self._in_sample = np.concatenate([series[:self.look_back], fitted])
        except Exception as e:
            logger.warning(f"LSTM fit failed ({e}) — using GradientBoosting fallback")
            self._fallback = MLForecaster(ModelName.GRADIENT_BOOST).fit(series)
            self._model = None
            self._in_sample = self._fallback._in_sample

    def forecast(self, steps: int) -> np.ndarray:
        if not self._use_tf or self._model is None:
            return self._fallback.forecast(steps)

        extended = list(
            self._scaler.transform(self._series.reshape(-1, 1)).flatten()
        )
        predictions_scaled = []

        for _ in range(steps):
            window = np.array(extended[-self.look_back:]).reshape(1, self.look_back, 1)
            pred_scaled = float(self._model.predict(window, verbose=0)[0][0])
            predictions_scaled.append(pred_scaled)
            extended.append(pred_scaled)

        preds = self._scaler.inverse_transform(
            np.array(predictions_scaled).reshape(-1, 1)
        ).flatten()
        return np.maximum(0, preds)

    def residuals(self, series: np.ndarray) -> np.ndarray:
        if self._in_sample is None:
            return np.zeros_like(series)
        return series - self._in_sample[:len(series)]


# ---------------------------------------------------------------------------
# Layer 3 — Ensemble
# ---------------------------------------------------------------------------

def compute_ensemble_weights(
    performances: Dict[ModelName, float],
) -> Dict[ModelName, float]:
    """
    Compute ensemble weights as softmax of inverse MAPE scores.
    Lower MAPE → higher weight.
    Handles infinite/zero MAPE gracefully.
    """
    inv_mape: Dict[ModelName, float] = {}
    for name, m in performances.items():
        if m is None or m <= 0 or math.isinf(m) or math.isnan(m):
            inv_mape[name] = 0.0
        else:
            inv_mape[name] = 1.0 / m

    total = sum(inv_mape.values())
    if total == 0:
        # Equal weights if all models failed
        n = len(performances)
        return {name: 1.0 / n for name in performances}

    return {name: v / total for name, v in inv_mape.items()}


def blend_forecasts(
    forecasts: Dict[ModelName, np.ndarray],
    weights: Dict[ModelName, float],
) -> np.ndarray:
    """Weighted combination of model forecasts."""
    if not forecasts:
        return np.array([])

    steps = len(next(iter(forecasts.values())))
    result = np.zeros(steps)
    total_weight = 0.0

    for name, fc in forecasts.items():
        w = weights.get(name, 0.0)
        if w > 0 and len(fc) == steps:
            result += w * fc
            total_weight += w

    if total_weight > 0:
        result /= total_weight

    return np.maximum(0, result)


# ---------------------------------------------------------------------------
# Model selection logic (§3.4 regional model split)
# ---------------------------------------------------------------------------

def get_primary_model_for_region(
    brand: str,
    region: Region,
    use_sarimax: bool = False,
) -> ModelName:
    """
    Implements §3.4 regional model split logic.

    Chennai:
      P1 → best statistical model (SARIMA or SARIMAX if improves >5%)
      P2 → XGBoost

    Outside Chennai:
      P1 → XGBoost  (non-linear growth better captured by ML)
      P2 → XGBoost
    """
    if region == Region.CHENNAI:
        if brand == "P1":
            return ModelName.SARIMAX if use_sarimax else ModelName.SARIMA
        else:  # P2
            return ModelName.XGBOOST
    else:  # Outside Chennai or All
        return ModelName.XGBOOST


# ---------------------------------------------------------------------------
# Main Forecasting Engine
# ---------------------------------------------------------------------------

class ForecastingEngine:
    """
    AC Industries EBITDA Platform — Forecasting Engine (Session 3).

    Entry points:
      run_forecast(company_id, brand, region, series_dates, series_values, ...)
        → ForecastBundle

      run_company_forecast(company_id, sales_data, ...)
        → CompanyForecastResult
    """

    def __init__(
        self,
        forecast_horizon: int = FORECAST_HORIZON_MONTHS,
        reeval_quarterly: bool = True,
    ):
        self.forecast_horizon = forecast_horizon
        self.reeval_quarterly = reeval_quarterly

    def _evaluate_all_models(
        self,
        series: np.ndarray,
        test_size: int = 3,
    ) -> Dict[ModelName, Dict[str, float]]:
        """
        Walk-forward evaluation of all models on hold-out test_size periods.
        Returns {model_name: {mape, mae, rmse}}.
        """
        if len(series) < test_size + 12:
            test_size = max(1, len(series) - 12)

        train = series[:-test_size]
        test = series[-test_size:]
        results: Dict[ModelName, Dict[str, float]] = {}

        model_classes = [
            (ModelName.SARIMA,         lambda: SARIMAModel().fit(train)),
            (ModelName.HOLT_WINTERS,   lambda: HoltWintersModel().fit(train)),
            (ModelName.SIMPLE_ES,      lambda: SimpleExponentialSmoothing().fit(train)),
            (ModelName.DOUBLE_ES,      lambda: DoubleExponentialSmoothing().fit(train)),
            (ModelName.RANDOM_FOREST,  lambda: MLForecaster(ModelName.RANDOM_FOREST).fit(train)),
            (ModelName.GRADIENT_BOOST, lambda: MLForecaster(ModelName.GRADIENT_BOOST).fit(train)),
            (ModelName.RIDGE,          lambda: MLForecaster(ModelName.RIDGE).fit(train)),
            (ModelName.LASSO,          lambda: MLForecaster(ModelName.LASSO).fit(train)),
            (ModelName.SVR,            lambda: MLForecaster(ModelName.SVR).fit(train)),
            (ModelName.XGBOOST,        lambda: MLForecaster(ModelName.XGBOOST).fit(train)),
            (ModelName.LSTM,           lambda: LSTMForecaster().fit(train)),
        ]

        for name, build_fn in model_classes:
            try:
                m = build_fn()
                pred = m.forecast(test_size)
                results[name] = {
                    "mape": mape(test, pred),
                    "mae":  mae(test, pred),
                    "rmse": rmse(test, pred),
                }
            except Exception as e:
                logger.warning(f"Model {name} evaluation failed: {e}")
                results[name] = {"mape": float("inf"), "mae": float("inf"), "rmse": float("inf")}

        return results

    def _select_baseline(
        self,
        company_id: str,
        brand: str,
        region: Region,
        series: np.ndarray,
        eval_results: Dict[ModelName, Dict[str, float]],
        exog: Optional[ExternalVariables] = None,
    ) -> ModelSelectionResult:
        """
        Auto-select best statistical baseline (§3.2):
          - Best AIC + lowest MAPE wins from SARIMA/HW/SimpleES/DoubleES
          - If <24 months: use Holt-Winters
          - Test SARIMAX improvement: use if MAPE improves >5%
        """
        history_months = len(series)
        fallback_to_hw = history_months < MIN_HISTORY_MONTHS_SARIMA

        stat_models = [ModelName.SARIMA, ModelName.HOLT_WINTERS,
                       ModelName.SIMPLE_ES, ModelName.DOUBLE_ES]

        if fallback_to_hw:
            selected = ModelName.HOLT_WINTERS
        else:
            # Pick statistical model with lowest MAPE
            stat_scores = {m: eval_results[m]["mape"] for m in stat_models
                          if m in eval_results}
            selected = min(stat_scores, key=lambda m: stat_scores[m])

        baseline_mape = eval_results.get(selected, {}).get("mape", float("inf"))

        # Test SARIMAX improvement
        use_sarimax = False
        sarimax_mape = None
        sarima_aic = None

        if (not fallback_to_hw and exog is not None and exog.has_data()
                and STATSMODELS_AVAILABLE):
            try:
                sarima = SARIMAModel()
                sarima.fit(series[:-3])
                sarima_aic = sarima.best_aic

                periods = [f"{2023 + i // 12}-{(i % 12) + 1:02d}"
                           for i in range(len(series))]
                exog_matrix = exog.to_regressor_matrix(periods)

                if exog_matrix is not None:
                    exog_arr = np.array(exog_matrix)
                    sarimax = SARIMAXModel(sarima)
                    sarimax.fit(series[:-3], exog_arr[:-3])
                    sarimax_pred = sarimax.forecast(3, exog_arr[-3:])
                    sarimax_mape = mape(series[-3:], sarimax_pred)

                    improvement = (baseline_mape - sarimax_mape) / baseline_mape
                    if improvement > SARIMAX_IMPROVEMENT_THRESHOLD:
                        use_sarimax = True
                        selected = ModelName.SARIMA  # SARIMAX wraps SARIMA
            except Exception as e:
                logger.warning(f"SARIMAX evaluation failed: {e}")

        sarima_order = None
        if STATSMODELS_AVAILABLE and not fallback_to_hw:
            try:
                s = SARIMAModel()
                s.fit(series)
                sarima_order = (s.best_order, s.best_seasonal_order) if s.best_order else None
            except Exception:
                pass

        return ModelSelectionResult(
            company_id=company_id,
            brand=brand,
            region=region,
            selected_baseline=selected,
            sarima_order=sarima_order,
            use_sarimax=use_sarimax,
            history_months=history_months,
            fallback_to_hw=fallback_to_hw,
            aic=sarima_aic,
            baseline_mape=baseline_mape,
            sarimax_mape=sarimax_mape,
            evaluated_at=date.today(),
        )

    def run_forecast(
        self,
        company_id: str,
        brand: str,
        region: Region,
        series_dates: List[date],
        series_values: List[float],
        exog: Optional[ExternalVariables] = None,
        sku_name_map: Optional[dict] = None,
        holiday_dates: Optional[List[date]] = None,
    ) -> ForecastBundle:
        """
        Run the full forecasting engine for one brand × region combination.

        Parameters
        ----------
        series_dates  : Monthly dates (first of each month)
        series_values : Monthly volumes in MT (parallel to series_dates)
        exog          : External variables for SARIMAX (all None = not used)
        sku_name_map  : (brand, size_mm) → display name for disaggregation
        holiday_dates : Production/sales holidays to exclude from daily plan
        """
        series = np.array(series_values, dtype=float)
        n = len(series)
        warnings_list: List[str] = []

        if n < 6:
            warnings_list.append(
                f"Only {n} months of history — forecasts will be low confidence. "
                "Minimum recommended: 24 months for SARIMA, 12 for Holt-Winters."
            )

        today = date.today()
        forecast_start = date(
            today.year + (today.month) // 12,
            (today.month % 12) + 1,
            1,
        )

        # --- Step 1: Evaluate all models ---
        eval_results = self._evaluate_all_models(series, test_size=min(3, n - 6))

        # --- Step 2: Model selection ---
        selection = self._select_baseline(
            company_id, brand, region, series, eval_results, exog
        )

        # --- Step 3: Fit all models on full history ---
        fitted_models: Dict[ModelName, Any] = {}

        # Statistical
        sarima = SARIMAModel()
        sarima.fit(series)
        fitted_models[ModelName.SARIMA] = sarima

        if selection.use_sarimax and exog is not None:
            periods = [f"{d.year}-{d.month:02d}" for d in series_dates]
            exog_matrix = exog.to_regressor_matrix(periods)
            exog_arr = np.array(exog_matrix) if exog_matrix else None
            sarimax = SARIMAXModel(sarima)
            sarimax.fit(series, exog_arr)
            fitted_models[ModelName.SARIMAX] = sarimax

        hw = HoltWintersModel()
        hw.fit(series)
        fitted_models[ModelName.HOLT_WINTERS] = hw

        simple_es = SimpleExponentialSmoothing()
        simple_es.fit(series)
        fitted_models[ModelName.SIMPLE_ES] = simple_es

        double_es = DoubleExponentialSmoothing()
        double_es.fit(series)
        fitted_models[ModelName.DOUBLE_ES] = double_es

        # ML
        for ml_name in [
            ModelName.XGBOOST, ModelName.RANDOM_FOREST, ModelName.GRADIENT_BOOST,
            ModelName.RIDGE, ModelName.LASSO, ModelName.SVR,
        ]:
            try:
                fitted_models[ml_name] = MLForecaster(ml_name).fit(series)
            except Exception as e:
                logger.warning(f"{ml_name} fit failed: {e}")

        lstm = LSTMForecaster()
        lstm.fit(series)
        fitted_models[ModelName.LSTM] = lstm

        # --- Step 4: Generate 12-month forecasts from all models ---
        all_forecasts: Dict[ModelName, np.ndarray] = {}
        all_monthly_points: List[ForecastPoint] = []

        for name, model in fitted_models.items():
            try:
                if name == ModelName.SARIMAX and exog is not None:
                    future_periods = [
                        f"{(forecast_start.year + (forecast_start.month + i - 2) // 12)}"
                        f"-{((forecast_start.month + i - 2) % 12) + 1:02d}"
                        for i in range(self.forecast_horizon)
                    ]
                    exog_future_matrix = exog.to_regressor_matrix(future_periods)
                    exog_future = np.array(exog_future_matrix) if exog_future_matrix else None
                    fc = model.forecast(self.forecast_horizon, exog_future)
                else:
                    fc = model.forecast(self.forecast_horizon)

                all_forecasts[name] = fc
                residuals = model.residuals(series) if hasattr(model, "residuals") else np.zeros(len(series))
                ci_low, ci_high = compute_confidence_interval(residuals, fc)

                for i, val in enumerate(fc):
                    period_date = date(
                        forecast_start.year + (forecast_start.month + i - 2) // 12,
                        ((forecast_start.month + i - 2) % 12) + 1,
                        1,
                    )
                    all_monthly_points.append(ForecastPoint(
                        company_id=company_id,
                        model_name=name,
                        forecast_date=today,
                        period=period_date,
                        granularity=ForecastGranularity.MONTHLY,
                        brand=brand,
                        sku_name=None,
                        region=region,
                        qty_forecast=round(float(val), 2),
                        confidence_low=round(float(ci_low[i]), 2),
                        confidence_high=round(float(ci_high[i]), 2),
                    ))
            except Exception as e:
                logger.warning(f"Forecast generation failed for {name}: {e}")
                warnings_list.append(f"Model {name.value} forecast failed: {str(e)}")

        # --- Step 5: Ensemble weights from rolling MAPE ---
        mape_scores = {name: eval_results.get(name, {}).get("mape", float("inf"))
                       for name in fitted_models}
        weights = compute_ensemble_weights(mape_scores)
        ensemble_fc = blend_forecasts(all_forecasts, weights)

        # Ensemble confidence interval
        # Build ensemble residuals from all fitted models weighted by their weights
        residual_lists = []
        for name, model in fitted_models.items():
            try:
                res = model.residuals(series)
                w = weights.get(name, 0.0)
                if w > 0 and len(res) == len(series):
                    residual_lists.append(res * w)
            except Exception:
                pass
        if residual_lists:
            ens_residuals = np.sum(residual_lists, axis=0)
        else:
            ens_residuals = np.zeros(len(series))
        ens_ci_low, ens_ci_high = compute_confidence_interval(ens_residuals, ensemble_fc)

        ensemble_points: List[ForecastPoint] = []
        for i, val in enumerate(ensemble_fc):
            period_date = date(
                forecast_start.year + (forecast_start.month + i - 2) // 12,
                ((forecast_start.month + i - 2) % 12) + 1,
                1,
            )
            ensemble_points.append(ForecastPoint(
                company_id=company_id,
                model_name=ModelName.ENSEMBLE,
                forecast_date=today,
                period=period_date,
                granularity=ForecastGranularity.MONTHLY,
                brand=brand,
                sku_name=None,
                region=region,
                qty_forecast=round(float(val), 2),
                confidence_low=round(float(ens_ci_low[i]), 2),
                confidence_high=round(float(ens_ci_high[i]), 2),
            ))

        # --- Step 6: Weekly disaggregation of ensemble ---
        weekly_points: List[ForecastPoint] = []
        for i, ep in enumerate(ensemble_points):
            weekly_skus = disaggregate_monthly_to_weekly(
                year=ep.period.year,
                month=ep.period.month,
                brand=brand,
                region=region.value,
                monthly_qty_tons=ep.qty_forecast,
                sku_name_map=sku_name_map,
            )
            for ws in weekly_skus:
                weekly_points.append(ForecastPoint(
                    company_id=company_id,
                    model_name=ModelName.ENSEMBLE,
                    forecast_date=today,
                    period=ws.week_start,
                    granularity=ForecastGranularity.WEEKLY,
                    brand=brand,
                    sku_name=ws.sku_name,
                    region=region,
                    qty_forecast=ws.qty_tons,
                    confidence_low=None,
                    confidence_high=None,
                ))

        # --- Step 7: Build ModelPerformance objects ---
        performances: List[ModelPerformance] = []
        for name, m_eval in eval_results.items():
            performances.append(ModelPerformance(
                company_id=company_id,
                model_name=name,
                eval_month=date(today.year, today.month, 1),
                brand=brand,
                region=region,
                mape=round(m_eval["mape"], 4),
                mae=round(m_eval["mae"], 2),
                rmse=round(m_eval["rmse"], 2),
                weight=round(weights.get(name, 0.0), 6),
                n_periods=min(3, n - 6),
                is_active=True,
            ))
        # Add ensemble
        ensemble_mape = float(np.mean([
            m_eval["mape"] for m_eval in eval_results.values()
            if m_eval["mape"] < float("inf")
        ])) if eval_results else float("inf")
        performances.append(ModelPerformance(
            company_id=company_id,
            model_name=ModelName.ENSEMBLE,
            eval_month=date(today.year, today.month, 1),
            brand=brand,
            region=region,
            mape=round(ensemble_mape, 4),
            mae=0.0,
            rmse=0.0,
            weight=1.0,
            n_periods=min(3, n - 6),
            is_active=True,
        ))

        return ForecastBundle(
            company_id=company_id,
            brand=brand,
            region=region,
            forecast_date=today,
            history_months=n,
            model_selection=selection,
            model_performances=performances,
            monthly_forecasts=all_monthly_points,
            ensemble_forecast=ensemble_points,
            weekly_disagg=weekly_points,
            warnings=warnings_list,
        )

    def run_company_forecast(
        self,
        company_id: str,
        brand_region_series: Dict[tuple, tuple],
        exog: Optional[ExternalVariables] = None,
        sku_name_map: Optional[dict] = None,
        holiday_dates: Optional[List[date]] = None,
    ) -> CompanyForecastResult:
        """
        Run forecasts for all brand × region combinations for a company.

        Parameters
        ----------
        brand_region_series : {(brand, region_str): (dates, values)} mapping
          e.g. {("P1", "Chennai"): ([date(...),...], [1200, 1350, ...])}
        """
        today = date.today()
        bundles: List[ForecastBundle] = []
        errors: List[str] = []

        for (brand, region_str), (dates, values) in brand_region_series.items():
            try:
                region = Region(region_str)
            except ValueError:
                region = Region.ALL

            try:
                bundle = self.run_forecast(
                    company_id=company_id,
                    brand=brand,
                    region=region,
                    series_dates=dates,
                    series_values=values,
                    exog=exog,
                    sku_name_map=sku_name_map,
                    holiday_dates=holiday_dates,
                )
                bundles.append(bundle)
            except Exception as e:
                msg = f"Forecast failed for {brand}/{region_str}: {str(e)}"
                logger.error(msg)
                errors.append(msg)

        return CompanyForecastResult(
            company_id=company_id,
            forecast_date=today,
            bundles=bundles,
            errors=errors,
        )
