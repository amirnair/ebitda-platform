"""
sku_capacity.py
---------------
Mill throughput (MT/hr) per SKU, changeover time, and daily runtime constants.

Source: §1.5 Key Production Parameters — Parmas sheet values.
Capacity graduates from 18 MT/hr (fine sizes) to 25 MT/hr (heavy sizes)
based on standard rolling mill physics: larger cross-section = faster tonnage.

These values are read from sku_master (company-configured) in production.
For the pilot (AC Industries) we derive from the §1.5 range directly.
"""

from dataclasses import dataclass
from typing import Dict

# ---------------------------------------------------------------------------
# Constants (§1.5)
# ---------------------------------------------------------------------------
CHANGEOVER_HOURS: float = 2.0          # Per SKU switch on mill
STANDARD_RUNTIME_HOURS: float = 16.0  # Per day
ROLLING_FACTOR: float = 1.05           # Billet → TMT yield (uniform all SKUs)

# ---------------------------------------------------------------------------
# SKU capacity table (MT/hr)
# Range 18–25 MT/hr, size-graduated.
# Logic: 8mm rolls slowest (fine wire area), 32mm rolls fastest (big billet).
# ---------------------------------------------------------------------------
_CAPACITY_BY_SIZE_MM: Dict[int, float] = {
    8:  18.0,
    10: 19.5,
    12: 20.5,
    16: 21.5,
    20: 22.5,
    25: 23.5,
    32: 25.0,
}


@dataclass(frozen=True)
class SkuCapacityRecord:
    sku_code: str
    size_mm: int
    brand_code: str          # P1 or P2
    capacity_mt_hr: float    # Mill throughput for this SKU
    margin_rank: int         # 1 = highest margin (from sku_master §5.2)
    billet_type: str         # e.g. "P1-6M"
    billet_length_m: float


# ---------------------------------------------------------------------------
# Full SKU master — mirrors §1.3 / §1.4 / §5.3 sku_master table
# ---------------------------------------------------------------------------
_SKU_DEFINITIONS = [
    # (sku_code,      size_mm, brand, margin_rank, billet_type,  billet_length_m)
    ("P1-SKU-8",   8,  "P1", 7,  "P1-6M",    6.00),
    ("P1-SKU-10",  10, "P1", 2,  "P1-6M",    6.00),
    ("P1-SKU-12",  12, "P1", 3,  "P1-6M",    6.00),
    ("P1-SKU-16",  16, "P1", 1,  "P1-6M",    6.00),
    ("P1-SKU-20",  20, "P1", 4,  "P1-6M",    6.00),
    ("P1-SKU-25",  25, "P1", 5,  "P1-5.6M",  5.60),
    ("P1-SKU-32",  32, "P1", 6,  "P1-5.05M", 5.05),
    ("P2-SKU-8",   8,  "P2", 14, "P2-6M",    6.00),
    ("P2-SKU-10",  10, "P2", 9,  "P2-6M",    6.00),
    ("P2-SKU-12",  12, "P2", 10, "P2-6M",    6.00),
    ("P2-SKU-16",  16, "P2", 8,  "P2-6M",    6.00),
    ("P2-SKU-20",  20, "P2", 11, "P2-6M",    6.00),
    ("P2-SKU-25",  25, "P2", 12, "P2-5.6M",  5.60),
    ("P2-SKU-32",  32, "P2", 13, "P2-4.9M",  4.90),
]

# Build lookup dict: sku_code → SkuCapacityRecord
SKU_CAPACITY: Dict[str, SkuCapacityRecord] = {
    sku_code: SkuCapacityRecord(
        sku_code=sku_code,
        size_mm=size_mm,
        brand_code=brand,
        capacity_mt_hr=_CAPACITY_BY_SIZE_MM[size_mm],
        margin_rank=margin_rank,
        billet_type=billet_type,
        billet_length_m=billet_length_m,
    )
    for sku_code, size_mm, brand, margin_rank, billet_type, billet_length_m
    in _SKU_DEFINITIONS
}

ALL_SKU_CODES = list(SKU_CAPACITY.keys())
P1_SKU_CODES = [k for k, v in SKU_CAPACITY.items() if v.brand_code == "P1"]
P2_SKU_CODES = [k for k, v in SKU_CAPACITY.items() if v.brand_code == "P2"]


def get_capacity(sku_code: str) -> float:
    """Return mill throughput (MT/hr) for a given SKU."""
    return SKU_CAPACITY[sku_code].capacity_mt_hr


def hours_to_produce(sku_code: str, qty_mt: float) -> float:
    """Calculate mill hours required to produce qty_mt tonnes of sku_code."""
    if qty_mt <= 0:
        return 0.0
    return qty_mt / get_capacity(sku_code)


def max_production_in_hours(sku_code: str, hours: float) -> float:
    """Maximum MT producible for sku_code in given hours."""
    return hours * get_capacity(sku_code)
