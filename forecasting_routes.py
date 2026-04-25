"""
forecasting_routes.py
---------------------
FastAPI routes for the AC Industries Forecasting Engine.
Follows the same pattern as Sessions 1 & 2 (api/main.py).

Endpoints:
  POST /forecast/run           — Run full forecast for a company/brand/region
  POST /forecast/company       — Run all brand×region combos for a company
  GET  /forecast/history/{id}  — Retrieve stored forecasts from DB
  GET  /forecast/performance   — Model performance / ensemble weights
  POST /forecast/evaluate      — Trigger model re-evaluation on demand
  GET  /forecast/model-select  — View current model selection config

Integration note:
  These routes currently use in-memory storage and synthetic data.
  Wire up to the Supabase `forecasts` and `model_performance` tables
  by replacing the stub DB calls (marked WIRE-UP) with actual queries.
"""

from __future__ import annotations

import logging
import sys
import os
from datetime import date, datetime
from typing import Dict, List, Optional, Any

# Add forecaster directory to path (same package in production)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Lazy import so routes file can be imported even when forecaster deps are loading
def _get_engine():
    from forecaster.forecasting_engine import ForecastingEngine
    return ForecastingEngine()

def _get_synth():
    from forecaster.synthetic_data import (
        generate_synthetic_sales,
        build_monthly_brand_series,
    )
    return generate_synthetic_sales, build_monthly_brand_series

def _get_models():
    from forecaster.forecast_models import ExternalVariables, Region
    return ExternalVariables, Region


router = APIRouter(prefix="/forecast", tags=["Forecasting Engine"])

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class TimeSeriesInput(BaseModel):
    """Manual time series input — dates and monthly volumes."""
    dates:  List[str]  = Field(..., description="ISO date strings, first of each month")
    values: List[float] = Field(..., description="Monthly volume in MT")

    class Config:
        json_schema_extra = {
            "example": {
                "dates":  ["2023-01-01", "2023-02-01", "2023-03-01"],
                "values": [1200.5, 1350.2, 1180.0],
            }
        }


class ExternalVariablesInput(BaseModel):
    """Optional external regressors for SARIMAX (§3.5). All fields optional."""
    gst_collections_cr:    Optional[Dict[str, float]] = None
    iip_steel_index:       Optional[Dict[str, float]] = None
    chennai_price_per_ton: Optional[Dict[str, float]] = None
    market_price_index:    Optional[Dict[str, float]] = None
    export_value_cr:       Optional[Dict[str, float]] = None
    import_value_cr:       Optional[Dict[str, float]] = None


class ForecastRequest(BaseModel):
    """Run a forecast for a single brand × region combination."""
    company_id:    str   = Field(..., example="AC001")
    brand:         str   = Field(..., example="P1", description="P1 or P2")
    region:        str   = Field(..., example="Chennai",
                                 description="'Chennai' or 'Outside Chennai'")
    series:        TimeSeriesInput
    exog:          Optional[ExternalVariablesInput] = None
    horizon_months: int  = Field(12, ge=1, le=24)


class CompanyForecastRequest(BaseModel):
    """
    Run forecasts for all brand × region combinations for a company.
    Uses synthetic data if no series provided (dev/demo mode).
    """
    company_id:      str  = Field(..., example="AC001")
    use_synthetic:   bool = Field(True,  description="Use synthetic data (dev mode)")
    synthetic_start: Optional[str] = Field("2023-01-01", description="ISO date")
    synthetic_end:   Optional[str] = Field("2025-03-31", description="ISO date")
    exog:            Optional[ExternalVariablesInput] = None
    horizon_months:  int  = Field(12, ge=1, le=24)


class ModelRevalRequest(BaseModel):
    """Trigger model re-evaluation on demand."""
    company_id: str
    brand:      str
    region:     str
    reason:     Optional[str] = "manual"


