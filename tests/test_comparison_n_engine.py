import pytest
from unittest.mock import MagicMock
from app.comparison.comparator import Comparator
from app.comparison.metrics import calculate_comparison_metrics


class TestNEngineMetrics:
    def test_two_engines_full_agreement(self):
        """Two engines with identical fields should have full agreement."""
        engine_fields = {
            "engine_a": [
                {"label": "registration_number", "value": "KA01AB1234"},
                {"label": "owner_name", "value": "RAJESH KUMAR"},
            ],
            "engine_b": [
                {"label": "registration_number", "value": "KA01AB1234"},
                {"label": "owner_name", "value": "RAJESH KUMAR"},
            ],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert result["agreement_rate"] == 1.0
        assert result["total_fields"] > 0

    def test_two_engines_partial_agreement(self):
        """Different values for same field should be partial agreement."""
        engine_fields = {
            "engine_a": [
                {"label": "registration_number", "value": "KA01AB1234"},
                {"label": "owner_name", "value": "RAJESH KUMAR"},
            ],
            "engine_b": [
                {"label": "registration_number", "value": "KA01AB1234"},
                {"label": "owner_name", "value": "RAJESH K"},
            ],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert 0 < result["agreement_rate"] < 1.0

    def test_three_engines_full_agreement(self):
        """Three engines all agreeing should have full agreement."""
        engine_fields = {
            "engine_a": [{"label": "registration_number", "value": "KA01AB1234"}],
            "engine_b": [{"label": "registration_number", "value": "KA01AB1234"}],
            "engine_c": [{"label": "registration_number", "value": "KA01AB1234"}],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert result["agreement_rate"] == 1.0

    def test_three_engines_mixed_agreement(self):
        """Two agree, one disagrees should have partial agreement."""
        engine_fields = {
            "engine_a": [{"label": "registration_number", "value": "KA01AB1234"}],
            "engine_b": [{"label": "registration_number", "value": "KA01AB1234"}],
            "engine_c": [{"label": "registration_number", "value": "KA01AB5678"}],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert result["agreement_rate"] > 0  # at least some agreement

    def test_field_agreement_matrix(self):
        """Should return per-field agreement status."""
        engine_fields = {
            "engine_a": [
                {"label": "registration_number", "value": "KA01AB1234"},
                {"label": "owner_name", "value": "RAJESH KUMAR"},
            ],
            "engine_b": [
                {"label": "registration_number", "value": "KA01AB1234"},
                {"label": "owner_name", "value": "RAJESH K"},
            ],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert "field_agreement" in result
        assert "registration_number" in result["field_agreement"]
        assert "owner_name" in result["field_agreement"]

    def test_field_agreement_status_types(self):
        """Each field should have status: full, partial, or disagreement."""
        engine_fields = {
            "engine_a": [
                {"label": "registration_number", "value": "KA01AB1234"},
            ],
            "engine_b": [
                {"label": "registration_number", "value": "KA01AB1234"},
            ],
        }
        result = calculate_comparison_metrics(engine_fields)
        field_status = result["field_agreement"]["registration_number"]
        assert field_status["status"] in ["full", "partial", "disagreement"]

    def test_single_engine_returns_results(self):
        """Single engine should still return valid results."""
        engine_fields = {
            "engine_a": [
                {"label": "registration_number", "value": "KA01AB1234"},
            ],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert "agreement_rate" in result
        assert result["agreement_rate"] == 1.0  # single engine agrees with itself

    def test_empty_fields_handled(self):
        """Engines with no fields should not crash."""
        engine_fields = {
            "engine_a": [],
            "engine_b": [],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert "agreement_rate" in result

    def test_engine_results_included(self):
        """Result should include per-engine field results."""
        engine_fields = {
            "engine_a": [{"label": "registration_number", "value": "KA01AB1234"}],
            "engine_b": [{"label": "registration_number", "value": "KA01AB5678"}],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert "engine_results" in result
        assert "engine_a" in result["engine_results"]
        assert "engine_b" in result["engine_results"]


class TestNEngineComparator:
    def test_comparator_accepts_n_engines(self):
        """Comparator should accept a dict of N engines."""
        engines = {
            "engine_a": MagicMock(),
            "engine_b": MagicMock(),
            "engine_c": MagicMock(),
        }
        comparator = Comparator(engines=engines)
        assert len(comparator.engines) == 3

    def test_comparator_runs_all_engines(self):
        """Comparator.compare should run all engines."""
        mock_a = MagicMock()
        mock_a.extract.return_value = "Registration No: KA01AB1234"
        mock_a.get_name.return_value = "engine_a"

        mock_b = MagicMock()
        mock_b.extract.return_value = "Registration No: KA01AB1234"
        mock_b.get_name.return_value = "engine_b"

        engines = {"engine_a": mock_a, "engine_b": mock_b}
        comparator = Comparator(engines=engines)

        result = comparator.compare(b"fake_image_data", document_type="rc_book")

        mock_a.extract.assert_called_once()
        mock_b.extract.assert_called_once()
        assert "metrics" in result
        assert "engine_results" in result
