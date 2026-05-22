from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

from src.care_score import add_scores, load_feature_data
from src.data_quality import add_confidence_flags
from src.market_opportunity import add_market_opportunity


DEFAULT_DATABASE_PATH = "data/elder_care_market.sqlite"


def build_feature_store(
    database_path: str = DEFAULT_DATABASE_PATH,
    public_path: str = "data/public_county_care_features.csv",
    sample_path: str = "data/sample_county_care_features.csv",
) -> Path:
    output_path = Path(database_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_features = load_feature_data(public_path=public_path, sample_path=sample_path)
    scored = add_confidence_flags(add_market_opportunity(add_scores(raw_features)))

    data_quality_columns = [
        "fips",
        "county",
        "state",
        "missing_feature_count",
        "missing_features",
        "small_senior_population_flag",
        "zero_workforce_flag",
        "wage_fallback_flag",
        "confidence_level",
        "confidence_notes",
    ]
    market_columns = [
        "fips",
        "county",
        "state",
        "care_gap_score",
        "business_opportunity_score",
        "market_action",
        "confidence_level",
    ]

    with sqlite3.connect(output_path) as connection:
        raw_features.to_sql("county_features", connection, if_exists="replace", index=False)
        scored.to_sql("scored_counties", connection, if_exists="replace", index=False)
        scored[[column for column in market_columns if column in scored.columns]].to_sql(
            "market_opportunity",
            connection,
            if_exists="replace",
            index=False,
        )
        scored[[column for column in data_quality_columns if column in scored.columns]].to_sql(
            "data_quality",
            connection,
            if_exists="replace",
            index=False,
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_scored_counties_fips ON scored_counties(fips)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_scored_counties_state ON scored_counties(state)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_market_action ON market_opportunity(market_action)")

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local SQLite feature tables for the dashboard.")
    parser.add_argument("--database", default=DEFAULT_DATABASE_PATH, help="Output SQLite database path.")
    parser.add_argument("--public-path", default="data/public_county_care_features.csv")
    parser.add_argument("--sample-path", default="data/sample_county_care_features.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_path = build_feature_store(
        database_path=args.database,
        public_path=args.public_path,
        sample_path=args.sample_path,
    )
    print(f"Wrote SQLite feature store to {database_path}")


if __name__ == "__main__":
    main()

