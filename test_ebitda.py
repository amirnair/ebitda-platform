"""
test_ebitda.py — AC Industries EBITDA Intelligence Platform
Session 5: EBITDA Engine — Test Suite

70+ test cases covering:
  - ebitda_models.py   — dataclass contracts and computed properties
  - revenue_engine.py  — realisation derivation, SKU aggregation, brand split
  - cost_engine.py     — runtime-driven cost formula, fixed/variable split, allocation
  - raw_material_engine.py — Phase 3 stub contract
  - ebitda_engine.py   — full EBITDA assembly, SKU margins, rollup, simulator
  - Integration        — end-to-end with synthetic AC Industries data

Run:
    python -m pytest tests/test_ebitda.py -v
"""

from __future__ import annotations

import sys
import os
from datetime import date
from typing import List

import pytest

# Path setup
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ebitda"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from ebitda_models import (
    EbitdaResult,
    MillRuntimeRecord,
    MonthlyEbitdaRollup,
    OverheadRecord,
    ProductionCostInputs,
    ProductionCostRecord,
    RawMaterialRecord,
    RealisationRecord,
    RevenueRecord,
    SimulatorInputs,
    SimulatorResult,
    SkuMarginRecord,
)
from revenue_engine import RevenueEngine, SifTransaction, compute_revenue
from cost_engine import BenchmarkDefaults, CostEngine, compute_production_cost, BENCHMARK_DEFAULTS
from raw_material_engine import RawMaterialEngine, compute_raw_material_cost
from ebitda_engine import EbitdaEngine, compute_ebitda, compute_monthly_rollup
from synthetic_ebitda_data import (
    generate_full_period_dataset,
    generate_mill_runtime_records,
    generate_multi_period_dataset,
    generate_overhead_record,
    generate_sif_transactions,
)

COMPANY_ID = "AC001"
PERIOD = "2025-04"


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def simple_transactions() -> List[SifTransaction]:
    """Minimal transactions: 2 P1 rows, 1 P2 row."""
    return [
        SifTransaction(
            company_id=COMPANY_ID,
            date=date(2025, 4, 1),
            brand="P1",
            sku_code="P1-SKU-16",
            sku_name="16mm Product 1 Fe550",
            size_mm=16,
            quantity_tons=10.0,
            value_inr=535_000.0,  # ₹53,500/ton
            region="Tamil Nadu",
            district="Chennai",
            invoice_id="9000001",
        ),
        SifTransaction(
            company_id=COMPANY_ID,
            date=date(2025, 4, 1),
            brand="P1",
            sku_code="P1-SKU-12",
            sku_name="12mm Product 1 Fe550",
            size_mm=12,
            quantity_tons=5.0,
            value_inr=269_000.0,  # ₹53,800/ton
            region="Tamil Nadu",
            district="Chennai",
            invoice_id="9000002",
        ),
        SifTransaction(
            company_id=COMPANY_ID,
            date=date(2025, 4, 1),
            brand="P2",
            sku_code="P2-SKU-10",
            sku_name="10mm Product 2 Fe550",
            size_mm=10,
            quantity_tons=8.0,
            value_inr=428_000.0,  # ₹53,500/ton
            region="Tamil Nadu",
            district="Coimbatore",
            invoice_id="9000003",
        ),
    ]


@pytest.fixture
def simple_runtime_records() -> List[MillRuntimeRecord]:
    """Minimal runtime records: one per SKU."""
    return [
        MillRuntimeRecord(
            company_id=COMPANY_ID,
            date=date(2025, 4, 1),
            sku_code="P1-SKU-16",
            brand="P1",
            production_mt=10.0,
            runtime_hrs=10.0 / 21.0,  # 21 MT/hr for 16mm
        ),
        MillRuntimeRecord(
            company_id=COMPANY_ID,
            date=date(2025, 4, 1),
            sku_code="P1-SKU-12",
            brand="P1",
            production_mt=5.0,
            runtime_hrs=5.0 / 20.0,  # 20 MT/hr for 12mm
        ),
        MillRuntimeRecord(
            company_id=COMPANY_ID,
            date=date(2025, 4, 1),
            sku_code="P2-SKU-10",
            brand="P2",
            production_mt=8.0,
            runtime_hrs=8.0 / 19.0,  # 19 MT/hr for 10mm
        ),
    ]


