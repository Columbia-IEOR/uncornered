def aggregate_counts(joined, area_col):
    counts = (
        joined.groupby(area_col)
        .size()
        .reset_index(name="incident_count")
    )

    return counts
