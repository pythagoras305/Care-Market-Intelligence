from __future__ import annotations

import argparse
import os
import socket
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from requests.exceptions import JSONDecodeError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ACS_YEAR = 2024
BLS_YEAR = 2025
ACS_SUBJECT_URL = "https://api.census.gov/data/{year}/acs/acs5/subject"
ACS_DETAIL_URL = "https://api.census.gov/data/{year}/acs/acs5"
CENSUS_REPORTER_URL = "https://api.censusreporter.org/1.0/data/show/latest"
PLACES_COUNTY_URL = "https://data.cdc.gov/resource/swc5-untb.json"
BLS_HEALTHCARE_SUPPORT_MEAN_WAGE_2024 = 39650

STATE_FIPS = {
    "AL": "01",
    "AK": "02",
    "AZ": "04",
    "AR": "05",
    "CA": "06",
    "CO": "08",
    "CT": "09",
    "DE": "10",
    "DC": "11",
    "FL": "12",
    "GA": "13",
    "HI": "15",
    "ID": "16",
    "IL": "17",
    "IN": "18",
    "IA": "19",
    "KS": "20",
    "KY": "21",
    "LA": "22",
    "ME": "23",
    "MD": "24",
    "MA": "25",
    "MI": "26",
    "MN": "27",
    "MS": "28",
    "MO": "29",
    "MT": "30",
    "NE": "31",
    "NV": "32",
    "NH": "33",
    "NJ": "34",
    "NM": "35",
    "NY": "36",
    "NC": "37",
    "ND": "38",
    "OH": "39",
    "OK": "40",
    "OR": "41",
    "PA": "42",
    "RI": "44",
    "SC": "45",
    "SD": "46",
    "TN": "47",
    "TX": "48",
    "UT": "49",
    "VT": "50",
    "VA": "51",
    "WA": "53",
    "WV": "54",
    "WI": "55",
    "WY": "56",
}

ACS_SUBJECT_VARIABLES = {
    "S0101_C01_001E": "total_population",
    "S0101_C01_030E": "senior_population",
    "S0103_C02_026E": "living_alone_65_share",
    "S1810_C03_001E": "disability_share",
    "S1901_C01_012E": "median_income",
}

ACS_WORKFORCE_VARIABLES = {
    "C24010_020E": "male_healthcare_support_workers",
    "C24010_056E": "female_healthcare_support_workers",
}

PLACES_MEASURES = {
    "DIABETES": "diabetes_prev",
    "CHD": "chd_prev",
    "COPD": "copd_prev",
    "PHLTH": "poor_physical_health_prev",
}

CENSUS_REPORTER_TABLES = ["B01001", "B09020", "B18101", "B19013", "C24010"]
SENIOR_POP_COLUMNS = [
    "B01001020",
    "B01001021",
    "B01001022",
    "B01001023",
    "B01001024",
    "B01001025",
    "B01001044",
    "B01001045",
    "B01001046",
    "B01001047",
    "B01001048",
    "B01001049",
]
DISABILITY_COLUMNS = [
    "B18101004",
    "B18101007",
    "B18101010",
    "B18101013",
    "B18101016",
    "B18101019",
    "B18101023",
    "B18101026",
    "B18101029",
    "B18101032",
    "B18101035",
    "B18101038",
]


def force_ipv4_dns() -> None:
    original_getaddrinfo = socket.getaddrinfo

    def getaddrinfo_ipv4(*args, **kwargs):
        return [
            info
            for info in original_getaddrinfo(*args, **kwargs)
            if info[0] == socket.AF_INET
        ]

    socket.getaddrinfo = getaddrinfo_ipv4


