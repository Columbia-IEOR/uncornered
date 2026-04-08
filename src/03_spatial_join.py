import geopandas as gpd

def spatial_join(df, boundaries):
    gdf_points = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326"
    )

    joined = gpd.sjoin(gdf_points, boundaries, how="left", predicate="within")

    return joined
