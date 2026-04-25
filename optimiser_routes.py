"""
optimiser_routes.py
-------------------
FastAPI layer for the Production Optimiser (Session 4).

Endpoints:
    POST /optimiser/daily-plan           Generate daily mill plan
    POST /optimiser/daily-plan/batch     Batch generate plans for a date range
    GET  /optimiser/sku-capacity         Return SKU capacity master
    GET  /optimiser/billet-types         Return billet type → SKU mapping
    GET  /optimiser/health               Health check

Request/Response models use Pydantic for validation and serialisation.
Same pattern as Sessions 1–3 (connector_routes, aggregation_routes, forecasting_routes).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from optimiser.production_plan import generate_daily_plan
from optimiser.sku_capacity import (
    SKU_CAPACITY,
    ALL_SKU_CODES,
    STANDARD_RUNTIME_HOURS,
    CHANGEOVER_HOURS,
    ROLLING_FACTOR,
)
from optimiser.billet_engine import BILLET_TYPE_TO_SKUS, ALL_BILLET_TYPES

router = APIRouter(prefix="/optimiser", tags=["Production Optimiser"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class DailyPlanRequest(BaseModel):
    company_id: str = Field(..., example="AC001")
    planning_date: date = Field(..., example="2025-05-01")
    fg_stocks: Optional[Dict[str, float]] = Field(
        default=None,
        description="Current FG stock: sku_code → MT. Omit to default to zero.",
        example={"P1-SKU-16": 25.0, "P1-SKU-10": 18.0},
    )
    billet_stocks: Optional[Dict[str, float]] = Field(
        default=None,
        description="Current billet stock: billet_type → MT. Omit for auto-default.",
        example={"P1-6M": 500.0, "P2-6M": 200.0},
    )
    previous_sku: Optional[str] = Field(
        default=None,
        description="Last SKU rolled on mill (for changeover calculation).",
        example="P1-SKU-16",
    )
    runtime_hours: float = Field(
        default=STANDARD_RUNTIME_HOURS,
        ge=1.0, le=24.0,
        description="Available mill hours today (default 16hrs, §1.5).",
    )
    demand_override: Optional[Dict[str, float]] = Field(
        default=None,
        description=(
            "Inject real forecast demand: sku_code → MT. "
            "Wire to Session 3 forecasts table. Omit for synthetic demand."
        ),
    )


class BatchPlanRequest(BaseModel):
    company_id: str = Field(..., example="AC001")
    start_date: date = Field(..., example="2025-05-01")
    days: int = Field(default=7, ge=1, le=30, description="Number of days to plan.")
    runtime_hours: float = Field(default=STANDARD_RUNTIME_HOURS, ge=1.0, le=24.0)
    billet_stocks: Optional[Dict[str, float]] = None
    fg_stocks: Optional[Dict[str, float]] = None


class SkuPlanLineResponse(BaseModel):
    sku_code: str
    brand_code: str
    size_mm: int
    demand_mt: float
    fg_stock_opening_mt: float
    production_mt: float
    billet_required_mt: float
    runtime_hrs: float
    unmet_mt: float
    is_urgent: bool
    margin_rank: int
    sequence_position: int


class BilletDrawdownResponse(BaseModel):
    billet_type: str
    brand: str
    required_mt: float
    available_mt: float
    drawdown_mt: float
    shortfall_mt: float
    closing_stock_mt: float
    is_critical: bool


class ProcurementRecResponse(BaseModel):
    billet_type: str
    brand: str
    closing_stock_mt: float
    daily_consumption_mt: float
    days_of_stock: float
    safety_stock_mt: float
    order_quantity_mt: float
    urgency: str
    procurement_trigger: bool


class DailyPlanResponse(BaseModel):
    company_id: str
    planning_date: date
    solver_status: str
    solver_used: str

    # §4.5 fields
    p1_production_mt: float
    p2_production_mt: float
    total_production_mt: float
    billet_required_p1_mt: float
    billet_required_p2_mt: float
    mill_runtime_p1_hrs: float
    mill_runtime_p2_hrs: float
    mill_runtime_total_hrs: float
    num_sku_switches: int
    total_changeover_hrs: float
    runtime_utilisation_pct: float

    urgent_skus: List[str]
    skus_produced: List[str]
    rolling_sequence: List[str]

    plan_lines: List[SkuPlanLineResponse]
    billet_drawdowns: List[BilletDrawdownResponse]
    procurement_recommendations: List[ProcurementRecResponse]

    warnings: List[str]
    has_warnings: bool


class SkuCapacityResponse(BaseModel):
    sku_code: str
    size_mm: int
    brand_code: str
    capacity_mt_hr: float
    margin_rank: int
    billet_type: str
    billet_length_m: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plan_to_response(plan) -> DailyPlanResponse:
    s = plan.summary
    return DailyPlanResponse(
        company_id=s.company_id,
        planning_date=s.planning_date,
        solver_status=s.solver_status,
        solver_used=s.solver_used,
        p1_production_mt=s.p1_production_mt,
        p2_production_mt=s.p2_production_mt,
        total_production_mt=s.total_production_mt,
        billet_required_p1_mt=s.billet_required_p1_mt,
        billet_required_p2_mt=s.billet_required_p2_mt,
        mill_runtime_p1_hrs=s.mill_runtime_p1_hrs,
        mill_runtime_p2_hrs=s.mill_runtime_p2_hrs,
        mill_runtime_total_hrs=s.mill_runtime_total_hrs,
        num_sku_switches=s.num_sku_switches,
        total_changeover_hrs=s.total_changeover_hrs,
        runtime_utilisation_pct=s.runtime_utilisation_pct,
        urgent_skus=s.urgent_skus,
        skus_produced=s.skus_produced,
        rolling_sequence=s.rolling_sequence,
        plan_lines=[
            SkuPlanLineResponse(
                sku_code=l.sku_code,
                brand_code=l.brand_code,
                size_mm=l.size_mm,
                demand_mt=l.demand_mt,
                fg_stock_opening_mt=l.fg_stock_opening_mt,
                production_mt=l.production_mt,
                billet_required_mt=l.billet_required_mt,
                runtime_hrs=l.runtime_hrs,
                unmet_mt=l.unmet_mt,
                is_urgent=l.is_urgent,
                margin_rank=l.margin_rank,
                sequence_position=l.sequence_position,
            )
            for l in s.plan_lines
        ],
        billet_drawdowns=[
            BilletDrawdownResponse(
                billet_type=d.billet_type,
                brand=d.brand,
                required_mt=d.required_mt,
                available_mt=d.available_mt,
                drawdown_mt=d.drawdown_mt,
                shortfall_mt=d.shortfall_mt,
                closing_stock_mt=d.closing_stock_mt,
                is_critical=d.is_critical,
            )
            for d in plan.billet_report.drawdowns
        ],
        procurement_recommendations=[
            ProcurementRecResponse(
                billet_type=r.billet_type,
                brand=r.brand,
                closing_stock_mt=r.closing_stock_mt,
                daily_consumption_mt=r.daily_consumption_mt,
                days_of_stock=r.days_of_stock,
                safety_stock_mt=r.safety_stock_mt,
                order_quantity_mt=r.order_quantity_mt,
                urgency=r.urgency,
                procurement_trigger=r.procurement_trigger,
            )
            for r in plan.billet_report.recommendations
        ],
        warnings=s.alert_summary(),
        has_warnings=s.has_warnings,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/daily-plan", response_model=DailyPlanResponse, summary="Generate daily mill plan")
def daily_plan(request: DailyPlanRequest):
    """
    Generate the §4.5 Daily Decision Report for one planning day.

    The optimiser:
    1. Fetches / generates demand forecast
    2. Scores SKUs by urgency (§4.3)
    3. Runs multi-objective LP (§4.2 — all 6 objectives)
    4. Calculates billet requirements and procurement (§4.4)
    5. Returns complete §4.5 report

    Wire `demand_override` to the Session 3 forecasts table for production use.
    """
    try:
        plan = generate_daily_plan(
            company_id=request.company_id,
            planning_date=request.planning_date,
            fg_stocks=request.fg_stocks,
            billet_stocks=request.billet_stocks,
            previous_sku=request.previous_sku,
            runtime_hours=request.runtime_hours,
            demand_override=request.demand_override,
        )
        return _plan_to_response(plan)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/daily-plan/batch",
    response_model=List[DailyPlanResponse],
    summary="Generate rolling plan for a date range",
)
def batch_plan(request: BatchPlanRequest):
    """
    Generate daily plans for a rolling window (up to 30 days).
    Each day carries forward the previous day's rolling sequence as previous_sku.
    """
    if request.days > 30:
        raise HTTPException(status_code=400, detail="Maximum 30 days per batch request.")

    plans = []
    prev_sku = None
    fg_stocks = request.fg_stocks
    billet_stocks = request.billet_stocks

    for i in range(request.days):
        d = request.start_date + timedelta(days=i)
        try:
            plan = generate_daily_plan(
                company_id=request.company_id,
                planning_date=d,
                fg_stocks=fg_stocks,
                billet_stocks=billet_stocks,
                previous_sku=prev_sku,
                runtime_hours=request.runtime_hours,
            )
            # Thread previous_sku forward
            if plan.summary.rolling_sequence:
                prev_sku = plan.summary.rolling_sequence[-1]
            plans.append(_plan_to_response(plan))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Day {d}: {str(e)}")

    return plans


@router.get(
    "/sku-capacity",
    response_model=List[SkuCapacityResponse],
    summary="Return SKU capacity master",
)
def sku_capacity():
    """Return the full SKU capacity table (§1.5 Parmas values)."""
    return [
        SkuCapacityResponse(
            sku_code=rec.sku_code,
            size_mm=rec.size_mm,
            brand_code=rec.brand_code,
            capacity_mt_hr=rec.capacity_mt_hr,
            margin_rank=rec.margin_rank,
            billet_type=rec.billet_type,
            billet_length_m=rec.billet_length_m,
        )
        for rec in SKU_CAPACITY.values()
    ]


@router.get("/billet-types", summary="Return billet type to SKU mapping")
def billet_types():
    """Return §4.4 billet type → SKU mapping with rolling factor."""
    return {
        "billet_types": {
            bt: {
                "skus": skus,
                "brand": "P1" if bt.startswith("P1") else "P2",
                "rolling_factor": ROLLING_FACTOR,
            }
            for bt, skus in BILLET_TYPE_TO_SKUS.items()
        },
        "constants": {
            "rolling_factor": ROLLING_FACTOR,
            "changeover_hours": CHANGEOVER_HOURS,
            "standard_runtime_hours": STANDARD_RUNTIME_HOURS,
        },
    }


@router.get("/health", summary="Health check")
def health():
    """Session 4 optimiser health check."""
    try:
        import pulp
        solver_status = f"PuLP {pulp.__version__} — COIN-BC available"
    except ImportError:
        solver_status = "PuLP not installed — greedy heuristic mode"

    return {
        "status": "ok",
        "session": 4,
        "module": "Production Optimiser",
        "skus_loaded": len(ALL_SKU_CODES),
        "billet_types_loaded": len(ALL_BILLET_TYPES),
        "solver": solver_status,
    }
