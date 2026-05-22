import pandas as pd

from src.care_score import add_scores


def test_add_scores_creates_expected_columns():
    df = pd.DataFrame(
        {
            "senior_share": [0.10, 0.20],
            "living_alone_65_share": [0.20, 0.30],
            "disability_share": [0.08, 0.16],
            "median_income": [90000, 50000],
            "diabetes_prev": [8.0, 13.0],
            "chd_prev": [4.0, 8.0],
            "copd_prev": [3.5, 8.5],
            "poor_physical_health_prev": [9.0, 18.0],
            "healthcare_support_per_1k_seniors": [20.0, 8.0],
            "healthcare_support_wage": [42000, 39000],
        }
    )

    scored = add_scores(df)

    assert "care_demand_score" in scored.columns
    assert "access_constraint_score" in scored.columns
    assert "care_gap_score" in scored.columns
    assert scored["care_gap_score"].between(0, 100).all()
