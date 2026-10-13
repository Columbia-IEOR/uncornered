"""
Quick check: service account can write to the Uncornered Google Sheet.

Run from repo root:
  python3 phase2_pipeline/fetch/test_sheets_connection.py
"""
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

PHASE2_ROOT = Path(__file__).resolve().parents[1]
CREDS_PATH = PHASE2_ROOT / "secrets" / "google_service_account.json"
SHEET_ID = "1J0HyZ0k8C9cvgbfXSWQfo5_BPYOvQD2aE3drWGiU2Lc"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def main():
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.sheet1
    ws.update_acell("A1", "hello from uncornered pipeline")
    print("SUCCESS")
    print(f"Spreadsheet: {sh.title}")
    print(f"Worksheet:   {ws.title}")
    print(f"A1:          {ws.acell('A1').value}")


if __name__ == "__main__":
    main()
