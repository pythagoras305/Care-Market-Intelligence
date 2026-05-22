from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEMAND_FEATURES = [
    "senior_share",
    "living_alone_65_share",
    "disability_share",
    "diabetes_prev",
    "chd_prev",
    "copd_prev",
    "poor_physical_health_prev",
]

ACCESS_FEATURES = [
    "healthcare_support_per_1k_seniors",
    "median_income",
    "healthcare_support_wage",
]


@dataclass(frozen=True)
class ScoreWeights:
    senior_share: float = 0.25
    living_alone_65_share: float = 0.15
    disability_share: float = 0.20
    diabetes_prev: float = 0.10
    chd_prev: float = 0.10
    copd_prev: float = 0.10
    poor_physical_health_prev: float = 0.10


def minmax_scale(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    span = values.max() - values.min()
    if pd.isna(span) or span == 0:
        return pd.Series(50.0, index=series.index)
    return ((values - values.min()) / span) * 100


def add_scores(df: pd.DataFrame, weights: ScoreWeights | None = None) -> pd.DataFrame:
    weights = weights or ScoreWeights()
    scored = df.copy()
    if "healthcare_support_per_1k_seniors" not in scored and "home_health_aide_per_1k_seniors" in scored:
        scored["healthcare_support_per_1k_seniors"] = scored["home_health_aide_per_1k_seniors"]
    if "poor_physical_health_prev" not in scored and "poor_health_days" in scored:
        scored["poor_physical_health_prev"] = scored["poor_health_days"]

    for feature in DEMAND_FEATURES + ACCESS_FEATURES:
        scored[f"{feature}_score"] = minmax_scale(scored[feature])

    scored["care_demand_score"] = sum(
        scored[f"{feature}_score"] * getattr(weights, feature)
        for feature in DEMAND_FEATURES
    )

    workforce_score = scored["healthcare_support_per_1k_seniors_score"]
    affordability_score = scored["median_income_score"]
    wage_pressure_score = scored["healthcare_support_wage_score"]

    scored["access_constraint_score"] = (
        (100 - workforce_score) * 0.55
        + (100 - affordability_score) * 0.30
        + wage_pressure_score * 0.15
    )

    scored["care_gap_score"] = (
        scored["care_demand_score"] * 0.65
        + scored["access_constraint_score"] * 0.35
    )

    risk_rank = scored["care_gap_score"].rank(method="first", ascending=False, pct=True)
    scored["priority_tier"] = "Monitor"
    scored.loc[risk_rank <= 0.35, "priority_tier"] = "Develop"
    scored.loc[risk_rank <= 0.10, "priority_tier"] = "Prioritize"

    return scored.sort_values("care_gap_score", ascending=False).reset_index(drop=True)


def load_sample_data(path: str = "data/sample_county_care_features.csv") -> pd.DataFrame:
    return pd.read_csv(path, dtype={"fips": str})


def load_feature_data(
    public_path: str = "data/public_county_care_features.csv",
    sample_path: str = "data/sample_county_care_features.csv",
) -> pd.DataFrame:
    path = Path(public_path)
    if not path.exists():
        path = Path(sample_path)
    return pd.read_csv(path, dtype={"fips": str})
