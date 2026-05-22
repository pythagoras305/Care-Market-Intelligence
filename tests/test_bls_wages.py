from src.bls_wages import state_healthcare_support_wage_series


def test_state_healthcare_support_wage_series_builds_bls_id():
    assert state_healthcare_support_wage_series("CA") == "OEUS060000000000031000004"
    assert state_healthcare_support_wage_series("TX") == "OEUS480000000000031000004"

