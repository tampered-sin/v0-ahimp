"""Sentiment analysis helpers for supplier review scoring."""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Callable


DEFAULT_SENTIMENT_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"
_POSITIVE_WORDS = {"good", "great", "excellent", "reliable", "fast", "helpful", "quality", "on-time"}
_NEGATIVE_WORDS = {"bad", "late", "delay", "poor", "terrible", "broken", "failed", "overpriced"}

_ANALYZER_CACHE: dict[str, dict[str, Any]] = {}
_PIPELINE_FN: Callable[[str], list[dict[str, Any]]] | None = None


def normalize_sentiment_to_100(sentiment_score: float) -> float:
    bounded = max(-1.0, min(1.0, float(sentiment_score)))
    return round((bounded + 1.0) * 50.0, 2)


def _label_to_signed_score(label: str, confidence: float) -> float:
    token = label.strip().upper()
    conf = max(0.0, min(1.0, float(confidence)))
    if "POS" in token:
        return conf
    if "NEG" in token:
        return -conf
    return 0.0


def _heuristic_sentiment(text: str) -> float:
    tokens = [tok.strip(".,!?;:\"'()[]{}").lower() for tok in text.split() if tok.strip()]
    if not tokens:
        return 0.0

    pos = sum(1 for tok in tokens if tok in _POSITIVE_WORDS)
    neg = sum(1 for tok in tokens if tok in _NEGATIVE_WORDS)
    score = (pos - neg) / max(1, len(tokens)) * 2.5
    return max(-1.0, min(1.0, score))


def _get_sentiment_pipeline() -> Callable[[str], list[dict[str, Any]]] | None:
    global _PIPELINE_FN
    if _PIPELINE_FN is not None:
        return _PIPELINE_FN

    try:
        from transformers import pipeline  # type: ignore

        _PIPELINE_FN = pipeline("sentiment-analysis", model=DEFAULT_SENTIMENT_MODEL)
        return _PIPELINE_FN
    except Exception:
        return None


def analyze_sentiment(review_text: str, use_cache: bool = True) -> dict[str, Any]:
    normalized_text = str(review_text or "").strip()
    cache_key = normalized_text.lower()

    if use_cache and cache_key in _ANALYZER_CACHE:
        return _ANALYZER_CACHE[cache_key]

    pipeline_fn = _get_sentiment_pipeline()
    model_used = DEFAULT_SENTIMENT_MODEL

    if pipeline_fn is not None and normalized_text:
        try:
            prediction = pipeline_fn(normalized_text[:512])[0]
            label = str(prediction.get("label", "NEUTRAL"))
            confidence = float(prediction.get("score", 0.0))
            sentiment_score = _label_to_signed_score(label, confidence)
        except Exception:
            model_used = "heuristic-fallback"
            sentiment_score = _heuristic_sentiment(normalized_text)
            label = "NEUTRAL" if abs(sentiment_score) < 0.05 else ("POSITIVE" if sentiment_score > 0 else "NEGATIVE")
    else:
        model_used = "heuristic-fallback"
        sentiment_score = _heuristic_sentiment(normalized_text)
        label = "NEUTRAL" if abs(sentiment_score) < 0.05 else ("POSITIVE" if sentiment_score > 0 else "NEGATIVE")

    result = {
        "text": normalized_text,
        "label": label,
        "sentiment_score": round(float(sentiment_score), 4),
        "normalized_score": normalize_sentiment_to_100(sentiment_score),
        "model": model_used,
        "analyzed_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    if use_cache:
        _ANALYZER_CACHE[cache_key] = result
    return result


def analyze_sentiment_batch(review_texts: list[str], use_cache: bool = True) -> dict[str, Any]:
    start = time.perf_counter()
    results = [analyze_sentiment(text, use_cache=use_cache) for text in review_texts]
    elapsed = max(1e-9, time.perf_counter() - start)

    return {
        "count": len(results),
        "results": results,
        "throughput_reviews_per_sec": round(len(results) / elapsed, 2),
    }


def clear_sentiment_cache() -> None:
    _ANALYZER_CACHE.clear()
