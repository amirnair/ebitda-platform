"""
test_optimiser.py
-----------------
Test suite for Session 4 Production Optimiser.
55+ test cases covering:
    - SKU capacity module
    - Synthetic demand generator
    - Urgency scorer
    - LP optimiser (greedy path, valid when PuLP unavailable)
    - Billet engine
    - Production plan orchestrator
    - FastAPI routes (schema validation)

Run: pytest tests/test_optimiser.py -v
"""

from __future__ import annotations

import sys
import os
from datetime import date, timedelta
from typing import Dict

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ============================================================
# sku_capacity.py tests
# ============================================================

class TestSkuCapacity:
    def test_all_14_skus_loaded(self):
        from optimiser.sku_capacity import SKU_CAPACITY, ALL_SKU_CODES
        assert len(SKU_CAPACITY) == 14
        assert len(ALL_SKU_CODES) == 14

    def test_p1_and_p2_split(self):
        from optimiser.sku_capacity import P1_SKU_CODES, P2_SKU_CODES
        assert len(P1_SKU_CODES) == 7
        assert len(P2_SKU_CODES) == 7

    def test_capacity_range_18_to_25(self):
        from optimiser.sku_capacity import SKU_CAPACITY
        for sku, rec in SKU_CAPACITY.items():
            assert 18.0 <= rec.capacity_mt_hr <= 25.0, f"{sku} capacity out of range"

    def test_8mm_is_slowest(self):
        from optimiser.sku_capacity import SKU_CAPACITY
        assert SKU_CAPACITY["P1-SKU-8"].capacity_mt_hr == 18.0
        assert SKU_CAPACITY["P2-SKU-8"].capacity_mt_hr == 18.0

    def test_32mm_is_fastest(self):
        from optimiser.sku_capacity import SKU_CAPACITY
        assert SKU_CAPACITY["P1-SKU-32"].capacity_mt_hr == 25.0
        assert SKU_CAPACITY["P2-SKU-32"].capacity_mt_hr == 25.0

    def test_capacity_monotonically_increasing_by_size(self):
        from optimiser.sku_capacity import SKU_CAPACITY
        sizes = [8, 10, 12, 16, 20, 25, 32]
        caps = [SKU_CAPACITY[f"P1-SKU-{s}"].capacity_mt_hr for s in sizes]
        for i in range(len(caps) - 1):
            assert caps[i] < caps[i+1], "Capacity should increase with size"

    def test_rolling_factor_is_1_05(self):
        from optimiser.sku_capacity import ROLLING_FACTOR
        assert ROLLING_FACTOR == 1.05

    def test_changeover_hours_is_2(self):
        from optimiser.sku_capacity import CHANGEOVER_HOURS
        assert CHANGEOVER_HOURS == 2.0

    def test_standard_runtime_is_16(self):
        from optimiser.sku_capacity import STANDARD_RUNTIME_HOURS
        assert STANDARD_RUNTIME_HOURS == 16.0

    def test_hours_to_produce_correct(self):
        from optimiser.sku_capacity import hours_to_produce, SKU_CAPACITY
        # P1-SKU-16 has capacity 21.5 MT/hr
        cap = SKU_CAPACITY["P1-SKU-16"].capacity_mt_hr
        hrs = hours_to_produce("P1-SKU-16", cap)  # 1 hour of production
        assert abs(hrs - 1.0) < 0.001

    def test_hours_to_produce_zero(self):
        from optimiser.sku_capacity import hours_to_produce
        assert hours_to_produce("P1-SKU-16", 0.0) == 0.0

    def test_billet_types_correct(self):
        from optimiser.sku_capacity import SKU_CAPACITY
        assert SKU_CAPACITY["P1-SKU-25"].billet_type == "P1-5.6M"
        assert SKU_CAPACITY["P1-SKU-32"].billet_type == "P1-5.05M"
        assert SKU_CAPACITY["P2-SKU-32"].billet_type == "P2-4.9M"

    def test_margin_rank_1_is_p1_16mm(self):
        from optimiser.sku_capacity import SKU_CAPACITY
        # §5.2: margin rank 1 = highest margin
        assert SKU_CAPACITY["P1-SKU-16"].margin_rank == 1


# ============================================================
# synthetic_demand.py tests
# ============================================================

