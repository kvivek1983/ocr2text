def test_backtest_computes_accuracy_report():
    from scripts.backtest import compute_accuracy_report
    comparisons = [
        {"field_name": "registration_number", "is_match": True, "source": "llm_vs_govt"},
        {"field_name": "registration_number", "is_match": True, "source": "llm_vs_govt"},
        {"field_name": "owner_name", "is_match": True, "source": "llm_vs_govt"},
        {"field_name": "owner_name", "is_match": False, "source": "llm_vs_govt"},
        {"field_name": "chassis_number", "is_match": True, "source": "llm_vs_govt"},
    ]
    report = compute_accuracy_report(comparisons)
    assert report["registration_number"]["accuracy"] == 1.0
    assert report["owner_name"]["accuracy"] == 0.5
