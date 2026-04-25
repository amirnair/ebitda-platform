"""
tests/test_connector.py
-----------------------
Tests for the Universal Data Connector (Session 1).

Run with:  pytest tests/test_connector.py -v
"""

import io
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from connector.connector_config import AC_INDUSTRIES_CONFIG, ConnectorConfig
from connector.sku_master import AC_INDUSTRIES_SKU_MASTER, SKUMaster
from connector.universal_connector import (
    ConnectorError,
    UniversalDataConnector,
    _extract_size_mm,
)
from connector.ingestion_pipeline import run_ingestion


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

SAP_COLUMNS = [
    "Billing Date", "Bill-to Party", "Division", "Product",
    "Sales Volume Qty", "Net Value", "Region", "Sales District",
    "Billing Document",
]

BRAND_MAP = {"10": "P1", "20": "P2"}
AC_VALID_SIZES = AC_INDUSTRIES_SKU_MASTER.valid_sizes
AC_VALID_BRANDS = AC_INDUSTRIES_SKU_MASTER.valid_brand_codes


def _make_connector(**kwargs) -> UniversalDataConnector:
    defaults = dict(
        company_id="AC001",
        erp_type="SAP",
        column_mappings=AC_INDUSTRIES_CONFIG["column_mappings"],
        brand_map=BRAND_MAP,
        valid_sizes=AC_VALID_SIZES,
        valid_brand_codes=AC_VALID_BRANDS,
        sheet_name=0,
        header_row=0,
    )
    defaults.update(kwargs)
    return UniversalDataConnector(**defaults)


