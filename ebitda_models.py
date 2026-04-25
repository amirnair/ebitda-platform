"""
ebitda_models.py — AC Industries EBITDA Intelligence Platform
Session 5: EBITDA Engine — Typed Output Dataclasses

All dataclasses are immutable (frozen=True) and JSON-serialisable via asdict().
Covers all three EBITDA cycles:
  - Revenue Lifecycle  (Phase 1 — live)
  - Production Cost    (Phase 2 — data partial)
  - Raw Material       (Phase 3 — stub, returns zeros)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Revenue Cycle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RealisationRecord:
    """Per-SKU realisation for a single day or aggregated period."""
    company_id: str
    period: str               # "YYYY-MM" for monthly, "YYYY-MM-DD" for daily
    brand: str                # "P1" | "P2"
    sku_code: str             # e.g. "P1-SKU-16"
    size_mm: int
    quantity_tons: float
    value_inr: float
    realisation_per_ton: float   # Derived: value_inr / quantity_tons


@dataclass(frozen=True)
class RevenueRecord:
    """Aggregated revenue for a company × period × brand."""
    company_id: str
    period: str                            # "YYYY-MM"
    brand: str
    total_quantity_tons: float
    total_value_inr: float
    blended_realisation_per_ton: float     # Σvalue / Σqty across all SKUs in brand
    sku_detail: List[RealisationRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Production Cost Cycle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MillRuntimeRecord:
    """
    Per-SKU runtime hours sourced from the production_plan table (Session 4 output).
    This is the primary driver for variable cost calculation.
    runtime_hrs comes from DailyProductionPlan.runtime_hrs_p1 / runtime_hrs_p2.
    """
    company_id: str
    date: date
    sku_code: str
    brand: str
    production_mt: float        # Actual / planned MT produced
    runtime_hrs: float          # Mill hours consumed — drives power + fuel cost


@dataclass(frozen=True)
class ProductionCostInputs:
    """
    Raw cost inputs for a single month.
    Variable costs are driven by runtime_hrs; fixed costs are flat per month.

    Benchmark defaults (from benchmarks table) are used when client has not
    overridden. Client overrides win when benchmark_config.is_overridden = True.
    """
    company_id: str
    period: str                       # "YYYY-MM"

    # Variable — driven by runtime hours (from production_plan / production_log)
    power_units_per_hr: float         # kWh consumed per mill running hour
    power_rate_inr_per_unit: float    # ₹ per kWh
    fuel_cost_per_hr_inr: float       # ₹ per mill running hour (diesel/gas)

    # Fixed — per month regardless of output
    electrode_cost_inr: float         # Total electrode cost for month
    labour_cost_inr: float            # Total labour cost for month
    other_fixed_cost_inr: float       # Maintenance, stores, misc.

    # Production volume for cost/ton normalisation
    total_production_mt: float        # Total MT produced in month (P1 + P2)
    total_runtime_hrs: float          # Total mill hours in month


@dataclass(frozen=True)
class ProductionCostRecord:
    """
    Computed production cost breakdown for a company × period.
    cost_per_ton is the key output: feeds EBITDA calculation.
    """
    company_id: str
    period: str

    # Variable costs (runtime-driven)
    power_cost_inr: float             # power_units_per_hr × runtime_hrs × power_rate
    fuel_cost_inr: float              # fuel_cost_per_hr × runtime_hrs

    # Fixed costs
    electrode_cost_inr: float
    labour_cost_inr: float
    other_fixed_cost_inr: float

    # Totals
    total_variable_cost_inr: float    # power + fuel
    total_fixed_cost_inr: float       # electrode + labour + other
    total_production_cost_inr: float  # variable + fixed

    # Normalised
    total_production_mt: float
    total_runtime_hrs: float
    cost_per_ton_inr: float           # total_production_cost / total_production_mt

    # Audit: inputs snapshot
    power_units_per_hr: float
    power_rate_inr_per_unit: float
    fuel_cost_per_hr_inr: float

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Raw Material Cycle — Phase 3 Stub
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawMaterialRecord:
    """
    # Phase 3 — Raw Material (Scrap → Billet) cycle.
    Stub: all cost fields return zero. Wire-up only.
    Will be populated in Phase 3 when scrap procurement data is available.
    """
    company_id: str
    period: str

    # Phase 3 fields — all zero until populated
    scrap_qty_tons: float = 0.0
    scrap_cost_per_ton_inr: float = 0.0
    billet_output_tons: float = 0.0
    yield_pct: float = 0.0            # billet_output / scrap_qty × 100
    consumables_cost_inr: float = 0.0
    total_raw_material_cost_inr: float = 0.0
    raw_material_cost_per_ton_inr: float = 0.0

    # Phase 3 flag — downstream code checks this before using RM cost
    is_phase3_stub: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Overheads
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OverheadRecord:
    """
    Fixed overheads — client-entered once, referenced each period.
    Covers SG&A, depreciation, interest, and any other below-the-line items
    that are not production costs.
    """
    company_id: str
    period: str
    admin_cost_inr: float = 0.0
    selling_cost_inr: float = 0.0
    depreciation_inr: float = 0.0
    interest_inr: float = 0.0
    other_overhead_inr: float = 0.0

    @property
    def total_overhead_inr(self) -> float:
        return (
            self.admin_cost_inr
            + self.selling_cost_inr
            + self.depreciation_inr
            + self.interest_inr
            + self.other_overhead_inr
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_overhead_inr"] = self.total_overhead_inr
        return d


# ---------------------------------------------------------------------------
# SKU Margin
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkuMarginRecord:
    """
    Contribution margin per SKU for a period.
    Production cost is allocated to SKU pro-rata by runtime_hrs share.
    Raw material cost is Phase 3 stub (zero).
    """
    company_id: str
    period: str
    brand: str
    sku_code: str
    size_mm: int

    quantity_tons: float
    revenue_inr: float
    realisation_per_ton: float

    # Cost allocation
    production_cost_allocated_inr: float   # Pro-rata by runtime share
    raw_material_cost_allocated_inr: float # Phase 3 — zero
    total_cost_allocated_inr: float

    # Margin
    contribution_inr: float               # revenue − production_cost − rm_cost
    contribution_per_ton: float
    contribution_margin_pct: float        # contribution / revenue × 100

    # Runtime share used for allocation (audit)
    runtime_hrs: float
    runtime_share_pct: float

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# EBITDA Result — Core Output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EbitdaResult:
    """
    Monthly EBITDA output — the primary output of the EBITDA Engine.
    One record per company × period.

    EBITDA = Revenue − Raw Material Cost − Production Cost − Overheads
    (Raw Material is Phase 3 stub = 0 until Phase 3 is built)
    """
    company_id: str
    period: str                    # "YYYY-MM"

    # Revenue (Phase 1)
    total_revenue_inr: float
    total_quantity_tons: float
    blended_realisation_per_ton: float

    # Raw Material Cost (Phase 3 stub — zero)
    raw_material_cost_inr: float   # Always 0.0 until Phase 3
    raw_material_cost_per_ton: float
    is_rm_stub: bool               # True until Phase 3

    # Production Cost (Phase 2)
    production_cost_inr: float
    production_cost_per_ton: float
    total_runtime_hrs: float
    total_production_mt: float

    # Overheads
    overhead_inr: float

    # EBITDA
    ebitda_inr: float              # revenue − rm − prod_cost − overheads
    ebitda_margin_pct: float       # ebitda / revenue × 100
    ebitda_per_ton: float          # ebitda / total_quantity_tons

    # Brand split (informational)
    p1_revenue_inr: float
    p2_revenue_inr: float
    p1_quantity_tons: float
    p2_quantity_tons: float

    # SKU-level margins
    sku_margins: List[SkuMarginRecord] = field(default_factory=list)

    # Metadata
    data_completeness_pct: float = 100.0   # < 100 if some days missing data
    has_warnings: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Monthly Rollup — Trend Series
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MonthlyEbitdaRollup:
    """
    Time-series of EBITDA results for a company — used for trend charts
    on the EBITDA Command Centre (Screen 1) and Strategy Dashboard (Screen 9).
    """
    company_id: str
    periods: List[str]                 # ["2024-01", "2024-02", ...]
    results: List[EbitdaResult]        # One per period, same order as periods

    # Pre-computed trend metrics
    latest_ebitda_inr: float
    latest_ebitda_margin_pct: float
    avg_ebitda_margin_pct: float       # Rolling average across all periods
    best_period: str
    worst_period: str
    trend_direction: str               # "improving" | "declining" | "stable"

    def to_dict(self) -> dict:
        return {
            "company_id": self.company_id,
            "periods": self.periods,
            "results": [r.to_dict() for r in self.results],
            "latest_ebitda_inr": self.latest_ebitda_inr,
            "latest_ebitda_margin_pct": self.latest_ebitda_margin_pct,
            "avg_ebitda_margin_pct": self.avg_ebitda_margin_pct,
            "best_period": self.best_period,
            "worst_period": self.worst_period,
            "trend_direction": self.trend_direction,
        }


# ---------------------------------------------------------------------------
# Simulator Input/Output — Screen 8
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SimulatorInputs:
    """
    What-if slider values for EBITDA Simulator (Screen 8).
    All fields are deltas or overrides relative to a base period.
    """
    base_period: str                          # Reference period to simulate from
    scrap_price_delta_pct: float = 0.0        # % change in scrap cost
    realisation_delta_pct: float = 0.0        # % change in selling price
    volume_delta_pct: float = 0.0             # % change in sales volume
    power_rate_delta_pct: float = 0.0         # % change in power cost
    yield_delta_pct: float = 0.0              # % change in billet yield


@dataclass(frozen=True)
class SimulatorResult:
    """
    Output of EBITDA Simulator — base vs simulated comparison.
    """
    base_period: str
    inputs: SimulatorInputs

    base_revenue_inr: float
    simulated_revenue_inr: float
    revenue_delta_inr: float

    base_production_cost_inr: float
    simulated_production_cost_inr: float
    production_cost_delta_inr: float

    base_raw_material_cost_inr: float         # Phase 3 stub — zero
    simulated_raw_material_cost_inr: float    # Phase 3 stub — zero

    base_ebitda_inr: float
    simulated_ebitda_inr: float
    ebitda_delta_inr: float

    base_ebitda_margin_pct: float
    simulated_ebitda_margin_pct: float
    margin_delta_pct: float

    def to_dict(self) -> dict:
        return asdict(self)
