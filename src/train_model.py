from __future__ import annotations

from pathlib import Path

import pandas as pd
import numpy as np

try:
    from .care_score import DEMAND_FEATURES, ACCESS_FEATURES, add_scores, load_feature_data
except ImportError:
    from care_score import DEMAND_FEATURES, ACCESS_FEATURES, add_scores, load_feature_data


OUTPUT_DIR = Path("outputs")


def _fallback_importance(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    label = df["high_gap"]
    rows = []
    for feature in features:
        corr = np.corrcoef(df[feature], label)[0, 1]
        rows.append({"feature": feature, "importance": 0.0 if np.isnan(corr) else abs(corr)})

    importance = pd.DataFrame(rows)
    total = importance["importance"].sum()
    if total > 0:
        importance["importance"] = importance["importance"] / total
    return importance.sort_values("importance", ascending=False).reset_index(drop=True)


def _train_with_sklearn(df: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, str]:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split

    x = df[features]
    y = df["high_gap"]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.30,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=250,
        max_depth=4,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    report = classification_report(y_test, predictions, zero_division=0)

    importance = (
        pd.DataFrame(
            {
                "feature": features,
                "importance": model.feature_importances_,
            }
        )
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    return importance, report


def train() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    df = add_scores(load_feature_data())
    df["high_gap"] = (df["priority_tier"] == "Prioritize").astype(int)

    features = DEMAND_FEATURES + ACCESS_FEATURES
    try:
        importance, report = _train_with_sklearn(df, features)
    except ModuleNotFoundError:
        importance = _fallback_importance(df, features)
        report = (
            "scikit-learn is not installed, so this run used a correlation-based "
            "feature-importance fallback. Install requirements.txt for the random "
            "forest classifier and classification report."
        )

    OUTPUT_DIR.mkdir(exist_ok=True)
    df.to_csv(OUTPUT_DIR / "scored_counties.csv", index=False)
    importance.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False)
    (OUTPUT_DIR / "classification_report.txt").write_text(report, encoding="utf-8")

    return df, importance, report


if __name__ == "__main__":
    scored, importance, report = train()
    print("Top care-gap counties")
    print(scored[["county", "state", "care_gap_score", "priority_tier"]].head(10))
    print()
    print("Feature importance")
    print(importance)
    print()
    print(report)
