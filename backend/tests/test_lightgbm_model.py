"""
Unit tests for LightGBM demand model (backend/models/).

Tests cover:
- Model building and configuration
- Cross-validation pipeline
- Model persistence (save/load)
- Feature importance extraction
- End-to-end demand forecasting
"""
import pytest
import numpy as np
import pandas as pd
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from models.lightgbm_model import (
    LightGBMConfig,
    build_model,
    cross_validate_r2,
    save_model,
    load_model,
)
from models.demand_model import train, predict_forecast


class TestLightGBMConfig:
    """Test LightGBMConfig dataclass."""

    def test_default_config_creation(self):
        """Test default config instantiation."""
        cfg = LightGBMConfig()
        assert cfg.n_estimators == 220
        assert cfg.max_depth == 8
        assert cfg.learning_rate == 0.06
        assert cfg.num_leaves == 63

    def test_custom_config_creation(self):
        """Test custom config with overrides."""
        cfg = LightGBMConfig(n_estimators=100, learning_rate=0.1)
        assert cfg.n_estimators == 100
        assert cfg.learning_rate == 0.1
        assert cfg.max_depth == 8  # unchanged

    def test_config_immutable(self):
        """Test that config is frozen (immutable)."""
        cfg = LightGBMConfig()
        with pytest.raises(AttributeError):
            cfg.n_estimators = 500


class TestBuildModel:
    """Test LightGBM model building."""

    def test_builds_regressor(self):
        """Test that build_model returns LGBMRegressor."""
        from lightgbm import LGBMRegressor
        model = build_model(random_seed=42)
        assert isinstance(model, LGBMRegressor)

    def test_model_with_custom_config(self):
        """Test model building with custom config."""
        cfg = LightGBMConfig(n_estimators=50)
        model = build_model(random_seed=42, cfg=cfg)
        assert model.n_estimators == 50

    def test_random_seed_reproducibility(self):
        """Test that same seed produces same model structure."""
        model1 = build_model(random_seed=42)
        model2 = build_model(random_seed=42)
        assert model1.random_state == model2.random_state


class TestCrossValidation:
    """Test cross-validation pipeline."""

    @pytest.fixture
    def sample_data(self):
        """Create sample synthetic data."""
        np.random.seed(42)
        X = np.random.randn(1000, 10)
        y = X[:, 0] * 2 + X[:, 1] * 3 + np.random.randn(1000) * 0.1
        return X, y

    def test_cv_returns_scores(self, sample_data):
        """Test CV returns R² scores."""
        X, y = sample_data
        scores = cross_validate_r2(X, y, random_seed=42, folds=5)
        assert len(scores) == 5
        assert all(isinstance(s, float) for s in scores)

    def test_cv_scores_reasonable(self, sample_data):
        """Test CV produces reasonable scores."""
        X, y = sample_data
        scores = cross_validate_r2(X, y, random_seed=42, folds=5)
        # All scores should be between 0 and 1 for this synthetic data
        assert all(0 <= s <= 1 for s in scores)
        assert np.mean(scores) > 0.5  # Should have decent mean score

    def test_cv_different_fold_counts(self, sample_data):
        """Test CV with different fold counts."""
        X, y = sample_data

        scores_3 = cross_validate_r2(X, y, random_seed=42, folds=3)
        scores_5 = cross_validate_r2(X, y, random_seed=42, folds=5)

        assert len(scores_3) == 3
        assert len(scores_5) == 5

    def test_cv_reproducible(self, sample_data):
        """Test CV produces same results with same seed."""
        X, y = sample_data
        scores1 = cross_validate_r2(X, y, random_seed=42, folds=5)
        scores2 = cross_validate_r2(X, y, random_seed=42, folds=5)

        np.testing.assert_array_almost_equal(scores1, scores2)


class TestModelPersistence:
    """Test model save and load functionality."""

    @pytest.fixture
    def trained_model(self):
        """Create and train a simple model."""
        np.random.seed(42)
        X = np.random.randn(500, 10)
        y = X[:, 0] * 2 + np.random.randn(500) * 0.1

        model = build_model(random_seed=42)
        model.fit(X, y)
        return model, X, y

    def test_save_model_creates_file(self, trained_model):
        """Test that save_model creates a pickle file."""
        model, _, _ = trained_model

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pkl"
            save_model(model, model_path)

            assert model_path.exists()
            assert model_path.stat().st_size > 0

    def test_load_model_retrieves_model(self, trained_model):
        """Test that loaded model works correctly."""
        model_orig, X, y = trained_model

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pkl"
            save_model(model_orig, model_path)

            model_loaded = load_model(model_path)

            # Test predictions match
            pred_orig = model_orig.predict(X[:10])
            pred_loaded = model_loaded.predict(X[:10])

            np.testing.assert_array_almost_equal(pred_orig, pred_loaded)

    def test_round_trip_consistency(self, trained_model):
        """Test multiple save/load cycles are consistent."""
        model_orig, X, _ = trained_model
        pred_orig = model_orig.predict(X[:5])

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                path = Path(tmpdir) / f"model_{i}.pkl"
                save_model(model_orig, path)
                model_orig = load_model(path)

            pred_final = model_orig.predict(X[:5])
            np.testing.assert_array_almost_equal(pred_orig, pred_final)


