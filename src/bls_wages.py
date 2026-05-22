from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import requests

from src.ingest_public_data import STATE_FIPS


BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_HEALTHCARE_SUPPORT_OCCUPATION = "310000"
BLS_ANNUAL_MEAN_WAGE_DATATYPE = "04"
BLS_NATIONAL_HEALTHCARE_SUPPORT_WAGE_SERIES = "OEUN000000000000031000004"


@dataclass(frozen=True)
class BlsWageRequest:
    state: str
    series_id: str


def state_healthcare_support_wage_series(state: str) -> str:
    state_fips = STATE_FIPS[state.upper()]
    area_code = f"{state_fips}00000"
    return f"OEUS{area_code}000000{BLS_HEALTHCARE_SUPPORT_OCCUPATION}{BLS_ANNUAL_MEAN_WAGE_DATATYPE}"


def _wage_requests(states: Iterable[str]) -> list[BlsWageRequest]:
    return [
        BlsWageRequest(state=state.upper(), series_id=state_healthcare_support_wage_series(state))
        for state in states
    ]


def _post_bls_series(series_ids: list[str], year: int, timeout: int) -> dict:
    response = requests.post(
        BLS_API_URL,
        json={"seriesid": series_ids, "startyear": str(year), "endyear": str(year)},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API request failed: {payload.get('message', [])}")
    return payload


def fetch_bls_healthcare_support_wages(
    states: Iterable[str],
    year: int,
    timeout: int = 60,
) -> pd.DataFrame:
    requests_by_state = _wage_requests(states)
    national_payload = _post_bls_series(
        [BLS_NATIONAL_HEALTHCARE_SUPPORT_WAGE_SERIES],
        year=year,
        timeout=timeout,
    )
    national_wage = _series_value(national_payload, BLS_NATIONAL_HEALTHCARE_SUPPORT_WAGE_SERIES)

    rows = []
    for start in range(0, len(requests_by_state), 25):
        chunk = requests_by_state[start : start + 25]
        payload = _post_bls_series([request.series_id for request in chunk], year=year, timeout=timeout)
        for request in chunk:
            wage = _series_value(payload, request.series_id)
            rows.append(
                {
                    "state": request.state,
                    "healthcare_support_wage": wage if pd.notna(wage) else national_wage,
                    "wage_geo_level": "state" if pd.notna(wage) else "national_fallback",
                    "wage_year": year,
                    "wage_source": "BLS OEWS annual mean wage, SOC 31-0000",
                }
            )

    return pd.DataFrame(rows)


def _series_value(payload: dict, series_id: str) -> float | pd.NA:
    series = payload.get("Results", {}).get("series", [])
    for item in series:
        if item.get("seriesID") == series_id and item.get("data"):
            value = item["data"][0].get("value")
            return pd.to_numeric(value, errors="coerce")
    return pd.NA

