"""
urgency_scorer.py
-----------------
Implements §4.3 Urgency Scoring Algorithm.

For each SKU, computes:
    - days_of_stock_remaining  = fg_stock_mt / avg_daily_demand_mt
    - is_urgent                = days_of_stock_remaining < min_buffer_days
    - urgency_score            = composite sort key

Sort order (§4.3):
    Urgent first → best margin rank → lowest changeover cost → highest P1 demand
    → highest P2 demand

The changeover cost of an SKU depends on the *previous* SKU rolled.
A changeover is incurred when switching between different sizes.
Same size = same brand counts as zero changeover (back-to-back same SKU).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from optimiser.sku_capacity import SKU_CAPACITY, SkuCapacityRecord


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MIN_BUFFER_DAYS: float = 2.0    # Below this → Urgent flag
DEFAULT_FG_STOCK_MT: float = 0.0


@dataclass
class SkuStockState:
    """Current inventory state for one SKU."""
    sku_code: str
    fg_stock_mt: float = 0.0           # Finished goods in stock (MT)
    avg_daily_demand_mt: float = 0.0   # Rolling average daily demand (MT)
    # Derived — set by scorer
    days_of_stock: float = field(default=0.0, init=False)
    is_urgent: bool = field(default=False, init=False)

    def __post_init__(self):
        self._compute()

    def _compute(self):
        if self.avg_daily_demand_mt > 0:
            self.days_of_stock = self.fg_stock_mt / self.avg_daily_demand_mt
        else:
            self.days_of_stock = float("inf")
        self.is_urgent = self.days_of_stock < MIN_BUFFER_DAYS


@dataclass
class ScoredSku:
    """SKU enriched with urgency score and sort key."""
    sku_code: str
    brand_code: str
    size_mm: int
    margin_rank: int
    fg_stock_mt: float
    avg_daily_demand_mt: float
    days_of_stock: float
    is_urgent: bool
    urgency_score: float       # Lower = higher priority
    sort_key: tuple            # For deterministic sort

    @property
    def capacity_record(self) -> SkuCapacityRecord:
        return SKU_CAPACITY[self.sku_code]


def score_skus(
    stock_states: List[SkuStockState],
    demand_today: Dict[str, float],
    previous_sku: Optional[str] = None,
) -> List[ScoredSku]:
    """
    Score and sort all SKUs by operational priority.

    Args:
        stock_states:   Current FG stock + avg demand per SKU.
        demand_today:   Today's forecast demand: sku_code → MT.
        previous_sku:   Last SKU rolled on mill (for changeover cost calc).

    Returns:
        List of ScoredSku sorted by priority (index 0 = highest priority).
    """
    scored: List[ScoredSku] = []

    for state in stock_states:
        rec = SKU_CAPACITY[state.sku_code]

        # Changeover penalty: 1 if switching size, 0 if same size (§1.5: 2hr per switch)
        if previous_sku is None:
            changeover_penalty = 0
        else:
            prev_rec = SKU_CAPACITY[previous_sku]
            changeover_penalty = 0 if prev_rec.size_mm == rec.size_mm else 1

        # Demand today for this SKU (used as tiebreaker)
        today_demand_p1 = demand_today.get(state.sku_code, 0.0) if rec.brand_code == "P1" else 0.0
        today_demand_p2 = demand_today.get(state.sku_code, 0.0) if rec.brand_code == "P2" else 0.0

        # Sort key (ascending = higher priority):
        # (not_urgent, margin_rank, changeover_penalty, -p1_demand, -p2_demand)
        sort_key = (
            0 if state.is_urgent else 1,        # Urgent first
            rec.margin_rank,                     # Best margin rank (1=best)
            changeover_penalty,                  # Lowest changeover
            -today_demand_p1,                    # Highest P1 demand
            -today_demand_p2,                    # Highest P2 demand
        )

        # Urgency score: scalar approximation of sort_key for reporting
        urgency_score = (
            (0 if state.is_urgent else 100) +
            rec.margin_rank * 10 +
            changeover_penalty * 5
        )

        scored.append(ScoredSku(
            sku_code=state.sku_code,
            brand_code=rec.brand_code,
            size_mm=rec.size_mm,
            margin_rank=rec.margin_rank,
            fg_stock_mt=state.fg_stock_mt,
            avg_daily_demand_mt=state.avg_daily_demand_mt,
            days_of_stock=state.days_of_stock,
            is_urgent=state.is_urgent,
            urgency_score=urgency_score,
            sort_key=sort_key,
        ))

    scored.sort(key=lambda s: s.sort_key)
    return scored


def build_stock_states(
    fg_stocks: Dict[str, float],
    demand_vector: Dict[str, float],
) -> List[SkuStockState]:
    """
    Convenience builder: create SkuStockState list from raw dicts.

    Args:
        fg_stocks:      sku_code → current FG stock (MT).
        demand_vector:  sku_code → today's forecast demand (MT) — used as
                        proxy for avg daily demand when no rolling avg available.
    """
    from optimiser.sku_capacity import ALL_SKU_CODES
    states = []
    for sku_code in ALL_SKU_CODES:
        states.append(SkuStockState(
            sku_code=sku_code,
            fg_stock_mt=fg_stocks.get(sku_code, DEFAULT_FG_STOCK_MT),
            avg_daily_demand_mt=demand_vector.get(sku_code, 0.0),
        ))
    return states
