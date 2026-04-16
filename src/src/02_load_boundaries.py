import geopandas as gpd

def load_boundaries(filepath):
    gdf = gpd.read_file(filepath)

    # Ensure consistent coordinate system
    gdf = gdf.to_crs(epsg=4326)

    return gdf
