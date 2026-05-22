from __future__ import annotations

import math

import pandas as pd

from src.care_score import minmax_scale


def add_market_opportunity(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()

    market_size_source = (
        scored["senior_population"]
        if "senior_population" in scored
        else scored["senior_share"]
    )

    scored["market_size_score"] = minmax_scale(market_size_source)
    scored["affordability_score"] = minmax_scale(scored["median_income"])
    scored["workforce_gap_score"] = 100 - minmax_scale(scored["healthcare_support_per_1k_seniors"])
    scored["business_opportunity_score"] = (
        scored["care_gap_score"] * 0.35
        + scored["market_size_score"] * 0.25
        + scored["affordability_score"] * 0.20
        + scored["workforce_gap_score"] * 0.20
    )

    opportunity_rank = scored["business_opportunity_score"].rank(method="first", ascending=False, pct=True)
    gap_rank = scored["care_gap_score"].rank(method="first", ascending=False, pct=True)

    scored["market_action"] = "Monitor"
    scored.loc[opportunity_rank <= 0.35, "market_action"] = "Outreach"
    scored.loc[opportunity_rank <= 0.10, "market_action"] = "Expand"
    scored.loc[
        (gap_rank <= 0.10) & (opportunity_rank > 0.35),
        "market_action",
    ] = "Validate"

    return scored


def estimate_roi(
    df: pd.DataFrame,
    monthly_revenue_per_client: float,
    gross_margin: float,
    outreach_rate: float,
    conversion_rate: float,
    clients_per_caregiver: float,
    recruiting_cost_per_caregiver: float,
    fixed_launch_cost: float,
) -> pd.DataFrame:
    roi = df.copy()
    if "senior_population" not in roi:
        roi["senior_population"] = pd.NA

    opportunity_multiplier = (roi["business_opportunity_score"].fillna(0) / 100).clip(lower=0, upper=1)
    roi["estimated_leads"] = roi["senior_population"] * outreach_rate
    roi["estimated_clients"] = roi["estimated_leads"] * conversion_rate * (0.5 + opportunity_multiplier)
    roi["caregivers_needed"] = roi["estimated_clients"].apply(
        lambda clients: math.ceil(clients / clients_per_caregiver) if pd.notna(clients) and clients > 0 else 0
    )
    roi["monthly_revenue"] = roi["estimated_clients"] * monthly_revenue_per_client
    roi["monthly_gross_profit"] = roi["monthly_revenue"] * gross_margin
    roi["launch_investment"] = roi["caregivers_needed"] * recruiting_cost_per_caregiver + fixed_launch_cost
    roi["payback_months"] = roi.apply(
        lambda row: row["launch_investment"] / row["monthly_gross_profit"]
        if pd.notna(row["monthly_gross_profit"]) and row["monthly_gross_profit"] > 0
        else pd.NA,
        axis=1,
    )
    roi["first_year_gross_profit"] = roi["monthly_gross_profit"] * 12 - roi["launch_investment"]
    return roi
