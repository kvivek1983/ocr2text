from app.verification.cross_doc import CrossDocValidator


def test_name_match_across_docs():
    validator = CrossDocValidator()
    result = validator.validate(
        dl_name="RAJESH KUMAR",
        aadhaar_name="RAJESH KUMAR",
        dl_dob="1990-05-15",
        aadhaar_dob="1990-05-15",
        dl_cov=["LMV"],
        rc_vehicle_class="LMV",
    )
    assert result["passed"] is True
    assert result["name_match"] is True
    assert result["dob_match"] is True
    assert result["cov_match"] is True
