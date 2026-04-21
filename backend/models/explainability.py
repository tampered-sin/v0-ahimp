"""
Explainability utilities for demand forecasts.

Provides SHAP (global + local) and LIME (local) explanations for tree-based
regression models used in AHIMP.
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
import pandas as pd


def _to_2d_array(data: pd.DataFrame | np.ndarray) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2:
        raise ValueError("Expected 2D feature matrix")
    return arr


def _stable_hash(arr: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(arr)
    return hashlib.md5(contiguous.tobytes()).hexdigest()


def _top_indices(values: np.ndarray, top_k: int) -> list[int]:
    if values.size == 0:
        return []
    order = np.argsort(np.abs(values))[::-1]
    return [int(i) for i in order[:top_k]]


class _SimpleCache:
    def __init__(self, max_size: int = 128):
        self.max_size = max_size
        self._store: OrderedDict[str, dict] = OrderedDict()

    def get(self, key: str) -> dict | None:
        value = self._store.get(key)
        if value is not None:
            self._store.move_to_end(key)
        return value

    def put(self, key: str, value: dict) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)


@dataclass
class ExplainabilityConfig:
    max_background_samples: int = 1000
    cache_size: int = 128


class SHAPExplainer:
    def __init__(self, cfg: ExplainabilityConfig | None = None):
        self.cfg = cfg or ExplainabilityConfig()
        self._global_cache = _SimpleCache(self.cfg.cache_size)
        self._local_cache = _SimpleCache(self.cfg.cache_size)

    def _sample_background(self, X: np.ndarray) -> np.ndarray:
        if len(X) <= self.cfg.max_background_samples:
            return X
        rng = np.random.default_rng(42)
        idx = rng.choice(len(X), size=self.cfg.max_background_samples, replace=False)
        return X[idx]

    def explain_global(
        self,
        model,
        X_background: pd.DataFrame | np.ndarray,
        feature_names: list[str],
    ) -> dict:
        X_bg = self._sample_background(_to_2d_array(X_background))
        cache_key = f"global:{type(model).__name__}:{_stable_hash(X_bg)}"
        cached = self._global_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            import shap
        except Exception as exc:
            return {
                "available": False,
                "importance": [],
                "sample_size": int(len(X_bg)),
                "error": f"SHAP unavailable: {exc}",
            }

        try:
            explainer = shap.TreeExplainer(model)
            shap_values = np.asarray(explainer.shap_values(X_bg))
            if shap_values.ndim == 3:
                shap_values = shap_values[0]

            mean_abs = np.abs(shap_values).mean(axis=0)
            importance = [
                {
                    "feature": feature_names[idx],
                    "mean_abs_shap": float(mean_abs[idx]),
                }
                for idx in range(len(feature_names))
            ]
            importance.sort(key=lambda x: x["mean_abs_shap"], reverse=True)

            payload = {
                "available": True,
                "importance": importance,
                "sample_size": int(len(X_bg)),
                "error": None,
            }
            self._global_cache.put(cache_key, payload)
            return payload
        except Exception as exc:
            return {
                "available": False,
                "importance": [],
                "sample_size": int(len(X_bg)),
                "error": f"SHAP computation failed: {exc}",
            }

    def explain_instance(
        self,
        model,
        X_background: pd.DataFrame | np.ndarray,
        instance: np.ndarray,
        feature_names: list[str],
        top_k: int = 8,
    ) -> dict:
        X_bg = self._sample_background(_to_2d_array(X_background))
        inst = np.asarray(instance, dtype=float).reshape(1, -1)
        cache_key = (
            f"local:{type(model).__name__}:{_stable_hash(X_bg)}:{_stable_hash(inst)}:{top_k}"
        )
        cached = self._local_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            import shap
        except Exception as exc:
            return {
                "available": False,
                "base_value": None,
                "prediction": None,
                "contributions": [],
                "top_contributions": [],
                "error": f"SHAP unavailable: {exc}",
            }

        try:
            explainer = shap.TreeExplainer(model)
            shap_values = np.asarray(explainer.shap_values(inst))
            if shap_values.ndim == 3:
                shap_values = shap_values[0]
            contrib = shap_values[0]

            expected = explainer.expected_value
            if isinstance(expected, (list, tuple, np.ndarray)):
                base_value = float(np.asarray(expected).reshape(-1)[0])
            else:
                base_value = float(expected)

            prediction = float(base_value + np.sum(contrib))

            rows = []
            for idx, feature in enumerate(feature_names):
                rows.append(
                    {
                        "feature": feature,
                        "feature_value": float(inst[0, idx]),
                        "shap_value": float(contrib[idx]),
                        "abs_shap": float(abs(contrib[idx])),
                    }
                )

            rows.sort(key=lambda x: x["abs_shap"], reverse=True)
            top_rows = rows[:top_k]

            payload = {
                "available": True,
                "base_value": base_value,
                "prediction": prediction,
                "contributions": rows,
                "top_contributions": top_rows,
                "error": None,
            }
            self._local_cache.put(cache_key, payload)
            return payload
        except Exception as exc:
            return {
                "available": False,
                "base_value": None,
                "prediction": None,
                "contributions": [],
                "top_contributions": [],
                "error": f"SHAP computation failed: {exc}",
            }


class LIMEExplainer:
    def __init__(self, cfg: ExplainabilityConfig | None = None):
        self.cfg = cfg or ExplainabilityConfig()
        self._cache = _SimpleCache(self.cfg.cache_size)

    def explain_instance(
        self,
        model,
        X_background: pd.DataFrame | np.ndarray,
        instance: np.ndarray,
        feature_names: list[str],
        top_k: int = 8,
        num_samples: int = 3000,
    ) -> dict:
        X_bg = _to_2d_array(X_background)
        inst = np.asarray(instance, dtype=float).reshape(-1)
        cache_key = (
            f"lime:{type(model).__name__}:{_stable_hash(X_bg)}:{_stable_hash(inst.reshape(1, -1))}:{top_k}:{num_samples}"
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            from lime.lime_tabular import LimeTabularExplainer
        except Exception as exc:
            return {
                "available": False,
                "prediction": None,
                "score": None,
                "weights": [],
                "error": f"LIME unavailable: {exc}",
            }

        try:
            explainer = LimeTabularExplainer(
                training_data=X_bg,
                feature_names=feature_names,
                mode="regression",
                discretize_continuous=True,
                random_state=42,
            )
            exp = explainer.explain_instance(
                data_row=inst,
                predict_fn=model.predict,
                num_features=min(top_k, len(feature_names)),
                num_samples=num_samples,
            )

            weights = [
                {"feature": str(desc), "weight": float(weight)}
                for desc, weight in exp.as_list()
            ]

            local_pred = getattr(exp, "local_pred", None)
            prediction = None
            if local_pred is not None:
                prediction = float(np.asarray(local_pred).reshape(-1)[0])

            payload = {
                "available": True,
                "prediction": prediction,
                "score": float(getattr(exp, "score", 0.0)),
                "weights": weights,
                "error": None,
            }
            self._cache.put(cache_key, payload)
            return payload
        except Exception as exc:
            return {
                "available": False,
                "prediction": None,
                "score": None,
                "weights": [],
                "error": f"LIME computation failed: {exc}",
            }


def build_item_explanation(
    model,
    feat_df: pd.DataFrame,
    item_id: int,
    feature_names: list[str],
    shap_explainer: SHAPExplainer,
    lime_explainer: LIMEExplainer,
    top_k: int = 8,
    target_usage_date: pd.Timestamp | None = None,
) -> dict:
    if feat_df.empty:
        return {"error": "No feature data available"}

    item_rows = feat_df[feat_df["item_id"] == item_id].sort_values("usage_date")
    if item_rows.empty:
        return {"error": "No data for this item"}

    if target_usage_date is not None:
        eligible = item_rows[item_rows["usage_date"] <= target_usage_date]
        if eligible.empty:
            chosen = item_rows.iloc[-1]
        else:
            chosen = eligible.iloc[-1]
    else:
        chosen = item_rows.iloc[-1]

    X_bg = feat_df[feature_names].to_numpy(dtype=float)
    instance = chosen[feature_names].to_numpy(dtype=float)

    shap_global = shap_explainer.explain_global(model, X_bg, feature_names)
    shap_local = shap_explainer.explain_instance(model, X_bg, instance, feature_names, top_k=top_k)
    lime_local = lime_explainer.explain_instance(model, X_bg, instance, feature_names, top_k=top_k)

    top_idx = _top_indices(instance, top_k=min(top_k, len(instance)))
    feature_snapshot = [
        {
            "feature": feature_names[idx],
            "value": float(instance[idx]),
        }
        for idx in top_idx
    ]

    return {
        "item_id": int(item_id),
        "item_name": str(chosen.get("item_name", item_id)),
        "usage_date": str(pd.Timestamp(chosen["usage_date"]).date()),
        "feature_snapshot": feature_snapshot,
        "shap": {
            "global": shap_global,
            "local": shap_local,
            "force_plot": {
                "base_value": shap_local.get("base_value"),
                "prediction": shap_local.get("prediction"),
                "top_features": shap_local.get("top_contributions", []),
            },
        },
        "lime": lime_local,
    }
