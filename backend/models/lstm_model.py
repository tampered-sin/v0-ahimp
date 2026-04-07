"""
LSTM/GRU demand forecasting model.

Architecture targets from TASK-103:
- Input shape: (14-day lookback, 10 features)
- LSTM stack: 64 units + dropout(0.2), then 32 units + dropout(0.2)
- Dense: 16 units
- Output: 14-day demand forecast
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from config import PKL_DIR, RANDOM_SEED, FORECAST_HORIZON
from data.sequence_generator import (
    FEATURE_COLS,
    create_demand_sequences,
    temporal_train_test_split,
)

try:
    import tensorflow as tf
    from tensorflow import keras
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "TensorFlow is required for lstm_model.py. Install tensorflow>=2.13."
    ) from exc

PKL_LSTM_META = PKL_DIR / "demand_lstm_meta.pkl"
PKL_GRU_META = PKL_DIR / "demand_gru_meta.pkl"
MODEL_LSTM = PKL_DIR / "demand_lstm.keras"
MODEL_GRU = PKL_DIR / "demand_gru.keras"

LOOKBACK = 14
HORIZON = FORECAST_HORIZON


# Ensure deterministic-ish behavior where possible.
keras.utils.set_random_seed(RANDOM_SEED)


def build_lstm_model(
    input_shape: tuple[int, int] = (LOOKBACK, len(FEATURE_COLS)),
    horizon: int = HORIZON,
) -> keras.Model:
    """Build LSTM architecture defined in TASK-103."""
    model = keras.Sequential(
        [
            keras.layers.Input(shape=input_shape),
            keras.layers.LSTM(64, return_sequences=True),
            keras.layers.Dropout(0.2),
            keras.layers.LSTM(32),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(16, activation="relu"),
            keras.layers.Dense(horizon),
        ]
    )
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=1e-3), loss="mae")
    return model


def build_gru_model(
    input_shape: tuple[int, int] = (LOOKBACK, len(FEATURE_COLS)),
    horizon: int = HORIZON,
) -> keras.Model:
    """Alternative GRU architecture for comparison experiments."""
    model = keras.Sequential(
        [
            keras.layers.Input(shape=input_shape),
            keras.layers.GRU(64, return_sequences=True),
            keras.layers.Dropout(0.2),
            keras.layers.GRU(32),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(16, activation="relu"),
            keras.layers.Dense(horizon),
        ]
    )
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=1e-3), loss="mae")
    return model


def _select_model(model_type: str) -> tuple[keras.Model, Path, Path]:
    model_type = model_type.lower().strip()
    if model_type == "lstm":
        return build_lstm_model(), MODEL_LSTM, PKL_LSTM_META
    if model_type == "gru":
        return build_gru_model(), MODEL_GRU, PKL_GRU_META
    raise ValueError("model_type must be 'lstm' or 'gru'")


def train(
    feat_df: pd.DataFrame,
    model_type: str = "lstm",
    epochs: int = 30,
    batch_size: int = 64,
) -> dict:
    """
    Train LSTM/GRU on sequence dataset and persist artifacts.

    Returns training/test metrics and training configuration.
    """
    feat_df = feat_df.dropna(subset=FEATURE_COLS + ["quantity_used", "item_id", "usage_date"])
    X, y = create_demand_sequences(feat_df, lookback=LOOKBACK, horizon=HORIZON)

    if len(X) < 20:
        raise ValueError("Not enough sequence samples to train LSTM/GRU model")

    X_train, X_test, y_train, y_test = temporal_train_test_split(X, y, train_ratio=0.8)

    model, model_path, meta_path = _select_model(model_type)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    early_stopping = keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=5,
        restore_best_weights=True,
    )
    checkpoint = keras.callbacks.ModelCheckpoint(
        filepath=str(model_path),
        monitor="val_loss",
        save_best_only=True,
    )

    history = model.fit(
        X_train,
        y_train,
        validation_data=(X_test, y_test),
        epochs=epochs,
        batch_size=batch_size,
        verbose=0,
        callbacks=[early_stopping, checkpoint],
    )

    y_pred = model.predict(X_test, verbose=0)
    mae = float(mean_absolute_error(y_test.flatten(), y_pred.flatten()))
    r2 = float(r2_score(y_test.flatten(), y_pred.flatten()))

    meta = {
        "model_type": model_type,
        "lookback": LOOKBACK,
        "horizon": HORIZON,
        "feature_cols": FEATURE_COLS,
        "samples_train": int(len(X_train)),
        "samples_test": int(len(X_test)),
        "epochs_ran": int(len(history.history.get("loss", []))),
        "best_val_loss": float(min(history.history.get("val_loss", [0.0]))),
        "mae": mae,
        "r2": r2,
        "architecture": {
            "input_shape": [LOOKBACK, len(FEATURE_COLS)],
            "lstm_gru_units": [64, 32],
            "dense_units": 16,
            "output_horizon": HORIZON,
        },
    }

    with open(meta_path, "wb") as f:
        pickle.dump(meta, f)

    print(f"[LSTMModel:{model_type.upper()}] MAE={mae:.2f} R2={r2:.3f}")
    return meta


def _load_model_and_meta(model_type: str = "lstm") -> tuple[keras.Model, dict]:
    model_type = model_type.lower().strip()
    if model_type == "lstm":
        model_path, meta_path = MODEL_LSTM, PKL_LSTM_META
    elif model_type == "gru":
        model_path, meta_path = MODEL_GRU, PKL_GRU_META
    else:
        raise ValueError("model_type must be 'lstm' or 'gru'")

    if not model_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"Model artifacts missing for model_type={model_type}")

    model = keras.models.load_model(model_path)
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)
    return model, meta


def is_trained(model_type: str = "lstm") -> bool:
    """Check if persisted artifacts exist for a specific model type."""
    model_type = model_type.lower().strip()
    if model_type == "lstm":
        return MODEL_LSTM.exists() and PKL_LSTM_META.exists()
    if model_type == "gru":
        return MODEL_GRU.exists() and PKL_GRU_META.exists()
    return False


def predict_forecast(feat_df: pd.DataFrame, item_id: int, model_type: str = "lstm") -> dict:
    """
    Forecast next 14 days for a specific item using trained LSTM/GRU model.
    """
    model, meta = _load_model_and_meta(model_type=model_type)

    item_df = (
        feat_df[feat_df["item_id"] == item_id]
        .sort_values("usage_date")
        .tail(meta["lookback"])
    )
    if len(item_df) < meta["lookback"]:
        return {"error": f"Need at least {meta['lookback']} days of history for item {item_id}"}

    X_input = item_df[meta["feature_cols"]].astype(float).to_numpy()
    X_input = X_input.reshape(1, meta["lookback"], len(meta["feature_cols"]))

    pred = model.predict(X_input, verbose=0)[0]
    pred = np.maximum(pred, 0)

    start_date = pd.Timestamp.today().normalize()
    forecast = []
    for i, value in enumerate(pred, start=1):
        target_dt = start_date + pd.Timedelta(days=i)
        val = float(value)
        forecast.append(
            {
                "date": target_dt.strftime("%Y-%m-%d"),
                "predicted": round(val, 1),
                "lower": round(max(0.0, val * 0.8), 1),
                "upper": round(val * 1.2, 1),
            }
        )

    return {
        "item_id": item_id,
        "model_type": model_type,
        "forecast": forecast,
        "metrics": {"mae": meta.get("mae"), "r2": meta.get("r2")},
    }
