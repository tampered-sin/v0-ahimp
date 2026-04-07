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
    lr: float = 0.1


class VotingPredictor:
    """Weighted prediction combiner with confidence scoring."""

    def __init__(self, weights: EnsembleWeights | None = None) -> None:
        self.weights = weights or EnsembleWeights()

    def _weights_map(self) -> dict[str, float]:
        return {
            "xgb": self.weights.xgb,
            "lgbm": self.weights.lgbm,
            "lstm": self.weights.lstm,
            "lr": self.weights.lr,
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
