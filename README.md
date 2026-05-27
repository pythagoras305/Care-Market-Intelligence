# Elder Care Demand and Access Intelligence

Portfolio data science project for identifying U.S. counties with elevated elder-care demand, caregiver access gaps, and attractive expansion economics.

## Why This Project



- Combine demographic, health, and workforce signals into county-level features.
- Build an interpretable care-demand and access-gap score.
- Rank markets by business opportunity and projected ROI.
- Train a baseline model that predicts high-risk counties.
- Present results in a recruiter-friendly dashboard and written recommendation.

## Recruiter Pitch

This project uses public demographic and health data to estimate where families may face higher elder-care demand and lower caregiver access. The dashboard helps a healthcare operations team prioritize caregiver recruitment, community outreach, market expansion, and budget allocation.

## Data Sources

Public data sources:

- [U.S. Census ACS 2024 5-Year API](https://api.census.gov/data/2024/acs/acs5.html): senior population, disability, household composition, income.
- [Census Reporter](https://censusreporter.org/about/): no-key ACS 5-year fallback used by default for the public-data ingestion script.
- [CDC PLACES](https://www.cdc.gov/places/): chronic disease prevalence and health-status measures at county level.
- [BLS OEWS Public API](https://www.bls.gov/developers/): state-level annual mean wage for Healthcare Support Occupations, SOC `31-0000`.

The repository includes `data/sample_county_care_features.csv`, a small synthetic-but-realistic sample dataset for offline development. The final version should replace or augment this with public-source extracts.

## Project Structure

```text
.
|-- app.py
|-- data/
|   |-- sample_county_care_features.csv
|-- docs/
|   |-- PROJECT_PLAN.md
|   |-- PROJECT_REPORT.md
|-- sql/
|   |-- data_quality_checks.sql
|   |-- state_summary.sql
|   |-- top_expansion_markets.sql
|-- src/
|   |-- bls_wages.py
|   |-- build_feature_store.py
|   |-- care_score.py
|   |-- data_quality.py
|   |-- ingest_public_data.py
|   |-- market_opportunity.py
|   |-- train_model.py
|-- tests/
|   |-- test_care_score.py
|-- requirements.txt
```

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/train_model.py
streamlit run app.py
```

If `scikit-learn` is not installed, `src/train_model.py` falls back to a correlation-based feature-importance output so the project still produces artifacts in `outputs/`.

To build a real public-data feature table with the no-key Census Reporter ACS source:

```powershell
python -m src.ingest_public_data --states CA FL TX NY PA MI OH MD MO IL
```

This writes `data/public_county_care_features.csv` using Census Reporter ACS data, CDC PLACES, and BLS OEWS state wage enrichment. The dashboard and model use that public-data file automatically when it exists, otherwise they fall back to `data/sample_county_care_features.csv`.

To use the official Census API instead, set a key and pass `--acs-source census-api`:

```powershell
$env:CENSUS_API_KEY="your_key_here"
python -m src.ingest_public_data --states CA --acs-source census-api --force-ipv4
```

If the Census API hangs during TLS/SSL, try:

```powershell
python -m src.ingest_public_data --states CA --output data\public_county_care_features_ca.csv --force-ipv4
```

Build the local SQLite feature store:

```powershell
python -m src.build_feature_store
```

This creates `data/elder_care_market.sqlite` with four recruiter-friendly tables:

- `county_features`: raw model-ready county features.
- `scored_counties`: scored demand, access, opportunity, and confidence fields.
- `market_opportunity`: compact business-prioritization table.
- `data_quality`: missingness, sparsity, wage-fallback, and confidence flags.

Example SQL queries live in `sql/`.

## What The Dashboard Shows

- County-level care demand and access-gap scores.
- Business opportunity score for expansion prioritization.
- ROI simulator for revenue, gross profit, staffing need, and payback.
- Geographic county heatmap for visual market prioritization.
- Data-confidence filtering for counties with missing, sparse, or fallback inputs.
- Top counties by risk and commercial opportunity.
- Priority tiers based on relative risk: top 10% `Prioritize`, next 25% `Develop`, remaining counties `Monitor`.
- Drivers such as senior share, disability prevalence, chronic disease burden, income, and healthcare support workforce supply.
- Model feature importance for transparent recommendations.

## Data Confidence

Each county receives a confidence label:

- `High`: complete core inputs, state-level BLS wage, and no sparse workforce warning.
- `Medium`: one missing or fallback/sparsity signal that should be reviewed.
- `Low`: multiple quality warnings, such as missing inputs plus zero reported workforce.

Confidence flags do not hide counties automatically. They help stakeholders decide whether a recommendation is ready for action or needs validation.

## BLS Wage Enrichment

The ingestion script joins BLS OEWS annual mean wages for Healthcare Support Occupations (`31-0000`) at the state level. This improves the access and opportunity scores because caregiver labor cost now varies by geography instead of using one national placeholder.

## Next Milestones

1. Add metro-level BLS wage matching for counties inside major MSAs.
2. Expand model validation and fairness checks.
3. Deploy the dashboard publicly.
4. Add a one-page executive insight report.
5. Add screenshots or a short demo GIF after the final visual polish pass.