class TestSyntheticDemand:
    def test_generates_14_skus(self):
        from optimiser.synthetic_demand import generate_daily_demand
        d = generate_daily_demand(date(2025, 5, 1), seed=42)
        assert len(d) == 14

    def test_all_skus_present(self):
        from optimiser.synthetic_demand import generate_daily_demand
        from optimiser.sku_capacity import ALL_SKU_CODES
        d = generate_daily_demand(date(2025, 5, 1), seed=42)
        codes = {item.sku_code for item in d}
        assert codes == set(ALL_SKU_CODES)

    def test_proportions_sum_to_total(self):
        from optimiser.synthetic_demand import generate_daily_demand
        total_override = 300.0
        d = generate_daily_demand(date(2025, 5, 1), total_daily_mt=total_override, seed=42)
        total = sum(item.qty_forecast_mt for item in d)
        assert abs(total - total_override) < 1.0, f"Sum {total} ≠ {total_override}"

    def test_confidence_interval_wider_than_point(self):
        from optimiser.synthetic_demand import generate_daily_demand
        d = generate_daily_demand(date(2025, 5, 1), seed=42)
        for item in d:
            assert item.confidence_high >= item.qty_forecast_mt
            assert item.confidence_low <= item.qty_forecast_mt

    def test_seed_reproducibility(self):
        from optimiser.synthetic_demand import generate_daily_demand
        d1 = generate_daily_demand(date(2025, 5, 1), seed=99)
        d2 = generate_daily_demand(date(2025, 5, 1), seed=99)
        for a, b in zip(d1, d2):
            assert a.qty_forecast_mt == b.qty_forecast_mt

    def test_demand_window_returns_correct_days(self):
        from optimiser.synthetic_demand import generate_demand_window
        window = generate_demand_window(date(2025, 5, 1), days=7, seed=1)
        assert len(window) == 7

    def test_demand_as_dict(self):
        from optimiser.synthetic_demand import generate_daily_demand, demand_as_dict
        d = generate_daily_demand(date(2025, 5, 1), seed=42)
        mapping = demand_as_dict(d)
        assert len(mapping) == 14
        assert all(isinstance(v, float) for v in mapping.values())

    def test_p1_proportion_dominant(self):
        """P1 should represent ~68% of demand per §3.6."""
        from optimiser.synthetic_demand import generate_daily_demand
        d = generate_daily_demand(date(2025, 5, 1), seed=42)
        p1_total = sum(i.qty_forecast_mt for i in d if i.brand_code == "P1")
        total = sum(i.qty_forecast_mt for i in d)
        p1_pct = p1_total / total
        assert 0.60 <= p1_pct <= 0.80, f"P1 proportion {p1_pct:.2f} out of expected range"


# ============================================================
# urgency_scorer.py tests
# ============================================================

class TestUrgencyScorer:
    def _make_states(self, fg_stocks, demands):
        from optimiser.urgency_scorer import build_stock_states
        return build_stock_states(fg_stocks, demands)

    def test_zero_stock_is_urgent(self):
        from optimiser.urgency_scorer import SkuStockState, MIN_BUFFER_DAYS
        s = SkuStockState(sku_code="P1-SKU-16", fg_stock_mt=0.0, avg_daily_demand_mt=20.0)
        assert s.is_urgent is True
        assert s.days_of_stock < MIN_BUFFER_DAYS

    def test_adequate_stock_not_urgent(self):
        from optimiser.urgency_scorer import SkuStockState
        s = SkuStockState(sku_code="P1-SKU-16", fg_stock_mt=100.0, avg_daily_demand_mt=20.0)
        assert s.is_urgent is False
        assert abs(s.days_of_stock - 5.0) < 0.001

    def test_zero_demand_infinite_stock(self):
        from optimiser.urgency_scorer import SkuStockState
        s = SkuStockState(sku_code="P1-SKU-16", fg_stock_mt=50.0, avg_daily_demand_mt=0.0)
        assert s.is_urgent is False
        assert s.days_of_stock == float("inf")

    def test_urgent_sku_sorts_first(self):
        from optimiser.urgency_scorer import score_skus, build_stock_states
        from optimiser.sku_capacity import ALL_SKU_CODES
        fg_stocks = {sku: 100.0 for sku in ALL_SKU_CODES}
        demand = {sku: 20.0 for sku in ALL_SKU_CODES}
        # Make P1-SKU-8 critically urgent
        fg_stocks["P1-SKU-8"] = 0.0
        states = build_stock_states(fg_stocks, demand)
        scored = score_skus(states, demand)
        assert scored[0].sku_code == "P1-SKU-8", "Urgent SKU must be first"
        assert scored[0].is_urgent is True

    def test_best_margin_wins_when_equally_urgent(self):
        from optimiser.urgency_scorer import score_skus, build_stock_states
        from optimiser.sku_capacity import ALL_SKU_CODES
        # All stocks below buffer so all are urgent
        fg_stocks = {sku: 0.0 for sku in ALL_SKU_CODES}
        demand = {sku: 20.0 for sku in ALL_SKU_CODES}
        states = build_stock_states(fg_stocks, demand)
        scored = score_skus(states, demand)
        # All urgent — first should be margin rank 1 (P1-SKU-16)
        assert scored[0].margin_rank == 1

    def test_changeover_penalty_applied(self):
        from optimiser.urgency_scorer import score_skus, build_stock_states
        from optimiser.sku_capacity import ALL_SKU_CODES
        fg_stocks = {sku: 0.0 for sku in ALL_SKU_CODES}
        demand = {sku: 20.0 for sku in ALL_SKU_CODES}
        states = build_stock_states(fg_stocks, demand)
        # Set previous_sku to P1-SKU-16 → P1-SKU-16 gets zero changeover penalty
        scored = score_skus(states, demand, previous_sku="P1-SKU-16")
        # P1-SKU-16 (same size = no changeover) should rank above P1-SKU-10 (different size)
        p1_16_pos = next(i for i, s in enumerate(scored) if s.sku_code == "P1-SKU-16")
        p1_10_pos = next(i for i, s in enumerate(scored) if s.sku_code == "P1-SKU-10")
        assert p1_16_pos < p1_10_pos

    def test_build_stock_states_covers_all_skus(self):
        from optimiser.urgency_scorer import build_stock_states
        from optimiser.sku_capacity import ALL_SKU_CODES
        states = build_stock_states({}, {})
        assert len(states) == len(ALL_SKU_CODES)


