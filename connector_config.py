"""
connector_config.py
-------------------
Loads ERP connector configuration for a given company from either:
  (a) a live Supabase / PostgreSQL database, or
  (b) a plain Python dict (for local dev / testing without a DB).

The config drives the UniversalDataConnector — column mappings,
ERP type, brand map, etc. — so that no client-specific detail is
ever hardcoded in the connector itself.

Config dict shape (mirrors the erp_connector_config DB table):
{
    "company_id":       "AC001",
    "erp_type":         "SAP",
    "connection_method":"excel_export",
    "file_format":      "xlsx",
    "sheet_name":       "Raw Data",
    "header_row":       0,
    "column_mappings": {
        "Billing Date":       "date",
        "Bill-to Party":      "customer_id",
        "Division":           "brand_raw",
        "Product":            "sku_name",
        "Sales Volume Qty":   "quantity_tons",
        "Net Value":          "value_inr",
        "Region":             "region",
        "Sales District":     "district",
        "Billing Document":   "invoice_id"
    },
    "brand_map": {
        "10": "P1",
        "20": "P2"
    }
}
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConnectorConfig:
    company_id: str
    erp_type: str = "SAP"
    connection_method: str = "excel_export"
    file_format: str = "xlsx"
    sheet_name: str | int = 0
    header_row: int = 0
    column_mappings: dict[str, str] = field(default_factory=dict)
    brand_map: dict[str, str] = field(default_factory=dict)
    # Populated from sku_master at pipeline startup — None = permissive mode
    valid_sizes: set | None = None
    valid_brand_codes: set | None = None

    @classmethod
    def from_dict(cls, cfg: dict[str, Any]) -> "ConnectorConfig":
        return cls(
            company_id=cfg["company_id"],
            erp_type=cfg.get("erp_type", "SAP"),
            connection_method=cfg.get("connection_method", "excel_export"),
            file_format=cfg.get("file_format", "xlsx"),
            sheet_name=cfg.get("sheet_name", 0),
            header_row=cfg.get("header_row", 0),
            column_mappings=cfg.get("column_mappings", {}),
            brand_map=cfg.get("brand_map", {}),
            # valid_sizes / valid_brand_codes injected separately from sku_master
        )

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "ConnectorConfig":
        """
        Parse a row from the erp_connector_config PostgreSQL table.
        column_mappings is stored as JSONB → may arrive as str or dict.
        """
        col_map = row.get("column_mappings", {})
        if isinstance(col_map, str):
            col_map = json.loads(col_map)

        brand_map = row.get("brand_map", {})
        if isinstance(brand_map, str):
            brand_map = json.loads(brand_map)

        return cls(
            company_id=row["company_id"],
            erp_type=row.get("erp_type", "SAP"),
            connection_method=row.get("connection_method", "excel_export"),
            file_format=row.get("file_format", "xlsx"),
            sheet_name=row.get("sheet_name", 0),
            header_row=int(row.get("header_row", 0)),
            column_mappings=col_map,
            brand_map=brand_map,
            # valid_sizes / valid_brand_codes injected separately from sku_master
        )


# ---------------------------------------------------------------------------
# AC Industries pilot config (used until DB is live)
# ---------------------------------------------------------------------------

AC_INDUSTRIES_CONFIG: dict[str, Any] = {
    "company_id": "AC001",
    "erp_type": "SAP",
    "connection_method": "excel_export",
    "file_format": "xlsx",
    "sheet_name": "Raw Data",
    "header_row": 0,
    "column_mappings": {
        # SAP export column name  →  SIF field
        "Billing Date":       "date",
        "Bill-to Party":      "customer_id",
        "Division":           "brand_raw",
        "Product":            "sku_name",
        "Sales Volume Qty":   "quantity_tons",
        "Net Value":          "value_inr",
        "Region":             "region",
        "Sales District":     "district",
        "Billing Document":   "invoice_id",
    },
    # Division codes in SAP → canonical brand codes
    # Adjust to match actual SAP division codes for this client
    "brand_map": {
        "10": "P1",
        "20": "P2",
        # If SAP already exports "P1"/"P2" leave brand_map empty {}
    },
}
