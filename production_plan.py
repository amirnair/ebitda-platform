"""
production_plan.py
------------------
Orchestrator: ties together demand → urgency scoring → LP → billet engine
→ §4.5 Daily Decision Report.

Public entry point:
    generate_daily_plan(company_id, planning_date, ...) → DailyProductionPlan

This module is the equivalent of run_ingestion() in Session 1 and
run_aggregation() in Session 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from optimiser.sku_capacity import (
    ALL_SKU_CODES,
    CHANGEOVER_HOURS,
    STANDARD_RUNTIME_HOURS,
    SKU_CAPACITY,
)
from optimiser.synthetic_demand import (
    DailySkuDemand,
    generate_daily_demand,
    demand_as_dict,
)
from optimiser.urgency_scorer import (
    ScoredSku,
    SkuStockState,
    build_stock_states,
    score_skus,
)
from optimiser.lp_optimiser import (
    OptimiserInput,
    OptimiserResult,
    SkuPlanLine,
    run_optimiser,
)
from optimiser.billet_engine import (
    BilletProcurementReport,
    run_billet_engine,
)


# ---------------------------------------------------------------------------
# §4.5 Daily Decision Report — output dataclass
# ---------------------------------------------------------------------------

@dataclass
class DailyPlanSummary:
    """
    §4.5 Daily Decision Report fields — one row per SKU (for non-zero production)
    plus aggregate totals.
    """
    # Header
    company_id: str
    planning_date: date
    solver_status: str
    solver_used: str

    # Per-SKU lines (§4.5 "SKU to Roll")
    plan_lines: List[SkuPlanLine]

    # Aggregates (§4.5 output fields)
    p1_production_mt: float
    p2_production_mt: float
    total_production_mt: float

    billet_required_p1_mt: float
    billet_required_p2_mt: float

    mill_runtime_p1_hrs: float
    mill_runtime_p2_hrs: float
    mill_runtime_total_hrs: float

    num_sku_switches: int
    total_changeover_hrs: float
    runtime_utilisation_pct: float

    # Urgency flags
    urgent_skus: List[str]
    skus_produced: List[str]

    # Rolling sequence (ordered by urgency scorer)
    rolling_sequence: List[str]    # SKU codes in mill order

    # Billet procurement
    billet_report: BilletProcurementReport

    # Warnings / alerts
    warnings: List[str] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings) or self.billet_report.has_critical_alerts

    def alert_summary(self) -> List[str]:
        return self.warnings + self.billet_report.critical_alerts


@dataclass
class DailyProductionPlan:
    """Full output package — summary + raw sub-outputs for API layer."""
    summary: DailyPlanSummary
    demand_inputs: List[DailySkuDemand]
    scored_skus: List[ScoredSku]
    lp_result: OptimiserResult
    billet_report: BilletProcurementReport


# ---------------------------------------------------------------------------
# Rolling sequence builder
# ---------------------------------------------------------------------------

def _build_rolling_sequence(
    scored_skus: List[ScoredSku],
    production_plan: Dict[str, float],
) -> List[str]:
    """
    Build the ordered sequence of SKUs to roll on the mill today.
    Only includes SKUs with production > 0, in urgency-scored order.
    """
    return [
        s.sku_code
        for s in scored_skus
        if production_plan.get(s.sku_code, 0.0) > 0.01
    ]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_daily_plan(
    company_id: str,
    planning_date: date,
    fg_stocks: Optional[Dict[str, float]] = None,
    billet_stocks: Optional[Dict[str, float]] = None,
    previous_sku: Optional[str] = None,
    runtime_hours: float = STANDARD_RUNTIME_HOURS,
    demand_override: Optional[Dict[str, float]] = None,
    demand_seed: Optional[int] = None,
) -> DailyProductionPlan:
    """
    Generate the Daily Decision Report (§4.5) for a given company + date.

    Args:
        company_id:       Multi-tenant company identifier.
        planning_date:    Date to plan for.
        fg_stocks:        Current finished goods stock: sku_code → MT.
                          Defaults to zero stock (pessimistic / conservative).
        billet_stocks:    Current billet stock: billet_type → MT.
                          Defaults to 5-day supply (adequate for planning).
        previous_sku:     Last SKU rolled (for changeover calculation).
        runtime_hours:    Available mill hours today (§1.5 default: 16hrs).
        demand_override:  Inject a real demand vector (from Session 3 forecasts).
                          If None, synthetic demand is generated.
        demand_seed:      Seed for synthetic demand RNG (tests only).

    Returns:
        DailyProductionPlan with full §4.5 output.
    """

    # ------------------------------------------------------------------
    # Step 1: Demand vector
    # ------------------------------------------------------------------
    if demand_override:
        demand_vector = demand_override
        demand_inputs = _make_demand_inputs(demand_vector, planning_date, company_id)
    else:
        demand_inputs = generate_daily_demand(
            forecast_date=planning_date,
            company_id=company_id,
            seed=demand_seed,
        )
        demand_vector = demand_as_dict(demand_inputs)

    # ------------------------------------------------------------------
    # Step 2: FG stock defaults
    # ------------------------------------------------------------------
    if fg_stocks is None:
        fg_stocks = {sku: 0.0 for sku in ALL_SKU_CODES}

    # ------------------------------------------------------------------
    # Step 3: Billet stock defaults (5 days of supply)
    # ------------------------------------------------------------------
    if billet_stocks is None:
        from optimiser.billet_engine import ALL_BILLET_TYPES, calculate_billet_requirements
        daily_billet_req = calculate_billet_requirements(demand_vector)
        billet_stocks = {bt: round(qty * 5.0, 2) for bt, qty in daily_billet_req.items()}

    # ------------------------------------------------------------------
    # Step 4: Urgency scoring
    # ------------------------------------------------------------------
    stock_states = build_stock_states(fg_stocks, demand_vector)
    scored_skus = score_skus(stock_states, demand_vector, previous_sku)
    urgent_skus = [s.sku_code for s in scored_skus if s.is_urgent]

    # ------------------------------------------------------------------
    # Step 5: LP optimisation
    # ------------------------------------------------------------------
    lp_input = OptimiserInput(
        company_id=company_id,
        planning_date=planning_date,
        demand_mt=demand_vector,
        fg_stock_mt=fg_stocks,
        scored_skus=scored_skus,
        runtime_hours=runtime_hours,
        previous_sku=previous_sku,
    )
    lp_result = run_optimiser(lp_input)

    # ------------------------------------------------------------------
    # Step 6: Billet procurement
    # ------------------------------------------------------------------
    production_plan = {line.sku_code: line.production_mt for line in lp_result.plan_lines}
    billet_report = run_billet_engine(
        planning_date=planning_date,
        company_id=company_id,
        production_plan=production_plan,
        billet_stocks=billet_stocks,
        forecast_demand=demand_vector,
    )

    # ------------------------------------------------------------------
    # Step 7: Assemble §4.5 Daily Decision Report
    # ------------------------------------------------------------------
    rolling_sequence = _build_rolling_sequence(scored_skus, production_plan)

    mill_runtime_p1 = sum(
        l.runtime_hrs for l in lp_result.plan_lines if l.brand_code == "P1"
    )
    mill_runtime_p2 = sum(
        l.runtime_hrs for l in lp_result.plan_lines if l.brand_code == "P2"
    )

    summary = DailyPlanSummary(
        company_id=company_id,
        planning_date=planning_date,
        solver_status=lp_result.status,
        solver_used=lp_result.solver_used,
        plan_lines=lp_result.plan_lines,
        p1_production_mt=lp_result.p1_production_mt,
        p2_production_mt=lp_result.p2_production_mt,
        total_production_mt=lp_result.total_production_mt,
        billet_required_p1_mt=billet_report.total_billet_required_p1_mt,
        billet_required_p2_mt=billet_report.total_billet_required_p2_mt,
        mill_runtime_p1_hrs=round(mill_runtime_p1, 2),
        mill_runtime_p2_hrs=round(mill_runtime_p2, 2),
        mill_runtime_total_hrs=lp_result.total_runtime_hrs,
        num_sku_switches=lp_result.num_sku_switches,
        total_changeover_hrs=lp_result.total_changeover_hrs,
        runtime_utilisation_pct=lp_result.runtime_utilisation_pct,
        urgent_skus=urgent_skus,
        skus_produced=lp_result.skus_produced,
        rolling_sequence=rolling_sequence,
        billet_report=billet_report,
        warnings=lp_result.warnings,
    )

    return DailyProductionPlan(
        summary=summary,
        demand_inputs=demand_inputs,
        scored_skus=scored_skus,
        lp_result=lp_result,
        billet_report=billet_report,
    )


def _make_demand_inputs(
    demand_dict: Dict[str, float],
    planning_date: date,
    company_id: str,
) -> List[DailySkuDemand]:
    """Convert a raw demand dict into DailySkuDemand list (for the real forecasts path)."""
    result = []
    for sku_code, qty in demand_dict.items():
        rec = SKU_CAPACITY.get(sku_code)
        if rec:
            result.append(DailySkuDemand(
                company_id=company_id,
                forecast_date=planning_date,
                sku_code=sku_code,
                brand_code=rec.brand_code,
                size_mm=rec.size_mm,
                qty_forecast_mt=qty,
                confidence_low=qty * 0.92,
                confidence_high=qty * 1.08,
                model_name="real_forecast",
            ))
    return result