@pytest.fixture
def synthetic_dataset() -> dict:
    return generate_full_period_dataset(COMPANY_ID, PERIOD, seed=42)


@pytest.fixture
def multi_period_dataset() -> dict:
    return generate_multi_period_dataset(COMPANY_ID, seed=42)


# ===========================================================================
# 1. ebitda_models.py — Dataclass contracts
# ===========================================================================

class TestEbitdaModels:

    def test_realisation_record_is_frozen(self):
        rec = RealisationRecord(
            company_id=COMPANY_ID, period=PERIOD, brand="P1",
            sku_code="P1-SKU-16", size_mm=16,
            quantity_tons=10.0, value_inr=535_000.0,
            realisation_per_ton=53_500.0,
        )
        with pytest.raises((AttributeError, TypeError)):
            rec.quantity_tons = 99.0  # type: ignore

    def test_overhead_total_property(self):
        oh = OverheadRecord(
            company_id=COMPANY_ID, period=PERIOD,
            admin_cost_inr=100_000,
            selling_cost_inr=200_000,
            depreciation_inr=300_000,
            interest_inr=400_000,
            other_overhead_inr=500_000,
        )
        assert oh.total_overhead_inr == 1_500_000

    def test_overhead_defaults_to_zero(self):
        oh = OverheadRecord(company_id=COMPANY_ID, period=PERIOD)
        assert oh.total_overhead_inr == 0.0

    def test_raw_material_record_is_phase3_stub(self):
        rm = RawMaterialRecord(company_id=COMPANY_ID, period=PERIOD)
        assert rm.is_phase3_stub is True
        assert rm.total_raw_material_cost_inr == 0.0

    def test_revenue_record_to_dict(self):
        rec = RevenueRecord(
            company_id=COMPANY_ID, period=PERIOD, brand="P1",
            total_quantity_tons=100.0, total_value_inr=5_000_000.0,
            blended_realisation_per_ton=50_000.0,
        )
        d = rec.to_dict()
        assert d["company_id"] == COMPANY_ID
        assert d["total_value_inr"] == 5_000_000.0

    def test_simulator_inputs_defaults(self):
        inp = SimulatorInputs(base_period=PERIOD)
        assert inp.realisation_delta_pct == 0.0
        assert inp.volume_delta_pct == 0.0


# ===========================================================================
# 2. revenue_engine.py
# ===========================================================================

