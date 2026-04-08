import pandas as pd

def clean_data(filepath):
    df = pd.read_excel(filepath)

    # Example assumptions — adjust to your dataset columns
    df = df.dropna(subset=["latitude", "longitude"])

    # Filter to recent (if date exists)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df[df["date"] >= pd.Timestamp.now() - pd.Timedelta(days=7)]

    # Standardize column names
    df.columns = df.columns.str.lower()

    return df