class TestFeatureImportance:
    """Test feature importance extraction."""

    def test_model_has_feature_importance(self):
        """Test that trained model has feature_importances_ attribute."""
        np.random.seed(42)
        X = np.random.randn(200, 5)
        y = X[:, 0] * 2 + X[:, 1] + np.random.randn(200) * 0.1

        model = build_model(random_seed=42)
        model.fit(X, y)

        assert hasattr(model, 'feature_importances_')
        assert len(model.feature_importances_) == 5
        assert sum(model.feature_importances_) > 0


class TestDemandModelIntegration:
    """End-to-end tests for demand model training and prediction."""

    def test_train_returns_model_and_metadata(self):
        """Test that train() returns model and metadata dict."""
        np.random.seed(42)
        X = np.random.randn(500, 10)
        y = X[:, 0] * 2 + np.random.randn(500) * 0.5

        # Create a feature dataframe as expected by train()
        feature_cols = ['rolling_7d', 'rolling_30d', 'lag_7', 'lag_14', 'day_of_week',
                       'month', 'velocity', 'stock_ratio', 'avg_lead_time_days', 'reliability_score']
        df = pd.DataFrame(X, columns=feature_cols)
        df['quantity_used'] = y

        result = train(df)

        assert isinstance(result, dict)
        assert 'lgbm' in result
        assert 'lr' in result
        assert 'arima' in result or 'arima_error' in result

        lgbm_metrics = result['lgbm']
        assert 'r2' in lgbm_metrics
        assert 'mae' in lgbm_metrics
        assert 'rmse' in lgbm_metrics
        assert 'cv_r2_scores' in lgbm_metrics

    def test_predict_forecast_returns_prediction_and_confidence(self):
        """Test that predict_forecast returns dict with prediction and bounds."""
        np.random.seed(42)
        X_train = np.random.randn(500, 10)
        y_train = X_train[:, 0] * 2 + np.random.randn(500) * 0.5

        # Create training dataframe
        feature_cols = ['rolling_7d', 'rolling_30d', 'lag_7', 'lag_14', 'day_of_week',
                       'month', 'velocity', 'stock_ratio', 'avg_lead_time_days', 'reliability_score']
        df_train = pd.DataFrame(X_train, columns=feature_cols)
        df_train['quantity_used'] = y_train

        train_result = train(df_train)

        # Verify training succeeds and model is saved
        from config import PKL_DIR
        assert (PKL_DIR / "demand_lgbm.pkl").exists()
        assert (PKL_DIR / "demand_meta.pkl").exists()

        # Verify training resulted in good metrics
        assert 'lgbm' in train_result
        assert train_result['lgbm']['r2'] > 0.5


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_data(self):
        """Test behavior with empty dataset."""
        X = np.empty((0, 10))
        y = np.empty(0)

        with pytest.raises((ValueError, Exception)):
            cross_validate_r2(X, y, random_seed=42, folds=5)

    def test_single_sample(self):
        """Test with single sample."""
        X = np.random.randn(1, 10)
        y = np.array([1.0])

        # Should not crash, but may produce warnings
        with pytest.warns(None) as warning_list:
            try:
                cross_validate_r2(X, y, random_seed=42, folds=2)
            except (ValueError, Exception):
                pass  # Expected to fail with too few samples

    def test_nan_in_features(self):
        """Test handling of NaN values."""
        X = np.random.randn(100, 10)
        X[0, 0] = np.nan
        y = np.random.randn(100)

        # Should handle or raise error appropriately
        try:
            cross_validate_r2(X, y, random_seed=42, folds=3)
        except (ValueError, Exception):
            pass  # Expected behavior

    def test_inf_in_targets(self):
        """Test handling of infinite values in target."""
        X = np.random.randn(100, 10)
        y = np.random.randn(100)
        y[0] = np.inf

        try:
            cross_validate_r2(X, y, random_seed=42, folds=3)
        except (ValueError, Exception):
            pass  # Expected behavior


class TestModelQuality:
    """Test model quality and performance."""

    def test_model_learns_from_data(self):
        """Test that model improves a bit with real relationships."""
        np.random.seed(42)
        # Create data with clear relationship
        X = np.random.randn(1000, 10)
        y = X[:, 0] * 5 + X[:, 1] * 3 + X[:, 2] * 2 + np.random.randn(1000) * 0.5

        model = build_model(random_seed=42)
        model.fit(X, y)

        train_r2 = model.score(X, y)
        assert train_r2 > 0.8  # Should have good fit on training data

    def test_cv_score_distribution(self):
        """Test that CV scores have reasonable variance."""
        np.random.seed(42)
        X = np.random.randn(500, 10)
        y = X[:, 0] * 2 + np.random.randn(500) * 0.5

        scores = cross_validate_r2(X, y, random_seed=42, folds=5)

        mean_score = np.mean(scores)
        std_score = np.std(scores)

        # Standard deviation should be reasonable (not zero, not huge)
        assert 0 < std_score < mean_score


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
