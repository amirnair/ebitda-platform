"""
sku_proportion_model.py
-----------------------
Converts monthly brand-level forecasts into weekly and daily SKU-level volumes.

Logic:
  1. Monthly brand forecast → weekly via proportion-of-month (business days)
  2. Weekly → daily via day-of-week adjustment (Mon–Sat, Sun=0)
  3. Daily brand volume → per-SKU via rolling SKU proportion averages (§3.6)

The proportions are learned from historical actuals and updated every month.
On first run (no history), the static proportions from §3.6 are used as priors.

Wire-up: replace compute_sku_proportions_from_actuals() with a DB query
against sales_transactions when live data is available.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Static priors from §3.6 — used when no historical data is available
# ---------------------------------------------------------------------------

# (brand, size_mm) → proportion of total daily brand volume
STATIC_SKU_PROPORTIONS: Dict[Tuple[str, int], float] = {
    ("P1", 10): 0.2556,   # 16.76% of all SKUs → normalised within P1
    ("P1", 16): 0.2511,
    ("P1", 12): 0.2266,
    ("P1",  8): 0.1679,
    ("P1", 20): 0.1069,
    ("P1", 25): 0.0534,
    ("P1", 32): 0.0371,   # residual — sums P1 to ~0.98 before norm
    ("P2", 10): 0.3088,
    ("P2", 12): 0.2370,
    ("P2",  8): 0.1752,
    ("P2", 16): 0.1475,
    ("P2", 20): 0.1014,
    ("P2", 25): 0.0673,
    ("P2", 32): 0.2535,   # residual
}

# Normalise within each brand
for _brand in ("P1", "P2"):
    _brand_total = sum(v for (b, s), v in STATIC_SKU_PROPORTIONS.items() if b == _brand)
    for key in [(b, s) for (b, s) in STATIC_SKU_PROPORTIONS if b == _brand]:
        STATIC_SKU_PROPORTIONS[key] /= _brand_total

# Day-of-week volume index (Mon=0 ... Sat=5, Sun=6=zero)
# TMT retail patterns: Mon–Wed moderate, Thu–Fri peak (project ordering),
# Sat lower (retail). Sunday excluded by holiday calendar.
DOW_INDEX: Dict[int, float] = {
    0: 0.95,   # Monday
    1: 0.98,   # Tuesday
    2: 1.00,   # Wednesday
    3: 1.08,   # Thursday
    4: 1.12,   # Friday — strongest ordering day
    5: 0.87,   # Saturday
    6: 0.00,   # Sunday — zero sales
}


@dataclass
class SkuDailyForecast:
    """Daily forecast for a single SKU."""
    date: date
    brand: str
    size_mm: int
    sku_name: str
    qty_tons: float
    region: str


@dataclass
class SkuWeeklyForecast:
    """Weekly forecast (Mon–Sun) for a single SKU."""
    week_start: date      # Monday of the week
    brand: str
    size_mm: int
    sku_name: str
    qty_tons: float
    region: str


def get_business_days_in_month(year: int, month: int) -> List[date]:
    """Return all non-Sunday days in a given month."""
    _, num_days = calendar.monthrange(year, month)
    return [
        date(year, month, d)
        for d in range(1, num_days + 1)
        if date(year, month, d).weekday() != 6  # exclude Sunday
    ]


def compute_sku_proportions_from_actuals(
    actuals: Optional[Dict[Tuple[str, int], float]] = None,
    smoothing: float = 0.3,
) -> Dict[Tuple[str, int], float]:
    """
    Blend actual observed SKU proportions with static priors.
    smoothing=0.3 means 30% weight on static prior, 70% on actuals.
    When actuals is None, returns static priors.

    Wire-up point: actuals should be a dict of (brand, size_mm) → rolling
    3-month average share computed from sales_transactions table.
    """
    if actuals is None:
        return dict(STATIC_SKU_PROPORTIONS)

    blended: Dict[Tuple[str, int], float] = {}
    for key, static_val in STATIC_SKU_PROPORTIONS.items():
        actual_val = actuals.get(key, static_val)
        blended[key] = smoothing * static_val + (1 - smoothing) * actual_val

    # Re-normalise within each brand
    for brand in ("P1", "P2"):
        brand_total = sum(v for (b, _), v in blended.items() if b == brand)
        if brand_total > 0:
            for key in [(b, s) for (b, s) in blended if b == brand]:
                blended[key] /= brand_total

    return blended


def disaggregate_monthly_to_weekly(
    year: int,
    month: int,
    brand: str,
    region: str,
    monthly_qty_tons: float,
    sku_name_map: Optional[Dict[Tuple[str, int], str]] = None,
    sku_proportions: Optional[Dict[Tuple[str, int], float]] = None,
) -> List[SkuWeeklyForecast]:
    """
    Disaggregate a monthly brand forecast to weekly SKU-level volumes.

    Parameters
    ----------
    year, month         : Target month
    brand               : "P1" or "P2"
    region              : "Chennai" or "Outside Chennai"
    monthly_qty_tons    : Total brand volume for the month (MT)
    sku_name_map        : (brand, size_mm) → display name. Uses generic if None.
    sku_proportions     : Pre-computed SKU proportions. Uses static priors if None.
    """
    if sku_proportions is None:
        sku_proportions = compute_sku_proportions_from_actuals()

    business_days = get_business_days_in_month(year, month)
    if not business_days:
        return []

    # Compute weighted daily volumes using DOW index
    dow_weights = [DOW_INDEX[d.weekday()] for d in business_days]
    total_dow = sum(dow_weights)
    if total_dow == 0:
        return []

    # Daily brand volumes
    daily_volumes: Dict[date, float] = {
        d: monthly_qty_tons * (DOW_INDEX[d.weekday()] / total_dow)
        for d in business_days
    }

    # Group days into weeks (Mon–Sun ISO weeks)
    weekly_volumes: Dict[date, float] = {}  # week_start → volume
    for d, vol in daily_volumes.items():
        week_start = d - timedelta(days=d.weekday())  # Monday of week
        weekly_volumes[week_start] = weekly_volumes.get(week_start, 0.0) + vol

    # Apply SKU proportions
    results: List[SkuWeeklyForecast] = []
    brand_skus = [(b, s) for (b, s) in sku_proportions if b == brand]

    for week_start, week_vol in sorted(weekly_volumes.items()):
        for (b, size_mm) in brand_skus:
            proportion = sku_proportions[(b, size_mm)]
            qty = week_vol * proportion

            if sku_name_map:
                name = sku_name_map.get((b, size_mm), f"{size_mm}mm {brand} Fe550")
            else:
                brand_label = "Product 1" if brand == "P1" else "Product 2"
                name = f"{size_mm}mm {brand_label} Fe550"

            results.append(SkuWeeklyForecast(
                week_start=week_start,
                brand=brand,
                size_mm=size_mm,
                sku_name=name,
                qty_tons=round(qty, 3),
                region=region,
            ))

    return results


def disaggregate_monthly_to_daily(
    year: int,
    month: int,
    brand: str,
    region: str,
    monthly_qty_tons: float,
    holiday_dates: Optional[List[date]] = None,
    sku_name_map: Optional[Dict[Tuple[str, int], str]] = None,
    sku_proportions: Optional[Dict[Tuple[str, int], float]] = None,
) -> List[SkuDailyForecast]:
    """
    Disaggregate a monthly brand forecast to daily SKU-level volumes.
    Excludes Sundays and any dates in holiday_dates.
    """
    if sku_proportions is None:
        sku_proportions = compute_sku_proportions_from_actuals()

    holiday_set = set(holiday_dates) if holiday_dates else set()
    business_days = [
        d for d in get_business_days_in_month(year, month)
        if d not in holiday_set
    ]
    if not business_days:
        return []

    dow_weights = [DOW_INDEX[d.weekday()] for d in business_days]
    total_dow = sum(dow_weights)
    if total_dow == 0:
        return []

    brand_skus = [(b, s) for (b, s) in sku_proportions if b == brand]
    results: List[SkuDailyForecast] = []

    for d, dow_weight in zip(business_days, dow_weights):
        day_brand_vol = monthly_qty_tons * (dow_weight / total_dow)

        for (b, size_mm) in brand_skus:
            proportion = sku_proportions[(b, size_mm)]
            qty = day_brand_vol * proportion

            if sku_name_map:
                name = sku_name_map.get((b, size_mm), f"{size_mm}mm {brand} Fe550")
            else:
                brand_label = "Product 1" if brand == "P1" else "Product 2"
                name = f"{size_mm}mm {brand_label} Fe550"

            results.append(SkuDailyForecast(
                date=d,
                brand=brand,
                size_mm=size_mm,
                sku_name=name,
                qty_tons=round(qty, 3),
                region=region,
            ))

    return results
