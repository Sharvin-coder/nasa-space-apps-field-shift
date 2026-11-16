# Farm Sight: the model

What produces the numbers today, and the learning model we designed to build on it.
This file is generated from `fieldshift/model_design.py`, which also feeds the app's
"The model" tab.

## What runs today: explicit rules

Farm Sight's rankings are produced by explicit rules, not by a trained model. That is a choice: a farmer can trace every score to a published range or check.

- **Suitability curves.** Each crop has a published range for temperature, rainfall and soil pH (FAO EcoCrop). A value inside the optimal range scores 1, outside the absolute range scores 0, with a straight line between. This is the same shape fuzzy logic uses for membership.
- **Lowest factor wins.** A crop's fit is its worst factor, not the average, because one limit (too dry, too cold) cannot be made up by the others.
- **Rule checks.** Soil health is four yes-or-no checks from USDA NRCS Standard 328, counted.
- **Exhaustive search.** Every rotation of two to four crops that keeps what the farmer grows is scored; there is no sampling and no learned shortcut.
- **Simple statistics.** Ten-year averages, year-to-year variability, a straight-line trend through yearly greenness, and a what-if that shifts the climate and re-scores.
- **Language model, optional.** An AI analyst (Claude) can write a plain-language reading of the page. It sees only the numbers already shown, and its figures are checked against them. It sets no score.

Several inputs are themselves model products made by their publishers: SoilGrids soil maps and the USDA crop maps come from machine-learning models, groundwater from satellite gravity blended into a land model, and the 2040 change from an average of physical climate models. Farm Sight reads these; it does not retrain them.

Rules are transparent but blunt. The crop ranges are global, so they miss local behaviour (grain sorghum is ruled out as too wet in Iowa). They score a climate average, not how a field responds through a season. And they cannot learn from the ten years of satellite history the app already fetches for every pin.

## What we would build next: a neurosymbolic world model for crop rotation

> **Status.** Design only. Nothing in this section is trained or running, and no result is claimed for it. Every ranking in the app today comes from the rule layer described first.

A world model is a model that learns how a system changes over time, so that you can run it forward and ask what would happen under a choice you have not made yet. Here the system is one field, the choice is what to plant, and the future is a climate that has not happened. Neurosymbolic means the learned part (neural) is tied to explicit agronomic rules (symbolic), so the model cannot drift away from what is known.

```
satellite + weather history --> [1 field encoder] --> field state
                                                         |
   crop planted, weather --> [2 world model] <-----------+   (neural: learns change over time)
                                   |  ^
                 correction only   v  |  mask, starting point, checker
                            [3 rule layer]                    (symbolic: published rules)
                                   |
   climate runs, priorities --> [4 planner] --> ranked rotations + spread
                                   |
                            [5 explainer] --> rules fired, correction applied, evidence
```

### 1. Field encoder (neural)

Turns one field's history into a compact state. The inputs arrive at different sharpness and tempo, so they are first put on one grid: one row per field per 16 days. Weather is averaged over each 16 days, greenness is used as observed, groundwater is interpolated, soil and slope are repeated.

**Uses:** MODIS greenness, NASA POWER weather, GRACE groundwater, SoilGrids, SRTM. Later: SMAP soil moisture, ECOSTRESS surface temperature, GPM rain.

### 2. World model (neural)

Learns how the field state moves from one 16-day step to the next, given the weather and the crop in the ground. It is trained to predict the next satellite readings, so it needs no yield records. Once trained it can roll a field forward under a rotation and a climate that has not happened.

**Uses:** The crop planted each year comes free from the USDA crop maps; how the field responded comes free from MODIS.

### 3. Rule layer (symbolic)

The rules the app runs today, used three ways. As a mask: a crop outside its absolute range is never proposed. As a starting point: the network predicts only a correction to the rule-based fit, not the fit itself. As a checker: every output is tested against the water balance, the season length and the four conservation checks.

**Uses:** FAO EcoCrop ranges, NRCS Standard 328, rain minus evapotranspiration, frost-free days.

### 4. Planner (search)

Lists the candidate rotations, as the app does now, and rolls each one forward many times: through each climate model separately instead of their average, and through replayed past years. The spread across those runs is the stated uncertainty.

**Uses:** NEX-GDDP-CMIP6 ensemble members, the ten-year replay, the farmer's priorities and constraints.

### 5. Explainer (symbolic + language)

Every recommendation carries the rules that fired, the correction the network applied and how large it was, and the past field-years it most resembles. The language model narrates from that record and nothing else.

**Uses:** The trace from steps 3 and 4.

## What sets the design apart

- **The rules are inside the model, not a filter after it.** The same published rules act as mask, starting point and checker. The network is only allowed to learn where the rules are wrong.
- **What it learns is readable.** The learned part is a correction to a crop range for a region (for example, sorghum tolerating more rain in Iowa than the global table says). A person can read that, question it and overrule it, which is not true of hidden weights.
- **The labels are free.** Yield records are scarce and private. What was planted and how green it grew are public for every field in the contiguous US, every year, and the app already fetches both.

We have not surveyed the research literature, so we do not claim this design is new to the field. It is new to this project, and it follows directly from data the app already holds.

## How we would train and test it

1. **Build the training set.** Sample fields across the Corn Belt and the Plains. For each, ten years of crop planted, 16-day greenness and weather: the same calls the app makes for one pin.
2. **Set honest baselines.** Predict next season's greenness three ways: repeat last year, use today's rule engine alone, and use a network with no rules. The design has to beat all three.
3. **Hold out whole years and whole regions.** Test on drought years and on states the model never saw, because that is the situation a farmer is actually in.
4. **Check against something that is not satellite greenness.** Compare with published county yields (USDA NASS) as an outside check, and have an agronomist review the learned range corrections before any reach a farmer.

## Where it could go wrong

- Greenness is not yield and not profit. A model that predicts greenness well may still rank rotations badly for income.
- A 250 m pixel can straddle two fields, and the crop maps contain errors, so some training labels will be wrong.
- A learned correction could reflect irrigation or management instead of climate, and then would not transfer to a neighbouring farm.
- The past ten years may not span the 2040 climate, which is where rules, not learned patterns, have to carry the weight.