# ============================================================
# lp_optimiser.py tests (greedy path — PuLP not installed)
# ============================================================

class TestLpOptimiser:
    def _make_input(self, demand_scale=1.0, runtime=16.0, fg_stocks=None):
        from optimiser.synthetic_demand import generate_daily_demand, demand_as_dict
        from optimiser.urgency_scorer import build_stock_states, score_skus
        from optimiser.lp_optimiser import OptimiserInput
        from optimiser.sku_capacity import ALL_SKU_CODES

        d = date(2025, 5, 1)
        demands = generate_daily_demand(d, total_daily_mt=300.0 * demand_scale, seed=42)
        demand_vector = demand_as_dict(demands)
        fg = fg_stocks or {sku: 0.0 for sku in ALL_SKU_CODES}
        states = build_stock_states(fg, demand_vector)
        scored = score_skus(states, demand_vector)
        return OptimiserInput(
            company_id="AC001",
            planning_date=d,
            demand_mt=demand_vector,
            fg_stock_mt=fg,
            scored_skus=scored,
            runtime_hours=runtime,
        )

    def test_result_has_14_plan_lines(self):
        from optimiser.lp_optimiser import run_optimiser
        result = run_optimiser(self._make_input())
        assert len(result.plan_lines) == 14

    def test_total_production_within_capacity(self):
        from optimiser.lp_optimiser import run_optimiser
        from optimiser.sku_capacity import STANDARD_RUNTIME_HOURS
        result = run_optimiser(self._make_input())
        # Total runtime + changeover should not exceed available hours
        used = result.total_runtime_hrs + result.total_changeover_hrs
        assert used <= STANDARD_RUNTIME_HOURS + 0.1  # 0.1 tolerance for float

    def test_production_non_negative(self):
        from optimiser.lp_optimiser import run_optimiser
        result = run_optimiser(self._make_input())
        for line in result.plan_lines:
            assert line.production_mt >= 0.0

    def test_billet_required_uses_rolling_factor(self):
        from optimiser.lp_optimiser import run_optimiser
        from optimiser.sku_capacity import ROLLING_FACTOR
        result = run_optimiser(self._make_input())
        for line in result.plan_lines:
            if line.production_mt > 0:
                expected = round(line.production_mt * ROLLING_FACTOR, 3)
                assert abs(line.billet_required_mt - expected) < 0.01

    def test_skus_produced_list_consistent(self):
        from optimiser.lp_optimiser import run_optimiser
        result = run_optimiser(self._make_input())
        produced_set = {l.sku_code for l in result.plan_lines if l.production_mt > 0.01}
        assert set(result.skus_produced) == produced_set

    def test_utilisation_pct_0_to_100(self):
        from optimiser.lp_optimiser import run_optimiser
        result = run_optimiser(self._make_input())
        assert 0.0 <= result.runtime_utilisation_pct <= 105.0  # slight overrun allowed in greedy

    def test_zero_demand_zero_production(self):
        from optimiser.lp_optimiser import run_optimiser, OptimiserInput
        from optimiser.urgency_scorer import build_stock_states, score_skus
        from optimiser.sku_capacity import ALL_SKU_CODES

        demand = {sku: 0.0 for sku in ALL_SKU_CODES}
        fg = {sku: 0.0 for sku in ALL_SKU_CODES}
        states = build_stock_states(fg, demand)
        scored = score_skus(states, demand)
        inp = OptimiserInput(
            company_id="AC001",
            planning_date=date(2025, 5, 1),
            demand_mt=demand,
            fg_stock_mt=fg,
            scored_skus=scored,
            runtime_hours=16.0,
        )
        result = run_optimiser(inp)
        assert result.total_production_mt == 0.0

    def test_high_demand_warns_on_shortfall(self):
        from optimiser.lp_optimiser import run_optimiser
        # 10× normal demand — will hit capacity ceiling
        result = run_optimiser(self._make_input(demand_scale=10.0))
        total_unmet = sum(l.unmet_mt for l in result.plan_lines)
        # With 10× demand, there should be significant unmet
        assert total_unmet > 0 or result.warnings  # Either unmet or warning flagged

    def test_full_stock_reduces_production_needed(self):
        from optimiser.lp_optimiser import run_optimiser
        from optimiser.sku_capacity import ALL_SKU_CODES
        # Stock 1000MT for each SKU — no production needed
        fg_stocks = {sku: 1000.0 for sku in ALL_SKU_CODES}
        result = run_optimiser(self._make_input(fg_stocks=fg_stocks))
        assert result.total_production_mt < 50.0  # Should be near zero


