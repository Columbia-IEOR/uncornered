from datetime import datetime

def refresh_public_data_pipeline(city="Both", dry_run=True):
    return {
        "requested_city": city,
        "dry_run": dry_run,
        "timestamp": datetime.now().isoformat(),
        "steps": [
            "Fetch public data (future)",
            "Clean and standardize data (future)",
            "Rebuild maps (future)",
            "Pull network data from Neo4j later",
            "Pull internal tables from Zoho later"
        ]
    }