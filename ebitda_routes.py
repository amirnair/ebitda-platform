"""
ebitda_routes.py — AC Industries EBITDA Intelligence Platform
Session 5: EBITDA Engine — FastAPI Route Layer

6 endpoints:
    GET  /ebitda/{company_id}/{period}             → EbitdaResult (single month)
    GET  /ebitda/{company_id}/rollup               → MonthlyEbitdaRollup (trend series)
    GET  /ebitda/{company_id}/{period}/sku-margins → List[SkuMarginRecord]
    POST /ebitda/{company_id}/simulate             → SimulatorResult (Screen 8)
    GET  /ebitda/{company_id}/{period}/cost-detail → ProductionCostRecord (cost breakdown)
    GET  /ebitda/health                            → health check

Pattern mirrors Sessions 1–4 route layer structure.
DB access is via dependency injection (get_db) — same pattern as optimiser_routes.py.

In production, transactions and runtime_records are loaded from:
    - sales_transactions table (revenue_engine)
    - production_plan table (cost_engine — runtime_hrs per SKU per day)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ebitda_models import (
    EbitdaResult,
    MillRuntimeRecord,
    MonthlyEbitdaRollup,
    OverheadRecord,
    SimulatorInputs,
    SimulatorResult,
    SkuMarginRecord,
)
from cost_engine import BenchmarkDefaults
from ebitda_engine import EbitdaEngine
from revenue_engine import SifTransaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ebitda", tags=["ebitda"])


# ---------------------------------------------------------------------------
# Pydantic Request/Response Models
# ---------------------------------------------------------------------------

class OverheadInput(BaseModel):
    """Client-entered overheads for a period (from Settings or API)."""
    admin_cost_inr: float = 0.0
    selling_cost_inr: float = 0.0
    depreciation_inr: float = 0.0
    interest_inr: float = 0.0
    other_overhead_inr: float = 0.0


class BenchmarkOverrideInput(BaseModel):
    """
    Optional client benchmark overrides.
    When not provided, industry defaults are used.
    Matches benchmark_config table fields (Section 5.3).
    """
    power_units_per_hr: Optional[float] = None
    power_rate_inr_per_unit: Optional[float] = None
    fuel_cost_per_hr_inr: Optional[float] = None
    electrode_cost_per_mt_inr: Optional[float] = None
    labour_cost_per_mt_inr: Optional[float] = None
    other_fixed_per_mt_inr: Optional[float] = None


class SimulatorRequest(BaseModel):
    """Request body for EBITDA simulator (Screen 8)."""
    base_period: str
    scrap_price_delta_pct: float = 0.0
    realisation_delta_pct: float = 0.0
    volume_delta_pct: float = 0.0
    power_rate_delta_pct: float = 0.0
    yield_delta_pct: float = 0.0
    overheads: Optional[OverheadInput] = None
    benchmarks: Optional[BenchmarkOverrideInput] = None


class EbitdaResponse(BaseModel):
    """Pydantic-serialisable wrapper for EbitdaResult."""
    success: bool
    company_id: str
    period: str
    data: dict


class RollupResponse(BaseModel):
    success: bool
    company_id: str
    data: dict


# ---------------------------------------------------------------------------
# Dependency stubs
# Replaced in production by real DB session injection (same pattern as Sessions 1–4)
# ---------------------------------------------------------------------------

def get_db():
    """DB session dependency — replaced by Supabase client in production."""
    return None


def _load_transactions(db, company_id: str, period: str) -> List[SifTransaction]:
    """
    Load SIF transactions from sales_transactions table for a period.
    In production: query Supabase with company_id + period filter.
    Returns empty list if DB not available (test/dev mode).
    """
    if db is None:
        logger.warning(
            "No DB connection — returning empty transactions for company=%s period=%s",
            company_id, period
        )
        return []
    # Production query pattern (Supabase client):
    # rows = db.table("sales_transactions")\
    #     .select("*")\
    #     .eq("company_id", company_id)\
    #     .like("date", f"{period}%")\
    #     .execute()
    # return [SifTransaction(**row) for row in rows.data]
    return []


def _load_runtime_records(db, company_id: str, period: str) -> List[MillRuntimeRecord]:
    """
    Load MillRuntimeRecord list from production_plan table for a period.
    These are the runtime_hrs outputs from Session 4's generate_daily_plan().

    Maps production_plan fields:
        date          → MillRuntimeRecord.date
        sku (brand)   → MillRuntimeRecord.sku_code / brand
        planned_qty   → MillRuntimeRecord.production_mt
        runtime_hrs   → MillRuntimeRecord.runtime_hrs  ← key field for cost calculation
    """
    if db is None:
        logger.warning(
            "No DB connection — returning empty runtime records for company=%s period=%s",
            company_id, period
        )
        return []
    # Production query pattern:
    # rows = db.table("production_plan")\
    #     .select("company_id, date, sku, planned_qty, runtime_hrs")\
    #     .eq("company_id", company_id)\
    #     .like("date", f"{period}%")\
    #     .execute()
    # return [MillRuntimeRecord(
    #     company_id=r["company_id"],
    #     date=r["date"],
    #     sku_code=r["sku"],
    #     brand="P1" if r["sku"].startswith("P1") else "P2",
    #     production_mt=r["planned_qty"],
    #     runtime_hrs=r["runtime_hrs"],
    # ) for r in rows.data]
    return []


def _load_overheads(db, company_id: str, period: str) -> Optional[OverheadRecord]:
    """Load client-entered overheads from benchmarks/settings table."""
    if db is None:
        return None
    return None


def _load_benchmarks(db, company_id: str) -> Optional[BenchmarkDefaults]:
    """Load client benchmark overrides from benchmark_config table."""
    if db is None:
        return None
    return None


def _build_benchmarks(override: Optional[BenchmarkOverrideInput]) -> Optional[BenchmarkDefaults]:
    """Build BenchmarkDefaults from API request override, applying only non-None fields."""
    if override is None:
        return None
    defaults = BenchmarkDefaults()
    return BenchmarkDefaults(
        power_units_per_hr=override.power_units_per_hr or defaults.power_units_per_hr,
        power_rate_inr_per_unit=override.power_rate_inr_per_unit or defaults.power_rate_inr_per_unit,
        fuel_cost_per_hr_inr=override.fuel_cost_per_hr_inr or defaults.fuel_cost_per_hr_inr,
        electrode_cost_per_mt_inr=override.electrode_cost_per_mt_inr or defaults.electrode_cost_per_mt_inr,
        labour_cost_per_mt_inr=override.labour_cost_per_mt_inr or defaults.labour_cost_per_mt_inr,
        other_fixed_per_mt_inr=override.other_fixed_per_mt_inr or defaults.other_fixed_per_mt_inr,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{company_id}/{period}", response_model=EbitdaResponse)
def get_ebitda(
    company_id: str,
    period: str,
    db=Depends(get_db),
) -> EbitdaResponse:
    """
    Compute and return EBITDA for a single period.

    period: "YYYY-MM" (e.g. "2025-04")

    Returns full EbitdaResult including:
      - Revenue breakdown (P1/P2, by SKU)
      - Production cost (runtime-driven)
      - Raw material cost (Phase 3 stub — zero)
      - Overheads
      - EBITDA and margin %
      - Per-SKU margin table
    """
    try:
        transactions = _load_transactions(db, company_id, period)
        runtime_records = _load_runtime_records(db, company_id, period)
        overheads = _load_overheads(db, company_id, period)
        benchmarks = _load_benchmarks(db, company_id)

        engine = EbitdaEngine(company_id=company_id)
        result = engine.compute_ebitda(
            period=period,
            transactions=transactions,
            runtime_records=runtime_records,
            overheads=overheads,
            benchmarks=benchmarks,
        )
        return EbitdaResponse(
            success=True,
            company_id=company_id,
            period=period,
            data=result.to_dict(),
        )
    except Exception as exc:
        logger.exception("EBITDA calculation failed for company=%s period=%s", company_id, period)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{company_id}/rollup", response_model=RollupResponse)
def get_rollup(
    company_id: str,
    periods: Optional[str] = Query(
        None,
        description="Comma-separated list of YYYY-MM periods. "
                    "If omitted, returns last 12 available months.",
    ),
    db=Depends(get_db),
) -> RollupResponse:
    """
    Compute EBITDA trend rollup for multiple periods.

    Used by:
      - Screen 1 (EBITDA Command Centre) — 36-month trend chart
      - Screen 9 (Strategy Dashboard) — forecast vs target comparison

    periods: "2024-10,2024-11,2024-12,2025-01" etc.
    """
    try:
        period_list = periods.split(",") if periods else _last_n_periods(12)

        # Load full history (filtered per period inside engine)
        first_period = period_list[0]
        last_period = period_list[-1]

        all_transactions: List[SifTransaction] = []
        all_runtime_records: List[MillRuntimeRecord] = []
        overheads_by_period: Dict[str, OverheadRecord] = {}

        for p in period_list:
            all_transactions += _load_transactions(db, company_id, p)
            all_runtime_records += _load_runtime_records(db, company_id, p)
            oh = _load_overheads(db, company_id, p)
            if oh:
                overheads_by_period[p] = oh

        benchmarks = _load_benchmarks(db, company_id)

        engine = EbitdaEngine(company_id=company_id)
        rollup = engine.compute_monthly_rollup(
            periods=period_list,
            transactions=all_transactions,
            runtime_records=all_runtime_records,
            overheads_by_period=overheads_by_period or None,
            benchmarks=benchmarks,
        )
        return RollupResponse(
            success=True,
            company_id=company_id,
            data=rollup.to_dict(),
        )
    except Exception as exc:
        logger.exception("EBITDA rollup failed for company=%s", company_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{company_id}/{period}/sku-margins")
def get_sku_margins(
    company_id: str,
    period: str,
    brand: Optional[str] = Query(None, description="Filter by brand: P1 | P2"),
    db=Depends(get_db),
) -> dict:
    """
    Return per-SKU contribution margins for a period.

    Used by:
      - Screen 4 (Sales Cycle) — SKU margin table
      - Screen 8 (EBITDA Simulator) — SKU-level sensitivity

    Results are sorted by contribution_margin_pct descending.
    """
    try:
        transactions = _load_transactions(db, company_id, period)
        runtime_records = _load_runtime_records(db, company_id, period)
        overheads = _load_overheads(db, company_id, period)
        benchmarks = _load_benchmarks(db, company_id)

        engine = EbitdaEngine(company_id=company_id)
        result = engine.compute_ebitda(
            period=period,
            transactions=transactions,
            runtime_records=runtime_records,
            overheads=overheads,
            benchmarks=benchmarks,
        )

        margins = result.sku_margins
        if brand:
            margins = [m for m in margins if m.brand == brand.upper()]

        sorted_margins = sorted(
            margins, key=lambda m: m.contribution_margin_pct, reverse=True
        )

        return {
            "success": True,
            "company_id": company_id,
            "period": period,
            "brand_filter": brand,
            "sku_count": len(sorted_margins),
            "sku_margins": [m.to_dict() for m in sorted_margins],
        }
    except Exception as exc:
        logger.exception(
            "SKU margin calculation failed for company=%s period=%s", company_id, period
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{company_id}/simulate")
def simulate_ebitda(
    company_id: str,
    request: SimulatorRequest,
    db=Depends(get_db),
) -> dict:
    """
    EBITDA Simulator (Screen 8) — what-if analysis.

    Apply delta sliders to a base period and return base vs simulated comparison.

    Active sliders:
      - realisation_delta_pct: % change in selling price/ton
      - volume_delta_pct: % change in sales volume
      - power_rate_delta_pct: % change in power cost per unit

    Phase 3 stubs (accepted but no effect until Phase 3):
      - scrap_price_delta_pct
      - yield_delta_pct
    """
    try:
        period = request.base_period
        transactions = _load_transactions(db, company_id, period)
        runtime_records = _load_runtime_records(db, company_id, period)

        overheads: Optional[OverheadRecord] = None
        if request.overheads:
            overheads = OverheadRecord(
                company_id=company_id,
                period=period,
                admin_cost_inr=request.overheads.admin_cost_inr,
                selling_cost_inr=request.overheads.selling_cost_inr,
                depreciation_inr=request.overheads.depreciation_inr,
                interest_inr=request.overheads.interest_inr,
                other_overhead_inr=request.overheads.other_overhead_inr,
            )

        benchmarks = _build_benchmarks(request.benchmarks)

        engine = EbitdaEngine(company_id=company_id)
        base_result = engine.compute_ebitda(
            period=period,
            transactions=transactions,
            runtime_records=runtime_records,
            overheads=overheads,
            benchmarks=benchmarks,
        )

        sim_inputs = SimulatorInputs(
            base_period=request.base_period,
            scrap_price_delta_pct=request.scrap_price_delta_pct,
            realisation_delta_pct=request.realisation_delta_pct,
            volume_delta_pct=request.volume_delta_pct,
            power_rate_delta_pct=request.power_rate_delta_pct,
            yield_delta_pct=request.yield_delta_pct,
        )

        sim_result = engine.simulate_ebitda(
            base_result=base_result,
            inputs=sim_inputs,
        )

        return {
            "success": True,
            "company_id": company_id,
            "base_period": request.base_period,
            "base": base_result.to_dict(),
            "simulated": sim_result.to_dict(),
            "phase3_note": (
                "scrap_price_delta_pct and yield_delta_pct have no effect until "
                "Phase 3 (Raw Material cycle) is built."
                if (request.scrap_price_delta_pct != 0.0 or request.yield_delta_pct != 0.0)
                else None
            ),
        }
    except Exception as exc:
        logger.exception("EBITDA simulation failed for company=%s", company_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{company_id}/{period}/cost-detail")
def get_cost_detail(
    company_id: str,
    period: str,
    db=Depends(get_db),
) -> dict:
    """
    Return production cost breakdown for a period.

    Shows variable vs fixed split:
      - Variable: Power cost (runtime_hrs × kWh/hr × ₹/kWh)
      - Variable: Fuel cost (runtime_hrs × ₹/hr)
      - Fixed: Electrode, Labour, Other

    Used by Screen 3 (Production Cycle) for cost waterfall chart.
    """
    try:
        from cost_engine import CostEngine

        runtime_records = _load_runtime_records(db, company_id, period)
        benchmarks = _load_benchmarks(db, company_id)

        engine = CostEngine(company_id=company_id)
        cost_record = engine.compute_production_cost(
            period=period,
            runtime_records=runtime_records,
            benchmarks=benchmarks,
        )

        return {
            "success": True,
            "company_id": company_id,
            "period": period,
            "cost_detail": cost_record.to_dict(),
            "formula_note": {
                "power_cost": "power_units_per_hr × total_runtime_hrs × power_rate_inr_per_unit",
                "fuel_cost": "fuel_cost_per_hr_inr × total_runtime_hrs",
                "cost_per_ton": "total_production_cost_inr / total_production_mt",
            },
        }
    except Exception as exc:
        logger.exception(
            "Cost detail retrieval failed for company=%s period=%s", company_id, period
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
def health() -> dict:
    """Health check — confirms EBITDA engine is live."""
    return {
        "status": "ok",
        "module": "ebitda_engine",
        "session": 5,
        "cycles": {
            "revenue": "live",
            "production_cost": "live",
            "raw_material": "phase3_stub",
        },
        "endpoints": [
            "GET  /ebitda/{company_id}/{period}",
            "GET  /ebitda/{company_id}/rollup",
            "GET  /ebitda/{company_id}/{period}/sku-margins",
            "POST /ebitda/{company_id}/simulate",
            "GET  /ebitda/{company_id}/{period}/cost-detail",
            "GET  /ebitda/health",
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_n_periods(n: int) -> List[str]:
    """Generate last N monthly period strings ending at current month."""
    from datetime import date
    import calendar

    today = date.today()
    periods = []
    year, month = today.year, today.month
    for _ in range(n):
        periods.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(periods))
