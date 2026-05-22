import pandas as pd

from src.market_opportunity import add_market_opportunity, estimate_roi


def test_add_market_opportunity_creates_business_score():
    df = pd.DataFrame(
        {
            "care_gap_score": [80.0, 40.0],
            "senior_population": [50000, 10000],
            "median_income": [90000, 50000],
            "healthcare_support_per_1k_seniors": [10.0, 30.0],
        }
    )

    scored = add_market_opportunity(df)

    assert "business_opportunity_score" in scored.columns
    assert "market_action" in scored.columns
    assert scored["business_opportunity_score"].notna().all()


def test_estimate_roi_creates_financial_outputs():
    df = pd.DataFrame(
        {
            "senior_population": [50000],
            "business_opportunity_score": [70.0],
        }
    )

    roi = estimate_roi(
        df,
        monthly_revenue_per_client=2200,
        gross_margin=0.30,
        outreach_rate=0.01,
        conversion_rate=0.08,
        clients_per_caregiver=3,
        recruiting_cost_per_caregiver=900,
        fixed_launch_cost=5000,
    )

    assert roi.loc[0, "estimated_clients"] > 0
    assert roi.loc[0, "monthly_revenue"] > 0
    assert roi.loc[0, "caregivers_needed"] > 0
