from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import optuna
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import hyperparameter_tuning as hpt


class _DummyModel:
    def fit(self, X, y, **kwargs):
        self._mean = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(shape=(len(X),), fill_value=self._mean, dtype=float)


def test_build_study_uses_tpe_and_successive_halving():
    study = hpt.build_study(direction="maximize", study_name="unit_test_study")
    assert isinstance(study.sampler, optuna.samplers.TPESampler)
    assert isinstance(study.pruner, optuna.pruners.SuccessiveHalvingPruner)


def test_objective_lightgbm_returns_float(monkeypatch):
    monkeypatch.setattr(hpt, "build_lgbm_model", lambda random_seed, cfg=None: _DummyModel())
    trial = optuna.trial.FixedTrial(
        {
            "n_estimators": 150,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "num_leaves": 32,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
        }
    )
    X_train = np.array([[1.0], [2.0], [3.0]])
    y_train = np.array([2.0, 4.0, 6.0])
    X_valid = np.array([[4.0], [5.0]])
    y_valid = np.array([8.0, 10.0])

    score = hpt.objective_lightgbm(trial, X_train, y_train, X_valid, y_valid)
    assert isinstance(score, float)


def test_objective_catboost_returns_float(monkeypatch):
    monkeypatch.setattr(hpt, "build_catboost_model", lambda random_seed, cfg=None: _DummyModel())
    monkeypatch.setattr(hpt, "prepare_catboost_input", lambda X, cat_features: X)

    trial = optuna.trial.FixedTrial(
        {
            "iterations": 200,
            "depth": 6,
            "learning_rate": 0.05,
            "l2_leaf_reg": 3.0,
            "subsample": 0.8,
            "colsample_bylevel": 0.8,
            "bagging_temperature": 1.0,
        }
    )
    X_train = np.array([[1.0], [2.0], [3.0]])
    y_train = np.array([2.0, 4.0, 6.0])
    X_valid = np.array([[4.0], [5.0]])
    y_valid = np.array([8.0, 10.0])

    score = hpt.objective_catboost(trial, X_train, y_train, X_valid, y_valid, cat_features=[])
    assert isinstance(score, float)


def test_objective_lstm_returns_mae(monkeypatch):
    monkeypatch.setattr(
        hpt.lstm_model,
        "train",
        lambda *args, **kwargs: {"mae": 3.14},
    )
    trial = optuna.trial.FixedTrial(
        {
            "lookback": 14,
            "epochs": 12,
            "batch_size": 64,
            "max_samples": 3000,
        }
    )
    df = pd.DataFrame(
        {
            "item_id": [1],
            "usage_date": ["2026-01-01"],
            "quantity_used": [10.0],
        }
    )
    mae = hpt.objective_lstm(trial, df)
    assert mae == 3.14


def test_save_best_params_merges_existing(tmp_path: Path):
    out = tmp_path / "best_params.json"
    out.write_text(json.dumps({"existing": {"ok": True}}), encoding="utf-8")

    result = {"lightgbm": {"best_value": 0.99, "best_params": {"n_estimators": 123}}}
    path = hpt.save_best_params(result, output_path=out)

    assert path == out
    merged = json.loads(out.read_text(encoding="utf-8"))
    assert "existing" in merged
    assert merged["lightgbm"]["best_value"] == 0.99
