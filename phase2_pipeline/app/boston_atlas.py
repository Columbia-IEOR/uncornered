"""
Uncornered · Learning Dashboard

Boston shootings from Analyze Boston crime incident reports
(SHOOTING = 1, ASSAULT - AGGRAVATED or MURDER), each classified Fatal / Non-Fatal
using the Boston Person Shot dashboard (see fetch/fetch_boston_to_sheets.py).

Run from repo root:
  python3 -m streamlit run phase2_pipeline/app/boston_atlas.py
"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import altair as alt
import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from branca.colormap import LinearColormap
from streamlit_folium import st_folium

PHASE2_ROOT = Path(__file__).resolve().parents[1]
INCIDENTS_CSV = PHASE2_ROOT / "data" / "cleaned" / "boston_shooting_incidents.csv"
NEIGH_GEOJSON = PHASE2_ROOT / "data" / "boundaries" / "boston_neighborhoods.geojson"
TRACT_GEOJSON = PHASE2_ROOT / "data" / "boundaries" / "boston_census_tracts_2020.geojson"
LOGO_PNG = Path(__file__).resolve().parent / "assets" / "uncornered_logo.png"

CRIME_REPORTS_URL = (
    "https://data.boston.gov/dataset/crime-incident-reports-august-2015-to-date-source-new-system"
)
PERSON_SHOT_URL = "https://www.arcgis.com/apps/dashboards/dbd16dfec5b54734bd7d927b26b38a24"

CITY_VIEWS = {
    "Boston": {"center": [42.315, -71.08], "zoom": 12, "ready": True},
    "Kansas City": {"center": [39.10, -94.58], "zoom": 11, "ready": False},
    "Providence": {"center": [41.82, -71.42], "zoom": 12, "ready": False},
}

# Choropleth palette (low green → high red)
COLOR_SCALE = ["#47944b", "#b1d878", "#ffffc6", "#f2b26e", "#c6322a"]
TYPE_COLORS = {"Fatal": "#c6322a", "Non-Fatal": "#f2b26e"}
UC_ORANGE = "#ed6a24"
UC_CHARCOAL = "#1c1c1c"

# CARTO basemaps now watermark tiles without an API key; Esri Light Gray is keyless.
BASEMAP_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
)
BASEMAP_ATTR = "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors"

PRESETS = [
    "Last 12 months",
    "Year to date",
    "Last 90 days",
    "Last 30 days",
    "All available data",
    "Custom range",
]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HOUR_BLOCKS = ["12a", "3a", "6a", "9a", "12p", "3p", "6p", "9p"]  # 3-hour blocks by start

try:
    st.set_page_config(
        page_title="Uncornered · Learning Dashboard",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
except st.errors.StreamlitAPIException:
    pass


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
CSS = """
<style>
.stApp { background: #f4f4f2; }
header[data-testid="stHeader"] { height: 0 !important; min-height: 0 !important; background: transparent; }
header[data-testid="stHeader"] * { display: none !important; }
div[data-testid="stToolbar"], div[data-testid="stDecoration"] { display: none; }
.block-container { padding: 1.1rem 2rem 2rem 2rem !important; max-width: 100% !important; }

div[class*="st-key-card_"] {
  background: #ffffff;
  border: 1px solid #e7e5e4 !important;
  border-radius: 14px !important;
  box-shadow: 0 1px 2px rgba(28,25,23,0.04);
  padding: 1rem 1.1rem !important;
}

.uc-header {
  background: #ffffff;
  border: 1px solid #e7e5e4;
  border-radius: 16px;
  padding: 0.9rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  box-shadow: 0 1px 2px rgba(28,25,23,0.04);
}
.uc-brandline { display: flex; align-items: center; gap: 1.4rem; flex-wrap: wrap; }
.uc-logo { height: 68px; width: auto; display: block; }
.uc-title {
  font-size: 1.45rem; font-weight: 750; color: __CHARCOAL__; line-height: 1.15;
  padding-left: 1.4rem; border-left: 2px solid #e7e5e4;
}
.uc-chips { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.uc-chip {
  font-size: 0.78rem; color: #57534e; background: #f5f5f4;
  border: 1px solid #e7e5e4; border-radius: 999px; padding: 0.3rem 0.75rem;
}
.uc-chip b { color: __CHARCOAL__; font-weight: 650; }

.uc-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.8rem; margin-bottom: 0.9rem; }
@media (max-width: 1100px) { .uc-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.uc-kpi {
  background: #ffffff; border: 1px solid #e7e5e4; border-radius: 14px;
  padding: 0.9rem 1.1rem; box-shadow: 0 1px 2px rgba(28,25,23,0.04);
  border-top: 4px solid var(--accent, #d6d3d1);
}
.uc-kpi-label { font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: #78716c; font-weight: 650; }
.uc-kpi-value { font-size: 2rem; font-weight: 750; color: #1c1917; line-height: 1.15; margin: 0.2rem 0 0.15rem; }
.uc-kpi-value.small { font-size: 1.35rem; padding: 0.35rem 0 0.2rem; }
.uc-kpi-sub { font-size: 0.8rem; color: #78716c; }
.uc-kpi-sub .up { color: #b91c1c; font-weight: 650; }
.uc-kpi-sub .down { color: #15803d; font-weight: 650; }
.uc-kpi-sub .flat { color: #57534e; font-weight: 650; }

.uc-section { font-size: 1rem; font-weight: 700; color: #1c1917; margin: 0 0 0.1rem; }
.uc-caption { font-size: 0.8rem; color: #78716c; margin-bottom: 0.6rem; }
.uc-panel-title { font-size: 0.72rem; letter-spacing: 0.1em; text-transform: uppercase; color: #78716c; font-weight: 700; margin-bottom: 0.4rem; }
.uc-range { font-size: 0.85rem; color: #44403c; background: #f5f5f4; border-radius: 8px; padding: 0.45rem 0.65rem; margin: -0.2rem 0 0.4rem; }

.uc-legend { display: flex; align-items: center; gap: 0.6rem; font-size: 0.75rem; color: #57534e; }
.uc-legend-bar { display: flex; width: 220px; height: 10px; border-radius: 5px; overflow: hidden; border: 1px solid rgba(0,0,0,0.08); }
.uc-legend-bar span { flex: 1; }
.uc-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 0.3rem; vertical-align: -1px; }

.uc-about { font-size: 0.84rem; color: #44403c; line-height: 1.5; }
.uc-about h4 { font-size: 0.72rem; letter-spacing: 0.1em; text-transform: uppercase; color: #78716c; margin: 0.8rem 0 0.2rem; }
.uc-about h4:first-child { margin-top: 0; }
.uc-about a { color: __ORANGE__; }

label, [data-testid="stWidgetLabel"] p { color: #1c1917 !important; font-weight: 600 !important; }
</style>
""".replace("__ORANGE__", UC_ORANGE).replace("__CHARCOAL__", UC_CHARCOAL)


def fmt_date(d) -> str:
    return f"{d:%b} {d.day}, {d:%Y}"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data
def load_neighborhoods() -> dict:
    return json.loads(NEIGH_GEOJSON.read_text())


@st.cache_data
def load_tracts() -> dict:
    return json.loads(TRACT_GEOJSON.read_text())


@st.cache_data
def load_tracts_gdf() -> gpd.GeoDataFrame:
    """2020 tracts labelled 'Tract 915 · Roxbury' (neighborhood containing the tract)."""
    gdf = gpd.read_file(TRACT_GEOJSON)
    gdf = gdf.set_crs(epsg=4326) if gdf.crs is None else gdf.to_crs(epsg=4326)
    hoods = gpd.read_file(NEIGH_GEOJSON).to_crs(epsg=4326)[["name", "geometry"]]
    centers = gpd.GeoDataFrame(geometry=gdf.geometry.representative_point(), crs="EPSG:4326")
    hood = gpd.sjoin(centers, hoods, how="left", predicate="within")
    hood = hood[~hood.index.duplicated(keep="first")]["name"].reindex(gdf.index)
    gdf["tract_id"] = gdf["geoid20"].astype(str)
    gdf["tract_label"] = "Tract " + gdf["name20"].astype(str) + hood.map(
        lambda n: f" · {n}" if isinstance(n, str) else ""
    )
    return gdf[["tract_id", "tract_label", "geometry"]].copy()


# File mtime is part of the cache key so the monthly refresh shows up without a restart.
@st.cache_data
def load_incidents(mtime: float) -> pd.DataFrame:
    df = pd.read_csv(INCIDENTS_CSV)
    df["date"] = pd.to_datetime(df["occurred_on_date"], errors="coerce")
    df = df.dropna(subset=["date", "latitude", "longitude"]).copy()
    df["shooting_type"] = df["shooting_type"].fillna("Non-Fatal")
    df["neighborhood"] = df["neighborhood"].fillna("Unknown")
    for col in ["street", "district", "offense_description"]:
        df[col] = df[col].fillna("")

    tracts = load_tracts_gdf()
    pts = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), index=df.index, crs="EPSG:4326"
    )
    joined = gpd.sjoin(pts, tracts, how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    df["tract_id"] = joined["tract_id"]
    return df


def in_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end) + pd.Timedelta(days=1)
    return df[(df["date"] >= s) & (df["date"] < e)]


def preset_range(name: str, data_min: date, data_max: date) -> Optional[Tuple[date, date]]:
    end = data_max
    if name == "All available data":
        return data_min, end
    if name == "Year to date":
        return date(end.year, 1, 1), end
    if name == "Last 30 days":
        return end - timedelta(days=29), end
    if name == "Last 90 days":
        return end - timedelta(days=89), end
    if name == "Last 12 months":
        return end - timedelta(days=364), end
    return None


def prior_period(start: date, end: date) -> Tuple[date, date]:
    length = (end - start).days + 1
    return start - timedelta(days=length), start - timedelta(days=1)


def next_monthly_refresh(now: datetime) -> datetime:
    """Matches the launchd schedule: 1st of each month, 9:00 AM local time."""
    this_month = now.replace(day=1, hour=9, minute=0, second=0, microsecond=0)
    if now < this_month:
        return this_month
    if now.month == 12:
        return this_month.replace(year=now.year + 1, month=1)
    return this_month.replace(month=now.month + 1)


def area_counts(df: pd.DataFrame, key: str, base: pd.DataFrame) -> pd.DataFrame:
    """Shootings / fatal / non-fatal per area, including areas with zero."""
    g = df.groupby(key).agg(
        shootings=("shooting_type", "size"),
        fatal=("shooting_type", lambda s: int((s == "Fatal").sum())),
    )
    out = base.merge(g, left_on="area_id", right_index=True, how="left").fillna(
        {"shootings": 0, "fatal": 0}
    )
    out["shootings"] = out["shootings"].astype(int)
    out["fatal"] = out["fatal"].astype(int)
    out["non_fatal"] = out["shootings"] - out["fatal"]
    return out


# ---------------------------------------------------------------------------
# Pieces of UI
# ---------------------------------------------------------------------------
def delta_html(cur: int, prev: Optional[int]) -> str:
    if prev is None:
        return ""
    if prev == 0:
        return "" if cur == 0 else '<span class="up">▲ new</span> vs previous period'
    pct = (cur - prev) / prev * 100
    if abs(pct) < 0.5:
        return '<span class="flat">● no change</span> vs previous period'
    arrow, cls = ("▲", "up") if pct > 0 else ("▼", "down")
    return f'<span class="{cls}">{arrow} {abs(pct):.0f}%</span> vs previous period ({prev:,})'


def kpi(label: str, value: str, sub: str, accent: str, small: bool = False) -> str:
    cls = "uc-kpi-value small" if small else "uc-kpi-value"
    return (
        f'<div class="uc-kpi" style="--accent:{accent}">'
        f'<div class="uc-kpi-label">{label}</div>'
        f'<div class="{cls}">{value}</div>'
        f'<div class="uc-kpi-sub">{sub or "&nbsp;"}</div></div>'
    )


def legend_html(max_c: int, show_points: bool) -> str:
    bar = "".join(f'<span style="background:{c}"></span>' for c in COLOR_SCALE)
    points = ""
    if show_points:
        points = (
            f'<span style="margin-left:1rem"><span class="uc-dot" style="background:{TYPE_COLORS["Fatal"]}"></span>Fatal</span>'
            f'<span><span class="uc-dot" style="background:{TYPE_COLORS["Non-Fatal"]}"></span>Non-fatal</span>'
        )
    return (
        f'<div class="uc-legend"><span>0</span><div class="uc-legend-bar">{bar}</div>'
        f"<span>{max_c}</span>{points}</div>"
    )


def style_chart(chart: alt.Chart, height: int) -> alt.Chart:
    return (
        chart.properties(height=height, background="#ffffff")
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor="#57534e",
            titleColor="#78716c",
            gridColor="#eeeeec",
            domain=False,
            tickColor="#e7e5e4",
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight="normal",
        )
        .configure_legend(orient="bottom", title=None, labelColor="#44403c", symbolType="circle")
    )


def type_scale(types: list) -> alt.Scale:
    return alt.Scale(domain=types, range=[TYPE_COLORS[t] for t in types])


def trend_chart(df: pd.DataFrame, start: date, end: date, types: list) -> Tuple[alt.Chart, str]:
    days = (end - start).days
    if days <= 120:
        freq, caption = "W", "Weekly"
        fmt = lambda p: f"{p.start_time:%b} {p.start_time.day}"
    elif days <= 3 * 366:
        freq, caption = "M", "Monthly"
        fmt = lambda p: p.start_time.strftime("%b '%y")
    else:
        freq, caption = "Y", "Yearly"
        fmt = lambda p: str(p.year)

    counts = (
        df.assign(p=df["date"].dt.to_period(freq))
        .groupby(["p", "shooting_type"])
        .size()
        .rename("n")
        .reset_index()
    )
    periods = pd.period_range(start, end, freq=freq)
    grid = pd.MultiIndex.from_product([periods, types], names=["p", "shooting_type"]).to_frame(index=False)
    data = grid.merge(counts, on=["p", "shooting_type"], how="left").fillna({"n": 0})
    data["label"] = data["p"].map(fmt)
    order = [fmt(p) for p in periods]
    data = data.drop(columns="p")

    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
        .encode(
            x=alt.X("label:N", sort=order, title=None, axis=alt.Axis(labelAngle=-40, labelOverlap=True)),
            y=alt.Y("sum(n):Q", title="Shootings", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("shooting_type:N", scale=type_scale(types)),
            order=alt.Order("shooting_type:N", sort="descending"),
            tooltip=[
                alt.Tooltip("label:N", title="Period"),
                alt.Tooltip("shooting_type:N", title="Outcome"),
                alt.Tooltip("n:Q", title="Shootings"),
            ],
        )
    )
    return style_chart(chart, 260), caption


def top_areas_chart(counts: pd.DataFrame, types: list, n: int = 10) -> Optional[alt.Chart]:
    top = counts[counts["shootings"] > 0].nlargest(n, "shootings")
    if top.empty:
        return None
    long = top.melt(
        id_vars=["area_label"], value_vars=["fatal", "non_fatal"], var_name="t", value_name="n"
    )
    long["shooting_type"] = long["t"].map({"fatal": "Fatal", "non_fatal": "Non-Fatal"})
    long = long[long["shooting_type"].isin(types)]
    chart = (
        alt.Chart(long)
        .mark_bar(cornerRadiusTopRight=2, cornerRadiusBottomRight=2)
        .encode(
            y=alt.Y(
                "area_label:N",
                sort=top["area_label"].tolist(),
                title=None,
                axis=alt.Axis(labelLimit=200, labelOverlap=False),
                scale=alt.Scale(paddingInner=0.25),
            ),
            x=alt.X("sum(n):Q", title="Shootings", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("shooting_type:N", scale=type_scale(types)),
            order=alt.Order("shooting_type:N", sort="descending"),
            tooltip=[
                alt.Tooltip("area_label:N", title="Area"),
                alt.Tooltip("shooting_type:N", title="Outcome"),
                alt.Tooltip("n:Q", title="Shootings"),
            ],
        )
    )
    return style_chart(chart, max(28 * len(top), 120))


def when_chart(df: pd.DataFrame) -> alt.Chart:
    data = (
        df.assign(
            day=df["date"].dt.dayofweek.map(dict(enumerate(DAYS))),
            block=(df["date"].dt.hour // 3).map(dict(enumerate(HOUR_BLOCKS))),
        )
        .groupby(["day", "block"])
        .size()
        .rename("n")
        .reset_index()
    )
    grid = pd.MultiIndex.from_product([DAYS, HOUR_BLOCKS], names=["day", "block"]).to_frame(index=False)
    data = grid.merge(data, on=["day", "block"], how="left").fillna({"n": 0})
    chart = (
        alt.Chart(data)
        .mark_rect(cornerRadius=3, stroke="#ffffff", strokeWidth=2)
        .encode(
            x=alt.X("block:N", sort=HOUR_BLOCKS, title="3-hour block starting at", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("day:N", sort=DAYS, title=None),
            color=alt.Color(
                "n:Q",
                scale=alt.Scale(range=["#f5f5f4", "#f2b26e", "#c6322a"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("day:N", title="Day"),
                alt.Tooltip("block:N", title="3 hours from"),
                alt.Tooltip("n:Q", title="Shootings"),
            ],
        )
    )
    return style_chart(chart, 250)


def build_map(
    city: str,
    geojson: Optional[dict],
    counts: Optional[pd.DataFrame],
    points: Optional[pd.DataFrame],
    geography: str,
    id_field: str,
) -> folium.Map:
    view = CITY_VIEWS[city]
    m = folium.Map(
        location=view["center"],
        zoom_start=view["zoom"],
        tiles=BASEMAP_URL,
        attr=BASEMAP_ATTR,
        control_scale=True,
    )
    if geojson is None or counts is None:
        return m

    by_id = counts.set_index("area_id")
    max_c = max(int(counts["shootings"].max()), 1)
    colormap = LinearColormap(colors=COLOR_SCALE, vmin=0, vmax=max_c)

    enriched = json.loads(json.dumps(geojson))
    for feat in enriched["features"]:
        props = feat["properties"]
        area_id = str(props.get(id_field, ""))
        row = by_id.loc[area_id] if area_id in by_id.index else None
        props["area_id"] = area_id
        props["area_label"] = str(row["area_label"]) if row is not None else area_id
        props["shootings"] = int(row["shootings"]) if row is not None else 0
        props["fatal"] = int(row["fatal"]) if row is not None else 0
        props["non_fatal"] = int(row["non_fatal"]) if row is not None else 0

    def style_fn(feature):
        val = feature["properties"]["shootings"]
        return {
            "fillColor": colormap(val),
            "color": "#ffffff",
            "weight": 0.6 if geography == "Census tracts" else 1.0,
            "fillOpacity": 0.70,
        }

    folium.GeoJson(
        enriched,
        name=geography,
        style_function=style_fn,
        highlight_function=lambda _: {"weight": 2.5, "color": UC_CHARCOAL, "fillOpacity": 0.8},
        tooltip=folium.GeoJsonTooltip(
            fields=["area_label", "shootings", "fatal", "non_fatal"],
            aliases=["", "Shootings", "Fatal", "Non-fatal"],
            style="font-size:12px; padding:6px 8px;",
        ),
    ).add_to(m)

    if points is not None and len(points):
        fg = folium.FeatureGroup(name="Individual shootings", show=True)
        for r in points.itertuples():
            folium.CircleMarker(
                location=[float(r.latitude), float(r.longitude)],
                radius=4,
                color="#ffffff",
                weight=0.8,
                fill=True,
                fill_color=TYPE_COLORS.get(r.shooting_type, TYPE_COLORS["Non-Fatal"]),
                fill_opacity=0.95,
                tooltip=f"{r.shooting_type} · {fmt_date(r.date)}",
                popup=folium.Popup(
                    f"<b>{r.shooting_type}</b><br>{fmt_date(r.date)} · {r.date:%I:%M %p}<br>"
                    f"{r.street}<br>{r.neighborhood} · District {r.district}",
                    max_width=260,
                ),
            ).add_to(fg)
        fg.add_to(m)
        folium.LayerControl(collapsed=True).add_to(m)
    return m


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
@st.cache_data
def logo_html() -> str:
    if not LOGO_PNG.exists():
        return '<div class="uc-title" style="border:0;padding:0">UNCORNERED</div>'
    encoded = base64.b64encode(LOGO_PNG.read_bytes()).decode("ascii")
    return f'<img class="uc-logo" src="data:image/png;base64,{encoded}" alt="Uncornered">'


def render_header(incidents: Optional[pd.DataFrame]) -> None:
    chips = ""
    if incidents is not None and len(incidents):
        fetched = pd.to_datetime(incidents["fetched_at_utc"].max(), utc=True, errors="coerce")
        updated = fmt_date(fetched.tz_convert("America/New_York")) if pd.notna(fetched) else "unknown"
        nxt = next_monthly_refresh(datetime.now())
        chips = (
            f'<span class="uc-chip">Data through <b>{fmt_date(incidents["date"].max())}</b></span>'
            f'<span class="uc-chip">Updated <b>{updated}</b></span>'
            f'<span class="uc-chip">Next refresh <b>{fmt_date(nxt)}</b></span>'
        )
    st.markdown(
        f"""
        <div class="uc-header">
          <div class="uc-brandline">
            {logo_html()}
            <div class="uc-title">Learning Dashboard</div>
          </div>
          <div class="uc-chips">{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_about(incidents: pd.DataFrame) -> None:
    n_total = len(incidents)
    n_dash = int((incidents["shooting_type_source"] == "arcgis_dashboard").sum())
    st.markdown(
        f"""
        <div class="uc-about">
          <h4>Shootings</h4>
          <a href="{CRIME_REPORTS_URL}" target="_blank">Analyze Boston crime incident reports</a>
          (Aug 2015 – present). A shooting is a report with <b>SHOOTING = 1</b> and offense
          <b>ASSAULT - AGGRAVATED</b> or <b>MURDER</b>. One row per incident.
          <h4>Fatal / non-fatal</h4>
          From the <a href="{PERSON_SHOT_URL}" target="_blank">Boston Person Shot dashboard</a>
          when the incident is on it ({n_dash:,} of {n_total:,}); otherwise murder = fatal,
          aggravated assault = non-fatal.
          <h4>Locations</h4>
          Reports without valid coordinates are left out. Neighborhoods and 2020 census tracts
          are assigned from each shooting's coordinates.
          <h4>Keep in mind</h4>
          Before 2019 most shootings were filed as "ASSAULT - AGGRAVATED - BATTERY", which this
          definition excludes, so 2015–2019 counts are lower than the true totals.
          <h4>Refresh</h4>
          Updated automatically on the 1st of every month.
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    for path in (INCIDENTS_CSV, NEIGH_GEOJSON, TRACT_GEOJSON):
        if not path.exists():
            render_header(None)
            st.error(f"Missing file: `{path}`. Run the fetch script first.")
            st.stop()

    incidents = load_incidents(INCIDENTS_CSV.stat().st_mtime)
    tracts_gdf = load_tracts_gdf()
    data_min = incidents["date"].min().date()
    data_max = incidents["date"].max().date()

    render_header(incidents)

    filters_col, main_col = st.columns([1, 3.4], gap="medium")

    # ---------------- Filters ----------------
    with filters_col:
        with st.container(border=True, key="card_filters"):
            st.markdown('<div class="uc-panel-title">Filters</div>', unsafe_allow_html=True)
            city = st.segmented_control(
                "City", list(CITY_VIEWS.keys()), default="Boston", selection_mode="single"
            ) or "Boston"

            preset = st.selectbox("Time period", PRESETS, index=0)
            dates = preset_range(preset, data_min, data_max)
            if dates is None:
                default_start = max(data_max - timedelta(days=364), data_min)
                c1, c2 = st.columns(2)
                start_date = c1.date_input("From", value=default_start, min_value=data_min, max_value=data_max)
                end_date = c2.date_input("To", value=data_max, min_value=data_min, max_value=data_max)
                if start_date > end_date:
                    st.error("From must be on or before To.")
                    st.stop()
            else:
                start_date, end_date = max(dates[0], data_min), dates[1]
                st.markdown(
                    f'<div class="uc-range">{fmt_date(start_date)} – {fmt_date(end_date)}</div>',
                    unsafe_allow_html=True,
                )

            outcome = st.segmented_control(
                "Outcome", ["All", "Fatal", "Non-Fatal"], default="All", selection_mode="single"
            ) or "All"
            geography = st.segmented_control(
                "Map areas", ["Census tracts", "Neighborhoods"], default="Census tracts",
                selection_mode="single",
            ) or "Census tracts"
            show_points = st.toggle("Show individual shootings", value=False)

    types = ["Fatal", "Non-Fatal"] if outcome == "All" else [outcome]
    period_label = f"{fmt_date(start_date)} – {fmt_date(end_date)}"

    if not CITY_VIEWS[city]["ready"]:
        with main_col:
            st.info(f"{city} shooting data is coming next — the map below is a preview.")
            with st.container(border=True, key="card_preview"):
                st_folium(
                    build_map(city, None, None, None, geography, ""),
                    height=560, returned_objects=[], use_container_width=True,
                )
        return

    in_period = in_range(incidents, start_date, end_date)
    filtered = in_period[in_period["shooting_type"].isin(types)]

    prev_start, prev_end = prior_period(start_date, end_date)
    prev = in_range(incidents, prev_start, prev_end) if prev_start >= data_min else None

    def count(df: Optional[pd.DataFrame], t: Optional[str] = None) -> Optional[int]:
        if df is None:
            return None
        return len(df) if t is None else int((df["shooting_type"] == t).sum())

    total_n, fatal_n, nonfatal_n = count(in_period), count(in_period, "Fatal"), count(in_period, "Non-Fatal")

    if geography == "Neighborhoods":
        geojson = load_neighborhoods()
        id_field = "name"
        names = [str(f["properties"]["name"]) for f in geojson["features"]]
        base = pd.DataFrame({"area_id": names, "area_label": names})
        counts = area_counts(filtered, "neighborhood", base)
        area_word = "neighborhood"
    else:
        geojson = load_tracts()
        id_field = "geoid20"
        base = tracts_gdf[["tract_id", "tract_label"]].rename(
            columns={"tract_id": "area_id", "tract_label": "area_label"}
        )
        counts = area_counts(filtered, "tract_id", base)
        area_word = "census tract"

    hood_counts = in_period["neighborhood"].value_counts()
    if len(hood_counts):
        top_hood, top_n = hood_counts.index[0], int(hood_counts.iloc[0])
        top_value = top_hood
        top_sub = f"{top_n:,} shootings · {top_n / max(total_n, 1):.0%} of total"
    else:
        top_value, top_sub = "—", "No shootings in this period"

    # ---------------- KPIs + map ----------------
    with main_col:
        st.markdown(
            '<div class="uc-kpis">'
            + kpi("Shootings", f"{total_n:,}", delta_html(total_n, count(prev)), UC_ORANGE)
            + kpi("Fatal", f"{fatal_n:,}", delta_html(fatal_n, count(prev, "Fatal")), TYPE_COLORS["Fatal"])
            + kpi("Non-fatal", f"{nonfatal_n:,}", delta_html(nonfatal_n, count(prev, "Non-Fatal")), TYPE_COLORS["Non-Fatal"])
            + kpi("Most affected neighborhood", top_value, top_sub, UC_CHARCOAL, small=True)
            + "</div>",
            unsafe_allow_html=True,
        )

        with st.container(border=True, key="card_map"):
            outcome_word = {"All": "Shootings", "Fatal": "Fatal shootings", "Non-Fatal": "Non-fatal shootings"}[outcome]
            head_l, head_r = st.columns([1.4, 1], vertical_alignment="center")
            head_l.markdown(
                f'<div class="uc-section">{outcome_word} by {area_word}</div>'
                f'<div class="uc-caption" style="margin:0">{period_label}</div>',
                unsafe_allow_html=True,
            )
            head_r.markdown(legend_html(int(counts["shootings"].max()), show_points), unsafe_allow_html=True)
            st_folium(
                build_map(city, geojson, counts, filtered if show_points else None, geography, id_field),
                height=560,
                returned_objects=[],
                use_container_width=True,
            )

    # ---------------- Insights ----------------
    trend_col, where_col, when_col = st.columns([1.35, 1, 1], gap="medium")
    with trend_col:
        with st.container(border=True, key="card_trend"):
            chart, granularity = trend_chart(filtered, start_date, end_date, types)
            st.markdown(
                f'<div class="uc-section">Over time</div><div class="uc-caption">{granularity} shootings · {period_label}</div>',
                unsafe_allow_html=True,
            )
            st.altair_chart(chart, use_container_width=True)
    with where_col:
        with st.container(border=True, key="card_where"):
            st.markdown(
                f'<div class="uc-section">Where</div><div class="uc-caption">Top 10 {area_word}s</div>',
                unsafe_allow_html=True,
            )
            chart = top_areas_chart(counts, types)
            if chart is None:
                st.caption("No shootings in this period.")
            else:
                st.altair_chart(chart, use_container_width=True)
    with when_col:
        with st.container(border=True, key="card_when"):
            st.markdown(
                '<div class="uc-section">When</div><div class="uc-caption">Day of week × time of day</div>',
                unsafe_allow_html=True,
            )
            st.altair_chart(when_chart(filtered), use_container_width=True)

    # ---------------- Recent + about ----------------
    recent_col, about_col = st.columns([1.9, 1], gap="medium")
    with recent_col:
        with st.container(border=True, key="card_recent"):
            st.markdown(
                f'<div class="uc-section">Shootings in this period</div>'
                f'<div class="uc-caption">{len(filtered):,} incidents · most recent first</div>',
                unsafe_allow_html=True,
            )
            table = filtered.sort_values("date", ascending=False)[
                ["date", "shooting_type", "neighborhood", "street", "district", "incident_number"]
            ]
            st.dataframe(
                table,
                hide_index=True,
                width="stretch",
                height=330,
                column_config={
                    "date": st.column_config.DatetimeColumn("Date", format="MMM D, YYYY · h:mm a"),
                    "shooting_type": "Outcome",
                    "neighborhood": "Neighborhood",
                    "street": "Street",
                    "district": "District",
                    "incident_number": "Incident #",
                },
            )
            st.download_button(
                "Download these shootings (CSV)",
                data=filtered.drop(columns=["date", "tract_id"]).to_csv(index=False).encode("utf-8"),
                file_name=f"boston_shootings_{start_date}_{end_date}.csv",
                mime="text/csv",
            )
    with about_col:
        with st.container(border=True, key="card_about"):
            st.markdown('<div class="uc-section">About the data</div>', unsafe_allow_html=True)
            render_about(incidents)


main()