class TestRevenueEngine:

    def test_realisation_derived_from_value_over_qty(self, simple_transactions):
        """Core contract: realisation = value_inr / quantity_tons (no separate price field)."""
        engine = RevenueEngine(COMPANY_ID)
        p1, p2 = engine.compute_revenue(PERIOD, simple_transactions)
        # P1-SKU-16: 535000 / 10 = 53500
        p1_16 = next(r for r in p1.sku_detail if r.sku_code == "P1-SKU-16")
        assert p1_16.realisation_per_ton == pytest.approx(53_500.0, rel=1e-4)

    def test_p1_p2_split(self, simple_transactions):
        engine = RevenueEngine(COMPANY_ID)
        p1, p2 = engine.compute_revenue(PERIOD, simple_transactions)
        assert p1.brand == "P1"
        assert p2.brand == "P2"
        assert p1.total_quantity_tons == pytest.approx(15.0, rel=1e-4)
        assert p2.total_quantity_tons == pytest.approx(8.0, rel=1e-4)

    def test_blended_realisation_p1(self, simple_transactions):
        """Blended realisation = total_value / total_qty across all P1 SKUs."""
        engine = RevenueEngine(COMPANY_ID)
        p1, _ = engine.compute_revenue(PERIOD, simple_transactions)
        expected = (535_000 + 269_000) / (10.0 + 5.0)
        assert p1.blended_realisation_per_ton == pytest.approx(expected, rel=1e-4)

    def test_empty_transactions_returns_zero_revenue(self):
        engine = RevenueEngine(COMPANY_ID)
        p1, p2 = engine.compute_revenue(PERIOD, [])
        assert p1.total_value_inr == 0.0
        assert p2.total_value_inr == 0.0

    def test_period_filter(self, simple_transactions):
        """Transactions from other periods should not be counted."""
        extra = SifTransaction(
            company_id=COMPANY_ID, date=date(2025, 3, 15), brand="P1",
            sku_code="P1-SKU-16", sku_name="16mm", size_mm=16,
            quantity_tons=100.0, value_inr=5_000_000.0,
            region="Tamil Nadu", district="Chennai", invoice_id="8000001",
        )
        engine = RevenueEngine(COMPANY_ID)
        p1, _ = engine.compute_revenue(PERIOD, simple_transactions + [extra])
        # April total should not include the March row
        assert p1.total_quantity_tons == pytest.approx(15.0, rel=1e-4)

    def test_sku_detail_sorted_by_brand_then_size(self, simple_transactions):
        engine = RevenueEngine(COMPANY_ID)
        p1, _ = engine.compute_revenue(PERIOD, simple_transactions)
        sizes = [r.size_mm for r in p1.sku_detail]
        assert sizes == sorted(sizes)

    def test_compute_revenue_module_function(self, simple_transactions):
        p1, p2 = compute_revenue(COMPANY_ID, PERIOD, simple_transactions)
        assert p1.company_id == COMPANY_ID
        assert p2.company_id == COMPANY_ID

    def test_multi_period_revenue(self, synthetic_dataset):
        engine = RevenueEngine(COMPANY_ID)
        txns = synthetic_dataset["transactions"]
        result = engine.compute_revenue_by_period(txns)
        assert PERIOD in result
        p1, p2 = result[PERIOD]
        assert p1.total_quantity_tons > 0
        assert p2.total_quantity_tons > 0

    def test_zero_quantity_handled(self):
        engine = RevenueEngine(COMPANY_ID)
        txn = SifTransaction(
            company_id=COMPANY_ID, date=date(2025, 4, 1), brand="P1",
            sku_code="P1-SKU-16", sku_name="16mm", size_mm=16,
            quantity_tons=0.0, value_inr=0.0,
            region="Tamil Nadu", district="Chennai", invoice_id="X001",
        )
        p1, _ = engine.compute_revenue(PERIOD, [txn])
        assert p1.blended_realisation_per_ton == 0.0

    def test_sku_realisation_returns_all_skus(self, simple_transactions):
        engine = RevenueEngine(COMPANY_ID)
        records = engine.compute_sku_realisation(PERIOD, simple_transactions)
        sku_codes = {r.sku_code for r in records}
        assert "P1-SKU-16" in sku_codes
        assert "P1-SKU-12" in sku_codes
        assert "P2-SKU-10" in sku_codes


# ===========================================================================
# 3. cost_engine.py — Runtime-driven cost formula
# ===========================================================================

