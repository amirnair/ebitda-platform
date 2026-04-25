"""
ebitda_engine.py — AC Industries EBITDA Intelligence Platform
Session 5: EBITDA Engine — Main Orchestrator

Connects all three EBITDA cycles and produces the complete EBITDA calculation:

    EBITDA = Revenue − Raw Material Cost − Production Cost − Overheads

Cycle wiring:
    Revenue        ← revenue_engine.py   ← sales_transactions table (SIF)
    Production Cost← cost_engine.py      ← production_plan.runtime_hrs (Session 4)
    Raw Material   ← raw_material_engine ← # Phase 3 stub (returns zero)
    Overheads      ← client-entered      ← benchmarks / settings

Public entry point:
    compute_ebitda(company_id, period, ...) → EbitdaResult
    compute_monthly_rollup(company_id, periods, ...) → MonthlyEbitdaRollup
    simulate_ebitda(company_id, base_period, inputs, ...) → SimulatorResult
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from ebitda_models import (
    EbitdaResult,
    MillRuntimeRecord,
    MonthlyEbitdaRollup,
    OverheadRecord,
    RawMaterialRecord,
    SimulatorInputs,
    SimulatorResult,
    SkuMarginRecord,
)
from revenue_engine import RevenueEngine, SifTransaction
from cost_engine import BenchmarkDefaults, CostEngine
from raw_material_engine import RawMaterialEngine

logger = logging.getLogger(__name__)


class EbitdaEngine:
    """
    Orchestrates all three EBITDA cycles into a single EbitdaResult per period.

    Designed to be stateless per call — no caching. The API layer (ebitda_routes.py)
    handles caching and DB persistence of results.

    Usage:
        engine = EbitdaEngine(company_id="AC001")
        result = engine.compute_ebitda(
            period="2025-04",
            transactions=sif_transactions,      # from sales_transactions table
            runtime_records=mill_runtime_list,  # from production_plan table (Session 4)
            overheads=overhead_record,          # client-entered
            benchmarks=client_benchmarks,       # from benchmark_config table
        )
    """

    def __init__(self, company_id: str):
        self.company_id = company_id
        self._revenue_engine = RevenueEngine(company_id)
        self._cost_engine = CostEngine(company_id)
        self._rm_engine = RawMaterialEngine(company_id)

    # ------------------------------------------------------------------
    # Primary: compute EBITDA for a single period
    # ------------------------------------------------------------------

    def compute_ebitda(
        self,
        period: str,
        transactions: List[SifTransaction],
        runtime_records: List[MillRuntimeRecord],
        overheads: Optional[OverheadRecord] = None,
        benchmarks: Optional[BenchmarkDefaults] = None,
        overhead_electrode_inr: Optional[float] = None,
        overhead_labour_inr: Optional[float] = None,
        overhead_other_inr: Optional[float] = None,
    ) -> EbitdaResult:
        """
        Compute EBITDA for a company × period.

        Args:
            period: "YYYY-MM"
            transactions: SIF transactions from sales_transactions table.
                          Only rows matching period are used; others filtered out.
            runtime_records: MillRuntimeRecord list from production_plan table.
                             These drive power_cost and fuel_cost via runtime_hrs.
                             Sourced from Session 4's generate_daily_plan() output.
            overheads: Fixed overhead record for the period (admin, selling, depreciation).
                       If None, overheads = 0.
            benchmarks: Client benchmark config. Falls back to industry defaults.
            overhead_electrode_inr: Monthly electrode cost if client tracks actuals.
            overhead_labour_inr: Monthly labour cost if client tracks actuals.
            overhead_other_inr: Monthly other fixed costs if client tracks actuals.

        Returns:
            EbitdaResult — complete EBITDA breakdown with SKU margins.
        """
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # 1. Revenue (Phase 1)
        # ------------------------------------------------------------------
        p1_rev, p2_rev = self._revenue_engine.compute_revenue(period, transactions)

        total_revenue = p1_rev.total_value_inr + p2_rev.total_value_inr
        total_qty = p1_rev.total_quantity_tons + p2_rev.total_quantity_tons

        if total_revenue == 0:
            warnings.append(f"No revenue data found for period {period}")

        blended_realisation = total_revenue / total_qty if total_qty > 0 else 0.0

        # ------------------------------------------------------------------
        # 2. Raw Material Cost (Phase 3 — stub returns zero)
        # ------------------------------------------------------------------
        rm_record: RawMaterialRecord = self._rm_engine.compute(period=period)
        # rm_record.is_phase3_stub == True; all cost fields are 0.0

        # ------------------------------------------------------------------
        # 3. Production Cost (Phase 2 — runtime-driven)
        # ------------------------------------------------------------------
        cost_record = self._cost_engine.compute_production_cost(
            period=period,
            runtime_records=runtime_records,
            benchmarks=benchmarks,
            overhead_electrode_inr=overhead_electrode_inr,
            overhead_labour_inr=overhead_labour_inr,
            overhead_other_inr=overhead_other_inr,
        )

        if cost_record.total_runtime_hrs == 0:
            warnings.append(
                f"No production runtime data found for period {period}. "
                f"Production cost calculated as zero."
            )

        # ------------------------------------------------------------------
        # 4. Overheads
        # ------------------------------------------------------------------
        if overheads is None:
            overheads = OverheadRecord(
                company_id=self.company_id,
                period=period,
            )
        overhead_total = overheads.total_overhead_inr

        # ------------------------------------------------------------------
        # 5. EBITDA Calculation
        # EBITDA = Revenue − RM Cost − Production Cost − Overheads
        # Note: RM Cost = 0 until Phase 3
        # ------------------------------------------------------------------
        ebitda_inr = (
            total_revenue
            - rm_record.total_raw_material_cost_inr
            - cost_record.total_production_cost_inr
            - overhead_total
        )

        ebitda_margin_pct = (ebitda_inr / total_revenue * 100) if total_revenue > 0 else 0.0
        ebitda_per_ton = ebitda_inr / total_qty if total_qty > 0 else 0.0

        production_cost_per_ton = cost_record.cost_per_ton_inr
        rm_cost_per_ton = rm_record.raw_material_cost_per_ton_inr  # 0.0 in Phase 3

        # ------------------------------------------------------------------
        # 6. SKU Margin Calculation
        # Allocate production cost to each SKU pro-rata by runtime_hrs share
        # ------------------------------------------------------------------
        sku_cost_allocation = self._cost_engine.sku_cost_allocation(
            cost_record=cost_record,
            runtime_records=runtime_records,
            period=period,
        )

        sku_realisation_records = self._revenue_engine.compute_sku_realisation(
            period, transactions
        )

        sku_runtime_map = self._build_sku_runtime_map(runtime_records, period)
        total_runtime = cost_record.total_runtime_hrs

        sku_margins: List[SkuMarginRecord] = []
        for sku_rec in sku_realisation_records:
            allocated_prod_cost = sku_cost_allocation.get(sku_rec.sku_code, 0.0)
            allocated_rm_cost = 0.0  # Phase 3 stub

            total_cost_allocated = allocated_prod_cost + allocated_rm_cost
            contribution = sku_rec.value_inr - total_cost_allocated
            contribution_per_ton = (
                contribution / sku_rec.quantity_tons if sku_rec.quantity_tons > 0 else 0.0
            )
            contribution_margin_pct = (
                contribution / sku_rec.value_inr * 100 if sku_rec.value_inr > 0 else 0.0
            )

            sku_runtime_hrs = sku_runtime_map.get(sku_rec.sku_code, 0.0)
            runtime_share_pct = (
                sku_runtime_hrs / total_runtime * 100 if total_runtime > 0 else 0.0
            )

            sku_margins.append(SkuMarginRecord(
                company_id=self.company_id,
                period=period,
                brand=sku_rec.brand,
                sku_code=sku_rec.sku_code,
                size_mm=sku_rec.size_mm,
                quantity_tons=sku_rec.quantity_tons,
                revenue_inr=sku_rec.value_inr,
                realisation_per_ton=sku_rec.realisation_per_ton,
                production_cost_allocated_inr=allocated_prod_cost,
                raw_material_cost_allocated_inr=allocated_rm_cost,
                total_cost_allocated_inr=round(total_cost_allocated, 2),
                contribution_inr=round(contribution, 2),
                contribution_per_ton=round(contribution_per_ton, 2),
                contribution_margin_pct=round(contribution_margin_pct, 2),
                runtime_hrs=sku_runtime_hrs,
                runtime_share_pct=round(runtime_share_pct, 2),
            ))

        # ------------------------------------------------------------------
        # 7. Data completeness check
        # ------------------------------------------------------------------
        data_completeness_pct = self._estimate_data_completeness(
            period=period,
            transactions=transactions,
            runtime_records=runtime_records,
        )
        if data_completeness_pct < 100.0:
            warnings.append(
                f"Data completeness: {data_completeness_pct:.1f}% — "
                f"some days in period may be missing."
            )

        return EbitdaResult(
            company_id=self.company_id,
            period=period,
            total_revenue_inr=round(total_revenue, 2),
            total_quantity_tons=round(total_qty, 4),
            blended_realisation_per_ton=round(blended_realisation, 2),
            raw_material_cost_inr=round(rm_record.total_raw_material_cost_inr, 2),
            raw_material_cost_per_ton=round(rm_cost_per_ton, 2),
            is_rm_stub=rm_record.is_phase3_stub,
            production_cost_inr=round(cost_record.total_production_cost_inr, 2),
            production_cost_per_ton=round(production_cost_per_ton, 2),
            total_runtime_hrs=round(cost_record.total_runtime_hrs, 2),
            total_production_mt=round(cost_record.total_production_mt, 4),
            overhead_inr=round(overhead_total, 2),
            ebitda_inr=round(ebitda_inr, 2),
            ebitda_margin_pct=round(ebitda_margin_pct, 2),
            ebitda_per_ton=round(ebitda_per_ton, 2),
            p1_revenue_inr=round(p1_rev.total_value_inr, 2),
            p2_revenue_inr=round(p2_rev.total_value_inr, 2),
            p1_quantity_tons=round(p1_rev.total_quantity_tons, 4),
            p2_quantity_tons=round(p2_rev.total_quantity_tons, 4),
            sku_margins=sku_margins,
            data_completeness_pct=round(data_completeness_pct, 1),
            has_warnings=len(warnings) > 0,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Monthly Rollup — Trend Series
    # ------------------------------------------------------------------

    def compute_monthly_rollup(
        self,
        periods: List[str],
        transactions: List[SifTransaction],
        runtime_records: List[MillRuntimeRecord],
        overheads_by_period: Optional[Dict[str, OverheadRecord]] = None,
        benchmarks: Optional[BenchmarkDefaults] = None,
    ) -> MonthlyEbitdaRollup:
        """
        Compute EBITDA for multiple periods and assemble a trend rollup.

        Args:
            periods: List of "YYYY-MM" strings in chronological order.
            transactions: Full transaction history (engine filters per period).
            runtime_records: Full runtime history (engine filters per period).
            overheads_by_period: Dict mapping period → OverheadRecord.
            benchmarks: Shared client benchmark config across all periods.

        Returns:
            MonthlyEbitdaRollup with trend direction and pre-computed summary metrics.
        """
        results: List[EbitdaResult] = []
        for period in periods:
            overhead = (overheads_by_period or {}).get(period)
            result = self.compute_ebitda(
                period=period,
                transactions=transactions,
                runtime_records=runtime_records,
                overheads=overhead,
                benchmarks=benchmarks,
            )
            results.append(result)

        if not results:
            return MonthlyEbitdaRollup(
                company_id=self.company_id,
                periods=periods,
                results=[],
                latest_ebitda_inr=0.0,
                latest_ebitda_margin_pct=0.0,
                avg_ebitda_margin_pct=0.0,
                best_period="",
                worst_period="",
                trend_direction="stable",
            )

        latest = results[-1]
        margins = [r.ebitda_margin_pct for r in results]
        avg_margin = sum(margins) / len(margins)

        best = max(results, key=lambda r: r.ebitda_margin_pct)
        worst = min(results, key=lambda r: r.ebitda_margin_pct)

        trend_direction = self._compute_trend(margins)

        return MonthlyEbitdaRollup(
            company_id=self.company_id,
            periods=periods,
            results=results,
            latest_ebitda_inr=latest.ebitda_inr,
            latest_ebitda_margin_pct=latest.ebitda_margin_pct,
            avg_ebitda_margin_pct=round(avg_margin, 2),
            best_period=best.period,
            worst_period=worst.period,
            trend_direction=trend_direction,
        )

    # ------------------------------------------------------------------
    # EBITDA Simulator — Screen 8
    # ------------------------------------------------------------------

    def simulate_ebitda(
        self,
        base_result: EbitdaResult,
        inputs: SimulatorInputs,
    ) -> SimulatorResult:
        """
        Apply what-if delta sliders to a base EbitdaResult and return comparison.

        Simulation logic:
            - realisation_delta_pct → scales revenue proportionally
            - volume_delta_pct → scales both revenue and production cost
            - power_rate_delta_pct → scales power_cost component only
            - scrap_price_delta_pct → Phase 3 stub (no effect until Phase 3)
            - yield_delta_pct → Phase 3 stub (no effect until Phase 3)
        """
        volume_factor = 1 + inputs.volume_delta_pct / 100
        realisation_factor = 1 + inputs.realisation_delta_pct / 100
        power_rate_factor = 1 + inputs.power_rate_delta_pct / 100

        # Simulated revenue
        sim_revenue = base_result.total_revenue_inr * volume_factor * realisation_factor

        # Simulated production cost
        # Variable cost scales with volume (more output = more runtime).
        # Fixed cost stays flat (electrode, labour, overheads don't scale linearly).
        # Power rate delta applies only to the power component of variable cost.
        base_variable = (
            base_result.production_cost_inr
            * (base_result.total_runtime_hrs / max(base_result.total_runtime_hrs, 1))
        )
        # Approximate variable share: power + fuel vs total production cost
        # Use cost record structure: variable ≈ total − fixed
        # We don't have the split on EbitdaResult directly, so approximate from
        # benchmark ratios. For the simulator, this is a fast approximation.
        estimated_variable_share = 0.55  # ~55% variable for TMT mills (power + fuel)
        estimated_fixed_share = 0.45

        base_var_cost = base_result.production_cost_inr * estimated_variable_share
        base_fixed_cost = base_result.production_cost_inr * estimated_fixed_share

        # Variable cost: scales with volume, power rate applies
        sim_var_cost = base_var_cost * volume_factor * power_rate_factor
        sim_fixed_cost = base_fixed_cost  # Fixed doesn't scale

        sim_production_cost = sim_var_cost + sim_fixed_cost

        # Raw material — Phase 3 stub: no change
        sim_rm_cost = base_result.raw_material_cost_inr  # 0.0 until Phase 3

        # Overheads unchanged by simulation sliders
        sim_overheads = base_result.overhead_inr

        # Simulated EBITDA
        sim_ebitda = sim_revenue - sim_rm_cost - sim_production_cost - sim_overheads
        sim_margin = (sim_ebitda / sim_revenue * 100) if sim_revenue > 0 else 0.0

        return SimulatorResult(
            base_period=base_result.period,
            inputs=inputs,
            base_revenue_inr=base_result.total_revenue_inr,
            simulated_revenue_inr=round(sim_revenue, 2),
            revenue_delta_inr=round(sim_revenue - base_result.total_revenue_inr, 2),
            base_production_cost_inr=base_result.production_cost_inr,
            simulated_production_cost_inr=round(sim_production_cost, 2),
            production_cost_delta_inr=round(
                sim_production_cost - base_result.production_cost_inr, 2
            ),
            base_raw_material_cost_inr=base_result.raw_material_cost_inr,
            simulated_raw_material_cost_inr=round(sim_rm_cost, 2),
            base_ebitda_inr=base_result.ebitda_inr,
            simulated_ebitda_inr=round(sim_ebitda, 2),
            ebitda_delta_inr=round(sim_ebitda - base_result.ebitda_inr, 2),
            base_ebitda_margin_pct=base_result.ebitda_margin_pct,
            simulated_ebitda_margin_pct=round(sim_margin, 2),
            margin_delta_pct=round(sim_margin - base_result.ebitda_margin_pct, 2),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sku_runtime_map(
        runtime_records: List[MillRuntimeRecord],
        period: str,
    ) -> Dict[str, float]:
        """Aggregate runtime_hrs per sku_code for a period."""
        runtime_map: Dict[str, float] = {}
        for r in runtime_records:
            if r.date.strftime("%Y-%m") == period:
                runtime_map[r.sku_code] = runtime_map.get(r.sku_code, 0.0) + r.runtime_hrs
        return runtime_map

    @staticmethod
    def _estimate_data_completeness(
        period: str,
        transactions: List[SifTransaction],
        runtime_records: List[MillRuntimeRecord],
    ) -> float:
        """
        Estimate how complete the data is for the period.
        Based on the number of distinct days with data vs expected working days.
        Returns 0–100.
        """
        import calendar
        from datetime import date as dt_date

        year, month = int(period[:4]), int(period[5:7])
        _, days_in_month = calendar.monthrange(year, month)

        # Sundays are zero-sales days — exclude from expected count
        expected_days = sum(
            1 for day in range(1, days_in_month + 1)
            if dt_date(year, month, day).weekday() != 6  # 6 = Sunday
        )

        txn_days = {t.date for t in transactions if t.date.strftime("%Y-%m") == period}
        runtime_days = {
            r.date for r in runtime_records if r.date.strftime("%Y-%m") == period
        }

        # Use the union of both data sources
        days_with_data = len(txn_days | runtime_days)

        if expected_days == 0:
            return 100.0

        return min(days_with_data / expected_days * 100, 100.0)

    @staticmethod
    def _compute_trend(margins: List[float]) -> str:
        """
        Simple linear trend over last N periods.
        Returns "improving" | "declining" | "stable".
        """
        if len(margins) < 3:
            return "stable"

        # Compare average of last third vs first third
        n = len(margins)
        third = max(1, n // 3)
        early_avg = sum(margins[:third]) / third
        late_avg = sum(margins[-third:]) / third

        delta = late_avg - early_avg
        if delta > 1.0:
            return "improving"
        elif delta < -1.0:
            return "declining"
        else:
            return "stable"


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def compute_ebitda(
    company_id: str,
    period: str,
    transactions: List[SifTransaction],
    runtime_records: List[MillRuntimeRecord],
    overheads: Optional[OverheadRecord] = None,
    benchmarks: Optional[BenchmarkDefaults] = None,
    **kwargs,
) -> EbitdaResult:
    """Module-level entry point for single-period EBITDA calculation."""
    engine = EbitdaEngine(company_id=company_id)
    return engine.compute_ebitda(
        period=period,
        transactions=transactions,
        runtime_records=runtime_records,
        overheads=overheads,
        benchmarks=benchmarks,
        **kwargs,
    )


def compute_monthly_rollup(
    company_id: str,
    periods: List[str],
    transactions: List[SifTransaction],
    runtime_records: List[MillRuntimeRecord],
    overheads_by_period: Optional[Dict[str, OverheadRecord]] = None,
    benchmarks: Optional[BenchmarkDefaults] = None,
) -> MonthlyEbitdaRollup:
    """Module-level entry point for multi-period rollup."""
    engine = EbitdaEngine(company_id=company_id)
    return engine.compute_monthly_rollup(
        periods=periods,
        transactions=transactions,
        runtime_records=runtime_records,
        overheads_by_period=overheads_by_period,
        benchmarks=benchmarks,
    )
