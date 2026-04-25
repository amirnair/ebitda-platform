"""
test_forecasting.py
-------------------
Test suite for Session 3: Forecasting Engine.
Follows the pattern from Sessions 1 & 2 (test_connector.py, test_aggregation.py).

Coverage:
  - Synthetic data generator (shape, proportions, seasonal patterns)
  - SKU proportion model (disaggregation accuracy, edge cases)
  - Statistical models (ES, Holt-Winters, SARIMA fallback)
  - ML models (feature engineering, walk-forward forecast)
  - Ensemble (weight computation, blending)
  - Model selection logic (regional split, Holt-Winters fallback)
  - ForecastBundle and CompanyForecastResult serialisation
  - API contract (response structure validation)
  - External variables interface (stub behaviour)
  - Edge cases (sparse data, zero values, single month)
"""

from __future__ import annotations

import sys
import os
import math
import pytest
from datetime import date, timedelta
from typing import List

import numpy as np

# Add module paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "forecaster"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from forecaster.synthetic_data import (
    generate_synthetic_sales,
    build_monthly_brand_series,
    aggregate_to_monthly,
    SKU_PROPORTIONS,
)
from forecaster.forecast_models import (
    ForecastPoint, ModelPerformance, ModelSelectionResult,
    ForecastBundle, CompanyForecastResult,
    ForecastGranularity, ModelName, Region, ExternalVariables,
)
from forecaster.sku_proportion_model import (
    disaggregate_monthly_to_weekly,
    disaggregate_monthly_to_daily,
    compute_sku_proportions_from_actuals,
    get_business_days_in_month,
    STATIC_SKU_PROPORTIONS,
    DOW_INDEX,
)
from forecaster.forecasting_engine import (
    ForecastingEngine,
    SimpleExponentialSmoothing,
    DoubleExponentialSmoothing,
    HoltWintersModel,
    SARIMAModel,
    MLForecaster,
    LSTMForecaster,
    compute_ensemble_weights,
    blend_forecasts,
    get_primary_model_for_region,
    mape, mae, rmse,
    build_ml_features,
    compute_confidence_interval,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synthetic_rows():
    """Generate a standard synthetic dataset once per module."""
    return generate_synthetic_sales(
        company_id="AC001",
        start_date=date(2023, 1, 1),
        end_date=date(2025, 3, 31),
        random_seed=42,
    )


@pytest.fixture(scope="module")
def p1_chennai_series(synthetic_rows):
    dates, values = build_monthly_brand_series(synthetic_rows, "P1", "Chennai")
    return dates, values


@pytest.fixture(scope="module")
def p1_outside_series(synthetic_rows):
    dates, values = build_monthly_brand_series(synthetic_rows, "P1", "Outside Chennai")
    return dates, values


@pytest.fixture(scope="module")
def p2_chennai_series(synthetic_rows):
    dates, values = build_monthly_brand_series(synthetic_rows, "P2", "Chennai")
    return dates, values


@pytest.fixture
def short_series():
    """18 months — triggers Holt-Winters fallback."""
    return np.array([100 + 10 * math.sin(2 * math.pi * i / 12) + i * 0.5
                     for i in range(18)])


@pytest.fixture
def long_series():
    """36 months — enables SARIMA."""
    return np.array([200 + 20 * math.sin(2 * math.pi * i / 12) + i * 0.8
                     for i in range(36)])


@pytest.fixture
def engine():
    return ForecastingEngine(forecast_horizon=6)  # shorter horizon for tests


# ---------------------------------------------------------------------------
# 1. Synthetic Data Tests
# ---------------------------------------------------------------------------

class TestSyntheticData:

    def test_generates_rows(self, synthetic_rows):
        assert len(synthetic_rows) > 1000, "Expected >1000 daily rows"

    def test_no_sunday_sales(self, synthetic_rows):
        """Sundays must have zero sales (§4.6 holiday calendar)."""
        sunday_rows = [r for r in synthetic_rows if r.date.weekday() == 6]
        assert len(sunday_rows) == 0, "Found Sunday sales rows — must be excluded"

    def test_company_id_injected(self, synthetic_rows):
        assert all(r.company_id == "AC001" for r in synthetic_rows)

    def test_brand_values(self, synthetic_rows):
        brands = {r.brand for r in synthetic_rows}
        assert brands == {"P1", "P2"}

    def test_region_is_tamil_nadu(self, synthetic_rows):
        assert all(r.region == "Tamil Nadu" for r in synthetic_rows)

    def test_positive_quantities(self, synthetic_rows):
        assert all(r.quantity_tons > 0 for r in synthetic_rows)

    def test_positive_values(self, synthetic_rows):
        assert all(r.value_inr > 0 for r in synthetic_rows)

    def test_sku_proportions_sum_to_1(self):
        total = sum(SKU_PROPORTIONS.values())
        assert abs(total - 1.0) < 1e-9

    def test_p1_has_higher_volume_than_p2(self, synthetic_rows):
        """P1 is growth brand — should dominate volume."""
        p1_vol = sum(r.quantity_tons for r in synthetic_rows if r.brand == "P1")
        p2_vol = sum(r.quantity_tons for r in synthetic_rows if r.brand == "P2")
        assert p1_vol > p2_vol * 1.5, f"P1 ({p1_vol:.0f}) should be >>P2 ({p2_vol:.0f})"

    def test_monthly_series_has_correct_length(self, p1_chennai_series):
        dates, values = p1_chennai_series
        # Jan 2023 – Mar 2025 = 27 months
        assert 24 <= len(dates) <= 30

    def test_seasonal_pattern_visible(self, p1_chennai_series):
        """Feb should be higher than Aug (peak vs trough seasons)."""
        dates, values = p1_chennai_series
        monthly: dict = {}
        for d, v in zip(dates, values):
            monthly[d.month] = monthly.get(d.month, [])
            monthly[d.month].append(v)
        feb_avg = sum(monthly.get(2, [0])) / max(1, len(monthly.get(2, [1])))
        aug_avg = sum(monthly.get(8, [0])) / max(1, len(monthly.get(8, [1])))
        assert feb_avg > aug_avg, f"Feb ({feb_avg:.0f}) should exceed Aug ({aug_avg:.0f})"

    def test_outside_chennai_has_more_p1(self, p1_chennai_series, p1_outside_series):
        _, chennai_vals = p1_chennai_series
        _, outside_vals = p1_outside_series
        assert sum(outside_vals) > sum(chennai_vals), \
            "Outside Chennai should have higher P1 volume (65% split vs 35%)"

    def test_reproducible_with_same_seed(self):
        rows1 = generate_synthetic_sales(random_seed=99)
        rows2 = generate_synthetic_sales(random_seed=99)
        assert rows1[0].quantity_tons == rows2[0].quantity_tons

    def test_different_seeds_give_different_data(self):
        rows1 = generate_synthetic_sales(random_seed=1)
        rows2 = generate_synthetic_sales(random_seed=2)
        assert rows1[0].quantity_tons != rows2[0].quantity_tons


# ---------------------------------------------------------------------------
# 2. SKU Proportion Model Tests
# ---------------------------------------------------------------------------

class TestSkuProportionModel:

    def test_static_proportions_sum_to_1_per_brand(self):
        for brand in ("P1", "P2"):
            total = sum(v for (b, _), v in STATIC_SKU_PROPORTIONS.items() if b == brand)
            assert abs(total - 1.0) < 1e-9, f"{brand} proportions don't sum to 1"

    def test_dow_index_sunday_is_zero(self):
        assert DOW_INDEX[6] == 0.0

    def test_business_days_exclude_sundays(self):
        days = get_business_days_in_month(2024, 1)
        assert all(d.weekday() != 6 for d in days)

    def test_business_days_count_reasonable(self):
        # January 2024: 31 days, 5 Sundays → 26 business days
        days = get_business_days_in_month(2024, 1)
        assert 24 <= len(days) <= 27

    def test_weekly_disagg_volumes_sum_to_monthly(self):
        weekly = disaggregate_monthly_to_weekly(
            year=2024, month=3, brand="P1",
            region="Chennai", monthly_qty_tons=1000.0,
        )
        total = sum(w.qty_tons for w in weekly)
        assert abs(total - 1000.0) < 1.0, f"Weekly sum {total:.2f} ≠ 1000"

    def test_weekly_disagg_all_positive(self):
        weekly = disaggregate_monthly_to_weekly(
            year=2024, month=6, brand="P2",
            region="Outside Chennai", monthly_qty_tons=500.0,
        )
        assert all(w.qty_tons >= 0 for w in weekly)

    def test_weekly_disagg_covers_all_skus(self):
        weekly = disaggregate_monthly_to_weekly(
            year=2024, month=1, brand="P1",
            region="Chennai", monthly_qty_tons=800.0,
        )
        sizes = {w.size_mm for w in weekly}
        assert {8, 10, 12, 16, 20, 25, 32}.issubset(sizes)

    def test_daily_disagg_volumes_sum_to_monthly(self):
        daily = disaggregate_monthly_to_daily(
            year=2024, month=2, brand="P1",
            region="Chennai", monthly_qty_tons=1200.0,
        )
        total = sum(d.qty_tons for d in daily)
        assert abs(total - 1200.0) < 2.0, f"Daily sum {total:.2f} ≠ 1200"

    def test_daily_disagg_no_sundays(self):
        daily = disaggregate_monthly_to_daily(
            year=2024, month=4, brand="P2",
            region="Outside Chennai", monthly_qty_tons=600.0,
        )
        assert all(d.date.weekday() != 6 for d in daily)

    def test_daily_disagg_respects_holidays(self):
        holiday = date(2024, 5, 1)  # Labour Day
        daily = disaggregate_monthly_to_daily(
            year=2024, month=5, brand="P1",
            region="Chennai", monthly_qty_tons=800.0,
            holiday_dates=[holiday],
        )
        assert not any(d.date == holiday for d in daily)

    def test_proportion_blending(self):
        actuals = {("P1", 10): 0.30, ("P1", 16): 0.25}
        blended = compute_sku_proportions_from_actuals(actuals, smoothing=0.3)
        # Should be between static prior and actual
        assert ("P1", 10) in blended
        total_p1 = sum(v for (b, _), v in blended.items() if b == "P1")
        assert abs(total_p1 - 1.0) < 1e-9

    def test_proportion_blending_none_returns_static(self):
        result = compute_sku_proportions_from_actuals(None)
        assert result == STATIC_SKU_PROPORTIONS


# ---------------------------------------------------------------------------
# 3. Statistical Model Tests
# ---------------------------------------------------------------------------

class TestStatisticalModels:

    def test_simple_es_forecast_length(self, long_series):
        model = SimpleExponentialSmoothing().fit(long_series)
        fc = model.forecast(12)
        assert len(fc) == 12

    def test_simple_es_positive_forecast(self, long_series):
        model = SimpleExponentialSmoothing().fit(long_series)
        fc = model.forecast(12)
        assert all(f >= 0 for f in fc)

    def test_simple_es_constant_forecast(self, long_series):
        """Simple ES forecasts a flat line (last smoothed level)."""
        model = SimpleExponentialSmoothing().fit(long_series)
        fc = model.forecast(12)
        assert all(abs(fc[i] - fc[0]) < 1e-10 for i in range(len(fc)))

    def test_double_es_handles_trend(self, long_series):
        """Gradient series should produce non-constant forecast."""
        trend_series = np.arange(1, 37, dtype=float)
        model = DoubleExponentialSmoothing().fit(trend_series)
        fc = model.forecast(6)
        assert fc[-1] > fc[0], "Upward trend should yield increasing forecast"

    def test_double_es_forecast_length(self, long_series):
        model = DoubleExponentialSmoothing().fit(long_series)
        fc = model.forecast(6)
        assert len(fc) == 6

    def test_holt_winters_seasonal_pattern(self):
        """HW should produce seasonal variation over 12-month horizon."""
        seasonal = np.array([
            100 + 30 * math.sin(2 * math.pi * i / 12)
            for i in range(36)
        ])
        model = HoltWintersModel(seasonal_periods=12).fit(seasonal)
        fc = model.forecast(12)
        assert len(fc) == 12
        # Should have variation (not flat)
        assert np.std(fc) > 1.0, "HW forecast should show seasonal variation"

    def test_holt_winters_positive_output(self, long_series):
        model = HoltWintersModel().fit(long_series)
        fc = model.forecast(12)
        assert all(f >= 0 for f in fc)

    def test_sarima_forecast_length(self, long_series):
        model = SARIMAModel().fit(long_series)
        fc = model.forecast(12)
        assert len(fc) == 12

    def test_sarima_positive_forecast(self, long_series):
        model = SARIMAModel().fit(long_series)
        fc = model.forecast(12)
        assert all(f >= 0 for f in fc)

    def test_sarima_confidence_interval(self, long_series):
        model = SARIMAModel().fit(long_series)
        point, low, high = model.forecast_with_ci(6)
        assert len(point) == len(low) == len(high) == 6
        assert all(lo <= pt for lo, pt in zip(low, point)), "CI lower must be ≤ point"
        assert all(pt <= hi for pt, hi in zip(point, high)), "Point must be ≤ CI upper"

    def test_sarima_residuals_shape(self, long_series):
        model = SARIMAModel().fit(long_series)
        res = model.residuals(long_series)
        assert len(res) == len(long_series)

    def test_short_series_holt_winters_fallback(self, short_series):
        """<24 months should trigger Holt-Winters, not SARIMA error."""
        model = SARIMAModel().fit(short_series)
        fc = model.forecast(6)
        assert len(fc) == 6  # Should not crash


# ---------------------------------------------------------------------------
# 4. ML Model Tests
# ---------------------------------------------------------------------------

class TestMLModels:

    def test_build_ml_features_shape(self, long_series):
        X, y = build_ml_features(long_series, n_lags=12)
        assert X.shape[0] == len(long_series) - 12
        assert y.shape[0] == len(long_series) - 12
        assert X.shape[1] > 12  # lag features + derived features

    def test_random_forest_forecast(self, long_series):
        model = MLForecaster(ModelName.RANDOM_FOREST).fit(long_series)
        fc = model.forecast(6)
        assert len(fc) == 6
        assert all(f >= 0 for f in fc)

    def test_gradient_boost_forecast(self, long_series):
        model = MLForecaster(ModelName.GRADIENT_BOOST).fit(long_series)
        fc = model.forecast(6)
        assert len(fc) == 6

    def test_ridge_forecast(self, long_series):
        model = MLForecaster(ModelName.RIDGE).fit(long_series)
        fc = model.forecast(6)
        assert len(fc) == 6

    def test_lasso_forecast(self, long_series):
        model = MLForecaster(ModelName.LASSO).fit(long_series)
        fc = model.forecast(6)
        assert len(fc) == 6

    def test_svr_forecast(self, long_series):
        model = MLForecaster(ModelName.SVR).fit(long_series)
        fc = model.forecast(6)
        assert len(fc) == 6

    def test_xgboost_forecast(self, long_series):
        """XGBoost (or GradientBoosting substitute) must produce output."""
        model = MLForecaster(ModelName.XGBOOST).fit(long_series)
        fc = model.forecast(6)
        assert len(fc) == 6
        assert all(f >= 0 for f in fc)

    def test_lstm_forecast(self, long_series):
        """LSTM (or GradientBoosting substitute) must produce output."""
        model = LSTMForecaster().fit(long_series)
        fc = model.forecast(6)
        assert len(fc) == 6

    def test_ml_residuals_shape(self, long_series):
        model = MLForecaster(ModelName.RANDOM_FOREST).fit(long_series)
        res = model.residuals(long_series)
        assert len(res) == len(long_series)

    def test_ml_handles_short_series(self, short_series):
        """ML models should not crash on short series."""
        model = MLForecaster(ModelName.RANDOM_FOREST).fit(short_series)
        fc = model.forecast(3)
        assert len(fc) == 3


# ---------------------------------------------------------------------------
# 5. Accuracy Metrics Tests
# ---------------------------------------------------------------------------

class TestAccuracyMetrics:

    def test_mape_perfect_forecast(self):
        a = np.array([100.0, 200.0, 300.0])
        assert mape(a, a) == 0.0

    def test_mape_known_error(self):
        actual = np.array([100.0])
        pred   = np.array([90.0])
        assert abs(mape(actual, pred) - 10.0) < 1e-9

    def test_mape_handles_zeros(self):
        actual = np.array([0.0, 100.0, 200.0])
        pred   = np.array([0.0, 90.0, 190.0])
        result = mape(actual, pred)
        assert math.isfinite(result)

    def test_mae_calculation(self):
        a = np.array([100.0, 200.0])
        p = np.array([90.0, 210.0])
        assert abs(mae(a, p) - 10.0) < 1e-9

    def test_rmse_calculation(self):
        a = np.array([100.0, 200.0])
        p = np.array([90.0, 210.0])  # errors: -10, 10 → rmse = 10
        assert abs(rmse(a, p) - 10.0) < 1e-9

    def test_confidence_interval_structure(self):
        residuals = np.random.normal(0, 10, 100)
        forecast  = np.full(12, 100.0)
        low, high = compute_confidence_interval(residuals, forecast)
        assert len(low) == len(high) == 12
        assert all(low[i] <= forecast[i] for i in range(12))
        assert all(forecast[i] <= high[i] for i in range(12))

    def test_confidence_interval_widens_with_horizon(self):
        """Uncertainty should grow over time."""
        residuals = np.random.normal(0, 10, 100)
        forecast  = np.full(12, 100.0)
        low, high = compute_confidence_interval(residuals, forecast)
        widths = [high[i] - low[i] for i in range(12)]
        assert widths[-1] > widths[0], "CI should widen with forecast horizon"


# ---------------------------------------------------------------------------
# 6. Ensemble Tests
# ---------------------------------------------------------------------------

class TestEnsemble:

    def test_weights_sum_to_1(self):
        perf = {
            ModelName.SARIMA:          5.0,
            ModelName.RANDOM_FOREST:   8.0,
            ModelName.HOLT_WINTERS:    7.0,
        }
        weights = compute_ensemble_weights(perf)
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_lower_mape_gets_higher_weight(self):
        perf = {
            ModelName.SARIMA:       3.0,   # best
            ModelName.RANDOM_FOREST: 10.0, # worst
        }
        weights = compute_ensemble_weights(perf)
        assert weights[ModelName.SARIMA] > weights[ModelName.RANDOM_FOREST]

    def test_blend_forecasts_weighted_average(self):
        fc = {
            ModelName.SARIMA:        np.full(3, 100.0),
            ModelName.RANDOM_FOREST: np.full(3, 200.0),
        }
        weights = {ModelName.SARIMA: 0.5, ModelName.RANDOM_FOREST: 0.5}
        blended = blend_forecasts(fc, weights)
        assert all(abs(b - 150.0) < 1e-9 for b in blended)

    def test_blend_handles_equal_weights(self):
        fc = {ModelName.SARIMA: np.full(6, 100.0),
              ModelName.HOLT_WINTERS: np.full(6, 100.0)}
        weights = {ModelName.SARIMA: 0.5, ModelName.HOLT_WINTERS: 0.5}
        blended = blend_forecasts(fc, weights)
        assert all(abs(b - 100.0) < 1e-9 for b in blended)

    def test_blend_output_non_negative(self):
        fc = {ModelName.RIDGE: np.full(6, -5.0)}
        weights = {ModelName.RIDGE: 1.0}
        blended = blend_forecasts(fc, weights)
        assert all(b >= 0 for b in blended)

    def test_infinite_mape_gets_zero_weight(self):
        perf = {
            ModelName.SARIMA: float("inf"),
            ModelName.RANDOM_FOREST: 5.0,
        }
        weights = compute_ensemble_weights(perf)
        assert weights[ModelName.SARIMA] == 0.0
        assert weights[ModelName.RANDOM_FOREST] == 1.0

    def test_all_infinite_mape_equal_weights(self):
        perf = {
            ModelName.SARIMA: float("inf"),
            ModelName.RANDOM_FOREST: float("inf"),
        }
        weights = compute_ensemble_weights(perf)
        assert abs(weights[ModelName.SARIMA] - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# 7. Regional Model Selection Tests (§3.4)
# ---------------------------------------------------------------------------

class TestRegionalModelSelection:

    def test_chennai_p1_gets_sarima(self):
        model = get_primary_model_for_region("P1", Region.CHENNAI, use_sarimax=False)
        assert model == ModelName.SARIMA

    def test_chennai_p1_gets_sarimax_when_enabled(self):
        model = get_primary_model_for_region("P1", Region.CHENNAI, use_sarimax=True)
        assert model == ModelName.SARIMAX

    def test_chennai_p2_gets_xgboost(self):
        model = get_primary_model_for_region("P2", Region.CHENNAI)
        assert model == ModelName.XGBOOST

    def test_outside_chennai_p1_gets_xgboost(self):
        model = get_primary_model_for_region("P1", Region.OUTSIDE_CHENNAI)
        assert model == ModelName.XGBOOST

    def test_outside_chennai_p2_gets_xgboost(self):
        model = get_primary_model_for_region("P2", Region.OUTSIDE_CHENNAI)
        assert model == ModelName.XGBOOST


# ---------------------------------------------------------------------------
# 8. Full Engine Integration Tests
# ---------------------------------------------------------------------------

class TestForecastingEngine:

    def test_run_forecast_returns_bundle(self, engine, p1_chennai_series):
        dates, values = p1_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001",
            brand="P1",
            region=Region.CHENNAI,
            series_dates=dates,
            series_values=values,
        )
        assert isinstance(bundle, ForecastBundle)
        assert bundle.company_id == "AC001"
        assert bundle.brand == "P1"
        assert bundle.region == Region.CHENNAI

    def test_ensemble_forecast_has_correct_horizon(self, engine, p1_chennai_series):
        dates, values = p1_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001",
            brand="P1",
            region=Region.CHENNAI,
            series_dates=dates,
            series_values=values,
        )
        assert len(bundle.ensemble_forecast) == engine.forecast_horizon

    def test_all_models_produce_monthly_points(self, engine, p1_chennai_series):
        dates, values = p1_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001",
            brand="P1",
            region=Region.CHENNAI,
            series_dates=dates,
            series_values=values,
        )
        model_names_in_output = {fp.model_name for fp in bundle.monthly_forecasts}
        # At minimum, statistical + core ML models should be present
        assert ModelName.SARIMA in model_names_in_output or \
               ModelName.HOLT_WINTERS in model_names_in_output

    def test_weekly_disagg_covers_all_skus(self, engine, p1_chennai_series):
        dates, values = p1_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001",
            brand="P1",
            region=Region.CHENNAI,
            series_dates=dates,
            series_values=values,
        )
        sizes = {fp.sku_name for fp in bundle.weekly_disagg if fp.sku_name}
        assert len(sizes) >= 7, f"Expected ≥7 P1 SKU sizes, got {sizes}"

    def test_forecast_quantities_positive(self, engine, p1_chennai_series):
        dates, values = p1_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001",
            brand="P1",
            region=Region.CHENNAI,
            series_dates=dates,
            series_values=values,
        )
        assert all(fp.qty_forecast >= 0 for fp in bundle.ensemble_forecast)

    def test_model_performances_recorded(self, engine, p1_chennai_series):
        dates, values = p1_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001",
            brand="P1",
            region=Region.CHENNAI,
            series_dates=dates,
            series_values=values,
        )
        assert len(bundle.model_performances) >= 5

    def test_model_selection_recorded(self, engine, p1_chennai_series):
        dates, values = p1_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001",
            brand="P1",
            region=Region.CHENNAI,
            series_dates=dates,
            series_values=values,
        )
        sel = bundle.model_selection
        assert sel.company_id == "AC001"
        assert sel.history_months > 0
        assert isinstance(sel.baseline_mape, float)

    def test_short_series_triggers_warning(self, engine):
        short_dates = [date(2024, m, 1) for m in range(1, 8)]
        short_values = [100.0 + i * 5 for i in range(7)]
        bundle = engine.run_forecast(
            company_id="AC001",
            brand="P1",
            region=Region.CHENNAI,
            series_dates=short_dates,
            series_values=short_values,
        )
        assert len(bundle.warnings) > 0

    def test_p2_chennai_uses_xgboost_primary(self, engine, p2_chennai_series):
        dates, values = p2_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001",
            brand="P2",
            region=Region.CHENNAI,
            series_dates=dates,
            series_values=values,
        )
        # XGBoost (or substitute) should be in the output models
        model_names = {fp.model_name for fp in bundle.monthly_forecasts}
        assert ModelName.XGBOOST in model_names or ModelName.GRADIENT_BOOST in model_names

    def test_company_forecast_runs_all_combinations(self, p1_chennai_series, p1_outside_series, p2_chennai_series):
        engine = ForecastingEngine(forecast_horizon=3)
        d1, v1 = p1_chennai_series
        d2, v2 = p1_outside_series
        d3, v3 = p2_chennai_series

        series_map = {
            ("P1", "Chennai"):         (d1, v1),
            ("P1", "Outside Chennai"): (d2, v2),
            ("P2", "Chennai"):         (d3, v3),
        }
        result = engine.run_company_forecast("AC001", series_map)
        assert isinstance(result, CompanyForecastResult)
        assert len(result.bundles) == 3
        assert len(result.errors) == 0


