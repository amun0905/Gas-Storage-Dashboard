# streamlit_app.py
import os
import time
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go


# -----------------------------
# Configuration & constants
# -----------------------------
AGSI_BASE_URL = "https://agsi.gie.eu/api"
TEST_BASE_URL = "https://agsitest.gie.eu/api"  # optional test environment
DEFAULT_YEARS = 10  # default fetch window in years
PAGE_SIZE = 300     # max page size to minimize calls (AGSI cap is 300)

# Some convenient country codes to choose from (you can extend this)
DEFAULT_COUNTRIES = [
    "AT","BE","BG","HR","CZ","DE","DK","ES","FR","HU","IT",
    "LT","LV","NL","PL","PT","RO","SE","SK","SI"
]


# -----------------------------
# Utilities
# -----------------------------
@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def fetch_agsi(
    api_key: str,
    scope: str = "EU",
    country: Optional[str] = None,
    from_date: str = "2016-01-01",
    to_date: str = None,
    base_url: str = AGSI_BASE_URL,
    sleep_s: float = 0.0,
) -> pd.DataFrame:
    """
    Fetch EU-aggregate or single-country series from AGSI within a date range.
    - EU: uses parameter 'type=eu'
    - Country: uses parameter 'country=XX'
    API requires header 'x-key: <API_KEY>'.

    Returns a tidy DataFrame with columns:
    [gasDayStart, gasInStorage (TWh), full (%), ...]
    """
    headers = {"x-key": api_key}
    if not to_date:
        to_date = date.today().isoformat()

    if scope == "EU":
        params = {"type": "eu", "from": from_date, "to": to_date, "size": PAGE_SIZE, "page": 1}
    else:
        if not country:
            raise ValueError("Country code is required when scope='Country'.")
        params = {"country": country.lower(), "from": from_date, "to": to_date, "size": PAGE_SIZE, "page": 1}

    all_rows: List[Dict[str, Any]] = []

    # First page
    r = requests.get(base_url, headers=headers, params=params, timeout=60)
    if r.status_code == 429:
        raise RuntimeError("Rate limited (HTTP 429). Wait and retry.")
    r.raise_for_status()
    payload = r.json()
    last_page = int(payload.get("last_page", 1))
    all_rows.extend(payload.get("data", []))

    # Remaining pages
    for p in range(2, last_page + 1):
        if sleep_s > 0:
            time.sleep(sleep_s)
        params["page"] = p
        r = requests.get(base_url, headers=headers, params=params, timeout=60)
        if r.status_code == 429:
            raise RuntimeError("Rate limited (HTTP 429). Wait and retry.")
        r.raise_for_status()
        payload = r.json()
        all_rows.extend(payload.get("data", []))

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df["gasDayStart"] = pd.to_datetime(df["gasDayStart"], errors="coerce")
    # Convert selected numeric fields
    for col in ["gasInStorage", "full", "injection", "withdrawal", "workingGasVolume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("gasDayStart").reset_index(drop=True)
    return df


def make_timeseries_figure(df: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["gasDayStart"], y=df["gasInStorage"],
        mode="lines", name="Gas in Storage (TWh)", line=dict(color="royalblue")
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Gas in Storage (TWh)",
        margin=dict(l=50, r=30, t=60, b=40),
        legend=dict(orientation="h", y=-0.2)
    )
    return fig


def make_seasonal_5yr(df: pd.DataFrame, title: str) -> go.Figure:
    d = df[["gasDayStart", "gasInStorage"]].dropna().copy()
    d["year"] = d["gasDayStart"].dt.year
    d["doy"] = d["gasDayStart"].dt.dayofyear

    max_year = d["year"].max()
    years = [max_year - i for i in range(5)]
    d = d[d["year"].isin(years)]

    pivot = d.pivot_table(index="doy", columns="year", values="gasInStorage").sort_index()

    fig = go.Figure()
    for y in sorted(pivot.columns):
        fig.add_trace(go.Scatter(
            x=pivot.index, y=pivot[y],
            mode="lines", name=str(y),
            line=dict(width=2 if y == max_year else 1.5)
        ))
    fig.update_layout(
        title=title,
        xaxis_title="Day of Year",
        yaxis_title="Gas in Storage (TWh)",
        margin=dict(l=50, r=30, t=60, b=40),
        legend=dict(orientation="h", y=-0.2)
    )
    return fig


def make_normal_band_10yr(df: pd.DataFrame, title: str) -> go.Figure:
    d = df[["gasDayStart", "gasInStorage"]].dropna().copy()
    d["year"] = d["gasDayStart"].dt.year
    d["doy"] = d["gasDayStart"].dt.dayofyear

    max_year = d["year"].max()
    years = [max_year - i for i in range(10)]
    d = d[d["year"].isin(years)]

    pivot = d.pivot_table(index="doy", columns="year", values="gasInStorage").sort_index()
    min_series = pivot.min(axis=1)
    max_series = pivot.max(axis=1)
    median_series = pivot.median(axis=1)

    fig = go.Figure()
    # Max line, then fill to min for shaded band
    fig.add_trace(go.Scatter(x=pivot.index, y=max_series, mode="lines",
                             line=dict(color="lightgray"), name="Max", showlegend=False))
    fig.add_trace(go.Scatter(x=pivot.index, y=min_series, mode="lines", fill="tonexty",
                             line=dict(color="lightgray"), fillcolor="rgba(200,200,200,0.45)",
                             name="Min–Max Range"))
    # Median
    fig.add_trace(go.Scatter(x=pivot.index, y=median_series, mode="lines",
                             line=dict(color="black", dash="dash"), name="Median"))
    # Current year
    if max_year in pivot.columns:
        fig.add_trace(go.Scatter(
            x=pivot.index, y=pivot[max_year], mode="lines",
            line=dict(color="royalblue", width=2.4), name=str(max_year)
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Day of Year",
        yaxis_title="Gas in Storage (TWh)",
        margin=dict(l=50, r=30, t=60, b=40),
        legend=dict(orientation="h", y=-0.2)
    )
    return fig


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="EU Gas Storage (AGSI) — Seasonal Views", layout="wide")

st.title("EU Gas Storage — AGSI (Seasonal & Time-Series)")
st.caption(
    "Data source: GIE AGSI (daily, gas-day basis). Use the sidebar to select EU or a country, date window, and view. "
    "AGSI updates at ~19:30 CET and again ~23:00 CET; if you fetch earlier in the day, the latest gas day may not yet be published."
)

# Secrets / API key
API_KEY = st.secrets.get("GIE_API_KEY") or os.getenv("GIE_API_KEY")
if not API_KEY:
    st.error("Missing API key. Add GIE_API_KEY to Streamlit **Secrets** or set it as an environment variable.")
    st.stop()

with st.sidebar:
    st.header("Controls")
    scope = st.radio("Scope", ["EU", "Country"], horizontal=True)
    country_code = None
    if scope == "Country":
        country_code = st.selectbox("Country (2-letter code)", DEFAULT_COUNTRIES, index=DEFAULT_COUNTRIES.index("DE") if "DE" in DEFAULT_COUNTRIES else 0)

    # Ten-year default window
    today = date.today()
    default_from = today - timedelta(days=365 * DEFAULT_YEARS)
    from_date = st.date_input("From", value=default_from)
    to_date = st.date_input("To", value=today)

    base_env = st.selectbox("Endpoint", ["Production", "Test (sandbox)"], index=0)
    base_url = AGSI_BASE_URL if base_env == "Production" else TEST_BASE_URL

    st.markdown("---")
    st.caption("Tip: Use the Plotly toolbar on the chart to **download PNG**, zoom, and pan.")

# Fetch data
with st.spinner("Fetching data from AGSI..."):
    df = fetch_agsi(
        api_key=API_KEY,
        scope=scope,
        country=country_code,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        base_url=base_url,
        sleep_s=0.0,
    )

if df.empty:
    st.warning("No data returned for the selected options.")
    st.stop()

# Tabs for different views
tab1, tab2, tab3 = st.tabs(["Time series", "5-year seasonal", "10-year band"])

# Titles based on scope
title_prefix = "EU" if scope == "EU" else f"{country_code}"
with tab1:
    st.subheader(f"{title_prefix} — Time Series")
    fig = make_timeseries_figure(df, f"{title_prefix} Gas in Storage (TWh)")
    st.plotly_chart(fig, use_container_width=True)
    st.download_button(
        "Download CSV (Time series)",
        data=df_to_csv_bytes(df[["gasDayStart", "gasInStorage", "full"]]),
        file_name=f"{title_prefix.lower()}_timeseries.csv",
        mime="text/csv",
    )

with tab2:
    st.subheader(f"{title_prefix} — 5-Year Seasonal Comparison")
    fig5 = make_seasonal_5yr(df, f"{title_prefix} — 5-Year Seasonal (Gas in Storage)")
    st.plotly_chart(fig5, use_container_width=True)
    # Build an aligned-by-DOY CSV for convenience
    d = df[["gasDayStart", "gasInStorage"]].dropna().copy()
    d["year"] = d["gasDayStart"].dt.year
    d["doy"] = d["gasDayStart"].dt.dayofyear
    max_year = d["year"].max()
    years = [max_year - i for i in range(5)]
    d5 = d[d["year"].isin(years)].pivot_table(index="doy", columns="year", values="gasInStorage").reset_index()
    st.download_button(
        "Download CSV (5-year DOY pivot)",
        data=df_to_csv_bytes(d5),
        file_name=f"{title_prefix.lower()}_5yr_doy.csv",
        mime="text/csv",
    )

with tab3:
    st.subheader(f"{title_prefix} — 10-Year Normal Range (Min–Max Band)")
    fig10 = make_normal_band_10yr(df, f"{title_prefix} — 10-Year Seasonal Band (Gas in Storage)")
    st.plotly_chart(fig10, use_container_width=True)
    # DOY pivot over 10 years for download
    d = df[["gasDayStart", "gasInStorage"]].dropna().copy()
    d["year"] = d["gasDayStart"].dt.year
    d["doy"] = d["gasDayStart"].dt.dayofyear
    max_year = d["year"].max()
    years = [max_year - i for i in range(10)]
    d10 = d[d["year"].isin(years)].pivot_table(index="doy", columns="year", values="gasInStorage").reset_index()
    st.download_button(
        "Download CSV (10-year DOY pivot)",
        data=df_to_csv_bytes(d10),
        file_name=f"{title_prefix.lower()}_10yr_doy.csv",
        mime="text/csv",
    )

st.caption(
    "Notes: API header `x-key` is required; EU aggregate uses `type=eu`, country requests use `country=XX`. "
    "AGSI rate limit is 60 calls/min; this app minimizes pages (size=300)."
)