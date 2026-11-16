# Space Apps 2026 submission draft — Farm Sight

Draft text for the project page. Items marked **[TEAM]** need a human answer.
Every number below comes from a live run of the app on 14–15 November 2026.

## Project name

Farm Sight

## Challenge

Field Shift: Adapting Farms with NASA Data

## Team

**[TEAM]** names and roles.

## Links

- Live app: https://sharvin-coder-nasa-space-apps-field-shift-app-265jl1.streamlit.app/
- Code: https://github.com/Sharvin-coder/nasa-space-apps-field-shift
- Demo video or slides: **[TEAM]** link (see the 30-second script at the end)

## High-level summary

A farmer drops a pin on a map. Farm Sight fills in 19 climate, water, terrain,
greenness, soil and crop-history criteria for that spot from NASA and open data, with no
typing. The farmer sets three priorities (climate fit, soil health, water
saving), and the tool ranks crop rotations against their current one, showing
the reasons for each. It also shows how each rotation's climate fit changes
under the climate projected for 2040. It is decision support: it explains its
reasoning and says plainly what it cannot tell you.

## The problem

Choosing a rotation means weighing rainfall, heat, season length, soil,
groundwater and what the climate will do next. That data exists, much of it
from NASA, but it sits in a dozen portals and formats. Most rotation tools ask
the farmer to supply those inputs. A farmer who has to look up ten years of
rainfall will not use the tool.

## What it does

1. **Pin.** Click the map or type coordinates.
2. **Auto-fill.** In about 6 seconds the app calls six data services and fills
   in the criteria: growing-season rain, growing degree days, heat days,
   frost-free days, solar radiation, aridity, rainfall variability, root-zone
   wetness, dry years, groundwater percentile, slope, projected 2040
   temperature and rainfall change, soil texture, organic carbon, pH, and the
   crops grown at that exact spot for the last five years.
3. **Current rotation.** The crops seen by satellite pre-fill "What do you
   grow now?". The farmer can correct it, and can also say the field is
   irrigated or enter a measured soil pH.
4. **Priorities.** Three sliders: climate fit, soil health, water saving.
5. **AI reading.** On request, an AI analyst reads the field's measurements
   and scores and explains in plain words what stands out, what the top shift
   changes, and what to ask an agronomist. It never changes the ranking.
6. **Ranked rotations.** The current rotation is scored as the baseline. The
   app then offers rotations that keep the current crops and add to them
   (a shift, not a restart), with the change in each score and a "Why" panel:
   which soil checks are met, and what limits each crop.

## Beyond the ranking

- **Climate time machine.** A year slider blends today's climate toward the
  2040 projection, and two what-if sliders shift temperature and rainfall.
  The ranking re-forms live and shows what moved. In central Iowa, +3 °C and
  −30% rain drops the current corn → soybean rotation from 0.66 to 0.50 and
  brings sorghum, which is not offered there today, into the top option.
- **Ten-year replay.** Each rotation is re-scored with every one of the last
  ten years' actual weather, with the driest years marked, so a farmer can
  see how it would have fitted in the years they remember.
- **Farmer constraints.** Crops the farmer cannot grow (equipment, market,
  contracts) can be ruled out, alongside corrections for irrigation, soil pH
  and the detected crops.
- **One-page farm report.** A printable download with the inputs, the key
  numbers and sources, the comparison, and questions to take to an
  agronomist, generated from that field's own results.
- **Plain-language help.** A glossary (evapotranspiration, aridity index,
  root-zone wetness, groundwater percentile, frost-free days, growing degree
  days), why legumes, sod crops, mixed plant groups and residue help the
  soil, how satellite and ground measurements differ, how datasets of
  different resolution are combined, and where local judgment is needed.

## The Farm Sight world model

The Farm Sight world model is set out in the app's "The model" tab and in
`MODEL.md`, with an architecture diagram.

- **A world model with the crop as the action.** A latent model of one field
  that steps every 16 days given the weather and the crop planted, so a
  rotation can be simulated forward under a climate that has not happened.
- **A two-clock state.** A fast state (canopy, root-zone water) and a yearly
  slow state that carries one crop's legacy into the next season.
- **Rules inside the model.** FAO EcoCrop ranges and NRCS 328 checks act as
  anchor, mask and verifier. The only learnable rule is a bounded offset on
  each crop range, so what the model learns is a revised table an agronomist
  can read and overrule.
- **A causal training signal from free labels.** USDA crop maps say what was
  planted, MODIS says how the field responded, and neighbouring fields with
  different crops act as near natural experiments. No yield records needed.
- **Risk-aware, verified planning.** Rotations are rolled through each
  climate model separately and scored on the bad tail as well as the average.

We checked this against published work on 16 November 2026 (weather-driven
satellite world models, hybrid physics and ML crop models, rotation planners
with symbolic limits, causal rotation studies) and found the ingredients
separately but not this combination. `MODEL.md` lists the seven systems
compared.

## Worked example

Central Iowa (42.10, −93.55). Satellite crop maps show corn and soybean
alternating for five years, so the app pre-fills both.

- Current rotation, corn → soybean: overall 0.66 (climate fit 0.97, soil
  health 0.50, water saving 0.50). It meets two of four soil checks.
- Top option, alfalfa → dry bean → corn → soybean: overall 0.84. It meets all
  four soil checks (three or more functional groups, a legume, a perennial
  sod crop, high-residue crops in at least half the sequence).
- Projected change by 2040 at this spot: +0.9 °C in the growing season and
  −0.2% annual rain.

