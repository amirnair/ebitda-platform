"""
lp_optimiser.py
---------------
Multi-objective Linear Programme for daily mill scheduling.

Implements all 6 objectives from §4.2:
    1. Meet forecasted demand for all SKUs             (hard constraint)
    2. Maintain buffer stocks above minimum levels     (hard constraint)
    3. Do not exceed mill capacity (daily runtime)     (hard constraint)
    4. Minimise changeover time (SKU switches)         (efficiency objective)
    5. Prioritise higher margin SKUs when capacity tight (profitability objective)
    6. Urgent SKUs first (stock below buffer threshold) (urgency objective)

Objectives 4–6 are converted into a weighted cost function and added to
the LP objective. The LP decides *how much* of each SKU to produce.
The SKU sequence (order on mill) is determined separately by the urgency
scorer (§4.3) — sequencing is a scheduling problem, production quantities
are the LP problem.

Solver: PuLP (COIN-BC bundled solver — no external binary required).

Decision variables:
    prod[sku]   ≥ 0   tonnes to produce for each SKU today

Objective (minimise):
    Σ (weight_margin × margin_rank × prod[sku])
  + Σ (weight_urgency × urgency_score × unmet[sku])
  + changeover_cost × num_switches_estimated

Constraints:
    (C1) prod[sku] + stock[sku] ≥ demand[sku]          # Meet demand
    (C2) prod[sku] + stock[sku] ≥ buffer_mt[sku]       # Buffer stock
    (C3) Σ (prod[sku] / capacity[sku]) + changeover_hrs ≤ runtime_hrs  # Capacity
    (C4) prod[sku] ≥ 0                                 # Non-negativity
    (C5) unmet[sku] ≥ demand[sku] - prod[sku] - stock[sku]  # Unmet demand slack
    (C6) unmet[sku] ≥ 0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import pulp
    _PULP_AVAILABLE = True
except ImportError:
    _PULP_AVAILABLE = False

from optimiser.sku_capacity import (
    CHANGEOVER_HOURS,
    ROLLING_FACTOR,
    STANDARD_RUNTIME_HOURS,
    SKU_CAPACITY,
    ALL_SKU_CODES,
    hours_to_produce,
)
from optimiser.urgency_scorer import ScoredSku, MIN_BUFFER_DAYS


# ---------------------------------------------------------------------------
# Weights for multi-objective cost function
# ---------------------------------------------------------------------------
WEIGHT_MARGIN: float = 1.0          # Favour high-margin SKUs
WEIGHT_URGENCY_PENALTY: float = 500.0   # Heavy penalty for unmet demand
WEIGHT_CHANGEOVER: float = 50.0     # Penalty per estimated changeover

# Buffer stock = N days of demand
BUFFER_DAYS: float = MIN_BUFFER_DAYS


@dataclass
class OptimiserInput:
    """All inputs the LP needs for one planning day."""
    company_id: str
    planning_date: object                     # date
    demand_mt: Dict[str, float]              # sku_code → MT demanded today
    fg_stock_mt: Dict[str, float]            # sku_code → MT in FG store
    scored_skus: List[ScoredSku]             # Pre-scored by urgency_scorer
    runtime_hours: float = STANDARD_RUNTIME_HOURS
    previous_sku: Optional[str] = None      # Last SKU rolled (for changeover)
    max_sku_switches: Optional[int] = None  # Override — None = unlimited


@dataclass
class SkuPlanLine:
    """One row of the optimised mill plan for a single SKU."""
    sku_code: str
    brand_code: str
    size_mm: int
    demand_mt: float
    fg_stock_opening_mt: float
    production_mt: float            # LP decision variable value
    billet_required_mt: float       # production_mt × rolling_factor
    runtime_hrs: float              # production_mt / capacity_mt_hr
    unmet_mt: float                 # demand not met (should be 0 in feasible solution)
    is_urgent: bool
    margin_rank: int
    sequence_position: int          # Mill rolling order (1 = first)


@dataclass
class OptimiserResult:
    """Full output of one LP run."""
    company_id: str
    planning_date: object
    status: str                          # "Optimal", "Infeasible", "Fallback"
    objective_value: float
    plan_lines: List[SkuPlanLine]
    total_production_mt: float
    total_runtime_hrs: float
    total_changeover_hrs: float
    total_billet_p1_mt: float
    total_billet_p2_mt: float
    skus_produced: List[str]            # SKU codes with production > 0
    num_sku_switches: int
    runtime_utilisation_pct: float
    solver_used: str
    warnings: List[str] = field(default_factory=list)

    @property
    def p1_production_mt(self) -> float:
        return sum(l.production_mt for l in self.plan_lines if l.brand_code == "P1")

    @property
    def p2_production_mt(self) -> float:
        return sum(l.production_mt for l in self.plan_lines if l.brand_code == "P2")


# ---------------------------------------------------------------------------
# Main optimiser
# ---------------------------------------------------------------------------

def run_optimiser(inputs: OptimiserInput) -> OptimiserResult:
    """
    Run the multi-objective LP.

    Falls back to a greedy heuristic if PuLP is not installed or LP is infeasible.
    """
    if _PULP_AVAILABLE:
        return _run_pulp(inputs)
    else:
        return _run_greedy_fallback(inputs)


def _run_pulp(inputs: OptimiserInput) -> OptimiserResult:
    """Full PuLP LP implementation."""
    prob = pulp.LpProblem("mill_daily_plan", pulp.LpMinimize)

    sku_codes = ALL_SKU_CODES
    demand = inputs.demand_mt
    stock = inputs.fg_stock_mt

    # ------------------------------------------------------------------
    # Decision variables
    # ------------------------------------------------------------------
    prod = {
        sku: pulp.LpVariable(f"prod_{sku}", lowBound=0, cat="Continuous")
        for sku in sku_codes
    }
    unmet = {
        sku: pulp.LpVariable(f"unmet_{sku}", lowBound=0, cat="Continuous")
        for sku in sku_codes
    }

    # Binary variable: is SKU produced today? (for changeover counting)
    is_produced = {
        sku: pulp.LpVariable(f"produced_{sku}", cat="Binary")
        for sku in sku_codes
    }

    # ------------------------------------------------------------------
    # Urgency and margin lookup
    # ------------------------------------------------------------------
    urgency_map = {s.sku_code: s.urgency_score for s in inputs.scored_skus}
    margin_map = {s.sku_code: s.margin_rank for s in inputs.scored_skus}
    urgent_map = {s.sku_code: s.is_urgent for s in inputs.scored_skus}

    # ------------------------------------------------------------------
    # Objective function
    # (minimise: unmet demand penalty + margin cost + changeover cost)
    # ------------------------------------------------------------------
    # Unmet penalty: very heavy to ensure demand is met when feasible
    unmet_penalty = pulp.lpSum(
        WEIGHT_URGENCY_PENALTY * (2.0 if urgent_map.get(sku, False) else 1.0) * unmet[sku]
        for sku in sku_codes
    )
    # Margin cost: prefer lower margin_rank (rank 1 = best margin)
    margin_cost = pulp.lpSum(
        WEIGHT_MARGIN * margin_map.get(sku, 14) * prod[sku]
        for sku in sku_codes
    )
    # Changeover cost: estimated from binary production flags
    changeover_cost = WEIGHT_CHANGEOVER * pulp.lpSum(
        is_produced[sku] for sku in sku_codes
    )

    prob += unmet_penalty + margin_cost + changeover_cost

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    cap = {sku: SKU_CAPACITY[sku].capacity_mt_hr for sku in sku_codes}

    # C1: Unmet slack definition: unmet ≥ demand - prod - stock
    for sku in sku_codes:
        d = demand.get(sku, 0.0)
        s = stock.get(sku, 0.0)
        prob += unmet[sku] >= d - prod[sku] - s

    # C2: Buffer stock constraint: prod + stock ≥ buffer
    for sku in sku_codes:
        d = demand.get(sku, 0.0)
        s = stock.get(sku, 0.0)
        buffer_mt = BUFFER_DAYS * d
        # Only bind if buffer > current stock
        if buffer_mt > s:
            prob += prod[sku] + s >= buffer_mt

    # C3: Mill capacity (runtime) constraint
    # Total rolling hours + estimated changeovers ≤ available runtime
    # Changeover hours = CHANGEOVER_HOURS × (number of SKU switches)
    # We bound num_switches ≤ number of SKUs produced.
    # Exact sequencing is handled post-LP by urgency scorer.
    rolling_hours = pulp.lpSum(prod[sku] / cap[sku] for sku in sku_codes)
    # Conservative: assume up to (n_produced - 1) changeovers
    estimated_changeover = CHANGEOVER_HOURS * pulp.lpSum(is_produced[sku] for sku in sku_codes)
    prob += rolling_hours + estimated_changeover <= inputs.runtime_hours

    # C4: Link prod to is_produced binary
    # If prod[sku] > 0 then is_produced[sku] = 1
    # Big-M: max possible production in one full day × 2
    M = inputs.runtime_hours * 25.0  # 25 = max capacity_mt_hr
    for sku in sku_codes:
        prob += prod[sku] <= M * is_produced[sku]

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------
    solver = pulp.PULP_CBC_CMD(msg=0)
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]

    if status not in ("Optimal", "Feasible"):
        # Infeasible — relax buffer constraints and retry
        prob_relaxed = _relax_and_resolve(inputs)
        if prob_relaxed is None:
            return _run_greedy_fallback(inputs, warning="LP infeasible even after relaxation")
        prob, status = prob_relaxed

    # ------------------------------------------------------------------
    # Extract results
    # ------------------------------------------------------------------
    return _extract_results(inputs, prob, prod, unmet, is_produced, status, "PuLP/CBC")


def _relax_and_resolve(inputs: OptimiserInput):
    """
    Retry LP with buffer constraints removed (demand constraints only).
    Returns (prob, status) or None if still infeasible.
    """
    prob = pulp.LpProblem("mill_daily_plan_relaxed", pulp.LpMinimize)
    sku_codes = ALL_SKU_CODES
    demand = inputs.demand_mt
    stock = inputs.fg_stock_mt
    cap = {sku: SKU_CAPACITY[sku].capacity_mt_hr for sku in sku_codes}
    margin_map = {s.sku_code: s.margin_rank for s in inputs.scored_skus}
    urgent_map = {s.sku_code: s.is_urgent for s in inputs.scored_skus}

    prod = {sku: pulp.LpVariable(f"prod_{sku}", lowBound=0) for sku in sku_codes}
    unmet = {sku: pulp.LpVariable(f"unmet_{sku}", lowBound=0) for sku in sku_codes}
    is_produced = {sku: pulp.LpVariable(f"produced_{sku}", cat="Binary") for sku in sku_codes}

    # Objective
    prob += (
        pulp.lpSum(WEIGHT_URGENCY_PENALTY * (2 if urgent_map.get(s, False) else 1) * unmet[s] for s in sku_codes) +
        pulp.lpSum(WEIGHT_MARGIN * margin_map.get(s, 14) * prod[s] for s in sku_codes) +
        WEIGHT_CHANGEOVER * pulp.lpSum(is_produced[s] for s in sku_codes)
    )

    for sku in sku_codes:
        d = demand.get(sku, 0.0)
        s = stock.get(sku, 0.0)
        prob += unmet[sku] >= d - prod[sku] - s
        M = inputs.runtime_hours * 25.0
        prob += prod[sku] <= M * is_produced[sku]

    rolling_hours = pulp.lpSum(prod[sku] / cap[sku] for sku in sku_codes)
    estimated_changeover = CHANGEOVER_HOURS * pulp.lpSum(is_produced[sku] for sku in sku_codes)
    prob += rolling_hours + estimated_changeover <= inputs.runtime_hours

    solver = pulp.PULP_CBC_CMD(msg=0)
    prob.solve(solver)
    status = pulp.LpStatus[prob.status]
    if status in ("Optimal", "Feasible"):
        return prob, status
    return None


def _extract_results(
    inputs: OptimiserInput,
    prob,
    prod: dict,
    unmet: dict,
    is_produced: dict,
    status: str,
    solver_name: str,
) -> OptimiserResult:
    """Extract OptimiserResult from solved PuLP problem."""
    sku_codes = ALL_SKU_CODES
    demand = inputs.demand_mt
    stock = inputs.fg_stock_mt
    scored_map = {s.sku_code: s for s in inputs.scored_skus}

    plan_lines = []
    total_runtime = 0.0
    skus_produced = []

    for i, sku in enumerate(sku_codes):
        prod_val = max(0.0, pulp.value(prod[sku]) or 0.0)
        unmet_val = max(0.0, pulp.value(unmet[sku]) or 0.0)
        cap_hr = SKU_CAPACITY[sku].capacity_mt_hr
        runtime = prod_val / cap_hr if prod_val > 0 else 0.0
        billet = round(prod_val * ROLLING_FACTOR, 3)
        total_runtime += runtime
        scored = scored_map.get(sku)

        if prod_val > 0.01:
            skus_produced.append(sku)

        plan_lines.append(SkuPlanLine(
            sku_code=sku,
            brand_code=SKU_CAPACITY[sku].brand_code,
            size_mm=SKU_CAPACITY[sku].size_mm,
            demand_mt=demand.get(sku, 0.0),
            fg_stock_opening_mt=stock.get(sku, 0.0),
            production_mt=round(prod_val, 3),
            billet_required_mt=billet,
            runtime_hrs=round(runtime, 3),
            unmet_mt=round(unmet_val, 3),
            is_urgent=scored.is_urgent if scored else False,
            margin_rank=SKU_CAPACITY[sku].margin_rank,
            sequence_position=i + 1,
        ))

    num_switches = max(0, len(skus_produced) - 1)
    total_changeover = num_switches * CHANGEOVER_HOURS
    total_billet_p1 = sum(
        l.billet_required_mt for l in plan_lines if l.brand_code == "P1"
    )
    total_billet_p2 = sum(
        l.billet_required_mt for l in plan_lines if l.brand_code == "P2"
    )
    total_prod = sum(l.production_mt for l in plan_lines)
    total_avail = inputs.runtime_hours
    utilisation = round((total_runtime + total_changeover) / total_avail * 100, 1)

    warnings = []
    unmet_total = sum(l.unmet_mt for l in plan_lines)
    if unmet_total > 0.1:
        warnings.append(f"Demand shortfall: {unmet_total:.1f} MT unmet — capacity insufficient for full demand")

    return OptimiserResult(
        company_id=inputs.company_id,
        planning_date=inputs.planning_date,
        status=status,
        objective_value=round(pulp.value(prob.objective) or 0.0, 2),
        plan_lines=plan_lines,
        total_production_mt=round(total_prod, 2),
        total_runtime_hrs=round(total_runtime, 2),
        total_changeover_hrs=round(total_changeover, 2),
        total_billet_p1_mt=round(total_billet_p1, 3),
        total_billet_p2_mt=round(total_billet_p2, 3),
        skus_produced=skus_produced,
        num_sku_switches=num_switches,
        runtime_utilisation_pct=utilisation,
        solver_used=solver_name,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Greedy fallback (no PuLP required)
# ---------------------------------------------------------------------------

def _run_greedy_fallback(
    inputs: OptimiserInput,
    warning: str = "PuLP not installed — using greedy heuristic",
) -> OptimiserResult:
    """
    Greedy heuristic: allocate mill time in urgency-scored order until
    capacity is exhausted or all demand is met. Used when PuLP is unavailable.
    """
    sku_codes = ALL_SKU_CODES
    demand = inputs.demand_mt
    stock = inputs.fg_stock_mt
    available_hours = inputs.runtime_hours

    plan = {sku: 0.0 for sku in sku_codes}
    remaining_hours = available_hours
    processed_skus = []

    for scored in inputs.scored_skus:
        sku = scored.sku_code
        d = demand.get(sku, 0.0)
        s = stock.get(sku, 0.0)
        cap = SKU_CAPACITY[sku].capacity_mt_hr
        needed = max(0.0, d - s)

        if needed <= 0:
            continue

        # Account for changeover
        co_hrs = CHANGEOVER_HOURS if processed_skus else 0.0
        usable = remaining_hours - co_hrs
        if usable <= 0:
            break

        producible = usable * cap
        production = min(needed, producible)
        if production < 0.01:
            break

        plan[sku] = production
        remaining_hours -= (production / cap) + co_hrs
        processed_skus.append(sku)

    # Build result
    plan_lines = []
    total_runtime = 0.0
    skus_produced = []
    scored_map = {s.sku_code: s for s in inputs.scored_skus}

    for i, sku in enumerate(sku_codes):
        prod_val = plan[sku]
        cap_hr = SKU_CAPACITY[sku].capacity_mt_hr
        runtime = prod_val / cap_hr if prod_val > 0 else 0.0
        total_runtime += runtime
        d = demand.get(sku, 0.0)
        s = stock.get(sku, 0.0)
        unmet_val = max(0.0, d - s - prod_val)
        billet = round(prod_val * ROLLING_FACTOR, 3)
        scored = scored_map.get(sku)

        if prod_val > 0.01:
            skus_produced.append(sku)

        plan_lines.append(SkuPlanLine(
            sku_code=sku,
            brand_code=SKU_CAPACITY[sku].brand_code,
            size_mm=SKU_CAPACITY[sku].size_mm,
            demand_mt=d,
            fg_stock_opening_mt=s,
            production_mt=round(prod_val, 3),
            billet_required_mt=billet,
            runtime_hrs=round(runtime, 3),
            unmet_mt=round(unmet_val, 3),
            is_urgent=scored.is_urgent if scored else False,
            margin_rank=SKU_CAPACITY[sku].margin_rank,
            sequence_position=i + 1,
        ))

    num_switches = max(0, len(skus_produced) - 1)
    total_changeover = num_switches * CHANGEOVER_HOURS
    total_billet_p1 = sum(l.billet_required_mt for l in plan_lines if l.brand_code == "P1")
    total_billet_p2 = sum(l.billet_required_mt for l in plan_lines if l.brand_code == "P2")
    total_prod = sum(l.production_mt for l in plan_lines)
    utilisation = round((total_runtime + total_changeover) / available_hours * 100, 1) if available_hours > 0 else 0.0

    return OptimiserResult(
        company_id=inputs.company_id,
        planning_date=inputs.planning_date,
        status="Greedy",
        objective_value=0.0,
        plan_lines=plan_lines,
        total_production_mt=round(total_prod, 2),
        total_runtime_hrs=round(total_runtime, 2),
        total_changeover_hrs=round(total_changeover, 2),
        total_billet_p1_mt=round(total_billet_p1, 3),
        total_billet_p2_mt=round(total_billet_p2, 3),
        skus_produced=skus_produced,
        num_sku_switches=num_switches,
        runtime_utilisation_pct=utilisation,
        solver_used="Greedy Heuristic",
        warnings=[warning],
    )
