"""Plain-language explanations shown in the app and the farm report.

Every definition is worded to match what the code actually computes
(fieldshift/fingerprint.py, fieldshift/recommend.py). The crop-benefit lines
paraphrase USDA NRCS Conservation Practice Standard 328, Conservation Crop
Rotation (Indiana, October 2015).
"""

# (term, definition)
GLOSSARY = [
    ("Reference evapotranspiration",
     "The water a well-watered grass surface would lose to the air, through evaporation "
     "from the soil and transpiration from the leaves. We estimate it for each day with the "
     "Hargreaves formula (FAO Irrigation and Drainage Paper 56) from the daily high and low "
     "temperature and the sunlight arriving at the top of the atmosphere, then add it up "
     "for the year."),
    ("Aridity index",
     "A simple water balance: annual rainfall divided by annual reference "
     "evapotranspiration, averaged over 2015 to 2024. Below 1, the air could take up more "
     "water than the rain supplies. The lower the number, the drier the climate."),
    ("Root-zone soil wetness",
     "How full of water the soil is in the layer roots reach, about the top metre, from 0 "
     "(completely dry) to 1 (saturated). It is an estimate from a NASA weather model "
     "(MERRA-2), averaged over the growing seasons of 2015 to 2024 for a grid cell about "
     "50 km wide. It is not a reading from a probe in your field."),
    ("Groundwater wetness percentile",
     "How wet the shallow groundwater is this week compared with the same week over past "
     "decades. 50 is typical; 5 means it has been this dry or drier only about 5% of the "
     "time. It comes from the GRACE and GRACE-FO satellites, which weigh water from orbit, "
     "combined with a land model, on a grid about 25 km wide. It describes water below "
     "the root zone and changes more slowly than soil wetness, so the two can disagree."),
    ("Frost-free days",
     "The longest unbroken run of days in a year when the daily low stayed above 0 °C, "
     "averaged over 2015 to 2024. A warm-season crop is only offered if this run covers "
     "its shortest growing cycle."),
    ("Growing degree days",
     "The heat a crop can use, added up from April to September. Each day counts the "
     "average of the daily high (capped at 30 °C) and the daily low (raised to at least "
     "10 °C), minus 10 °C."),
    ("Heat days",
     "Days from April to September when the daily high passed 32 °C, averaged per season."),
    ("Dry season and rainfall variability",
     "A dry season is one whose April to September rain fell below 80% of the ten-year "
     "average. Rainfall variability (CV) is how much season rain swings from year to "
     "year: the standard deviation divided by the average, so 0.27 means swings of "
     "roughly 27%."),
    ("Crop fit",
     "A score from 0 to 1 for how well a crop's published temperature, rainfall and soil "
     "pH ranges (FAO EcoCrop) match this location. It is 1 inside the crop's optimal "
     "range, 0 outside its absolute range, and a straight line in between. It is not a "
     "yield estimate."),
    ("Greenness (NDVI)",
     "The Normalized Difference Vegetation Index: a satellite measure, from about 0 for "
     "bare soil to about 0.9 for a dense green canopy, of how much healthy leaf covers the "
     "ground. We read NASA's MODIS satellite for the 250 m pixel under the pin and take "
     "each year's peak between late April and mid September, skipping cloudy or snowy "
     "readings. A lower peak in a dry season is a sign the crop was stressed. The crop "
     "grown also changes the peak, so compare like with like."),
]