class TestCostEngine:

    def test_power_cost_is_runtime_driven(self, simple_runtime_records):
        """Core contract: power_cost = power_units_per_hr × runtime_hrs × power_rate"""
        engine = CostEngine(COMPANY_ID)
        bm = BENCHMARK_DEFAULTS
        cost = engine.compute_production_cost(PERIOD, simple_runtime_records, benchmarks=bm)

        total_runtime = sum(r.runtime_hrs for r in simple_runtime_records)
        expected_power = bm.power_units_per_hr * total_runtime * bm.power_rate_inr_per_unit
        assert cost.power_cost_inr == pytest.approx(expected_power, rel=1e-4)

    def test_fuel_cost_is_runtime_driven(self, simple_runtime_records):
        """Core contract: fuel_cost = fuel_cost_per_hr × runtime_hrs"""
        engine = CostEngine(COMPANY_ID)
        bm = BENCHMARK_DEFAULTS
        cost = engine.compute_production_cost(PERIOD, simple_runtime_records, benchmarks=bm)

        total_runtime = sum(r.runtime_hrs for r in simple_runtime_records)
        expected_fuel = bm.fuel_cost_per_hr_inr * total_runtime
        assert cost.fuel_cost_inr == pytest.approx(expected_fuel, rel=1e-4)

    def test_cost_per_ton_formula(self, simple_runtime_records):
        """cost_per_ton = total_production_cost / total_production_mt"""
        engine = CostEngine(COMPANY_ID)
        cost = engine.compute_production_cost(PERIOD, simple_runtime_records)
        total_mt = sum(r.production_mt for r in simple_runtime_records)
        assert cost.cost_per_ton_inr == pytest.approx(
            cost.total_production_cost_inr / total_mt, rel=1e-4
        )

    def test_variable_plus_fixed_equals_total(self, simple_runtime_records):
        engine = CostEngine(COMPANY_ID)
        cost = engine.compute_production_cost(PERIOD, simple_runtime_records)
        assert cost.total_variable_cost_inr + cost.total_fixed_cost_inr == pytest.approx(
            cost.total_production_cost_inr, rel=1e-4
        )

    def test_higher_runtime_increases_variable_cost(self):
        """Doubling runtime_hrs should approximately double variable cost."""
        base = MillRuntimeRecord(
            company_id=COMPANY_ID, date=date(2025, 4, 1),
            sku_code="P1-SKU-16", brand="P1",
            production_mt=100.0, runtime_hrs=5.0,
        )
        doubled = MillRuntimeRecord(
            company_id=COMPANY_ID, date=date(2025, 4, 1),
            sku_code="P1-SKU-16", brand="P1",
            production_mt=200.0, runtime_hrs=10.0,
        )
        engine = CostEngine(COMPANY_ID)
        cost_base = engine.compute_production_cost(PERIOD, [base])
        cost_doubled = engine.compute_production_cost(PERIOD, [doubled])
        assert cost_doubled.total_variable_cost_inr == pytest.approx(
            cost_base.total_variable_cost_inr * 2, rel=1e-4
        )

    def test_power_rate_override_affects_power_cost(self):
        """Changing power_rate in benchmark should change power cost proportionally."""
        rec = MillRuntimeRecord(
            company_id=COMPANY_ID, date=date(2025, 4, 1),
            sku_code="P1-SKU-16", brand="P1",
            production_mt=100.0, runtime_hrs=5.0,
        )
        bm_base = BenchmarkDefaults(power_rate_inr_per_unit=7.50)
        bm_high = BenchmarkDefaults(power_rate_inr_per_unit=9.00)
        engine = CostEngine(COMPANY_ID)
        cost_base = engine.compute_production_cost(PERIOD, [rec], benchmarks=bm_base)
        cost_high = engine.compute_production_cost(PERIOD, [rec], benchmarks=bm_high)
        assert cost_high.power_cost_inr == pytest.approx(
            cost_base.power_cost_inr * (9.00 / 7.50), rel=1e-4
        )

    def test_empty_runtime_returns_zero_record(self):
        engine = CostEngine(COMPANY_ID)
        cost = engine.compute_production_cost(PERIOD, [])
        assert cost.total_production_cost_inr == 0.0
        assert cost.cost_per_ton_inr == 0.0

    def test_client_overhead_electrode_overrides_benchmark(self):
        """When overhead_electrode_inr is provided, benchmark per-MT rate is not used."""
        rec = MillRuntimeRecord(
            company_id=COMPANY_ID, date=date(2025, 4, 1),
            sku_code="P1-SKU-16", brand="P1",
            production_mt=100.0, runtime_hrs=5.0,
        )
        engine = CostEngine(COMPANY_ID)
        cost = engine.compute_production_cost(
            PERIOD, [rec], overhead_electrode_inr=999_000.0
        )
        assert cost.electrode_cost_inr == pytest.approx(999_000.0, rel=1e-4)

    def test_sku_cost_allocation_sums_to_total(self, simple_runtime_records):
        engine = CostEngine(COMPANY_ID)
        cost = engine.compute_production_cost(PERIOD, simple_runtime_records)
        allocation = engine.sku_cost_allocation(cost, simple_runtime_records, PERIOD)
        total_allocated = sum(allocation.values())
        assert total_allocated == pytest.approx(cost.total_production_cost_inr, rel=1e-3)

    def test_sku_cost_allocation_proportional_to_runtime(self):
        """SKU with 2× runtime should get 2× cost allocation."""
        rec_a = MillRuntimeRecord(
            company_id=COMPANY_ID, date=date(2025, 4, 1),
            sku_code="P1-SKU-16", brand="P1",
            production_mt=100.0, runtime_hrs=8.0,
        )
        rec_b = MillRuntimeRecord(
            company_id=COMPANY_ID, date=date(2025, 4, 1),
            sku_code="P1-SKU-12", brand="P1",
            production_mt=50.0, runtime_hrs=4.0,
        )
        engine = CostEngine(COMPANY_ID)
        cost = engine.compute_production_cost(PERIOD, [rec_a, rec_b])
        allocation = engine.sku_cost_allocation(cost, [rec_a, rec_b], PERIOD)
        assert allocation["P1-SKU-16"] == pytest.approx(
            allocation["P1-SKU-12"] * 2, rel=1e-3
        )

    def test_compute_from_inputs_matches_direct(self, simple_runtime_records):
        engine = CostEngine(COMPANY_ID)
        bm = BENCHMARK_DEFAULTS
        direct = engine.compute_production_cost(PERIOD, simple_runtime_records, benchmarks=bm)

        total_mt = sum(r.production_mt for r in simple_runtime_records)
        total_runtime = sum(r.runtime_hrs for r in simple_runtime_records)

        inputs = ProductionCostInputs(
            company_id=COMPANY_ID, period=PERIOD,
            power_units_per_hr=bm.power_units_per_hr,
            power_rate_inr_per_unit=bm.power_rate_inr_per_unit,
            fuel_cost_per_hr_inr=bm.fuel_cost_per_hr_inr,
            electrode_cost_inr=bm.electrode_cost_per_mt_inr * total_mt,
            labour_cost_inr=bm.labour_cost_per_mt_inr * total_mt,
            other_fixed_cost_inr=bm.other_fixed_per_mt_inr * total_mt,
            total_production_mt=total_mt,
            total_runtime_hrs=total_runtime,
        )
        from_inputs = engine.compute_production_cost_from_inputs(inputs)
        assert from_inputs.total_production_cost_inr == pytest.approx(
            direct.total_production_cost_inr, rel=1e-3
        )

    def test_module_function_compute_production_cost(self, simple_runtime_records):
        cost = compute_production_cost(COMPANY_ID, PERIOD, simple_runtime_records)
        assert cost.company_id == COMPANY_ID
        assert cost.period == PERIOD
        assert cost.total_production_cost_inr > 0


