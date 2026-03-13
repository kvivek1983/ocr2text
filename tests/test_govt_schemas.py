from app.govt.schemas import RCGovtFields, DLGovtFields, AadhaarGovtFields, GovtVerificationResult

def test_rc_govt_fields():
    f = RCGovtFields(owner_name="SHIVA SAI", rc_status="ACTIVE")
    assert f.owner_name == "SHIVA SAI"
    assert f.chassis_number is None

def test_govt_verification_result():
    r = GovtVerificationResult(status="success", reseller_code="gridlines", normalized_fields={"owner_name": "TEST"}, raw_response={"data": {}})
    assert r.status == "success"