# ---------------------------------------------------------------------------
# In-memory store (WIRE-UP: replace with Supabase queries)
# ---------------------------------------------------------------------------
_forecast_store: Dict[str, Any] = {}
_performance_store: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/run", summary="Run forecast — single brand × region")
async def run_forecast(req: ForecastRequest):
    """
    Run the full 12-model ensemble forecast for one brand × region combination.

    - Evaluates all models on hold-out data
    - Auto-selects best statistical baseline (SARIMA / Holt-Winters)
    - Tests SARIMAX if external variables are provided
    - Returns 12-month ensemble + weekly SKU disaggregation
    """
    try:
        ExternalVariables, Region = _get_models()
        engine = _get_engine()

        # Parse dates
        try:
            dates = [date.fromisoformat(d) for d in req.series.dates]
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid date format: {e}")

        if len(dates) != len(req.series.values):
            raise HTTPException(
                status_code=422,
                detail="dates and values must have the same length"
            )

        # Build ExternalVariables
        exog = None
        if req.exog is not None:
            exog = ExternalVariables(
                gst_collections_cr=req.exog.gst_collections_cr,
                iip_steel_index=req.exog.iip_steel_index,
                chennai_price_per_ton=req.exog.chennai_price_per_ton,
                market_price_index=req.exog.market_price_index,
                export_value_cr=req.exog.export_value_cr,
                import_value_cr=req.exog.import_value_cr,
            )

        try:
            region = Region(req.region)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid region '{req.region}'. Use 'Chennai' or 'Outside Chennai'."
            )

        bundle = engine.run_forecast(
            company_id=req.company_id,
            brand=req.brand,
            region=region,
            series_dates=dates,
            series_values=req.series.values,
            exog=exog,
        )

        result = bundle.to_dict()

        # WIRE-UP: persist to Supabase `forecasts` table
        store_key = f"{req.company_id}:{req.brand}:{req.region}"
        _forecast_store[store_key] = result

        return {
            "status": "ok",
            "company_id": req.company_id,
            "brand": req.brand,
            "region": req.region,
            "history_months": bundle.history_months,
            "model_selected": bundle.model_selection.selected_baseline.value,
            "use_sarimax": bundle.model_selection.use_sarimax,
            "forecast_horizon": len(bundle.ensemble_forecast),
            "warnings": bundle.warnings,
            "forecast": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Forecast run failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/company", summary="Run all brand × region forecasts for a company")
async def run_company_forecast(req: CompanyForecastRequest):
    """
    Run forecasts for all brand × region combinations.
    In dev mode (use_synthetic=True): generates AC Industries-shaped synthetic data.
    In production: pass brand_region_series from the sales_transactions table.
    """
    try:
        ExternalVariables, Region = _get_models()
        engine = _get_engine()

        brand_region_series: Dict[tuple, tuple] = {}

        if req.use_synthetic:
            generate_synthetic_sales, build_monthly_brand_series = _get_synth()
            start = date.fromisoformat(req.synthetic_start or "2023-01-01")
            end   = date.fromisoformat(req.synthetic_end   or "2025-03-31")

            rows = generate_synthetic_sales(
                company_id=req.company_id,
                start_date=start,
                end_date=end,
            )

            # Build all 4 combinations: P1/P2 × Chennai/Outside Chennai
            for brand in ("P1", "P2"):
                for region_str in ("Chennai", "Outside Chennai"):
                    dates, values = build_monthly_brand_series(rows, brand, region_str)
                    if dates:
                        brand_region_series[(brand, region_str)] = (dates, values)
        else:
            # WIRE-UP: query sales_transactions for each brand × region
            raise HTTPException(
                status_code=501,
                detail="Live data mode not yet wired up. Pass use_synthetic=true for dev/demo."
            )

        exog = None
        if req.exog is not None:
            exog = ExternalVariables(
                gst_collections_cr=req.exog.gst_collections_cr,
                iip_steel_index=req.exog.iip_steel_index,
                chennai_price_per_ton=req.exog.chennai_price_per_ton,
                market_price_index=req.exog.market_price_index,
                export_value_cr=req.exog.export_value_cr,
                import_value_cr=req.exog.import_value_cr,
            )

        result = engine.run_company_forecast(
            company_id=req.company_id,
            brand_region_series=brand_region_series,
            exog=exog,
        )

        # WIRE-UP: persist all ForecastPoint objects to Supabase `forecasts` table

        summary = {
            "status": "ok",
            "company_id": req.company_id,
            "forecast_date": result.forecast_date.isoformat(),
            "bundles_computed": len(result.bundles),
            "errors": result.errors,
            "bundles": []
        }

        for b in result.bundles:
            summary["bundles"].append({
                "brand": b.brand,
                "region": b.region.value,
                "history_months": b.history_months,
                "model_selected": b.model_selection.selected_baseline.value,
                "use_sarimax": b.model_selection.use_sarimax,
                "ensemble_12m_forecast_mt": [
                    {"period": ep.period.isoformat(), "qty_mt": ep.qty_forecast}
                    for ep in b.ensemble_forecast
                ],
                "best_model_mape": min(
                    (p.mape for p in b.model_performances
                     if p.model_name.value != "ensemble" and p.mape < float("inf")),
                    default=None
                ),
                "warnings": b.warnings,
            })

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Company forecast failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance", summary="Model performance and ensemble weights")
async def get_model_performance(
    company_id: str = Query(..., example="AC001"),
    brand:      str = Query(..., example="P1"),
    region:     str = Query("Chennai", example="Chennai"),
):
    """
    Return model accuracy metrics and current ensemble weights for a
    company / brand / region combination.
    WIRE-UP: replace _performance_store with Supabase `model_performance` query.
    """
    key = f"{company_id}:{brand}:{region}"
    stored = _forecast_store.get(key)

    if stored is None:
        raise HTTPException(
            status_code=404,
            detail=f"No forecast found for {company_id}/{brand}/{region}. "
                   "Run /forecast/run or /forecast/company first."
        )

    performances = stored.get("model_performances", [])
    return {
        "company_id": company_id,
        "brand": brand,
        "region": region,
        "model_performances": sorted(
            performances,
            key=lambda p: p.get("mape", float("inf"))
        ),
    }


@router.get("/model-select", summary="View current model selection config")
async def get_model_selection(
    company_id: str = Query(..., example="AC001"),
    brand:      str = Query(..., example="P1"),
    region:     str = Query("Chennai", example="Chennai"),
):
    """
    Return the current auto-selected model config for a company/brand/region.
    WIRE-UP: query model_config table (§5.3).
    """
    key = f"{company_id}:{brand}:{region}"
    stored = _forecast_store.get(key)

    if stored is None:
        raise HTTPException(
            status_code=404,
            detail=f"No forecast config found. Run /forecast/run first."
        )

    return {
        "company_id": company_id,
        "brand": brand,
        "region": region,
        "model_selection": stored.get("model_selection", {}),
    }


@router.post("/evaluate", summary="Trigger on-demand model re-evaluation")
async def trigger_evaluation(req: ModelRevalRequest):
    """
    Re-evaluate model selection for a company/brand/region on demand.
    Normally runs quarterly (§3.2). This endpoint supports manual triggers
    (e.g. after a major market shift, or after a new data upload).

    WIRE-UP: pull latest 24 months from sales_transactions and re-run engine.
    """
    return {
        "status": "evaluation_queued",
        "company_id": req.company_id,
        "brand": req.brand,
        "region": req.region,
        "reason": req.reason,
        "note": "WIRE-UP: Queue a background task to pull latest 24 months "
                "from sales_transactions and call engine.run_forecast(). "
                "Currently returns stub response.",
        "queued_at": datetime.utcnow().isoformat(),
    }


@router.get("/health", summary="Forecasting engine health check")
async def forecast_health():
    """Check which model libraries are available."""
    try:
        from forecaster.forecasting_engine import (
            STATSMODELS_AVAILABLE, XGBOOST_AVAILABLE, TENSORFLOW_AVAILABLE
        )
    except ImportError:
        STATSMODELS_AVAILABLE = False
        XGBOOST_AVAILABLE = False
        TENSORFLOW_AVAILABLE = False

    return {
        "status": "ok",
        "libraries": {
            "statsmodels": STATSMODELS_AVAILABLE,
            "xgboost":     XGBOOST_AVAILABLE,
            "tensorflow":  TENSORFLOW_AVAILABLE,
            "sklearn":     True,    # always available (hard dependency)
            "numpy":       True,
            "pandas":      True,
        },
        "models_available": {
            "sarima_sarimax":    STATSMODELS_AVAILABLE,
            "holt_winters":      True,  # manual fallback always works
            "simple_double_es":  True,
            "xgboost":           True,  # GradientBoosting substitute when not installed
            "random_forest":     True,
            "gradient_boosting": True,
            "ridge_lasso":       True,
            "svr":               True,
            "lstm":              True,  # GradientBoosting substitute when TF not installed
        },
        "note": (
            "Install statsmodels for full SARIMA/SARIMAX. "
            "Install xgboost for XGBoost (GradientBoosting used as substitute). "
            "Install tensorflow for LSTM (GradientBoosting used as substitute)."
        ),
    }