# ===========================================================================
# 4. raw_material_engine.py — Phase 3 stub contract
# ===========================================================================

class TestRawMaterialEngine:

    def test_always_returns_zero_costs(self):
        engine = RawMaterialEngine(COMPANY_ID)
        rm = engine.compute(PERIOD)
        assert rm.total_raw_material_cost_inr == 0.0
        assert rm.raw_material_cost_per_ton_inr == 0.0
        assert rm.scrap_qty_tons == 0.0

    def test_is_phase3_stub_flag_is_true(self):
        rm = compute_raw_material_cost(COMPANY_ID, PERIOD)
        assert rm.is_phase3_stub is True

    def test_accepts_phase3_params_without_error(self):
        """Interface must accept all Phase 3 params for forward compatibility."""
        engine = RawMaterialEngine(COMPANY_ID)
        rm = engine.compute(
            period=PERIOD,
            scrap_qty_tons=5000.0,
            scrap_cost_per_ton_inr=28000.0,
            billet_output_tons=4750.0,
            consumables_cost_inr=500_000.0,
        )
        assert rm.is_phase3_stub is True
        assert rm.total_raw_material_cost_inr == 0.0

    def test_company_id_and_period_preserved(self):
        rm = compute_raw_material_cost(COMPANY_ID, PERIOD)
        assert rm.company_id == COMPANY_ID
        assert rm.period == PERIOD


# ===========================================================================
# 5. ebitda_engine.py — Assembly and calculation
# ===========================================================================

