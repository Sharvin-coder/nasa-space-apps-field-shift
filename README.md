# Field Shift

**NASA Space Apps Challenge 2026 — [Field Shift: Adapting Farms with NASA Data](https://www.spaceappschallenge.org/2026/challenges/field-shift-adapting-farms-with-nasa-data/)**

> Enter your farm's location. We fill in ~20 criteria from NASA data and
> recommend crop rotations, showing the reasons behind each one.

## How it works

1. **Location in.** The farmer enters a location (or drops a pin).
2. **Auto-fill.** We pull ~20 criteria on climate, water, soil and field
   history from NASA and open soil data. The farmer types none of it.
3. **Priorities.** The farmer sets what matters most: profit, soil health,
   water saving. Any auto-filled value can be overridden.
4. **Recommendation.** We rank rotations and list the top criteria behind
   each one, so the farmer can see why.

## Ground rules

- **Real data only.** No invented yields, prices or scores. If a value can't
  be fetched, show it as missing.
- **No invented weights.** Crop suitability comes from published crop
  requirement ranges and extension guidance, with the source cited.
- **Explain every recommendation.** Each one lists the criteria that drove it.
- **Say what it can't do.** It is decision support, not a yield forecast.

## The criteria

| # | Criterion | Source | Status |
|---|---|---|---|
| 1 | Growing-season rainfall | NASA POWER | done |
| 2 | Growing degree days | NASA POWER | done |
| 3 | Heat days (max > 32 °C) | NASA POWER | done |
| 4 | Frost-free days | NASA POWER | done |
| 5 | Solar radiation | NASA POWER | done |
| 6 | Aridity (rain vs. evaporative demand) | NASA POWER | to do |
| 7 | Year-to-year rainfall variability | NASA POWER | done |
| 8 | Root-zone soil wetness | NASA POWER (MERRA-2); upgrade to SMAP | done (interim source) |
| 9 | Dry years in the last 10 | NASA POWER | done |
| 10 | Groundwater trend | NASA GRACE-FO | to do |
| 11 | Slope / erosion risk | NASADEM | to do |
| 12 | Field greenness trend | NASA MODIS / HLS | to do |
| 13 | Greenness drop in dry years | NASA MODIS / HLS | to do |
| 14 | Projected 2040 temperature change | NASA NEX-GDDP-CMIP6 | to do |
| 15 | Projected 2040 rainfall change | NASA NEX-GDDP-CMIP6 | to do |
| 16 | Soil texture (clay, sand) | ISRIC SoilGrids | done |
| 17 | Soil organic carbon | ISRIC SoilGrids | done |
| 18 | Soil pH | ISRIC SoilGrids | done |
| 19 | Current crop sequence | USDA Cropland Data Layer (US only) | to do |
| 20 | Farmer priorities (profit / soil / water) | Farmer input | to do (UI) |

## Run what exists

```bash
uv venv --python 3.11
uv pip install --link-mode=copy -r requirements.txt
.venv/Scripts/python -m fieldshift.fingerprint 42.03 -93.47
```

(On macOS/Linux use `.venv/bin/python`.) This prints the auto-filled criteria
as JSON from live NASA POWER and SoilGrids calls. Assumptions so far: an
April–September growing season and a 2015–2024 window, both constants at the
top of `fieldshift/fingerprint.py`.

## Milestones

1. **Location → criteria → ranked rotations with reasons, in the terminal.**
   This alone is a complete demo.
2. Web app: map pin, criteria panel with overrides, priority sliders,
   recommendation cards.
3. Remaining criteria (10–15, 19) and the 2040 view.
4. Pitch video and submission.

## Task split (three roles — claim one)

**Role A — Data**
- Finish the remaining criteria: aridity (6), groundwater (10), slope (11),
  greenness trend (12–13), climate projections (14–15), crop sequence (19).
- Make each criterion fail safely: missing stays missing.

**Role B — Recommendation engine**
- Crop table: each candidate crop's published tolerance ranges (temperature,
  rainfall, pH, soil texture, season length), with sources. FAO's EcoCrop
  database is the first place to check.
- Score each crop against the criteria; build rotations from rules that
  extension guidance supports (for example, a legume after a cereal).
- Weight by the farmer's priorities; output the top criteria behind each pick.

**Role C — App and pitch**
- Web app (see milestone 2) and a printable one-page farmer card.
- Pitch: one real location, start to finish, in 30 seconds.
- Submission write-up, including data sources and limits.

## Earlier experiment (removed)

We first tried backing recommendations with satellite comparisons of
neighbouring fields. Pilots in Iowa and Nebraska found no dry-year benefit
for winter-green (cover-crop proxy) fields, and a negative difference in
Nebraska, so we dropped that approach. The code and results are in git
history at commit `b7848e8`. One lesson carried forward: do not promise that
cover crops improve drought resilience everywhere.

## Data sources

- [NASA POWER](https://power.larc.nasa.gov/) — daily weather and solar
- [NASA MODIS](https://modis.gsfc.nasa.gov/) / [HLS](https://www.earthdata.nasa.gov/data/projects/hls) — vegetation greenness
- [NASA SMAP](https://smap.jpl.nasa.gov/) — soil moisture
- [NASA GRACE-FO](https://gracefo.jpl.nasa.gov/) — groundwater change
- [NASA NEX-GDDP-CMIP6](https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6) — downscaled climate projections
- [ISRIC SoilGrids](https://soilgrids.org/) — soil properties
- [USDA Cropland Data Layer](https://www.nass.usda.gov/Research_and_Science/Cropland/SARS1a.php) — yearly crop type per field (US only)
