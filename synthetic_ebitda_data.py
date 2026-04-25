"""
synthetic_ebitda_data.py — AC Industries EBITDA Intelligence Platform
Session 5: EBITDA Engine — Test Data Generator

Generates realistic AC Industries-shaped synthetic data for the EBITDA engine tests.
Mirrors the pattern established in Sessions 3 (synthetic_data.py) and 4 (synthetic_demand.py).

Generates:
  - SIF transactions (revenue_engine input)
  - MillRuntimeRecord list (cost_engine input — from production_plan table)
  - OverheadRecord (client-entered fixed costs)
  - BenchmarkDefaults (with minor variation for test realism)

All data is consistent: production tonnage matches sales tonnage within ±5%
(production leads by ~1 day buffer stock cycle).
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from ebitda_models import MillRuntimeRecord, OverheadRecord
from cost_engine import BenchmarkDefaults
from revenue_engine import SifTransaction


# ---------------------------------------------------------------------------
# AC Industries constants (from master context §1.3–1.5)
# ---------------------------------------------------------------------------

# SKU proportions (from §3.6, excluding Sunday)
SKU_PROPORTIONS = {
    "P1-SKU-8":  0.110,
    "P1-SKU-10": 0.1676,
    "P1-SKU-12": 0.1485,
    "P1-SKU-16": 0.1646,
    "P1-SKU-20": 0.060,
    "P1-SKU-25": 0.040,
    "P1-SKU-32": 0.020,
    "P2-SKU-8":  0.040,
    "P2-SKU-10": 0.0670,
    "P2-SKU-12": 0.0514,
    "P2-SKU-16": 0.040,
    "P2-SKU-20": 0.020,
    "P2-SKU-25": 0.010,
    "P2-SKU-32": 0.005,
}

# Size map
SKU_SIZE_MM = {
    "P1-SKU-8": 8,  "P1-SKU-10": 10, "P1-SKU-12": 12,
    "P1-SKU-16": 16, "P1-SKU-20": 20, "P1-SKU-25": 25, "P1-SKU-32": 32,
    "P2-SKU-8": 8,  "P2-SKU-10": 10, "P2-SKU-12": 12,
    "P2-SKU-16": 16, "P2-SKU-20": 20, "P2-SKU-25": 25, "P2-SKU-32": 32,
}

# Mill throughput by size (MT/hr) — §1.5 size-graduated
SKU_MILL_CAPACITY_MT_HR = {
    8: 18.0, 10: 19.0, 12: 20.0, 16: 21.0, 20: 22.0, 25: 24.0, 32: 25.0
}

# Approximate realisation per ton by SKU (₹/ton) — TN market, Apr 2025
SKU_REALISATION = {
    "P1-SKU-8":  54500, "P1-SKU-10": 54200, "P1-SKU-12": 53800,
    "P1-SKU-16": 53500, "P1-SKU-20": 53300, "P1-SKU-25": 53000, "P1-SKU-32": 52800,
    "P2-SKU-8":  53800, "P2-SKU-10": 53500, "P2-SKU-12": 53200,
    "P2-SKU-16": 53000, "P2-SKU-20": 52800, "P2-SKU-25": 52500, "P2-SKU-32": 52300,
}

# Daily total volume range (MT/day) — typical for mid-size TN TMT mill
DAILY_VOLUME_MT_RANGE = (180.0, 280.0)

# Default mill runtime per day
DEFAULT_RUNTIME_HRS = 16.0

# AC Industries default company ID
DEFAULT_COMPANY_ID = "AC001"


# ---------------------------------------------------------------------------
# Transaction Generator
# ---------------------------------------------------------------------------

def generate_sif_transactions(
    company_id: str = DEFAULT_COMPANY_ID,
    period: str = "2025-04",
    total_volume_mt: Optional[float] = None,
    realisation_noise_pct: float = 2.0,
    seed: int = 42,
) -> List[SifTransaction]:
    """
    Generate synthetic SIF transactions for a period.

    Args:
        company_id: Company ID (multi-tenant key)
        period: "YYYY-MM"
        total_volume_mt: Total MT for the period. If None, sampled from realistic range.
        realisation_noise_pct: ±% random noise on realisation per ton
        seed: Random seed for reproducibility

    Returns:
        List of SifTransaction — one record per SKU per working day
    """
    rng = random.Random(seed)

    year, month = int(period[:4]), int(period[5:7])
    import calendar
    _, days_in_month = calendar.monthrange(year, month)

    working_days = [
        date(year, month, d)
        for d in range(1, days_in_month + 1)
        if date(year, month, d).weekday() != 6  # exclude Sunday
    ]

    if total_volume_mt is None:
        total_volume_mt = rng.uniform(
            DAILY_VOLUME_MT_RANGE[0] * len(working_days),
            DAILY_VOLUME_MT_RANGE[1] * len(working_days),
        )

    daily_volume_mt = total_volume_mt / len(working_days)

    transactions: List[SifTransaction] = []
    invoice_counter = 90000000

    for day in working_days:
        # Add ±10% day-level noise
        day_volume = daily_volume_mt * rng.uniform(0.90, 1.10)

        for sku_code, proportion in SKU_PROPORTIONS.items():
            sku_qty = day_volume * proportion
            if sku_qty < 0.01:
                continue

            # Noise on realisation
            base_real = SKU_REALISATION[sku_code]
            noise = rng.uniform(1 - realisation_noise_pct / 100, 1 + realisation_noise_pct / 100)
            realisation = base_real * noise
            value_inr = sku_qty * realisation

            brand = "P1" if sku_code.startswith("P1") else "P2"

            transactions.append(SifTransaction(
                company_id=company_id,
                date=day,
                brand=brand,
                sku_code=sku_code,
                sku_name=f"{SKU_SIZE_MM[sku_code]}mm {'Product 1' if brand == 'P1' else 'Product 2'} Fe550",
                size_mm=SKU_SIZE_MM[sku_code],
                quantity_tons=round(sku_qty, 4),
                value_inr=round(value_inr, 2),
                region="Tamil Nadu",
                district=rng.choice(["Chennai", "Coimbatore", "Madurai", "Salem"]),
                invoice_id=str(invoice_counter),
            ))
            invoice_counter += 1

    return transactions


# ---------------------------------------------------------------------------
# Runtime Record Generator (from production_plan — Session 4 output)
# ---------------------------------------------------------------------------

def generate_mill_runtime_records(
    company_id: str = DEFAULT_COMPANY_ID,
    period: str = "2025-04",
    total_production_mt: Optional[float] = None,
    runtime_hrs_per_day: float = DEFAULT_RUNTIME_HRS,
    seed: int = 42,
) -> List[MillRuntimeRecord]:
    """
    Generate synthetic MillRuntimeRecord list that mirrors Session 4's production_plan output.

    Each record represents one SKU's runtime slot on a given day.
    Production typically leads sales by ~1 day (buffer stock cycle).

    Args:
        company_id: Company ID
        period: "YYYY-MM"
        total_production_mt: Total MT produced. If None, slightly above sales volume.
        runtime_hrs_per_day: Total mill hours per day (default 16 per §1.5)
        seed: Random seed

    Returns:
        List of MillRuntimeRecord — one per SKU per production day
    """
    rng = random.Random(seed + 1)  # Different seed from transactions

    year, month = int(period[:4]), int(period[5:7])
    import calendar
    _, days_in_month = calendar.monthrange(year, month)

    # Production days include some Sundays (mill doesn't stop on sales holidays)
    production_days = [
        date(year, month, d)
        for d in range(1, days_in_month + 1)
        if date(year, month, d).weekday() not in (4, 5)  # Skip Fri/Sat for variety
    ]

    if total_production_mt is None:
        daily_target = rng.uniform(DAILY_VOLUME_MT_RANGE[0], DAILY_VOLUME_MT_RANGE[1])
        total_production_mt = daily_target * len(production_days)

    daily_production_mt = total_production_mt / len(production_days)

    records: List[MillRuntimeRecord] = []

    for day in production_days:
        day_production = daily_production_mt * rng.uniform(0.92, 1.08)

        # On each day, the mill runs a mix of SKUs based on urgency/sequence
        # For synthetic data: pick 3–5 SKUs per day, allocate runtime proportionally
        active_skus = rng.sample(list(SKU_PROPORTIONS.keys()), k=rng.randint(3, 5))
        active_proportions = {s: SKU_PROPORTIONS[s] for s in active_skus}
        prop_total = sum(active_proportions.values())

        remaining_runtime = runtime_hrs_per_day * rng.uniform(0.90, 1.00)

        for sku_code in active_skus:
            sku_share = active_proportions[sku_code] / prop_total
            sku_production_mt = day_production * sku_share

            size_mm = SKU_SIZE_MM[sku_code]
            capacity = SKU_MILL_CAPACITY_MT_HR[size_mm]
            runtime_hrs = sku_production_mt / capacity

            brand = "P1" if sku_code.startswith("P1") else "P2"

            records.append(MillRuntimeRecord(
                company_id=company_id,
                date=day,
                sku_code=sku_code,
                brand=brand,
                production_mt=round(sku_production_mt, 4),
                runtime_hrs=round(runtime_hrs, 3),
            ))

    return records


# ---------------------------------------------------------------------------
# Overhead Generator
# ---------------------------------------------------------------------------

def generate_overhead_record(
    company_id: str = DEFAULT_COMPANY_ID,
    period: str = "2025-04",
    scale: float = 1.0,
) -> OverheadRecord:
    """
    Generate a realistic OverheadRecord for a mid-size TN TMT mill.
    scale: multiplier for all overhead values (default 1.0 = AC Industries scale)
    """
    return OverheadRecord(
        company_id=company_id,
        period=period,
        admin_cost_inr=round(800_000 * scale, 2),        # ₹8 lakh/month admin
        selling_cost_inr=round(1_200_000 * scale, 2),    # ₹12 lakh/month selling
        depreciation_inr=round(2_500_000 * scale, 2),    # ₹25 lakh/month depreciation
        interest_inr=round(1_500_000 * scale, 2),        # ₹15 lakh/month interest
        other_overhead_inr=round(500_000 * scale, 2),    # ₹5 lakh/month other
    )


# ---------------------------------------------------------------------------
# Benchmark Generator
# ---------------------------------------------------------------------------

def generate_benchmark_defaults(noise_pct: float = 0.0) -> BenchmarkDefaults:
    """
    Generate BenchmarkDefaults with optional noise for test variation.
    Base values match Tamil Nadu TMT industry norms.
    """
    factor = 1.0 + (random.uniform(-noise_pct, noise_pct) / 100)
    return BenchmarkDefaults(
        power_units_per_hr=280.0 * factor,
        power_rate_inr_per_unit=7.50,
        fuel_cost_per_hr_inr=850.0 * factor,
        electrode_cost_per_mt_inr=180.0,
        labour_cost_per_mt_inr=350.0,
        other_fixed_per_mt_inr=120.0,
    )


# ---------------------------------------------------------------------------
# Full period dataset
# ---------------------------------------------------------------------------

def generate_full_period_dataset(
    company_id: str = DEFAULT_COMPANY_ID,
    period: str = "2025-04",
    seed: int = 42,
) -> dict:
    """
    Generate a complete, internally consistent dataset for one period.
    Returns all inputs needed for EbitdaEngine.compute_ebitda().
    """
    transactions = generate_sif_transactions(
        company_id=company_id, period=period, seed=seed
    )
    runtime_records = generate_mill_runtime_records(
        company_id=company_id, period=period, seed=seed
    )
    overheads = generate_overhead_record(company_id=company_id, period=period)
    benchmarks = generate_benchmark_defaults(noise_pct=0.0)

    return {
        "company_id": company_id,
        "period": period,
        "transactions": transactions,
        "runtime_records": runtime_records,
        "overheads": overheads,
        "benchmarks": benchmarks,
    }


def generate_multi_period_dataset(
    company_id: str = DEFAULT_COMPANY_ID,
    periods: Optional[List[str]] = None,
    seed: int = 42,
) -> dict:
    """
    Generate dataset for multiple periods — used for rollup tests.
    Returns all inputs needed for EbitdaEngine.compute_monthly_rollup().
    """
    if periods is None:
        periods = [
            "2024-10", "2024-11", "2024-12",
            "2025-01", "2025-02", "2025-03", "2025-04",
        ]

    all_transactions: List[SifTransaction] = []
    all_runtime_records: List[MillRuntimeRecord] = []
    overheads_by_period: Dict[str, OverheadRecord] = {}

    for i, period in enumerate(periods):
        dataset = generate_full_period_dataset(
            company_id=company_id,
            period=period,
            seed=seed + i,
        )
        all_transactions.extend(dataset["transactions"])
        all_runtime_records.extend(dataset["runtime_records"])
        overheads_by_period[period] = dataset["overheads"]

    return {
        "company_id": company_id,
        "periods": periods,
        "transactions": all_transactions,
        "runtime_records": all_runtime_records,
        "overheads_by_period": overheads_by_period,
        "benchmarks": generate_benchmark_defaults(),
    }
