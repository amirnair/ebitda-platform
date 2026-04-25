"""
raw_material_engine.py — AC Industries EBITDA Intelligence Platform
Session 5: EBITDA Engine — Raw Material Cycle

# Phase 3 — Stub implementation only.
# The Consumables / Raw Material cycle (Scrap → Billet → TMT) is deferred
# to Phase 3 once the Revenue and Production cycles are live and validated.
# See Section 2.1 of master context: "Build sequence decision".

This module provides the correct interface so ebitda_engine.py can wire it in
without change when Phase 3 is built. All methods return zero-cost records with
is_phase3_stub=True flagged throughout.

When Phase 3 is implemented, replace the body of RawMaterialEngine.compute()
without changing the signature or the RawMaterialRecord dataclass.

Public entry point (Phase 3 stub):
    compute_raw_material_cost(company_id, period, ...) -> RawMaterialRecord
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ebitda_models import RawMaterialRecord

logger = logging.getLogger(__name__)


class RawMaterialEngine:
    """
    # Phase 3 stub.
    Accepts the interface that will be needed in Phase 3 but returns zeros.

    Phase 3 inputs (accepted but ignored until Phase 3):
        - scrap_qty_tons: Monthly scrap purchased (from raw_material table)
        - scrap_cost_per_ton_inr: Average scrap price paid (from raw_material table)
        - billet_output_tons: Billet produced from scrap (from raw_material table)
        - consumables_cost_inr: Electrode, fuel, flux consumed in induction furnace

    Phase 3 formula (to be implemented):
        yield_pct = billet_output_tons / scrap_qty_tons × 100
        raw_material_cost = scrap_qty_tons × scrap_cost_per_ton + consumables_cost
        rm_cost_per_ton = raw_material_cost / billet_output_tons
    """

    def __init__(self, company_id: str):
        self.company_id = company_id

    def compute(
        self,
        period: str,
        # Phase 3 params — accepted now so callers don't need to change signature later
        scrap_qty_tons: float = 0.0,
        scrap_cost_per_ton_inr: float = 0.0,
        billet_output_tons: float = 0.0,
        consumables_cost_inr: float = 0.0,
        **kwargs: Any,  # Forward-compat for additional Phase 3 fields
    ) -> RawMaterialRecord:
        """
        # Phase 3 stub — returns zero cost record.
        is_phase3_stub=True on the returned record signals downstream consumers
        (ebitda_engine.py, API layer) to note that RM cost is not yet live.
        """
        logger.debug(
            "RawMaterialEngine.compute: Phase 3 stub called for company=%s period=%s — "
            "returning zero RM cost record",
            self.company_id, period
        )
        return RawMaterialRecord(
            company_id=self.company_id,
            period=period,
            scrap_qty_tons=0.0,
            scrap_cost_per_ton_inr=0.0,
            billet_output_tons=0.0,
            yield_pct=0.0,
            consumables_cost_inr=0.0,
            total_raw_material_cost_inr=0.0,
            raw_material_cost_per_ton_inr=0.0,
            is_phase3_stub=True,
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def compute_raw_material_cost(
    company_id: str,
    period: str,
    **kwargs: Any,
) -> RawMaterialRecord:
    """
    # Phase 3 stub.
    Module-level entry point — returns zero RM cost record.
    Replace body of RawMaterialEngine.compute() when Phase 3 is built.
    """
    engine = RawMaterialEngine(company_id=company_id)
    return engine.compute(period=period, **kwargs)
