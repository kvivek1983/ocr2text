# tests/test_comparison.py
from app.comparison.metrics import calculate_comparison_metrics
from app.comparison.comparator import EngineComparator
from unittest.mock import MagicMock


def test_calculate_metrics_exact_match():
    paddle_fields = [
        {"label": "vendor", "value": "Big Bazaar"},
        {"label": "total", "value": "1234"},
    ]
    google_fields = [
        {"label": "vendor", "value": "Big Bazaar"},
        {"label": "total", "value": "1234"},
    ]
    metrics = calculate_comparison_metrics(paddle_fields, google_fields)
    assert metrics["total_fields"] == 2
    assert metrics["exact_match"] == 2
    assert metrics["mismatch"] == 0


def test_calculate_metrics_partial_match():
    paddle_fields = [
        {"label": "total", "value": "1234"},
    ]
    google_fields = [
        {"label": "total", "value": "\u20b91,234.00"},
    ]
    metrics = calculate_comparison_metrics(paddle_fields, google_fields)
    assert metrics["partial_match"] >= 1 or metrics["mismatch"] >= 1


def test_calculate_metrics_one_engine_only():
    paddle_fields = [
        {"label": "vendor", "value": "Big Bazaar"},
    ]
    google_fields = [
        {"label": "vendor", "value": "Big Bazaar"},
        {"label": "date", "value": "15/01/2024"},
    ]
    metrics = calculate_comparison_metrics(paddle_fields, google_fields)
    assert metrics["google_only"] == 1


def test_comparator_runs_both_engines():
    mock_paddle = MagicMock()
    mock_paddle.extract.return_value = {
        "raw_text": "Vendor: Big Bazaar\nTotal: 1234",
        "confidence": 0.90,
        "blocks": [],
        "processing_time_ms": 100,
    }
    mock_paddle.get_name.return_value = "paddle"

    mock_google = MagicMock()
    mock_google.extract.return_value = {
        "raw_text": "Vendor: Big Bazaar\nTotal: \u20b91,234.00",
        "confidence": 0.95,
        "blocks": [],
        "processing_time_ms": 200,
    }
    mock_google.get_name.return_value = "google"

    comparator = EngineComparator(mock_paddle, mock_google)
    result = comparator.compare(b"fake_image")

    assert "paddle" in result
    assert "google" in result
    assert "comparison" in result
    assert result["paddle"]["confidence"] == 0.90
    assert result["google"]["confidence"] == 0.95
