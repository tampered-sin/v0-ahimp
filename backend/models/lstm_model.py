"""Recurrent time-series demand forecasting model (TASK-103)."""
from __future__ import annotations

import pickle
import time

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from config import FORECAST_HORIZON, PKL_DIR, RANDOM_SEED
from data.sequence_generator import generate_sequences, split_sequences
from models.demand_model import FEATURE_COLS

try:
    import tensorflow as tf
    from tensorflow.keras import callbacks, layers, models

    TF_AVAILABLE = True
except Exception:
    TF_AVAILABLE = False


LSTM_H5 = PKL_DIR / "demand_lstm.h5"
GRU_H5 = PKL_DIR / "demand_gru.h5"
LSTM_META = PKL_DIR / "demand_lstm_meta.pkl"
GRU_META = PKL_DIR / "demand_gru_meta.pkl"
LSTM_SCALER = PKL_DIR / "demand_lstm_scaler.pkl"
GRU_SCALER = PKL_DIR / "demand_gru_scaler.pkl"
LSTM_Y_SCALER = PKL_DIR / "demand_lstm_y_scaler.pkl"
GRU_Y_SCALER = PKL_DIR / "demand_gru_y_scaler.pkl"


def _paths(model_type: str) -> tuple:
    key = model_type.lower()
    if key == "lstm":
        return LSTM_H5, LSTM_META, LSTM_SCALER, LSTM_Y_SCALER
    if key == "gru":
        return GRU_H5, GRU_META, GRU_SCALER, GRU_Y_SCALER
    raise ValueError("model_type must be 'lstm' or 'gru'")


def build_lstm_model(
    input_shape: tuple[int, int] = (14, 10),
    output_horizon: int = FORECAST_HORIZON,
    model_type: str = "lstm",
):
    """Build LSTM/GRU architecture for 14-step demand forecasting."""
    if not TF_AVAILABLE:
        raise RuntimeError("TensorFlow/Keras is not available")

    tf.keras.utils.set_random_seed(RANDOM_SEED)
    model = models.Sequential(name=f"{model_type.lower()}_demand_forecaster")

    model.add(layers.Input(shape=input_shape))
    if model_type.lower() == "gru":
        model.add(layers.GRU(64, return_sequences=True, dropout=0.2))
        model.add(layers.GRU(32, dropout=0.2))
    else:
        model.add(layers.LSTM(64, return_sequences=True, dropout=0.2))
        model.add(layers.LSTM(32, dropout=0.2))

    model.add(layers.Dense(16, activation="relu"))
    model.add(layers.Dense(output_horizon, activation="linear"))

    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def _scale_sequences(X_train: np.ndarray, X_test: np.ndarray) -> tuple[np.ndarray, np.ndarray, StandardScaler]:
    n_features = X_train.shape[2]
    scaler = StandardScaler()

    X_train_flat = X_train.reshape(-1, n_features)
    X_test_flat = X_test.reshape(-1, n_features)

    X_train_scaled = scaler.fit_transform(X_train_flat).reshape(X_train.shape)
    X_test_scaled = scaler.transform(X_test_flat).reshape(X_test.shape)
    return X_train_scaled, X_test_scaled, scaler


