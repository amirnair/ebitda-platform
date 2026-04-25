"""
AC Industries EBITDA Intelligence Platform
==========================================
Session 1 — Universal Data Connector

Reads ERP exports (SAP Excel/CSV, Tally, generic CSV) and outputs
the platform's Standard Internal Format (SIF).

Multi-tenant: every output row carries company_id.
No client name / brand name is hardcoded — all mappings come from
the erp_connector_config table (or a config dict passed at runtime).

Standard Internal Format (SIF) fields
--------------------------------------
date            DATE        Billing Date
customer_id     str         Bill-to Party
brand           str (P1/P2) Division → resolved via brand_config
sku_name        str         Full SKU name (e.g. "16mm Product 1 Fe550")
size_mm         int         Derived from SKU
quantity_tons   float       Sales Volume Qty
value_inr       float       Net Value
region          str         Region
district        str         Sales District
invoice_id      str         Billing Document
company_id      str         Multi-tenant key (injected by connector)
source_file     str         Origin filename (audit trail)
ingested_at     datetime    UTC timestamp of ingestion
"""

import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Column-name normaliser
# ---------------------------------------------------------------------------

def _normalise_col(col: str) -> str:
    """Lowercase, strip, collapse internal whitespace → single space."""
    return re.sub(r"\s+", " ", str(col).strip().lower())


# ---------------------------------------------------------------------------
# Built-in SAP column map
# (mirrors Section 6.4 of the Master Context Document)
# Can be overridden entirely via erp_connector_config.column_mappings
# ---------------------------------------------------------------------------

SAP_DEFAULT_COLUMN_MAP: dict[str, str] = {
    "billing date":           "date",
    "bill-to party":          "customer_id",
    "division":               "brand_raw",        # P1 / P2 resolved later
    "product":                "sku_name",
    "sales volume qty":       "quantity_tons",
    "net value":              "value_inr",
    "region":                 "region",
    "sales district":         "district",
    "billing document":       "invoice_id",
}

# ---------------------------------------------------------------------------
# ERP-type registry — add new ERP types here without touching the rest
# ---------------------------------------------------------------------------

ERP_COLUMN_MAPS: dict[str, dict[str, str]] = {
    "SAP":     SAP_DEFAULT_COLUMN_MAP,
    "TALLY":   {},   # populated in Phase 2
    "GENERIC": {},   # passthrough — column names must already match SIF
}


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------

REQUIRED_SIF_FIELDS = [
    "date", "customer_id", "brand", "sku_name",
    "size_mm", "quantity_tons", "value_inr",
    "region", "district", "invoice_id",
]

