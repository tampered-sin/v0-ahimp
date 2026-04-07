"""
CatBoost Model for Demand Forecasting with Categorical Features

Utilizes native categorical feature support for:
- supplier_id
- department_id
- category
- patient_type

Advantages over LightGBM:
- Native categorical handling (no label encoding needed)
- Better performance on categorical features
- Faster training with symmetric tree growing
- Built-in feature importance with categorical insights
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from catboost import CatBoostRegressor


@dataclass(frozen=True)
class CatBoostConfig:
    """CatBoost hyperparameters optimized for hospital inventory data."""
    iterations: int = 500
    depth: int = 7
    learning_rate: float = 0.05
    l2_leaf_reg: float = 3.0
    subsample: float = 0.8
    colsample_bylevel: float = 0.8
    bagging_temperature: float = 1.0
    nan_mode: str = "Min"  # How to handle NaN values
    grow_policy: str = "SymmetricTree"  # Symmetric tree growth for stability


def build_model(random_seed: int, cfg: CatBoostConfig | None = None) -> CatBoostRegressor:
    """
    Build a CatBoost regressor with optimal hyperparameters.

    Args:
        random_seed: Random seed for reproducibility
        cfg: Optional custom CatBoostConfig

    Returns:
        Unfitted CatBoostRegressor instance
    """
    c = cfg or CatBoostConfig()
    return CatBoostRegressor(
        iterations=c.iterations,
        depth=c.depth,
        learning_rate=c.learning_rate,
        l2_leaf_reg=c.l2_leaf_reg,
        subsample=c.subsample,
        colsample_bylevel=c.colsample_bylevel,
        bagging_temperature=c.bagging_temperature,
        nan_mode=c.nan_mode,
        grow_policy=c.grow_policy,
        random_seed=random_seed,
        thread_count=-1,
        verbose=False,
        task_type="CPU",
    )


def prepare_catboost_array(X: np.ndarray, cat_features: list[int]) -> np.ndarray:
    """
    Convert a numpy feature matrix for use with CatBoost categorical features.

    CatBoost requires that when cat_features are specified, the data is NOT a
    plain float array: categorical columns must be integer or string values.
    This function converts the array to object dtype and casts categorical
    columns to Python int so CatBoost can accept them.

    Args:
        X: Feature matrix (may be float64)
        cat_features: List of column indices that are categorical

    Returns:
        Object-dtype array with categorical columns stored as Python ints
    """
    if not cat_features:
        return X
    X_obj = X.astype(object)
    for idx in cat_features:
        X_obj[:, idx] = [int(v) for v in X_obj[:, idx]]
    return X_obj


def cross_validate_r2(
    X: np.ndarray,
    y: np.ndarray,
    cat_features: list[int],
    random_seed: int,
    folds: int = 5,
) -> list[float]:
    """
    Run k-fold cross-validation with categorical features and early stopping.

    Args:
        X: Feature matrix
        y: Target vector
        cat_features: List of column indices that are categorical
        random_seed: Random seed for reproducibility
        folds: Number of cross-validation folds

    Returns:
        List of R² scores for each fold
    """
    model = build_model(random_seed)
    tss = TimeSeriesSplit(n_splits=folds)

    scores = []
    for train_idx, val_idx in tss.split(X):
        X_train = prepare_catboost_array(X[train_idx], cat_features)
        X_val = prepare_catboost_array(X[val_idx], cat_features)
        y_train, y_val = y[train_idx], y[val_idx]

        model.fit(
            X_train,
            y_train,
            cat_features=cat_features,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=50,
            verbose=False,
        )

        score = model.score(X_val, y_val)
        scores.append(score)

    return scores


def save_model(model: CatBoostRegressor, path: Path) -> None:
    """
    Save trained CatBoost model to pickle file.

    Args:
        model: Trained CatBoostRegressor
        path: Destination file path
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)


def load_model(path: Path) -> CatBoostRegressor:
    """
    Load trained CatBoost model from pickle file.

    Args:
        path: Path to pickle file

    Returns:
        Loaded CatBoostRegressor
    """
    with open(path, "rb") as f:
        return pickle.load(f)


def get_feature_importance(
    model: CatBoostRegressor,
    feature_names: list[str],
    cat_feature_names: list[str],
) -> list[dict]:
    """
    Extract feature importance with categorical insights.

    Args:
        model: Trained CatBoostRegressor
        feature_names: List of all feature names
        cat_feature_names: List of categorical feature names

    Returns:
        List of dicts with feature name, importance, and categorical flag
    """
    importance_values = model.get_feature_importance()

    importance = []
    for idx, (name, imp_value) in enumerate(zip(feature_names, importance_values)):
        is_categorical = name in cat_feature_names
        importance.append({
            "feature": name,
            "importance": float(imp_value),
            "is_categorical": is_categorical,
        })

    importance.sort(key=lambda x: x["importance"], reverse=True)
    return importance