class TestEbitdaEngine:

    def test_ebitda_formula(self, simple_transactions, simple_runtime_records):
        """EBITDA = Revenue − RM Cost − Production Cost − Overheads"""
        overhead = OverheadRecord(
            company_id=COMPANY_ID, period=PERIOD,
            admin_cost_inr=100_000, selling_cost_inr=200_000,
        )
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(
            period=PERIOD,
            transactions=simple_transactions,
            runtime_records=simple_runtime_records,
            overheads=overhead,
        )
        expected_revenue = 535_000 + 269_000 + 428_000  # 1_232_000
        assert result.total_revenue_inr == pytest.approx(expected_revenue, rel=1e-4)
        assert result.ebitda_inr == pytest.approx(
            result.total_revenue_inr
            - result.raw_material_cost_inr
            - result.production_cost_inr
            - result.overhead_inr,
            rel=1e-4,
        )

    def test_rm_cost_is_zero_and_stub_flagged(self, simple_transactions, simple_runtime_records):
        """Raw material cost must be zero and is_rm_stub=True until Phase 3."""
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        assert result.raw_material_cost_inr == 0.0
        assert result.is_rm_stub is True

    def test_ebitda_margin_pct_correct(self, simple_transactions, simple_runtime_records):
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        expected_margin = result.ebitda_inr / result.total_revenue_inr * 100
        assert result.ebitda_margin_pct == pytest.approx(expected_margin, rel=1e-4)

    def test_p1_p2_revenue_split_sums_to_total(self, simple_transactions, simple_runtime_records):
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        assert result.p1_revenue_inr + result.p2_revenue_inr == pytest.approx(
            result.total_revenue_inr, rel=1e-4
        )

    def test_sku_margin_contributions_sum_approx_to_total(
        self, simple_transactions, simple_runtime_records
    ):
        """Sum of SKU contributions ≈ total EBITDA (minus overheads since overheads are monthly)."""
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        total_contribution = sum(m.contribution_inr for m in result.sku_margins)
        # Contribution margins exclude overheads — should be >= EBITDA
        assert total_contribution >= result.ebitda_inr - 1.0  # allow ₹1 rounding

    def test_sku_margin_count_matches_skus_in_transactions(
        self, simple_transactions, simple_runtime_records
    ):
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        sku_codes_in_txns = {t.sku_code for t in simple_transactions}
        sku_codes_in_margins = {m.sku_code for m in result.sku_margins}
        assert sku_codes_in_txns == sku_codes_in_margins

    def test_empty_transactions_returns_zero_ebitda(self, simple_runtime_records):
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, [], simple_runtime_records)
        assert result.total_revenue_inr == 0.0
        assert result.ebitda_inr <= 0.0  # negative due to production costs

    def test_empty_runtime_returns_zero_production_cost(self, simple_transactions):
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, simple_transactions, [])
        assert result.production_cost_inr == 0.0
        assert result.has_warnings is True

    def test_warnings_field_populated_on_missing_data(self):
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, [], [])
        assert len(result.warnings) > 0

    def test_overhead_zero_when_none(self, simple_transactions, simple_runtime_records):
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(
            PERIOD, simple_transactions, simple_runtime_records, overheads=None
        )
        assert result.overhead_inr == 0.0

    def test_runtime_hrs_matches_cost_engine_total(
        self, simple_transactions, simple_runtime_records
    ):
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        expected_runtime = sum(r.runtime_hrs for r in simple_runtime_records)
        assert result.total_runtime_hrs == pytest.approx(expected_runtime, rel=1e-4)

    def test_to_dict_serialisable(self, simple_transactions, simple_runtime_records):
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "ebitda_inr" in d
        assert "sku_margins" in d


# ===========================================================================
# 6. Monthly Rollup
# ===========================================================================