def api_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "elder-care-demand-intelligence/0.1 "
            "(portfolio project; public API research)"
        }
    )
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_json(session: requests.Session, url: str, params: dict[str, str | int], timeout: int) -> list:
    try:
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        if "missing_key.html" in response.url.lower() or "Missing Key" in response.text[:300]:
            raise RuntimeError(
                "The Census API requires a key for this request. "
                "Request a free key at https://api.census.gov/data/key_signup.html "
                "and set it with: $env:CENSUS_API_KEY=\"your_key_here\""
            )
        return response.json()
    except JSONDecodeError as exc:
        raise RuntimeError(
            "Public API returned a non-JSON response.\n"
            f"URL: {response.url}\n"
            f"Status: {response.status_code}\n"
            f"Body preview: {response.text[:1000]}"
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            "Public API request failed. Check your network connection, try again later, "
            "or set CENSUS_API_KEY for Census requests if you are fetching many states."
        ) from exc


def fetch_census_county_data(
    url_template: str,
    variables: dict[str, str],
    states: Iterable[str],
    year: int = ACS_YEAR,
    api_key: str | None = None,
) -> pd.DataFrame:
    frames = []
    url = url_template.format(year=year)
    session = api_session()

    for state in states:
        state_fips = STATE_FIPS[state.upper()]
        params = {
            "get": ",".join(["NAME", *variables.keys()]),
            "for": "county:*",
            "in": f"state:{state_fips}",
        }
        if api_key:
            params["key"] = api_key

        rows = get_json(session, url, params=params, timeout=120)
        frame = pd.DataFrame(rows[1:], columns=rows[0])
        frames.append(frame)

    raw = pd.concat(frames, ignore_index=True)
    return clean_census_frame(raw, variables)


def clean_census_frame(raw: pd.DataFrame, variables: dict[str, str]) -> pd.DataFrame:
    cleaned = raw.rename(columns=variables).copy()
    cleaned["fips"] = cleaned["state"] + cleaned["county"]
    cleaned[["county_name", "state_name"]] = cleaned["NAME"].str.rsplit(", ", n=1, expand=True)

    numeric_columns = list(variables.values())
    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
        cleaned[column] = cleaned[column].replace(
            {-666666666: pd.NA, -888888888: pd.NA, -999999999: pd.NA}
        )

    return cleaned[["fips", "county_name", "state_name", *numeric_columns]]


def fetch_acs_features(states: Iterable[str], year: int = ACS_YEAR) -> pd.DataFrame:
    api_key = os.getenv("CENSUS_API_KEY")
    demographics = fetch_census_county_data(
        ACS_SUBJECT_URL,
        ACS_SUBJECT_VARIABLES,
        states=states,
        year=year,
        api_key=api_key,
    )
    workforce = fetch_census_county_data(
        ACS_DETAIL_URL,
        ACS_WORKFORCE_VARIABLES,
        states=states,
        year=year,
        api_key=api_key,
    )
    return demographics.merge(
        workforce[["fips", *ACS_WORKFORCE_VARIABLES.values()]],
        on="fips",
        how="left",
    )


def value_from_reporter(data: dict, table: str, column: str) -> float | None:
    return data.get(table, {}).get("estimate", {}).get(column)


def sum_from_reporter(data: dict, table: str, columns: list[str]) -> float:
    return sum(
        value or 0
        for value in (value_from_reporter(data, table, column) for column in columns)
    )


