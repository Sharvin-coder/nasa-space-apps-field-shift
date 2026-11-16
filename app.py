"""Field Shift -- Streamlit app.

Run from the repo root:
    streamlit run app.py

The page is laid out as a cross-section of the pinned field: the air, the
surface, the soil and the water under it, then the fine print.
"""
from __future__ import annotations

import html
import json
import os

import folium
import streamlit as st
from streamlit_folium import st_folium

from fieldshift.analyst import analyse, build_payload
from fieldshift.fingerprint import fingerprint
from fieldshift.recommend import (
    CDL_TO_CROP,
    detected_crops,
    load_crops,
    recommend,
    texture_class,
)

st.set_page_config(page_title="Field Shift", page_icon="🌾", layout="wide")

REPO_URL = "https://github.com/Sharvin-coder/nasa-space-apps-field-shift"

# The two worked examples from the submission write-up.
EXAMPLES = {"Central Iowa": (42.10, -93.55), "Southwest Kansas": (38.05, -100.95)}

# criterion key -> (README number, label, unit, decimals, source)
CRITERIA = {
    "c01_season_rain_mm": ("1", "Growing-season rainfall", "mm", 0, "NASA POWER"),
    "annual_rain_mm": ("", "Annual rainfall", "mm", 0, "NASA POWER"),
    "season_mean_temp_c": ("", "Growing-season mean temperature", "°C", 1, "NASA POWER"),
    "c02_season_gdd_c": ("2", "Growing degree days", "°C·days", 0, "NASA POWER"),
    "c03_heat_days_per_season": ("3", "Heat days (max above 32 °C)", "days", 0, "NASA POWER"),
    "c04_frost_free_days": ("4", "Frost-free days", "days", 0, "NASA POWER"),
    "c05_season_solar_mj_m2_day": ("5", "Solar radiation", "MJ/m²/day", 2, "NASA POWER"),
    "c06_aridity_index": ("6", "Aridity index (rain ÷ evaporative demand)", "", 2,
                          "NASA POWER"),
    "c07_season_rain_cv": ("7", "Year-to-year rainfall variability", "CV", 2, "NASA POWER"),
    "c08_root_zone_wetness_0to1": ("8", "Root-zone soil wetness", "on a 0–1 scale", 2,
                                   "NASA POWER (MERRA-2)"),
    "c09_dry_years": ("9", "Dry seasons, 2015–2024", "", 0, "NASA POWER"),
    "c10_groundwater_percentile_latest": ("10", "Groundwater wetness now", "percentile", 1,
                                          "NASA GRACE-FO"),
    "c10_groundwater_percentile_10yr_mean": ("10", "Groundwater wetness, 10-year average",
                                             "percentile", 1, "NASA GRACE / GRACE-FO"),
    "c11_slope_pct": ("11", "Slope", "%", 1, "NASA SRTM"),
    "c14_season_temp_change_2040_c": ("14", "Projected temperature change by 2040", "°C", 2,
                                      "NASA NEX-GDDP-CMIP6"),
    "c15_annual_rain_change_2040_pct": ("15", "Projected rainfall change by 2040", "%", 1,
                                        "NASA NEX-GDDP-CMIP6"),
    "c16_clay_pct": ("16", "Soil clay", "%", 1, "ISRIC SoilGrids 250m"),
    "c16_sand_pct": ("16", "Soil sand", "%", 1, "ISRIC SoilGrids 250m"),
    "c17_soil_organic_carbon_g_per_kg": ("17", "Soil organic carbon", "g/kg", 1,
                                         "ISRIC SoilGrids 250m"),
    "c18_soil_ph": ("18", "Soil pH in H₂O", "", 1, "ISRIC SoilGrids 250m"),
    "c19_crop_sequence": ("19", "Crops grown here, last 5 years", "", 0,
                          "USDA Cropland Data Layer"),
}
SIGNED = {"c14_season_temp_change_2040_c", "c15_annual_rain_change_2040_pct"}

# Planned criteria that are not wired yet (README, criteria 12 and 13).
UNWIRED = [
    ("12", "Field greenness trend", "NASA MODIS / HLS"),
    ("13", "Greenness drop in dry years", "NASA MODIS / HLS"),
]

CROPS = {c["crop"]: c for c in load_crops()}

# functional group -> (ink token, plain name). The four soil-health checks count these.
GROUPS = {
    "warm_grass": ("corn", "Warm-season grass"),
    "cool_grass": ("grain", "Cool-season grass"),
    "warm_broadleaf": ("squash", "Warm-season broadleaf"),
    "cool_broadleaf": ("hay", "Cool-season broadleaf"),
}

# --------------------------------------------------------------------- styles
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Besley:wght@400..900&family=Libre+Franklin:ital,wght@0,300..800;1,400..500&display=swap');

:root {
  --paper: #F0EDE2;
  --paper-2: #E2DED0;
  --ink: #1F150D;
  --ink-2: #5B4A39;

  --sky: #125A64;
  --sky-deep: #0C434B;
  --sky-tint: #C6E6E1;
  --ground: #39230F;
  --ground-deep: #25160A;
  --ground-tint: #E2CDAA;
  --leaf: #256B36;
  --leaf-tint: #CFE6C4;
  --water: #1B4A7C;
  --water-deep: #123863;
  --water-tint: #CADFF4;

  --corn: #55A04E;
  --grain: #EFBB3F;
  --squash: #E58238;
  --hay: #3FA0AB;
  --fallow: #B9A98C;

  --barn: #D2452F;
  --gold: #F4C24C;

  --good: #9AD06A;
  --note: #9AD6EA;
  --watch: #F4C24C;
  --concern: #F59A52;

  --display: 'Besley', Clarendon, Rockwell, Georgia, serif;
  --text: 'Libre Franklin', 'Franklin Gothic Medium', 'Helvetica Neue', Arial, sans-serif;
  --ease: cubic-bezier(.16, 1, .3, 1);
  --wrap: 80rem;
  --pad: max(1.25rem, calc((100vw - var(--wrap)) / 2));

  --grain-img: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .5 -.16'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  --grain-soft: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 .35 0 0 0 0 .25 0 0 0 0 .12 0 0 0 .34 -.13'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  --isobars: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 700' preserveAspectRatio='none'%3E%3Cg fill='none' stroke='%23F0EDE2' stroke-opacity='.11' stroke-width='1.5'%3E%3Cpath vector-effect='non-scaling-stroke' d='M-20 96C260 20 520 190 820 96S1260 6 1460 112'/%3E%3Cpath vector-effect='non-scaling-stroke' d='M-20 214C300 150 560 300 860 214S1240 140 1460 236'/%3E%3Cpath vector-effect='non-scaling-stroke' d='M-20 338C240 280 600 420 900 330S1280 270 1460 352'/%3E%3Cpath vector-effect='non-scaling-stroke' d='M-20 462C320 400 620 540 920 452S1260 400 1460 470'/%3E%3Cpath vector-effect='non-scaling-stroke' d='M-20 586C280 530 640 660 940 574S1300 520 1460 592'/%3E%3C/g%3E%3C/svg%3E");
  --strip-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100' preserveAspectRatio='none'%3E%3Cpath d='M0 8C22 0 46 11 100 3V94C74 100 44 89 0 97Z'/%3E%3C/svg%3E");
}

/* ------------------------------------------------------------------- base */
html, body, .stApp, .stApp button, .stApp input, .stApp textarea, .stApp select {
  font-family: var(--text) !important;
}
.stApp {
  background: var(--sky);
  color: var(--paper);
  font-variant-numeric: lining-nums;
  -webkit-font-smoothing: antialiased;
}
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stAppFooter"],
[data-testid="stFooter"],
#MainMenu { display: none !important; }

[data-testid="stMain"] {
  overflow-x: hidden;
  scroll-behavior: smooth;
  scrollbar-color: var(--paper-2) var(--sky-deep);
}
[data-testid="stMainBlockContainer"] { max-width: none !important; padding: 0 !important; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 0 !important; }

::selection { background: var(--gold); color: var(--ink); }
.st-key-plate, .st-key-plan, .st-key-band-paper { --ring: var(--barn); }
.stApp input { caret-color: var(--barn); }
.stApp a:focus-visible,
.stApp button:focus-visible,
.stApp summary:focus-visible,
.stApp input:focus-visible {
  outline: 2px solid var(--ring, var(--gold));
  outline-offset: 2px;
  border-radius: 2px;
}

.stApp [data-testid="stMarkdownContainer"] { color: inherit; margin-bottom: 0 !important; }
.stApp [data-testid="stMarkdownContainer"] p { margin: 0; color: inherit; }
.stApp [data-testid="stMarkdownContainer"] a { color: inherit; }

/* ------------------------------------------------------------------ bands */
.st-key-band-sky,
.st-key-band-leaf,
.st-key-band-gold,
.st-key-band-ground,
.st-key-band-water,
.st-key-band-paper {
  gap: 0 !important;
  padding: 0 var(--pad);
  color: var(--fg);
  background-color: var(--bg);
  background-image: var(--grain-img);
}
.st-key-band-paper { background-image: var(--grain-soft); }
.stApp:has(.foot) { background: linear-gradient(var(--sky) 0 50%, var(--paper) 50% 100%); }
.st-key-band-sky {
  padding-bottom: clamp(1.75rem, 3.4vw, 3rem);
  --bg: var(--sky); --fg: var(--paper); --fg2: var(--sky-tint);
  --rule: rgba(240, 237, 226, .28); --field: rgba(4, 34, 39, .32);
}
.st-key-band-sky {
  background-image: var(--grain-img), var(--isobars);
  background-repeat: repeat, no-repeat;
  background-size: auto, 100% 46rem;
  background-position: 0 0, 0 3.5rem;
}
.st-key-band-leaf {
  --bg: var(--leaf); --fg: var(--paper); --fg2: var(--leaf-tint);
  --rule: rgba(240, 237, 226, .28); --field: rgba(4, 26, 9, .3);
}
.st-key-band-gold {
  --bg: var(--grain); --fg: var(--ink); --fg2: #54432F;
  --rule: rgba(31, 21, 13, .3); --field: rgba(31, 21, 13, .06);
  --good: #2B6B2A; --note: #125A64; --watch: var(--ink); --concern: #A23A12;
}
.st-key-band-gold ::selection { background: var(--ink); color: var(--paper); }
.st-key-band-ground {
  --bg: var(--ground); --fg: var(--paper); --fg2: var(--ground-tint);
  --rule: rgba(240, 237, 226, .24); --field: rgba(0, 0, 0, .28);
}
.st-key-band-water {
  --bg: var(--water); --fg: var(--paper); --fg2: var(--water-tint);
  --rule: rgba(240, 237, 226, .28); --field: rgba(6, 22, 48, .34);
}
.st-key-band-paper,
.st-key-plate,
.st-key-plan {
  --bg: var(--paper); --fg: var(--ink); --fg2: var(--ink-2);
  --rule: rgba(31, 21, 13, .2); --field: rgba(31, 21, 13, .05);
}

/* --------------------------------------------------------------------- type */
.stApp h1.hero-h {
  margin: 0; padding: 0;
  font: 900 clamp(2.5rem, .2rem + 5.1vw, 5rem)/.98 var(--display);
  letter-spacing: -.024em;
  color: var(--paper);
  text-wrap: balance;
}
/* Streamlit wraps a heading's contents in one more span; step through it */
.stApp h1.hero-h > span:not(.hl-1):not(.hl-2) { display: contents; }
.stApp h1.hero-h .hl-1, .stApp h1.hero-h .hl-2 { display: block; }
.stApp h1.hero-h .hl-2 { color: var(--gold); }
.stApp h2.layer-h {
  margin: 0; padding: 0;
  font: 800 clamp(1.75rem, 1.25rem + 1.35vw, 2.375rem)/1.06 var(--display);
  letter-spacing: -.016em;
  color: var(--fg);
  text-wrap: balance;
}
.stApp h3.group-h {
  margin: 0; padding: 0;
  font: 700 1.1875rem/1.2 var(--display);
  letter-spacing: -.005em;
  color: var(--fg);
}
.stApp p.lead {
  margin: .625rem 0 0;
  max-width: 64ch;
  font-size: 1.0625rem;
  line-height: 1.5;
  color: var(--fg2);
}
.stApp p.small, .small {
  font-size: .8125rem;
  line-height: 1.45;
  color: var(--fg2);
}
.stApp .tnum { font-variant-numeric: tabular-nums lining-nums; }

