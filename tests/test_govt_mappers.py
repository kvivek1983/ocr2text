from app.govt.mappers.gridlines import GridlinesMapper
from app.govt.mappers.cashfree import CashfreeMapper
from app.govt.mappers.hyperverge import HyperVergeMapper
from app.govt.schemas import RCGovtFields


def test_gridlines_rc_normalize():
    raw = {
        "data": {
            "rc_data": {
                "owner_data": {"name": "SHIVA SAI TRAVELS"},
                "vehicle_data": {
                    "chassis_number": "MBHCZFB3SPG458278",
                    "engine_number": "K12NP7316940",
                    "fuel_type": "PETROL/CNG",
                    "category": "LMV",
                },
                "status": "ACTIVE",
                "insurance_data": {"expiry_date": "2025-08-04"},
            }
        }
    }
    mapper = GridlinesMapper()
    fields = mapper.normalize(raw, "rc_book")
    assert isinstance(fields, RCGovtFields)
    assert fields.owner_name == "SHIVA SAI TRAVELS"
    assert fields.chassis_number == "MBHCZFB3SPG458278"
    assert fields.rc_status == "ACTIVE"
    assert fields.fitness_upto is None


def test_cashfree_rc_normalize():
    raw = {
        "owner": "SHIVA SAI TRAVELS",
        "chassis": "MBHCZFB3SPG458278",
        "engine": "K12NP7316940",
        "type": "PETROL/CNG",
        "class": "LMV",
        "rc_status": "ACTIVE",
        "reg_no": "MH47BL1775",
        "vehicle_insurance_upto": "2025-08-04",
    }
    mapper = CashfreeMapper()
    fields = mapper.normalize(raw, "rc_book")
    assert isinstance(fields, RCGovtFields)
    assert fields.owner_name == "SHIVA SAI TRAVELS"
    assert fields.registration_number == "MH47BL1775"


def test_hyperverge_rc_normalize_flat_format():
    raw = {
        "result": {
            "rcInfo": {
                "owner_name": "SHIVA SAI TRAVELS",
                "chassis_no": "MBHCZFB3SPG458278",
                "engine_no": "K12NP7316940",
                "fuel_descr": "PETROL/CNG",
                "vehicle_class_desc": "LMV",
                "status": "ACTIVE",
                "reg_no": "MH47BL1775",
                "fit_upto": "2028-01-06",
                "vehicle_insurance_details": {"insurance_upto": "2025-08-04"},
            }
        }
    }
    mapper = HyperVergeMapper()
    fields = mapper.normalize(raw, "rc_book")
    assert isinstance(fields, RCGovtFields)
    assert fields.owner_name == "SHIVA SAI TRAVELS"
    assert fields.fitness_upto == "2028-01-06"
    assert fields.registration_number == "MH47BL1775"