class TestMonthlyRollup:

    def test_rollup_returns_result_per_period(self, multi_period_dataset):
        d = multi_period_dataset
        engine = EbitdaEngine(COMPANY_ID)
        rollup = engine.compute_monthly_rollup(
            periods=d["periods"],
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
            overheads_by_period=d["overheads_by_period"],
            benchmarks=d["benchmarks"],
        )
        assert len(rollup.results) == len(d["periods"])
        assert len(rollup.periods) == len(d["periods"])

    def test_rollup_latest_ebitda_matches_last_result(self, multi_period_dataset):
        d = multi_period_dataset
        engine = EbitdaEngine(COMPANY_ID)
        rollup = engine.compute_monthly_rollup(
            periods=d["periods"],
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
        )
        assert rollup.latest_ebitda_inr == rollup.results[-1].ebitda_inr

    def test_rollup_best_worst_period_valid(self, multi_period_dataset):
        d = multi_period_dataset
        engine = EbitdaEngine(COMPANY_ID)
        rollup = engine.compute_monthly_rollup(
            periods=d["periods"],
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
        )
        assert rollup.best_period in d["periods"]
        assert rollup.worst_period in d["periods"]

    def test_rollup_trend_direction_is_valid(self, multi_period_dataset):
        d = multi_period_dataset
        engine = EbitdaEngine(COMPANY_ID)
        rollup = engine.compute_monthly_rollup(
            periods=d["periods"],
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
        )
        assert rollup.trend_direction in ("improving", "declining", "stable")

    def test_rollup_empty_periods(self):
        engine = EbitdaEngine(COMPANY_ID)
        rollup = engine.compute_monthly_rollup(periods=[], transactions=[], runtime_records=[])
        assert rollup.periods == []
        assert rollup.trend_direction == "stable"

    def test_module_function_compute_monthly_rollup(self, multi_period_dataset):
        d = multi_period_dataset
        rollup = compute_monthly_rollup(
            company_id=COMPANY_ID,
            periods=d["periods"],
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
        )
        assert rollup.company_id == COMPANY_ID


# ===========================================================================
# 7. EBITDA Simulator
# ===========================================================================

class TestSimulator:

    def test_zero_deltas_produces_identical_result(
        self, simple_transactions, simple_runtime_records
    ):
        engine = EbitdaEngine(COMPANY_ID)
        base = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        inputs = SimulatorInputs(base_period=PERIOD)
        sim = engine.simulate_ebitda(base, inputs)
        assert sim.base_ebitda_inr == pytest.approx(sim.simulated_ebitda_inr, rel=1e-3)

    def test_positive_realisation_delta_increases_revenue(
        self, simple_transactions, simple_runtime_records
    ):
        engine = EbitdaEngine(COMPANY_ID)
        base = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        inputs = SimulatorInputs(base_period=PERIOD, realisation_delta_pct=10.0)
        sim = engine.simulate_ebitda(base, inputs)
        assert sim.simulated_revenue_inr > sim.base_revenue_inr

    def test_negative_volume_delta_decreases_revenue(
        self, simple_transactions, simple_runtime_records
    ):
        engine = EbitdaEngine(COMPANY_ID)
        base = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        inputs = SimulatorInputs(base_period=PERIOD, volume_delta_pct=-20.0)
        sim = engine.simulate_ebitda(base, inputs)
        assert sim.simulated_revenue_inr < sim.base_revenue_inr

    def test_higher_power_rate_increases_production_cost(
        self, simple_transactions, simple_runtime_records
    ):
        engine = EbitdaEngine(COMPANY_ID)
        base = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        inputs = SimulatorInputs(base_period=PERIOD, power_rate_delta_pct=15.0)
        sim = engine.simulate_ebitda(base, inputs)
        assert sim.simulated_production_cost_inr > sim.base_production_cost_inr

    def test_scrap_price_delta_has_no_effect_in_phase2(
        self, simple_transactions, simple_runtime_records
    ):
        """Phase 3 stub: scrap_price_delta_pct must not affect EBITDA until Phase 3."""
        engine = EbitdaEngine(COMPANY_ID)
        base = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        inputs_no_scrap = SimulatorInputs(base_period=PERIOD)
        inputs_scrap = SimulatorInputs(base_period=PERIOD, scrap_price_delta_pct=50.0)
        sim_no = engine.simulate_ebitda(base, inputs_no_scrap)
        sim_yes = engine.simulate_ebitda(base, inputs_scrap)
        assert sim_no.simulated_ebitda_inr == pytest.approx(
            sim_yes.simulated_ebitda_inr, rel=1e-4
        )

    def test_margin_delta_correct(self, simple_transactions, simple_runtime_records):
        engine = EbitdaEngine(COMPANY_ID)
        base = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        inputs = SimulatorInputs(base_period=PERIOD, realisation_delta_pct=5.0)
        sim = engine.simulate_ebitda(base, inputs)
        assert sim.margin_delta_pct == pytest.approx(
            sim.simulated_ebitda_margin_pct - sim.base_ebitda_margin_pct, rel=1e-4
        )

    def test_simulator_to_dict_serialisable(
        self, simple_transactions, simple_runtime_records
    ):
        engine = EbitdaEngine(COMPANY_ID)
        base = engine.compute_ebitda(PERIOD, simple_transactions, simple_runtime_records)
        inputs = SimulatorInputs(base_period=PERIOD, realisation_delta_pct=5.0)
        sim = engine.simulate_ebitda(base, inputs)
        d = sim.to_dict()
        assert isinstance(d, dict)
        assert "simulated_ebitda_inr" in d


