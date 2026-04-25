"""
aggregation_models.py — Typed output models for the Aggregation Engine

All public methods on AggregationEngine return one of these dataclasses.
The FastAPI layer serialises them directly via Pydantic.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ------------------------------------------------------------------ #
# Row-level types                                                      #
# ------------------------------------------------------------------ #

@dataclass
class DailySkuTotal:
    """Total volume and value for one SKU on one date."""
    date: date
    brand_code: str        # "P1" / "P2"
    size_mm: int
    quantity_tons: float
    value_inr: float
    realisation_per_ton: float   # value_inr / quantity_tons; 0 if qty == 0


@dataclass
class DailyBrandTotal:
    """Aggregated volume and value for one brand on one date."""
    date: date
    brand_code: str
    quantity_tons: float
    value_inr: float
    realisation_per_ton: float
    sku_count: int          # number of distinct SKUs sold that day


@dataclass
class DailyRegionTotal:
    """Volume and value for one region on one date (all brands combined)."""
    date: date
    region: str            # e.g. "Chennai" / "Outside Chennai"
    quantity_tons: float
    value_inr: float
    brand_breakdown: dict[str, float] = field(default_factory=dict)
    # brand_breakdown = {"P1": 12.5, "P2": 7.0}  — qty by brand


@dataclass
class SkuProportion:
    """
    SKU's share of total volume over a given period.

    Mirrors the proportion model in §3.6 of the master context.
    Sundays (sales holiday) are excluded from the calculation by default.
    """
    brand_code: str
    size_mm: int
    total_quantity_tons: float
    proportion_pct: float          # 0–100
    trading_days: int              # days with at least one sale (excl. Sundays)
    avg_daily_tons: float          # total_quantity_tons / trading_days


@dataclass
class BrandSplit:
    """Brand mix for a date range."""
    brand_code: str
    total_quantity_tons: float
    total_value_inr: float
    proportion_pct: float          # share of overall volume
    realisation_per_ton: float


# ------------------------------------------------------------------ #
# Summary / report types                                              #
# ------------------------------------------------------------------ #

@dataclass
class DailySummary:
    """Full aggregation output for a single date."""
    date: date
    company_id: str
    total_quantity_tons: float
    total_value_inr: float
    overall_realisation_per_ton: float
    brand_totals: list[DailyBrandTotal] = field(default_factory=list)
    sku_totals: list[DailySkuTotal] = field(default_factory=list)
    region_totals: list[DailyRegionTotal] = field(default_factory=list)
    is_sunday: bool = False
    is_holiday: bool = False


@dataclass
class PeriodSummary:
    """Aggregated report over a date range (week / month / custom)."""
    company_id: str
    from_date: date
    to_date: date
    total_quantity_tons: float
    total_value_inr: float
    overall_realisation_per_ton: float
    trading_days: int              # non-Sunday, non-holiday days
    brand_splits: list[BrandSplit] = field(default_factory=list)
    sku_proportions: list[SkuProportion] = field(default_factory=list)
    region_totals: list[DailyRegionTotal] = field(default_factory=list)
    daily_summaries: list[DailySummary] = field(default_factory=list)


@dataclass
class AggregationResult:
    """
    Top-level wrapper returned by AggregationEngine.aggregate().
    Contains both the period summary and every daily breakdown.
    """
    company_id: str
    from_date: date
    to_date: date
    period_summary: PeriodSummary
    warnings: list[str] = field(default_factory=list)
    # e.g. ["3 rows had unknown district — assigned to 'Outside Chennai'"]
