import pandas as pd

from src.ingest_public_data import clean_places_frame, combine_features, sum_from_reporter


def test_clean_places_frame_pivots_measures():
    raw = pd.DataFrame(
        [
            {"locationid": "06037", "measureid": "DIABETES", "data_value_type": "Crude prevalence", "data_value": "9.6"},
            {"locationid": "06037", "measureid": "CHD", "data_value_type": "Crude prevalence", "data_value": "5.5"},
            {"locationid": "06037", "measureid": "COPD", "data_value_type": "Crude prevalence", "data_value": "5.1"},
            {"locationid": "06037", "measureid": "PHLTH", "data_value_type": "Crude prevalence", "data_value": "12.7"},
        ]
    )

    cleaned = clean_places_frame(raw)

    assert cleaned.loc[0, "fips"] == "06037"
    assert cleaned.loc[0, "diabetes_prev"] == 9.6
    assert cleaned.loc[0, "poor_physical_health_prev"] == 12.7


def test_combine_features_builds_model_ready_columns():
    acs = pd.DataFrame(
        {
            "fips": ["06037"],
            "county_name": ["Los Angeles County"],
            "state_name": ["California"],
            "total_population": [1000],
            "senior_population": [200],
            "living_alone_65_share": [25.0],
            "disability_share": [12.0],
            "median_income": [75000],
            "male_healthcare_support_workers": [10],
            "female_healthcare_support_workers": [30],
        }
    )
    places = pd.DataFrame(
        {
            "fips": ["06037"],
            "diabetes_prev": [9.6],
            "chd_prev": [5.5],
            "copd_prev": [5.1],
            "poor_physical_health_prev": [12.7],
        }
    )

    features = combine_features(acs, places)

    assert features.loc[0, "senior_share"] == 0.2
    assert features.loc[0, "living_alone_65_share"] == 0.25
    assert features.loc[0, "healthcare_support_per_1k_seniors"] == 200
    assert features.loc[0, "wage_geo_level"] == "national_placeholder"


def test_combine_features_joins_state_bls_wages():
    acs = pd.DataFrame(
        {
            "fips": ["06037"],
            "county_name": ["Los Angeles County"],
            "state_name": ["California"],
            "total_population": [1000],
            "senior_population": [200],
            "living_alone_65_share": [25.0],
            "disability_share": [12.0],
            "median_income": [75000],
            "male_healthcare_support_workers": [10],
            "female_healthcare_support_workers": [30],
        }
    )
    places = pd.DataFrame(
        {
            "fips": ["06037"],
            "diabetes_prev": [9.6],
            "chd_prev": [5.5],
            "copd_prev": [5.1],
            "poor_physical_health_prev": [12.7],
        }
    )
    bls_wages = pd.DataFrame(
        {
            "state": ["CA"],
            "healthcare_support_wage": [41640],
            "wage_geo_level": ["state"],
            "wage_year": [2025],
            "wage_source": ["BLS OEWS annual mean wage, SOC 31-0000"],
        }
    )

    features = combine_features(acs, places, bls_wages=bls_wages)

    assert features.loc[0, "healthcare_support_wage"] == 41640
    assert features.loc[0, "wage_geo_level"] == "state"


def test_sum_from_reporter_ignores_missing_values():
    data = {"B01001": {"estimate": {"B01001020": 10, "B01001021": None, "B01001022": 5}}}

    assert sum_from_reporter(data, "B01001", ["B01001020", "B01001021", "B01001022"]) == 15
