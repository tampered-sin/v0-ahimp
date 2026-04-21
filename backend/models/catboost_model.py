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
from sklearn.model_selection import KFold
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


def _to_dataframe(X: np.ndarray | pd.DataFrame) -> pd.DataFrame:
    """Normalize input to a DataFrame so CatBoost can handle mixed dtypes."""
    if isinstance(X, pd.DataFrame):
        return X.copy()
    return pd.DataFrame(np.asarray(X).copy())


def _resolve_column(df: pd.DataFrame, feature: int | str):
    """Resolve feature identifier (index or name) to a concrete DataFrame column."""
    if isinstance(feature, int):
        return df.columns[feature]
    return feature


def prepare_catboost_input(
    X: np.ndarray | pd.DataFrame,
    cat_features: list[int | str] | None,
) -> pd.DataFrame:
    """
    Prepare input data for CatBoost with categorical columns coerced appropriately.

    CatBoost disallows floating-point numpy arrays when cat_features are provided,
    so we always use a DataFrame and cast categorical columns to category dtype.
    """
    df = _to_dataframe(X)
    if not cat_features:
        return df

    for feature in cat_features:
        col = _resolve_column(df, feature)
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            series = pd.to_numeric(series, errors="coerce").fillna(-1).astype(np.int64)
        else:
            series = series.astype(str).fillna("unknown")
        df[col] = series.astype("category")

    return df


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
    kf = KFold(n_splits=folds, shuffle=False)

    scores = []
    for train_idx, val_idx in kf.split(X):
        model = build_model(random_seed)

        if isinstance(X, pd.DataFrame):
            X_train_raw, X_val_raw = X.iloc[train_idx], X.iloc[val_idx]
        else:
            X_train_raw, X_val_raw = X[train_idx], X[val_idx]

        X_train = prepare_catboost_input(X_train_raw, cat_features)
        X_val = prepare_catboost_input(X_val_raw, cat_features)
        y_train, y_val = np.asarray(y)[train_idx], np.asarray(y)[val_idx]

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


def get_shap_importance(
    model: CatBoostRegressor,
    X: np.ndarray | pd.DataFrame,
    feature_names: list[str],
    cat_feature_names: list[str],
    max_samples: int = 500,
) -> list[dict]:
    """
    Compute SHAP-based global feature importance for CatBoost.

    Returns an empty list when SHAP is unavailable or SHAP computation fails.
    """
    try:
        import shap
    except Exception:
        return []

    cat_indices = [idx for idx, name in enumerate(feature_names) if name in cat_feature_names]
    X_df = prepare_catboost_input(X, cat_indices)

    if len(X_df) > max_samples:
        X_df = X_df.sample(n=max_samples, random_state=42)

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_df)
        values = np.asarray(shap_values)
        if values.ndim == 3:
            values = values[0]
        mean_abs = np.abs(values).mean(axis=0)

        importance = []
        for idx, name in enumerate(feature_names):
            importance.append(
                {
                    "feature": name,
                    "mean_abs_shap": float(mean_abs[idx]),
                    "is_categorical": name in cat_feature_names,
                }
            )

        importance.sort(key=lambda x: x["mean_abs_shap"], reverse=True)
        return importance
    except Exception:
        return []


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