# Size extraction pattern — e.g. "16mm Product 1 Fe550" → 16
SIZE_PATTERN = re.compile(r"(\d+)\s*mm", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Core connector class
# ---------------------------------------------------------------------------

class UniversalDataConnector:
    """
    Reads a raw ERP file (Excel or CSV) and returns a clean DataFrame
    in Standard Internal Format (SIF).

    Parameters
    ----------
    company_id : str
        Multi-tenant key — injected into every output row.
    erp_type : str
        One of SAP | TALLY | GENERIC.
    column_mappings : dict | None
        Overrides the default ERP column map.  Useful when a client's
        SAP export has localised or renamed column headers.
        Key = raw column name (case-insensitive), Value = SIF field name.
    brand_map : dict | None
        Maps raw division/brand codes in the source file to canonical
        brand codes (e.g. {"10": "P1", "20": "P2"}).
        Defaults to identity mapping (assumes source already says P1/P2).
    valid_sizes : set[int] | None
        Set of valid size_mm values for this client, loaded from their
        sku_master.  If None, size validation is SKIPPED (permissive mode —
        use only during initial onboarding data upload).
        Example: {8, 10, 12, 16, 20, 25, 32}
    valid_brand_codes : set[str] | None
        Set of valid canonical brand codes for this client, loaded from
        their brand_config.  If None, brand validation is SKIPPED.
        Example: {"P1", "P2"}
    sheet_name : str | int
        Excel sheet to read.  Default = 0 (first sheet).
    header_row : int
        0-based row index of the column header row.  Default = 0.
    """

    def __init__(
        self,
        company_id: str,
        erp_type: str = "SAP",
        column_mappings: dict[str, str] | None = None,
        brand_map: dict[str, str] | None = None,
        valid_sizes: set | None = None,
        valid_brand_codes: set | None = None,
        sheet_name: str | int = 0,
        header_row: int = 0,
    ) -> None:
        self.company_id = company_id
        self.erp_type = erp_type.upper()
        self.sheet_name = sheet_name
        self.header_row = header_row

        # Build the effective column map: default ERP map overridden by
        # any client-specific mappings supplied at runtime
        base_map = ERP_COLUMN_MAPS.get(self.erp_type, {}).copy()
        if column_mappings:
            base_map.update(
                {_normalise_col(k): v for k, v in column_mappings.items()}
            )
        self._col_map: dict[str, str] = {
            _normalise_col(k): v for k, v in base_map.items()
        }

        # Brand code resolver: raw value → canonical brand codes
        self._brand_map: dict[str, str] = brand_map or {}

        # Validation sets — populated from sku_master / brand_config at runtime.
        # None = permissive (skip that check); use during onboarding only.
        self._valid_sizes: set | None = valid_sizes
        self._valid_brand_codes: set | None = valid_brand_codes

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def load(self, filepath: str | Path) -> pd.DataFrame:
        """
        Read, validate, and clean an ERP export file.

        Returns
        -------
        pd.DataFrame
            Clean SIF DataFrame.  Raises ConnectorError on fatal issues.
        """
        filepath = Path(filepath)
        logger.info("Loading %s for company=%s erp_type=%s",
                    filepath.name, self.company_id, self.erp_type)

        raw = self._read_file(filepath)
        mapped = self._apply_column_map(raw)
        cleaned = self._clean_and_cast(mapped)
        validated = self._validate(cleaned)
        enriched = self._enrich(validated, source_file=filepath.name)

        logger.info(
            "Loaded %d rows from %s (%d rejected)",
            len(enriched), filepath.name, len(raw) - len(enriched)
        )
        return enriched

    # ------------------------------------------------------------------
    # Step 1 — Read raw file
    # ------------------------------------------------------------------

    def _read_file(self, filepath: Path) -> pd.DataFrame:
        suffix = filepath.suffix.lower()
        try:
            if suffix in (".xlsx", ".xls", ".xlsm"):
                df = pd.read_excel(
                    filepath,
                    sheet_name=self.sheet_name,
                    header=self.header_row,
                    dtype=str,          # read everything as str; cast later
                )
            elif suffix in (".csv", ".txt"):
                df = pd.read_csv(
                    filepath,
                    header=self.header_row,
                    dtype=str,
                    encoding="utf-8-sig",   # handles BOM from SAP exports
                )
            else:
                raise ConnectorError(
                    f"Unsupported file format: {suffix}. "
                    "Accepted: .xlsx, .xls, .xlsm, .csv"
                )
        except Exception as exc:
            raise ConnectorError(f"Cannot read file {filepath.name}: {exc}") from exc

        if df.empty:
            raise ConnectorError(f"File {filepath.name} is empty.")

        # Drop completely blank rows
        df.dropna(how="all", inplace=True)
        return df

    # ------------------------------------------------------------------
    # Step 2 — Rename source columns → SIF names
    # ------------------------------------------------------------------

    def _apply_column_map(self, df: pd.DataFrame) -> pd.DataFrame:
        rename: dict[str, str] = {}
        unmapped: list[str] = []

        for col in df.columns:
            norm = _normalise_col(col)
            if norm in self._col_map:
                rename[col] = self._col_map[norm]
            else:
                unmapped.append(col)

        if unmapped:
            logger.debug("Columns not in map (will be dropped): %s", unmapped)

        df = df.rename(columns=rename)
        # Keep only columns that are recognised SIF fields + brand_raw
        keep = set(REQUIRED_SIF_FIELDS) | {"brand_raw"}
        present = [c for c in df.columns if c in keep]
        return df[present].copy()

    # ------------------------------------------------------------------
    # Step 3 — Clean, cast, derive fields
    # ------------------------------------------------------------------

    def _clean_and_cast(self, df: pd.DataFrame) -> pd.DataFrame:
        # --- date ---
        if "date" in df.columns:
            df["date"] = pd.to_datetime(
                df["date"], dayfirst=True, errors="coerce"
            ).dt.date
        else:
            raise ConnectorError("Column 'date' (Billing Date) is missing.")

        # --- numeric ---
        for num_col in ("quantity_tons", "value_inr"):
            if num_col in df.columns:
                df[num_col] = (
                    df[num_col]
                    .astype(str)
                    .str.replace(",", "", regex=False)   # remove thousands sep
                    .str.strip()
                )
                df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
            else:
                raise ConnectorError(f"Required column '{num_col}' is missing.")

        # --- string columns: strip whitespace ---
        for str_col in ("customer_id", "sku_name", "region", "district", "invoice_id"):
            if str_col in df.columns:
                df[str_col] = df[str_col].astype(str).str.strip()
                df[str_col] = df[str_col].replace(
                    {"nan": None, "": None, "NaN": None}
                )

        # --- brand resolution ---
        if "brand_raw" in df.columns:
            df["brand"] = df["brand_raw"].astype(str).str.strip().apply(
                lambda v: self._brand_map.get(v, v)  # use map if provided; else keep
            )
            df.drop(columns=["brand_raw"], inplace=True)
        elif "brand" not in df.columns:
            raise ConnectorError(
                "Neither 'brand' nor a mappable division column is present."
            )

        # --- size_mm: extract integer from sku_name ---
        if "sku_name" in df.columns:
            df["size_mm"] = df["sku_name"].apply(_extract_size_mm)

        return df

    # ------------------------------------------------------------------
    # Step 4 — Validate; segregate good vs bad rows
    # ------------------------------------------------------------------

    def _validate(self, df: pd.DataFrame) -> pd.DataFrame:
        issues: pd.Series = pd.Series(False, index=df.index)
        issue_reasons: pd.Series = pd.Series("", index=df.index)

        # Null checks on required fields
        for field in REQUIRED_SIF_FIELDS:
            if field not in df.columns:
                raise ConnectorError(
                    f"SIF field '{field}' is missing after mapping. "
                    "Check your column_mappings config."
                )
            null_mask = df[field].isna()
            issues |= null_mask
            issue_reasons[null_mask] += f"null:{field} "

        # Numeric sanity
        neg_qty = df["quantity_tons"] < 0
        neg_val = df["value_inr"] < 0
        issues |= neg_qty | neg_val
        issue_reasons[neg_qty] += "negative:quantity_tons "
        issue_reasons[neg_val] += "negative:value_inr "

        # Brand code validity — only checked when brand_config is loaded
        if self._valid_brand_codes is not None:
            invalid_brand = ~df["brand"].isin(self._valid_brand_codes)
            issues |= invalid_brand
            issue_reasons[invalid_brand] += "invalid:brand "
        else:
            logger.debug("Brand validation skipped — valid_brand_codes not provided.")

        # size_mm validity — only checked when sku_master is loaded
        if self._valid_sizes is not None:
            invalid_size = ~df["size_mm"].isin(self._valid_sizes)
            issues |= invalid_size
            issue_reasons[invalid_size] += "invalid:size_mm "
        else:
            logger.debug("Size validation skipped — valid_sizes not provided.")

        bad = df[issues].copy()
        bad["_rejection_reason"] = issue_reasons[issues].str.strip()
        good = df[~issues].copy()

        if not bad.empty:
            logger.warning(
                "%d rows rejected:\n%s",
                len(bad),
                bad[["invoice_id", "_rejection_reason"]].to_string(index=False),
            )
            # Store rejected rows as an attribute for caller inspection
            self.rejected_rows = bad
        else:
            self.rejected_rows = pd.DataFrame()

        if good.empty:
            raise ConnectorError(
                "All rows failed validation. Check column mappings and source data."
            )

        return good

    # ------------------------------------------------------------------
    # Step 5 — Add audit / tenant fields
    # ------------------------------------------------------------------

    def _enrich(self, df: pd.DataFrame, source_file: str) -> pd.DataFrame:
        df = df.copy()
        df["company_id"] = self.company_id
        df["source_file"] = source_file
        df["ingested_at"] = datetime.now(timezone.utc).replace(microsecond=0)

        # Enforce column order matching SIF spec
        sif_order = [
            "date", "customer_id", "brand", "sku_name", "size_mm",
            "quantity_tons", "value_inr", "region", "district",
            "invoice_id", "company_id", "source_file", "ingested_at",
        ]
        return df[sif_order]


# ---------------------------------------------------------------------------
# Helper — extract size integer from SKU name string
# ---------------------------------------------------------------------------

def _extract_size_mm(sku_name: str | None) -> int | None:
    if not sku_name:
        return None
    match = SIZE_PATTERN.search(str(sku_name))
    if match:
        return int(match.group(1))
    return None


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ConnectorError(Exception):
    """Raised when the connector cannot produce valid SIF output."""