.ic {
  flex: none; fill: none; stroke: currentColor; stroke-width: 1.6;
  stroke-linecap: round; stroke-linejoin: round; vertical-align: -.16em;
}

/* ---------------------------------------------------------------- masthead */
.mast {
  display: flex; align-items: center; flex-wrap: wrap; gap: .5rem 1rem;
  padding: 1.125rem 0 .875rem;
  border-bottom: 1px solid var(--rule);
  animation: rise .7s var(--ease) both;
}
.mast-mark {
  display: inline-flex; align-items: center; gap: .6rem;
  font: 900 1.4375rem/1 var(--display);
  letter-spacing: -.012em;
  color: var(--paper);
}
.stApp .mast-tag { font-size: .8125rem; color: var(--sky-tint); }
.mast-nav { margin-left: auto; display: flex; gap: 1.375rem; }
.stApp .mast-nav a {
  font-size: .875rem; font-weight: 600; color: var(--paper);
  text-decoration: underline;
  text-decoration-color: rgba(240, 237, 226, .45);
  text-decoration-thickness: 1.5px;
  text-underline-offset: .24em;
  transition: text-decoration-color .18s var(--ease);
}
.stApp .mast-nav a:hover { text-decoration-color: var(--gold); }

/* -------------------------------------------------------------------- hero */
/* line one sits beside the deck; line two runs the full width under both */
.hero {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  column-gap: clamp(2rem, 4vw, 4rem);
  align-items: end;
  padding: clamp(1.5rem, 2.6vw, 2.25rem) 0 clamp(1.125rem, 1.9vw, 1.625rem);
}
.hero > div:has(> h1) { display: contents; }
.stApp h1.hero-h {
  grid-column: 1 / -1; grid-row: 1 / 3;
  display: grid; grid-template-columns: subgrid; grid-template-rows: subgrid;
  align-items: end;
}
.stApp h1.hero-h .hl-1 { grid-area: 1 / 1; white-space: nowrap; }
/* inline-size containment keeps the long second line from sizing the first column */
.stApp h1.hero-h .hl-2 { grid-area: 2 / 1 / 3 / -1; contain: inline-size; }
.stApp p.hero-deck {
  grid-area: 1 / 2;
  justify-self: end; align-self: end;
  font-size: 1.0625rem; line-height: 1.5; color: var(--sky-tint);
  max-width: 44ch; padding-bottom: .75rem;
  animation: rise .9s var(--ease) .24s both;
}
.stApp h1.hero-h .hl-1, .stApp h1.hero-h .hl-2 { animation: rise .9s var(--ease) both; }
.stApp h1.hero-h .hl-2 { animation-delay: .12s; }

.st-key-hero-cols { gap: 0 !important; }
.st-key-hero-cols > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {
  gap: 1.75rem !important;
  align-items: stretch !important;
}
.st-key-hero-cols > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"]
  > [data-testid="stColumn"] > [data-testid="stVerticalBlock"],
.st-key-hero-cols > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"]
  > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] {
  height: 100%;
}

/* the two paper plates: the map and the plan */
.st-key-plate, .st-key-plan {
  background: var(--paper);
  color: var(--ink);
  border-radius: 3px;
  box-shadow: 0 26px 48px -26px rgba(2, 24, 28, .78), 0 3px 9px rgba(2, 24, 28, .24);
}
.st-key-plate {
  padding: .625rem .625rem .875rem;
  gap: .625rem !important;
  animation: settle 1s var(--ease) .3s both;
}
.st-key-plan {
  padding: 1.25rem 1.375rem 1.125rem;
  gap: .75rem !important;
  height: 100%;
  animation: settle 1s var(--ease) .42s both;
}
.st-key-plate iframe { display: block; border: 0; border-radius: 2px; background: var(--sky-deep); }
.st-key-plate-controls { padding: 0 .375rem; gap: .625rem !important; }
.plat {
  display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem;
  padding: .375rem .375rem .125rem;
}
.stApp p.plat-title { font: 800 1.1875rem/1.15 var(--display); letter-spacing: -.008em; color: var(--ink); }
.stApp p.plat-sub { margin-top: .2rem; font-size: .8125rem; line-height: 1.35; color: var(--ink-2); }
.north { flex: none; color: var(--ink); }
.north path { fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
.north path.north-head { fill: currentColor; }
.north text { font: 800 11px var(--display); fill: currentColor; }
.stApp p.plate-cap { font-size: .875rem; line-height: 1.4; color: var(--ink-2); }
.stApp p.plate-cap b { color: var(--ink); font-weight: 650; }

.st-key-examples {
  flex-direction: row !important; flex-wrap: wrap !important;
  align-items: baseline !important; gap: .25rem 1rem !important;
}
.st-key-examples > [data-testid="stElementContainer"] { width: auto !important; flex: 0 0 auto !important; }
.st-key-examples [data-testid="stBaseButton-secondary"] {
  background: transparent !important; border: 0 !important; padding: 0 !important;
  min-height: 0 !important;
  color: var(--ink) !important; font-size: .875rem; font-weight: 650;
  text-decoration: underline;
  text-decoration-color: var(--barn);
  text-decoration-thickness: 2px;
  text-underline-offset: .22em;
}
.st-key-examples [data-testid="stBaseButton-secondary"]:hover { color: var(--barn) !important; }

.stApp h2.plan-h {
  margin: 0; padding: 0 0 .125rem;
  font: 800 1.5rem/1.1 var(--display);
  letter-spacing: -.012em;
  color: var(--ink);
}
.stApp p.plan-note { font-size: .8125rem; line-height: 1.4; color: var(--ink-2); margin-top: -.375rem; }
.stApp p.plan-key { margin-top: .5rem; }

.shift { display: grid; gap: .75rem; margin-top: .125rem; }
.shift-row { display: grid; gap: .3rem; }
.shift-head { display: flex; align-items: baseline; justify-content: space-between; gap: .75rem; }
.shift-label { font: 700 1rem/1.1 var(--display); color: var(--ink-2); }
.shift-row.is-next .shift-label { color: var(--ink); }
.shift-score {
  display: inline-flex; align-items: center; gap: .6rem;
  font: 700 1.375rem/1 var(--display);
  color: var(--ink-2);
}
.shift-row.is-next .shift-score { font-weight: 900; font-size: 2.125rem; color: var(--ink); }
.stApp p.plan-sum { font-size: .9375rem; line-height: 1.45; color: var(--ink); margin-top: .125rem; }
.stApp p.plan-sum b { font-weight: 700; }
.stApp p.plan-more { font-size: .875rem; }
.stApp p.plan-more a {
  display: inline-flex; align-items: center; gap: .4rem;
  color: var(--ink); font-weight: 650;
  text-decoration: underline;
  text-decoration-color: var(--barn);
  text-decoration-thickness: 2px;
  text-underline-offset: .22em;
}
.stApp p.plan-more a:hover { color: var(--barn); }
.plan-msg {
  padding: .75rem .875rem;
  border: 1.5px dashed rgba(31, 21, 13, .45);
  border-radius: 3px;
  font-size: .9375rem; line-height: 1.45; color: var(--ink);
}
.plan-msg b { font-weight: 700; }

/* ------------------------------------------------------------------ strips */
.stApp ol.strips {
  --n: 4;
  list-style: none; margin: 0; padding: 0;
  display: grid;
  grid-template-columns: repeat(var(--n), minmax(0, 1fr));
  -webkit-mask: var(--strip-mask) center / 100% 100% no-repeat;
  mask: var(--strip-mask) center / 100% 100% no-repeat;
}
/* each year carries its own dark backing, so a wrapped row leaves no empty block */
.stApp ol.strips > li {
  margin: 0;
  padding: 3px 1.5px;
  display: flex;
  background: var(--ground-deep);
  container-type: inline-size;
}
.strip-cell {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; gap: .2rem;
  min-height: 4.375rem;
  padding: .5rem .75rem .5rem .85rem;
  color: var(--ink);
  background: var(--c, var(--fallow));
  clip-path: polygon(.5rem 0, 100% 0, calc(100% - .5rem) 100%, 0 100%);
  line-height: 1.12;
}
.stApp ol.strips.p0 .strip-cell { animation: plant0 .85s var(--ease) both; animation-delay: calc(var(--i) * 85ms + var(--d, 0ms)); }
.stApp ol.strips.p1 .strip-cell { animation: plant1 .85s var(--ease) both; animation-delay: calc(var(--i) * 85ms + var(--d, 0ms)); }
.stApp ol.strips > li.g-corn { --c: var(--corn); }
.stApp ol.strips > li.g-grain { --c: var(--grain); }
.stApp ol.strips > li.g-squash { --c: var(--squash); }
.stApp ol.strips > li.g-hay { --c: var(--hay); }
.stApp ol.strips > li.strip-empty .strip-cell {
  background: repeating-linear-gradient(-58deg, rgba(240, 237, 226, .2) 0 2px, transparent 2px 9px);
}
.strip-top { display: flex; align-items: center; justify-content: space-between; gap: .25rem; height: 1.25rem; }
.strip-yr { font-size: .75rem; font-weight: 550; white-space: nowrap; }
@container (max-width: 4rem) { .strip-yr-word { display: none; } }
.strip-tag {
  display: inline-flex; align-items: center; gap: .2rem;
  font-size: .75rem; font-weight: 700; line-height: 1;
  padding: .2rem .34rem .2rem .26rem; border-radius: 2px;
  background: var(--ink); color: var(--paper);
}
.strip-tag .ic { stroke-width: 2.2; }
@container (max-width: 8.5rem) {
  .strip-tag { padding: .2rem; }
  .strip-tag-word { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
}
.strip-crop { font-weight: 750; font-size: clamp(.75rem, 14cqi, .9375rem); overflow-wrap: break-word; }
/* the marks keep a line of their own, so every crop name starts on the same line */
.strip-marks { display: flex; gap: .25rem; margin-top: auto; min-height: .875rem; }

.legend {
  display: flex; flex-wrap: wrap; gap: .4rem 1.25rem;
  margin: .75rem 0 0;
  font-size: .8125rem; line-height: 1.4; color: var(--fg2);
}
.legend span { display: inline-flex; align-items: center; gap: .4rem; white-space: nowrap; }
.legend i {
  width: .875rem; height: .875rem; border-radius: 2px; background: var(--c); flex: none;
  box-shadow: 0 0 0 1.5px var(--ground-deep);
}
.legend .ic { color: var(--fg); }

/* ------------------------------------------------------------------ layers */
.layer { padding: clamp(2.25rem, 4.4vw, 4rem) 0 0; }
.layer-end { padding-bottom: clamp(2.25rem, 4.4vw, 4rem); }
.intro {
  display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr);
  gap: .75rem 3.5rem; align-items: start;
  padding: clamp(2.5rem, 5vw, 4.25rem) 0 0;
}
.stApp p.intro-big {
  font: 700 clamp(1.375rem, 1rem + 1.1vw, 1.875rem)/1.18 var(--display);
  letter-spacing: -.012em;
  color: var(--paper);
  text-wrap: balance;
}
.stApp p.intro-big b { color: var(--gold); font-weight: 900; }
.keyline {
  display: flex; flex-wrap: wrap; align-items: center; gap: .35rem 1.125rem;
  margin: 0;
  font-size: .8125rem; line-height: 1.4; color: var(--fg2);
}
.keyline .verdict { font-weight: 500; color: var(--fg2); }

.ledgers {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2rem 4rem;
  margin-top: 1.5rem;
}
.ledgers.is-three { grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); }
.stApp ul.ledger { list-style: none; margin: .625rem 0 0; padding: 0; }
.stApp ul.ledger > li {
  margin: 0;
  padding: .55rem 0 .6rem;
  display: grid;
  grid-template-columns: 1.875rem minmax(0, 1fr);
  border-top: 1px solid var(--rule);
  font-size: .9375rem; line-height: 1.35;
}
.stApp ul.ledger > li:last-child { border-bottom: 1px solid var(--rule); }
.lg-num {
  grid-row: 1 / span 3;
  padding-top: .22rem;
  font-size: .75rem; font-weight: 600; color: var(--fg2);
  font-variant-numeric: tabular-nums lining-nums;
}
.lg-main { display: flex; align-items: baseline; gap: .5rem; min-width: 0; }
.lg-name { font-weight: 550; color: var(--fg); }
.lg-lead {
  flex: 1 1 1.25rem; min-width: 1.25rem;
  border-bottom: 1.5px dotted currentColor;
  opacity: .38;
  transform: translateY(-.26em);
}
.lg-val { white-space: nowrap; color: var(--fg); font-variant-numeric: tabular-nums lining-nums; }
.lg-val b { font: 700 1.1875rem/1 var(--display); }
.lg-unit { font-size: .8125rem; color: var(--fg2); margin-left: .18em; }
.lg-meta {
  grid-column: 2;
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: .1rem 1rem;
  margin-top: .12rem;
  font-size: .8125rem; color: var(--fg2);
}
.lg-extra { grid-column: 2; margin-top: .55rem; }
.lg-sub .lg-name::before {
  content: ""; display: inline-block;
  width: .6rem; height: .55rem; margin-right: .45rem;
  border-left: 1.5px solid var(--fg2); border-bottom: 1.5px solid var(--fg2);
  transform: translateY(-.25em);
}
.slot {
  display: inline-block;
  padding: .12rem .5rem;
  border: 1.5px dashed var(--fg2);
  border-radius: 2px;
  font: 600 .8125rem/1.3 var(--text);
  color: var(--fg2);
}

