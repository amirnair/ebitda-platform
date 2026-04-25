"""
api/main.py — FastAPI layer for the Aggregation Engine
AC Industries EBITDA Intelligence Platform — Session 2

Endpoints:
  POST /aggregate                  Full period aggregation
  GET  /daily/{date}/sku           Daily SKU totals for a date
  GET  /daily/{date}/brands        Daily brand split for a date
  GET  /daily/{date}/regions       Daily region split for a date
  GET  /proportions                SKU proportion table for a period
  GET  /health                     Health check

All endpoints are company-scoped via the X-Company-ID header.
In production, this will be replaced by JWT claims (Session 7 — Auth).

Run locally:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from aggregator import (
    AggregationEngine,
    SIFRow,
    AC_INDUSTRIES_SKU_MASTER,
)
from aggregator.aggregation_models import (
    AggregationResult,
    BrandSplit,
    DailyBrandTotal,
    DailyRegionTotal,
    DailySkuTotal,
    DailySummary,
    PeriodSummary,
    SkuProportion,
)

# ------------------------------------------------------------------ #
# App setup                                                           #
# ------------------------------------------------------------------ #

app = FastAPI(
    title="AC Industries — Aggregation Engine API",
    description=(
        "Session 2: Aggregation Engine for the EBITDA Intelligence Platform. "
        "Consumes SIF rows and produces daily totals, brand splits, "
        "region splits, and SKU proportions."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
# In-memory SKU master registry (replace with DB lookup in Session 7) #
# ------------------------------------------------------------------ #

SKU_MASTER_REGISTRY = {
    "AC001": AC_INDUSTRIES_SKU_MASTER,
}


def get_engine(company_id: str, holidays: Optional[list[str]] = None) -> AggregationEngine:
    master = SKU_MASTER_REGISTRY.get(company_id)
    if not master:
        raise HTTPException(status_code=404, detail=f"Unknown company_id: {company_id}")
    holiday_dates = {date.fromisoformat(h) for h in (holidays or [])}
    return AggregationEngine(company_id, master, holiday_dates)


# ------------------------------------------------------------------ #
# Pydantic request / response models                                  #
# ------------------------------------------------------------------ #

class SIFRowIn(BaseModel):
    date: date
    customer_id: str
    brand: str
    sku_name: str
    size_mm: int
    quantity_tons: float
    value_inr: float
    region: str
    district: str
    invoice_id: str
    company_id: str
    source_file: str = ""
    ingested_at: Optional[str] = None

    def to_sif(self) -> SIFRow:
        return SIFRow(**self.model_dump())


class AggregateRequest(BaseModel):
    rows: list[SIFRowIn] = Field(..., description="SIF rows from the connector")
    from_date: Optional[date] = Field(None, description="Start of period (inclusive)")
    to_date: Optional[date] = Field(None, description="End of period (inclusive)")
    holidays: list[str] = Field(
        default_factory=list,
        description="ISO date strings of holidays to exclude from trading day count"
    )


# ---- Response models (Pydantic mirrors of the dataclasses) -------- #

class DailySkuTotalOut(BaseModel):
    date: date
    brand_code: str
    size_mm: int
    quantity_tons: float
    value_inr: float
    realisation_per_ton: float

    @classmethod
    def from_dc(cls, dc: DailySkuTotal) -> "DailySkuTotalOut":
        return cls(**dc.__dict__)


class DailyBrandTotalOut(BaseModel):
    date: date
    brand_code: str
    quantity_tons: float
    value_inr: float
    realisation_per_ton: float
    sku_count: int

    @classmethod
    def from_dc(cls, dc: DailyBrandTotal) -> "DailyBrandTotalOut":
        return cls(**dc.__dict__)


class DailyRegionTotalOut(BaseModel):
    date: date
    region: str
    quantity_tons: float
    value_inr: float
    brand_breakdown: dict[str, float]

    @classmethod
    def from_dc(cls, dc: DailyRegionTotal) -> "DailyRegionTotalOut":
        return cls(**dc.__dict__)


class SkuProportionOut(BaseModel):
    brand_code: str
    size_mm: int
    total_quantity_tons: float
    proportion_pct: float
    trading_days: int
    avg_daily_tons: float

    @classmethod
    def from_dc(cls, dc: SkuProportion) -> "SkuProportionOut":
        return cls(**dc.__dict__)


class BrandSplitOut(BaseModel):
    brand_code: str
    total_quantity_tons: float
    total_value_inr: float
    proportion_pct: float
    realisation_per_ton: float

    @classmethod
    def from_dc(cls, dc: BrandSplit) -> "BrandSplitOut":
        return cls(**dc.__dict__)


class DailySummaryOut(BaseModel):
    date: date
    company_id: str
    total_quantity_tons: float
    total_value_inr: float
    overall_realisation_per_ton: float
    brand_totals: list[DailyBrandTotalOut]
    sku_totals: list[DailySkuTotalOut]
    region_totals: list[DailyRegionTotalOut]
    is_sunday: bool
    is_holiday: bool

    @classmethod
    def from_dc(cls, dc: DailySummary) -> "DailySummaryOut":
        return cls(
            date=dc.date,
            company_id=dc.company_id,
            total_quantity_tons=dc.total_quantity_tons,
            total_value_inr=dc.total_value_inr,
            overall_realisation_per_ton=dc.overall_realisation_per_ton,
            brand_totals=[DailyBrandTotalOut.from_dc(b) for b in dc.brand_totals],
            sku_totals=[DailySkuTotalOut.from_dc(s) for s in dc.sku_totals],
            region_totals=[DailyRegionTotalOut.from_dc(r) for r in dc.region_totals],
            is_sunday=dc.is_sunday,
            is_holiday=dc.is_holiday,
        )


class PeriodSummaryOut(BaseModel):
    company_id: str
    from_date: date
    to_date: date
    total_quantity_tons: float
    total_value_inr: float
    overall_realisation_per_ton: float
    trading_days: int
    brand_splits: list[BrandSplitOut]
    sku_proportions: list[SkuProportionOut]
    region_totals: list[DailyRegionTotalOut]
    daily_summaries: list[DailySummaryOut]

    @classmethod
    def from_dc(cls, dc: PeriodSummary) -> "PeriodSummaryOut":
        return cls(
            company_id=dc.company_id,
            from_date=dc.from_date,
            to_date=dc.to_date,
            total_quantity_tons=dc.total_quantity_tons,
            total_value_inr=dc.total_value_inr,
            overall_realisation_per_ton=dc.overall_realisation_per_ton,
            trading_days=dc.trading_days,
            brand_splits=[BrandSplitOut.from_dc(b) for b in dc.brand_splits],
            sku_proportions=[SkuProportionOut.from_dc(s) for s in dc.sku_proportions],
            region_totals=[DailyRegionTotalOut.from_dc(r) for r in dc.region_totals],
            daily_summaries=[DailySummaryOut.from_dc(d) for d in dc.daily_summaries],
        )


class AggregateResponse(BaseModel):
    company_id: str
    from_date: date
    to_date: date
    period_summary: PeriodSummaryOut
    warnings: list[str]

    @classmethod
    def from_result(cls, result: AggregationResult) -> "AggregateResponse":
        return cls(
            company_id=result.company_id,
            from_date=result.from_date,
            to_date=result.to_date,
            period_summary=PeriodSummaryOut.from_dc(result.period_summary),
            warnings=result.warnings,
        )


# ------------------------------------------------------------------ #
# Endpoints                                                           #
# ------------------------------------------------------------------ #

@app.get("/health")
def health():
    """Health check — used by Railway/Render deployment."""
    return {"status": "ok", "session": "2 — Aggregation Engine"}


@app.post("/aggregate", response_model=AggregateResponse)
def aggregate(
    body: AggregateRequest,
    x_company_id: str = Header(..., description="Multi-tenant company identifier"),
):
    """
    Full period aggregation.

    Submit a batch of SIF rows and receive:
    - Period totals (qty, value, realisation)
    - Brand split with proportions
    - SKU proportion table (Sunday-excluded)
    - Region totals (Chennai vs Outside Chennai)
    - Daily breakdown for every date in the range
    """
    engine = get_engine(x_company_id, body.holidays)
    sif_rows = [r.to_sif() for r in body.rows]
    result = engine.aggregate(sif_rows, body.from_date, body.to_date)
    return AggregateResponse.from_result(result)


@app.post("/daily/{target_date}/sku", response_model=list[DailySkuTotalOut])
def daily_sku(
    target_date: date,
    rows: list[SIFRowIn],
    x_company_id: str = Header(...),
):
    """Daily totals broken down by SKU (brand + size) for a single date."""
    engine = get_engine(x_company_id)
    sif_rows = [r.to_sif() for r in rows]
    totals = engine.daily_sku_totals(sif_rows, target_date)
    return [DailySkuTotalOut.from_dc(t) for t in totals]


@app.post("/daily/{target_date}/brands", response_model=list[DailyBrandTotalOut])
def daily_brands(
    target_date: date,
    rows: list[SIFRowIn],
    x_company_id: str = Header(...),
):
    """Daily brand split (P1 vs P2) for a single date."""
    engine = get_engine(x_company_id)
    sif_rows = [r.to_sif() for r in rows]
    totals = engine.daily_brand_totals(sif_rows, target_date)
    return [DailyBrandTotalOut.from_dc(t) for t in totals]


@app.post("/daily/{target_date}/regions", response_model=list[DailyRegionTotalOut])
def daily_regions(
    target_date: date,
    rows: list[SIFRowIn],
    x_company_id: str = Header(...),
):
    """Daily region split (Chennai vs Outside Chennai) for a single date."""
    engine = get_engine(x_company_id)
    sif_rows = [r.to_sif() for r in rows]
    totals = engine.daily_region_totals(sif_rows, target_date)
    return [DailyRegionTotalOut.from_dc(t) for t in totals]


@app.post("/proportions", response_model=list[SkuProportionOut])
def sku_proportions(
    rows: list[SIFRowIn],
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    exclude_sundays: bool = Query(True, description="Exclude Sundays from proportion calc"),
    x_company_id: str = Header(...),
):
    """
    SKU proportion table for a period.

    Sundays excluded by default — mirrors the §3.6 proportion model.
    Output is sorted highest-volume first and feeds directly into
    the Session 3 Forecasting Engine.
    """
    engine = get_engine(x_company_id)
    sif_rows = [r.to_sif() for r in rows]
    props = engine.sku_proportions(sif_rows, from_date, to_date, exclude_sundays)
    return [SkuProportionOut.from_dc(p) for p in props]
