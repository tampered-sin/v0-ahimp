"""LightGBM utilities for demand forecasting."""

from __future__ import annotations

from dataclasses import dataclass
import pickle
from pathlib import Path

import numpy as np
from lightgbm import LGBMRegressor
from sklearn.model_selection import KFold, cross_val_score


@dataclass(frozen=True)
class LightGBMConfig:
    n_estimators: int = 220
    max_depth: int = 8
    learning_rate: float = 0.06
    subsample: float = 0.85
    colsample_bytree: float = 0.85
    num_leaves: int = 63
    reg_alpha: float = 0.1
    reg_lambda: float = 0.2


def build_model(random_seed: int, cfg: LightGBMConfig | None = None) -> LGBMRegressor:
    c = cfg or LightGBMConfig()
    return LGBMRegressor(
        n_estimators=c.n_estimators,
        max_depth=c.max_depth,
        learning_rate=c.learning_rate,
        subsample=c.subsample,
        colsample_bytree=c.colsample_bytree,
        num_leaves=c.num_leaves,
        reg_alpha=c.reg_alpha,
        reg_lambda=c.reg_lambda,
        random_state=random_seed,
        n_jobs=-1,
        verbosity=-1,
    )


def cross_validate_r2(X: np.ndarray, y: np.ndarray, random_seed: int, folds: int = 5) -> list[float]:
    model = build_model(random_seed)
    kf = KFold(n_splits=folds, shuffle=False)
    scores = cross_val_score(model, X, y, cv=kf, scoring="r2")
    return [float(s) for s in scores]


def save_model(model: LGBMRegressor, pkl_path: Path) -> None:
    with open(pkl_path, "wb") as f:
        pickle.dump(model, f)


def load_model(pkl_path: Path) -> LGBMRegressor:
    with open(pkl_path, "rb") as f:
        return pickle.load(f)
