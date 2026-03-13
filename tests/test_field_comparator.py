from app.verification.comparator import FieldComparator


def test_exact_match_chassis():
    comp = FieldComparator()
    result = comp.compare_field(
        field_name="chassis_number",
        mapper_value="MBHCZFB3SPG458278",
        llm_value="MBHCZFB3SPG458278",
        govt_value="MBHCZFB3SPG458278",
    )
    assert result["is_match"] is True
    assert result["similarity_score"] == 1.0


def test_fuzzy_match_owner_name():
    comp = FieldComparator()
    result = comp.compare_field(
        field_name="owner_name",
        mapper_value="SHIVA SAI TRAVEL",
        llm_value="SHIVA SAI TRAVELS",
        govt_value="SHIVA SAI TRAVELS",
    )
    assert result["is_match"] is True
    assert result["similarity_score"] > 0.85


def test_compute_match_score():
    comp = FieldComparator()
    comparisons = [
        {"field_name": "chassis_number", "is_match": True, "similarity_score": 1.0},
        {"field_name": "engine_number", "is_match": True, "similarity_score": 1.0},
        {"field_name": "owner_name", "is_match": True, "similarity_score": 0.9},
        {"field_name": "registration_number", "is_match": True, "similarity_score": 1.0},
        {"field_name": "fuel_type", "is_match": False, "similarity_score": 0.5},
    ]
    score = comp.compute_match_score(comparisons)
    assert 0.85 < score < 1.0
