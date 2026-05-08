# Geospatial Analysis to Support Community Safety Initiatives

**README, as of May 8th 2026**

## Project Overview

This is a web-based analytics project for helping Uncornered track and visualize gun violence patterns across cities such as Boston and Kansas City. The project is designed to reduce manual data processing, improve geographic visibility, and lay the foundation for connecting external violence data with internal community network insights.

The project builds a data pipeline and dashboard framework for analyzing public shooting and crime incident data. The pipeline collects data from public city data portals, processes the data into geospatial heatmaps, and supports the overlay of crew and catalyst network data to help identify areas for targeted community outreach.

The workflow in this repository has four main stages:

1. **Data Collection** - Public shooting and crime incident data is collected from city data portals using API endpoint calls.
2. **Data Storage** - The downloaded data is saved as local CSV files for reproducibility and fallback use.
3. **Data Processing and Mapping** - Jupyter notebooks clean and standardize the data, join incidents with geographic boundaries, and generate interactive heatmaps using GeoPandas and Folium.
4. **Dashboard Display** - The generated HTML maps can be used as standalone interactive maps or incorporated into a dashboard/prototype interface.

## Features

- **View Violence Heatmaps** - Explore incident density across city maps to identify high-risk areas.
- **Compare Cities** - View geographic patterns across multiple cities, including Boston and Kansas City.
- **Boundary-Based Insights** - Aggregate incidents by district, census tract, or neighborhood for easier interpretation.
- **Foundation for Network Integration** - Prepare the system for future layering of catalyst and crew/network data.
- **Automated Data Pipeline** - Reduce manual downloading, cleaning, and visualization work.

## Project Workflow

The general workflow for both cities is:

```text
Public incident data/API
        ↓
Clean and standardize data
        ↓
Load geographic boundaries
        ↓
Join incidents to map regions
        ↓
Overlay crew/catalyst network data
        ↓
Export interactive HTML map
```

The Boston and Kansas City notebooks follow the same overall structure, but use different public data sources, geographic boundaries, and local network files.

## Repository Structure

The final project is organized around the main notebooks, supporting datasets, and generated map outputs.

```text
.
├── boston_crew_dashboard.ipynb
├── KC_heatmaps_3.ipynb
├── KCPD_Data.csv
├── kc_crew_network_map.html
├── data/
├── outputs/maps/
├── figures/
├── requirements.txt
└── README.md
```

Key file descriptions:

- `boston_crew_dashboard.ipynb` - Generates the Boston shooting and catalyst network map.
- `KC_heatmaps_3.ipynb` - Generates the Kansas City incident and catalyst network map.
- `KCPD_Data.csv` - Kansas City crew/catalyst network data.
- `kc_crew_network_map.html` - Exported Kansas City interactive map.
- `requirements.txt` - Python package dependencies.

## Main Project Files

### `boston_crew_dashboard.ipynb`

This notebook generates the Boston geospatial dashboard. It loads public shooting incident data, joins it with geographic boundary information, overlays crew and catalyst network data, and exports an interactive Folium map.

The Boston notebook includes:

- Boston shooting incident data loading from the Analyze Boston API.
- Local CSV fallback support for reproducibility.
- Census tract and geographic boundary processing.
- Police district-level incident mapping.
- Crew and catalyst marker layers.
- Affiliation, conflict, and catalyst network connection layers.
- A client-side date filter for viewing incidents over time.
- Interactive Folium map export.

The notebook exports the final Boston map as:

```text
boston_crew_network_dashboard.html
```

One important note is that Boston shooting incidents are mapped approximately by police district rather than exact incident coordinates. Representative district coordinates are used, with small random offsets added so incident points can be displayed visually on the map.

### `KC_heatmaps_3.ipynb`

This notebook generates the Kansas City geospatial dashboard. It pulls public KCPD incident data, cleans and filters the records, maps incidents by geographic location, overlays crew and catalyst network data, and exports an interactive Folium map.

The Kansas City notebook includes:

- KCPD public crime incident data loading from the Kansas City open data API.
- Local CSV fallback support if the API is unavailable.
- Incident cleaning and filtering.
- Latitude and longitude extraction from incident location fields.
- Homicide and firearm-related incident classification.
- Census tract-level choropleth mapping.
- Crew and catalyst marker layers.
- Affiliation, conflict, and catalyst network connection layers.
- A client-side date filter and year-to-date view.
- Interactive Folium map export.

The notebook exports the final Kansas City map as:

```text
kc_crew_network_map.html
```

### `KCPD_Data.csv`

This file contains the Kansas City crew and catalyst network data used by `KC_heatmaps_3.ipynb`.

The file supports map layers such as:

- Crew locations.
- Catalyst locations.
- Catalyst types.
- Catalyst assignments/statuses.
- Crew affiliations.
- Crew conflicts.
- Catalyst-to-catalyst network links.