.verdict { display: inline-flex; align-items: center; gap: .4rem; font-weight: 600; color: var(--fg); white-space: nowrap; }
.v-mark { width: .625rem; height: .625rem; flex: none; border-radius: 50%; background: var(--v, var(--fg2)); }
.v-good { --v: var(--good); }
.v-note { --v: var(--note); }
.v-watch .v-mark {
  background: linear-gradient(90deg, var(--watch) 50%, transparent 50%);
  box-shadow: inset 0 0 0 1.5px var(--watch);
}
.v-concern .v-mark { border-radius: 0; background: var(--concern); clip-path: polygon(50% 0, 100% 100%, 0 100%); }
.v-plain .v-mark { background: transparent; box-shadow: inset 0 0 0 1.5px var(--fg2); }

/* ten-year histories drawn from the fetched data */
.hist { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 3px; max-width: 26rem; }
.hist-bars { align-items: end; height: 3.5rem; border-bottom: 1.5px solid var(--rule); }
.hist-bars i {
  display: block; height: var(--h); min-height: 2px;
  background: rgba(240, 237, 226, .5);
  border-radius: 1px 1px 0 0;
}
.hist-bars i.is-mark { background: var(--watch); }
.hist-bars i.is-now { background: var(--paper); }
.hist-x {
  margin-top: .25rem;
  font-size: .75rem; line-height: 1; color: var(--fg2); text-align: center;
  font-variant-numeric: tabular-nums lining-nums;
}
.stApp p.hist-cap { margin-top: .4rem; font-size: .8125rem; line-height: 1.4; color: var(--fg2); max-width: 26rem; }
.stApp ol.strips.strips-hist { max-width: 38rem; grid-template-columns: repeat(auto-fit, minmax(5.75rem, 1fr)); }
.stApp ol.strips.strips-hist .strip-cell { min-height: 3.25rem; }

