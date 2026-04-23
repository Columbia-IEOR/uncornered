'''
Authors: Columbia University Uncornered Team

The file will extract all rows from the table on shooting incidents related to Boston
Run this file on a weekly basis to refresh the data with any new updates

'''

import pandas as pd

from download_boston_this_year import get_boston_this_year_df
from download_boston_last_year import get_boston_last_year_df
from download_boston_prev_years import get_boston_prev_years_df

MASTER_CSV = "boston_shootings.csv"

def standardize_columns(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    rename_map = {
        "Neighborhood": "NEIGHBORHOOD",
        "Victim Ethnicity NIBRS": "Victim_Ethnicity_NIBRS",
        "Victim Gender": "Victim_Gender",
        "Victim Race": "Victim_Race",
        "Incident Num": "Incident_Num",
        "Shooting Date": "Shooting_Date",
        "Shooting Type V2": "Shooting_Type_V2",
    }
    existing = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=existing)

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()

    return df

def build_boston_data_query():
    df_this_year = get_boston_this_year_df(save_csv=True)
    df_this_year["source_period"] = "this_year"

    df_last_year = get_boston_last_year_df(save_csv=True)
    df_last_year["source_period"] = "last_year"

    df_prev_years = get_boston_prev_years_df(save_csv=True)
    df_prev_years["source_period"] = "previous_years"

    df_this_year = standardize_columns(df_this_year)
    df_last_year = standardize_columns(df_last_year)
    df_prev_years = standardize_columns(df_prev_years)

    boston_data_query = pd.concat(
        [df_this_year, df_last_year, df_prev_years],
        ignore_index=True,
        sort=False
    )

    dedupe_cols = [
        c for c in [
            "Incident_Num", "Shooting_Date", "Shooting_Type_V2", "Location",
            "NEIGHBORHOOD", "District", "Victim_Gender", "Victim_Race",
            "Victim_Ethnicity_NIBRS", "Age"
        ]
        if c in boston_data_query.columns
    ]

    if dedupe_cols:
        boston_data_query = boston_data_query.drop_duplicates(subset=dedupe_cols)
    else:
        boston_data_query = boston_data_query.drop_duplicates()

    if "Shooting_Date" in boston_data_query.columns:
        boston_data_query["Shooting_Date_Parsed"] = pd.to_datetime(
        boston_data_query["Shooting_Date"],
        errors="coerce",
        utc=True
    )

    boston_data_query = boston_data_query.sort_values(
        by="Shooting_Date_Parsed",
        ascending=True,
        na_position="last"
    ).reset_index(drop=True)

    boston_data_query.to_csv(MASTER_CSV, index=False)
    return boston_data_query

def prompt_and_print_timeframe(df):
    if "Shooting_Date_Parsed" not in df.columns:
        print("Shooting_Date_Parsed column not found.")
        return

    while True:
        user_input = input(
            "\nEnter timeframe as YYYY-MM-DD to YYYY-MM-DD "
            "(or press Enter to skip): "
        ).strip()

        if user_input == "":
            break

        try:
            start_str, end_str = [x.strip() for x in user_input.split("to")]

            start = pd.to_datetime(start_str, utc=True)
            end = pd.to_datetime(end_str, utc=True) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

            mask = (
                (df["Shooting_Date_Parsed"] >= start) &
                (df["Shooting_Date_Parsed"] <= end)
            )

            filtered = df.loc[mask].copy()

            if filtered.empty:
                print("\nNo rows found in that timeframe.")
            else:
                print(f"\nFound {len(filtered)} rows:\n")
                print(filtered.to_string(index=True))

        except Exception:
            print("Invalid format. Use: YYYY-MM-DD to YYYY-MM-DD")

if __name__ == "__main__":
    boston_data_query = build_boston_data_query()
    print(boston_data_query.head())
    print(f"Saved master file to {MASTER_CSV}")
    prompt_and_print_timeframe(boston_data_query)