"""
revenue_engine.py — AC Industries EBITDA Intelligence Platform
Session 5: EBITDA Engine — Revenue Lifecycle

Pulls sales_transactions (SIF format, output of Session 1 connector),
aggregates revenue and quantity by period × brand × SKU, and derives
realisation per ton as: value_inr / quantity_tons.

No separate price field exists in the SAP export — realisation is always
derived from the SIF record's value_inr and quantity_tons fields.

Public entry point:
    compute_revenue(company_id, period, transactions) -> tuple[RevenueRecord, RevenueRecord]
    Returns (p1_record, p2_record).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Protocol, Tuple

from ebitda_models import RealisationRecord, RevenueRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SIF Transaction Protocol — duck-typed so real DB rows and dicts both work
# ---------------------------------------------------------------------------

@dataclass
class SifTransaction:
    """
    Mirrors the Standard Internal Format (SIF) fields used by revenue engine.
    Only the fields needed for revenue calculation are declared here.
    Full SIF spec is in Section 6.2 of the master context.
    """
    company_id: str
    date: date
    brand: str          # "P1" | "P2"
    sku_code: str       # e.g. "P1-SKU-16" — derived field, may be absent in raw SIF
    sku_name: str       # e.g. "16mm Product 1 Fe550"
    size_mm: int
    quantity_tons: float
    value_inr: float
    region: str
    district: str
    invoice_id: str


# ---------------------------------------------------------------------------
# Revenue Engine
# ---------------------------------------------------------------------------

class RevenueEngine:
    """
    Computes revenue records from a list of SIF transactions for a given period.

    Usage:
        engine = RevenueEngine(company_id="AC001")
        p1, p2 = engine.compute_revenue("2025-04", transactions)
    """

    def __init__(self, company_id: str):
        self.company_id = company_id

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def compute_revenue(
        self,
        period: str,
        transactions: List[SifTransaction],
    ) -> Tuple[RevenueRecord, RevenueRecord]:
        """
        Aggregate transactions for the given period into P1 and P2 RevenueRecords.

        Args:
            period: "YYYY-MM" — used as label on all output records
            transactions: List of SIF transactions. May contain multiple brands.
                          Rows for other periods are filtered out gracefully.

        Returns:
            (p1_record, p2_record) — one per brand
        """
        period_txns = [t for t in transactions if self._period_of(t.date) == period]

        if not period_txns:
            logger.warning(
                "RevenueEngine: no transactions found for company=%s period=%s",
                self.company_id, period
            )

        p1_txns = [t for t in period_txns if t.brand == "P1"]
        p2_txns = [t for t in period_txns if t.brand == "P2"]

        p1_record = self._aggregate_brand(period, "P1", p1_txns)
        p2_record = self._aggregate_brand(period, "P2", p2_txns)

        return p1_record, p2_record

    def compute_revenue_by_period(
        self,
        transactions: List[SifTransaction],
        periods: Optional[List[str]] = None,
    ) -> Dict[str, Tuple[RevenueRecord, RevenueRecord]]:
        """
        Compute revenue for multiple periods at once.

        Args:
            transactions: Full transaction history
            periods: If None, compute for all periods found in transactions

        Returns:
            Dict mapping period → (p1_record, p2_record)
        """
        if periods is None:
            periods = sorted(set(self._period_of(t.date) for t in transactions))

        return {
            period: self.compute_revenue(period, transactions)
            for period in periods
        }

    # ------------------------------------------------------------------
    # SKU-level realisation
    # ------------------------------------------------------------------

    def compute_sku_realisation(
        self,
        period: str,
        transactions: List[SifTransaction],
    ) -> List[RealisationRecord]:
        """
        Return per-SKU realisation records for a period.
        Used for SKU margin calculation in ebitda_engine.py.
        """
        period_txns = [t for t in transactions if self._period_of(t.date) == period]
        return self._build_sku_records(period, period_txns)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _aggregate_brand(
        self,
        period: str,
        brand: str,
        txns: List[SifTransaction],
    ) -> RevenueRecord:
        """Build a RevenueRecord from a filtered list of same-brand transactions."""
        sku_records = self._build_sku_records(period, txns)

        total_qty = sum(t.quantity_tons for t in txns)
        total_val = sum(t.value_inr for t in txns)

        if total_qty <= 0:
            blended_realisation = 0.0
        else:
            blended_realisation = total_val / total_qty

        if total_qty == 0 and len(txns) == 0:
            logger.info(
                "RevenueEngine: zero transactions for company=%s period=%s brand=%s",
                self.company_id, period, brand
            )

        return RevenueRecord(
            company_id=self.company_id,
            period=period,
            brand=brand,
            total_quantity_tons=round(total_qty, 4),
            total_value_inr=round(total_val, 2),
            blended_realisation_per_ton=round(blended_realisation, 2),
            sku_detail=sku_records,
        )

    def _build_sku_records(
        self,
        period: str,
        txns: List[SifTransaction],
    ) -> List[RealisationRecord]:
        """Aggregate transactions by SKU and compute realisation per ton."""
        # Accumulate qty and value per sku_code
        sku_qty: Dict[str, float] = defaultdict(float)
        sku_val: Dict[str, float] = defaultdict(float)
        sku_meta: Dict[str, Tuple[str, int]] = {}  # sku_code → (brand, size_mm)

        for t in txns:
            key = t.sku_code or f"{t.brand}-SKU-{t.size_mm}"
            sku_qty[key] += t.quantity_tons
            sku_val[key] += t.value_inr
            if key not in sku_meta:
                sku_meta[key] = (t.brand, t.size_mm)

        records: List[RealisationRecord] = []
        for sku_code, qty in sku_qty.items():
            val = sku_val[sku_code]
            brand, size_mm = sku_meta[sku_code]
            realisation = val / qty if qty > 0 else 0.0
            records.append(RealisationRecord(
                company_id=self.company_id,
                period=period,
                brand=brand,
                sku_code=sku_code,
                size_mm=size_mm,
                quantity_tons=round(qty, 4),
                value_inr=round(val, 2),
                realisation_per_ton=round(realisation, 2),
            ))

        # Sort by brand then size_mm for consistent output
        return sorted(records, key=lambda r: (r.brand, r.size_mm))

    @staticmethod
    def _period_of(d: date) -> str:
        """Convert a date to "YYYY-MM" period string."""
        return d.strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Convenience function (matches Session 1–4 pattern)
# ---------------------------------------------------------------------------

def compute_revenue(
    company_id: str,
    period: str,
    transactions: List[SifTransaction],
) -> Tuple[RevenueRecord, RevenueRecord]:
    """
    Module-level entry point — matches the Session 1–4 function-per-module pattern.

    Returns:
        (p1_record, p2_record)
    """
    engine = RevenueEngine(company_id=company_id)
    return engine.compute_revenue(period, transactions)