## Data Sources

The project uses a combination of public incident data and internal or demo catalyst network data.

### Boston

Boston shooting incident data is collected from the Analyze Boston API. The notebook uses the stable CKAN API endpoint for the public shootings dataset and saves a local copy for future reproducibility.

Supporting Boston data includes:

- Public Boston shooting incident data.
- Boston census tract boundary/reference data.
- Boston crew and catalyst network data.

### Kansas City

Kansas City incident data is collected from the KCPD open data API. If the API is unavailable, the notebook can fall back to a locally saved CSV file.

Supporting Kansas City data includes:

- Public KCPD crime incident data.
- Census tract boundaries for the Kansas City area.
- Kansas City crew and catalyst network data from `KCPD_Data.csv`.

## Map Features

The generated maps include several interactive layers:

- Choropleth heatmaps showing incident concentration by geographic area.
- Individual shooting or crime incident markers.
- Crew location markers.
- Catalyst location markers.
- Crew affiliation lines.
- Crew conflict lines.
- Catalyst network connection lines.
- Layer toggles for turning map features on and off.
- Date filters for adjusting the visible incident window.

The maps are generated with Folium and exported as standalone HTML files.

## How to Run the Project

### 1. Clone the repository

```bash
git clone https://github.com/Columbia-IEOR/uncornered.git
cd uncornered
```

### 2. Install dependencies

Install the required Python packages using:

```bash
pip install -r requirements.txt
```

If installing manually, the main packages used include:

```bash
pip install pandas folium requests geopandas shapely openpyxl branca
```

### 3. Run the Boston notebook

Open and run:

```text
boston_crew_dashboard.ipynb
```

This notebook loads Boston shooting data, processes the map layers, and exports:

```text
boston_crew_network_dashboard.html
```

### 4. Run the Kansas City notebook

Open and run:

```text
KC_heatmaps_3.ipynb
```

This notebook loads KCPD incident data, processes the map layers, and exports:

```text
kc_crew_network_map.html
```

### 5. Launch the dashboard application if applicable

If the Streamlit dashboard version is included in the working repository, launch the app with:

```bash
streamlit run app.py
```

### 6. View the generated maps

Open the exported `.html` files in a web browser to view the interactive maps.

## Updating the Maps

To refresh the dashboards with new incident data, rerun the corresponding notebook.

### Boston refresh process

1. Open `boston_crew_dashboard.ipynb`.
2. Set the notebook to pull the latest public incident data rather than only using a local cached file.
3. Run all cells.
4. The notebook saves an updated local data copy and exports a refreshed HTML map.

### Kansas City refresh process

1. Open `KC_heatmaps_3.ipynb`.
2. Run all cells.
3. The notebook attempts to pull the latest KCPD data from the public API.
4. If the API is unavailable, it falls back to the local CSV file.
5. The notebook exports a refreshed HTML map.

## Outputs

The primary outputs are interactive HTML maps.

```text
boston_crew_network_dashboard.html
kc_crew_network_map.html
```

These files can be opened directly in a browser or embedded into a larger dashboard/prototype interface.

## Notes and Limitations

- Boston incident points are approximate and are mapped using representative police district coordinates rather than exact shooting locations.
- Kansas City incidents are mapped using available latitude/longitude information from the public KCPD dataset.
- Catalyst and crew network data may include demo or manually maintained information and should be reviewed before public use.
- Local CSV files are used as fallbacks to make the notebooks reproducible even if an API request fails.
- The generated maps are static HTML exports, but they include client-side interactivity such as layer toggles and date filtering.

## Future Improvements and Features

- Zoho integration for internal staff access.
- ArcGIS automation for updated map layers.
- Real-time catalyst and network data integration.
- Automated weekly data refresh pipeline.
- Standardize input data paths across both notebooks.
- User-friendly dashboard for non-technical staff and Core Influencers.
- Move all generated map outputs into a dedicated `outputs/maps/` folder.
- Standardize input data paths across both notebooks.
- Add clearer separation between raw data, processed data, and generated outputs.
- Add a visual pipeline diagram to show the full data-to-dashboard workflow.

## Additional Developer Notes

Scripts inside the `DataSourcing/Boston` folder provide additional fallback options for collecting reliable, live public data reported by the Boston Police Department to utilize in this project. These scripts are currently not associated with the current API endpoint used within `boston_crew_dashboard.ipynb`. Developers may elect to integrate these alternative processes if the existing endpoint or current collection methods are no longer feasible in the future.

For formatting purposes, the homicide/aggravated assault column in Kansas City has been adjusted to match Fatal/Non-Fatal entries as in Boston, per the client's request.

## Created By

Uncornered Student Team - Columbia University

- Tarit Hongsyok
- Afsana Rahman
- Eleanor Koo
- Robert Sun

---
