from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import agents.sentiment_analyzer as sentiment_analyzer


def test_analyze_sentiment_with_mocked_pipeline(monkeypatch):
    sentiment_analyzer.clear_sentiment_cache()

    monkeypatch.setattr(
        sentiment_analyzer,
        "_get_sentiment_pipeline",
        lambda: (lambda text: [{"label": "POSITIVE", "score": 0.91}]),
    )

    result = sentiment_analyzer.analyze_sentiment("delivery was excellent")

    assert result["label"] == "POSITIVE"
    assert result["sentiment_score"] > 0
    assert result["normalized_score"] > 90


def test_analyze_sentiment_fallback_negative(monkeypatch):
    sentiment_analyzer.clear_sentiment_cache()

    monkeypatch.setattr(sentiment_analyzer, "_get_sentiment_pipeline", lambda: None)

    result = sentiment_analyzer.analyze_sentiment("terrible delay and bad quality")

    assert result["model"] == "heuristic-fallback"
    assert result["sentiment_score"] < 0


def test_analyze_sentiment_batch_reports_throughput(monkeypatch):
    sentiment_analyzer.clear_sentiment_cache()

    monkeypatch.setattr(sentiment_analyzer, "_get_sentiment_pipeline", lambda: None)

    out = sentiment_analyzer.analyze_sentiment_batch(
        ["good quality", "late shipment", "reliable partner"]
    )

    assert out["count"] == 3
    assert out["throughput_reviews_per_sec"] > 0