def fetch_acs_features_census_reporter(states: Iterable[str]) -> pd.DataFrame:
    session = api_session()
    frames = []
    for state in states:
        state_fips = STATE_FIPS[state.upper()]
        params = {
            "table_ids": ",".join(CENSUS_REPORTER_TABLES),
            "geo_ids": f"050|04000US{state_fips}",
        }
        payload = get_json(session, CENSUS_REPORTER_URL, params=params, timeout=120)
        geographies = payload["geography"]
        rows = []
        for geoid, tables in payload["data"].items():
            geography = geographies[geoid]
            county_name = geography["name"].rsplit(", ", 1)[0]
            total_population = value_from_reporter(tables, "B01001", "B01001001")
            senior_population = sum_from_reporter(tables, "B01001", SENIOR_POP_COLUMNS)
            living_alone_65 = (
                (value_from_reporter(tables, "B09020", "B09020015") or 0)
                + (value_from_reporter(tables, "B09020", "B09020018") or 0)
            )
            older_adults_65 = value_from_reporter(tables, "B09020", "B09020001") or senior_population
            healthcare_support_workers = (
                (value_from_reporter(tables, "C24010", "C24010020") or 0)
                + (value_from_reporter(tables, "C24010", "C24010056") or 0)
            )
            rows.append(
                {
                    "fips": geoid.replace("05000US", ""),
                    "county_name": county_name,
                    "state_name": geographies[f"04000US{state_fips}"]["name"],
                    "total_population": total_population,
                    "senior_population": senior_population,
                    "living_alone_65_share": (
                        living_alone_65 / older_adults_65 if older_adults_65 else pd.NA
                    ),
                    "disability_share": (
                        sum_from_reporter(tables, "B18101", DISABILITY_COLUMNS) / total_population
                        if total_population
                        else pd.NA
                    ),
                    "median_income": value_from_reporter(tables, "B19013", "B19013001"),
                    "male_healthcare_support_workers": value_from_reporter(tables, "C24010", "C24010020"),
                    "female_healthcare_support_workers": value_from_reporter(tables, "C24010", "C24010056"),
                    "healthcare_support_workers": healthcare_support_workers,
                }
            )
        frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True)


def fetch_places_features() -> pd.DataFrame:
    session = api_session()
    query = (
        "SELECT locationid,stateabbr,locationname,measureid,data_value_type,data_value "
        f"WHERE measureid in({','.join(repr(measure) for measure in PLACES_MEASURES)}) "
        "LIMIT 500000"
    )
    places = pd.DataFrame(get_json(session, PLACES_COUNTY_URL, params={"$query": query}, timeout=120))
    return clean_places_frame(places)


def clean_places_frame(raw: pd.DataFrame) -> pd.DataFrame:
    places = raw.rename(
        columns={
            "locationid": "fips",
            "stateabbr": "state",
            "locationname": "county",
            "data_value_type": "datavaluetype",
            "datavaluetypeid": "datavaluetype",
        }
    ).copy()
    places["data_value"] = pd.to_numeric(places["data_value"], errors="coerce")
    places["crude_rank"] = places["datavaluetype"].fillna("").str.lower().str.contains("crude|crd")
    places = places.sort_values("crude_rank", ascending=False)
    places = places.drop_duplicates(["fips", "measureid"])

    pivot = places.pivot(index="fips", columns="measureid", values="data_value").reset_index()
    pivot = pivot.rename(columns=PLACES_MEASURES)
    return pivot[["fips", *PLACES_MEASURES.values()]]