/* ------------------------------------------------------- horizon and edges */
.horizon { line-height: 0; background: var(--sky) var(--grain-img); }
.horizon svg { display: block; width: 100%; height: clamp(7.5rem, 14vw, 13rem); }
.hz-top { fill: none; stroke: rgba(240, 237, 226, .6); stroke-width: 2; vector-effect: non-scaling-stroke; }
.hz-band { animation: sweep 1.15s var(--ease) both; animation-delay: calc(var(--i) * 110ms + .35s); }
.hz-band path { transition: fill .7s var(--ease); }
.hz-row { fill: none; stroke: rgba(31, 21, 13, .3); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.hz-ground { fill: var(--leaf); }
/* below the fold the planting pass is tied to the scroll, so it plays as the hills arrive */
@supports (animation-timeline: view()) {
  .horizon { view-timeline: --horizon block; }
  .hz-band {
    animation: sweep linear both;
    animation-timeline: --horizon;
    animation-delay: 0s;
    animation-range: entry 0% cover 30%;
  }
  .hz-band:nth-child(2) { animation-range: entry 20% cover 35%; }
  .hz-band:nth-child(3) { animation-range: entry 40% cover 40%; }
  .hz-band:nth-child(4) { animation-range: entry 60% cover 45%; }
}
.divide { line-height: 0; }
.divide svg { display: block; width: 100%; height: clamp(2rem, 4vw, 3.5rem); }
.divide-water { background: var(--ground) var(--grain-img); }
.divide-water .dv-fill { fill: var(--water); }
.divide-water .dv-line { fill: none; stroke: rgba(202, 223, 244, .38); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
/* where one ink meets the next: a contour edge with a sliver of overprint */
.edge { line-height: 0; background: var(--from) var(--grain-img); }
.edge svg { display: block; width: 100%; height: clamp(2rem, 3.8vw, 3.5rem); }
.edge-to { fill: var(--to); }
.edge-over { fill: var(--to); mix-blend-mode: multiply; opacity: .5; }

/* ---------------------------------------------------------------- rotations */
.st-key-priorities { gap: .875rem !important; margin-top: 1.75rem; }
.group-head { display: grid; gap: .25rem; }

.sch { margin-top: 1.75rem; }
.sch-head, .sch-row {
  display: grid;
  grid-template-columns: 3.25rem minmax(0, 1fr) minmax(0, 29rem);
  column-gap: 1.5rem;
  align-items: center;
}
.sch-head { padding-bottom: .625rem; font-size: .8125rem; font-weight: 500; color: var(--fg2); }
.sch-cols, .stApp dl.sch-nums {
  display: grid;
  grid-template-columns: 1.55fr 1fr 1fr 1.2fr 1fr;
  column-gap: .75rem;
  align-items: baseline;
  margin: 0;
}
.st-key-ranked { gap: 0 !important; }
.st-key-ranked > [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {
  gap: .375rem !important;
  padding: .875rem 0 .5rem;
  border-top: 1px solid var(--rule);
}
.sch-rank { font: 900 2.125rem/1 var(--display); color: var(--fg2); font-variant-numeric: lining-nums; }
.sch-row.is-top .sch-rank { color: var(--gold); }
.sch-rank.is-now { font: 700 .9375rem/1.1 var(--display); color: var(--fg2); }
.stApp dl.sch-nums > div { margin: 0; min-width: 0; }
.stApp dl.sch-nums dt { font-size: .75rem; font-weight: 500; color: var(--fg2); margin: 0 0 .15rem; }
.stApp dl.sch-nums dd {
  margin: 0;
  font-size: 1rem; font-weight: 600; color: var(--fg);
  font-variant-numeric: tabular-nums lining-nums;
}
.stApp dl.sch-nums dd.sch-score { font: 800 1.5rem/1 var(--display); }
.sch-row.is-top dd.sch-score { color: var(--gold); font-size: 1.875rem; font-weight: 900; }
.delta {
  display: inline-block;
  padding: .12rem .34rem;
  border-radius: 2px;
  font: 700 .8125rem/1.1 var(--text);
  font-variant-numeric: tabular-nums lining-nums;
  white-space: nowrap;
}
.delta.up { background: var(--gold); color: var(--ink); }
.delta.down { box-shadow: inset 0 0 0 1.5px currentColor; color: var(--concern); }
.st-key-plan .delta.down { color: var(--barn); }
.delta.flat { box-shadow: inset 0 0 0 1.5px var(--rule); color: var(--fg2); }
.sch-score-wrap { display: flex; align-items: baseline; flex-wrap: wrap; gap: .25rem .5rem; }
@media (min-width: 62.01rem) {
  .stApp dl.sch-nums dt {
    position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden;
    clip-path: inset(50%); white-space: nowrap;
  }
  .st-key-ranked [data-testid="stExpander"] { padding-left: 4.75rem; box-sizing: border-box; }
}
.stApp p.sch-foot { margin-top: 1.25rem; max-width: 80ch; }

.why-checks { list-style: none; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .3rem 1.25rem; margin: 0 0 .75rem; padding: 0; }
.stApp ul.why-checks > li {
  margin: 0; padding: 0;
  display: flex; align-items: baseline; gap: .4rem;
  font-size: .875rem; line-height: 1.35; color: var(--fg);
}
.stApp ul.why-checks > li.no { color: var(--fg2); }
.stApp ul.why-checks .ic { color: var(--good); transform: translateY(.12em); }
.st-key-plan ul.why-checks .ic { color: #2F7A2B; }
.stApp ul.why-checks > li.no .ic { color: var(--fg2); }
.why-wrap { overflow-x: auto; }
.stApp table.why {
  width: 100%; border-collapse: collapse; border: 0;
  font-size: .875rem; line-height: 1.3;
  font-variant-numeric: tabular-nums lining-nums;
}
.stApp table.why th, .stApp table.why td {
  padding: .4rem .75rem .4rem 0;
  border: 0; border-bottom: 1px solid var(--rule);
  text-align: left; vertical-align: baseline;
  color: var(--fg); background: transparent;
}
.stApp table.why thead th { font-size: .75rem; font-weight: 600; color: var(--fg2); white-space: nowrap; }
.stApp table.why tbody th { font-weight: 700; }
.stApp table.why td.num { font-weight: 600; }
.stApp p.why-note { margin-top: .45rem; font-size: .8125rem; line-height: 1.4; color: var(--fg2); }
.stApp p.why-note b { color: var(--fg); font-weight: 650; }

/* ------------------------------------------------------------- corrections */
.st-key-corrections { gap: .375rem !important; margin-top: 2rem; max-width: 34rem; }
.st-key-corrections .group-head { margin-bottom: .375rem; }
.st-key-refetch { margin-top: .75rem; }
.st-key-problems { gap: .75rem !important; margin-top: 1.5rem; }
.problem {
  display: flex; gap: .625rem; align-items: baseline;
  padding: .7rem .875rem;
  border: 1.5px dashed var(--fg2);
  border-radius: 3px;
  font-size: .9375rem; line-height: 1.45; color: var(--fg);
}
.problem + .problem { margin-top: .5rem; }

/* --------------------------------------------------------------- fine print */
.fine { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 2rem 3rem; margin-top: 1.5rem; }
.stApp ul.fine-list { list-style: none; margin: .75rem 0 0; padding: 0; }
.stApp ul.fine-list > li {
  margin: 0; padding: .6rem 0;
  border-top: 1px solid var(--rule);
  font-size: .9375rem; line-height: 1.5; color: var(--ink);
  max-width: 68ch;
}
.stApp ul.fine-list b { font-weight: 700; }
.foot {
  display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: .75rem 2rem;
  margin-top: 2.5rem; padding: 1.125rem 0 2.25rem;
  border-top: 1.5px solid var(--ink);
  font-size: .8125rem; line-height: 1.5; color: var(--ink-2);
}
.stApp .foot p { max-width: 78ch; }
.stApp .foot b { color: var(--ink); font-weight: 700; }
.foot nav { display: flex; flex-wrap: wrap; gap: .25rem 1.25rem; }
.stApp .foot a {
  color: var(--ink); font-weight: 650;
  text-decoration: underline; text-decoration-color: var(--barn);
  text-decoration-thickness: 2px; text-underline-offset: .22em;
}
.stApp .foot a:hover { color: var(--barn); }

/* ------------------------------------------------------- Streamlit widgets */
.stApp [data-testid="stWidgetLabel"] p {
  font-size: .875rem; font-weight: 600; line-height: 1.3; color: var(--fg);
}
.stApp [data-testid="stNumberInputContainer"] {
  background: transparent !important;
  border: 0 !important;
  border-bottom: 1.5px solid var(--fg) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
.stApp [data-testid="stNumberInputField"] {
  padding: .2rem 0 .25rem !important;
  background: transparent !important;
  color: var(--fg) !important;
  font-size: 1.0625rem !important; font-weight: 650 !important;
  font-variant-numeric: tabular-nums lining-nums;
}
.stApp [data-testid="stNumberInputContainer"]:focus-within { border-bottom-color: var(--barn) !important; }
.stApp [data-testid="stNumberInputContainer"] button { color: var(--fg2) !important; background: transparent !important; }

.stApp [data-testid="stMultiSelect"] [role="group"] {
  min-height: 2.75rem;
  background: var(--field) !important;
  border: 1.5px solid var(--fg2) !important;
  border-radius: 3px !important;
  color: var(--fg) !important;
}
.stApp [data-testid="stMultiSelect"] [role="group"]:focus-within { border-color: var(--barn) !important; }
.stApp [data-testid="stMultiSelect"] input { color: var(--fg) !important; font-size: .9375rem !important; }
.stApp [data-testid="stMultiSelect"] input::placeholder { color: var(--fg2) !important; opacity: 1; }
.stApp [data-testid="stMultiSelect"] button,
.stApp [data-testid="stMultiSelect"] svg { color: var(--fg) !important; }
.stApp span[data-tag] {
  background: var(--fallow) !important;
  color: var(--ink) !important;
  border: 0 !important;
  border-radius: 2px !important;
  font-weight: 700 !important;
}
.stApp span[data-tag] span, .stApp span[data-tag] button { color: var(--ink) !important; }

.stApp [data-testid="stRadio"] [role="radiogroup"] {
  display: inline-flex; flex-wrap: nowrap; gap: 0 !important;
  border: 1.5px solid var(--fg);
  border-radius: 3px;
  overflow: hidden;
  width: fit-content;
}
.stApp [data-testid="stRadioOption"] {
  margin: 0 !important; padding: .32rem .7rem !important;
  min-height: 0 !important;
  color: var(--fg); cursor: pointer;
  transition: background-color .16s var(--ease), color .16s var(--ease);
}
.stApp [data-testid="stRadioOption"] > div { min-height: 0 !important; }
.stApp [data-testid="stRadioOption"] > div > div:first-child { display: none !important; }
.stApp [data-testid="stRadioOption"] p { font-size: .8125rem !important; font-weight: 650; color: inherit !important; white-space: nowrap; }
.stApp [data-testid="stRadioOption"]:hover { background: var(--field); }
.stApp [data-testid="stRadioOption"][data-selected="true"] { background: var(--fg); color: var(--bg); }
.stApp [data-testid="stRadioOption"]:has(input:focus-visible) { outline: 2px solid var(--ring, var(--gold)); outline-offset: 2px; }

.stApp [data-testid="stBaseButton-secondary"] {
  min-height: 0;
  padding: .5rem .95rem;
  background: var(--paper);
  color: var(--ink);
  border: 1.5px solid var(--ink);
  border-radius: 3px;
  font-weight: 650;
  transition: background-color .18s var(--ease), transform .18s var(--ease);
}
.stApp [data-testid="stBaseButton-secondary"]:hover { background: var(--gold); color: var(--ink); border-color: var(--ink); }
.stApp [data-testid="stBaseButton-secondary"]:active { transform: translateY(1px); }
.stApp [data-testid="stBaseButton-secondary"] p { font-size: .875rem; font-weight: 650; color: inherit; }

.stApp [data-testid="stCheckbox"] label p { font-size: .9375rem; font-weight: 500; color: var(--fg); }

.stApp [data-testid="stSlider"] [role="group"] { padding-top: .875rem; }
.stApp [data-testid="stSlider"] [role="group"] > div[data-orientation] > div:first-child {
  background-color: var(--ground-deep);
  box-shadow: 0 0 0 4px var(--ground-deep), 0 0 0 5px rgba(240, 237, 226, .5);
  border-radius: 999px;
}
.stApp [data-testid="stSlider"] [role="group"] > div[data-orientation] > div[data-rac] {
  box-shadow: 0 0 0 2.5px var(--paper), 0 3px 8px rgba(0, 0, 0, .45);
}
.stApp [data-testid="stSlider"] [data-testid="stSliderThumbValue"] p {
  font: 800 1.0625rem/1 var(--display); color: var(--fg);
}
.stApp [data-testid="stSlider"] [data-testid="stSliderTickBar"] { color: var(--fg2); font-size: .75rem; }

.stApp [data-testid="stExpander"] details {
  border: 0; border-radius: 0; background: transparent;
  border-top: 1px solid var(--rule);
}
.st-key-ranked [data-testid="stExpander"] details { border-top: 0; }
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary:hover,
.stApp [data-testid="stExpander"] summary:focus,
.stApp [data-testid="stExpander"] summary:active,
.stApp [data-testid="stExpander"] details[open] > summary {
  background: transparent !important;
}
.stApp [data-testid="stExpander"] summary {
  padding: .5rem 0;
  color: var(--fg);
  transition: color .16s var(--ease);
}
.stApp [data-testid="stExpander"] summary p { font-size: .9375rem; font-weight: 650; color: inherit; }
.stApp [data-testid="stExpander"] summary:hover { color: var(--gold); }
.st-key-plan [data-testid="stExpander"] summary:hover { color: var(--barn); }
.stApp [data-testid="stExpander"] summary svg, .stApp [data-testid="stExpander"] summary [data-testid="stIconMaterial"] { color: inherit; }
.stApp [data-testid="stExpanderDetails"] { padding: .25rem 0 .75rem; }

/* ----------------------------------------------------------------- loading */
.loading { display: grid; gap: .875rem; }
.stApp ol.strips.is-loading .strip-cell { min-height: 3.25rem; animation: seed 1.6s var(--ease) infinite; animation-delay: calc(var(--i) * 160ms); }
.stApp .loading p { font-size: .9375rem; line-height: 1.45; color: var(--ink); }

/* ------------------------------------------------------------------ motion */
@keyframes rise {
  from { opacity: 0; transform: translateY(1.1rem); filter: blur(5px); }
  to { opacity: 1; transform: none; filter: none; }
}
@keyframes settle {
  from { opacity: 0; transform: translateY(1.5rem) rotate(-.5deg); }
  to { opacity: 1; transform: none; }
}
@keyframes sweep {
  from { clip-path: inset(0 100% 0 0); }
  to { clip-path: inset(0 0 0 0); }
}
@keyframes plant0 {
  from { clip-path: polygon(.5rem 0, .5rem 0, 0 100%, 0 100%); }
  to { clip-path: polygon(.5rem 0, 100% 0, calc(100% - .5rem) 100%, 0 100%); }
}
@keyframes plant1 {
  from { clip-path: polygon(.5rem 0, .5rem 0, 0 100%, 0 100%); }
  to { clip-path: polygon(.5rem 0, 100% 0, calc(100% - .5rem) 100%, 0 100%); }
}
@keyframes seed {
  0%, 100% { background: var(--fallow); }
  25% { background: var(--corn); }
  50% { background: var(--grain); }
  75% { background: var(--squash); }
}
@media (prefers-reduced-motion: reduce) {
  .stApp *, .stApp *::before, .stApp *::after {
    animation-duration: .01ms !important;
    animation-delay: 0ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
  }
  [data-testid="stMain"] { scroll-behavior: auto; }
  .hz-band { animation: none !important; }
}

/* -------------------------------------------------------------- responsive */
@media (max-width: 62rem) {
  .hero, .intro { grid-template-columns: minmax(0, 1fr); align-items: start; }
  .hero { row-gap: .75rem; }
  .stApp h1.hero-h { display: block; grid-column: auto; grid-row: auto; }
  .stApp h1.hero-h .hl-1 { white-space: normal; }
  .stApp h1.hero-h .hl-2 { contain: none; }
  .stApp p.hero-deck { grid-area: auto; justify-self: start; max-width: 46ch; padding-bottom: 0; }
  .fine { grid-template-columns: minmax(0, 1fr); }
  /* stacked: the answer leads, the map follows */
  .st-key-hero-cols > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {
    order: -1;
  }
  .st-key-hero-cols > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {
    flex-direction: column !important;
  }
  .st-key-hero-cols > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    width: 100% !important; flex: 1 1 auto !important; min-width: 0 !important;
  }
  .sch-head { display: none; }
  .sch-row { grid-template-columns: 2.75rem minmax(0, 1fr); row-gap: .75rem; }
  .stApp dl.sch-nums { grid-column: 1 / -1; grid-template-columns: 1.4fr 1fr 1fr 1.2fr 1fr; }
}
@media (max-width: 52rem) {
  .ledgers, .ledgers.is-three { grid-template-columns: minmax(0, 1fr); }
  .ledgers { row-gap: 0; }
  .ledgers > div + div { margin-top: 1.75rem; }
  .stApp .ledgers > ul.ledger + ul.ledger { margin-top: 0; }
  .stApp .ledgers > ul.ledger + ul.ledger > li:first-child { border-top: 0; }
}
@media (max-width: 40rem) {
  .st-key-plate-controls > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {
    flex-direction: row !important; flex-wrap: wrap !important; gap: .75rem 1rem !important;
  }
  .st-key-plate-controls > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex: 1 1 7.5rem !important; width: auto !important; min-width: 7.5rem !important;
  }
  .st-key-plate-controls > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
    flex-basis: 100% !important;
  }
}
@media (max-width: 40rem) {
  .st-key-priorities > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] { gap: .25rem !important; }
  .st-key-plan { padding: 1.125rem 1rem 1rem; }
  .sch-row { grid-template-columns: minmax(0, 1fr); row-gap: .5rem; }
  .sch-rank { font-size: 1.625rem; }
}
@media (max-width: 36rem) {
  .mast-nav { margin-left: 0; width: 100%; }
  .stApp dl.sch-nums { grid-template-columns: repeat(3, minmax(0, 1fr)); row-gap: .6rem; }
  .why-checks { grid-template-columns: minmax(0, 1fr); }
  .strip-cell { padding: .45rem .5rem .45rem .7rem; }
  .shift-row.is-next .shift-score { font-size: 1.75rem; }
}
</style>
"""

# one tag colour per crop in "What do you grow now?", matching its strip ink
CSS_TAGS = "<style>" + "".join(
    f'.stApp span[data-tag][aria-label="{name}"]{{background:var(--{GROUPS[c["group"]][0]})!important;}}'
    for name, c in CROPS.items()) + "</style>"

ICONS = {
    "check": '<path d="M3 8.6l3.1 3L13 4.6"/>',
    "cross": '<path d="M4.2 4.2l7.6 7.6M11.8 4.2l-7.6 7.6"/>',
    "down": '<path d="M8 2.6v10.6M3.9 9.3L8 13.4l4.1-4.1"/>',
    "plus": '<path d="M8 3v10M3 8h10"/>',
    "legume": '<path d="M8 14V7.2M8 9.6C5.4 9.6 3.9 8 3.9 5.5 6.5 5.5 8 7.1 8 9.6zM8 7.2c0-2.3 1.4-3.8 3.8-3.8 0 2.4-1.5 3.8-3.8 3.8z"/>',
    "sod": '<path d="M2.4 13.6h11.2M8 13.6V5.8M5.2 13.6c0-2.6-.9-4.2-2.2-5.2M10.8 13.6c0-2.6.9-4.2 2.2-5.2"/>',
    "residue": '<path d="M2.4 13.6h11.2M4.8 13.6V9.2M8 13.6V7.4M11.2 13.6V9.2M4.8 9.2L3.6 8M8 7.4l1.2-1.3M11.2 9.2l1.2-1.2"/>',
    "alert": '<path d="M8 2.6l5.8 10.4H2.2zM8 6.6v3.2M8 11.6v.2"/>',
}

MARK = ('<svg width="36" height="24" viewBox="0 0 36 24" aria-hidden="true">'
        '<path d="M1 8C9 1 15 9 23 5s9-3 12-1v5c-4-3-7-2-12 1S9 6 1 13z" fill="#EFBB3F"/>'
        '<path d="M1 14c8-7 14 1 22-3s9-3 12-1v5c-4-3-7-2-12 1S9 12 1 19z" fill="#F0EDE2"/>'
        '<path d="M1 20c8-7 14 1 22-3s9-3 12-1v5c-4-3-7-2-12 1S9 18 1 24z" fill="#E58238"/></svg>')


# --------------------------------------------------------------------- helpers
def esc(value) -> str:
    return html.escape(str(value), quote=True)


def emit(body: str) -> None:
    """Write a block of HTML. Blank or indented lines would end Markdown's raw-HTML block."""
    text = "\n".join(line.strip() for line in body.splitlines() if line.strip())
    try:
        st.markdown(text, unsafe_allow_html=True, anchors=False)
    except TypeError:  # Streamlit before the anchors option
        st.markdown(text, unsafe_allow_html=True)


def icon(name: str, size: int = 16, label: str = "") -> str:
    a11y = f'role="img" aria-label="{esc(label)}"' if label else 'aria-hidden="true"'
    title = f"<title>{esc(label)}</title>" if label else ""
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 16 16" {a11y}>'
            f"{title}{ICONS[name]}</svg>")


