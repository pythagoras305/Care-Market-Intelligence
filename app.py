from __future__ import annotations

import plotly.express as px
import requests
import streamlit as st

from src.care_score import add_scores, load_feature_data
from src.data_quality import add_confidence_flags
from src.market_opportunity import add_market_opportunity, estimate_roi


COUNTY_GEOJSON_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"

METRIC_LABELS = {
    "business_opportunity_score": "Opportunity",
    "care_gap_score": "Care Gap",
    "care_demand_score": "Demand",
    "access_constraint_score": "Access Gap",
    "healthcare_support_per_1k_seniors": "Workers / 1k Seniors",
    "healthcare_support_wage": "Support Wage",
    "confidence_level": "Confidence",
    "market_action": "Action",
}


st.set_page_config(
    page_title="Elder Care Market Intelligence",
    layout="wide",
)


@st.cache_data
def get_data():
    return add_confidence_flags(add_market_opportunity(add_scores(load_feature_data())))


@st.cache_data(show_spinner=False)
def get_county_geojson():
    response = requests.get(COUNTY_GEOJSON_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def add_display_columns(df):
    display = df.copy()
    for column in ["senior_share", "living_alone_65_share", "disability_share"]:
        if column in display:
            display[f"{column}_pct"] = display[column] * 100
    return display


def format_metric_name(value):
    return METRIC_LABELS.get(value, value.replace("_", " ").title())


def market_table_columns(df):
    columns = [
        "county",
        "state",
        "business_opportunity_score",
        "care_gap_score",
        "senior_population",
        "median_income",
        "healthcare_support_per_1k_seniors",
        "healthcare_support_wage",
        "confidence_level",
        "market_action",
    ]
    return [column for column in columns if column in df.columns]


def market_column_config():
    return {
        "business_opportunity_score": st.column_config.NumberColumn("Opportunity", format="%.2f"),
        "care_gap_score": st.column_config.NumberColumn("Care Gap", format="%.2f"),
        "care_demand_score": st.column_config.NumberColumn("Demand", format="%.2f"),
        "access_constraint_score": st.column_config.NumberColumn("Access Gap", format="%.2f"),
        "senior_population": st.column_config.NumberColumn("Seniors", format="%d"),
        "median_income": st.column_config.NumberColumn("Median Income", format="$%d"),
        "healthcare_support_per_1k_seniors": st.column_config.NumberColumn("Workers / 1k", format="%.2f"),
        "healthcare_support_wage": st.column_config.NumberColumn("Support Wage", format="$%d"),
        "confidence_level": st.column_config.TextColumn("Confidence"),
        "market_action": st.column_config.TextColumn("Action"),
    }


df = get_data()

st.title("Elder Care Market Intelligence")
st.caption("County-level market prioritization for expansion, caregiver recruiting, outreach, and budget planning.")

states = sorted(df["state"].dropna().unique())
selected_states = st.sidebar.multiselect("State", states, default=states)
confidence_levels = ["High", "Medium", "Low"]
selected_confidence = st.sidebar.multiselect(
    "Data confidence",
    confidence_levels,
    default=confidence_levels,
)
filtered = df[
    df["state"].isin(selected_states)
    & df["confidence_level"].isin(selected_confidence)
].copy()

st.sidebar.markdown("**Label Guide**")
st.sidebar.caption("Opportunity: commercial expansion score.")
st.sidebar.caption("Care Gap: estimated need plus access constraint.")
st.sidebar.caption("Demand: age, health, disability, and living-alone signals.")
st.sidebar.caption("Access Gap: lower workforce supply and affordability pressure.")
st.sidebar.caption("Confidence: completeness and sparsity of county inputs.")
st.sidebar.caption("Action: Expand, Outreach, Validate, or Monitor.")

metric_cols = st.columns(4)
metric_cols[0].metric("Counties", f"{len(filtered):,}")
metric_cols[1].metric("Avg Opportunity", f"{filtered['business_opportunity_score'].mean():.2f}")
metric_cols[2].metric("Expand Markets", f"{(filtered['market_action'] == 'Expand').sum():,}")
metric_cols[3].metric("Priority Need", f"{(filtered['priority_tier'] == 'Prioritize').sum():,}")
st.caption(
    f"{(filtered['confidence_level'] == 'High').sum():,} high-confidence counties | "
    f"{(filtered['confidence_level'] == 'Low').sum():,} low-confidence counties after filters"
)

map_tab, capacity_tab, detail_tab, market_tab = st.tabs(
    ["Geographic Heatmap", "Capacity Analysis", "County Detail", "Market Opportunity"]
)

with map_tab:
    st.subheader("County Heatmap")
    st.caption("Use the map to see where high-need and high-opportunity counties cluster geographically.")
    map_metric = st.selectbox(
        "Map metric",
        ["business_opportunity_score", "care_gap_score", "care_demand_score", "access_constraint_score"],
        format_func=format_metric_name,
    )
    map_df = filtered.dropna(subset=[map_metric]).copy()
    if map_df.empty:
        st.info("No counties with complete map scores are available for the selected states.")
    else:
        try:
            county_geojson = get_county_geojson()
            map_fig = px.choropleth(
                map_df,
                geojson=county_geojson,
                locations="fips",
                color=map_metric,
                color_continuous_scale="YlOrRd",
                scope="usa",
                hover_name="county",
                hover_data={
                    "fips": False,
                    "state": True,
                    "business_opportunity_score": ":.2f",
                    "care_gap_score": ":.2f",
                    "care_demand_score": ":.2f",
                    "access_constraint_score": ":.2f",
                    "healthcare_support_wage": ":$,.0f",
                    "confidence_level": True,
                    "market_action": True,
                },
                labels={key: value for key, value in METRIC_LABELS.items()},
            )
            map_fig.update_geos(fitbounds="locations", visible=False)
            map_fig.update_layout(
                height=760,
                margin={"r": 0, "t": 0, "l": 0, "b": 0},
                coloraxis_colorbar={"title": format_metric_name(map_metric)},
            )
            st.plotly_chart(map_fig, width="stretch")
        except requests.RequestException:
            st.warning("County map geometry could not be loaded. Other dashboard tabs are still available.")

with capacity_tab:
    st.subheader("Market Need vs Workforce Capacity")
    st.caption("Higher dots have more care demand. Dots farther left have fewer healthcare support workers per 1,000 seniors.")
    plot_required_columns = [
        "healthcare_support_per_1k_seniors",
        "care_demand_score",
        "business_opportunity_score",
    ]
    plot_df = filtered.dropna(subset=plot_required_columns).copy()
    omitted_plot_rows = len(filtered) - len(plot_df)

    if omitted_plot_rows:
        st.caption(f"{omitted_plot_rows} county omitted because required chart inputs are missing.")
    if plot_df.empty:
        st.info("No counties with complete score inputs are available for the selected states.")
    else:
        fig = px.scatter(
            plot_df,
            x="healthcare_support_per_1k_seniors",
            y="care_demand_score",
            size="business_opportunity_score",
            color="market_action",
            hover_name="county",
            hover_data={
                "state": True,
                "healthcare_support_per_1k_seniors": ":.2f",
                "care_demand_score": ":.2f",
                "business_opportunity_score": ":.2f",
                "care_gap_score": ":.2f",
                "senior_share": ":.2%",
                "disability_share": ":.2%",
                "healthcare_support_wage": ":$,.0f",
                "confidence_level": True,
            },
            labels={key: value for key, value in METRIC_LABELS.items()},
        )
        fig.update_layout(
            height=680,
            legend_title_text="Action",
            margin={"r": 10, "t": 10, "l": 10, "b": 10},
            xaxis_title="Workers / 1k Seniors",
            yaxis_title="Demand Score",
        )
        st.plotly_chart(fig, width="stretch")

    st.markdown("**Recommended Expansion Markets**")
    top = filtered.nlargest(12, "business_opportunity_score")[market_table_columns(filtered)]
    st.dataframe(
        top,
        hide_index=True,
        width="stretch",
        column_config=market_column_config(),
    )

with detail_tab:
    st.subheader("County Detail")
    st.caption("Detailed county-level inputs and scores. Download this table for deeper analysis or reporting.")
    detail = add_display_columns(filtered.sort_values("business_opportunity_score", ascending=False))
    detail_columns = [
        "fips",
        "county",
        "state",
        "senior_population",
        "senior_share_pct",
        "living_alone_65_share_pct",
        "disability_share_pct",
        "median_income",
        "diabetes_prev",
        "chd_prev",
        "copd_prev",
        "poor_physical_health_prev",
        "healthcare_support_per_1k_seniors",
        "healthcare_support_wage",
        "care_gap_score",
        "business_opportunity_score",
        "market_action",
        "confidence_level",
        "confidence_notes",
    ]
    detail_columns = [column for column in detail_columns if column in detail.columns]
    st.dataframe(
        detail[detail_columns],
        hide_index=True,
        width="stretch",
        column_config={
            "senior_population": st.column_config.NumberColumn("Seniors", format="%d"),
            "senior_share_pct": st.column_config.NumberColumn("Senior Share", format="%.2f%%"),
            "living_alone_65_share_pct": st.column_config.NumberColumn("65+ Alone", format="%.2f%%"),
            "disability_share_pct": st.column_config.NumberColumn("Disability", format="%.2f%%"),
            "median_income": st.column_config.NumberColumn("Median Income", format="$%d"),
            "diabetes_prev": st.column_config.NumberColumn("Diabetes", format="%.2f%%"),
            "chd_prev": st.column_config.NumberColumn("CHD", format="%.2f%%"),
            "copd_prev": st.column_config.NumberColumn("COPD", format="%.2f%%"),
            "poor_physical_health_prev": st.column_config.NumberColumn("Poor Health", format="%.2f%%"),
            "healthcare_support_per_1k_seniors": st.column_config.NumberColumn("Workers / 1k", format="%.2f"),
            "healthcare_support_wage": st.column_config.NumberColumn("Support Wage", format="$%d"),
            "care_gap_score": st.column_config.NumberColumn("Care Gap", format="%.2f"),
            "business_opportunity_score": st.column_config.NumberColumn("Opportunity", format="%.2f"),
            "market_action": st.column_config.TextColumn("Action"),
            "confidence_level": st.column_config.TextColumn("Confidence"),
            "confidence_notes": st.column_config.TextColumn("Confidence Notes"),
        },
    )
    st.download_button(
        "Download filtered county detail",
        data=detail.to_csv(index=False),
        file_name="county_market_detail.csv",
        mime="text/csv",
    )

with market_tab:
    st.subheader("Market Opportunity / ROI")
    with st.expander("How this tab works", expanded=True):
        st.markdown(
            """
            **Opportunity** ranks counties by commercial attractiveness: care gap, senior market size,
            median income, and workforce shortage.

            The ROI model is a scenario calculator. Adjust the assumptions to estimate clients,
            revenue, gross profit, caregiver hiring needs, launch investment, payback, and first-year gross profit.
            It is not a financial forecast; it is a planning tool for comparing markets under the same assumptions.
            """
        )

    assumptions, results = st.columns([0.8, 1.6])

    with assumptions:
        st.markdown("**ROI Assumptions**")
        monthly_revenue_per_client = st.number_input(
            "Revenue / Client / Mo",
            min_value=0,
            value=2200,
            step=100,
            format="%d",
            help="Average monthly revenue from one active client.",
        )
        gross_margin = st.slider("Gross Margin", 5, 80, 30, help="Share of revenue retained after direct service costs.") / 100
        outreach_rate = st.slider("Outreach Reach", 1, 10, 2, help="Share of seniors reached in a month.") / 100
        conversion_rate = st.slider("Lead Conversion", 1, 30, 8, help="Share of reached prospects who become clients.") / 100
        clients_per_caregiver = st.number_input(
            "Clients / Caregiver",
            min_value=1.0,
            value=3.0,
            step=0.5,
            help="Average active client capacity per caregiver.",
        )
        recruiting_cost_per_caregiver = st.number_input(
            "Recruiting Cost / Caregiver",
            min_value=0,
            value=900,
            step=100,
            format="%d",
        )
        fixed_launch_cost = st.number_input(
            "Fixed Launch Cost",
            min_value=0,
            value=5000,
            step=500,
            format="%d",
        )

    roi_df = estimate_roi(
        filtered.dropna(subset=["business_opportunity_score"]),
        monthly_revenue_per_client=monthly_revenue_per_client,
        gross_margin=gross_margin,
        outreach_rate=outreach_rate,
        conversion_rate=conversion_rate,
        clients_per_caregiver=clients_per_caregiver,
        recruiting_cost_per_caregiver=recruiting_cost_per_caregiver,
        fixed_launch_cost=fixed_launch_cost,
    ).sort_values("first_year_gross_profit", ascending=False)

    with results:
        top_10 = roi_df.head(10)
        roi_metrics = st.columns(4)
        roi_metrics[0].metric("Top 10 Revenue", f"${top_10['monthly_revenue'].sum():,.0f}/mo")
        roi_metrics[1].metric("Top 10 Gross Profit", f"${top_10['monthly_gross_profit'].sum():,.0f}/mo")
        roi_metrics[2].metric("Caregivers Needed", f"{top_10['caregivers_needed'].sum():,.0f}")
        roi_metrics[3].metric("Median Payback", f"{top_10['payback_months'].median():.2f} mo")

        roi_columns = [
            "county",
            "state",
            "business_opportunity_score",
            "market_action",
            "confidence_level",
            "estimated_clients",
            "caregivers_needed",
            "monthly_revenue",
            "monthly_gross_profit",
            "payback_months",
            "first_year_gross_profit",
        ]
        st.dataframe(
            roi_df.head(15)[roi_columns],
            hide_index=True,
            width="stretch",
            column_config={
                "business_opportunity_score": st.column_config.NumberColumn("Opportunity", format="%.2f"),
                "market_action": st.column_config.TextColumn("Action"),
                "confidence_level": st.column_config.TextColumn("Confidence"),
                "estimated_clients": st.column_config.NumberColumn("Clients", format="%.2f"),
                "caregivers_needed": st.column_config.NumberColumn("Caregivers", format="%d"),
                "monthly_revenue": st.column_config.NumberColumn("Revenue / Mo", format="$%.0f"),
                "monthly_gross_profit": st.column_config.NumberColumn("Gross Profit / Mo", format="$%.0f"),
                "payback_months": st.column_config.NumberColumn("Payback", format="%.2f mo"),
                "first_year_gross_profit": st.column_config.NumberColumn("Year 1 Profit", format="$%.0f"),
            },
        )
        st.download_button(
            "Download ROI-ranked markets",
            data=roi_df.to_csv(index=False),
            file_name="roi_ranked_markets.csv",
            mime="text/csv",
        )

    st.subheader("Opportunity Score Drivers")
    st.caption("Counties in the upper-right combine high care need with strong commercial opportunity.")
    driver_df = filtered.dropna(subset=["business_opportunity_score", "care_gap_score"]).copy()
    if driver_df.empty:
        st.info("No complete opportunity records are available for the selected states.")
    else:
        driver_fig = px.scatter(
            driver_df,
            x="care_gap_score",
            y="business_opportunity_score",
            size="senior_population" if "senior_population" in driver_df else "senior_share",
            color="market_action",
            hover_name="county",
            hover_data={
                "state": True,
                "care_gap_score": ":.2f",
                "business_opportunity_score": ":.2f",
                "median_income": ":$,.0f",
                "healthcare_support_per_1k_seniors": ":.2f",
                "confidence_level": True,
            },
            labels={key: value for key, value in METRIC_LABELS.items()},
        )
        driver_fig.update_layout(
            height=620,
            legend_title_text="Action",
            margin={"r": 10, "t": 10, "l": 10, "b": 10},
            xaxis_title="Care Gap",
            yaxis_title="Opportunity",
        )
        st.plotly_chart(driver_fig, width="stretch")