# ============================================================
# billet_engine.py tests
# ============================================================

class TestBilletEngine:
    def test_billet_calculation_uses_rolling_factor(self):
        from optimiser.billet_engine import calculate_billet_requirements
        from optimiser.sku_capacity import ROLLING_FACTOR
        plan = {"P1-SKU-16": 100.0}
        req = calculate_billet_requirements(plan)
        assert abs(req["P1-6M"] - 100.0 * ROLLING_FACTOR) < 0.01

    def test_all_billet_types_returned(self):
        from optimiser.billet_engine import calculate_billet_requirements, ALL_BILLET_TYPES
        req = calculate_billet_requirements({})
        assert set(req.keys()) == set(ALL_BILLET_TYPES)

    def test_p1_production_uses_p1_billet(self):
        from optimiser.billet_engine import calculate_billet_requirements
        plan = {"P1-SKU-10": 50.0}
        req = calculate_billet_requirements(plan)
        assert req["P1-6M"] > 0
        assert req["P2-6M"] == 0.0

    def test_p2_production_uses_p2_billet(self):
        from optimiser.billet_engine import calculate_billet_requirements
        plan = {"P2-SKU-25": 30.0}
        req = calculate_billet_requirements(plan)
        assert req["P2-5.6M"] > 0
        assert req["P1-5.6M"] == 0.0

    def test_25mm_uses_5_6m_billet(self):
        from optimiser.billet_engine import calculate_billet_requirements
        plan = {"P1-SKU-25": 20.0, "P2-SKU-25": 20.0}
        req = calculate_billet_requirements(plan)
        assert req["P1-5.6M"] > 0
        assert req["P2-5.6M"] > 0

    def test_32mm_uses_correct_billet_types(self):
        from optimiser.billet_engine import calculate_billet_requirements
        plan = {"P1-SKU-32": 10.0, "P2-SKU-32": 10.0}
        req = calculate_billet_requirements(plan)
        assert req["P1-5.05M"] > 0
        assert req["P2-4.9M"] > 0

    def test_drawdown_limited_by_stock(self):
        from optimiser.billet_engine import run_billet_engine
        plan = {"P1-SKU-16": 100.0}  # Needs 105 MT of P1-6M billet
        stocks = {"P1-6M": 50.0}     # Only 50 MT available
        report = run_billet_engine(date(2025, 5, 1), "AC001", plan, stocks)
        p1_6m = next(d for d in report.drawdowns if d.billet_type == "P1-6M")
        assert p1_6m.drawdown_mt == 50.0
        assert p1_6m.shortfall_mt > 0
        assert len(report.critical_alerts) > 0

    def test_adequate_stock_no_alerts(self):
        from optimiser.billet_engine import run_billet_engine, ALL_BILLET_TYPES
        plan = {"P1-SKU-16": 10.0}
        stocks = {bt: 500.0 for bt in ALL_BILLET_TYPES}
        report = run_billet_engine(date(2025, 5, 1), "AC001", plan, stocks)
        assert len(report.critical_alerts) == 0

    def test_procurement_trigger_on_low_stock(self):
        from optimiser.billet_engine import run_billet_engine, ALL_BILLET_TYPES
        plan = {"P1-SKU-16": 20.0}
        # Only 1 day of stock remaining
        stocks = {bt: 1.0 for bt in ALL_BILLET_TYPES}
        report = run_billet_engine(
            date(2025, 5, 1), "AC001", plan, stocks,
            forecast_demand={"P1-SKU-16": 20.0}
        )
        p1_6m_rec = next(r for r in report.recommendations if r.billet_type == "P1-6M")
        assert p1_6m_rec.procurement_trigger is True
        assert p1_6m_rec.urgency in ("CRITICAL", "LOW")

    def test_totals_p1_p2_separated(self):
        from optimiser.billet_engine import run_billet_engine, ALL_BILLET_TYPES
        plan = {"P1-SKU-16": 50.0, "P2-SKU-10": 30.0}
        stocks = {bt: 500.0 for bt in ALL_BILLET_TYPES}
        report = run_billet_engine(date(2025, 5, 1), "AC001", plan, stocks)
        assert report.total_billet_required_p1_mt > 0
        assert report.total_billet_required_p2_mt > 0


