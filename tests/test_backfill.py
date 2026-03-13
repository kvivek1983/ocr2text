def test_backfill_transforms_rc_master_row():
    from scripts.backfill_mysql_pg import transform_rc_master_row
    mysql_row = {
        "rc_number": "MH47BL1775",
        "owner_name": "SHIVA SAI TRAVELS",
        "vehicle_chasi_number": "MBHCZFB3SPG458278",
        "vehicle_engine_number": "K12NP7316940",
        "fuel_type": "PETROL/CNG",
        "vehicle_category": "LPV",
        "rc_status": "ACTIVE",
        "fit_up_to": "2028-01-06",
        "insurance_upto": "2025-08-04",
        "body_type": "Sedan",
        "color": "White",
    }
    result = transform_rc_master_row(mysql_row)
    assert result["govt_registration_number"] == "MH47BL1775"
    assert result["govt_owner_name"] == "SHIVA SAI TRAVELS"
    assert result["govt_vehicle_class"] == "LPV"
    assert "body_type" in result["govt_fields"]
