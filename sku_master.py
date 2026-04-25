"""
sku_master.py
-------------
The SKU Master is the single source of truth for what products a client
actually manufactures.  It lives in the database (sku_master table) and
is configured once during onboarding via the Settings UI.

This module provides:
  - SKUEntry          dataclass for one SKU row
  - SKUMaster         class that holds a client's full catalogue and
                      exposes the sets the connector needs for validation
  - AC_INDUSTRIES_SKU_MASTER   pilot client config (used until DB is live)

Why this exists
---------------
The connector must validate that every row in an ERP export refers to a
product the client actually makes.  But valid sizes and brand codes differ
per client — one client may make 6mm and 40mm bars; another may have three
brands.  Hardcoding {8,10,12,16,20,25,32} would silently reject legitimate
data for any client whose catalogue differs.

The SKU Master is populated once at onboarding and updated whenever the
client adds or retires a product.  The connector reads it at runtime to
get the current valid sets.

Database table: sku_master (defined in Section 7.2 of Master Context)
Key fields used here:
    company_id, brand_id, sku_code, sku_name, size_mm, grade,
    billet_type, billet_length_m, mill_capacity_mt_hr,
    margin_rank, is_active
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SKUEntry:
    """One row from the sku_master table."""
    company_id: str
    brand_id: str           # e.g. "P1" or "P2" — matches brand_config.brand_id
    sku_code: str           # e.g. "P1-SKU-16"
    sku_name: str           # e.g. "16mm Product 1 Fe550"
    size_mm: int            # e.g. 16
    grade: str              # e.g. "Fe 550"
    billet_type: str        # e.g. "Product 1 Billet"
    billet_length_m: float  # e.g. 6.0
    mill_capacity_mt_hr: float  # e.g. 18.0
    margin_rank: int        # 1 = highest margin (used by production optimiser)
    is_active: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SKUEntry":
        return cls(
            company_id=d["company_id"],
            brand_id=d["brand_id"],
            sku_code=d["sku_code"],
            sku_name=d["sku_name"],
            size_mm=int(d["size_mm"]),
            grade=d["grade"],
            billet_type=d["billet_type"],
            billet_length_m=float(d["billet_length_m"]),
            mill_capacity_mt_hr=float(d["mill_capacity_mt_hr"]),
            margin_rank=int(d["margin_rank"]),
            is_active=bool(d.get("is_active", True)),
        )


class SKUMaster:
    """
    Holds the full SKU catalogue for one client.

    Built from:
      - a list of SKUEntry objects (loaded from DB or a config dict), or
      - SKUMaster.from_records(list_of_dicts)

    Key properties used by the connector
    -------------------------------------
    valid_sizes         → set of active size_mm integers
    valid_brand_codes   → set of active brand_id strings
    active_skus         → list of SKUEntry where is_active=True
    """

    def __init__(self, entries: list[SKUEntry]) -> None:
        self._entries: list[SKUEntry] = entries

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> "SKUMaster":
        return cls([SKUEntry.from_dict(r) for r in records])

    # ------------------------------------------------------------------
    # Connector-facing validation sets
    # ------------------------------------------------------------------

    @property
    def active_skus(self) -> list[SKUEntry]:
        return [e for e in self._entries if e.is_active]

    @property
    def valid_sizes(self) -> set[int]:
        """All active size_mm values — passed to UniversalDataConnector."""
        return {e.size_mm for e in self.active_skus}

    @property
    def valid_brand_codes(self) -> set[str]:
        """All active brand_id values — passed to UniversalDataConnector."""
        return {e.brand_id for e in self.active_skus}

    # ------------------------------------------------------------------
    # Lookup helpers (used by production optimiser in Session 4)
    # ------------------------------------------------------------------

    def get_sku(self, brand_id: str, size_mm: int) -> SKUEntry | None:
        for e in self.active_skus:
            if e.brand_id == brand_id and e.size_mm == size_mm:
                return e
        return None

    def skus_for_brand(self, brand_id: str) -> list[SKUEntry]:
        return [e for e in self.active_skus if e.brand_id == brand_id]

    def by_margin_rank(self) -> list[SKUEntry]:
        """Active SKUs sorted best margin first (lowest rank number = best)."""
        return sorted(self.active_skus, key=lambda e: e.margin_rank)

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return (
            f"SKUMaster(company={self._entries[0].company_id if self._entries else '?'}, "
            f"total={len(self._entries)}, active={len(self.active_skus)})"
        )


# ---------------------------------------------------------------------------
# AC Industries pilot SKU master
# Mirrors Section 1.3 & 1.4 of the Master Context Document.
# margin_rank and mill_capacity_mt_hr are placeholders — confirm with SME.
# ---------------------------------------------------------------------------

AC_INDUSTRIES_SKU_RECORDS: list[dict[str, Any]] = [
    # ── Product 1 ──────────────────────────────────────────────────────
    {"company_id": "AC001", "brand_id": "P1", "sku_code": "P1-SKU-8",
     "sku_name": "8mm Product 1 Fe550",   "size_mm": 8,  "grade": "Fe 550",
     "billet_type": "Product 1 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 25.0, "margin_rank": 5},

    {"company_id": "AC001", "brand_id": "P1", "sku_code": "P1-SKU-10",
     "sku_name": "10mm Product 1 Fe550",  "size_mm": 10, "grade": "Fe 550",
     "billet_type": "Product 1 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 24.0, "margin_rank": 4},

    {"company_id": "AC001", "brand_id": "P1", "sku_code": "P1-SKU-12",
     "sku_name": "12mm Product 1 Fe550",  "size_mm": 12, "grade": "Fe 550",
     "billet_type": "Product 1 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 22.0, "margin_rank": 3},

    {"company_id": "AC001", "brand_id": "P1", "sku_code": "P1-SKU-16",
     "sku_name": "16mm Product 1 Fe550",  "size_mm": 16, "grade": "Fe 550",
     "billet_type": "Product 1 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 20.0, "margin_rank": 2},

    {"company_id": "AC001", "brand_id": "P1", "sku_code": "P1-SKU-20",
     "sku_name": "20mm Product 1 Fe550",  "size_mm": 20, "grade": "Fe 550",
     "billet_type": "Product 1 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 19.0, "margin_rank": 6},

    {"company_id": "AC001", "brand_id": "P1", "sku_code": "P1-SKU-25",
     "sku_name": "25mm Product 1 Fe550",  "size_mm": 25, "grade": "Fe 550",
     "billet_type": "Product 1 Billet",   "billet_length_m": 5.6,
     "mill_capacity_mt_hr": 18.0, "margin_rank": 7},

    {"company_id": "AC001", "brand_id": "P1", "sku_code": "P1-SKU-32",
     "sku_name": "32mm Product 1 Fe550",  "size_mm": 32, "grade": "Fe 550",
     "billet_type": "Product 1 Billet",   "billet_length_m": 5.05,
     "mill_capacity_mt_hr": 18.0, "margin_rank": 8},

    # ── Product 2 ──────────────────────────────────────────────────────
    {"company_id": "AC001", "brand_id": "P2", "sku_code": "P2-SKU-8",
     "sku_name": "8mm Product 2 Fe550",   "size_mm": 8,  "grade": "Fe 550",
     "billet_type": "Product 2 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 25.0, "margin_rank": 13},

    {"company_id": "AC001", "brand_id": "P2", "sku_code": "P2-SKU-10",
     "sku_name": "10mm Product 2 Fe550",  "size_mm": 10, "grade": "Fe 550",
     "billet_type": "Product 2 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 24.0, "margin_rank": 12},

    {"company_id": "AC001", "brand_id": "P2", "sku_code": "P2-SKU-12",
     "sku_name": "12mm Product 2 Fe550",  "size_mm": 12, "grade": "Fe 550",
     "billet_type": "Product 2 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 22.0, "margin_rank": 11},

    {"company_id": "AC001", "brand_id": "P2", "sku_code": "P2-SKU-16",
     "sku_name": "16mm Product 2 Fe550",  "size_mm": 16, "grade": "Fe 550",
     "billet_type": "Product 2 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 20.0, "margin_rank": 10},

    {"company_id": "AC001", "brand_id": "P2", "sku_code": "P2-SKU-20",
     "sku_name": "20mm Product 2 Fe550",  "size_mm": 20, "grade": "Fe 550",
     "billet_type": "Product 2 Billet",   "billet_length_m": 6.0,
     "mill_capacity_mt_hr": 19.0, "margin_rank": 14},

    {"company_id": "AC001", "brand_id": "P2", "sku_code": "P2-SKU-25",
     "sku_name": "25mm Product 2 Fe550",  "size_mm": 25, "grade": "Fe 550",
     "billet_type": "Product 2 Billet",   "billet_length_m": 5.6,
     "mill_capacity_mt_hr": 18.0, "margin_rank": 15},

    {"company_id": "AC001", "brand_id": "P2", "sku_code": "P2-SKU-32",
     "sku_name": "32mm Product 2 Fe550",  "size_mm": 32, "grade": "Fe 550",
     "billet_type": "Product 2 Billet",   "billet_length_m": 4.9,
     "mill_capacity_mt_hr": 18.0, "margin_rank": 16},
]

# Convenience singleton for dev/testing
AC_INDUSTRIES_SKU_MASTER = SKUMaster.from_records(AC_INDUSTRIES_SKU_RECORDS)
