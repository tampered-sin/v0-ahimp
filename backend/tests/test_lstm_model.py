from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import lstm_model


def test_predict_forecast_returns_error_if_untrained(monkeypatch):
    monkeypatch.setattr(lstm_model, "is_trained", lambda model_type="lstm": False)
    df = pd.DataFrame(
        {
            "item_id": [1],
            "usage_date": ["2026-01-01"],
            "quantity_used": [10],
        }
    )
    out = lstm_model.predict_forecast(df, item_id=1, model_type="lstm")
    assert "error" in out


def test_build_lstm_model_output_units():
    if not lstm_model.TF_AVAILABLE:
        pytest.skip("TensorFlow unavailable in test environment")

    model = lstm_model.build_lstm_model(input_shape=(14, 10), output_horizon=14, model_type="lstm")
    assert model.output_shape[-1] == 14
