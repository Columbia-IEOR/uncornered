import folium

def make_map(boundaries, counts, area_col):
    merged = boundaries.merge(counts, on=area_col, how="left")
    merged["incident_count"] = merged["incident_count"].fillna(0)

    m = folium.Map(location=[42.36, -71.05], zoom_start=11)

    folium.Choropleth(
        geo_data=merged,
        data=merged,
        columns=[area_col, "incident_count"],
        key_on=f"feature.properties.{area_col}",
        fill_color="Reds",
        legend_name="Incident Count"
    ).add_to(m)

    return m