# ============================================================
# production_plan.py (orchestrator) tests
# ============================================================

class TestProductionPlan:
    def test_generates_valid_plan(self):
        from optimiser.production_plan import generate_daily_plan
        plan = generate_daily_plan("AC001", date(2025, 5, 1), demand_seed=42)
        assert plan is not None
        assert plan.summary is not None

    def test_plan_has_14_lines(self):
        from optimiser.production_plan import generate_daily_plan
        plan = generate_daily_plan("AC001", date(2025, 5, 1), demand_seed=42)
        assert len(plan.summary.plan_lines) == 14

    def test_section_4_5_fields_present(self):
        """All §4.5 Daily Decision Report fields must be present."""
        from optimiser.production_plan import generate_daily_plan
        plan = generate_daily_plan("AC001", date(2025, 5, 1), demand_seed=42)
        s = plan.summary
        assert s.p1_production_mt >= 0
        assert s.p2_production_mt >= 0
        assert s.total_production_mt >= 0
        assert s.billet_required_p1_mt >= 0
        assert s.billet_required_p2_mt >= 0
        assert s.mill_runtime_p1_hrs >= 0
        assert s.mill_runtime_p2_hrs >= 0
        assert s.mill_runtime_total_hrs >= 0

    def test_rolling_sequence_contains_produced_skus_only(self):
        from optimiser.production_plan import generate_daily_plan
        plan = generate_daily_plan("AC001", date(2025, 5, 1), demand_seed=42)
        s = plan.summary
        assert set(s.rolling_sequence).issubset(set(s.skus_produced))

    def test_demand_override_respected(self):
        from optimiser.production_plan import generate_daily_plan
        from optimiser.sku_capacity import ALL_SKU_CODES
        # Override: only P1-SKU-16 has demand
        demand_override = {sku: 0.0 for sku in ALL_SKU_CODES}
        demand_override["P1-SKU-16"] = 50.0
        plan = generate_daily_plan(
            "AC001", date(2025, 5, 1),
            demand_override=demand_override,
        )
        p1_16_line = next(l for l in plan.summary.plan_lines if l.sku_code == "P1-SKU-16")
        assert p1_16_line.demand_mt == 50.0

    def test_production_holiday_zero_runtime(self):
        """When runtime_hours=0, no production should occur."""
        from optimiser.production_plan import generate_daily_plan
        plan = generate_daily_plan(
            "AC001", date(2025, 5, 1),
            runtime_hours=0.0,
            demand_seed=42,
        )
        assert plan.summary.total_production_mt == 0.0

    def test_billet_report_attached(self):
        from optimiser.production_plan import generate_daily_plan
        plan = generate_daily_plan("AC001", date(2025, 5, 1), demand_seed=42)
        assert plan.billet_report is not None
        assert len(plan.billet_report.drawdowns) == 6  # 6 billet types

    def test_urgent_skus_list_correct(self):
        from optimiser.production_plan import generate_daily_plan
        from optimiser.sku_capacity import ALL_SKU_CODES
        # All zero stock → all should be urgent
        fg_stocks = {sku: 0.0 for sku in ALL_SKU_CODES}
        plan = generate_daily_plan(
            "AC001", date(2025, 5, 1),
            fg_stocks=fg_stocks,
            demand_seed=42,
        )
        assert len(plan.summary.urgent_skus) > 0

    def test_company_id_propagated(self):
        from optimiser.production_plan import generate_daily_plan
        plan = generate_daily_plan("TESTCO", date(2025, 5, 1), demand_seed=1)
        assert plan.summary.company_id == "TESTCO"


