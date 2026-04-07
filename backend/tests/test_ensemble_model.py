from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.ensemble_model import VotingPredictor


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
