"""
test_aggregation.py — Session 2 test suite
AC Industries EBITDA Intelligence Platform

35+ test cases covering:
  - Daily SKU totals
  - Daily brand split
  - Daily region split (Chennai vs Outside Chennai)
  - SKU proportions (with/without Sunday exclusion)
  - Period summaries
  - Multi-tenant isolation
  - Edge cases (empty input, zero qty, single row, all-Sunday period)
  - Holiday handling
  - Unknown/blank district assignment
  - Region classifier
  - Realisation calculation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import date

from aggregator import (
    AggregationEngine,
    SIFRow,
    classify_region,
    AC_INDUSTRIES_SKU_MASTER,
)


# ================================================================== #
# Fixtures                                                            #
# ================================================================== #

COMPANY = "AC001"
OTHER_COMPANY = "AC002"

# Monday 2025-04-07
MON = date(2025, 4, 7)
TUE = date(2025, 4, 8)
WED = date(2025, 4, 9)
SUN = date(2025, 4, 13)   # Sunday
HOL = date(2025, 4, 14)   # Public holiday (Tamil New Year)


def make_row(
    d: date = MON,
    brand: str = "P1",
    size: int = 16,
    qty: float = 10.0,
    value: float = 550000.0,
    district: str = "Chennai",
    company: str = COMPANY,
    invoice: str = "INV001",
) -> SIFRow:
    return SIFRow(
        date=d,
        customer_id="CUST001",
        brand=brand,
        sku_name=f"{size}mm {brand}",
        size_mm=size,
        quantity_tons=qty,
        value_inr=value,
        region=classify_region(district),
        district=district,
        invoice_id=invoice,
        company_id=company,
        source_file="test.xlsx",
    )


@pytest.fixture
def engine():
    return AggregationEngine(COMPANY, AC_INDUSTRIES_SKU_MASTER)


@pytest.fixture
def engine_with_holiday():
    return AggregationEngine(COMPANY, AC_INDUSTRIES_SKU_MASTER, holidays={HOL})


@pytest.fixture
def basic_rows():
    """One Chennai P1 row and one Outside Chennai P2 row on a Monday."""
    return [
        make_row(MON, "P1", 16, 10.0, 550000.0, "Chennai",       COMPANY, "INV001"),
        make_row(MON, "P2", 10,  5.0, 260000.0, "Coimbatore",    COMPANY, "INV002"),
    ]


@pytest.fixture
def multi_day_rows():
    """Three days of data, two SKUs each day."""
    rows = []
    for d in [MON, TUE, WED]:
        rows += [
            make_row(d, "P1", 16, 12.0, 660000.0, "Chennai",    COMPANY, f"INV-P1-16-{d}"),
            make_row(d, "P1", 12,  8.0, 424000.0, "Chennai",    COMPANY, f"INV-P1-12-{d}"),
            make_row(d, "P2", 10,  5.0, 260000.0, "Coimbatore", COMPANY, f"INV-P2-10-{d}"),
        ]
    return rows


# ================================================================== #
# 1. Region Classifier                                               #
# ================================================================== #

class TestClassifyRegion:
    def test_chennai_exact(self):
        assert classify_region("Chennai") == "Chennai"

    def test_chennai_lowercase(self):
        assert classify_region("chennai") == "Chennai"

    def test_chennai_padded(self):
        assert classify_region("  Chennai  ") == "Chennai"

    def test_coimbatore_is_outside(self):
        assert classify_region("Coimbatore") == "Outside Chennai"

    def test_blank_is_outside(self):
        assert classify_region("") == "Outside Chennai"

    def test_madurai_is_outside(self):
        assert classify_region("Madurai") == "Outside Chennai"

    def test_salem_is_outside(self):
        assert classify_region("Salem") == "Outside Chennai"


# ================================================================== #
# 2. Daily SKU Totals                                                #
# ================================================================== #

class TestDailySkuTotals:
    def test_single_row(self, engine, basic_rows):
        totals = engine.daily_sku_totals(basic_rows, MON)
        p1_16 = next(t for t in totals if t.brand_code == "P1" and t.size_mm == 16)
        assert p1_16.quantity_tons == 10.0
        assert p1_16.value_inr == 550000.0
        assert p1_16.realisation_per_ton == 55000.0

    def test_two_brands_two_sizes(self, engine, basic_rows):
        totals = engine.daily_sku_totals(basic_rows, MON)
        assert len(totals) == 2

    def test_aggregates_multiple_invoices_same_sku(self, engine):
        rows = [
            make_row(MON, "P1", 16, 5.0, 275000.0, "Chennai", COMPANY, "INV001"),
            make_row(MON, "P1", 16, 3.0, 165000.0, "Chennai", COMPANY, "INV002"),
        ]
        totals = engine.daily_sku_totals(rows, MON)
        assert len(totals) == 1
        assert totals[0].quantity_tons == 8.0
        assert totals[0].value_inr == 440000.0

    def test_no_rows_for_date_returns_empty(self, engine, basic_rows):
        totals = engine.daily_sku_totals(basic_rows, TUE)
        assert totals == []

    def test_realisation_zero_qty_safe(self, engine):
        row = make_row(MON, "P1", 16, 0.0, 0.0)
        totals = engine.daily_sku_totals([row], MON)
        assert totals[0].realisation_per_ton == 0.0

    def test_company_isolation(self, engine):
        rows = [
            make_row(MON, "P1", 16, 10.0, 550000.0, "Chennai", COMPANY),
            make_row(MON, "P1", 16, 99.0, 999999.0, "Chennai", OTHER_COMPANY),
        ]
        totals = engine.daily_sku_totals(rows, MON)
        assert len(totals) == 1
        assert totals[0].quantity_tons == 10.0


# ================================================================== #
# 3. Daily Brand Totals                                              #
# ================================================================== #

class TestDailyBrandTotals:
    def test_two_brands(self, engine, basic_rows):
        totals = engine.daily_brand_totals(basic_rows, MON)
        brands = {t.brand_code for t in totals}
        assert brands == {"P1", "P2"}

    def test_p1_values(self, engine, basic_rows):
        totals = engine.daily_brand_totals(basic_rows, MON)
        p1 = next(t for t in totals if t.brand_code == "P1")
        assert p1.quantity_tons == 10.0
        assert p1.value_inr == 550000.0
        assert p1.realisation_per_ton == 55000.0
        assert p1.sku_count == 1

    def test_sku_count_multiple_sizes(self, engine):
        rows = [
            make_row(MON, "P1", 16, 10.0, 550000.0),
            make_row(MON, "P1", 12,  8.0, 424000.0),
            make_row(MON, "P1", 10,  6.0, 300000.0),
        ]
        totals = engine.daily_brand_totals(rows, MON)
        p1 = totals[0]
        assert p1.sku_count == 3
        assert p1.quantity_tons == 24.0

    def test_single_brand_only(self, engine):
        rows = [make_row(MON, "P1", 16, 10.0, 550000.0)]
        totals = engine.daily_brand_totals(rows, MON)
        assert len(totals) == 1
        assert totals[0].brand_code == "P1"


# ================================================================== #
# 4. Daily Region Totals                                             #
# ================================================================== #

class TestDailyRegionTotals:
    def test_two_regions(self, engine, basic_rows):
        totals = engine.daily_region_totals(basic_rows, MON)
        regions = {t.region for t in totals}
        assert regions == {"Chennai", "Outside Chennai"}

    def test_chennai_qty(self, engine, basic_rows):
        totals = engine.daily_region_totals(basic_rows, MON)
        ch = next(t for t in totals if t.region == "Chennai")
        assert ch.quantity_tons == 10.0

    def test_outside_chennai_qty(self, engine, basic_rows):
        totals = engine.daily_region_totals(basic_rows, MON)
        oc = next(t for t in totals if t.region == "Outside Chennai")
        assert oc.quantity_tons == 5.0

    def test_brand_breakdown_in_region(self, engine, basic_rows):
        totals = engine.daily_region_totals(basic_rows, MON)
        ch = next(t for t in totals if t.region == "Chennai")
        assert "P1" in ch.brand_breakdown
        assert ch.brand_breakdown["P1"] == 10.0

    def test_all_chennai(self, engine):
        rows = [
            make_row(MON, "P1", 16, 10.0, 550000.0, "Chennai"),
            make_row(MON, "P2", 10,  5.0, 260000.0, "Chennai"),
        ]
        totals = engine.daily_region_totals(rows, MON)
        assert len(totals) == 1
        assert totals[0].region == "Chennai"
        assert totals[0].quantity_tons == 15.0

    def test_unknown_district_goes_to_outside(self, engine):
        rows = [make_row(MON, "P1", 16, 7.0, 385000.0, "")]
        result = engine.aggregate(rows)
        oc = next(
            t for t in result.period_summary.region_totals
            if t.region == "Outside Chennai"
        )
        assert oc.quantity_tons == 7.0
        assert len(result.warnings) == 1
        assert "blank/unknown district" in result.warnings[0]


# ================================================================== #
# 5. SKU Proportions                                                 #
# ================================================================== #

class TestSkuProportions:
    def test_proportions_sum_to_100(self, engine, multi_day_rows):
        props = engine.sku_proportions(multi_day_rows)
        total = sum(p.proportion_pct for p in props)
        assert abs(total - 100.0) < 0.01

    def test_sunday_excluded_by_default(self, engine):
        rows = [
            make_row(MON, "P1", 16, 10.0, 550000.0),
            make_row(SUN, "P1", 16, 99.0, 999999.0),  # Sunday — should be excluded
        ]
        props = engine.sku_proportions(rows)
        assert len(props) == 1
        assert props[0].total_quantity_tons == 10.0

    def test_sunday_included_when_flag_off(self, engine):
        rows = [
            make_row(MON, "P1", 16, 10.0, 550000.0),
            make_row(SUN, "P1", 16, 99.0, 5445000.0),
        ]
        props = engine.sku_proportions(rows, exclude_sundays=False)
        assert props[0].total_quantity_tons == 109.0

    def test_highest_volume_first(self, engine):
        rows = [
            make_row(MON, "P1", 16, 20.0, 1100000.0),
            make_row(MON, "P1", 12, 5.0,  265000.0),
        ]
        props = engine.sku_proportions(rows)
        assert props[0].size_mm == 16

    def test_proportion_correct_pct(self, engine):
        rows = [
            make_row(MON, "P1", 16, 75.0, 4125000.0),
            make_row(MON, "P2", 10, 25.0, 1300000.0),
        ]
        props = engine.sku_proportions(rows)
        p1 = next(p for p in props if p.brand_code == "P1")
        assert p1.proportion_pct == 75.0

    def test_empty_returns_empty_list(self, engine):
        assert engine.sku_proportions([]) == []

    def test_company_isolation(self, engine):
        rows = [
            make_row(MON, "P1", 16, 10.0, 550000.0, company=COMPANY),
            make_row(MON, "P1", 16, 99.0, 999999.0, company=OTHER_COMPANY),
        ]
        props = engine.sku_proportions(rows)
        assert props[0].total_quantity_tons == 10.0


# ================================================================== #
# 6. Full Aggregate — Period Summary                                 #
# ================================================================== #

class TestAggregate:
    def test_period_totals(self, engine, multi_day_rows):
        result = engine.aggregate(multi_day_rows)
        expected_qty = (12.0 + 8.0 + 5.0) * 3   # 3 days
        assert result.period_summary.total_quantity_tons == pytest.approx(expected_qty)

    def test_daily_summaries_count(self, engine, multi_day_rows):
        result = engine.aggregate(multi_day_rows)
        assert len(result.period_summary.daily_summaries) == 3

    def test_date_range_filter(self, engine, multi_day_rows):
        result = engine.aggregate(multi_day_rows, from_date=MON, to_date=TUE)
        assert len(result.period_summary.daily_summaries) == 2

    def test_brand_splits_present(self, engine, multi_day_rows):
        result = engine.aggregate(multi_day_rows)
        brands = {b.brand_code for b in result.period_summary.brand_splits}
        assert brands == {"P1", "P2"}

    def test_sku_proportions_in_period(self, engine, multi_day_rows):
        result = engine.aggregate(multi_day_rows)
        assert len(result.period_summary.sku_proportions) == 3  # P1-16, P1-12, P2-10

    def test_region_totals_in_period(self, engine, multi_day_rows):
        result = engine.aggregate(multi_day_rows)
        regions = {r.region for r in result.period_summary.region_totals}
        assert regions == {"Chennai", "Outside Chennai"}

    def test_realisation_per_ton(self, engine):
        rows = [make_row(MON, "P1", 16, 10.0, 550000.0)]
        result = engine.aggregate(rows)
        assert result.period_summary.overall_realisation_per_ton == 55000.0

    def test_empty_input_returns_warnings(self, engine):
        result = engine.aggregate([])
        assert len(result.warnings) >= 1

    def test_wrong_company_rows_ignored(self, engine):
        rows = [make_row(MON, "P1", 16, 99.0, 999999.0, company=OTHER_COMPANY)]
        result = engine.aggregate(rows)
        assert result.period_summary.total_quantity_tons == 0.0

    def test_trading_days_excludes_sundays(self, engine):
        rows = [
            make_row(MON, "P1", 16, 10.0, 550000.0),
            make_row(SUN, "P1", 16, 10.0, 550000.0),
        ]
        result = engine.aggregate(rows, from_date=MON, to_date=SUN)
        # 7-day window: 6 weekdays + 1 Sunday → 6 trading days
        assert result.period_summary.trading_days == 6

    def test_trading_days_excludes_holidays(self, engine_with_holiday):
        # HOL is Monday 2025-04-14
        rows = [make_row(HOL, "P1", 16, 10.0, 550000.0)]
        result = engine_with_holiday.aggregate(rows, from_date=HOL, to_date=HOL)
        assert result.period_summary.trading_days == 0

    def test_is_sunday_flag_on_daily_summary(self, engine):
        rows = [make_row(SUN, "P1", 16, 10.0, 550000.0)]
        result = engine.aggregate(rows)
        summary = result.period_summary.daily_summaries[0]
        assert summary.is_sunday is True

    def test_is_holiday_flag_on_daily_summary(self, engine_with_holiday):
        rows = [make_row(HOL, "P1", 16, 10.0, 550000.0)]
        result = engine_with_holiday.aggregate(rows)
        summary = result.period_summary.daily_summaries[0]
        assert summary.is_holiday is True

    def test_p1_brand_split_proportion(self, engine):
        rows = [
            make_row(MON, "P1", 16, 60.0, 3300000.0),
            make_row(MON, "P2", 10, 40.0, 2080000.0),
        ]
        result = engine.aggregate(rows)
        p1_split = next(b for b in result.period_summary.brand_splits if b.brand_code == "P1")
        assert p1_split.proportion_pct == 60.0

    def test_no_warnings_on_clean_data(self, engine, multi_day_rows):
        result = engine.aggregate(multi_day_rows)
        assert result.warnings == []
