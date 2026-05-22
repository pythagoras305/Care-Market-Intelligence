from __future__ import annotations

import pandas as pd

from src.care_score import ACCESS_FEATURES, DEMAND_FEATURES


QUALITY_FEATURES = [
    "total_population",
    "senior_population",
    *DEMAND_FEATURES,
    *ACCESS_FEATURES,
]

SPARSE_SENIOR_POPULATION_THRESHOLD = 1_000


def add_confidence_flags(df: pd.DataFrame) -> pd.DataFrame:
    quality = df.copy()
    available_quality_features = [column for column in QUALITY_FEATURES if column in quality.columns]

    quality["missing_feature_count"] = quality[available_quality_features].isna().sum(axis=1)
    quality["missing_features"] = quality.apply(
        lambda row: ", ".join(column for column in available_quality_features if pd.isna(row[column])),
        axis=1,
    )
    senior_population = quality["senior_population"] if "senior_population" in quality else pd.Series(pd.NA, index=quality.index)
    healthcare_support_workers = (
        quality["healthcare_support_workers"]
        if "healthcare_support_workers" in quality
        else pd.Series(pd.NA, index=quality.index)
    )
    quality["small_senior_population_flag"] = (
        pd.to_numeric(senior_population, errors="coerce") < SPARSE_SENIOR_POPULATION_THRESHOLD
    )
    quality["zero_workforce_flag"] = (
        pd.to_numeric(healthcare_support_workers, errors="coerce").fillna(0) <= 0
    )
    if "wage_geo_level" in quality:
        wage_geo_level = quality["wage_geo_level"]
    else:
        wage_geo_level = pd.Series("", index=quality.index)
    quality["wage_fallback_flag"] = wage_geo_level.astype(str).str.contains(
        "fallback|national", case=False, na=False
    )

    risk_flags = (
        quality["small_senior_population_flag"].astype(int)
        + quality["zero_workforce_flag"].astype(int)
        + quality["wage_fallback_flag"].astype(int)
    )
    quality["confidence_level"] = "High"
    quality.loc[(quality["missing_feature_count"] > 0) | (risk_flags > 0), "confidence_level"] = "Medium"
    quality.loc[(quality["missing_feature_count"] > 1) | (risk_flags > 1), "confidence_level"] = "Low"

    quality["confidence_notes"] = quality.apply(_confidence_notes, axis=1)
    return quality


def _confidence_notes(row: pd.Series) -> str:
    notes = []
    if row["missing_feature_count"]:
        notes.append(f"{int(row['missing_feature_count'])} missing input(s)")
    if row["small_senior_population_flag"]:
        notes.append("small senior population")
    if row["zero_workforce_flag"]:
        notes.append("zero reported workforce")
    if row["wage_fallback_flag"]:
        notes.append("national wage fallback")
    return "; ".join(notes) if notes else "complete core inputs"
