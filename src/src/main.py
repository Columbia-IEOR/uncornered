from clean_data import clean_data
from load_boundaries import load_boundaries
from spatial_join import spatial_join
from aggregate import aggregate_counts
from make_map import make_map

# FILE PATHS
DATA_PATH = "data/raw/Fake_Small_BostonCrews&Networks.xlsx"
BOUNDARY_PATH = "data/boundaries/boston.geojson"

def main():
    df = clean_data(DATA_PATH)
    boundaries = load_boundaries(BOUNDARY_PATH)

    joined = spatial_join(df, boundaries)

    counts = aggregate_counts(joined, "district")

    m = make_map(boundaries, counts, "district")

    m.save("outputs/maps/boston_map.html")

if __name__ == "__main__":
    main()
