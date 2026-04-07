from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.ensemble_model import (
    VotingPredictor,
    select_best_single_model,
    tune_weights_via_grid,
)


def test_weighted_combine_uses_available_models():
    vp = VotingPredictor()
    preds = {
        "xgb": np.array([10.0, 20.0]),
        "lr": np.array([14.0, 18.0]),
    }
    out = vp.combine(preds)

    expected = (0.4 / 0.5) * preds["xgb"] + (0.1 / 0.5) * preds["lr"]
    np.testing.assert_allclose(out, expected)


def test_confidence_shape_matches_predictions():
    vp = VotingPredictor()
    preds = {
        "xgb": np.array([10.0, 20.0, 30.0]),
        "lgbm": np.array([11.0, 19.0, 29.0]),
        "lr": np.array([9.0, 21.0, 31.0]),
    }
    conf = vp.confidence(preds)
    assert conf.shape == (3,)
    assert np.all(conf > 0)


def test_tune_weights_grid_sums_to_one():
    preds = {
        "lgbm": np.array([10.0, 11.0, 12.0]),
        "lr": np.array([9.0, 10.0, 11.0]),
    }
    target = np.array([10.0, 11.0, 12.0])
    tuned = tune_weights_via_grid(preds, target, step=0.1)

    assert set(tuned.keys()) == {"lgbm", "lr"}
    assert abs(sum(tuned.values()) - 1.0) < 1e-8
    assert tuned["lgbm"] >= tuned["lr"]


def test_select_best_single_model_uses_target_error():
    preds = {
        "lgbm": np.array([20.0, 20.0]),
        "lr": np.array([10.0, 10.0]),
    }
    target = np.array([10.0, 10.0])
    model, arr = select_best_single_model(preds, target)

    assert model == "lr"
    np.testing.assert_allclose(arr, preds["lr"])
