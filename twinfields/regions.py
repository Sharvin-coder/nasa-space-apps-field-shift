"""Pilot regions. Add a region here BEFORE looking at its greenness results.

dry_years comes from the rainfall rule in twinfields.fingerprint (April-
September rain below 80% of the 2015-2024 mean, NASA POWER) at the box centre.
"""

REGIONS = {
    # ~20 km box east of Ames, Story County, Iowa
    "iowa_story": {
        "bbox": (-93.59, 41.94, -93.35, 42.12),   # lon_min, lat_min, lon_max, lat_max
        "dry_years": [2020, 2021, 2023],
    },
    # ~20 km box around Beatrice, Gage County, southeast Nebraska.
    # Chosen 2026-11-14 after the Iowa null, as a mostly rain-fed corn/soy
    # area; region and dry years were committed before fetching its data.
    "nebraska_gage": {
        "bbox": (-96.82, 40.18, -96.58, 40.36),
        "dry_years": [2021, 2023, 2024],
    },
}
