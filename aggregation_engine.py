"""
aggregation_engine.py — Session 2: Aggregation Engine
AC Industries EBITDA Intelligence Platform

Consumes rows in Standard Internal Format (SIF) — the output of the
Session 1 Universal Data Connector — and computes:

    1. Daily totals by SKU
    2. Daily brand split (P1 vs P2)
    3. Daily region split (Chennai vs Outside Chennai)
    4. SKU proportion calculations (used by the Session 3 Forecasting Engine)

All logic is pure Python — no pandas dependency — so the engine can run
both inside FastAPI and inside test suites without heavy dependencies.

Key decisions from master context v1.1:
  - Region classification: "Chennai" district → Chennai region;
    everything else → "Outside Chennai"
  - Sunday exclusion: Sales holiday calendars exclude Sundays from
    proportion calculations (§4.6)
  - Realisation per ton = value_inr / quantity_tons (§6.2)
  - Rolling factor and billet logic live in the Production Optimiser
    (Session 4) — NOT here
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from .aggregation_models import (
    AggregationResult,
    BrandSplit,
    DailyBrandTotal,
    DailyRegionTotal,
    DailySkuTotal,
    DailySummary,
    PeriodSummary,
    SkuProportion,
)
from .sku_master import SKUMaster


# ------------------------------------------------------------------ #
# SIF Row — mirrors the Standard Internal Format from §6.2            #
# ------------------------------------------------------------------ #

@dataclass
class SIFRow:
    """
    One row of Standard Internal Format data.
    This is the input contract for the aggregation engine.
    The Session 1 connector outputs rows in this shape.
    """
    date: date
    customer_id: str
    brand: str              # "P1" or "P2"
    sku_name: str
    size_mm: int
    quantity_tons: float
    value_inr: float
    region: str
    district: str
    invoice_id: str
    company_id: str
    source_file: str = ""
    ingested_at: Optional[str] = None


# ------------------------------------------------------------------ #
# Region classifier                                                   #
# ------------------------------------------------------------------ #

CHENNAI_DISTRICT = "Chennai"   # canonical district name from SAP export


def classify_region(district: str) -> str:
    """
    Map a SAP district value to the two-region split used by the
    forecasting engine (§3.4).

    Chennai → "Chennai"
    Anything else → "Outside Chennai"
    """
    return CHENNAI_DISTRICT if district.strip().lower() == "chennai" else "Outside Chennai"


# ------------------------------------------------------------------ #
# Aggregation Engine                                                  #
# ------------------------------------------------------------------ #

class AggregationEngine:
    """
    Stateless aggregation engine.  Instantiate once per company and call
    aggregate() with whatever date range and rows you need.

    Parameters
    ----------
    company_id : str
        Multi-tenant key injected by the connector (§7.1).
    sku_master : SKUMaster
        Client's SKU catalogue — used to validate brand/size combos
        and to detect unknown SKUs in the input.
    holidays : set[date], optional
        Production/sales holiday dates (§4.6).  Sundays are always
        excluded from proportion calculations regardless of this set.
    """

    def __init__(
        self,
        company_id: str,
        sku_master: SKUMaster,
        holidays: Optional[set[date]] = None,
    ) -> None:
        self.company_id = company_id
        self.sku_master = sku_master
        self.holidays: set[date] = holidays or set()

    # ---------------------------------------------------------------- #
    # Public API                                                        #
    # ---------------------------------------------------------------- #

    def aggregate(
        self,
        rows: list[SIFRow],
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> AggregationResult:
        """
        Main entry point.  Aggregates all rows into a full report.

        Parameters
        ----------
        rows : list[SIFRow]
            SIF rows for the company (may span multiple dates).
        from_date / to_date : date, optional
            If supplied, only rows within [from_date, to_date] are
            included.  If omitted, the full range of the input is used.
        """
        warnings: list[str] = []

        # ── Filter to company + date range ──────────────────────────
        rows = [r for r in rows if r.company_id == self.company_id]
        if from_date:
            rows = [r for r in rows if r.date >= from_date]
        if to_date:
            rows = [r for r in rows if r.date <= to_date]

        if not rows:
            fd = from_date or date.today()
            td = to_date or date.today()
            return self._empty_result(fd, td)

        actual_from = min(r.date for r in rows)
        actual_to   = max(r.date for r in rows)
        from_date = from_date or actual_from
        to_date   = to_date   or actual_to

        # ── Validate / normalise regions ────────────────────────────
        unknown_district_count = 0
        normalised: list[SIFRow] = []
        for r in rows:
            region = classify_region(r.district)
            if r.district.strip() == "" or r.district.strip().lower() == "unknown":
                unknown_district_count += 1
                region = "Outside Chennai"
            normalised.append(
                SIFRow(
                    date=r.date,
                    customer_id=r.customer_id,
                    brand=r.brand,
                    sku_name=r.sku_name,
                    size_mm=r.size_mm,
                    quantity_tons=r.quantity_tons,
                    value_inr=r.value_inr,
                    region=region,
                    district=r.district,
                    invoice_id=r.invoice_id,
                    company_id=r.company_id,
                    source_file=r.source_file,
                    ingested_at=r.ingested_at,
                )
            )
        if unknown_district_count:
            warnings.append(
                f"{unknown_district_count} row(s) had blank/unknown district "
                f"— assigned to 'Outside Chennai'."
            )

        rows = normalised

        # ── Build daily summaries ────────────────────────────────────
        by_date: dict[date, list[SIFRow]] = defaultdict(list)
        for r in rows:
            by_date[r.date].append(r)

        daily_summaries: list[DailySummary] = []
        for d in sorted(by_date):
            daily_summaries.append(
                self._build_daily_summary(d, by_date[d])
            )

        # ── Period-level aggregations ────────────────────────────────
        trading_days = self._count_trading_days(from_date, to_date)
        period_summary = self._build_period_summary(
            from_date, to_date, rows, daily_summaries, trading_days
        )

        return AggregationResult(
            company_id=self.company_id,
            from_date=from_date,
            to_date=to_date,
            period_summary=period_summary,
            warnings=warnings,
        )

    def daily_sku_totals(
        self, rows: list[SIFRow], target_date: date
    ) -> list[DailySkuTotal]:
        """Return per-SKU totals for a single date."""
        day_rows = [r for r in rows if r.date == target_date and r.company_id == self.company_id]
        return self._sku_totals_for_rows(target_date, day_rows)

    def daily_brand_totals(
        self, rows: list[SIFRow], target_date: date
    ) -> list[DailyBrandTotal]:
        """Return per-brand totals for a single date."""
        day_rows = [r for r in rows if r.date == target_date and r.company_id == self.company_id]
        return self._brand_totals_for_rows(target_date, day_rows)

    def daily_region_totals(
        self, rows: list[SIFRow], target_date: date
    ) -> list[DailyRegionTotal]:
        """Return per-region totals for a single date."""
        day_rows = [r for r in rows if r.date == target_date and r.company_id == self.company_id]
        normalised = [
            SIFRow(**{**r.__dict__, "region": classify_region(r.district)})
            for r in day_rows
        ]
        return self._region_totals_for_rows(target_date, normalised)

    def sku_proportions(
        self,
        rows: list[SIFRow],
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        exclude_sundays: bool = True,
    ) -> list[SkuProportion]:
        """
        Calculate SKU proportion table (§3.6).

        Sunday exclusion is on by default — mirrors the proportion model
        in the master context which notes "(excl Sunday)".
        """
        rows = [r for r in rows if r.company_id == self.company_id]
        if from_date:
            rows = [r for r in rows if r.date >= from_date]
        if to_date:
            rows = [r for r in rows if r.date <= to_date]
        if exclude_sundays:
            rows = [r for r in rows if r.date.weekday() != 6]  # 6 = Sunday

        if not rows:
            return []

        # Accumulate qty per (brand, size)
        totals: dict[tuple[str, int], float] = defaultdict(float)
        trading_dates: dict[tuple[str, int], set[date]] = defaultdict(set)

        grand_total = 0.0
        for r in rows:
            key = (r.brand, r.size_mm)
            totals[key] += r.quantity_tons
            trading_dates[key].add(r.date)
            grand_total += r.quantity_tons

        if grand_total == 0:
            return []

        all_trading_days = len({r.date for r in rows})

        proportions: list[SkuProportion] = []
        for (brand, size), qty in sorted(totals.items(), key=lambda x: -x[1]):
            days = len(trading_dates[(brand, size)])
            proportions.append(
                SkuProportion(
                    brand_code=brand,
                    size_mm=size,
                    total_quantity_tons=round(qty, 3),
                    proportion_pct=round(qty / grand_total * 100, 2),
                    trading_days=days,
                    avg_daily_tons=round(qty / all_trading_days, 3),
                )
            )
        return proportions

    # ---------------------------------------------------------------- #
    # Private helpers                                                   #
    # ---------------------------------------------------------------- #

    def _build_daily_summary(self, d: date, rows: list[SIFRow]) -> DailySummary:
        total_qty   = sum(r.quantity_tons for r in rows)
        total_value = sum(r.value_inr for r in rows)
        realisation = total_value / total_qty if total_qty else 0.0

        return DailySummary(
            date=d,
            company_id=self.company_id,
            total_quantity_tons=round(total_qty, 3),
            total_value_inr=round(total_value, 2),
            overall_realisation_per_ton=round(realisation, 2),
            brand_totals=self._brand_totals_for_rows(d, rows),
            sku_totals=self._sku_totals_for_rows(d, rows),
            region_totals=self._region_totals_for_rows(d, rows),
            is_sunday=(d.weekday() == 6),
            is_holiday=(d in self.holidays),
        )

    @staticmethod
    def _sku_totals_for_rows(d: date, rows: list[SIFRow]) -> list[DailySkuTotal]:
        acc: dict[tuple[str, int], dict] = defaultdict(lambda: {"qty": 0.0, "val": 0.0})
        for r in rows:
            key = (r.brand, r.size_mm)
            acc[key]["qty"] += r.quantity_tons
            acc[key]["val"] += r.value_inr

        result = []
        for (brand, size), totals in sorted(acc.items()):
            qty = totals["qty"]
            val = totals["val"]
            result.append(
                DailySkuTotal(
                    date=d,
                    brand_code=brand,
                    size_mm=size,
                    quantity_tons=round(qty, 3),
                    value_inr=round(val, 2),
                    realisation_per_ton=round(val / qty, 2) if qty else 0.0,
                )
            )
        return result

    @staticmethod
    def _brand_totals_for_rows(d: date, rows: list[SIFRow]) -> list[DailyBrandTotal]:
        acc: dict[str, dict] = defaultdict(lambda: {"qty": 0.0, "val": 0.0, "skus": set()})
        for r in rows:
            acc[r.brand]["qty"] += r.quantity_tons
            acc[r.brand]["val"] += r.value_inr
            acc[r.brand]["skus"].add(r.size_mm)

        result = []
        for brand, totals in sorted(acc.items()):
            qty = totals["qty"]
            val = totals["val"]
            result.append(
                DailyBrandTotal(
                    date=d,
                    brand_code=brand,
                    quantity_tons=round(qty, 3),
                    value_inr=round(val, 2),
                    realisation_per_ton=round(val / qty, 2) if qty else 0.0,
                    sku_count=len(totals["skus"]),
                )
            )
        return result

    @staticmethod
    def _region_totals_for_rows(d: date, rows: list[SIFRow]) -> list[DailyRegionTotal]:
        acc: dict[str, dict] = defaultdict(lambda: {"qty": 0.0, "val": 0.0, "brands": defaultdict(float)})
        for r in rows:
            acc[r.region]["qty"] += r.quantity_tons
            acc[r.region]["val"] += r.value_inr
            acc[r.region]["brands"][r.brand] += r.quantity_tons

        result = []
        for region, totals in sorted(acc.items()):
            result.append(
                DailyRegionTotal(
                    date=d,
                    region=region,
                    quantity_tons=round(totals["qty"], 3),
                    value_inr=round(totals["val"], 2),
                    brand_breakdown={k: round(v, 3) for k, v in totals["brands"].items()},
                )
            )
        return result

    def _build_period_summary(
        self,
        from_date: date,
        to_date: date,
        rows: list[SIFRow],
        daily_summaries: list[DailySummary],
        trading_days: int,
    ) -> PeriodSummary:
        total_qty   = sum(r.quantity_tons for r in rows)
        total_value = sum(r.value_inr for r in rows)
        realisation = total_value / total_qty if total_qty else 0.0

        # Brand splits
        brand_acc: dict[str, dict] = defaultdict(lambda: {"qty": 0.0, "val": 0.0})
        for r in rows:
            brand_acc[r.brand]["qty"] += r.quantity_tons
            brand_acc[r.brand]["val"] += r.value_inr

        brand_splits = []
        for brand, totals in sorted(brand_acc.items()):
            qty = totals["qty"]
            val = totals["val"]
            brand_splits.append(
                BrandSplit(
                    brand_code=brand,
                    total_quantity_tons=round(qty, 3),
                    total_value_inr=round(val, 2),
                    proportion_pct=round(qty / total_qty * 100, 2) if total_qty else 0.0,
                    realisation_per_ton=round(val / qty, 2) if qty else 0.0,
                )
            )

        # Region totals across the whole period
        region_acc: dict[str, dict] = defaultdict(lambda: {"qty": 0.0, "val": 0.0, "brands": defaultdict(float)})
        for r in rows:
            region_acc[r.region]["qty"] += r.quantity_tons
            region_acc[r.region]["val"] += r.value_inr
            region_acc[r.region]["brands"][r.brand] += r.quantity_tons

        # Use a synthetic "period" date for region totals
        region_totals = []
        for region, totals in sorted(region_acc.items()):
            region_totals.append(
                DailyRegionTotal(
                    date=from_date,   # start of period as reference
                    region=region,
                    quantity_tons=round(totals["qty"], 3),
                    value_inr=round(totals["val"], 2),
                    brand_breakdown={k: round(v, 3) for k, v in totals["brands"].items()},
                )
            )

        sku_proportions = self.sku_proportions(rows, from_date, to_date)

        return PeriodSummary(
            company_id=self.company_id,
            from_date=from_date,
            to_date=to_date,
            total_quantity_tons=round(total_qty, 3),
            total_value_inr=round(total_value, 2),
            overall_realisation_per_ton=round(realisation, 2),
            trading_days=trading_days,
            brand_splits=brand_splits,
            sku_proportions=sku_proportions,
            region_totals=region_totals,
            daily_summaries=daily_summaries,
        )

    def _count_trading_days(self, from_date: date, to_date: date) -> int:
        """Count non-Sunday, non-holiday days in the range (inclusive)."""
        count = 0
        d = from_date
        while d <= to_date:
            if d.weekday() != 6 and d not in self.holidays:
                count += 1
            d += timedelta(days=1)
        return count

    @staticmethod
    def _empty_result(from_date: date, to_date: date) -> AggregationResult:
        empty_period = PeriodSummary(
            company_id="",
            from_date=from_date,
            to_date=to_date,
            total_quantity_tons=0.0,
            total_value_inr=0.0,
            overall_realisation_per_ton=0.0,
            trading_days=0,
        )
        return AggregationResult(
            company_id="",
            from_date=from_date,
            to_date=to_date,
            period_summary=empty_period,
            warnings=["No rows found for the given company_id / date range."],
        )
