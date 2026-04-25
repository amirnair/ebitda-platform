"""
synthetic_data.py
-----------------
Generates synthetic sales data shaped to AC Industries' actual patterns:
  - Chennai vs Outside Chennai regional split
  - Product 1 (growth) vs Product 2 (managed decline) brand mix
  - SKU proportions from §3.6 of master context
  - Seasonal TMT demand (construction cycles in Tamil Nadu)
  - Sunday zero-sales exclusion

Used as a stand-in until real SAP export data is available.
Wire-up point: replace generate_synthetic_sales() with a real DB query
against sales_transactions table when live data is ready.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Constants — derived from §3.6 (SKU proportions) and §1.2 (brand strategy)
# ---------------------------------------------------------------------------

# SKU proportions (excl. Sunday) — from §3.6, normalised to sum to 1.0
SKU_PROPORTIONS: dict[str, float] = {
    "P1-10mm": 0.1676,
    "P1-16mm": 0.1646,
    "P1-12mm": 0.1485,
    "P1-8mm":  0.1100,
    "P1-20mm": 0.0700,
    "P1-25mm": 0.0350,
    "P1-32mm": 0.0243,
    "P2-10mm": 0.0670,
    "P2-12mm": 0.0514,
    "P2-8mm":  0.0380,
    "P2-16mm": 0.0320,
    "P2-20mm": 0.0220,
    "P2-25mm": 0.0146,
    "P2-32mm": 0.0550,  # residual to sum to 1.0
}

# Normalise to exactly 1.0 (handles floating point drift)
_total = sum(SKU_PROPORTIONS.values())
SKU_PROPORTIONS = {k: v / _total for k, v in SKU_PROPORTIONS.items()}

# Regional split: Chennai ~40%, Outside Chennai ~60% for P1 (P2 heavier in Chennai)
REGIONAL_SPLIT = {
    "Chennai":         {"P1": 0.35, "P2": 0.50},
    "Outside Chennai": {"P1": 0.65, "P2": 0.50},
}

# Tamil Nadu TMT seasonal index (Jan=1 through Dec=12)
# Peak: Q1 (post-monsoon construction season) and Q4 pre-monsoon.
# Trough: Aug–Oct (NE monsoon, construction slows).
SEASONAL_INDEX: dict[int, float] = {
    1: 1.15,   # Jan — strong post-holiday construction start
    2: 1.20,   # Feb — peak season
    3: 1.18,   # Mar — sustained
    4: 1.05,   # Apr — tapering pre-summer
    5: 0.95,   # May — heat slowdown
    6: 0.85,   # Jun — SW monsoon begins
    7: 0.80,   # Jul — monsoon
    8: 0.75,   # Aug — NE monsoon builds
    9: 0.78,   # Sep — still slow
    10: 0.88,  # Oct — post-monsoon pickup
    11: 1.05,  # Nov — Diwali construction surge
    12: 1.10,  # Dec — year-end project completions
}

# Base daily volume (MT) — all SKUs combined, weekday non-holiday
BASE_DAILY_VOLUME_MT = 185.0  # approximately 4,000–4,500 MT/month

# P1 growth trend: +8% per year YoY; P2 decline: -5% per year
P1_ANNUAL_GROWTH = 0.08
P2_ANNUAL_DECLINE = -0.05


@dataclass
class SyntheticSaleRow:
    """Mirrors the SIF (Standard Internal Format) from §6.2."""
    date: date
    company_id: str
    brand: str          # "P1" or "P2"
    sku_name: str       # e.g. "16mm Product 1 Fe550"
    size_mm: int
    quantity_tons: float
    value_inr: float
    region: str         # "Tamil Nadu"
    district: str       # "Chennai" or district name
    invoice_id: str
    source_file: str = "synthetic_data"
    ingested_at: str = ""


def _brand_from_sku(sku_key: str) -> str:
    return "P1" if sku_key.startswith("P1") else "P2"


def _size_from_sku(sku_key: str) -> int:
    return int(sku_key.split("-")[1].replace("mm", ""))


def _sku_display_name(sku_key: str, brand_names: dict[str, str]) -> str:
    brand = _brand_from_sku(sku_key)
    size = _size_from_sku(sku_key)
    brand_label = brand_names.get(brand, brand)
    return f"{size}mm {brand_label} Fe550"


OUTSIDE_CHENNAI_DISTRICTS = [
    "Coimbatore", "Madurai", "Salem", "Trichy", "Tirunelveli",
    "Erode", "Tiruppur", "Vellore", "Thoothukudi", "Karur",
]

# Approximate realisation per ton (₹) by SKU size — smaller bars have lower realisation
BASE_REALISATION: dict[int, float] = {
    8:  57_500,
    10: 57_800,
    12: 57_600,
    16: 57_900,
    20: 58_100,
    25: 58_500,
    32: 59_000,
}


def _apply_growth_factor(base: float, brand: str, months_from_start: int) -> float:
    """Apply annual growth/decline trend to a base volume."""
    if brand == "P1":
        factor = (1 + P1_ANNUAL_GROWTH) ** (months_from_start / 12)
    else:
        factor = (1 + P2_ANNUAL_DECLINE) ** (months_from_start / 12)
    return base * factor


def generate_synthetic_sales(
    company_id: str = "AC001",
    start_date: date = date(2023, 1, 1),
    end_date: date = date(2025, 3, 31),
    random_seed: int = 42,
    brand_names: Optional[dict[str, str]] = None,
) -> List[SyntheticSaleRow]:
    """
    Generate day-level synthetic sales rows shaped to AC Industries patterns.

    Parameters
    ----------
    company_id   : Multi-tenant key
    start_date   : First date to generate (inclusive)
    end_date     : Last date to generate (inclusive)
    random_seed  : Reproducibility seed
    brand_names  : Display names for brands, e.g. {"P1": "ACI TMT", "P2": "ACE TMT"}

    Returns
    -------
    List[SyntheticSaleRow] — one row per (date, district, sku) combination
    """
    if brand_names is None:
        brand_names = {"P1": "Product 1", "P2": "Product 2"}

    rng = np.random.default_rng(random_seed)
    rows: List[SyntheticSaleRow] = []
    invoice_counter = 90_000_000

    current = start_date
    months_from_start = 0
    current_month = (start_date.year, start_date.month)

    while current <= end_date:
        # Track months elapsed for trend application
        new_month = (current.year, current.month)
        if new_month != current_month:
            months_elapsed = (
                (new_month[0] - start_date.year) * 12 +
                (new_month[1] - start_date.month)
            )
            months_from_start = months_elapsed
            current_month = new_month

        # Sundays: zero sales (§4.6 sales holiday calendar)
        if current.weekday() == 6:
            current += timedelta(days=1)
            continue

        # Festival/public holidays — approximate: 2 random days per month
        # (In production, this will use the holiday calendar table)
        day_of_month = current.day
        if day_of_month in (1, 15) and current.month in (1, 4, 8, 10):
            current += timedelta(days=1)
            continue

        seasonal = SEASONAL_INDEX[current.month]

        # Noise: daily variation ±12%
        day_noise = rng.normal(1.0, 0.08)
        day_noise = float(np.clip(day_noise, 0.80, 1.20))

        daily_total = BASE_DAILY_VOLUME_MT * seasonal * day_noise

        # Distribute across SKUs using proportion model
        for sku_key, proportion in SKU_PROPORTIONS.items():
            brand = _brand_from_sku(sku_key)
            size = _size_from_sku(sku_key)
            sku_display = _sku_display_name(sku_key, brand_names)

            sku_volume = daily_total * proportion
            # Apply YoY growth/decline trend
            sku_volume = _apply_growth_factor(sku_volume, brand, months_from_start)

            # Add SKU-level noise
            sku_noise = rng.normal(1.0, 0.06)
            sku_noise = float(np.clip(sku_noise, 0.85, 1.15))
            sku_volume *= sku_noise

            # Distribute to districts using regional split
            for district_type, brand_splits in REGIONAL_SPLIT.items():
                district_fraction = brand_splits[brand]

                if district_type == "Chennai":
                    district = "Chennai"
                else:
                    # Pick a random outside-Chennai district
                    idx = rng.integers(0, len(OUTSIDE_CHENNAI_DISTRICTS))
                    district = OUTSIDE_CHENNAI_DISTRICTS[int(idx)]

                qty = sku_volume * district_fraction
                # Add realistic minimum invoice size (0.5 MT lots)
                qty = max(0.5, round(qty, 2))

                base_real = BASE_REALISATION.get(size, 57_800)
                # Price variation ±3%
                price_noise = rng.normal(1.0, 0.015)
                realisation = base_real * float(np.clip(price_noise, 0.96, 1.04))
                value = round(qty * realisation, 2)

                invoice_counter += 1
                rows.append(SyntheticSaleRow(
                    date=current,
                    company_id=company_id,
                    brand=brand,
                    sku_name=sku_display,
                    size_mm=size,
                    quantity_tons=qty,
                    value_inr=value,
                    region="Tamil Nadu",
                    district=district,
                    invoice_id=str(invoice_counter),
                    source_file="synthetic_v1",
                    ingested_at=str(date.today()),
                ))

        current += timedelta(days=1)

    return rows


def aggregate_to_monthly(
    rows: List[SyntheticSaleRow],
) -> dict[tuple[int, int, str, str, str], float]:
    """
    Aggregate synthetic rows to monthly brand/sku/district totals.
    Returns: {(year, month, brand, sku_name, district): total_qty_tons}
    """
    totals: dict[tuple, float] = {}
    for r in rows:
        key = (r.date.year, r.date.month, r.brand, r.sku_name, r.district)
        totals[key] = totals.get(key, 0.0) + r.quantity_tons
    return totals


def build_monthly_brand_series(
    rows: List[SyntheticSaleRow],
    brand: str,
    district: Optional[str] = None,
) -> tuple[list[date], list[float]]:
    """
    Build a monthly time series of total quantity (MT) for a given brand.
    Optionally filter by district ("Chennai" or any outside-Chennai district).
    Returns (dates, quantities) as parallel lists sorted by date.
    """
    monthly: dict[tuple[int, int], float] = {}
    for r in rows:
        if r.brand != brand:
            continue
        if district is not None:
            if district == "Chennai" and r.district != "Chennai":
                continue
            if district == "Outside Chennai" and r.district == "Chennai":
                continue
        key = (r.date.year, r.date.month)
        monthly[key] = monthly.get(key, 0.0) + r.quantity_tons

    sorted_keys = sorted(monthly.keys())
    dates = [date(y, m, 1) for y, m in sorted_keys]
    quantities = [monthly[k] for k in sorted_keys]
    return dates, quantities
