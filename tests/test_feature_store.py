import sqlite3

from src.build_feature_store import build_feature_store


def test_build_feature_store_creates_sqlite_tables(tmp_path):
    database_path = tmp_path / "market.sqlite"

    build_feature_store(
        database_path=str(database_path),
        sample_path="data/sample_county_care_features.csv",
        public_path=str(tmp_path / "missing.csv"),
    )

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        row_count = connection.execute("SELECT COUNT(*) FROM scored_counties").fetchone()[0]

    assert {"county_features", "scored_counties", "market_opportunity", "data_quality"} <= tables
    assert row_count > 0

