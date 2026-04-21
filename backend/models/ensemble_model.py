"""
Ensemble voting predictor (TASK-105 starter).

Combines model predictions via weighted averaging with graceful fallback when
some models are unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EnsembleWeights:
    xgb: float = 0.4
    lgbm: float = 0.3
    lstm: float = 0.2
    gru: float = 0.0
    lr: float = 0.1


class VotingPredictor:
    """Weighted prediction combiner with confidence scoring."""

    def __init__(
        self,
        weights: EnsembleWeights | None = None,
        custom_weights: dict[str, float] | None = None,
    ) -> None:
        self.weights = weights or EnsembleWeights()
        self.custom_weights = custom_weights or {}

    def _weights_map(self) -> dict[str, float]:
        return {
            "xgb": self.weights.xgb,
            "lgbm": self.weights.lgbm,
            "lstm": self.weights.lstm,
            "gru": self.weights.gru,
            "lr": self.weights.lr,
            **self.custom_weights,
        }

    def combine(self, predictions: dict[str, np.ndarray]) -> np.ndarray:
        """
        Combine per-model predictions using available weights.

        Args:
            predictions: map like {'xgb': arr, 'lgbm': arr, ...}

        Returns:
            Weighted average prediction array
        """
        if not predictions:
            raise ValueError("No predictions provided")

        weights = self._weights_map()
        available = [name for name in predictions if name in weights]
        if not available:
            raise ValueError("No supported model keys in predictions")

        total_weight = sum(weights[name] for name in available)
        if total_weight <= 0:
            raise ValueError("Total weight must be > 0")

        first_shape = np.asarray(predictions[available[0]]).shape
        for name in available:
            if np.asarray(predictions[name]).shape != first_shape:
                raise ValueError("All prediction arrays must have the same shape")

        output = np.zeros(first_shape, dtype=float)
        for name in available:
            output += np.asarray(predictions[name], dtype=float) * (weights[name] / total_weight)

        return output

    def confidence(self, predictions: dict[str, np.ndarray]) -> np.ndarray:
        """Return confidence as inverse dispersion across model outputs."""
        if not predictions:
            raise ValueError("No predictions provided")

        arrs = [np.asarray(v, dtype=float) for v in predictions.values()]
        stacked = np.stack(arrs, axis=0)
        std = np.std(stacked, axis=0)
        return 1.0 / (1.0 + std)


def select_best_single_model(
    predictions: dict[str, np.ndarray],
    target: np.ndarray | None = None,
) -> tuple[str, np.ndarray]:
    """Return best single model forecast using optional target error."""
    if not predictions:
        raise ValueError("No predictions provided")

    if target is None:
        best_key = sorted(predictions.keys())[0]
        return best_key, np.asarray(predictions[best_key], dtype=float)

    y = np.asarray(target, dtype=float)
    best_key = ""
    best_loss = float("inf")
    for key, values in predictions.items():
        pred = np.asarray(values, dtype=float)
        if pred.shape != y.shape:
            continue
        loss = float(np.mean((pred - y) ** 2))
        if loss < best_loss:
            best_loss = loss
            best_key = key

    if not best_key:
        best_key = sorted(predictions.keys())[0]

    return best_key, np.asarray(predictions[best_key], dtype=float)


def tune_weights_via_grid(
    predictions: dict[str, np.ndarray],
    target: np.ndarray,
    step: float = 0.1,
) -> dict[str, float]:
    """Tune ensemble weights via coarse grid search on validation target."""
    if not predictions:
        raise ValueError("No predictions provided")
    if step <= 0 or step > 1:
        raise ValueError("step must be in (0, 1]")

    y = np.asarray(target, dtype=float)
    keys = [key for key in sorted(predictions.keys())]
    arrays = {k: np.asarray(predictions[k], dtype=float) for k in keys}
    for arr in arrays.values():
        if arr.shape != y.shape:
            raise ValueError("Prediction and target shapes must match")

    if len(keys) == 1:
        return {keys[0]: 1.0}

    ticks = int(round(1.0 / step))
    ticks = max(ticks, 1)
    step = 1.0 / ticks

    best_weights: dict[str, float] | None = None
    best_loss = float("inf")

    def _recurse(idx: int, remaining: int, current: list[int]):
        nonlocal best_loss, best_weights
        if idx == len(keys) - 1:
            current.append(remaining)
            weights = np.asarray(current, dtype=float) / float(ticks)
            pred = np.zeros_like(y, dtype=float)
            for key, w in zip(keys, weights):
                pred += arrays[key] * w
            loss = float(np.mean((pred - y) ** 2))
            if loss < best_loss:
                best_loss = loss
                best_weights = {k: float(w) for k, w in zip(keys, weights)}
            current.pop()
            return

        for value in range(remaining + 1):
            current.append(value)
            _recurse(idx + 1, remaining - value, current)
            current.pop()

    _recurse(0, ticks, [])

    if not best_weights:
        return {key: 1.0 / len(keys) for key in keys}
    return best_weights
