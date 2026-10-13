# Phase 2 — Automated Data Pipeline + Boston Atlas Demo
#
# Self-contained folder for Phase 2 work. Original project files remain elsewhere;
# legacy Boston scripts are copied here for reference.

## Folder map

```text
phase2_pipeline/
├── README.md                 ← this file
├── requirements.txt
├── secrets/                  ← Google service account JSON (do not commit)
│   └── google_service_account.json
├── fetch/                    ← NEW automated fetch scripts
│   ├── fetch_boston_to_sheets.py
│   └── test_sheets_connection.py
├── app/                      ← NEW Streamlit demo
│   └── boston_atlas.py
├── data/
│   ├── cleaned/
│   │   ├── boston_shooting_incidents.csv   ← total shootings (crime CSVs)
│   │   └── boston_shooting_victims.csv     ← fatal / non-fatal (ArcGIS dashboard)
│   └── boundaries/
│       ├── boston_neighborhoods.geojson
│       ├── boston_census_tracts_2020.geojson
│       └── us_states.geojson
└── legacy_boston_scripts/    ← COPIES of existing Data Sourcing/Boston scripts
    ├── boston_data_query.py
    ├── download_boston_this_year.py
    ├── download_boston_last_year.py
    ├── download_boston_prev_years.py
    └── fetch_boston_arcgis_person_shot.py  ← previous ArcGIS-only fetch
```

## What each part does

| Path | Purpose |
|------|---------|
| `fetch/fetch_boston_to_sheets.py` | Pulls total shootings from Analyze Boston crime incident reports and Fatal / Non-Fatal victims from the Person Shot ArcGIS dashboard → two CSVs + two Google Sheet tabs |
| `fetch/test_sheets_connection.py` | Checks Google Sheets credentials work |
| `app/boston_atlas.py` | Uncornered Learning Dashboard: filters, KPIs, map, trend / where / when charts, shootings table (Boston; KC / Providence placeholders) |
| `data/cleaned/` | Boston datasets used by Streamlit |
| `data/boundaries/` | Neighborhood polygons for the choropleth |
| `legacy_boston_scripts/` | Copies of earlier team scrapers (reference only; not used by the new fetch) |
| `secrets/` | Private Google Cloud key |

## How to run

From the **repo root** (`uncornered/`):

```bash
# Optional: test Sheets connection
python3 phase2_pipeline/fetch/test_sheets_connection.py

# Refresh Boston open data → CSV + Google Sheet
python3 phase2_pipeline/fetch/fetch_boston_to_sheets.py

# Launch map demo
python3 -m streamlit run phase2_pipeline/app/boston_atlas.py
```

Then open http://localhost:8501

## Monthly automatic refresh (this Mac)

`launchd` runs `schedule/run_boston_refresh.sh` on the **1st of every month at 9:00 AM**
(if the Mac is asleep then, it runs on wake; if it is shut down, that month is skipped
until the next run or a manual run).

```bash
# Check the last run
tail -n 20 phase2_pipeline/logs/boston_refresh.log

# Run it now (same as the monthly job)
launchctl kickstart gui/$(id -u)/com.uncornered.boston-refresh

# Install / reinstall after editing the plist
cp phase2_pipeline/schedule/com.uncornered.boston-refresh.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.uncornered.boston-refresh 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.uncornered.boston-refresh.plist

# Stop the schedule
launchctl bootout gui/$(id -u)/com.uncornered.boston-refresh
rm ~/Library/LaunchAgents/com.uncornered.boston-refresh.plist
```

On the Hostinger VPS, the same script runs from cron instead:
`0 9 1 * * /bin/bash /path/to/phase2_pipeline/schedule/run_boston_refresh.sh`

## Flow

```text
Analyze Boston — Crime Incident Reports          Boston Person Shot ArcGIS dashboard
(Aug 2015 – to date, one CSV per year)           (one row per victim)
  filter: SHOOTING = 1 (or 'Y' pre-2019)           Fatal / Non-Fatal, demographics,
  AND OFFENSE_DESCRIPTION =                        location
    'ASSAULT - AGGRAVATED' or murder
  sort: OCCURRED_ON_DATE
        ↓                                                ↓
             fetch_boston_to_sheets.py  (joined by incident number: each
                                         shooting gets Fatal / Non-Fatal from the
                                         dashboard, else murder = Fatal)
        ↓                                                ↓
boston_shooting_incidents.csv                    boston_shooting_victims.csv
Sheet tab "Boston"  (shootings, Fatal/Non-Fatal) Sheet tab "Boston_Fatal_NonFatal"
        ↓
app/boston_atlas.py (Streamlit) — reads the incidents file:
  KPIs vs previous period, choropleth (tracts / neighborhoods), trend,
  top areas, day × time heatmap, recent shootings table + CSV download
```

Sources:
- https://data.boston.gov/dataset/crime-incident-reports-august-2015-to-date-source-new-system
- https://www.arcgis.com/apps/dashboards/dbd16dfec5b54734bd7d927b26b38a24

## Notes

- Original scripts still exist under `Data Sourcing/Boston/` in the main repo.
- `legacy_boston_scripts/` are **copies** kept here so Phase 2 stays organized and self-contained.
- Never commit `secrets/` or push the service account JSON to GitHub.