# (crop trait, what the standard says, whether Field Shift scores it)
CROP_BENEFITS = [
    ("Legumes",
     "Legumes such as soybean, peas, alfalfa and clover take nitrogen from the air. The "
     "standard credits the nutrients legumes provide and advises choosing crops that can "
     "supply more biologically fixed nitrogen.",
     "Scored: one of the four soil-health checks."),
    ("Perennial sod crops",
     "The standard advises including perennial sod crops with deep or extensive fibrous "
     "roots, such as alfalfa and red clover, to build organic matter throughout the soil "
     "profile.",
     "Scored: one of the four soil-health checks."),
    ("A mix of plant groups",
     "Rotating crops from different functional groups (warm- and cool-season grasses and "
     "broadleaves) suppresses the life cycles of weeds, insects and diseases.",
     "Scored: three or more groups meets the check. The threshold of three is our own."),
    ("High-residue crops",
     "High-residue crops such as corn and small grains add more to soil organic matter, "
     "and their residue helps protect the soil from erosion. The standard suggests they "
     "make up at least half of the sequence.",
     "Scored: one of the four soil-health checks."),
    ("Deep-rooted crops",
     "Deep-rooted crops can reduce compaction, and rotating them with shallow-rooted "
     "crops uses water through the whole soil profile.",
     "Not scored: rooting depth is not in our crop table."),
    ("Crops that need less water",
     "Crops with lower rainfall requirements (FAO EcoCrop) leave the rotation less "
     "exposed in dry years.",
     "Scored: the water-saving score, and the dry-year fit."),
]

# (dataset, what we take, size of one grid cell, how often it updates)
RESOLUTIONS = [
    ("NASA POWER weather", "rain, temperature, sunlight, root-zone wetness",
     "about 50 km", "daily, 2015 to 2024"),
    ("NASA NEX-GDDP-CMIP6", "projected temperature and rain change", "about 25 km",
     "daily, model ensemble"),
    ("NASA GRACE / GRACE-FO", "groundwater wetness percentile", "about 25 km", "weekly"),
    ("NASA MODIS (MOD13Q1)", "greenness (NDVI)", "250 m", "every 16 days"),
    ("ISRIC SoilGrids", "clay, sand, organic carbon, pH", "250 m", "one map"),
    ("NASA SRTM", "elevation, for slope", "30 m", "one map"),
    ("USDA Cropland Data Layer", "crop grown each year", "10 to 30 m", "yearly"),
]

SATELLITE_VS_GROUND = (
    "Every number on this page comes from a satellite or a model. That gives the same "
    "coverage for any field, but each value is an average over an area: about 50 km for "
    "weather, 250 m for soil. A rain gauge, a soil probe or a lab soil test measures one "
    "exact spot, and only that spot. Used together they are more accurate than either "
    "alone. Today you can already correct the soil pH, say the field is irrigated, fix "
    "the detected crops and rule crops out. Entering your own rain-gauge or soil-test "
    "readings is a planned next step.")

HOW_COMBINED = (
    "These datasets do not share a grid, so we do not blend them into one map. Each is "
    "read at the pin and reduced to one number for the field: ten-year averages for "
    "weather, a weekly percentile for groundwater, the single pixel under the pin for "
    "soil and crops. Coarse values are therefore shared by neighbouring fields, and "
    "fine ones can change within a field.")

UNCERTAINTY = (
    "The tool does not calculate error bars. Instead it shows the spread it has: ten "
    "years of rain and groundwater, the three driest years scored separately, each "
    "rotation replayed through every year, and a what-if for other climates. The 2040 "
    "figures are one emissions pathway from an average of climate models. Local "
    "judgment matters most where the data is coarsest or absent: drainage, soil "
    "variation inside the field, pests and disease history, markets, equipment and "
    "labour. Treat the ranking as a shortlist to discuss with a local agronomist.")

SCENARIO_NOTE = (
    "A what-if, not a forecast. The year slider is a straight-line blend between "
    "today's climate (the 2015 to 2024 average) and the 2035 to 2044 projection. The "
    "other two sliders add your own shift on top. The same shift is applied to the "
    "three driest years. It changes crop fit, never yield.")

REPLAY_NOTE = (
    "Each bar is the rotation's average crop fit using that year's actual rainfall "
    "and temperature. It is fit with that year's weather, not a harvest result. The "
    "lit bars are the three driest years.")
