import os
import requests
import urllib3

# ── SSL bypass for corporate Cisco proxy ─────────────────────────────────────
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_orig_send = requests.Session.send
def _insecure_send(self, request, **kwargs):
    kwargs["verify"] = False
    return _orig_send(self, request, **kwargs)
requests.Session.send = _insecure_send
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Jabodetabek House Prices",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Load data ─────────────────────────────────────────────────────────────────
DATA_PATH = Path(__file__).parent / "jabodetabek_house_price.csv"

@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)

    # Normalise column names
    df.columns = df.columns.str.strip()

    # Numeric coercion
    for col in ["price_in_rp", "bedrooms", "bathrooms", "land_size_m2",
                "building_size_m2", "floors", "building_age", "year_built",
                "carports", "garages", "maid_bedrooms", "maid_bathrooms"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows without a price or city
    df = df.dropna(subset=["price_in_rp", "city"])

    # Clean city strings
    df["city"] = df["city"].str.strip().str.title()

    # Price in billion IDR (easier to read)
    df["price_b"] = df["price_in_rp"] / 1e9

    # Price-per-m2 for building
    df["price_per_m2"] = np.where(
        df["building_size_m2"] > 0,
        df["price_in_rp"] / df["building_size_m2"],
        np.nan,
    )

    return df


df = load_data(DATA_PATH)

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 Filters")

    cities = sorted(df["city"].dropna().unique())
    sel_cities = st.multiselect("City", cities, default=cities)

    price_min, price_max = float(df["price_b"].min()), float(df["price_b"].max())
    sel_price = st.slider(
        "Price (Billion IDR)",
        price_min, price_max,
        (price_min, min(price_max, 10.0)),
        step=0.1,
    )

    bed_opts = sorted([x for x in df["bedrooms"].dropna().unique() if x <= 10])
    sel_beds = st.multiselect("Bedrooms", [int(x) for x in bed_opts],
                              default=[int(x) for x in bed_opts])

    prop_types = sorted(df["property_type"].dropna().unique()) if "property_type" in df.columns else []
    sel_types = st.multiselect("Property Type", prop_types, default=prop_types)

    cert_opts = sorted(df["certificate"].dropna().unique()) if "certificate" in df.columns else []
    sel_certs = st.multiselect("Certificate", cert_opts, default=cert_opts)

# ── Apply filters ─────────────────────────────────────────────────────────────
mask = (
    df["city"].isin(sel_cities)
    & df["price_b"].between(*sel_price)
)
if sel_beds:
    mask &= df["bedrooms"].isin(sel_beds)
if sel_types and prop_types:
    mask &= df["property_type"].isin(sel_types)
if sel_certs and cert_opts:
    mask &= df["certificate"].isin(sel_certs)

fdf = df[mask].copy()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🏠 Jabodetabek House Price Dashboard")
st.caption(f"Showing **{len(fdf):,}** of **{len(df):,}** listings after filters")

if fdf.empty:
    st.warning("No listings match your filters. Try relaxing the criteria.")
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Listings", f"{len(fdf):,}")
k2.metric("Median Price", f"Rp {fdf['price_b'].median():.2f}B")
k3.metric("Avg Land Size", f"{fdf['land_size_m2'].median():.0f} m²")
k4.metric("Avg Building", f"{fdf['building_size_m2'].median():.0f} m²")
k5.metric("Avg Bedrooms", f"{fdf['bedrooms'].median():.0f}")

st.divider()

# ── Row 1: Price distribution + Price by city ─────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Price Distribution")
    cap = fdf["price_b"].quantile(0.97)
    fig = px.histogram(
        fdf[fdf["price_b"] <= cap],
        x="price_b",
        nbins=50,
        labels={"price_b": "Price (Billion IDR)"},
        color_discrete_sequence=["#4C72B0"],
    )
    fig.update_layout(showlegend=False, margin=dict(t=20, b=20))
    st.plotly_chart(fig, width='stretch')

with col2:
    st.subheader("Median Price by City")
    city_med = (
        fdf.groupby("city")["price_b"]
        .median()
        .sort_values(ascending=True)
        .reset_index()
    )
    fig2 = px.bar(
        city_med,
        x="price_b",
        y="city",
        orientation="h",
        labels={"price_b": "Median Price (B IDR)", "city": ""},
        color="price_b",
        color_continuous_scale="Blues",
    )
    fig2.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=20))
    st.plotly_chart(fig2, width='stretch')

# ── Row 2: Scatter (size vs price) + Box (price by beds) ─────────────────────
col3, col4 = st.columns(2)

