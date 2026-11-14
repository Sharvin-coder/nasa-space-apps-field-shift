# Twin Fields

**NASA Space Apps Challenge 2026 — [Field Shift: Adapting Farms with NASA Data](https://www.spaceappschallenge.org/2026/challenges/field-shift-adapting-farms-with-nasa-data/)**

> Every recommendation is backed by a real field, not a formula.
> We find your field's twins: one nearby, and one from your future.

## The idea in four steps

1. **Fingerprint.** The farmer enters a location. We auto-fill ~20 criteria
   (climate, water, soil, field history) from NASA and open soil data. The
   farmer only sets their priorities.
2. **Near twin.** Find nearby fields with a matching fingerprint that already
   rotate differently (for example, with cover crops). The satellite record
   shows how they held up in dry years compared with fields that did not change.
3. **Future twin.** Find the region whose climate today matches this farm's
   projected 2040 climate, and show what rotations are grown there.
4. **Recommendation.** Rank the rotations the twins actually use, weighted by
   the farmer's priorities, and show the top criteria behind each one.

## Ground rules

- **Real data only.** No invented yields, prices or scores. If a value can't be
  fetched, show it as missing.
- **One pilot region, end to end.** Proposed: central Iowa (Story County area),
  because US crop-history data is strongest there and 2020, 2021 and 2023 show
  up as dry seasons in the NASA POWER record. Team to confirm.
- **Say what it can't do.** Twins show correlation, not proof. This goes in the pitch.

## The fingerprint criteria

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
| 12 | Field productivity trend | NASA HLS greenness | to do |
| 13 | Greenness drop in dry years | NASA HLS greenness | to do |
| 14 | Projected 2040 temperature change | NASA NEX-GDDP-CMIP6 | to do |
| 15 | Projected 2040 rainfall change | NASA NEX-GDDP-CMIP6 | to do |
| 16 | Soil texture (clay, sand) | ISRIC SoilGrids | done |
| 17 | Soil organic carbon | ISRIC SoilGrids | done |
| 18 | Soil pH | ISRIC SoilGrids | done |
| 19 | Current crop sequence | USDA Cropland Data Layer | to do |
| 20 | Farmer priorities (profit / soil / water) | Farmer input | to do (UI) |

## Run what exists

```bash
uv venv --python 3.11
uv pip install --link-mode=copy -r requirements.txt
.venv/Scripts/python -m twinfields.fingerprint 42.03 -93.47
```

(On macOS/Linux use `.venv/bin/python`.) This prints the fingerprint as JSON
from live NASA POWER and SoilGrids calls. Assumptions baked in so far: an
April–September growing season and a 2015–2024 window; both are constants at
the top of `twinfields/fingerprint.py`.

## Near-twin pipeline (first pilot run)

```bash
.venv/Scripts/python -m twinfields.fetch_pilot   # ~3 min, downloads to data/cache/
.venv/Scripts/python -m twinfields.neartwin      # ~1 s, writes results/neartwin_pilot.json
```

- **Data:** 467 NASA MODIS 250 m greenness composites (2014–2024) and 11 years
  of USDA crop maps for a 20 km box east of Ames, Iowa. No login needed.
- **Method:** keep pixels that are ≥95% corn or soy two years running; flag a
  pixel-year as "winter-green" (a cover-crop proxy) when its spring NDVI is
  0.10 above that year's median; compare summer EVI against the same pixel's
  unflagged years (difference-in-differences, ~1 km block bootstrap). Details
  are in the docstring of `twinfields/neartwin.py`.
- **Result: no drought benefit found in this pilot.** Winter-green pixel-years
  (572 of them) show about +0.01 EVI in non-dry years (mean July–August EVI
  +0.016, 95% CI 0.004 to 0.027) and no difference in the three dry years
  (−0.003, CI −0.018 to 0.008). Year-by-year signs are mixed.
- **Why this pilot is weak evidence either way:**
  - The low-rainfall seasons here (2020, 2021, 2023) were not low-greenness
    seasons; 2018 was the lowest. Rainfall alone is a poor stress marker on
    these soils.
  - The winter-green flag is unvalidated and fires on only 1–7% of pixels a year.
  - 250 m pixels blur field edges. HLS (30 m) is the planned upgrade.
- **Open decision:** move the pilot to a rain-fed region with a clear stress
  year, chosen before looking at its results, or keep Iowa and present the
  honest null.

## Milestones

1. **Near twin works for the pilot county** — this alone is a complete demo.
2. Future twin (climate analog).
3. Web UI with the map and the farmer card.
4. Pitch video and submission.

Cut order if time runs short: text-message delivery mock-up, then criteria
10–11, then the future twin.

## Task split (three roles — claim one)

**Role A — Field data pipeline**
- Pull HLS greenness time series for fields in the pilot county (needs a free
  NASA Earthdata login).
- Pull USDA Cropland Data Layer crop sequences per field.
- Flag fields that are green in winter (likely cover crops), with a confidence level.
- Output: one table, one row per field per year.

**Role B — Matching and recommendation**
- Finish the fingerprint (criteria 6, 10, 11, 14, 15).
- Near-twin matching: same soil and crop, different practice; compare
  greenness in dry vs. normal years.
- Future-twin search: projected 2040 fingerprint vs. current fingerprints elsewhere.
- Rank rotations by farmer priorities and list the criteria behind each.

**Role C — App and pitch**
- Web app: location entry, auto-filled criteria the farmer can override,
  twin map, recommendation card.
- Printable one-page farmer card.
- 30-second story for the pitch: one named farm and its two twins.
- Submission write-up, including data sources and limits.

## Repo layout

```
twinfields/
  fingerprint.py   auto-fill criteria for a lat/lon
  fetch_pilot.py   download MODIS greenness + crop history for the pilot box
  neartwin.py      winter-green flag and dry-year comparison
results/           one JSON per analysis run (config, numbers, git commit)
data/cache/        local downloads (not committed)
```

## Data sources

- [NASA POWER](https://power.larc.nasa.gov/) — daily weather and solar
- [NASA HLS](https://www.earthdata.nasa.gov/data/projects/hls) — Landsat + Sentinel-2 surface reflectance
- [NASA SMAP](https://smap.jpl.nasa.gov/) — soil moisture
- [NASA GRACE-FO](https://gracefo.jpl.nasa.gov/) — groundwater change
- [NASA NEX-GDDP-CMIP6](https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6) — downscaled climate projections
- [ISRIC SoilGrids](https://soilgrids.org/) — soil properties
- [USDA Cropland Data Layer](https://www.nass.usda.gov/Research_and_Science/Cropland/SARS1a.php) — yearly crop type per field (US only)
