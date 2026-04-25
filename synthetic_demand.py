"""
synthetic_demand.py
-------------------
Provides a daily SKU-level demand vector for the Production Optimiser.

In production: reads from the `forecasts` table (§7.2) — specifically the
daily-granularity rows output by forecasting_engine.py (Session 3).

For development / testing: generates synthetic demand shaped to match
AC Industries' actual SKU proportions (§3.6) and seasonal Tamil Nadu
construction demand patterns.

Interface contract (matches `forecasts` table schema §7.2):
    DailySkuDemand(
        company_id: str,
        forecast_date: date,
        sku_code: str,
        brand_code: str,      # P1 / P2
        size_mm: int,
        qty_forecast_mt: float,
        confidence_low: float,
        confidence_high: float,
        model_name: str,
    )
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List

from optimiser.sku_capacity import ALL_SKU_CODES, SKU_CAPACITY

# ---------------------------------------------------------------------------
# SKU proportion weights — §3.6 (normalised so P1+P2 = 1.0)
# ---------------------------------------------------------------------------
_SKU_PROPORTIONS: Dict[str, float] = {
    "P1-SKU-8":  0.110,
    "P1-SKU-10": 0.168,
    "P1-SKU-12": 0.149,
    "P1-SKU-16": 0.165,
    "P1-SKU-20": 0.045,
    "P1-SKU-25": 0.025,
    "P1-SKU-32": 0.015,
    "P2-SKU-8":  0.045,
    "P2-SKU-10": 0.067,
    "P2-SKU-12": 0.051,
    "P2-SKU-16": 0.060,
    "P2-SKU-20": 0.035,
    "P2-SKU-25": 0.015,
    "P2-SKU-32": 0.010,
}
# Normalise to sum=1
_total = sum(_SKU_PROPORTIONS.values())
_SKU_PROPORTIONS = {k: v / _total for k, v in _SKU_PROPORTIONS.items()}


@dataclass
class DailySkuDemand:
    """Mirrors one row of the forecasts table at daily granularity."""
    company_id: str
    forecast_date: date
    sku_code: str
    brand_code: str
    size_mm: int
    qty_forecast_mt: float
    confidence_low: float
    confidence_high: float
    model_name: str


def generate_daily_demand(
    forecast_date: date,
    company_id: str = "AC001",
    total_daily_mt: float | None = None,
    seed: int | None = None,
) -> List[DailySkuDemand]:
    """
    Generate a synthetic daily demand vector for all SKUs.

    Args:
        forecast_date: The planning date.
        company_id:    Multi-tenant key.
        total_daily_mt: Override total daily volume (MT). If None, a
                        seasonally-shaped value is generated (~280–380 MT/day).
        seed:          Random seed for reproducibility in tests.

    Returns:
        List of DailySkuDemand, one per SKU (14 rows).
    """
    rng = random.Random(seed)

    if total_daily_mt is None:
        # Seasonal shape: Q4 (Oct–Dec) = peak, Q2 (Apr–Jun) = trough.
        # Tamil Nadu construction seasonality (§3.5 context).
        month = forecast_date.month
        _seasonal_index = {
            1: 1.05, 2: 1.00, 3: 0.95, 4: 0.90,
            5: 0.88, 6: 0.85, 7: 0.90, 8: 0.95,
            9: 1.00, 10: 1.08, 11: 1.12, 12: 1.10,
        }
        base = 320.0  # MT/day average
        total_daily_mt = base * _seasonal_index[month] * rng.uniform(0.95, 1.05)

    demands = []
    for sku_code in ALL_SKU_CODES:
        rec = SKU_CAPACITY[sku_code]
        prop = _SKU_PROPORTIONS[sku_code]
        qty = round(total_daily_mt * prop, 2)
        ci_half = round(qty * 0.08, 2)   # ±8% confidence interval

        demands.append(DailySkuDemand(
            company_id=company_id,
            forecast_date=forecast_date,
            sku_code=sku_code,
            brand_code=rec.brand_code,
            size_mm=rec.size_mm,
            qty_forecast_mt=qty,
            confidence_low=max(0.0, qty - ci_half),
            confidence_high=qty + ci_half,
            model_name="synthetic_v1",
        ))
    return demands


def generate_demand_window(
    start_date: date,
    days: int = 7,
    company_id: str = "AC001",
    seed: int | None = None,
) -> Dict[date, List[DailySkuDemand]]:
    """
    Generate demand for a rolling window of days.
    Returns dict: date → list of DailySkuDemand.
    """
    result = {}
    for i in range(days):
        d = start_date + timedelta(days=i)
        result[d] = generate_daily_demand(
            forecast_date=d,
            company_id=company_id,
            seed=(seed + i) if seed is not None else None,
        )
    return result


def demand_as_dict(demands: List[DailySkuDemand]) -> Dict[str, float]:
    """Quick lookup: sku_code → qty_forecast_mt."""
    return {d.sku_code: d.qty_forecast_mt for d in demands}