with col3:
    st.subheader("Building Size vs Price")
    sdf = fdf.dropna(subset=["building_size_m2", "price_b"])
    sdf = sdf[(sdf["building_size_m2"] < 1000) & (sdf["price_b"] <= sdf["price_b"].quantile(0.97))]
    fig3 = px.scatter(
        sdf,
        x="building_size_m2",
        y="price_b",
        color="city",
        opacity=0.5,
        labels={
            "building_size_m2": "Building Size (m²)",
            "price_b": "Price (B IDR)",
        },
        hover_data=["bedrooms", "bathrooms", "certificate"] if "certificate" in sdf.columns else ["bedrooms", "bathrooms"],
    )
    fig3.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig3, width='stretch')

with col4:
    st.subheader("Price by Bedrooms")
    bdf = fdf.dropna(subset=["bedrooms", "price_b"])
    bdf = bdf[bdf["bedrooms"].between(1, 8)]
    bdf["bedrooms"] = bdf["bedrooms"].astype(int).astype(str)
    fig4 = px.box(
        bdf,
        x="bedrooms",
        y="price_b",
        color="bedrooms",
        labels={"bedrooms": "Bedrooms", "price_b": "Price (B IDR)"},
        points=False,
    )
    fig4.update_layout(showlegend=False, margin=dict(t=20, b=20))
    st.plotly_chart(fig4, width='stretch')

# ── Row 3: Map ────────────────────────────────────────────────────────────────
if "lat" in fdf.columns and "long" in fdf.columns:
    mdf = fdf.dropna(subset=["lat", "long", "price_b"]).copy()
    # Remove clearly bogus coordinates
    mdf = mdf[mdf["lat"].between(-8, -5) & mdf["long"].between(105, 108)]

    if not mdf.empty:
        st.subheader("🗺️ Listing Map")
        cap97 = mdf["price_b"].quantile(0.97)
        mdf["price_capped"] = mdf["price_b"].clip(upper=cap97)
        fig5 = px.scatter_map(
            mdf,
            lat="lat",
            lon="long",
            color="price_capped",
            size="price_capped",
            size_max=12,
            color_continuous_scale="Viridis",
            zoom=9,
            center={"lat": -6.21, "lon": 106.85},
            map_style="carto-positron",
            labels={"price_capped": "Price (B IDR)"},
            hover_data={
                "city": True,
                "price_b": ":.2f",
                "bedrooms": True,
                "building_size_m2": True,
                "lat": False,
                "lon": False,
                "price_capped": False,
            } if "city" in mdf.columns else {},
            opacity=0.7,
        )
        fig5.update_layout(margin=dict(t=0, b=0))
        st.plotly_chart(fig5, width='stretch')

# ── Row 4: Price/m² by city + Certificate breakdown ──────────────────────────
col5, col6 = st.columns(2)

with col5:
    st.subheader("Price per m² by City")
    pm2 = fdf.dropna(subset=["price_per_m2", "city"])
    pm2 = pm2[pm2["price_per_m2"] < pm2["price_per_m2"].quantile(0.97)]
    pm2_city = (
        pm2.groupby("city")["price_per_m2"]
        .median()
        .sort_values(ascending=False)
        .reset_index()
    )
    pm2_city["price_per_m2_m"] = pm2_city["price_per_m2"] / 1e6
    fig6 = px.bar(
        pm2_city,
        x="city",
        y="price_per_m2_m",
        labels={"city": "", "price_per_m2_m": "Median (M IDR / m²)"},
        color="price_per_m2_m",
        color_continuous_scale="Oranges",
    )
    fig6.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=20))
    st.plotly_chart(fig6, width='stretch')

with col6:
    if "certificate" in fdf.columns:
        st.subheader("Certificate Types")
        cert_counts = fdf["certificate"].value_counts().reset_index()
        cert_counts.columns = ["certificate", "count"]
        fig7 = px.pie(
            cert_counts,
            names="certificate",
            values="count",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig7.update_layout(margin=dict(t=20, b=20), legend=dict(orientation="v"))
        st.plotly_chart(fig7, width='stretch')

# ── Raw data table ────────────────────────────────────────────────────────────
with st.expander("📋 Raw Data", expanded=False):
    show_cols = [c for c in [
        "title", "city", "district", "price_b",
        "bedrooms", "bathrooms", "land_size_m2", "building_size_m2",
        "floors", "certificate", "furnishing", "property_type",
    ] if c in fdf.columns]
    st.dataframe(
        fdf[show_cols]
        .rename(columns={"price_b": "price (B IDR)"})
        .reset_index(drop=True),
        use_container_width=True,
    )

