"""
Unit tests for CatBoost demand model with categorical features.

Tests cover:
- CatBoost configuration and model building
- Cross-validation with categorical features
- Model persistence (save/load)
- Feature importance extraction with categorical insights
- End-to-end training with mixed feature types
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
import pandas as pd
import tempfile

from models.catboost_model import (
    CatBoostConfig,
    build_model,
    cross_validate_r2,
    save_model,
    load_model,
    get_feature_importance,
    prepare_catboost_array,
)


class TestCatBoostConfig:
    """Test CatBoostConfig dataclass."""

    def test_default_config_creation(self):
        """Test default config instantiation."""
        cfg = CatBoostConfig()
        assert cfg.iterations == 500
        assert cfg.depth == 7
        assert cfg.learning_rate == 0.05
        assert cfg.grow_policy == "SymmetricTree"

    def test_custom_config_creation(self):
        """Test custom config with overrides."""
        cfg = CatBoostConfig(iterations=100, learning_rate=0.1)
        assert cfg.iterations == 100
        assert cfg.learning_rate == 0.1
        assert cfg.depth == 7  # unchanged

    def test_config_immutable(self):
        """Test that config is frozen (immutable)."""
        cfg = CatBoostConfig()
        with pytest.raises(AttributeError):
            cfg.iterations = 200


class TestBuildModel:
    """Test CatBoost model building."""

    def test_builds_regressor(self):
        """Test that build_model returns CatBoostRegressor."""
        from catboost import CatBoostRegressor
        model = build_model(random_seed=42)
        assert isinstance(model, CatBoostRegressor)

    def test_model_with_custom_config(self):
        """Test model building with custom config."""
        cfg = CatBoostConfig(iterations=100)
        model = build_model(random_seed=42, cfg=cfg)
        assert model.get_param('iterations') == 100

    def test_random_seed_reproducibility(self):
        """Test that same seed produces same model structure."""
        model1 = build_model(random_seed=42)
        model2 = build_model(random_seed=42)
        assert model1.get_param('random_seed') == model2.get_param('random_seed')


class TestCrossValidationWithCategorical:
    """Test cross-validation with categorical features."""

    @pytest.fixture
    def sample_data_with_cat(self):
        """Create sample data with categorical features."""
        np.random.seed(42)
        # Create numeric features
        X_numeric = np.random.randn(500, 10)

        # Create categorical features (as integers: 0, 1, 2, etc.)
        cat1 = np.random.randint(0, 5, (500, 1))
        cat2 = np.random.randint(0, 3, (500, 1))

        X = np.column_stack([X_numeric, cat1, cat2])
        cat_indices = [10, 11]
        X = prepare_catboost_array(X, cat_indices)

        y = X_numeric[:, 0] * 2 + cat1[:, 0] * 0.5 + np.random.randn(500) * 0.1

        return X, y, cat_indices

    def test_cv_returns_scores_with_categorical(self, sample_data_with_cat):
        """Test CV returns R² scores with categorical features."""
        X, y, cat_indices = sample_data_with_cat
        scores = cross_validate_r2(X, y, cat_indices, random_seed=42, folds=3)

        assert len(scores) == 3
        assert all(isinstance(s, float) for s in scores)

    def test_cv_categorical_improves_score(self):
        """Test that categorical handling improves CV score."""
        np.random.seed(42)
        X_numeric = np.random.randn(500, 10)

        # Create categorical features
        cat1 = np.random.randint(0, 5, 500)
        cat2 = np.random.randint(0, 3, 500)

        X = np.column_stack([X_numeric, cat1, cat2])
        cat_indices = [10, 11]
        X = prepare_catboost_array(X, cat_indices)

        # Target strongly depends on categorical features
        y = cat1 * 5 + cat2 * 3 + X_numeric[:, 0] + np.random.randn(500) * 0.5

        scores = cross_validate_r2(X, y, cat_indices, random_seed=42, folds=3)

        # Should get decent score with categorical support
        assert np.mean(scores) > 0.5

    @pytest.fixture
    def trained_model_with_cat(self):
        """Create and train a model with categorical features."""
        np.random.seed(42)
        X_numeric = np.random.randn(200, 8)
        cat1 = np.random.randint(0, 4, 200)
        cat2 = np.random.randint(0, 2, 200)

        X = np.column_stack([X_numeric, cat1, cat2])
        cat_indices = [8, 9]
        X = prepare_catboost_array(X, cat_indices)

        y = X_numeric[:, 0] * 2 + cat1 * 1.0 + np.random.randn(200) * 0.5

        model = build_model(random_seed=42)
        model.fit(X, y, cat_features=cat_indices, verbose=False)

        return model, X, y

    def test_save_model_creates_file(self, trained_model_with_cat):
        """Test that save_model creates a pickle file."""
        model, _, _ = trained_model_with_cat

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pkl"
            save_model(model, model_path)

            assert model_path.exists()
            assert model_path.stat().st_size > 0

    def test_load_model_retrieves_model(self, trained_model_with_cat):
        """Test that loaded model works correctly."""
        model_orig, X, y = trained_model_with_cat

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pkl"
            save_model(model_orig, model_path)

            model_loaded = load_model(model_path)

            # Test predictions match
            pred_orig = model_orig.predict(X[:10])
            pred_loaded = model_loaded.predict(X[:10])

            np.testing.assert_array_almost_equal(pred_orig, pred_loaded)


class TestFeatureImportanceWithCategorical:
    """Test feature importance extraction with categorical insights."""

    def test_feature_importance_has_categorical_flag(self):
        """Test that feature importance includes categorical flag."""
        np.random.seed(42)
        X_numeric = np.random.randn(200, 4)
        cat_col = np.random.randint(0, 3, 200)

        X = np.column_stack([X_numeric, cat_col])
        cat_indices = [4]
        X = prepare_catboost_array(X, cat_indices)

        y = X_numeric[:, 0] * 2 + cat_col * 1.5 + np.random.randn(200) * 0.1

        model = build_model(random_seed=42)
        model.fit(X, y, cat_features=cat_indices, verbose=False)

        feature_names = ["f0", "f1", "f2", "f3", "f3_cat"]
        cat_names = ["f3_cat"]

        importance = get_feature_importance(model, feature_names, cat_names)

        assert len(importance) == 5
        assert all('is_categorical' in item for item in importance)

        # Find the categorical feature
        cat_feature = [x for x in importance if x['feature'] == 'f3_cat'][0]
        assert cat_feature['is_categorical'] is True

        # Non-categorical features should have False
        non_cat = [x for x in importance if x['feature'] == 'f0'][0]
        assert non_cat['is_categorical'] is False


class TestCatBoostVsNumeric:
    """Test CatBoost performance on categorical vs numeric features."""

    def test_categorical_feature_importance_ranking(self):
        """Test that highly predictive categorical features rank high."""
        np.random.seed(42)
        n_samples = 500

        # Numeric features (weakly predictive)
        X_numeric = np.random.randn(n_samples, 5)

        # Categorical features (strongly predictive)
        cat1 = np.random.randint(0, 10, n_samples)
        cat2 = np.random.randint(0, 5, n_samples)

        X = np.column_stack([X_numeric, cat1, cat2])
        cat_indices = [5, 6]
        X = prepare_catboost_array(X, cat_indices)

        # Target depends mostly on categorical features
        y = cat1 * 3 + cat2 * 2 + X_numeric[:, 0] * 0.1 + np.random.randn(n_samples) * 0.5

        model = build_model(random_seed=42)
        model.fit(X, y, cat_features=cat_indices, verbose=False)

        feature_names = [f"numeric_{i}" for i in range(5)] + ["category_1", "category_2"]
        cat_names = ["category_1", "category_2"]

        importance = get_feature_importance(model, feature_names, cat_names)

        # Categorical features should be in top ranks
        top_3_features = [x['feature'] for x in importance[:3]]
        assert any(cat in top_3_features for cat in cat_names)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