# ---------------------------------------------------------------------------
# 9. Data Model / Serialisation Tests
# ---------------------------------------------------------------------------

class TestDataModels:

    def test_forecast_point_to_dict(self):
        fp = ForecastPoint(
            company_id="AC001",
            model_name=ModelName.SARIMA,
            forecast_date=date(2025, 4, 1),
            period=date(2025, 5, 1),
            granularity=ForecastGranularity.MONTHLY,
            brand="P1",
            sku_name=None,
            region=Region.CHENNAI,
            qty_forecast=1234.56,
            confidence_low=1100.0,
            confidence_high=1370.0,
        )
        d = fp.to_dict()
        assert d["model_name"] == "sarima"
        assert d["granularity"] == "monthly"
        assert d["region"] == "Chennai"
        assert d["qty_forecast"] == 1234.56
        assert isinstance(d["forecast_date"], str)

    def test_external_variables_has_data_false(self):
        ev = ExternalVariables()
        assert not ev.has_data()

    def test_external_variables_has_data_true(self):
        ev = ExternalVariables(gst_collections_cr={"2025-01": 180000.0})
        assert ev.has_data()

    def test_external_variables_regressor_matrix_none_when_empty(self):
        ev = ExternalVariables()
        result = ev.to_regressor_matrix(["2025-01", "2025-02"])
        assert result is None

    def test_external_variables_regressor_matrix_shape(self):
        ev = ExternalVariables(
            gst_collections_cr={"2025-01": 180000.0, "2025-02": 185000.0},
            iip_steel_index={"2025-01": 140.5, "2025-02": 142.1},
        )
        matrix = ev.to_regressor_matrix(["2025-01", "2025-02"])
        assert matrix is not None
        assert len(matrix) == 2    # 2 periods
        assert len(matrix[0]) == 2  # 2 variables

    def test_model_performance_to_dict(self):
        mp = ModelPerformance(
            company_id="AC001",
            model_name=ModelName.RANDOM_FOREST,
            eval_month=date(2025, 4, 1),
            brand="P1",
            region=Region.OUTSIDE_CHENNAI,
            mape=4.2,
            mae=52.3,
            rmse=68.1,
            weight=0.15,
            n_periods=3,
        )
        d = mp.to_dict()
        assert d["model_name"] == "random_forest"
        assert d["region"] == "Outside Chennai"

    def test_company_forecast_result_to_dict_structure(self, engine, p1_chennai_series):
        dates, values = p1_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001", brand="P1",
            region=Region.CHENNAI,
            series_dates=dates, series_values=values,
        )
        result = CompanyForecastResult(
            company_id="AC001",
            forecast_date=date.today(),
            bundles=[bundle],
        )
        d = result.to_dict()
        assert "company_id" in d
        assert "bundles" in d
        assert isinstance(d["bundles"], list)
        assert "ensemble_forecast" in d["bundles"][0]