def normalize_percent(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.where(values <= 1, values / 100)


def combine_features(
    acs: pd.DataFrame,
    places: pd.DataFrame,
    bls_wages: pd.DataFrame | None = None,
) -> pd.DataFrame:
    features = acs.merge(places, on="fips", how="inner")
    features["state"] = features["fips"].str[:2].map({v: k for k, v in STATE_FIPS.items()})
    features["county"] = features["county_name"]
    features["senior_share"] = features["senior_population"] / features["total_population"]
    features["living_alone_65_share"] = normalize_percent(features["living_alone_65_share"])
    features["disability_share"] = normalize_percent(features["disability_share"])
    features["healthcare_support_workers"] = (
        features["male_healthcare_support_workers"].fillna(0)
        + features["female_healthcare_support_workers"].fillna(0)
    )
    features["healthcare_support_per_1k_seniors"] = (
        features["healthcare_support_workers"] / features["senior_population"] * 1000
    )
    if bls_wages is not None and not bls_wages.empty:
        features = features.merge(bls_wages, on="state", how="left")
    if "healthcare_support_wage" not in features:
        features["healthcare_support_wage"] = pd.NA
    features["healthcare_support_wage"] = features["healthcare_support_wage"].fillna(
        BLS_HEALTHCARE_SUPPORT_MEAN_WAGE_2024
    )
    if "wage_geo_level" not in features:
        features["wage_geo_level"] = "national_placeholder"
    features["wage_geo_level"] = features["wage_geo_level"].fillna("national_placeholder")
    if "wage_year" not in features:
        features["wage_year"] = 2024
    features["wage_year"] = features["wage_year"].fillna(2024).astype(int)
    if "wage_source" not in features:
        features["wage_source"] = "BLS OEWS national placeholder"
    features["wage_source"] = features["wage_source"].fillna("BLS OEWS national placeholder")

    columns = [
        "fips",
        "state",
        "county",
        "total_population",
        "senior_population",
        "senior_share",
        "living_alone_65_share",
        "disability_share",
        "median_income",
        "diabetes_prev",
        "chd_prev",
        "copd_prev",
        "poor_physical_health_prev",
        "healthcare_support_workers",
        "healthcare_support_per_1k_seniors",
        "healthcare_support_wage",
        "wage_geo_level",
        "wage_year",
        "wage_source",
    ]
    return features[columns].sort_values(["state", "county"]).reset_index(drop=True)


def build_public_feature_table(
    states: Iterable[str],
    year: int = ACS_YEAR,
    acs_source: str = "census-reporter",
    bls_year: int = BLS_YEAR,
    include_bls_wages: bool = True,
) -> pd.DataFrame:
    if acs_source == "census-api":
        acs = fetch_acs_features(states=states, year=year)
    elif acs_source == "census-reporter":
        acs = fetch_acs_features_census_reporter(states=states)
    else:
        raise ValueError(f"Unsupported ACS source: {acs_source}")
    places = fetch_places_features()
    bls_wages = None
    if include_bls_wages:
        from src.bls_wages import fetch_bls_healthcare_support_wages

        try:
            bls_wages = fetch_bls_healthcare_support_wages(states=states, year=bls_year)
        except Exception as exc:
            print(f"BLS wage enrichment failed, using national placeholder: {exc}")
    return combine_features(acs, places, bls_wages=bls_wages)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build county care-demand features from public data APIs.")
    parser.add_argument(
        "--states",
        nargs="+",
        default=sorted(STATE_FIPS),
        help="State abbreviations to fetch. Defaults to all states plus DC.",
    )
    parser.add_argument("--year", type=int, default=ACS_YEAR, help="ACS 5-year vintage.")
    parser.add_argument("--bls-year", type=int, default=BLS_YEAR, help="BLS OEWS wage year.")
    parser.add_argument(
        "--skip-bls-wages",
        action="store_true",
        help="Skip BLS state wage enrichment and use the bundled national placeholder.",
    )
    parser.add_argument(
        "--acs-source",
        choices=["census-reporter", "census-api"],
        default="census-reporter",
        help="ACS source. Census Reporter is no-key and default; Census API requires CENSUS_API_KEY.",
    )
    parser.add_argument(
        "--output",
        default="data/public_county_care_features.csv",
        help="CSV path for the engineered feature table.",
    )
    parser.add_argument(
        "--force-ipv4",
        action="store_true",
        help="Force IPv4 DNS resolution for networks where api.census.gov hangs during TLS over IPv6.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.force_ipv4:
        force_ipv4_dns()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    states = [state.upper() for state in args.states]
    features = build_public_feature_table(
        states=states,
        year=args.year,
        acs_source=args.acs_source,
        bls_year=args.bls_year,
        include_bls_wages=not args.skip_bls_wages,
    )
    features.to_csv(output, index=False)
    print(f"Wrote {len(features):,} county rows to {output}")


if __name__ == "__main__":
    main()