def train(
    feat_df: pd.DataFrame,
    model_type: str = "lstm",
    lookback: int = 14,
    horizon: int = FORECAST_HORIZON,
    epochs: int = 25,
    batch_size: int = 64,
    max_samples: int = 25000,
) -> dict:
    """Train recurrent model and persist checkpoint/meta/scaler."""
    if not TF_AVAILABLE:
        raise RuntimeError("TensorFlow/Keras is not installed")

    model_path, meta_path, scaler_path, y_scaler_path = _paths(model_type)

    X, y = generate_sequences(
        feat_df,
        lookback=lookback,
        horizon=horizon,
        feature_cols=FEATURE_COLS,
        target_col="quantity_used",
    )
    if len(X) < 8:
        raise ValueError("Not enough sequence samples for recurrent model training")

    if max_samples > 0 and len(X) > max_samples:
        rng = np.random.default_rng(RANDOM_SEED)
        idx = np.sort(rng.choice(len(X), size=max_samples, replace=False))
        X = X[idx]
        y = y[idx]

    X_train, X_test, y_train, y_test = split_sequences(X, y, train_ratio=0.8)
    X_train_scaled, X_test_scaled, scaler = _scale_sequences(X_train, X_test)

    y_scaler = StandardScaler()
    y_train_scaled = y_scaler.fit_transform(y_train.reshape(-1, 1)).reshape(y_train.shape)
    y_test_scaled = y_scaler.transform(y_test.reshape(-1, 1)).reshape(y_test.shape)

    model = build_lstm_model(
        input_shape=(lookback, len(FEATURE_COLS)),
        output_horizon=horizon,
        model_type=model_type,
    )

    early_stop = callbacks.EarlyStopping(
        monitor="val_loss",
        patience=5,
        restore_best_weights=True,
    )
    checkpoint = callbacks.ModelCheckpoint(
        filepath=str(model_path),
        monitor="val_loss",
        save_best_only=True,
        save_weights_only=False,
    )

    start = time.perf_counter()
    model.fit(
        X_train_scaled,
        y_train_scaled,
        validation_data=(X_test_scaled, y_test_scaled),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stop, checkpoint],
        verbose=0,
    )
    elapsed = time.perf_counter() - start

    # Ensure final persisted model exists even if checkpoint callback skipped write.
    if not model_path.exists():
        model.save(str(model_path))

    y_pred_scaled = model.predict(X_test_scaled, verbose=0)
    y_pred = y_scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).reshape(y_pred_scaled.shape)
    y_test_flat = y_test.reshape(-1)
    y_pred_flat = y_pred.reshape(-1)

    mae = float(mean_absolute_error(y_test_flat, y_pred_flat))
    rmse = float(np.sqrt(mean_squared_error(y_test_flat, y_pred_flat)))
    r2 = float(r2_score(y_test_flat, y_pred_flat))

    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    with open(y_scaler_path, "wb") as f:
        pickle.dump(y_scaler, f)

    meta = {
        "model_type": model_type.lower(),
        "lookback": lookback,
        "horizon": horizon,
        "features": FEATURE_COLS,
        "train_samples": int(len(X_train_scaled)),
        "test_samples": int(len(X_test_scaled)),
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "training_time_sec": round(elapsed, 3),
    }
    with open(meta_path, "wb") as f:
        pickle.dump(meta, f)

    return meta


def is_trained(model_type: str = "lstm") -> bool:
    model_path, meta_path, scaler_path, y_scaler_path = _paths(model_type)
    return model_path.exists() and meta_path.exists() and scaler_path.exists() and y_scaler_path.exists()


def _load_meta(model_type: str = "lstm") -> dict:
    _, meta_path, _, _ = _paths(model_type)
    with open(meta_path, "rb") as f:
        return pickle.load(f)


def _load_scaler(model_type: str = "lstm") -> StandardScaler:
    _, _, scaler_path, _ = _paths(model_type)
    with open(scaler_path, "rb") as f:
        return pickle.load(f)


def _load_y_scaler(model_type: str = "lstm") -> StandardScaler:
    _, _, _, y_scaler_path = _paths(model_type)
    with open(y_scaler_path, "rb") as f:
        return pickle.load(f)


def _load_model(model_type: str = "lstm"):
    if not TF_AVAILABLE:
        raise RuntimeError("TensorFlow/Keras is not installed")
    model_path, _, _, _ = _paths(model_type)
    return tf.keras.models.load_model(str(model_path), compile=False)


def predict_forecast(
    feat_df: pd.DataFrame,
    item_id: int,
    model_type: str = "lstm",
) -> dict:
    """Generate 14-day forecast using saved LSTM/GRU model."""
    if not is_trained(model_type=model_type):
        return {"error": f"{model_type.upper()} model not trained"}

    meta = _load_meta(model_type)
    lookback = int(meta.get("lookback", 14))
    horizon = int(meta.get("horizon", FORECAST_HORIZON))
    features = meta.get("features", FEATURE_COLS)

    item_df = (
        feat_df[feat_df["item_id"] == item_id]
        .sort_values("usage_date")
        .reset_index(drop=True)
    )
    if len(item_df) < lookback:
        return {"error": "Insufficient history for recurrent forecast"}

    seq = item_df[features].tail(lookback).astype(float).to_numpy()
    scaler = _load_scaler(model_type)
    seq_scaled = scaler.transform(seq).reshape(1, lookback, len(features))

    model = _load_model(model_type)
    y_scaler = _load_y_scaler(model_type)
    pred_scaled = model.predict(seq_scaled, verbose=0)[0]
    pred = y_scaler.inverse_transform(np.asarray(pred_scaled).reshape(-1, 1)).reshape(-1)
    pred = np.maximum(0.0, np.asarray(pred, dtype=float))[:horizon]

    last_date = pd.Timestamp(item_df["usage_date"].iloc[-1]).normalize()
    forecast = []
    for i, val in enumerate(pred, start=1):
        target_date = last_date + pd.Timedelta(days=i)
        forecast.append(
            {
                "date": target_date.strftime("%Y-%m-%d"),
                "predicted": round(float(val), 1),
                "lower": round(max(0.0, float(val) * 0.8), 1),
                "upper": round(float(val) * 1.2, 1),
            }
        )

    return {
        "item_id": item_id,
        "item_name": item_df["item_name"].iloc[0] if "item_name" in item_df.columns else str(item_id),
        "model": model_type.upper(),
        "forecast": forecast,
        "metrics": meta,
    }