# ---------------------------------------------------------------------------
# 10. Edge Case Tests
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_all_zero_series_handled(self, engine):
        dates = [date(2023, m, 1) for m in range(1, 25)]
        values = [0.0] * 24
        # Should not crash, may warn
        bundle = engine.run_forecast(
            company_id="AC001", brand="P1",
            region=Region.CHENNAI,
            series_dates=dates, series_values=values,
        )
        assert bundle is not None

    def test_single_outlier_handled(self, engine, long_series):
        series_with_spike = long_series.copy()
        series_with_spike[15] = long_series[15] * 10  # spike
        dates = [date(2022, 1 + i % 12, 1) for i in range(len(series_with_spike))]
        bundle = engine.run_forecast(
            company_id="AC001", brand="P1",
            region=Region.OUTSIDE_CHENNAI,
            series_dates=dates,
            series_values=list(series_with_spike),
        )
        assert bundle is not None

    def test_company_forecast_with_empty_series_map(self, engine):
        result = engine.run_company_forecast("AC001", {})
        assert isinstance(result, CompanyForecastResult)
        assert len(result.bundles) == 0

    def test_forecast_point_non_negative_clamp(self, engine, p1_chennai_series):
        """Ensemble output must never be negative."""
        dates, values = p1_chennai_series
        bundle = engine.run_forecast(
            company_id="AC001", brand="P1",
            region=Region.CHENNAI,
            series_dates=dates, series_values=values,
        )
        for fp in bundle.ensemble_forecast:
            assert fp.qty_forecast >= 0, f"Negative forecast: {fp.qty_forecast}"

    def test_weekly_disagg_for_zero_monthly(self):
        weekly = disaggregate_monthly_to_weekly(
            year=2024, month=8, brand="P1",
            region="Chennai", monthly_qty_tons=0.0,
        )
        assert all(w.qty_tons == 0.0 for w in weekly)

    def test_mape_all_zeros_actual(self):
        a = np.array([0.0, 0.0, 0.0])
        p = np.array([1.0, 2.0, 3.0])
        result = mape(a, p)
        assert math.isinf(result) or math.isnan(result) or result >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