def _sap_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal SAP-like DataFrame from a list of row dicts."""
    return pd.DataFrame(rows, columns=SAP_COLUMNS)


def _df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Raw Data") -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf.getvalue()


def _write_tmp_excel(df: pd.DataFrame, tmp_path: Path, name: str = "test.xlsx") -> Path:
    p = tmp_path / name
    df.to_excel(p, index=False, sheet_name="Raw Data")
    return p


GOOD_ROW = {
    "Billing Date":     "01-04-2025",
    "Bill-to Party":    "CUST00133",
    "Division":         "10",
    "Product":          "16mm Product 1 Fe550",
    "Sales Volume Qty": "2.49",
    "Net Value":        "134335.55",
    "Region":           "Tamil Nadu",
    "Sales District":   "Chennai",
    "Billing Document": "90000006",
}

GOOD_ROW_P2 = {**GOOD_ROW, "Division": "20", "Product": "12mm Product 2 Fe550",
               "Billing Document": "90000007"}


# ===========================================================================
# 1. Column mapping
# ===========================================================================

class TestColumnMapping:

    def test_sap_columns_mapped_correctly(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path)
        conn = _make_connector(sheet_name="Raw Data")
        result = conn.load(p)
        assert set(result.columns) >= {
            "date", "customer_id", "brand", "sku_name", "size_mm",
            "quantity_tons", "value_inr", "region", "district", "invoice_id"
        }

    def test_extra_columns_are_dropped(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        df["Some Extra SAP Column"] = "junk"
        p = _write_tmp_excel(df, tmp_path)
        conn = _make_connector(sheet_name="Raw Data")
        result = conn.load(p)
        assert "Some Extra SAP Column" not in result.columns

    def test_case_insensitive_column_names(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        df.columns = [c.lower() for c in df.columns]   # lowercase all headers
        p = _write_tmp_excel(df, tmp_path)
        conn = _make_connector(sheet_name="Raw Data")
        result = conn.load(p)
        assert "date" in result.columns

    def test_custom_override_column_map(self, tmp_path):
        """Client with renamed SAP headers."""
        df = pd.DataFrame([{
            "TRX Date":    "01-04-2025",
            "Customer":    "CUST00133",
            "Brand Code":  "P1",
            "Item":        "16mm Product 1 Fe550",
            "Qty (MT)":    "2.49",
            "Amount":      "134335.55",
            "State":       "Tamil Nadu",
            "City":        "Chennai",
            "Invoice No":  "90000099",
        }])
        p = tmp_path / "custom.xlsx"
        df.to_excel(p, index=False, sheet_name="Sheet1")
        custom_map = {
            "TRX Date":   "date",
            "Customer":   "customer_id",
            "Brand Code": "brand_raw",
            "Item":       "sku_name",
            "Qty (MT)":   "quantity_tons",
            "Amount":     "value_inr",
            "State":      "region",
            "City":       "district",
            "Invoice No": "invoice_id",
        }
        conn = UniversalDataConnector(
            company_id="AC001", erp_type="GENERIC",
            column_mappings=custom_map, brand_map={},
            sheet_name="Sheet1",
        )
        result = conn.load(p)
        assert len(result) == 1
        assert result.iloc[0]["brand"] == "P1"


# ===========================================================================
# 2. Data cleaning & type casting
# ===========================================================================

class TestDataCleaning:

    def test_date_parsed_correctly(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        assert result.iloc[0]["date"] == date(2025, 4, 1)

    def test_numeric_thousands_separator_removed(self, tmp_path):
        row = {**GOOD_ROW, "Sales Volume Qty": "1,500.00", "Net Value": "80,000,000.00"}
        df = _sap_df([row])
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        assert result.iloc[0]["quantity_tons"] == pytest.approx(1500.0)
        assert result.iloc[0]["value_inr"] == pytest.approx(80_000_000.0)

    def test_brand_mapped_from_division_code(self, tmp_path):
        df = _sap_df([GOOD_ROW, GOOD_ROW_P2])
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        assert set(result["brand"]) == {"P1", "P2"}

    def test_size_extracted_from_sku_name(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        assert result.iloc[0]["size_mm"] == 16

    def test_whitespace_stripped_from_strings(self, tmp_path):
        row = {**GOOD_ROW, "Bill-to Party": "  CUST00133  ", "Region": " Tamil Nadu "}
        df = _sap_df([row])
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        assert result.iloc[0]["customer_id"] == "CUST00133"
        assert result.iloc[0]["region"] == "Tamil Nadu"

    def test_bom_in_csv_handled(self, tmp_path):
        """SAP CSV exports sometimes include a UTF-8 BOM."""
        csv_content = "\ufeffBilling Date,Bill-to Party,Division,Product,Sales Volume Qty,Net Value,Region,Sales District,Billing Document\n01-04-2025,CUST00133,10,16mm Product 1 Fe550,2.49,134335.55,Tamil Nadu,Chennai,90000006\n"
        p = tmp_path / "sap_bom.csv"
        p.write_bytes(csv_content.encode("utf-8-sig"))
        result = _make_connector(sheet_name=0).load(p)
        assert len(result) == 1


# ===========================================================================
# 3. Validation — good data passes
# ===========================================================================

class TestValidationPass:

    def test_good_rows_all_pass(self, tmp_path):
        df = _sap_df([GOOD_ROW, GOOD_ROW_P2])
        p = _write_tmp_excel(df, tmp_path)
        conn = _make_connector(sheet_name="Raw Data")
        result = conn.load(p)
        assert len(result) == 2
        assert len(conn.rejected_rows) == 0

    def test_all_tmts_sizes_accepted(self, tmp_path):
        rows = []
        for size in [8, 10, 12, 16, 20, 25, 32]:
            rows.append({**GOOD_ROW,
                         "Product": f"{size}mm Product 1 Fe550",
                         "Billing Document": f"INV{size}"})
        df = _sap_df(rows)
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        assert len(result) == 7


# ===========================================================================
# 4. Validation — bad rows rejected
# ===========================================================================

class TestValidationReject:

    def _load_single_bad(self, bad_row: dict, tmp_path: Path) -> tuple:
        df = _sap_df([GOOD_ROW, bad_row])
        p = _write_tmp_excel(df, tmp_path)
        conn = _make_connector(sheet_name="Raw Data")
        result = conn.load(p)
        return result, conn.rejected_rows

    def test_null_date_rejected(self, tmp_path):
        row = {**GOOD_ROW, "Billing Date": None, "Billing Document": "BAD001"}
        good, bad = self._load_single_bad(row, tmp_path)
        assert len(good) == 1
        assert len(bad) == 1
        assert "null:date" in bad.iloc[0]["_rejection_reason"]

    def test_null_quantity_rejected(self, tmp_path):
        row = {**GOOD_ROW, "Sales Volume Qty": None, "Billing Document": "BAD002"}
        good, bad = self._load_single_bad(row, tmp_path)
        assert len(bad) == 1

    def test_negative_quantity_rejected(self, tmp_path):
        row = {**GOOD_ROW, "Sales Volume Qty": "-5.0", "Billing Document": "BAD003"}
        good, bad = self._load_single_bad(row, tmp_path)
        assert len(bad) == 1
        assert "negative:quantity_tons" in bad.iloc[0]["_rejection_reason"]

    def test_invalid_brand_code_rejected(self, tmp_path):
        row = {**GOOD_ROW, "Division": "99", "Billing Document": "BAD004"}
        good, bad = self._load_single_bad(row, tmp_path)
        assert len(bad) == 1
        assert "invalid:brand" in bad.iloc[0]["_rejection_reason"]

    def test_unknown_size_rejected(self, tmp_path):
        row = {**GOOD_ROW, "Product": "14mm Product 1 Fe550", "Billing Document": "BAD005"}
        good, bad = self._load_single_bad(row, tmp_path)
        assert len(bad) == 1
        assert "invalid:size_mm" in bad.iloc[0]["_rejection_reason"]

    def test_all_bad_rows_raises(self, tmp_path):
        row = {**GOOD_ROW, "Billing Date": None, "Sales Volume Qty": None,
               "Net Value": None, "Billing Document": "BAD006"}
        df = _sap_df([row])
        p = _write_tmp_excel(df, tmp_path)
        conn = _make_connector(sheet_name="Raw Data")
        with pytest.raises(ConnectorError, match="All rows failed"):
            conn.load(p)


# ===========================================================================
# 5. SIF output correctness
# ===========================================================================

class TestSIFOutput:

    def test_company_id_injected(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        assert result.iloc[0]["company_id"] == "AC001"

    def test_source_file_injected(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path, name="april_sales.xlsx")
        result = _make_connector(sheet_name="Raw Data").load(p)
        assert result.iloc[0]["source_file"] == "april_sales.xlsx"

    def test_ingested_at_is_utc_datetime(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        ts = result.iloc[0]["ingested_at"]
        assert isinstance(ts, datetime)
        assert ts.tzinfo is not None   # UTC-aware

    def test_column_order_matches_sif_spec(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        expected_first_cols = [
            "date", "customer_id", "brand", "sku_name", "size_mm",
            "quantity_tons", "value_inr", "region", "district", "invoice_id"
        ]
        assert list(result.columns[:10]) == expected_first_cols

    def test_realisation_derivable(self, tmp_path):
        """Open question in Master Context: realisation = value / qty."""
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path)
        result = _make_connector(sheet_name="Raw Data").load(p)
        row = result.iloc[0]
        realisation = row["value_inr"] / row["quantity_tons"]
        assert realisation == pytest.approx(134335.55 / 2.49, rel=1e-4)


# ===========================================================================
# 5b. SKU Master — dynamic validation sets
# ===========================================================================

class TestSKUMaster:

    def test_ac_industries_valid_sizes(self):
        assert AC_INDUSTRIES_SKU_MASTER.valid_sizes == {8, 10, 12, 16, 20, 25, 32}

    def test_ac_industries_valid_brands(self):
        assert AC_INDUSTRIES_SKU_MASTER.valid_brand_codes == {"P1", "P2"}

    def test_custom_client_different_sizes(self):
        """A client making 6mm and 40mm bars works without any code changes."""
        records = [
            {"company_id": "C2", "brand_id": "B1", "sku_code": "B1-6",
             "sku_name": "6mm Brand1 Fe500", "size_mm": 6, "grade": "Fe 500",
             "billet_type": "B1 Billet", "billet_length_m": 6.0,
             "mill_capacity_mt_hr": 28.0, "margin_rank": 1},
            {"company_id": "C2", "brand_id": "B1", "sku_code": "B1-40",
             "sku_name": "40mm Brand1 Fe500", "size_mm": 40, "grade": "Fe 500",
             "billet_type": "B1 Billet", "billet_length_m": 5.0,
             "mill_capacity_mt_hr": 16.0, "margin_rank": 2},
        ]
        master = SKUMaster.from_records(records)
        assert master.valid_sizes == {6, 40}
        assert master.valid_brand_codes == {"B1"}

    def test_three_brand_client(self):
        """A client with 3 brands has all three in valid_brand_codes."""
        records = [
            {"company_id": "C3", "brand_id": "PREMIUM", "sku_code": "PR-16",
             "sku_name": "16mm Premium Fe550D", "size_mm": 16, "grade": "Fe 550D",
             "billet_type": "Premium Billet", "billet_length_m": 6.0,
             "mill_capacity_mt_hr": 20.0, "margin_rank": 1},
            {"company_id": "C3", "brand_id": "STANDARD", "sku_code": "ST-16",
             "sku_name": "16mm Standard Fe500", "size_mm": 16, "grade": "Fe 500",
             "billet_type": "Standard Billet", "billet_length_m": 6.0,
             "mill_capacity_mt_hr": 20.0, "margin_rank": 2},
            {"company_id": "C3", "brand_id": "ECONOMY", "sku_code": "EC-12",
             "sku_name": "12mm Economy Fe415", "size_mm": 12, "grade": "Fe 415",
             "billet_type": "Economy Billet", "billet_length_m": 6.0,
             "mill_capacity_mt_hr": 22.0, "margin_rank": 3},
        ]
        master = SKUMaster.from_records(records)
        assert master.valid_brand_codes == {"PREMIUM", "STANDARD", "ECONOMY"}

    def test_inactive_sku_excluded_from_validation(self):
        """Retired SKUs (is_active=False) must not appear in valid_sizes."""
        records = [
            {"company_id": "AC001", "brand_id": "P1", "sku_code": "P1-SKU-16",
             "sku_name": "16mm Product 1 Fe550", "size_mm": 16, "grade": "Fe 550",
             "billet_type": "P1 Billet", "billet_length_m": 6.0,
             "mill_capacity_mt_hr": 20.0, "margin_rank": 1, "is_active": True},
            {"company_id": "AC001", "brand_id": "P1", "sku_code": "P1-SKU-36",
             "sku_name": "36mm Product 1 Fe550", "size_mm": 36, "grade": "Fe 550",
             "billet_type": "P1 Billet", "billet_length_m": 4.8,
             "mill_capacity_mt_hr": 16.0, "margin_rank": 9, "is_active": False},
        ]
        master = SKUMaster.from_records(records)
        assert 36 not in master.valid_sizes
        assert 16 in master.valid_sizes

    def test_custom_sizes_accepted_by_connector(self, tmp_path):
        """A 6mm SKU from a custom-catalogue client passes validation."""
        records = [
            {"company_id": "C2", "brand_id": "P1", "sku_code": "P1-6",
             "sku_name": "6mm Brand Fe500", "size_mm": 6, "grade": "Fe 500",
             "billet_type": "Billet", "billet_length_m": 6.0,
             "mill_capacity_mt_hr": 28.0, "margin_rank": 1},
        ]
        master = SKUMaster.from_records(records)
        row = {**GOOD_ROW, "Product": "6mm Brand Fe500"}
        df = _sap_df([row])
        p = _write_tmp_excel(df, tmp_path)
        conn = UniversalDataConnector(
            company_id="C2", erp_type="SAP",
            column_mappings=AC_INDUSTRIES_CONFIG["column_mappings"],
            brand_map={"10": "P1"},
            valid_sizes=master.valid_sizes,
            valid_brand_codes=master.valid_brand_codes,
            sheet_name=0,
        )
        result = conn.load(p)
        assert len(result) == 1
        assert result.iloc[0]["size_mm"] == 6

    def test_permissive_mode_skips_size_validation(self, tmp_path):
        """valid_sizes=None → size check skipped (onboarding mode)."""
        row = {**GOOD_ROW, "Product": "14mm Product 1 Fe550"}
        df = _sap_df([row])
        p = _write_tmp_excel(df, tmp_path)
        conn = _make_connector(valid_sizes=None, sheet_name=0)
        result = conn.load(p)
        assert len(result) == 1

    def test_permissive_mode_skips_brand_validation(self, tmp_path):
        """valid_brand_codes=None → brand check skipped (onboarding mode)."""
        row = {**GOOD_ROW, "Division": "99"}
        df = _sap_df([row])
        p = _write_tmp_excel(df, tmp_path)
        conn = _make_connector(valid_brand_codes=None, sheet_name=0)
        result = conn.load(p)
        assert len(result) == 1


# ===========================================================================
# 6. Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / "empty.xlsx"
        pd.DataFrame().to_excel(p, index=False)
        conn = _make_connector(sheet_name=0)
        with pytest.raises(ConnectorError):
            conn.load(p)

    def test_unsupported_format_raises(self, tmp_path):
        p = tmp_path / "file.pdf"
        p.write_bytes(b"%PDF-1.4 fake")
        conn = _make_connector(sheet_name=0)
        with pytest.raises(ConnectorError, match="Unsupported file format"):
            conn.load(p)

    def test_csv_input_works(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = tmp_path / "sap_export.csv"
        df.to_csv(p, index=False)
        result = _make_connector(sheet_name=0).load(p)
        assert len(result) == 1

    def test_large_file_performance(self, tmp_path):
        """10 000 rows should process in reasonable time (no explicit timer,
        but verifies no O(n²) path by completing without hanging)."""
        base_rows = [GOOD_ROW.copy() for _ in range(10_000)]
        for i, r in enumerate(base_rows):
            r["Billing Document"] = f"INV{i:06d}"
        df = _sap_df(base_rows)
        p = _write_tmp_excel(df, tmp_path, name="large.xlsx")
        result = _make_connector(sheet_name="Raw Data").load(p)
        assert len(result) == 10_000


# ===========================================================================
# 7. _extract_size_mm unit tests
# ===========================================================================

class TestExtractSizeMm:

    @pytest.mark.parametrize("sku,expected", [
        ("16mm Product 1 Fe550", 16),
        ("8mm Product 2 Fe550",  8),
        ("25 MM VIKI TMT",       25),
        ("32mm",                 32),
        ("no size here",         None),
        (None,                   None),
        ("",                     None),
    ])
    def test_extraction(self, sku, expected):
        assert _extract_size_mm(sku) == expected


# ===========================================================================
# 8. Ingestion pipeline integration
# ===========================================================================

class TestIngestionPipeline:

    def test_pipeline_returns_result(self, tmp_path):
        df = _sap_df([GOOD_ROW, GOOD_ROW_P2])
        p = _write_tmp_excel(df, tmp_path, name="Raw Data.xlsx")
        result = run_ingestion(company_id="AC001", filepath=p)
        assert result.success
        assert result.rows_ingested == 2
        assert result.rows_rejected == 0

    def test_pipeline_summary_string(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path)
        result = run_ingestion(company_id="AC001", filepath=p)
        summary = result.summary()
        assert "AC001" in summary
        assert "1 rows ingested" in summary

    def test_pipeline_unknown_company_raises(self, tmp_path):
        df = _sap_df([GOOD_ROW])
        p = _write_tmp_excel(df, tmp_path)
        with pytest.raises(ConnectorError, match="No ERP connector config"):
            run_ingestion(company_id="UNKNOWN999", filepath=p)

    def test_pipeline_rejects_tracked_separately(self, tmp_path):
        bad_row = {**GOOD_ROW, "Sales Volume Qty": None, "Billing Document": "BAD_INV"}
        df = _sap_df([GOOD_ROW, bad_row])
        p = _write_tmp_excel(df, tmp_path)
        result = run_ingestion(company_id="AC001", filepath=p)
        assert result.rows_ingested == 1
        assert result.rows_rejected == 1
        assert "BAD_INV" in result.rejected_df["invoice_id"].values