Move the pin to a field in southwest Kansas (38.05, −100.95) and the picture
changes without any typing. The aridity index falls from 0.81 to 0.38.
Groundwater sits at the 2nd percentile, against a 10-year average at the
22nd. The detected crops are wheat and corn, which score 0.29 as a rotation;
the top option, alfalfa → corn → wheat → sorghum, scores 0.66.

## How it works

- **Crop fit** uses the FAO EcoCrop method. For temperature, annual rainfall
  and soil pH a crop scores 1 inside its optimal range, 0 outside its absolute
  range, and a straight line in between. The lowest factor wins. Ranges are
  taken from EcoCrop unchanged for 17 field crops.
- **Dry-year fit** repeats that for the location's three driest of the last
  ten years.
- **Soil health** is the share of four checks met, taken from USDA NRCS
  Conservation Practice Standard 328 (Conservation Crop Rotation).
- **Water saving** reflects how little rainfall the rotation's crops need.
- **2040 fit** shifts today's temperature and rainfall by the projected
  change and recomputes crop fit. It is shown, not scored.
- The final score is the farmer-weighted average of fit, soil health and
  water saving.

Built in Python with Streamlit. No API keys are needed, so anyone can run it.

## NASA data used

| Data | What we take from it |
|---|---|
| NASA POWER (MERRA-2, CERES) daily point data, 2016–2025 | Rain, temperature, growing degree days, heat days, frost-free days, solar radiation, root-zone wetness, aridity, rainfall variability, dry years |
| NASA NEX-GDDP-CMIP6, through the NASA POWER climate projection service | Change in growing-season temperature and annual rain, 2016–2025 to 2035–2044, ensemble mean, SSP2-4.5 |
| NASA GRACE / GRACE-FO data-assimilation drought indicator (rasters hosted by NDMC) | Groundwater wetness percentile: latest week and a 10-year average |
| NASA SRTM 30 m elevation (through OpenTopoData) | Slope |
| NASA MODIS MOD13Q1 vegetation indices, 250 m, every 16 days (through Microsoft Planetary Computer, with NASA's ORNL DAAC as fallback) | Peak greenness (NDVI) each year, its ten-year trend, and greenness in dry seasons against other years |

## Other data and references

- ISRIC SoilGrids v2.0 — clay, sand, organic carbon, pH (0–5 cm)
- USDA NASS Cropland Data Layer — crop type per pixel per year (contiguous US)
- FAO EcoCrop database — crop requirement ranges (copy hosted at
  github.com/OpenCLIM/ecocrop)
- USDA NRCS Conservation Practice Standard 328, Conservation Crop Rotation
- FAO Irrigation and Drainage Paper 56 — Hargreaves reference
  evapotranspiration, used for the aridity index
- OpenStreetMap — base map

## What it cannot do

We list these in the app and the README, because a farmer should know them.

- **No yield or profit forecast.** Prices, markets, equipment and local
  practice are not considered. Some picks are climatically sound but may not
  be practical.
- **Climate values are coarse.** NASA POWER is on a grid about 50 km wide, so
  neighbouring fields share climate values. Soil and crop history are local.
- **US-centred.** Crop history covers the contiguous US only, and the
  projection service returned no data for our test sites in India and Brazil.
  Climate, groundwater, slope and soil work elsewhere.
- **One growing window** (April–September) for all crops.
- **Shown but not scored:** aridity, groundwater, slope and 2040 fit. Turning
  them into weights would have meant inventing numbers.
- **Our own judgment calls,** which need an agronomist's review: each crop's
  functional group and residue class, the "three or more groups" threshold,
  and the soil texture cut-offs.
- **Greenness is one 250 m pixel.** Near a field edge it mixes two fields,
  and the crop grown changes the peak, so the trend is not soil health on its
  own.

## What we tried and dropped

We first tested whether satellite data could show that fields with winter
cover stay greener in drought. Pilots in Iowa and Nebraska found no benefit,
and a negative difference in Nebraska, so we removed that feature instead of
shipping a claim the data did not support. The code and results are in the
repository history.

## Use of AI

**[TEAM]** confirm wording against this year's Space Apps AI rules.

**[TEAM]** list every AI tool each member used. One commit in the history is
labelled as a DeepSeek iteration, so the list below may be incomplete.

Suggested text: We used AI coding assistants (Anthropic's Claude through
Claude Code; **[TEAM]** add any others) to write and test the Python code,
find data endpoints and draft documentation. Team members chose the idea and
direction and reviewed the results.

Inside the app, AI is used in one place: an optional "AI reading of this
field", written by Anthropic's Claude from the measurements and scores already
on the page. It interprets the data in plain language and is labelled as
AI-written. It does not set or change any score: every ranking comes from
published crop ranges and conservation rules applied to measured data, and can
be traced in the "Why" panel. Figures in the AI text are checked against the
data automatically and flagged if they do not match. No AI-generated images,
video or audio are used.

## What's next

- A profit view from real price and yield data.
- Sharper greenness per field from HLS (30 m), and SMAP soil moisture.
- Agronomist review of the crop labels and thresholds.
- Growing seasons for the Southern Hemisphere and the tropics.
- A printable one-page card for each field.

## 30-second demo script

1. (0–5 s) "Choosing a crop rotation takes data most farmers never see."
   Show the app with the map.
2. (5–12 s) Click a field in Iowa. "One click. NASA climate, groundwater,
   terrain, soil, and five years of crop history fill in on their own."
3. (12–20 s) Point at the baseline and Option 1. "Corn and soybean scores
   0.66. Adding alfalfa and dry bean lifts it to 0.84, and here is why."
   Open the "Why" panel.
4. (20–26 s) Click southwest Kansas. "Different field, different answer:
   far drier, groundwater near its record low, and sorghum joins the
   rotation."
5. (26–30 s) "Farm Sight. NASA data in, an explained rotation out."
