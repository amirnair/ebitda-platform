"""
forecast_models.py
------------------
Typed output dataclasses for the AC Industries Forecasting Engine.
Mirrors the pattern established in Sessions 1 & 2 (connector_models.py,
aggregation_models.py) — every output is a typed dataclass, serialisable
to dict/JSON for the FastAPI layer.

DB target tables (§7.2):
  forecasts          — all model outputs (one row per model × period × sku)
  model_performance  — rolling MAPE tracking, ensemble weights
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional, List, Dict, Any
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ForecastGranularity(str, Enum):
    DAILY   = "daily"
    WEEKLY  = "weekly"
    MONTHLY = "monthly"


class ModelName(str, Enum):
    # Statistical baseline layer
    SARIMA          = "sarima"
    SARIMAX         = "sarimax"
    HOLT_WINTERS    = "holt_winters"
    SIMPLE_ES       = "simple_es"
    DOUBLE_ES       = "double_es"
    # ML challenger layer
    XGBOOST         = "xgboost"
    RANDOM_FOREST   = "random_forest"
    GRADIENT_BOOST  = "gradient_boost"
    RIDGE           = "ridge"
    LASSO           = "lasso"
    SVR             = "svr"
    LSTM            = "lstm"
    # Meta
    ENSEMBLE        = "ensemble"


class Region(str, Enum):
    CHENNAI         = "Chennai"
    OUTSIDE_CHENNAI = "Outside Chennai"
    ALL             = "All"


# ---------------------------------------------------------------------------
# Core forecast output
# ---------------------------------------------------------------------------

@dataclass
class ForecastPoint:
    """
    Single forecast value for one period.
    Maps directly to the `forecasts` DB table (§7.2).
    """
    company_id:       str
    model_name:       ModelName
    forecast_date:    date          # date the forecast was produced
    period:           date          # start of the period being forecast
    granularity:      ForecastGranularity
    brand:            str           # "P1" or "P2"
    sku_name:         Optional[str] # None for brand-level aggregates
    region:           Region
    qty_forecast:     float         # MT
    confidence_low:   Optional[float] = None   # 80% CI lower
    confidence_high:  Optional[float] = None   # 80% CI upper

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["model_name"]    = self.model_name.value
        d["granularity"]   = self.granularity.value
        d["region"]        = self.region.value
        d["forecast_date"] = self.forecast_date.isoformat()
        d["period"]        = self.period.isoformat()
        return d


@dataclass
class ModelPerformance:
    """
    Rolling accuracy metrics for one model in one evaluation period.
    Maps to `model_performance` DB table (§7.2).
    """
    company_id:     str
    model_name:     ModelName
    eval_month:     date        # first day of the month this was computed
    brand:          str
    region:         Region
    mape:           float       # Mean Absolute Percentage Error (%)
    mae:            float       # Mean Absolute Error (MT)
    rmse:           float       # Root Mean Squared Error (MT)
    weight:         float       # Ensemble weight derived from this MAPE
    n_periods:      int         # Number of periods used in evaluation
    is_active:      bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["model_name"]  = self.model_name.value
        d["region"]      = self.region.value
        d["eval_month"]  = self.eval_month.isoformat()
        return d


@dataclass
class ModelSelectionResult:
    """
    Result of auto model selection for a given company/brand/region combination.
    Stored in model_config table (§5.3).
    """
    company_id:             str
    brand:                  str
    region:                 Region
    selected_baseline:      ModelName       # Best AIC + MAPE statistical model
    sarima_order:           Optional[tuple] # (p,d,q)(P,D,Q,s) if SARIMA selected
    use_sarimax:            bool            # True if SARIMAX improved MAPE >5%
    history_months:         int             # Months of data available
    fallback_to_hw:         bool            # True if <24 months — Holt-Winters used
    aic:                    Optional[float]
    baseline_mape:          float
    sarimax_mape:           Optional[float]
    evaluated_at:           date

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["selected_baseline"] = self.selected_baseline.value
        d["region"]            = self.region.value
        d["evaluated_at"]      = self.evaluated_at.isoformat()
        if self.sarima_order:
            d["sarima_order"]  = list(self.sarima_order)
        return d


@dataclass
class ForecastBundle:
    """
    Complete forecast output for one company/brand/region combination.
    Contains outputs from all 12 models + ensemble.
    """
    company_id:           str
    brand:                str
    region:               Region
    forecast_date:        date
    history_months:       int
    model_selection:      ModelSelectionResult
    model_performances:   List[ModelPerformance]
    monthly_forecasts:    List[ForecastPoint]   # 12-month horizon, all models
    ensemble_forecast:    List[ForecastPoint]   # Final ensemble output
    weekly_disagg:        List[ForecastPoint]   # Weekly breakdown of ensemble
    warnings:             List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company_id":        self.company_id,
            "brand":             self.brand,
            "region":            self.region.value,
            "forecast_date":     self.forecast_date.isoformat(),
            "history_months":    self.history_months,
            "model_selection":   self.model_selection.to_dict(),
            "model_performances": [p.to_dict() for p in self.model_performances],
            "monthly_forecasts": [f.to_dict() for f in self.monthly_forecasts],
            "ensemble_forecast": [f.to_dict() for f in self.ensemble_forecast],
            "weekly_disagg":     [f.to_dict() for f in self.weekly_disagg],
            "warnings":          self.warnings,
        }


@dataclass
class CompanyForecastResult:
    """
    Top-level output: all brand × region combinations for one company.
    This is what the FastAPI /forecast endpoint returns.
    """
    company_id:   str
    forecast_date: date
    bundles:      List[ForecastBundle]
    errors:       List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company_id":    self.company_id,
            "forecast_date": self.forecast_date.isoformat(),
            "bundles":       [b.to_dict() for b in self.bundles],
            "errors":        self.errors,
        }


# ---------------------------------------------------------------------------
# External variable interface — stub for SARIMAX (§3.5)
# ---------------------------------------------------------------------------

@dataclass
class ExternalVariables:
    """
    Optional external regressors for SARIMAX.
    All fields are None until live data feeds are wired up (future session).
    The forecasting engine accepts this object and uses whichever fields
    are non-None. Adding a new variable later requires no engine changes —
    just populate the field and ensure the SARIMAX regressor matrix is updated.

    Sources (§3.5):
      gst_collections_cr   : GST Collections ₹ CR — lag 1 month
      iip_steel_index      : IIP Steel Index — lag 1 month
      chennai_price_per_ton: Chennai TMT market price ₹/ton — lag 0
      market_price_index   : Broader market index — lag 0
      export_value_cr      : Steel export value ₹ CR — lag 1–2 months
      import_value_cr      : Steel import value ₹ CR — lag 1–2 months
    """
    # Keys are date strings "YYYY-MM" → float value
    gst_collections_cr:    Optional[Dict[str, float]] = None
    iip_steel_index:       Optional[Dict[str, float]] = None
    chennai_price_per_ton: Optional[Dict[str, float]] = None
    market_price_index:    Optional[Dict[str, float]] = None
    export_value_cr:       Optional[Dict[str, float]] = None
    import_value_cr:       Optional[Dict[str, float]] = None

    def has_data(self) -> bool:
        """Returns True if at least one variable is populated."""
        return any([
            self.gst_collections_cr,
            self.iip_steel_index,
            self.chennai_price_per_ton,
            self.market_price_index,
            self.export_value_cr,
            self.import_value_cr,
        ])

    def to_regressor_matrix(
        self,
        periods: List[str],
        lag: int = 0,
    ) -> Optional[List[List[float]]]:
        """
        Build aligned regressor matrix for SARIMAX.
        Returns None if no external data is available.
        periods: list of "YYYY-MM" strings for the forecast/history window.
        lag: number of periods to shift (positive = look back).
        """
        if not self.has_data():
            return None

        series_list = []
        for series in [
            self.gst_collections_cr,
            self.iip_steel_index,
            self.chennai_price_per_ton,
            self.market_price_index,
            self.export_value_cr,
            self.import_value_cr,
        ]:
            if series is None:
                continue
            # Align to requested periods, shift by lag, fill missing with 0
            lagged_periods = periods[:len(periods) - lag] if lag > 0 else periods
            values = [series.get(p, 0.0) for p in lagged_periods]
            if lag > 0:
                values = [0.0] * lag + values
            series_list.append(values[:len(periods)])

        if not series_list:
            return None

        # Transpose: list of [var1, var2, ...] per period
        return [list(row) for row in zip(*series_list)]
