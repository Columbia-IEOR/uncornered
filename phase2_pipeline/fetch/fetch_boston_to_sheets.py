"""
Unified Boston shootings fetch → Google Sheet.

Produces two datasets (each with locations) for the Boston dashboard:

1. Total shootings  →  tab "Boston"  /  boston_shooting_incidents.csv
   Analyze Boston — Crime Incident Reports (August 2015 – To Date)
     https://data.boston.gov/dataset/crime-incident-reports-august-2015-to-date-source-new-system
   One CSV resource per year (2015 … 2022) plus "2023 to Present". Each is
   queried through the CKAN Datastore SQL API with the shooting filter:
     SHOOTING = 1            (2015–2018 files use 'Y' instead of '1')
     OFFENSE_DESCRIPTION  = 'ASSAULT - AGGRAVATED'  or
                            'MURDER, NON-NEGLIGENT MANSLAUGHTER'
     ORDER BY OCCURRED_ON_DATE
   One row per incident.

2. Fatal / Non-Fatal  →  tab "Boston_Fatal_NonFatal"  /  boston_shooting_victims.csv
   Boston Person Shot ArcGIS dashboard
     https://www.arcgis.com/apps/dashboards/dbd16dfec5b54734bd7d927b26b38a24
   One row per victim.

Every incident is classified Fatal / Non-Fatal: from the dashboard's victim
outcomes when the incident is on it (same incident number), otherwise from the
offense (murder → Fatal, aggravated assault → Non-Fatal).

Rows without valid Boston coordinates are dropped from both datasets
(the incident numbers are logged on every run).

Usage (from repo root):
  python3 phase2_pipeline/fetch/fetch_boston_to_sheets.py
  python3 phase2_pipeline/fetch/fetch_boston_to_sheets.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import gspread
import pandas as pd
import requests
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PHASE2_ROOT = Path(__file__).resolve().parents[1]
CREDS_PATH = PHASE2_ROOT / "secrets" / "google_service_account.json"
CLEANED_DIR = PHASE2_ROOT / "data" / "cleaned"
INCIDENTS_CSV = CLEANED_DIR / "boston_shooting_incidents.csv"
VICTIMS_CSV = CLEANED_DIR / "boston_shooting_victims.csv"
NEIGH_GEOJSON = PHASE2_ROOT / "data" / "boundaries" / "boston_neighborhoods.geojson"

SHEET_ID = "1J0HyZ0k8C9cvgbfXSWQfo5_BPYOvQD2aE3drWGiU2Lc"
INCIDENTS_WORKSHEET = "Boston"
VICTIMS_WORKSHEET = "Boston_Fatal_NonFatal"

DATASET_ID = "crime-incident-reports-august-2015-to-date-source-new-system"
DATASET_URL = f"https://data.boston.gov/dataset/{DATASET_ID}"
CKAN_API = "https://data.boston.gov/api/3/action"

# Only these two offenses; 'ASSAULT - AGGRAVATED - BATTERY' is deliberately excluded.
# Murder appears under two spellings in the data (NEGLIGENT / NEGLIGIENT).
# The Datastore SQL endpoint rejects functions like UPPER/TRIM, so match exact values.
OFFENSES = [
    "ASSAULT - AGGRAVATED",
    "MURDER, NON-NEGLIGENT MANSLAUGHTER",
    "MURDER, NON-NEGLIGIENT MANSLAUGHTER",
]
SHOOTING_FILTER = (
    "\"SHOOTING\" IN ('1', 'Y') AND \"OFFENSE_DESCRIPTION\" IN ("
    + ", ".join(f"'{o}'" for o in OFFENSES)
    + ")"
)

DASHBOARD_URL = "https://www.arcgis.com/apps/dashboards/dbd16dfec5b54734bd7d927b26b38a24"
FEATURE_LAYER_URL = (
    "https://services.arcgis.com/sFnw0xNflSi8J0uh/arcgis/rest/services/"
    "Person_Shot_PubView/FeatureServer/0"
)
ARCGIS_PAGE_SIZE = 2000  # layer maxRecordCount

LOCAL_TZ = "America/New_York"

# Rough Boston bounding box — coordinates outside it (0, -1, etc.) are treated as missing.
LAT_RANGE = (42.2, 42.45)
LON_RANGE = (-71.2, -70.85)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

INCIDENT_COLUMNS = [
    "incident_number",
    "occurred_on_date",
    "year",
    "month",
    "quarter",
    "day_of_week",
    "hour",
    "offense_code",
    "offense_description",
    "shooting_type",
    "shooting_type_source",
    "victims_total",
    "victims_fatal",
    "victims_non_fatal",
    "district",
    "reporting_area",
    "street",
    "neighborhood",
    "latitude",
    "longitude",
    "source_resource",
    "fetched_at_utc",
]

VICTIM_COLUMNS = [
    "incident_number",
    "shooting_date",
    "year",
    "month",
    "quarter",
    "day_of_week",
    "hour",
    "shooting_type",
    "victim_gender",
    "victim_race",
    "victim_ethnicity_nibrs",
    "age",
    "multi_victim",
    "district",
    "location",
    "neighborhood",
    "latitude",
    "longitude",
    "fetched_at_utc",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("boston_fetch")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def incident_key(series: pd.Series) -> pd.Series:
    """Common join key: 'I152000196-00' and '152000196' → '152000196'."""
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .str.replace(r"-\d+$", "", regex=True)
        .str.replace(r"^I", "", regex=True)
    )


def clean_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    ok = df["latitude"].between(*LAT_RANGE) & df["longitude"].between(*LON_RANGE)
    df.loc[~ok, ["latitude", "longitude"]] = pd.NA
    return df


def drop_missing_coordinates(df: pd.DataFrame, name: str) -> pd.DataFrame:
    missing = df["latitude"].isna() | df["longitude"].isna()
    if missing.any():
        log.info(
            "Dropped %s %s rows without valid coordinates: %s",
            int(missing.sum()),
            name,
            ", ".join(df.loc[missing, "incident_number"].astype(str)),
        )
    return df.loc[~missing].copy()


def lookup_neighborhood(df: pd.DataFrame) -> pd.Series:
    """Neighborhood name from lat/lon using the same polygons as the dashboard map."""
    hood = pd.Series(pd.NA, index=df.index, dtype="object")
    if not NEIGH_GEOJSON.exists():
        log.warning("Neighborhood boundaries missing at %s — skipping.", NEIGH_GEOJSON)
        return hood
    has_geo = df["latitude"].notna() & df["longitude"].notna()
    pts = gpd.GeoDataFrame(
        df.loc[has_geo, []],
        geometry=gpd.points_from_xy(df.loc[has_geo, "longitude"], df.loc[has_geo, "latitude"]),
        crs="EPSG:4326",
    )
    hoods = gpd.read_file(NEIGH_GEOJSON).to_crs(epsg=4326)[["name", "geometry"]]
    joined = gpd.sjoin(pts, hoods, how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    hood.loc[joined.index] = joined["name"]
    return hood


def add_time_parts(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    d = df[date_col]
    df["year"] = d.dt.year.astype("Int64")
    df["month"] = d.dt.month.astype("Int64")
    df["quarter"] = d.dt.quarter.astype("Int64")
    df["day_of_week"] = d.dt.day_name()
    df["hour"] = d.dt.hour.astype("Int64")
    return df


# ---------------------------------------------------------------------------
# Source 1: Analyze Boston crime incident reports (CKAN Datastore)
# ---------------------------------------------------------------------------
def list_year_resources() -> list[dict]:
    """Return the datastore-backed yearly CSV resources of the crime dataset."""
    resp = requests.get(f"{CKAN_API}/package_show", params={"id": DATASET_ID}, timeout=60)
    resp.raise_for_status()
    resources = resp.json()["result"]["resources"]
    yearly = [
        r
        for r in resources
        if r.get("datastore_active")
        and str(r.get("format", "")).upper() == "CSV"
        and str(r.get("name") or "").startswith("Crime Incident Reports")
    ]
    if not yearly:
        raise RuntimeError("No yearly crime incident resources found on Analyze Boston.")
    return sorted(yearly, key=lambda r: r["name"])


def fetch_resource_shootings(resource: dict) -> pd.DataFrame:
    sql = (
        f'SELECT * FROM "{resource["id"]}" '
        f"WHERE {SHOOTING_FILTER} "
        f'ORDER BY "OCCURRED_ON_DATE"'
    )
    resp = requests.get(f"{CKAN_API}/datastore_search_sql", params={"sql": sql}, timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"Datastore query failed for {resource['name']}: {payload.get('error')}")
    df = pd.DataFrame(payload["result"]["records"])
    df["source_resource"] = resource["name"]
    return df


def fetch_crime_reports() -> pd.DataFrame:
    log.info("Source 1 — crime incident reports: %s", DATASET_URL)
    frames = []
    for res in list_year_resources():
        df = fetch_resource_shootings(res)
        log.info("  %-45s → %s shooting rows", res["name"], f"{len(df):,}")
        frames.append(df)

    raw = pd.concat(frames, ignore_index=True)
    if raw.empty:
        raise RuntimeError("No shooting records returned from Analyze Boston.")
    return raw


def _clean_street(value) -> str:
    """STREET sometimes holds a multi-line address ('X ST\\nROXBURY, MA 02120\\nU')."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.split("\n")[0]).strip()


