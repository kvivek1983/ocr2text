from app.verification.engine import AutoApprovalEngine


def test_auto_approve_valid_rc():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_rc(
        front_quality=0.85,
        back_quality=0.80,
        llm_status="success",
        govt_status="success",
        govt_match_score=0.92,
        govt_rc_status="ACTIVE",
        govt_fitness_upto="2028-01-06",
        govt_insurance_upto="2026-08-04",
        critical_fields_match=True,
    )
    assert decision.method == "auto_approved"


def test_auto_reject_inactive_rc():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_rc(
        front_quality=0.85,
        back_quality=0.80,
        llm_status="success",
        govt_status="success",
        govt_match_score=0.92,
        govt_rc_status="SUSPENDED",
        govt_fitness_upto="2028-01-06",
        govt_insurance_upto="2026-08-04",
        critical_fields_match=True,
    )
    assert decision.method == "auto_rejected"
    assert "not ACTIVE" in decision.reason


def test_manual_review_low_match():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_rc(
        front_quality=0.85,
        back_quality=0.80,
        llm_status="success",
        govt_status="success",
        govt_match_score=0.70,
        govt_rc_status="ACTIVE",
        govt_fitness_upto="2028-01-06",
        govt_insurance_upto="2026-08-04",
        critical_fields_match=False,
    )
    assert decision.method == "manual_review"


def test_auto_reject_expired_dl():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_dl(
        front_quality=0.85, back_quality=0.80,
        llm_status="success", govt_status="success",
        govt_match_score=0.92, govt_dl_status="ACTIVE",
        govt_validity_tr="2020-01-01",  # expired
        cov_covers_vehicle=True,
        critical_fields_match=True,
    )
    assert decision.method == "auto_rejected"
    assert "expired" in decision.reason.lower()


def test_auto_approve_valid_aadhaar():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_aadhaar(
        front_quality=0.85, back_quality=0.80,
        llm_status="success", govt_status="success",
        govt_match_score=0.90, govt_aadhaar_status="VALID",
        critical_fields_match=True,
    )
    assert decision.method == "auto_approved"
