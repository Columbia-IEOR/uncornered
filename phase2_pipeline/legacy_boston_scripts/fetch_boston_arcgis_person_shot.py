"""
Unified Boston shootings fetch → Google Sheet.

Source: City of Boston Person Shot ArcGIS Dashboard backend
  Dashboard: https://www.arcgis.com/apps/dashboards/dbd16dfec5b54734bd7d927b26b38a24
  Feature layer (same live data the dashboard uses):
    Person_Shot_PubView / FeatureServer/0

- Pulls ALL years in one run
- Cleans / standardizes (includes lat/lon, neighborhood, address)
- Replaces the Boston tab so each monthly re-run stays current

Usage (from repo root):
  python3 phase2_pipeline/fetch/fetch_boston_to_sheets.py
  python3 phase2_pipeline/fetch/fetch_boston_to_sheets.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

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
LOCAL_CSV = PHASE2_ROOT / "data" / "cleaned" / "boston_shootings_master.csv"

SHEET_ID = "1J0HyZ0k8C9cvgbfXSWQfo5_BPYOvQD2aE3drWGiU2Lc"
WORKSHEET_NAME = "Boston"

DASHBOARD_URL = "https://www.arcgis.com/apps/dashboards/dbd16dfec5b54734bd7d927b26b38a24"
FEATURE_LAYER_URL = (
    "https://services.arcgis.com/sFnw0xNflSi8J0uh/arcgis/rest/services/"
    "Person_Shot_PubView/FeatureServer/0"
)
PAGE_SIZE = 2000  # layer maxRecordCount

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

OUTPUT_COLUMNS = [
    "incident_num",
    "shooting_date",
    "year",
    "month",
    "quarter",
    "district",
    "neighborhood",
    "location",
    "latitude",
    "longitude",
    "shooting_type_v2",
    "victim_gender",
    "victim_race",
    "victim_ethnicity_nibrs",
    "age",
    "multi_victim",
    "day_of_week",
    "hour_of_day",
    "is_primary_incident",
    "fetched_at_utc",
    "source_dashboard",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("boston_fetch")


# ---------------------------------------------------------------------------
# Fetch (ArcGIS FeatureServer behind the dashboard)
# ---------------------------------------------------------------------------
def fetch_all_boston_shootings() -> pd.DataFrame:
    """Download every Person Shot record powering the ArcGIS dashboard."""
    log.info("Source dashboard: %s", DASHBOARD_URL)
    log.info("Fetching from FeatureServer: %s", FEATURE_LAYER_URL)

    count_resp = requests.get(
        f"{FEATURE_LAYER_URL}/query",
        params={"f": "json", "where": "1=1", "returnCountOnly": "true"},
        timeout=60,
    )
    count_resp.raise_for_status()
    total = int(count_resp.json().get("count") or 0)
    log.info("Remote count: %s", f"{total:,}")

    all_attrs = []
    offset = 0
    while True:
        params = {
            "f": "json",
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "orderByFields": "OBJECTID ASC",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
        }
        resp = requests.get(f"{FEATURE_LAYER_URL}/query", params=params, timeout=120)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("error"):
            raise RuntimeError(f"ArcGIS query error: {payload['error']}")

        features = payload.get("features") or []
        if not features:
            break

        all_attrs.extend(f.get("attributes") or {} for f in features)
        log.info("  downloaded %s / %s rows", f"{len(all_attrs):,}", f"{total:,}")

        if len(features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

        # Safety against infinite loops if offset is ignored
        if total and len(all_attrs) >= total:
            break

    if not all_attrs:
        raise RuntimeError("No Boston shooting records returned from ArcGIS layer.")

    return pd.DataFrame(all_attrs)


# ---------------------------------------------------------------------------
# Clean / standardize
# ---------------------------------------------------------------------------
def _epoch_ms_to_datetime(series: pd.Series) -> pd.Series:
    """ArcGIS dates often arrive as epoch milliseconds."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit="ms", utc=True, errors="coerce")
    return pd.to_datetime(series, utc=True, errors="coerce")


