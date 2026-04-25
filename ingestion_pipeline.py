"""
ingestion_pipeline.py
---------------------
High-level pipeline that:
  1. Loads the connector config for a company
  2. Instantiates the UniversalDataConnector
  3. Reads and validates the uploaded file
  4. Writes clean rows to the sales_transactions table (or returns
     the DataFrame when running headless / in tests)
  5. Logs rejected rows to a separate audit file / table

Usage (CLI):
    python ingestion_pipeline.py --company AC001 --file sales_apr25.xlsx

Usage (as module):
    from connector.ingestion_pipeline import run_ingestion
    result = run_ingestion(company_id="AC001", filepath="sales.xlsx")
    print(result.summary())
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from connector.connector_config import AC_INDUSTRIES_CONFIG, ConnectorConfig
from connector.sku_master import AC_INDUSTRIES_SKU_MASTER, SKUMaster
from connector.universal_connector import ConnectorError, UniversalDataConnector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result object
# ---------------------------------------------------------------------------

@dataclass
class IngestionResult:
    company_id: str
    source_file: str
    rows_ingested: int
    rows_rejected: int
    rejected_df: pd.DataFrame
    clean_df: pd.DataFrame

    def summary(self) -> str:
        return (
            f"[{self.company_id}] {self.source_file} — "
            f"{self.rows_ingested} rows ingested, "
            f"{self.rows_rejected} rows rejected"
        )

    @property
    def success(self) -> bool:
        return self.rows_ingested > 0


# ---------------------------------------------------------------------------
# Config registry (replace with DB lookup in production)
# ---------------------------------------------------------------------------

CONFIG_REGISTRY: dict[str, dict] = {
    "AC001": AC_INDUSTRIES_CONFIG,
    # "CLIENT002": CLIENT002_CONFIG,  ← add new clients here
}

# SKU master registry — in production, loaded from DB at startup
SKU_MASTER_REGISTRY: dict[str, SKUMaster] = {
    "AC001": AC_INDUSTRIES_SKU_MASTER,
}


def _load_config(company_id: str) -> ConnectorConfig:
    """
    Dev: loads from CONFIG_REGISTRY + SKU_MASTER_REGISTRY.
    Prod: swap for DB queries on erp_connector_config + sku_master tables.
    """
    raw = CONFIG_REGISTRY.get(company_id)
    if raw is None:
        raise ConnectorError(
            f"No ERP connector config found for company_id='{company_id}'. "
            "Check CONFIG_REGISTRY or the erp_connector_config table."
        )
    cfg = ConnectorConfig.from_dict(raw)

    # Inject validation sets from sku_master
    sku_master = SKU_MASTER_REGISTRY.get(company_id)
    if sku_master is not None:
        cfg.valid_sizes = sku_master.valid_sizes
        cfg.valid_brand_codes = sku_master.valid_brand_codes
    else:
        logger.warning(
            "No SKU master found for company_id='%s'. "
            "Size and brand validation will be skipped (permissive mode). "
            "Configure the SKU master in Settings before going live.",
            company_id,
        )

    return cfg


# ---------------------------------------------------------------------------
# Main pipeline function
# ---------------------------------------------------------------------------

def run_ingestion(
    company_id: str,
    filepath: str | Path,
    write_to_db: bool = False,
    db_engine=None,
) -> IngestionResult:
    """
    Run the full ingestion pipeline for one file.

    Parameters
    ----------
    company_id  : Client identifier — must exist in config registry / DB
    filepath    : Path to the ERP export file (Excel or CSV)
    write_to_db : If True, appends clean rows to sales_transactions via
                  SQLAlchemy engine (pass db_engine too)
    db_engine   : SQLAlchemy engine (required when write_to_db=True)
    """
    filepath = Path(filepath)
    cfg = _load_config(company_id)

    connector = UniversalDataConnector(
        company_id=cfg.company_id,
        erp_type=cfg.erp_type,
        column_mappings=cfg.column_mappings,
        brand_map=cfg.brand_map,
        valid_sizes=cfg.valid_sizes,
        valid_brand_codes=cfg.valid_brand_codes,
        sheet_name=cfg.sheet_name,
        header_row=cfg.header_row,
    )

    try:
        clean_df = connector.load(filepath)
    except ConnectorError as exc:
        logger.error("Ingestion failed: %s", exc)
        raise

    rejected_df = connector.rejected_rows
    result = IngestionResult(
        company_id=company_id,
        source_file=filepath.name,
        rows_ingested=len(clean_df),
        rows_rejected=len(rejected_df),
        rejected_df=rejected_df,
        clean_df=clean_df,
    )

    logger.info(result.summary())

    if write_to_db and db_engine is not None:
        _write_to_db(clean_df, db_engine)
        if not rejected_df.empty:
            _write_rejected_to_db(rejected_df, company_id, filepath.name, db_engine)

    return result


# ---------------------------------------------------------------------------
# DB write helpers (stubs — wired up in Session 7/Database session)
# ---------------------------------------------------------------------------

def _write_to_db(df: pd.DataFrame, engine) -> None:
    """Append clean SIF rows to sales_transactions."""
    df.to_sql(
        "sales_transactions",
        con=engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )
    logger.info("Wrote %d rows to sales_transactions", len(df))


def _write_rejected_to_db(
    df: pd.DataFrame, company_id: str, source_file: str, engine
) -> None:
    """Log rejected rows to ingestion_errors for audit."""
    df = df.copy()
    df["company_id"] = company_id
    df["source_file"] = source_file
    df.to_sql(
        "ingestion_errors",
        con=engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )
    logger.warning("Logged %d rejected rows to ingestion_errors", len(df))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run the EBITDA Platform Universal Data Connector"
    )
    p.add_argument("--company", required=True, help="Company ID (e.g. AC001)")
    p.add_argument("--file", required=True, help="Path to ERP export file")
    p.add_argument("--db", default=None, help="SQLAlchemy DB URL (optional)")
    p.add_argument("--output", default=None, help="Save clean CSV to this path")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    engine = None
    if args.db:
        from sqlalchemy import create_engine
        engine = create_engine(args.db)

    try:
        result = run_ingestion(
            company_id=args.company,
            filepath=args.file,
            write_to_db=engine is not None,
            db_engine=engine,
        )
    except ConnectorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(result.summary())

    if args.output:
        result.clean_df.to_csv(args.output, index=False)
        print(f"Clean data saved to {args.output}")

    if not result.rejected_df.empty:
        print("\nRejected rows:")
        print(result.rejected_df[["invoice_id", "_rejection_reason"]].to_string(index=False))

    sys.exit(0 if result.success else 1)