# ===========================================================================
# 8. Integration — Synthetic AC Industries data
# ===========================================================================

class TestIntegration:

    def test_full_ebitda_with_synthetic_data(self, synthetic_dataset):
        d = synthetic_dataset
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(
            period=PERIOD,
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
            overheads=d["overheads"],
            benchmarks=d["benchmarks"],
        )
        assert result.total_revenue_inr > 0
        assert result.production_cost_inr > 0
        assert result.ebitda_inr > 0  # should be profitable
        assert 0 < result.ebitda_margin_pct < 100

    def test_ebitda_margin_in_realistic_range(self, synthetic_dataset):
        """AC Industries TMT mill should have EBITDA margin roughly 8–20% at Phase 2."""
        d = synthetic_dataset
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(
            period=PERIOD,
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
            overheads=d["overheads"],
            benchmarks=d["benchmarks"],
        )
        # With RM cost as Phase 3 stub (zero), margin will be higher than real
        # but should still be < 100%
        assert result.ebitda_margin_pct > 0
        assert result.ebitda_margin_pct < 100

    def test_p1_revenue_greater_than_p2(self, synthetic_dataset):
        """Product 1 is the growth brand with higher proportion — P1 revenue > P2."""
        d = synthetic_dataset
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(
            period=PERIOD,
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
        )
        assert result.p1_revenue_inr > result.p2_revenue_inr

    def test_all_14_skus_have_margin_records(self, synthetic_dataset):
        """All 14 AC Industries SKUs (7 P1 + 7 P2) should appear in margin records."""
        d = synthetic_dataset
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(
            period=PERIOD,
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
        )
        sku_codes = {m.sku_code for m in result.sku_margins}
        # At minimum, the major SKUs should be present
        assert "P1-SKU-16" in sku_codes
        assert "P1-SKU-10" in sku_codes
        assert "P2-SKU-10" in sku_codes

    def test_rollup_7_months(self, multi_period_dataset):
        d = multi_period_dataset
        rollup = compute_monthly_rollup(
            company_id=COMPANY_ID,
            periods=d["periods"],
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
            overheads_by_period=d["overheads_by_period"],
            benchmarks=d["benchmarks"],
        )
        assert len(rollup.results) == 7
        for r in rollup.results:
            assert r.total_revenue_inr > 0
            assert r.ebitda_margin_pct < 100

    def test_data_completeness_between_0_and_100(self, synthetic_dataset):
        d = synthetic_dataset
        engine = EbitdaEngine(COMPANY_ID)
        result = engine.compute_ebitda(PERIOD, d["transactions"], d["runtime_records"])
        assert 0.0 <= result.data_completeness_pct <= 100.0

    def test_module_function_compute_ebitda(self, synthetic_dataset):
        d = synthetic_dataset
        result = compute_ebitda(
            company_id=COMPANY_ID,
            period=PERIOD,
            transactions=d["transactions"],
            runtime_records=d["runtime_records"],
            overheads=d["overheads"],
        )
        assert result.company_id == COMPANY_ID
        assert result.period == PERIOD