def fmt_num(value, digits: int = 1, signed: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return esc(value)
    if signed:
        return f"{number:+,.{digits}f}"
    return f"{number:,.{digits}f}" if digits else f"{round(number):,}"


def join_words(items) -> str:
    items = [str(x) for x in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def coord_text(lat: float, lon: float) -> str:
    return (f"{abs(lat):.3f}° {'N' if lat >= 0 else 'S'}, "
            f"{abs(lon):.3f}° {'E' if lon >= 0 else 'W'}")


# ------------------------------------------------------------------- verdicts
# The cut-offs below are the team's own rules of thumb. They are shown beside the
# measurements for quick reading and never enter the ranking.
def verdict_for(key: str, c: dict):
    """Return (label, tone) for one criterion, or None when there is nothing to say."""
    v = c.get(key)
    if v is None:
        return None
    if key == "c10_groundwater_percentile_latest":
        if v < 10:
            return "Severe deficit", "concern"
        if v < 30:
            return "Deficit / dry", "watch"
        if v <= 65:
            return "Normal baseline", "good"
        if v <= 80:
            return "Above normal", "note"
        return "Very wet", "note"
    if key == "c10_groundwater_percentile_10yr_mean":
        if v < 25:
            return "Below normal", "watch"
        if v <= 75:
            return "Normal baseline", "good"
        return "Above normal", "note"
    if key == "c11_slope_pct":
        if v < 2:
            return "Minimal runoff risk", "plain"
        if v <= 5:
            return "Moderate slope", "watch"
        return "Erosion risk", "concern"
    if key == "c14_season_temp_change_2040_c":
        if v < 0:
            return "Cooling trend", "note"
        if v < 0.3:
            return "Stable", "plain"
        if v < 1.0:
            return "Warming trend", "concern"
        return "Strong warming", "concern"
    if key == "c15_annual_rain_change_2040_pct":
        if v > 2:
            return "Wetter trend", "good"
        if v > -2:
            return "Near normal", "plain"
        if v > -5:
            return "Slight decrease", "watch"
        return "Drying trend", "concern"
    if key == "c16_clay_pct":
        texture = texture_class(v, c.get("c16_sand_pct"))
        return {"heavy": "Heavy texture", "light": "Light texture",
                "medium": "Medium texture"}.get(texture, "Texture unknown"), "plain"
    if key == "c16_sand_pct":
        if v > 65:
            return "Fast drainage", "watch"
        if v >= 35:
            return "Balanced drainage", "plain"
        return "Slow drainage", "watch"
    if key == "c17_soil_organic_carbon_g_per_kg":
        if v < 10:
            return "Depleted / needs carbon", "watch"
        if v < 20:
            return "Moderate carbon", "plain"
        return "Carbon-rich", "good"
    if key == "c18_soil_ph":
        if 5.5 <= v <= 7.5:
            return "Optimal range", "good"
        if 5.0 <= v <= 8.0:
            return "Acceptable", "watch"
        return "Out of range", "concern"
    if key == "c03_heat_days_per_season":
        if v > 45:
            return "Heat stress", "concern"
        if v > 25:
            return "Warm season", "watch"
        return None
    if key == "c04_frost_free_days":
        if v >= 180:
            return "Long season", "good"
        if v >= 120:
            return "Adequate season", "plain"
        return "Short season", "watch"
    if key == "c06_aridity_index":
        if v < 0.05:
            return "Hyper-arid", "concern"
        if v < 0.2:
            return "Arid", "concern"
        if v < 0.5:
            return "Semi-arid", "watch"
        if v < 0.65:
            return "Dry sub-humid", "watch"
        return "Humid / sub-humid", "good"
    if key == "c07_season_rain_cv":
        if v < 0.2:
            return "Stable rainfall", "good"
        if v < 0.3:
            return "Variable rainfall", "watch"
        return "Highly variable", "concern"
    if key == "c08_root_zone_wetness_0to1":
        if v < 0.3:
            return "Dry root zone", "watch"
        if v <= 0.6:
            return "Moderate moisture", "plain"
        return "Wet root zone", "good"
    if key == "c09_dry_years":
        n = len(v) if isinstance(v, (list, tuple)) else 0
        return f"{n} dry season{'s' if n != 1 else ''}", "watch" if n >= 3 else "plain"
    return None


def verdict_html(label: str, tone: str) -> str:
    return f'<span class="verdict v-{tone}"><i class="v-mark"></i>{esc(label)}</span>'


# -------------------------------------------------------------------- ledgers
def is_filled(key: str, c: dict) -> bool:
    value = c.get(key)
    if key == "c19_crop_sequence":
        return bool(value)
    return value is not None


def ledger_row(key: str, c: dict, *, sub: bool = False, extra: str = "", note: str = "") -> str:
    num, label, unit, digits, source = CRITERIA[key]
    value = c.get(key)
    if not is_filled(key, c):
        val = '<span class="slot">missing</span>'
    elif key == "c09_dry_years":
        val = f"<b>{esc(', '.join(str(y) for y in value) or 'none')}</b>"
    else:
        val = f"<b>{fmt_num(value, digits, key in SIGNED)}</b>"
        if unit:
            val += f'<span class="lg-unit">{esc(unit)}</span>'
    verdict = verdict_for(key, c)
    verdict_part = verdict_html(*verdict) if verdict else ""
    note_part = f" · {esc(note)}" if note else ""
    extra_part = f'<div class="lg-extra">{extra}</div>' if extra else ""
    return (f'<li class="lg-row{" lg-sub" if sub else ""}"><span class="lg-num">{esc(num)}</span>'
            f'<div class="lg-main"><span class="lg-name">{esc(label)}</span>'
            f'<span class="lg-lead" aria-hidden="true"></span><span class="lg-val">{val}</span></div>'
            f'<div class="lg-meta"><span>{esc(source)}{note_part}</span>{verdict_part}</div>'
            f"{extra_part}</li>")


def slot_row(num: str, label: str, source: str) -> str:
    return (f'<li class="lg-row"><span class="lg-num">{esc(num)}</span>'
            f'<div class="lg-main"><span class="lg-name">{esc(label)}</span>'
            f'<span class="lg-lead" aria-hidden="true"></span>'
            f'<span class="lg-val"><span class="slot">not wired yet</span></span></div>'
            f'<div class="lg-meta"><span>{esc(source)}</span></div></li>')


def history_bars(series: dict, *, marked=(), latest=None, ceiling=None, unit: str = "",
                 label: str = "") -> str:
    """Ten-year history as bars. series maps a year (or date) label to a value."""
    if not series:
        return ""
    keys = sorted(series)
    top = ceiling or max(series.values()) or 1
    bars, ticks = [], []
    for k in keys:
        year = str(k)[:4]
        cls = "is-now" if k == latest else "is-mark" if year in {str(m) for m in marked} else ""
        height = max(3.0, min(100.0, 100 * float(series[k]) / top))
        bars.append(f'<i class="{cls}" style="--h:{height:.0f}%" '
                    f'title="{esc(year)}: {float(series[k]):.0f}{esc(unit)}"></i>')
        ticks.append(f"<span>’{esc(year[2:])}</span>")
    return (f'<div class="hist hist-bars" role="img" aria-label="{esc(label)}">{"".join(bars)}</div>'
            f'<div class="hist hist-x" aria-hidden="true">{"".join(ticks)}</div>')


# --------------------------------------------------------------------- strips
def crop_marks(crop: dict) -> str:
    marks = []
    if crop["legume"]:
        marks.append(icon("legume", 14, "legume"))
    if crop["perennial"]:
        marks.append(icon("sod", 14, "perennial sod crop"))
    if crop["residue"] == "high":
        marks.append(icon("residue", 14, "high residue"))
    return f'<span class="strip-marks">{"".join(marks)}</span>'


def strips_html(rotation, *, slots: int | None = None, added=(), flip: int = 0,
                delay_ms: int = 0, label: str = "") -> str:
    """One rotation cycle as a row of year strips, coloured by functional group."""
    cells = []
    for i, name in enumerate(rotation):
        crop = CROPS.get(name)
        ink = GROUPS[crop["group"]][0] if crop else ""
        tag = (f'<span class="strip-tag">{icon("plus", 11)}<span class="strip-tag-word">added</span></span>'
               if name in added else "")
        cells.append(
            f'<li class="g-{ink}" style="--i:{i}"><span class="strip-cell"><span class="strip-top">'
            f'<span class="strip-yr"><span class="strip-yr-word">Year </span>{i + 1}</span>{tag}</span>'
            f'<span class="strip-crop">{esc(name)}</span>{crop_marks(crop) if crop else ""}</span></li>')
    for i in range(len(rotation), slots or len(rotation)):
        cells.append(f'<li class="strip-empty" style="--i:{i}" aria-hidden="true">'
                     '<span class="strip-cell"></span></li>')
    return (f'<ol class="strips p{flip}" style="--n:{max(slots or 0, len(rotation))};--d:{delay_ms}ms" '
            f'aria-label="{esc(label or " then ".join(rotation))}">{"".join(cells)}</ol>')


def history_strips(seq: dict) -> str:
    cells = []
    for i, year in enumerate(sorted(seq)):
        crop = CROPS.get(CDL_TO_CROP.get(seq[year], ""))
        ink = GROUPS[crop["group"]][0] if crop else ""
        cells.append(
            f'<li class="g-{ink}" style="--i:{i}"><span class="strip-cell"><span class="strip-top">'
            f'<span class="strip-yr">{esc(year)}</span></span>'
            f'<span class="strip-crop">{esc(seq[year])}</span></span></li>')
    return (f'<ol class="strips strips-hist p0" style="--n:{len(cells)}" '
            f'aria-label="Crops by year">{"".join(cells)}</ol>')


def delta_html(value, baseline_value) -> str:
    if baseline_value is None:
        return ""
    diff = value - baseline_value
    if abs(diff) < 0.005:
        return '<span class="delta flat">same as now</span>'
    return f'<span class="delta {"up" if diff > 0 else "down"}">{diff:+.2f} vs now</span>'


def schedule_row(r: dict, *, rank: int | None, baseline: dict | None, slots: int,
                 current, flip: int) -> str:
    met = sum(1 for ok in r["soil_checks"].values() if ok)
    rank_html = (f'<div class="sch-rank">{rank}</div>' if rank
                 else '<div class="sch-rank is-now">Now</div>')
    added = [] if rank is None else [n for n in r["rotation"] if n not in current]
    future = f'{r["fit_2040"]:.2f}' if r.get("fit_2040") is not None else '<span class="slot">missing</span>'
    delta = delta_html(r["score"], baseline["score"]) if (baseline and rank) else ""
    return f"""
<div class="sch-row{' is-top' if rank == 1 else ''}">
{rank_html}
{strips_html(r['rotation'], slots=slots, added=added, flip=flip, delay_ms=(rank or 0) * 70)}
<dl class="sch-nums">
<div><dt>Overall score</dt><dd class="sch-score"><span class="sch-score-wrap">{r['score']:.2f}{delta}</span></dd></div>
<div><dt>Climate fit</dt><dd>{r['fit']:.2f}</dd></div>
<div><dt>Soil checks</dt><dd>{met} of 4</dd></div>
<div><dt>Water saving</dt><dd>{r['water_saving']:.2f}</dd></div>
<div><dt>Fit in 2040</dt><dd>{future}</dd></div>
</dl>
</div>
"""


def why_html(r: dict) -> str:
    checks = "".join(
        f'<li class="{"" if ok else "no"}">{icon("check" if ok else "cross", 14, "met" if ok else "not met")}'
        f"<span>{esc(name[:1].upper() + name[1:])}</span></li>"
        for name, ok in r["soil_checks"].items())
    has_future = any(c.get("fit_2040") is not None for c in r["crops"].values())
    rows, notes = [], []
    for name, c in r["crops"].items():
        future = ""
        if has_future:
            future = (f'<td class="num">{c["fit_2040"]:.2f}</td>' if c.get("fit_2040") is not None
                      else "<td>not available</td>")
        rows.append(f'<tr><th scope="row">{esc(name)}</th><td class="num">{c["fit"]:.2f}</td>'
                    f'<td class="num">{c["dry_year_fit"]:.2f}</td>{future}'
                    f"<td>{esc(c['limiting_factor'] or 'nothing')}</td></tr>")
        if c["notes"]:
            notes.append(f'<p class="why-note"><b>{esc(name)}:</b> {esc("; ".join(c["notes"]))}</p>')
    future_head = '<th scope="col">Fit in 2040</th>' if has_future else ""
    return f"""
<ul class="why-checks">{checks}</ul>
<div class="why-wrap"><table class="why">
<thead><tr><th scope="col">Crop</th><th scope="col">Fit</th><th scope="col">Dry-year fit</th>{future_head}<th scope="col">Limited by</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>
{''.join(notes)}
<p class="why-note">Average optimal-minimum rainfall for these crops is <b>{r['mean_optimal_min_rain_mm']:.0f} mm</b>.</p>
"""


def horizon_html(inks) -> str:
    tops = ["M0 96C230 40 470 62 720 84S1200 126 1440 70",
            "M0 130C250 78 520 100 760 118S1220 160 1440 106",
            "M0 164C290 118 560 140 800 152S1240 194 1440 142",
            "M0 198C320 156 600 178 840 186S1260 226 1440 178"]
    bands = "".join(
        f'<g class="hz-band" style="--i:{i}"><path d="{d}V240H0Z" fill="var(--{inks[i % len(inks)]})"/>'
        + (f'<path class="hz-top" d="{d}"/>' if i == 0 else "")
        + f'<path class="hz-row" d="{d}" transform="translate(0 12)"/>'
        f'<path class="hz-row" d="{d}" transform="translate(0 23)"/></g>'
        for i, d in enumerate(tops))
    return ('<div class="horizon" aria-hidden="true"><svg viewBox="0 0 1440 240" '
            f'preserveAspectRatio="none">{bands}'
            '<path class="hz-ground" d="M0 228C340 198 640 212 880 218S1280 240 1440 210V240H0Z"/>'
            "</svg></div>")


WATER_TABLE = ('<div class="divide divide-water" aria-hidden="true"><svg viewBox="0 0 1440 56" '
               'preserveAspectRatio="none">'
               '<path class="dv-fill" d="M0 20C180 4 360 32 540 20S900 6 1080 22 1320 32 1440 16V56H0Z"/>'
               '<path class="dv-line" d="M0 34C180 20 360 46 540 34S900 22 1080 36 1320 46 1440 30"/>'
               '<path class="dv-line" d="M0 47C180 35 360 57 540 47S900 37 1080 49 1320 57 1440 43"/>'
               "</svg></div>")
EDGE_PATHS = ["M0 26C200 6 420 40 680 24S1160 4 1440 22",
              "M0 18C240 40 520 4 800 22S1240 42 1440 16",
              "M0 30C180 12 380 36 620 20S1100 8 1440 28"]


def edge(frm: str, to: str, shape: int = 0) -> str:
    """The curved contour where one band of ink meets the next."""
    d = EDGE_PATHS[shape % len(EDGE_PATHS)]
    return (f'<div class="edge" style="--from:var(--{frm});--to:var(--{to})" aria-hidden="true">'
            '<svg viewBox="0 0 1440 56" preserveAspectRatio="none">'
            f'<path class="edge-over" d="{d}V56H0Z" transform="translate(0 -7)"/>'
            f'<path class="edge-to" d="{d}V56H0Z"/></svg></div>')


# ---------------------------------------------------------------------- data
@st.cache_data(show_spinner=False, ttl=24 * 3600)
def site_data(lat: float, lon: float) -> dict:
    """One NASA POWER + SoilGrids fetch per location. Failures are not cached."""
    fp = fingerprint(lat, lon)
    if "annual_rain_mm" not in fp["criteria"]:
        raise RuntimeError("; ".join(fp["notes"]) or "climate data unavailable")
    return fp


def analyst_key() -> str | None:
    """The Anthropic API key from Streamlit secrets or the environment, if any."""
    try:
        key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:  # no secrets file, or no such secret
        key = os.environ.get("ANTHROPIC_API_KEY")
    return key or None


@st.cache_data(show_spinner=False, ttl=24 * 3600, max_entries=500)
def ai_reading(signature: str, _res: dict, _api_key: str) -> dict:
    """One paid model call per distinct field and settings, shared by all visitors."""
    return analyse(_res, _api_key)


def ai_panel(res: dict) -> None:
    """The AI analyst's reading of this field. It interprets; it never re-ranks."""
    api_key = analyst_key()
    if not api_key:      # no key configured: the app runs without the analyst
        return
    with st.expander("AI reading of this field"):
        signature = json.dumps(build_payload(res), sort_keys=True, default=str)
        wanted = st.session_state.setdefault("ai_wanted", set())
        if signature not in wanted:
            emit('<p class="plan-note">An AI model (Claude) reads the measurements and scores '
                 'on this page and says what they mean for this field. It does not change '
                 'the ranking.</p>')
            if st.button("Write the AI reading", key="ai-read"):
                wanted.add(signature)
                st.rerun()
            return
        try:
            with st.spinner("The AI analyst is reading this field…"):
                reading = ai_reading(signature, res, api_key)
        except Exception as exc:
            wanted.discard(signature)
            emit(f'<p class="plan-note">{esc(exc)}</p>')
            return
        body = "".join(f'<p class="plan-sum"><b>{esc(sec["title"].rstrip("."))}.</b> '
                       f'{esc(sec["text"])}</p>' for sec in reading["sections"])
        note = ("Written by an AI model from this page's data. It can be wrong, and it is "
                "not agronomic advice.")
        if reading["unverified_numbers"]:
            note += (" Figures in this text that we could not match to the data: "
                     + ", ".join(reading["unverified_numbers"]) + ".")
        emit(body + f'<p class="plan-note" style="margin-top:.5rem">{esc(note)}</p>')


def make_map(lat: float, lon: float, style: str) -> folium.Map:
    fmap = folium.Map(location=[lat, lon], zoom_start=13, tiles=None,
                      control_scale=True, prefer_canvas=True)

    satellite = ("https://tiles.maps.eox.at/wmts/1.0.0/"
                 "s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg")
    satellite_attr = ("Sentinel-2 cloudless 2024 by EOX IT Services GmbH "
                      "(contains modified Copernicus Sentinel data 2024)")
    labels = ("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/"
              "World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}")
    terrain = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
               "World_Topo_Map/MapServer/tile/{z}/{y}/{x}")

    if style in ("Hybrid", "Satellite"):
        folium.TileLayer(
            tiles=satellite, name="Satellite",
            attr=satellite_attr, max_zoom=18, control=False).add_to(fmap)
    if style == "Hybrid":
        folium.TileLayer(
            tiles=labels, name="Labels", overlay=True, control=False,
            attr="Tiles &copy; Esri — Esri, DeLorme, NAVTEQ",
            max_zoom=18).add_to(fmap)
    if style == "Terrain":
        folium.TileLayer(
            tiles=terrain, name="Terrain",
            attr="Tiles &copy; Esri — Esri, DeLorme, NAVTEQ",
            max_zoom=18, control=False).add_to(fmap)

    # 160 acres is about a 454 m radius circle, drawn like an inked field line.
    folium.Circle(
        [lat, lon], radius=454, color="#F0EDE2", weight=2, dash_array="7 6",
        fill=True, fill_color="#D2452F", fill_opacity=0.14).add_to(fmap)

    marker_html = ('<div class="fs-pin"><span class="fs-pin-ring"></span>'
                   '<span class="fs-pin-dot"></span></div>')
    folium.Marker(
        [lat, lon],
        tooltip="Your field",
        icon=folium.DivIcon(
            html=marker_html, icon_size=(44, 44), icon_anchor=(22, 22),
            class_name="fs-field-marker")).add_to(fmap)

    fmap.get_root().header.add_child(folium.Element("""
<style>
  .leaflet-container {
    background: #0C434B !important;
    font-family: 'Libre Franklin', 'Franklin Gothic Medium', 'Helvetica Neue', Arial, sans-serif;
    cursor: crosshair;
  }
  .fs-pin { position: relative; width: 44px; height: 44px; }
  .fs-pin-dot {
    position: absolute; left: 12px; top: 12px; width: 20px; height: 20px;
    box-sizing: border-box; border-radius: 50%;
    background: #D2452F; border: 3px solid #F0EDE2;
    box-shadow: 0 3px 8px rgba(0, 0, 0, .5);
  }
  .fs-pin-ring {
    position: absolute; inset: 5px; border-radius: 50%;
    border: 2px solid #F0EDE2;
    animation: fs-ping 2.8s cubic-bezier(.16, 1, .3, 1) infinite;
  }
  @keyframes fs-ping {
    0% { transform: scale(.6); opacity: .95; }
    70%, 100% { transform: scale(1.7); opacity: 0; }
  }
  @media (prefers-reduced-motion: reduce) { .fs-pin-ring { animation: none; opacity: .6; } }
  .leaflet-control-attribution {
    background: rgba(240, 237, 226, .84) !important;
    color: #5B4A39 !important;
    padding: 1px 6px !important;
    font-size: 9.5px !important;
    line-height: 1.35 !important;
  }
  @media (max-width: 480px) {
    .leaflet-bottom.leaflet-right { left: 0; }
    .leaflet-control-attribution {
      max-width: 100%; box-sizing: border-box;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .leaflet-control-attribution:hover,
    .leaflet-control-attribution:focus-within { white-space: normal; }
  }
  /* the scale bar sits top right, clear of the attribution line */
  .leaflet-bottom.leaflet-left { top: 0; bottom: auto; left: auto; right: 0; }
  .leaflet-bottom.leaflet-left .leaflet-control { margin: 10px 10px 0 0; }
  .leaflet-control-attribution a { color: #1F150D !important; }
  .leaflet-bar { border: 0 !important; box-shadow: 0 3px 9px rgba(2, 24, 28, .45) !important; border-radius: 3px !important; }
  .leaflet-bar a {
    background: #F0EDE2 !important; color: #1F150D !important;
    border-bottom-color: rgba(31, 21, 13, .2) !important;
    font-weight: 700;
  }
  .leaflet-bar a:first-child { border-radius: 3px 3px 0 0 !important; }
  .leaflet-bar a:last-child { border-radius: 0 0 3px 3px !important; }
  .leaflet-bar a:hover { background: #F4C24C !important; }
  .leaflet-control-scale-line {
    background: rgba(240, 237, 226, .88) !important;
    border-color: #1F150D !important;
    color: #1F150D !important;
    font-size: 10px !important;
  }
  .leaflet-tooltip {
    background: #F0EDE2 !important;
    border: 0 !important;
    border-radius: 2px !important;
    color: #1F150D !important;
    box-shadow: 0 3px 9px rgba(2, 24, 28, .45) !important;
    font-size: 12px !important; font-weight: 650;
  }
  .leaflet-tooltip-top:before { border-top-color: #F0EDE2 !important; }
</style>
"""))
    return fmap


def fine_print(divider: str) -> None:
    """How scores are made, what the tool cannot tell you, and the footer."""
    emit(divider)
    with st.container(key="band-paper"):
        emit(f"""
    <section class="layer" id="fine-print" aria-label="The fine print">
    <h2 class="layer-h">The fine print</h2>
    <div class="fine">
    <div>
    <h3 class="group-h">How scores are made</h3>
    <ul class="fine-list">
    <li><b>Climate fit</b> compares each crop's published temperature, rainfall and soil pH
    ranges (FAO EcoCrop) with this location, for the ten-year average and for the three driest years.</li>
    <li><b>Soil health</b> is the share of four checks met, from USDA NRCS Conservation Practice
    Standard 328: three or more functional groups, a legume, a perennial sod crop, and
    high-residue crops in at least half the sequence.</li>
    <li><b>Water saving</b> reflects how little rainfall the rotation's crops need (FAO EcoCrop).</li>
    <li><b>2040 fit</b> shifts today's temperature and rainfall by the change projected for
    2035–2044 (NASA NEX-GDDP-CMIP6 ensemble, middle-of-the-road SSP2-4.5 pathway) and recomputes
    crop fit. It is shown for information and does not change the ranking.</li>
    <li><b>Groundwater, slope and aridity</b> are shown for context and do not change the ranking.</li>
    <li><b>The AI reading</b> is written by a language model (Claude) that sees only the
    measurements and scores on this page. It explains them; it does not set or change any
    score. Figures in its text are checked against the data and flagged if they do not match.</li>
    </ul>
    </div>
    <div>
    <h3 class="group-h">What this tool cannot tell you</h3>
    <ul class="fine-list">
    <li><b>This is not a yield or profit forecast.</b> Prices, markets, equipment and local
    practice are not considered. Talk to a local agronomist before changing a rotation.</li>
    <li><b>Weather values are coarse.</b> They come from a grid cell about 50 km wide, so
    neighbouring fields share them. Soil and crop history are local.</li>
    <li><b>It is centred on the United States.</b> Crop history covers the contiguous US only,
    and the 2040 projection returned no data for our test sites elsewhere.</li>
    <li><b>One growing window,</b> April to September, is used for every crop.</li>
    <li><b>Two planned criteria are not wired yet:</b> field greenness trend and greenness drop
    in dry years.</li>
    </ul>
    </div>
    <div>
    <h3 class="group-h">Our own rules of thumb</h3>
    <ul class="fine-list">
    <li><b>The plain-word verdicts</b> beside each measurement, such as “Carbon-rich” or
    “Erosion risk”, use cut-offs we chose ourselves. None of them changes the ranking.</li>
    <li><b>Each crop's functional group and residue class,</b> and the “three or more groups”
    threshold, are our own labels too.</li>
    <li><b>All of these choices</b> need an agronomist's review.</li>
    </ul>
    </div>
    </div>
    <footer class="foot">
    <p><b>Field Shift</b>, built for the NASA Space Apps Challenge 2026. Data: NASA POWER,
    GRACE-FO, SRTM and NEX-GDDP-CMIP6; ISRIC SoilGrids; USDA Cropland Data Layer. Map imagery:
    Sentinel-2 cloudless by EOX, with labels and terrain from Esri.</p>
    <nav aria-label="More about Field Shift">
    <a href="{REPO_URL}#readme" target="_blank" rel="noopener">Methodology</a>
    <a href="https://power.larc.nasa.gov/" target="_blank" rel="noopener">NASA POWER</a>
    </nav>
    </footer>
    </section>
    """)


# ---------------------------------------------------------------------- state
st.session_state.setdefault("lat", 42.10)
st.session_state.setdefault("lon", -93.55)
st.session_state.setdefault("w_fit", 1)
st.session_state.setdefault("w_soil", 1)
st.session_state.setdefault("w_water", 1)
# a map click is applied here, before the coordinate boxes are drawn
if "pending_click" in st.session_state:
    st.session_state.lat, st.session_state.lon = st.session_state.pop("pending_click")
crop_names = list(CROPS)
LAT, LON = round(st.session_state.lat, 3), round(st.session_state.lon, 3)

st.markdown(CSS + CSS_TAGS, unsafe_allow_html=True)

# ================================================================== the sky
sky = st.container(key="band-sky")
with sky:
    emit(f"""
<header class="mast">
<span class="mast-mark">{MARK}Field Shift</span>
<span class="mast-tag">NASA Space Apps Challenge 2026</span>
<nav class="mast-nav" aria-label="About this tool">
<a href="#fine-print">How it scores</a>
</nav>
</header>
<div class="hero">
<h1 class="hero-h"><span class="hl-1">Drop a pin.</span> <span class="hl-2">NASA data fills in the rest.</span></h1>
<p class="hero-deck">Field Shift reads the weather, soil, groundwater and crop history for
the spot you pin, then ranks the crop rotations that fit it. It keeps what you grow now
and shows its reasons.</p>
</div>
""")

    with st.container(key="hero-cols"):
        map_col, plan_col = st.columns([7, 5])

    # ------------------------------------------------------ the map plate
    with map_col, st.container(key="plate"):
        emit(f"""
<div class="plat">
<div><p class="plat-title">Your field at {esc(coord_text(LAT, LON))}</p>
<p class="plat-sub">The dashed circle marks 160 acres around the pin.</p></div>
<svg class="north" width="26" height="42" viewBox="0 0 26 42" role="img" aria-label="North is up"><title>North is up</title><text x="13" y="10" text-anchor="middle">N</text><path class="north-head" d="M13 14l5.5 11h-11z"/><path d="M13 25v15"/></svg>
</div>
""")
        fmap = make_map(LAT, LON, st.session_state.get("map_style", "Hybrid"))
        clicked = st_folium(fmap, height=384, use_container_width=True,
                            returned_objects=["last_clicked"], key="map")
        with st.container(key="plate-controls"):
            lat_col, lon_col, style_col = st.columns([3, 3, 5], vertical_alignment="bottom")
            with lat_col:
                st.number_input("Latitude", -60.0, 75.0, step=0.001, format="%.3f", key="lat")
            with lon_col:
                st.number_input("Longitude", -180.0, 180.0, step=0.001, format="%.3f", key="lon")
            with style_col:
                st.radio("Map style", ["Hybrid", "Satellite", "Terrain"], horizontal=True,
                         label_visibility="collapsed", key="map_style")
            emit('<p class="plate-cap">Click the map to move the pin, or type its coordinates.</p>')
            with st.container(key="examples"):
                emit('<p class="plate-cap">Or try a worked example:</p>')
                for name, spot in EXAMPLES.items():
                    if st.button(name, key=f"example-{name}"):
                        st.session_state.pending_click = spot
                        st.rerun()

        click = (clicked or {}).get("last_clicked")
        if click:
            new = (round(click["lat"], 3), round(click["lng"], 3))
            # act on each click once, so typed coordinates are not overwritten later
            if new != st.session_state.get("handled_click"):
                st.session_state.handled_click = new
                st.session_state.pending_click = new
                st.rerun()

    # ----------------------------------------------------- fetch the data
    with plan_col:
        plan = st.container(key="plan")
    with plan:
        waiting = st.empty()
        if st.session_state.get("read_for") != (LAT, LON):
            with waiting:
                emit("""
<div class="loading" role="status">
<ol class="strips is-loading" style="--n:4" aria-hidden="true"><li style="--i:0"><span class="strip-cell"></span></li><li style="--i:1"><span class="strip-cell"></span></li><li style="--i:2"><span class="strip-cell"></span></li><li style="--i:3"><span class="strip-cell"></span></li></ol>
<p>Reading NASA climate, groundwater, terrain and soil data for this spot. A new location
takes about ten seconds while six data services answer.</p>
</div>
""")
    fp = None
    fetch_error = None
    try:
        fp = site_data(LAT, LON)
        st.session_state.read_for = (LAT, LON)
    except Exception as exc:  # keep the map alive so the pin can be moved
        fetch_error = exc
    waiting.empty()

    # crops seen here by satellite become the starting answer for a new location
    detected = detected_crops(fp) if fp else []
    if fp and st.session_state.get("crops_for") != (LAT, LON):
        st.session_state.crops_for = (LAT, LON)
        if detected:
            st.session_state.current = detected[:3]
    st.session_state.setdefault("current", ["corn", "soybean"])

    # every control is read from session state, so each can sit beside what it changes
    current = [n for n in st.session_state.current if n in CROPS]
    weights = {"fit": st.session_state.w_fit, "soil": st.session_state.w_soil,
               "water": st.session_state.w_water}
    irrigated = bool(st.session_state.get("irrigated", False))
    use_ph = bool(st.session_state.get("use_ph", False))
    ph = float(st.session_state.get("ph_value", 6.5)) if use_ph else None

    res = None
    rec_error = None
    if fp is not None and sum(weights.values()) > 0:
        try:
            res = recommend(LAT, LON, weights, top=5, current=tuple(current), fp=fp,
                            overrides={"ph": ph, "irrigated": irrigated or None})
        except Exception as exc:
            rec_error = exc

    baseline = res["current_rotation"] if res else None
    recs = res["recommendations"] if res else []
    top = recs[0] if recs else None
    slots = max([len(r["rotation"]) for r in recs] + [len(baseline["rotation"]) if baseline else 0, 2])

    # the strips replay their planting pass whenever the ranking changes
    signature = (LAT, LON, tuple(tuple(r["rotation"]) for r in recs),
                 tuple(baseline["rotation"]) if baseline else ())
    if st.session_state.get("rank_signature") != signature:
        st.session_state.rank_signature = signature
        st.session_state.flip = 1 - st.session_state.get("flip", 0)
    flip = st.session_state.get("flip", 0)

    # ------------------------------------------------------ the plan plate
    with plan:
        emit('<h2 class="plan-h">The shift for this field</h2>')
        st.multiselect("What do you grow now?", crop_names, key="current",
                       max_selections=3, placeholder="Add a crop")
        if detected:
            crop_note = ("Pre-filled from USDA satellite crop maps for this spot. "
                         "Change it if it is wrong.")
        elif fp and fp["criteria"].get("c19_crop_sequence"):
            crop_note = ("USDA crop maps show no field crop at this exact spot. "
                         "Pick what you grow.")
        else:
            crop_note = "Crop history is not available at this spot. Pick what you grow."
        emit(f'<p class="plan-note">{esc(crop_note)}</p>')

        if fp is None:
            emit(f"""
<div class="plan-msg"><b>Could not read this spot.</b> {esc(fetch_error)}. Move the pin onto
farmland, or try again in a moment.</div>
""")
            if st.button("Try again", key="retry-all"):
                site_data.clear()
                st.rerun()
        elif sum(weights.values()) == 0:
            emit('<div class="plan-msg">Set at least one priority above zero to rank '
                 'rotations. The three sliders are under <a href="#rotations">Rotations, '
                 'ranked</a>.</div>')
        elif rec_error is not None:
            emit(f'<div class="plan-msg">{esc(rec_error)}</div>')
        elif not top:
            emit('<div class="plan-msg">No rotation fits this field yet. Try fewer current '
                 'crops or move the pin.</div>')
        else:
            added = [n for n in top["rotation"] if n not in current]
            kept = [n for n in top["rotation"] if n in current]
            rows = ""
            if baseline:
                rows += f"""
<div class="shift-row">
<div class="shift-head"><span class="shift-label">Now</span><span class="shift-score">{baseline['score']:.2f}</span></div>
{strips_html(baseline['rotation'], slots=slots, flip=flip, delay_ms=350)}
</div>
"""
            rows += f"""
<div class="shift-row is-next">
<div class="shift-head"><span class="shift-label">Shift to</span><span class="shift-score">{delta_html(top['score'], baseline['score']) if baseline else ''}{top['score']:.2f}</span></div>
{strips_html(top['rotation'], slots=slots, added=added if baseline else (), flip=flip, delay_ms=560)}
</div>
"""
            met_top = sum(1 for ok in top["soil_checks"].values() if ok)
            if baseline:
                met_now = sum(1 for ok in baseline["soil_checks"].values() if ok)
                if met_top > met_now:
                    checks = f"Meets {met_top} of 4 soil-health checks, up from {met_now}."
                else:
                    checks = f"Meets {met_top} of 4 soil-health checks; your rotation now meets {met_now}."
                summary = (f"Keeps <b>{esc(join_words(kept))}</b> and adds "
                           f"<b>{esc(join_words(added))}</b>. {checks}")
            else:
                summary = (f"Meets {met_top} of 4 soil-health checks. Pick the crops you grow "
                           "now to compare against your current rotation.")
            emit(f"""
<div class="shift">{rows}</div>
<p class="plan-sum">{summary}</p>
<p class="small plan-key">Overall score from 0 to 1, weighted by your priorities. One strip is one year.</p>
""")
            with st.expander("Why this shift"):
                emit(why_html(top))
            ai_panel(res)
            others = len(recs) - 1
            if others > 0:
                emit(f'<p class="plan-more"><a href="#rotations">{icon("down", 15)}'
                     f'{others} more option{"s" if others != 1 else ""}, ranked</a></p>')

    # ------------------------------------------------- what the pin filled in
    if fp is not None:
        c = fp["criteria"]
        filled = sum(1 for key in CRITERIA if is_filled(key, c))
        emit(f"""
<div class="intro" id="measured">
<p class="intro-big"><b>{filled} of {len(CRITERIA)}</b> measurements filled in for this spot
from NASA and open data. You typed none of them.</p>
<div>
<p class="small">They are laid out the way they sit in the field: the air, the surface,
the soil, then the water under it.</p>
<p class="keyline" style="margin-top:.5rem">
{verdict_html('favourable', 'good')}{verdict_html('worth noting', 'note')}{verdict_html('watch', 'watch')}{verdict_html('concern', 'concern')}{verdict_html('neutral', 'plain')}
</p>
<p class="small" style="margin-top:.35rem">The plain-word verdicts use cut-offs we chose
ourselves as rules of thumb. They are not part of the data and never change the ranking.</p>
</div>
</div>
""")
        if fp["notes"]:
            with st.container(key="problems"):
                emit("".join(f'<div class="problem">{icon("alert", 16)}<span>{esc(note)}</span></div>'
                             for note in fp["notes"]))
                if st.button("Retry the missing data", key="retry-missing"):
                    site_data.clear()
                    st.rerun()

        dry_chart = history_bars(
            c.get("_season_rain_by_year_mm") or {}, marked=c.get("c09_dry_years") or (),
            unit=" mm", label="Growing-season rainfall for each year, dry seasons highlighted")
        if dry_chart:
            dry_chart += ('<p class="hist-cap">Growing-season rainfall each year. '
                          "Dry seasons are the lit bars.</p>")
        emit(f"""
<section class="layer" aria-label="In the air">
<h2 class="layer-h">In the air</h2>
<p class="lead">Ten years of daily weather, 2015 to 2024, and the change projected for 2040.
These values come from a NASA grid cell about 50 km wide, so nearby fields share them.</p>
<div class="ledgers">
<div>
<h3 class="group-h">Rain</h3>
<ul class="ledger">
{ledger_row('c01_season_rain_mm', c)}
{ledger_row('annual_rain_mm', c)}
{ledger_row('c15_annual_rain_change_2040_pct', c, sub=True)}
{ledger_row('c07_season_rain_cv', c)}
{ledger_row('c06_aridity_index', c)}
{ledger_row('c09_dry_years', c, extra=dry_chart)}
</ul>
</div>
<div>
<h3 class="group-h">Heat and season</h3>
<ul class="ledger">
{ledger_row('season_mean_temp_c', c)}
{ledger_row('c14_season_temp_change_2040_c', c, sub=True)}
{ledger_row('c02_season_gdd_c', c)}
{ledger_row('c03_heat_days_per_season', c)}
{ledger_row('c04_frost_free_days', c)}
{ledger_row('c05_season_solar_mj_m2_day', c)}
</ul>
</div>
</div>
</section>
""")
        with st.container(key="refetch"):
            if st.button("Fetch this field's data again", icon=":material/refresh:",
                         key="refresh-feeds"):
                site_data.clear()
                st.rerun()

if fp is None:
    fine_print(edge("sky", "paper", 2))
    st.stop()

# ============================================================== the horizon
horizon_inks = ([GROUPS[CROPS[n]["group"]][0] for n in top["rotation"]] if top
                else ["corn", "grain", "squash", "hay"])
emit(horizon_html(horizon_inks))

# ============================================= the field: rotations, ranked
with st.container(key="band-leaf"):
    if res:
        driest = ", ".join(str(y) for y, _r, _t in res["site"]["driest_years"])
        rot_lead = (f"Ranked from this field's ten-year temperature and rainfall, its three "
                    f"driest years ({driest}), soil pH and texture, and the three priorities "
                    f"below. Every option keeps what you grow now and adds to it.")
    elif sum(weights.values()) == 0:
        rot_lead = "Set at least one priority above zero to rank rotations."
    else:
        rot_lead = "Ranked by your priorities and the criteria measured for this field."
    emit(f"""
<section class="layer" id="rotations" aria-label="Rotations, ranked for this field">
<h2 class="layer-h">Rotations, ranked for this field</h2>
<p class="lead">{esc(rot_lead)}</p>
</section>
""")

    with st.container(key="priorities"):
        emit('<div class="group-head"><h3 class="group-h">What matters most to you?</h3>'
             '<p class="small">Slide each from 0 to 5. The ranking re-forms as you move them.</p></div>')
        fit_col, soil_col, water_col = st.columns(3, gap="large")
        with fit_col:
            st.slider("Climate fit", 0, 5, key="w_fit")
        with soil_col:
            st.slider("Soil health", 0, 5, key="w_soil")
        with water_col:
            st.slider("Water saving", 0, 5, key="w_water")

    if sum(weights.values()) == 0:
        emit(f'<div class="problem" style="margin-top:1.5rem">{icon("alert", 16)}<span>Every '
             "priority is at zero, so there is nothing to rank by. Raise at least one.</span></div>")
    elif rec_error is not None:
        emit(f'<div class="problem" style="margin-top:1.5rem">{icon("alert", 16)}'
             f"<span>{esc(rec_error)}</span></div>")
    else:
        legend = "".join(f'<span><i style="--c:var(--{ink})"></i>{esc(name)}</span>'
                         for ink, name in GROUPS.values())
        emit(f"""
<div class="legend" aria-label="What the strips show">
{legend}
<span>{icon('legume', 15)}legume</span>
<span>{icon('sod', 15)}perennial sod crop</span>
<span>{icon('residue', 15)}high residue</span>
<span><b class="strip-tag">{icon('plus', 11)}</b>added to what you grow now</span>
</div>
<p class="small" style="margin-top:.4rem">A strip's colour is its crop's functional group.
The four soil-health checks count the colours and the three marks.</p>
<div class="sch">
<div class="sch-head" aria-hidden="true">
<span>Rank</span><span>One cycle, a strip per year</span>
<div class="sch-cols"><span>Overall score</span><span>Climate fit</span><span>Soil checks</span><span>Water saving</span><span>Fit in 2040</span></div>
</div>
</div>
""")
        with st.container(key="ranked"):
            if baseline:
                with st.container(key="rank-now"):
                    emit(schedule_row(baseline, rank=None, baseline=None, slots=slots,
                                      current=current, flip=flip))
                    with st.expander(f"Why your rotation now scores {baseline['score']:.2f}"):
                        emit(why_html(baseline))
            else:
                with st.container(key="rank-now"):
                    emit('<div class="problem">Pick the crops you grow now, in the plan beside '
                         "the map, to compare these options against your current rotation.</div>")
            if not recs:
                with st.container(key="rank-none"):
                    emit(f'<div class="problem">{icon("alert", 16)}<span>No rotation fits this '
                         "field yet. Try fewer current crops or move the pin.</span></div>")
            for index, r in enumerate(recs, 1):
                with st.container(key=f"rank-{index}"):
                    emit(schedule_row(r, rank=index, baseline=baseline, slots=slots,
                                      current=current, flip=flip))
                    with st.expander(f"Why option {index} scores {r['score']:.2f}"):
                        emit(why_html(r))

        site = res["site"]
        foot = ("Dry-year check uses this location's three driest years: "
                + ", ".join(f"{y} ({r:.0f} mm)" for y, r, _ in site["driest_years"]) + ". "
                + (f"Soil texture class: {site['texture']}. " if site["texture"] else
                   "Soil texture missing, not checked. ")
                + (f"Not offered here (poor climate fit): {', '.join(res['crops_not_offered'])}."
                   if res["crops_not_offered"] else ""))
        emit(f'<p class="small sch-foot">{esc(foot)}</p>')
    emit('<div class="layer-end"></div>')

# ============================================== the surface: what grew here
emit(edge("leaf", "grain", 0))
with st.container(key="band-gold"):
    c = fp["criteria"]
    seq = c.get("c19_crop_sequence") or {}
    history = (history_strips(seq) if seq else
               '<span class="slot">no field crop registered at this spot</span>')
    num, label, _unit, _digits, source = CRITERIA["c19_crop_sequence"]
    emit(f"""
<section class="layer layer-end" aria-label="On the surface">
<h2 class="layer-h">On the surface</h2>
<p class="lead">What satellites saw growing at the pin, and the lie of the land. Crop history
is read for one pixel, 10 to 30 m wide, so a pin on a road or farmyard returns no crop.</p>
<div class="ledgers is-three">
<div>
<ul class="ledger">
<li class="lg-row"><span class="lg-num">{esc(num)}</span>
<div class="lg-main"><span class="lg-name">{esc(label)}</span></div>
<div class="lg-meta"><span>{esc(source)}</span></div>
<div class="lg-extra">{history}</div></li>
</ul>
</div>
<div>
<ul class="ledger">
{ledger_row('c11_slope_pct', c)}
{''.join(slot_row(*row) for row in UNWIRED)}
</ul>
</div>
</div>
</section>
""")

# ================================================================= the soil
emit(edge("grain", "ground", 1))
with st.container(key="band-ground"):
    c = fp["criteria"]
    ph_note = f"scoring with your value, {ph:.1f}" if ph is not None else ""
    emit(f"""
<section class="layer" aria-label="In the soil">
<h2 class="layer-h">In the soil</h2>
<p class="lead">The top 5 cm, read for a cell 250 m wide, so these values are local to the pin.</p>
<div class="ledgers">
<ul class="ledger">
{ledger_row('c16_clay_pct', c)}
{ledger_row('c16_sand_pct', c)}
</ul>
<ul class="ledger">
{ledger_row('c17_soil_organic_carbon_g_per_kg', c)}
{ledger_row('c18_soil_ph', c, note=ph_note)}
</ul>
</div>
</section>
""")
    with st.container(key="corrections"):
        emit('<div class="group-head"><h3 class="group-h">Know better than the satellite?</h3>'
             '<p class="small">Correct an auto-filled value and the ranking above follows.</p></div>')
        st.checkbox("This field is irrigated", key="irrigated")
        st.checkbox("I know my soil pH", key="use_ph")
        if st.session_state.get("use_ph"):
            st.number_input("Soil pH", 3.0, 11.0, 6.5, 0.1, key="ph_value")
    emit('<div class="layer-end"></div>')

# ================================================================ the water
emit(WATER_TABLE)
with st.container(key="band-water"):
    c = fp["criteria"]
    gw_series = c.get("_groundwater_percentile_by_date") or {}
    gw_chart = history_bars(
        gw_series, latest=c.get("_groundwater_latest_date"), ceiling=100,
        label="Groundwater wetness percentile, one reading a year")
    if gw_chart:
        gw_chart += ('<p class="hist-cap">One reading a year, taken in the same week. '
                     "The pale bar is the latest.</p>")
    emit(f"""
<section class="layer layer-end" aria-label="In the water below">
<h2 class="layer-h">In the water below</h2>
<p class="lead">Groundwater is weighed from orbit by the GRACE-FO satellites: 0 is the driest
on record for the week, 100 the wettest. Groundwater, slope and aridity are shown for context
and do not change the ranking.</p>
<div class="ledgers">
<ul class="ledger">
{ledger_row('c10_groundwater_percentile_latest', c, extra=gw_chart)}
</ul>
<ul class="ledger">
{ledger_row('c10_groundwater_percentile_10yr_mean', c)}
{ledger_row('c08_root_zone_wetness_0to1', c)}
</ul>
</div>
</section>
""")

# ============================================================ the fine print
fine_print(edge("water", "paper", 2))