def clean_boston(df: pd.DataFrame, fetched_at: str) -> pd.DataFrame:
    df = df.copy()
    # Normalize API field names → snake_case keys we control
    rename = {
        "Incident_Num": "incident_num",
        "Shooting_Date": "shooting_date",
        "District": "district",
        "Shooting_Type_V2": "shooting_type_v2",
        "Victim_Gender": "victim_gender",
        "Victim_Race": "victim_race",
        "Victim_Ethnicity_NIBRS": "victim_ethnicity_nibrs",
        "Multi_Victim": "multi_victim",
        "Location": "location",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "IsPrimaryIncident": "is_primary_incident",
        "HOUR_OF_DAY": "hour_of_day",
        "DAY_OF_WEEK": "day_of_week",
        "YEAR": "year",
        "QUARTER": "quarter",
        "MONTH": "month",
        "NEIGHBORHOOD": "neighborhood",
        "Age": "age",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df.columns = [str(c).strip() for c in df.columns]

    if "shooting_date" not in df.columns:
        raise RuntimeError("Expected column 'Shooting_Date' missing from ArcGIS response.")

    df["shooting_date"] = _epoch_ms_to_datetime(df["shooting_date"])
    before = len(df)
    df = df.dropna(subset=["shooting_date"]).copy()
    dropped = before - len(df)
    if dropped:
        log.warning("Dropped %s rows with invalid shooting_date", dropped)

    # Prefer layer YEAR/MONTH when present; else derive
    if "year" not in df.columns or df["year"].isna().all():
        df["year"] = df["shooting_date"].dt.year
    if "month" not in df.columns or df["month"].isna().all():
        df["month"] = df["shooting_date"].dt.month
    if "quarter" not in df.columns or df["quarter"].isna().all():
        df["quarter"] = df["shooting_date"].dt.quarter

    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["month"] = pd.to_numeric(df["month"], errors="coerce").astype("Int64")
    df["quarter"] = pd.to_numeric(df["quarter"], errors="coerce").astype("Int64")

    df["shooting_date"] = df["shooting_date"].dt.strftime("%Y-%m-%d %H:%M:%S%z")

    if "multi_victim" in df.columns:
        df["multi_victim"] = pd.to_numeric(df["multi_victim"], errors="coerce").fillna(0).astype(int)
        df["multi_victim"] = df["multi_victim"].map(lambda x: bool(x))

    if "is_primary_incident" in df.columns:
        df["is_primary_incident"] = (
            pd.to_numeric(df["is_primary_incident"], errors="coerce").fillna(0).astype(int)
        )

    # Rows are per victim — same Incident_Num can appear more than once.
    # Prefer OBJECTID uniqueness; do not collapse to one row per incident.
    if "OBJECTID" in df.columns:
        df = df.drop_duplicates(subset=["OBJECTID"], keep="last")
    elif "incident_num" in df.columns:
        df["incident_num"] = df["incident_num"].astype(str).str.strip()
        subset = [
            c
            for c in [
                "incident_num",
                "shooting_date",
                "victim_gender",
                "victim_race",
                "age",
                "location",
            ]
            if c in df.columns
        ]
        df = df.drop_duplicates(subset=subset, keep="last")
    else:
        df = df.drop_duplicates()

    if "incident_num" in df.columns:
        df["incident_num"] = df["incident_num"].astype(str).str.strip()

    df["fetched_at_utc"] = fetched_at
    df["source_dashboard"] = DASHBOARD_URL

    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    df = (
        df[OUTPUT_COLUMNS]
        .sort_values(["shooting_date", "incident_num"])
        .reset_index(drop=True)
    )
    return df


# ---------------------------------------------------------------------------
# Local + Sheets output
# ---------------------------------------------------------------------------
def save_local_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log.info("Saved local copy → %s (%s rows)", path, f"{len(df):,}")


def open_worksheet(sheet_id: str, worksheet_name: str):
    if not CREDS_PATH.exists():
        raise FileNotFoundError(
            f"Missing credentials at {CREDS_PATH}. "
            "Place the service account JSON there first."
        )
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        log.info("Worksheet '%s' not found — creating it.", worksheet_name)
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=len(OUTPUT_COLUMNS))
    return sh, ws


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
    values = [OUTPUT_COLUMNS]
    for row in df.itertuples(index=False, name=None):
        values.append([_cell_value(v) for v in row])

    ws.clear()
    end_a1 = rowcol_to_a1(len(values), len(OUTPUT_COLUMNS))
    ws.update(range_name=f"A1:{end_a1}", values=values, value_input_option="USER_ENTERED")
    log.info("Wrote %s data rows to worksheet '%s'", f"{len(df):,}", ws.title)


def print_month_summary(df: pd.DataFrame) -> None:
    counts = (
        df.groupby(["year", "month"], as_index=False)
        .size()
        .rename(columns={"size": "incidents"})
        .sort_values(["year", "month"])
    )
    log.info("Incidents by year-month (tail):")
    for _, r in counts.tail(12).iterrows():
        log.info("  %04d-%02d → %s", int(r["year"]), int(r["month"]), int(r["incidents"]))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(dry_run: bool = False) -> None:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = fetch_all_boston_shootings()
    clean = clean_boston(raw, fetched_at=fetched_at)

    missing_geo = clean["latitude"].isna().sum() + (clean["latitude"] == "").sum()
    log.info(
        "Cleaned dataset: %s rows | %s → %s | missing lat: %s",
        f"{len(clean):,}",
        clean["shooting_date"].min(),
        clean["shooting_date"].max(),
        int(clean["latitude"].isna().sum()),
    )
    print_month_summary(clean)
    save_local_csv(clean, LOCAL_CSV)

    if dry_run:
        log.info("Dry run — skipped Google Sheets write.")
        return

    sh, ws = open_worksheet(SHEET_ID, WORKSHEET_NAME)
    write_dataframe_to_sheet(ws, clean)
    log.info(
        "Done. Spreadsheet '%s' / tab '%s' refreshed at %s (UTC).",
        sh.title,
        ws.title,
        fetched_at,
    )
    log.info(
        "Monthly habit: re-run this same file each month. "
        "Each run reloads ALL years from the dashboard data source."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Fetch all Boston shootings from ArcGIS dashboard layer → Google Sheet"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + clean + save CSV only; do not write to Google Sheets",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
