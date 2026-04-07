"""Optuna-based hyperparameter optimization utilities (TASK-106)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from config import RANDOM_SEED
from models import lstm_model
from models.catboost_model import CatBoostConfig, build_model as build_catboost_model, prepare_catboost_input
from models.demand_model import FEATURE_COLS, TARGET_COL
from models.lightgbm_model import LightGBMConfig, build_model as build_lgbm_model

BEST_PARAMS_PATH = Path(__file__).resolve().parent / "best_params.json"


def _temporal_split(
    X: np.ndarray | pd.DataFrame,
    y: np.ndarray,
    test_ratio: float = 0.2,
) -> tuple[np.ndarray | pd.DataFrame, np.ndarray | pd.DataFrame, np.ndarray, np.ndarray]:
    split_idx = max(1, int(len(y) * (1.0 - test_ratio)))
    split_idx = min(split_idx, len(y) - 1)
    if isinstance(X, pd.DataFrame):
        return X.iloc[:split_idx], X.iloc[split_idx:], y[:split_idx], y[split_idx:]
    return X[:split_idx], X[split_idx:], y[:split_idx], y[split_idx:]


def build_study(direction: str, study_name: str | None = None) -> optuna.Study:
    """Create Optuna study with TPE sampler and Successive Halving pruner."""
    return optuna.create_study(
        direction=direction,
        study_name=study_name,
        sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED),
        pruner=optuna.pruners.SuccessiveHalvingPruner(),
    )


def objective_lightgbm(
    trial: optuna.trial.Trial,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_valid: np.ndarray,
    y_valid: np.ndarray,
) -> float:
    """Optuna objective: maximize LightGBM validation R2."""
    cfg = LightGBMConfig(
        n_estimators=trial.suggest_int("n_estimators", 100, 500),
        max_depth=trial.suggest_int("max_depth", 3, 10),
        learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        subsample=trial.suggest_float("subsample", 0.5, 1.0),
        colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
        num_leaves=trial.suggest_int("num_leaves", 16, 128),
        reg_alpha=trial.suggest_float("reg_alpha", 0.0, 1.0),
        reg_lambda=trial.suggest_float("reg_lambda", 0.0, 1.0),
    )
    model = build_lgbm_model(RANDOM_SEED, cfg=cfg)
    model.fit(X_train, y_train)
    pred = model.predict(X_valid)
    return float(r2_score(y_valid, pred))


def objective_catboost(
    trial: optuna.trial.Trial,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_valid: np.ndarray,
    y_valid: np.ndarray,
    cat_features: list[int] | None = None,
) -> float:
    """Optuna objective: maximize CatBoost validation R2."""
    cat_idx = cat_features or []
    cfg = CatBoostConfig(
        iterations=trial.suggest_int("iterations", 100, 500),
        depth=trial.suggest_int("depth", 3, 10),
        learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        l2_leaf_reg=trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
        subsample=trial.suggest_float("subsample", 0.5, 1.0),
        colsample_bylevel=trial.suggest_float("colsample_bylevel", 0.5, 1.0),
        bagging_temperature=trial.suggest_float("bagging_temperature", 0.0, 5.0),
    )

    model = build_catboost_model(RANDOM_SEED, cfg=cfg)
    X_train_cb = prepare_catboost_input(X_train, cat_idx)
    X_valid_cb = prepare_catboost_input(X_valid, cat_idx)
    model.fit(
        X_train_cb,
        y_train,
        cat_features=cat_idx,
        eval_set=[(X_valid_cb, y_valid)],
        early_stopping_rounds=30,
        verbose=False,
    )
    pred = model.predict(X_valid_cb)
    return float(r2_score(y_valid, pred))


def objective_lstm(
    trial: optuna.trial.Trial,
    feat_df: pd.DataFrame,
    model_type: str = "lstm",
) -> float:
    """Optuna objective: minimize recurrent model MAE."""
    lookback = trial.suggest_int("lookback", 7, 21)
    epochs = trial.suggest_int("epochs", 10, 40)
    batch_size = trial.suggest_categorical("batch_size", [32, 64, 128])
    max_samples = trial.suggest_int("max_samples", 2000, 12000, step=1000)

    metrics = lstm_model.train(
        feat_df,
        model_type=model_type,
        lookback=lookback,
        epochs=epochs,
        batch_size=batch_size,
        max_samples=max_samples,
    )
    return float(metrics["mae"])


def optimize_lightgbm(
    feat_df: pd.DataFrame,
    n_trials: int = 100,
    timeout: int | None = None,
) -> optuna.Study:
    """Run LightGBM hyperparameter search (maximize R2)."""
    data = feat_df.dropna(subset=FEATURE_COLS + [TARGET_COL])
    X = data[FEATURE_COLS].to_numpy(dtype=float)
    y = data[TARGET_COL].to_numpy(dtype=float)
    X_train, X_valid, y_train, y_valid = _temporal_split(X, y)

    study = build_study(direction="maximize", study_name="lgbm_r2")
    study.optimize(
        lambda trial: objective_lightgbm(trial, X_train, y_train, X_valid, y_valid),
        n_trials=n_trials,
        timeout=timeout,
    )
    return study


def optimize_catboost(
    feat_df: pd.DataFrame,
    n_trials: int = 100,
    timeout: int | None = None,
    cat_features: list[int] | None = None,
) -> optuna.Study:
    """Run CatBoost hyperparameter search (maximize R2)."""
    data = feat_df.dropna(subset=FEATURE_COLS + [TARGET_COL])
    X = data[FEATURE_COLS].to_numpy(dtype=float)
    y = data[TARGET_COL].to_numpy(dtype=float)
    X_train, X_valid, y_train, y_valid = _temporal_split(X, y)

    study = build_study(direction="maximize", study_name="catboost_r2")
    study.optimize(
        lambda trial: objective_catboost(trial, X_train, y_train, X_valid, y_valid, cat_features=cat_features),
        n_trials=n_trials,
        timeout=timeout,
    )
    return study


def optimize_lstm(
    feat_df: pd.DataFrame,
    n_trials: int = 100,
    timeout: int | None = None,
    model_type: str = "lstm",
) -> optuna.Study:
    """Run recurrent model search (minimize MAE)."""
    study = build_study(direction="minimize", study_name=f"{model_type}_mae")
    study.optimize(
        lambda trial: objective_lstm(trial, feat_df=feat_df, model_type=model_type),
        n_trials=n_trials,
        timeout=timeout,
    )
    return study


def _top_trials(study: optuna.Study, top_n: int = 3) -> list[dict]:
    ordered = sorted(study.trials, key=lambda t: float(t.value), reverse=study.direction.name == "MAXIMIZE")
    output = []
    for trial in ordered[:top_n]:
        output.append(
            {
                "number": trial.number,
                "value": float(trial.value),
                "params": trial.params,
            }
        )
    return output


def save_best_params(result: dict, output_path: Path = BEST_PARAMS_PATH) -> Path:
    """Merge and persist optimization results to best_params.json."""
    existing = {}
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))

    merged = {**existing, **result}
    output_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return output_path


def run_all_optimizations(
    feat_df: pd.DataFrame,
    n_trials: int = 100,
    include_lstm: bool = True,
    output_path: Path = BEST_PARAMS_PATH,
) -> dict:
    """Run all model optimizations and persist top/best params."""
    lgbm_study = optimize_lightgbm(feat_df, n_trials=n_trials)
    catboost_study = optimize_catboost(feat_df, n_trials=n_trials)

    output = {
        "lightgbm": {
            "best_value": float(lgbm_study.best_value),
            "best_params": lgbm_study.best_params,
            "top3": _top_trials(lgbm_study, top_n=3),
        },
        "catboost": {
            "best_value": float(catboost_study.best_value),
            "best_params": catboost_study.best_params,
            "top3": _top_trials(catboost_study, top_n=3),
        },
    }

    if include_lstm:
        lstm_study = optimize_lstm(feat_df, n_trials=n_trials, model_type="lstm")
        output["lstm"] = {
            "best_value": float(lstm_study.best_value),
            "best_params": lstm_study.best_params,
            "top3": _top_trials(lstm_study, top_n=3),
        }

    save_best_params(output, output_path=output_path)
    return output
