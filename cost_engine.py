"""
cost_engine.py — AC Industries EBITDA Intelligence Platform
Session 5: EBITDA Engine — Production Cost Cycle

Key design decision (confirmed Session 5):
    Power cost and fuel cost are driven by ACTUAL MILL RUNTIME HOURS,
    not by tonnage benchmarks.

    Formula:
        power_cost  = power_units_per_hr × runtime_hrs × power_rate_inr_per_unit
        fuel_cost   = fuel_cost_per_hr_inr × runtime_hrs
        cost_per_ton = (power_cost + fuel_cost + electrode + labour + other) / production_mt

    Runtime hours come from the production_plan table — specifically the
    runtime_hrs fields output by Session 4's generate_daily_plan().

Benchmark defaults are used when client has not overridden via Settings → Benchmarks.
Client overrides always win.

Public entry point:
    compute_production_cost(company_id, period, runtime_records, inputs) -> ProductionCostRecord
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from ebitda_models import (
    MillRuntimeRecord,
    ProductionCostInputs,
    ProductionCostRecord,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Industry Benchmarks — defaults when client has not overridden
# These are loaded from the benchmarks table at runtime.
# Values here are fallback defaults only — never used if DB is available.
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkDefaults:
    """
    Default production cost benchmarks for TMT rebar manufacturing.
    All values are per-hour of mill runtime unless noted.
    Source: Industry standard for Tamil Nadu TMT mills.
    """
    power_units_per_hr: float = 280.0          # kWh per mill hour (280–320 kWh typical)
    power_rate_inr_per_unit: float = 7.50      # ₹/kWh — Tamil Nadu industrial tariff
    fuel_cost_per_hr_inr: float = 850.0        # ₹/hr — diesel/LPG for reheating furnace
    electrode_cost_per_mt_inr: float = 180.0   # ₹/MT — graphite electrode consumption
    labour_cost_per_mt_inr: float = 350.0      # ₹/MT — direct + indirect labour
    other_fixed_per_mt_inr: float = 120.0      # ₹/MT — maintenance, stores, misc.


BENCHMARK_DEFAULTS = BenchmarkDefaults()


# ---------------------------------------------------------------------------
# Cost Engine
# ---------------------------------------------------------------------------

class CostEngine:
    """
    Computes production cost from mill runtime records (Session 4 output).

    The separation of variable (runtime-driven) and fixed costs is critical:
      - Variable: Power + Fuel — scale exactly with runtime_hrs
      - Fixed: Electrode + Labour + Other — aggregated for the month,
        then normalised by total production MT for cost/ton

    Usage:
        engine = CostEngine(company_id="AC001")
        cost_record = engine.compute_production_cost(
            period="2025-04",
            runtime_records=daily_runtime_list,
            benchmarks=client_benchmarks,          # from benchmarks table
        )
    """

    def __init__(self, company_id: str):
        self.company_id = company_id

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def compute_production_cost(
        self,
        period: str,
        runtime_records: List[MillRuntimeRecord],
        benchmarks: Optional[BenchmarkDefaults] = None,
        overhead_electrode_inr: Optional[float] = None,
        overhead_labour_inr: Optional[float] = None,
        overhead_other_inr: Optional[float] = None,
    ) -> ProductionCostRecord:
        """
        Compute production cost for a period from runtime records.

        Args:
            period: "YYYY-MM"
            runtime_records: List of MillRuntimeRecord — one per SKU per day,
                             sourced from the production_plan table (Session 4 output).
                             Fields used: runtime_hrs, production_mt, sku_code, brand.
            benchmarks: BenchmarkDefaults from client's benchmark_config table.
                        Falls back to BENCHMARK_DEFAULTS if not provided.
            overhead_electrode_inr: Monthly electrode cost total (overrides benchmark
                                    per-MT rate if provided). Use when client tracks
                                    actual electrode spend in ₹.
            overhead_labour_inr: Monthly labour cost total (overrides benchmark).
            overhead_other_inr: Monthly other fixed cost total (overrides benchmark).

        Returns:
            ProductionCostRecord with full cost breakdown and cost_per_ton.
        """
        bm = benchmarks or BENCHMARK_DEFAULTS

        period_records = [
            r for r in runtime_records
            if r.company_id == self.company_id and self._period_of(r) == period
        ]

        if not period_records:
            logger.warning(
                "CostEngine: no runtime records for company=%s period=%s — "
                "returning zero cost record",
                self.company_id, period
            )
            return self._zero_record(period)

        # Aggregate runtime and production across all SKUs for the period
        total_runtime_hrs = sum(r.runtime_hrs for r in period_records)
        total_production_mt = sum(r.production_mt for r in period_records)

        # ------------------------------------------------------------------
        # Variable Costs — driven by runtime hours
        # Formula confirmed Session 5:
        #   power_cost = power_units_per_hr × runtime_hrs × power_rate
        #   fuel_cost  = fuel_cost_per_hr × runtime_hrs
        # ------------------------------------------------------------------
        power_cost_inr = (
            bm.power_units_per_hr
            * total_runtime_hrs
            * bm.power_rate_inr_per_unit
        )
        fuel_cost_inr = bm.fuel_cost_per_hr_inr * total_runtime_hrs

        # ------------------------------------------------------------------
        # Fixed Costs — monthly totals
        # Use client-provided actuals if available, else derive from benchmark rate × MT
        # ------------------------------------------------------------------
        if overhead_electrode_inr is not None:
            electrode_cost_inr = overhead_electrode_inr
        else:
            electrode_cost_inr = bm.electrode_cost_per_mt_inr * total_production_mt

        if overhead_labour_inr is not None:
            labour_cost_inr = overhead_labour_inr
        else:
            labour_cost_inr = bm.labour_cost_per_mt_inr * total_production_mt

        if overhead_other_inr is not None:
            other_fixed_cost_inr = overhead_other_inr
        else:
            other_fixed_cost_inr = bm.other_fixed_per_mt_inr * total_production_mt

        # ------------------------------------------------------------------
        # Totals and cost/ton normalisation
        # ------------------------------------------------------------------
        total_variable_cost_inr = power_cost_inr + fuel_cost_inr
        total_fixed_cost_inr = electrode_cost_inr + labour_cost_inr + other_fixed_cost_inr
        total_production_cost_inr = total_variable_cost_inr + total_fixed_cost_inr

        if total_production_mt <= 0:
            logger.warning(
                "CostEngine: total_production_mt=0 for company=%s period=%s — "
                "cost_per_ton will be 0",
                self.company_id, period
            )
            cost_per_ton_inr = 0.0
        else:
            cost_per_ton_inr = total_production_cost_inr / total_production_mt

        return ProductionCostRecord(
            company_id=self.company_id,
            period=period,
            power_cost_inr=round(power_cost_inr, 2),
            fuel_cost_inr=round(fuel_cost_inr, 2),
            electrode_cost_inr=round(electrode_cost_inr, 2),
            labour_cost_inr=round(labour_cost_inr, 2),
            other_fixed_cost_inr=round(other_fixed_cost_inr, 2),
            total_variable_cost_inr=round(total_variable_cost_inr, 2),
            total_fixed_cost_inr=round(total_fixed_cost_inr, 2),
            total_production_cost_inr=round(total_production_cost_inr, 2),
            total_production_mt=round(total_production_mt, 4),
            total_runtime_hrs=round(total_runtime_hrs, 2),
            cost_per_ton_inr=round(cost_per_ton_inr, 2),
            power_units_per_hr=bm.power_units_per_hr,
            power_rate_inr_per_unit=bm.power_rate_inr_per_unit,
            fuel_cost_per_hr_inr=bm.fuel_cost_per_hr_inr,
        )

    def compute_production_cost_from_inputs(
        self,
        inputs: ProductionCostInputs,
    ) -> ProductionCostRecord:
        """
        Alternative entry point when cost inputs are pre-assembled
        (e.g., loaded directly from production_costs table).
        Performs the same runtime-driven calculation from structured inputs.
        """
        power_cost_inr = (
            inputs.power_units_per_hr
            * inputs.total_runtime_hrs
            * inputs.power_rate_inr_per_unit
        )
        fuel_cost_inr = inputs.fuel_cost_per_hr_inr * inputs.total_runtime_hrs

        total_variable_cost_inr = power_cost_inr + fuel_cost_inr
        total_fixed_cost_inr = (
            inputs.electrode_cost_inr
            + inputs.labour_cost_inr
            + inputs.other_fixed_cost_inr
        )
        total_production_cost_inr = total_variable_cost_inr + total_fixed_cost_inr

        cost_per_ton_inr = (
            total_production_cost_inr / inputs.total_production_mt
            if inputs.total_production_mt > 0
            else 0.0
        )

        return ProductionCostRecord(
            company_id=inputs.company_id,
            period=inputs.period,
            power_cost_inr=round(power_cost_inr, 2),
            fuel_cost_inr=round(fuel_cost_inr, 2),
            electrode_cost_inr=round(inputs.electrode_cost_inr, 2),
            labour_cost_inr=round(inputs.labour_cost_inr, 2),
            other_fixed_cost_inr=round(inputs.other_fixed_cost_inr, 2),
            total_variable_cost_inr=round(total_variable_cost_inr, 2),
            total_fixed_cost_inr=round(total_fixed_cost_inr, 2),
            total_production_cost_inr=round(total_production_cost_inr, 2),
            total_production_mt=round(inputs.total_production_mt, 4),
            total_runtime_hrs=round(inputs.total_runtime_hrs, 2),
            cost_per_ton_inr=round(cost_per_ton_inr, 2),
            power_units_per_hr=inputs.power_units_per_hr,
            power_rate_inr_per_unit=inputs.power_rate_inr_per_unit,
            fuel_cost_per_hr_inr=inputs.fuel_cost_per_hr_inr,
        )

    def sku_cost_allocation(
        self,
        cost_record: ProductionCostRecord,
        runtime_records: List[MillRuntimeRecord],
        period: str,
    ) -> Dict[str, float]:
        """
        Allocate total production cost to individual SKUs pro-rata by runtime_hrs.

        Returns:
            Dict mapping sku_code → allocated_cost_inr

        Used by ebitda_engine.py when building SkuMarginRecord.
        """
        period_records = [
            r for r in runtime_records
            if r.company_id == self.company_id and self._period_of(r) == period
        ]

        total_runtime = sum(r.runtime_hrs for r in period_records)
        if total_runtime <= 0:
            return {r.sku_code: 0.0 for r in period_records}

        allocation: Dict[str, float] = {}
        for rec in period_records:
            share = rec.runtime_hrs / total_runtime
            allocated = share * cost_record.total_production_cost_inr
            # Accumulate if same SKU appears across multiple days
            allocation[rec.sku_code] = allocation.get(rec.sku_code, 0.0) + allocated

        return {k: round(v, 2) for k, v in allocation.items()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _zero_record(self, period: str) -> ProductionCostRecord:
        """Return an all-zero ProductionCostRecord when no data is available."""
        return ProductionCostRecord(
            company_id=self.company_id,
            period=period,
            power_cost_inr=0.0,
            fuel_cost_inr=0.0,
            electrode_cost_inr=0.0,
            labour_cost_inr=0.0,
            other_fixed_cost_inr=0.0,
            total_variable_cost_inr=0.0,
            total_fixed_cost_inr=0.0,
            total_production_cost_inr=0.0,
            total_production_mt=0.0,
            total_runtime_hrs=0.0,
            cost_per_ton_inr=0.0,
            power_units_per_hr=BENCHMARK_DEFAULTS.power_units_per_hr,
            power_rate_inr_per_unit=BENCHMARK_DEFAULTS.power_rate_inr_per_unit,
            fuel_cost_per_hr_inr=BENCHMARK_DEFAULTS.fuel_cost_per_hr_inr,
        )

    @staticmethod
    def _period_of(record: MillRuntimeRecord) -> str:
        return record.date.strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def compute_production_cost(
    company_id: str,
    period: str,
    runtime_records: List[MillRuntimeRecord],
    benchmarks: Optional[BenchmarkDefaults] = None,
    overhead_electrode_inr: Optional[float] = None,
    overhead_labour_inr: Optional[float] = None,
    overhead_other_inr: Optional[float] = None,
) -> ProductionCostRecord:
    """
    Module-level entry point.

    runtime_records should be sourced from the production_plan table,
    specifically the runtime_hrs output from Session 4's generate_daily_plan().
    """
    engine = CostEngine(company_id=company_id)
    return engine.compute_production_cost(
        period=period,
        runtime_records=runtime_records,
        benchmarks=benchmarks,
        overhead_electrode_inr=overhead_electrode_inr,
        overhead_labour_inr=overhead_labour_inr,
        overhead_other_inr=overhead_other_inr,
    )
