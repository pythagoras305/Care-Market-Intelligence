import pandas as pd

from src.data_quality import add_confidence_flags


def test_add_confidence_flags_marks_complete_rows_high_confidence():
    df = pd.DataFrame(
        {
            "total_population": [10000],
            "senior_population": [2000],
            "senior_share": [0.20],
            "living_alone_65_share": [0.25],
            "disability_share": [0.12],
            "diabetes_prev": [9.5],
            "chd_prev": [5.2],
            "copd_prev": [6.1],
            "poor_physical_health_prev": [12.3],
            "median_income": [70000],
            "healthcare_support_workers": [120],
            "healthcare_support_per_1k_seniors": [60],
            "healthcare_support_wage": [41000],
            "wage_geo_level": ["state"],
        }
    )

    quality = add_confidence_flags(df)

    assert quality.loc[0, "confidence_level"] == "High"
    assert quality.loc[0, "confidence_notes"] == "complete core inputs"


def test_add_confidence_flags_marks_sparse_or_missing_rows_low_confidence():
    df = pd.DataFrame(
        {
            "total_population": [2000],
            "senior_population": [500],
            "senior_share": [0.25],
            "living_alone_65_share": [pd.NA],
            "disability_share": [0.12],
            "diabetes_prev": [9.5],
            "chd_prev": [pd.NA],
            "copd_prev": [6.1],
            "poor_physical_health_prev": [12.3],
            "median_income": [70000],
            "healthcare_support_workers": [0],
            "healthcare_support_per_1k_seniors": [0],
            "healthcare_support_wage": [39650],
            "wage_geo_level": ["national_fallback"],
        }
    )

    quality = add_confidence_flags(df)

    assert quality.loc[0, "confidence_level"] == "Low"
    assert "missing input" in quality.loc[0, "confidence_notes"]
    assert quality.loc[0, "zero_workforce_flag"]