def clean_crime_reports(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per incident from the crime incident reports."""
    df = raw.rename(
        columns={
            "INCIDENT_NUMBER": "incident_number",
            "OCCURRED_ON_DATE": "occurred_on_date",
            "OFFENSE_CODE": "offense_code",
            "OFFENSE_DESCRIPTION": "offense_description",
            "DISTRICT": "district",
            "REPORTING_AREA": "reporting_area",
            "STREET": "street",
            "Lat": "latitude",
            "Long": "longitude",
        }
    ).copy()

    # Times are Boston local time; the datastore just appends '+00'.
    df["occurred_on_date"] = pd.to_datetime(
        df["occurred_on_date"].astype(str).str.replace(r"[+-]\d{2}(:?\d{2})?$", "", regex=True),
        errors="coerce",
    )
    before = len(df)
    df = df.dropna(subset=["occurred_on_date"]).copy()
    if before - len(df):
        log.warning("Dropped %s crime rows with invalid OCCURRED_ON_DATE", before - len(df))

    for col in ["incident_number", "offense_description", "district", "reporting_area"]:
        df[col] = df[col].astype("string").str.strip()
    df["street"] = df["street"].map(_clean_street)
    df["offense_code"] = pd.to_numeric(df["offense_code"], errors="coerce").astype("Int64")
    df = clean_coordinates(df)

    # An incident can carry both offenses (assault + murder) → keep one row, list both.
    df["is_murder"] = df["offense_description"].str.startswith("MURDER", na=False)
    df = df.sort_values(["incident_number", "is_murder"], ascending=[True, False])
    offenses = df.groupby("incident_number")["offense_description"].agg(
        lambda s: " | ".join(dict.fromkeys(s.dropna()))
    )
    df = df.drop_duplicates(subset=["incident_number"], keep="first").set_index("incident_number")
    df["offense_description"] = offenses
    df = df.reset_index()

    df["key"] = incident_key(df["incident_number"])
    return df


# ---------------------------------------------------------------------------
# Source 2: Person Shot ArcGIS dashboard (FeatureServer behind it)
# ---------------------------------------------------------------------------
def fetch_arcgis_victims() -> pd.DataFrame:
    log.info("Source 2 — Person Shot dashboard: %s", DASHBOARD_URL)
    rows = []
    offset = 0
    while True:
        resp = requests.get(
            f"{FEATURE_LAYER_URL}/query",
            params={
                "f": "json",
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "false",
                "orderByFields": "OBJECTID ASC",
                "resultOffset": offset,
                "resultRecordCount": ARCGIS_PAGE_SIZE,
            },
            timeout=120,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("error"):
            raise RuntimeError(f"ArcGIS query error: {payload['error']}")
        features = payload.get("features") or []
        rows.extend(f.get("attributes") or {} for f in features)
        if len(features) < ARCGIS_PAGE_SIZE:
            break
        offset += ARCGIS_PAGE_SIZE

    if not rows:
        raise RuntimeError("No victim records returned from the Person Shot dashboard.")
    victims = pd.DataFrame(rows).drop_duplicates(subset=["OBJECTID"])
    log.info("  %s victim rows", f"{len(victims):,}")
    return victims


def clean_arcgis_victims(raw: pd.DataFrame, fetched_at: str) -> pd.DataFrame:
    """One row per victim, Fatal / Non-Fatal, with location."""
    df = raw.rename(
        columns={
            "Incident_Num": "incident_number",
            "Shooting_Date": "shooting_date",
            "Shooting_Type_V2": "shooting_type",
            "Victim_Gender": "victim_gender",
            "Victim_Race": "victim_race",
            "Victim_Ethnicity_NIBRS": "victim_ethnicity_nibrs",
            "Age": "age",
            "Multi_Victim": "multi_victim",
            "District": "district",
            "Location": "location",
            "NEIGHBORHOOD": "arc_neighborhood",
            "LATITUDE": "latitude",
            "LONGITUDE": "longitude",
        }
    ).copy()

    # Dashboard dates are true UTC epoch ms → Boston local time to match crime reports.
    df["shooting_date"] = (
        pd.to_datetime(df["shooting_date"], unit="ms", utc=True, errors="coerce")
        .dt.tz_convert(LOCAL_TZ)
        .dt.tz_localize(None)
    )
    df = df.dropna(subset=["shooting_date"]).copy()

    df["incident_number"] = (
        df["incident_number"].astype("string").str.strip().str.replace(r"-\d+$", "", regex=True)
    )
    df["shooting_type"] = df["shooting_type"].astype("string").str.strip()
    df["location"] = df["location"].astype("string").str.strip()
    df["multi_victim"] = pd.to_numeric(df["multi_victim"], errors="coerce").fillna(0).astype(int).astype(bool)
    df = drop_missing_coordinates(clean_coordinates(df), "dashboard victim")
    df["neighborhood"] = lookup_neighborhood(df).fillna(df["arc_neighborhood"])
    df = add_time_parts(df, "shooting_date")
    df["key"] = incident_key(df["incident_number"])
    df["fetched_at_utc"] = fetched_at

    df = df.sort_values(["shooting_date", "incident_number"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Build the two output tables
# ---------------------------------------------------------------------------
def build_incidents(crime: pd.DataFrame, victims: pd.DataFrame, fetched_at: str) -> pd.DataFrame:
    """Crime-report incidents + dashboard victim counts where the incident matches."""
    per_incident = victims.groupby("key").agg(
        victims_total=("shooting_type", "size"),
        victims_fatal=("shooting_type", lambda s: int((s == "Fatal").sum())),
        dash_lat=("latitude", "first"),
        dash_lon=("longitude", "first"),
    )
    df = crime.merge(per_incident, left_on="key", right_index=True, how="left")

    df["victims_total"] = df["victims_total"].astype("Int64")
    df["victims_fatal"] = df["victims_fatal"].astype("Int64")
    df["victims_non_fatal"] = df["victims_total"] - df["victims_fatal"]
    # Fatal / Non-Fatal: dashboard victim outcome when the incident is on it,
    # otherwise the offense (murder → Fatal, aggravated assault → Non-Fatal).
    on_dashboard = df["victims_total"].notna()
    dashboard_fatal = df["victims_fatal"].fillna(0) > 0
    offense_fatal = df["offense_description"].str.contains("MURDER", na=False)
    df["shooting_type"] = (
        dashboard_fatal.where(on_dashboard, offense_fatal).map({True: "Fatal", False: "Non-Fatal"})
    )
    df["shooting_type_source"] = on_dashboard.map(
        {True: "arcgis_dashboard", False: "offense_description"}
    )

    no_geo = df["latitude"].isna()
    df.loc[no_geo, "latitude"] = df.loc[no_geo, "dash_lat"]
    df.loc[no_geo, "longitude"] = df.loc[no_geo, "dash_lon"]
    df = drop_missing_coordinates(df, "crime incident")

    df["neighborhood"] = lookup_neighborhood(df)
    df = add_time_parts(df, "occurred_on_date")
    df["fetched_at_utc"] = fetched_at

    df = df.sort_values(["occurred_on_date", "incident_number"]).reset_index(drop=True)
    df["occurred_on_date"] = df["occurred_on_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df[INCIDENT_COLUMNS]


def finalize_victims(victims: pd.DataFrame) -> pd.DataFrame:
    out = victims.copy()
    out["shooting_date"] = out["shooting_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out[VICTIM_COLUMNS]


def validate(incidents: pd.DataFrame, victims: pd.DataFrame) -> None:
    """Stop before touching the Sheet if either pull looks broken."""
    if incidents.empty or victims.empty:
        raise RuntimeError("A dataset came back empty — refusing to overwrite the Sheet.")
    this_year = datetime.now().year
    for name, df in [("crime reports", incidents), ("dashboard", victims)]:
        if not (df["year"] == this_year).any():
            log.warning("No %s rows for %s yet — check the source.", name, this_year)
    log.info(
        "Incidents: %s matched on dashboard | %s missing coordinates",
        int(incidents["victims_total"].notna().sum()),
        int(incidents["latitude"].isna().sum()),
    )
    log.info(
        "Victims: %s fatal, %s non-fatal | %s missing coordinates",
        int((victims["shooting_type"] == "Fatal").sum()),
        int((victims["shooting_type"] == "Non-Fatal").sum()),
        int(victims["latitude"].isna().sum()),
    )


# ---------------------------------------------------------------------------
# Local + Sheets output
# ---------------------------------------------------------------------------
def save_local_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log.info("Saved local copy → %s (%s rows)", path, f"{len(df):,}")


def open_spreadsheet(sheet_id: str):
    if not CREDS_PATH.exists():
        raise FileNotFoundError(
            f"Missing credentials at {CREDS_PATH}. "
            "Place the service account JSON there first."
        )
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(sheet_id)


def get_worksheet(sh, name: str, n_cols: int):
    try:
        return sh.worksheet(name)
    except gspread.WorksheetNotFound:
        log.info("Worksheet '%s' not found — creating it.", name)
        return sh.add_worksheet(title=name, rows=1000, cols=n_cols)


def _cell_value(v):
    """Convert pandas/numpy values into JSON-safe Python scalars for Sheets."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        try:
            v = v.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return float(v)
    return str(v)


def write_dataframe_to_sheet(ws, df: pd.DataFrame) -> None:
    columns = list(df.columns)
    values = [columns]
    for row in df.itertuples(index=False, name=None):
        values.append([_cell_value(v) for v in row])

    ws.clear()
    end_a1 = rowcol_to_a1(len(values), len(columns))
    ws.update(range_name=f"A1:{end_a1}", values=values, value_input_option="USER_ENTERED")
    log.info("Wrote %s data rows to worksheet '%s'", f"{len(df):,}", ws.title)


def print_year_summary(incidents: pd.DataFrame, victims: pd.DataFrame) -> None:
    inc = incidents.groupby("year").size()
    vic = victims.groupby(["year", "shooting_type"]).size().unstack(fill_value=0)
    log.info("By year: shooting incidents (crime CSV) | fatal / non-fatal victims (dashboard)")
    for year in sorted(set(inc.index) | set(vic.index)):
        log.info(
            "  %s → %4s incidents | %3s fatal, %3s non-fatal",
            year,
            int(inc.get(year, 0)),
            int(vic.loc[year].get("Fatal", 0)) if year in vic.index else 0,
            int(vic.loc[year].get("Non-Fatal", 0)) if year in vic.index else 0,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(dry_run: bool = False) -> None:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    crime = clean_crime_reports(fetch_crime_reports())
    victims = clean_arcgis_victims(fetch_arcgis_victims(), fetched_at=fetched_at)
    incidents = build_incidents(crime, victims, fetched_at=fetched_at)
    victims_out = finalize_victims(victims)

    print_year_summary(incidents, victims_out)
    validate(incidents, victims_out)
    save_local_csv(incidents, INCIDENTS_CSV)
    save_local_csv(victims_out, VICTIMS_CSV)

    if dry_run:
        log.info("Dry run — skipped Google Sheets write.")
        return

    sh = open_spreadsheet(SHEET_ID)
    write_dataframe_to_sheet(get_worksheet(sh, INCIDENTS_WORKSHEET, len(INCIDENT_COLUMNS)), incidents)
    write_dataframe_to_sheet(get_worksheet(sh, VICTIMS_WORKSHEET, len(VICTIM_COLUMNS)), victims_out)
    log.info("Done. Spreadsheet '%s' refreshed at %s (UTC).", sh.title, fetched_at)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Boston shootings (Analyze Boston crime incident reports + "
            "Person Shot ArcGIS dashboard) → Google Sheet"
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + clean + save CSVs only; do not write to Google Sheets",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