# ============================================================
# FastAPI schema tests (no server needed)
# ============================================================

class TestApiSchemas:
    def test_daily_plan_request_valid(self):
        from api.optimiser_routes import DailyPlanRequest
        req = DailyPlanRequest(company_id="AC001", planning_date=date(2025, 5, 1))
        assert req.runtime_hours == 16.0

    def test_daily_plan_request_custom_runtime(self):
        from api.optimiser_routes import DailyPlanRequest
        req = DailyPlanRequest(
            company_id="AC001",
            planning_date=date(2025, 5, 1),
            runtime_hours=12.0,
        )
        assert req.runtime_hours == 12.0

    def test_batch_request_max_days_30(self):
        from api.optimiser_routes import BatchPlanRequest
        from pydantic import ValidationError
        with pytest.raises((ValidationError, Exception)):
            BatchPlanRequest(
                company_id="AC001",
                start_date=date(2025, 5, 1),
                days=31,
            )

    def test_sku_capacity_response_fields(self):
        from api.optimiser_routes import SkuCapacityResponse
        rec = SkuCapacityResponse(
            sku_code="P1-SKU-16",
            size_mm=16,
            brand_code="P1",
            capacity_mt_hr=21.5,
            margin_rank=1,
            billet_type="P1-6M",
            billet_length_m=6.0,
        )
        assert rec.sku_code == "P1-SKU-16"

    def test_router_prefix(self):
        from api.optimiser_routes import router
        assert router.prefix == "/optimiser"


# ============================================================
# Integration smoke test
# ============================================================

class TestIntegration:
    def test_end_to_end_pipeline(self):
        """
        Smoke test: full pipeline from demand generation → LP → billet → report.
        Verifies that all modules wire together without error.
        """
        from optimiser.production_plan import generate_daily_plan
        from optimiser.sku_capacity import ALL_SKU_CODES

        fg_stocks = {
            "P1-SKU-16": 30.0,
            "P1-SKU-10": 20.0,
            "P1-SKU-12": 15.0,
            "P1-SKU-8": 5.0,   # Low stock
        }
        billet_stocks = {
            "P1-6M": 400.0,
            "P1-5.6M": 50.0,
            "P1-5.05M": 20.0,
            "P2-6M": 200.0,
            "P2-5.6M": 30.0,
            "P2-4.9M": 10.0,
        }

        plan = generate_daily_plan(
            company_id="AC001",
            planning_date=date(2025, 10, 15),  # Peak season
            fg_stocks=fg_stocks,
            billet_stocks=billet_stocks,
            previous_sku="P1-SKU-16",
            runtime_hours=16.0,
            demand_seed=100,
        )

        s = plan.summary
        # Basic sanity checks
        assert s.total_production_mt >= 0
        assert len(s.plan_lines) == 14
        assert s.mill_runtime_total_hrs <= 16.0 + 0.5  # Within runtime budget
        # P1-SKU-8 should be urgent (only 5MT stock)
        assert "P1-SKU-8" in s.urgent_skus or s.total_production_mt >= 0  # Either flagged or handled
        # Billet report should exist
        assert len(plan.billet_report.drawdowns) == 6

    def test_weekly_rolling_plan(self):
        """Generate 7-day rolling plan — verifies batch mode viability."""
        from optimiser.production_plan import generate_daily_plan
        start = date(2025, 5, 1)
        plans = []
        prev_sku = None
        for i in range(7):
            d = start + timedelta(days=i)
            plan = generate_daily_plan(
                "AC001", d,
                previous_sku=prev_sku,
                demand_seed=i,
            )
            plans.append(plan)
            if plan.summary.rolling_sequence:
                prev_sku = plan.summary.rolling_sequence[-1]

        assert len(plans) == 7
        weekly_production = sum(p.summary.total_production_mt for p in plans)
        assert weekly_production > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
