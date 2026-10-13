'''
Authors: Columbia University Uncornered Team

The file will extract all rows from the table on shooting incidents that occured from 2015 - 2024

This script uses requests and BeautifulSoup to scrape the Analyze Boston resource page for the current CSV download link, then downloads the CSV file directly. 

DO NOT MODIFY THIS FILE
'''

import io
import re
from urllib.parse import urljoin

import requests
import pandas as pd
from bs4 import BeautifulSoup

RESOURCE_PAGE = "https://data.boston.gov/dataset/shootings/resource/73c7e069-701f-4910-986d-b950f46c91a1"
OUTPUT_CSV = "boston_shootings.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def get_csv_download_url(resource_page: str) -> str:
    resp = requests.get(resource_page, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(resource_page, href)
        if "/download/" in full and full.lower().endswith(".csv"):
            return full

    match = re.search(r'https?://[^"\']+/download/[^"\']+\.csv', html, flags=re.I)
    if match:
        return match.group(0)

    match = re.search(r'/dataset/[^"\']+/resource/[^"\']+/download/[^"\']+\.csv', html, flags=re.I)
    if match:
        return urljoin(resource_page, match.group(0))

    raise RuntimeError("Could not find a CSV download link on the resource page.")


def normalize_prev_years_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Clean raw column names
    df.columns = [str(c).strip() for c in df.columns]

    # Rename to match this_year / last_year schema
    rename_map = {
        "incident_num": "Incident_Num",
        "shooting_date": "Shooting_Date",
        "district": "District",
        "shooting_type_v2": "Shooting_Type_V2",
        "victim_gender": "Victim_Gender",
        "victim_race": "Victim_Race",
        "victim_ethnicity_nibrs": "Victim_Ethnicity_NIBRS",
        "multi_victim": "Multi_Victim",
    }
    df = df.rename(columns=rename_map)

    # Remove the first 2 characters from incident number
    if "Incident_Num" in df.columns:
        df["Incident_Num"] = df["Incident_Num"].astype("string").str.strip()
        df["Incident_Num"] = df["Incident_Num"].apply(
            lambda x: x[1:] if pd.notna(x) and len(x) >= 2 else x
        )

    # Add missing columns so schema matches this_year / last_year
    if "Location" not in df.columns:
        df["Location"] = pd.NA

    if "NEIGHBORHOOD" not in df.columns:
        df["NEIGHBORHOOD"] = pd.NA

    if "Age" not in df.columns:
        df["Age"] = pd.NA

    # Optional cleanup for multi-victim flag
    if "Multi_Victim" in df.columns:
        df["Multi_Victim"] = df["Multi_Victim"].replace({
            "t": True,
            "f": False,
            "True": True,
            "False": False
        })

    # Reorder so it lines up with the newer-year files
    preferred_order = [
        "Incident_Num",
        "Shooting_Date",
        "Shooting_Type_V2",
        "Location",
        "NEIGHBORHOOD",
        "District",
        "Victim_Gender",
        "Victim_Race",
        "Victim_Ethnicity_NIBRS",
        "Age",
        "Multi_Victim",
    ]

    cols = [c for c in preferred_order if c in df.columns] + [c for c in df.columns if c not in preferred_order]
    df = df[cols]

    return df


def download_csv(csv_url: str, output_path: str) -> None:
    with requests.get(csv_url, headers=HEADERS, timeout=60, stream=True) as resp:
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def get_boston_prev_years_df(save_csv=True, output_csv=OUTPUT_CSV):
    csv_url = get_csv_download_url(RESOURCE_PAGE)

    # Read raw download into dataframe
    resp = requests.get(csv_url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))

    # Normalize to match other Boston files
    df = normalize_prev_years_df(df)

    if save_csv:
        df.to_csv(output_csv, index=False)

    return df


def main():
    df = get_boston_prev_years_df(save_csv=True, output_csv=OUTPUT_CSV)

    print(f"\nSaved to: {OUTPUT_CSV}")
    print(f"\nRows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print("\nColumn names:")
    for col in df.columns:
        print(" -", col)

    print("\nFirst 5 rows:")
    print(df.head())


if __name__ == "__main__":
    main()