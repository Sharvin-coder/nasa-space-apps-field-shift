"""Field Shift -- Streamlit app.

Run from the repo root:
    streamlit run app.py
"""
from __future__ import annotations

import html

import folium
import streamlit as st
from streamlit_folium import st_folium

from fieldshift.fingerprint import fingerprint
from fieldshift.recommend import (
    detected_crops,
    load_crops,
    recommend,
    texture_class,
)

st.set_page_config(page_title="Field Shift", page_icon="🌾", layout="wide")

REPO_URL = "https://github.com/Sharvin-coder/nasa-space-apps-field-shift"

# criterion key -> (label, unit, source)
CRITERIA = [
    ("c01_season_rain_mm", "Growing-season rainfall", "mm", "NASA POWER"),
    ("annual_rain_mm", "Annual rainfall", "mm", "NASA POWER"),
    ("season_mean_temp_c", "Growing-season mean temperature", "°C", "NASA POWER"),
    ("c02_season_gdd_c", "Growing degree days", "°C·days", "NASA POWER"),
    ("c03_heat_days_per_season", "Heat days (max above 32 °C)", "days", "NASA POWER"),
    ("c04_frost_free_days", "Frost-free days", "days", "NASA POWER"),
    ("c05_season_solar_mj_m2_day", "Solar radiation", "MJ/m²/day", "NASA POWER"),
    ("c06_aridity_index", "Aridity index (rain ÷ evaporative demand)", "", "NASA POWER"),
    ("c07_season_rain_cv", "Year-to-year rainfall variability", "CV", "NASA POWER"),
    ("c08_root_zone_wetness_0to1", "Root-zone soil wetness", "0–1", "NASA POWER (MERRA-2)"),
    ("c09_dry_years", "Dry seasons, 2015–2024", "", "NASA POWER"),
    ("c10_groundwater_percentile_latest", "Groundwater wetness now (0 driest – 100 wettest)",
     "percentile", "NASA GRACE-FO"),
    ("c10_groundwater_percentile_10yr_mean", "Groundwater wetness, 10-year average",
     "percentile", "NASA GRACE / GRACE-FO"),
    ("c11_slope_pct", "Slope", "%", "NASA SRTM"),
    ("c14_season_temp_change_2040_c", "Projected temperature change by 2040", "°C",
     "NASA NEX-GDDP-CMIP6"),
    ("c15_annual_rain_change_2040_pct", "Projected rainfall change by 2040", "%",
     "NASA NEX-GDDP-CMIP6"),
    ("c16_clay_pct", "Soil clay", "%", "ISRIC SoilGrids 250m"),
    ("c16_sand_pct", "Soil sand", "%", "ISRIC SoilGrids 250m"),
    ("c17_soil_organic_carbon_g_per_kg", "Soil organic carbon", "g/kg", "ISRIC SoilGrids 250m"),
    ("c18_soil_ph", "Soil pH", "", "ISRIC SoilGrids 250m"),
    ("c19_crop_sequence", "Crops grown here, last 5 years", "", "USDA Cropland Data Layer"),
]

PRIMARY_KEYS = {
    "c10_groundwater_percentile_latest",
    "c10_groundwater_percentile_10yr_mean",
    "c11_slope_pct",
    "c14_season_temp_change_2040_c",
    "c15_annual_rain_change_2040_pct",
    "c16_clay_pct",
    "c16_sand_pct",
    "c17_soil_organic_carbon_g_per_kg",
    "c18_soil_ph",
    "c19_crop_sequence",
}

EXTRA_SPECS = {
    "c01_season_rain_mm": (0, "mm"),
    "annual_rain_mm": (0, "mm"),
    "season_mean_temp_c": (1, "°C"),
    "c02_season_gdd_c": (0, "°C·days"),
    "c03_heat_days_per_season": (0, "days"),
    "c04_frost_free_days": (0, "days"),
    "c05_season_solar_mj_m2_day": (2, "MJ/m²/day"),
    "c06_aridity_index": (2, ""),
    "c07_season_rain_cv": (2, ""),
    "c08_root_zone_wetness_0to1": (2, "0–1"),
    "c09_dry_years": (0, ""),
}

# --------------------------------------------------------------------- styles
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
  --fs-bg: #0b0f17;
  --fs-850: #111827;
  --fs-800: #172033;
  --fs-750: #1e293b;
  --fs-700: #334155;
  --fs-brand: #10b981;
  --fs-brand-soft: #34d399;
  --fs-text: #e2e8f0;
  --fs-muted: #94a3b8;
}

html, body, .stApp, button, input, textarea, select {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif !important;
}

.stApp {
  color: var(--fs-text);
  background:
    radial-gradient(1100px 540px at 12% -8%, rgba(16, 185, 129, 0.09), transparent 62%),
    radial-gradient(900px 520px at 92% 4%, rgba(14, 116, 144, 0.07), transparent 60%),
    var(--fs-bg);
}

/* remove the Streamlit chrome so the dashboard owns the page */
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stAppFooter"],
[data-testid="stFooter"],
#MainMenu {
  display: none !important;
}

[data-testid="stAppViewBlockContainer"],
[data-testid="stMainBlockContainer"],
.block-container {
  max-width: 1360px;
  padding: 0 24px 40px;
}

::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: var(--fs-bg); }
::-webkit-scrollbar-thumb { background: var(--fs-700); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #475569; }

::selection { background: var(--fs-brand); color: #020617; }

[data-testid="stMarkdownContainer"] p { margin-bottom: 0; }
[data-testid="stVerticalBlock"] { gap: 0.85rem; }

/* ------------------------------------------------------------------ header */
.fs-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  margin: -14px calc(50% - 50vw) 24px;
  padding: 12px max(24px, calc(50vw - 656px));
  border-bottom: 1px solid var(--fs-750);
  background: rgba(17, 24, 39, 0.84);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}
.fs-header-inner {
  max-width: 1312px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.fs-brand { display: flex; align-items: center; gap: 14px; min-width: 0; }
.fs-logo {
  width: 42px; height: 42px; flex: 0 0 42px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 13px;
  color: #020617;
  background: linear-gradient(135deg, #34d399, #047857);
  box-shadow: 0 10px 26px rgba(16, 185, 129, 0.2);
  border: 1px solid rgba(110, 231, 183, 0.35);
}
.fs-brand-line { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.stApp .fs-brand-line h1 {
  margin: 0;
  font-size: 20px;
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #fff;
}
.fs-version {
  display: inline-flex; align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid rgba(16, 185, 129, 0.22);
  background: rgba(16, 185, 129, 0.1);
  color: #34d399;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
}
.stApp .fs-brand p {
  margin: 3px 0 0;
  color: var(--fs-muted);
  font-size: 11.5px;
  line-height: 1.35;
}
.fs-header-actions { display: flex; align-items: center; gap: 8px; flex: 0 0 auto; }
.fs-top-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 10px;
  border-radius: 9px;
  border: 1px solid var(--fs-700);
  background: var(--fs-800);
  color: #cbd5e1;
  font-size: 11.5px;
  font-weight: 600;
  text-decoration: none !important;
  transition: all 0.15s ease;
}
.fs-top-btn:hover { background: var(--fs-750); color: #fff; border-color: #475569; }
.fs-top-btn.fs-icon-only { padding: 7px; }
.fs-top-sep { width: 1px; height: 20px; background: var(--fs-700); margin: 0 2px; }

/* ------------------------------------------------------------------- cards */
.fs-card-gap { height: 0; }
.st-key-field-panel,
.st-key-map-card,
.st-key-criteria-card,
.st-key-recs-card {
  background: var(--fs-850);
  border: 1px solid rgba(51, 65, 85, 0.72);
  border-radius: 16px;
  box-shadow: 0 18px 46px rgba(0, 0, 0, 0.26);
}
.st-key-field-panel { padding: 20px; position: sticky; top: 118px; }
.st-key-map-card,
.st-key-criteria-card,
.st-key-recs-card { overflow: hidden; }
.st-key-recs-card { padding: 20px; }
.st-key-field-panel { gap: 0.72rem !important; }
.st-key-map-card,
.st-key-criteria-card { gap: 0 !important; }
.st-key-recs-card { gap: 0.9rem !important; }
.st-key-method-card { gap: 0 !important; }
.stHorizontalBlock > [data-testid="stColumn"]:nth-child(2) > [data-testid="stVerticalBlock"] {
  gap: 1.5rem;
}

/* -------------------------------------------------------------- left panel */
.fs-panel-head {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding-bottom: 11px;
  border-bottom: 1px solid rgba(30, 41, 59, 0.8);
  margin-bottom: 2px;
}
.fs-panel-title { display: flex; align-items: center; gap: 9px; }
.stApp .fs-panel-title h2 {
  margin: 0; color: #fff; font-size: 11px; line-height: 1.2;
  letter-spacing: 0.09em; text-transform: uppercase; font-weight: 700;
}
.fs-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: 0 0 auto; }
.fs-dot-green { background: #34d399; box-shadow: 0 0 10px rgba(52, 211, 153, 0.55); }
.fs-dot-amber { background: #fbbf24; box-shadow: 0 0 10px rgba(251, 191, 36, 0.4); }
.fs-dot-rose { background: #fb7185; box-shadow: 0 0 10px rgba(251, 113, 133, 0.4); }
.fs-dot-sky { background: #38bdf8; box-shadow: 0 0 10px rgba(56, 189, 248, 0.4); }
.fs-dot-slate { background: #94a3b8; }
.fs-code { color: var(--fs-muted); font: 500 10px 'JetBrains Mono', monospace; white-space: nowrap; }

.fs-section {
  padding-top: 13px;
  border-top: 1px solid rgba(30, 41, 59, 0.75);
}
.fs-section-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-bottom: 3px;
}
.fs-label { color: #e2e8f0; font-size: 12px; font-weight: 650; line-height: 1.3; }
.fs-link {
  display: inline-flex; align-items: center; gap: 4px;
  color: #34d399; font-size: 10.5px; font-weight: 500;
  text-decoration: none !important; white-space: nowrap;
}
.stApp .fs-hint { color: var(--fs-muted); font-size: 10.5px; line-height: 1.45; margin: 3px 0 9px; }

.fs-coord-head {
  display: flex; align-items: center; justify-content: space-between;
  color: var(--fs-muted); font-size: 10px; margin-bottom: 1px;
}
.fs-coord-head .fs-unit { color: #34d399; font-size: 10.5px; font-family: 'JetBrains Mono', monospace; }
.st-key-coord-lat,
.st-key-coord-lon {
  background: var(--fs-bg);
  border: 1px solid rgba(51, 65, 85, 0.8);
  border-radius: 11px;
  padding: 7px 10px 5px;
  transition: border-color 0.15s ease;
}
.st-key-coord-lat:focus-within,
.st-key-coord-lon:focus-within { border-color: var(--fs-brand); }
.st-key-coord-lat [data-testid="stNumberInput"],
.st-key-coord-lon [data-testid="stNumberInput"] { border: 0 !important; background: transparent !important; }
.st-key-coord-lat [data-testid="stNumberInput"] input,
.st-key-coord-lon [data-testid="stNumberInput"] input {
  color: #fff !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 13px !important;
  padding: 0 !important;
  min-height: 22px !important;
  background: transparent !important;
}
.st-key-coord-lat [data-testid="stNumberInput"] button,
.st-key-coord-lon [data-testid="stNumberInput"] button {
  color: #64748b !important;
  background: transparent !important;
  border: 0 !important;
  padding: 0 1px !important;
  min-height: 12px !important;
  height: 12px !important;
}
.st-key-coord-lat [data-testid="stNumberInput"] button svg,
.st-key-coord-lon [data-testid="stNumberInput"] button svg { width: 9px !important; height: 9px !important; }
.st-key-coord-lat [data-testid="stNumberInput"] button:hover,
.st-key-coord-lon [data-testid="stNumberInput"] button:hover { color: #fff !important; }

.fs-slider-wrap { padding: 1px 0 0; }
.fs-slider-label {
  display: flex; align-items: baseline; justify-content: space-between; gap: 8px;
  margin: 1px 0 -3px;
}
.fs-slider-label span:first-child {
  color: #cbd5e1; font-size: 11px; font-weight: 500; line-height: 1.35;
}
.fs-slider-value {
  color: #34d399;
  font: 700 11px 'JetBrains Mono', monospace;
}
.fs-slider-scale {
  display: flex; justify-content: space-between;
  color: #64748b; font: 400 9px 'JetBrains Mono', monospace;
  margin-top: -5px;
}
.stApp .fs-note {
  display: flex; align-items: flex-start; gap: 6px;
  color: rgba(251, 191, 36, 0.92);
  font-size: 10.5px;
  line-height: 1.45;
  margin-top: 7px;
}
.fs-note svg { flex: 0 0 auto; margin-top: 1px; }

/* Streamlit widgets inside the control panel */
.st-key-field-panel [data-testid="stMultiSelect"] div[role="group"] {
  background: var(--fs-bg) !important;
  border: 1px solid rgba(51, 65, 85, 0.8) !important;
  border-radius: 11px !important;
  min-height: 42px;
  transition: border-color 0.15s ease;
}
.st-key-field-panel [data-testid="stMultiSelect"] div[role="group"]:focus-within {
  border-color: var(--fs-brand) !important;
}
.st-key-field-panel [data-testid="stMultiSelect"] input {
  color: #fff !important;
  font-size: 11px !important;
}
.st-key-field-panel [data-testid="stMultiSelectTagsContainer"] span[data-tag] {
  background: rgba(244, 63, 94, 0.18) !important;
  border: 1px solid rgba(244, 63, 94, 0.3) !important;
  color: #fda4af !important;
  border-radius: 6px !important;
  font-size: 11px !important;
  min-height: 24px !important;
}
.st-key-field-panel [data-testid="stMultiSelectTagsContainer"] span[data-tag-index="1"] {
  background: rgba(245, 158, 11, 0.18) !important;
  border-color: rgba(245, 158, 11, 0.3) !important;
  color: #fcd34d !important;
}
.st-key-field-panel [data-testid="stMultiSelectTagsContainer"] span[data-tag-index="2"] {
  background: rgba(56, 189, 248, 0.18) !important;
  border-color: rgba(56, 189, 248, 0.3) !important;
  color: #7dd3fc !important;
}
.st-key-field-panel [data-testid="stMultiSelectTagsContainer"] span[data-tag] span {
  color: inherit !important;
  font-size: 11px !important;
}
.st-key-field-panel [data-testid="stMultiSelect"] button[aria-label="Clear all"] {
  background: transparent !important;
  color: #64748b !important;
  width: 20px !important;
  height: 20px !important;
  min-height: 20px !important;
}
.st-key-field-panel [data-testid="stMultiSelect"] button[aria-label="Clear all"]:hover { color: #fff !important; }

.st-key-field-panel [data-testid="stWidgetLabel"] p {
  color: #e2e8f0 !important;
  font-size: 12px !important;
  font-weight: 620 !important;
}
.st-key-field-panel [data-testid="stSlider"] [data-testid="stTickBar"],
.st-key-field-panel [data-testid="stSliderTickBar"],
.st-key-field-panel [data-testid="stSliderThumbValue"] { display: none !important; }
.st-key-field-panel [data-testid="stSlider"] [role="slider"] {
  background: var(--fs-brand) !important;
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.55);
  border: 2px solid var(--fs-bg) !important;
}
.st-key-field-panel [data-testid="stSlider"] [data-baseweb="slider"] > div > div {
  background: var(--fs-700) !important;
}
.st-key-field-panel [data-testid="stSlider"] [data-testid="stThumbValue"] {
  display: none !important;
}

.st-key-field-panel [data-testid="stCheckbox"] label {
  align-items: flex-start;
  gap: 8px;
}
.st-key-field-panel [data-testid="stCheckbox"] label p {
  color: #cbd5e1 !important;
  font-size: 11px !important;
  line-height: 1.35 !important;
}
.st-key-field-panel [data-testid="stCheckbox"] label > div:first-of-type {
  background: var(--fs-bg) !important;
  border: 1px solid var(--fs-700) !important;
  border-radius: 4px;
}
.st-key-field-panel [data-testid="stCheckbox"] label:has(input:checked) > div:first-of-type {
  background: var(--fs-brand) !important;
  border-color: var(--fs-brand) !important;
  color: #020617 !important;
}
.st-key-field-panel [data-testid="stNumberInput"] > div {
  background: var(--fs-bg) !important;
  border-color: var(--fs-700) !important;
  border-radius: 9px !important;
}
.st-key-field-panel [data-testid="stNumberInput"] input {
  color: #fff !important; font-size: 11px !important;
  font-family: 'JetBrains Mono', monospace !important;
}
.st-key-field-panel [data-testid="stNumberInputContainer"] > div:last-child {
  display: flex !important;
  flex-direction: column;
  justify-content: center;
  align-items: stretch;
  gap: 2px;
  width: 26px;
  height: 100%;
  padding: 3px 4px 3px 0;
}
.st-key-field-panel [data-testid="stNumberInput"] [data-testid="stNumberInputStepDown"],
.st-key-field-panel [data-testid="stNumberInput"] [data-testid="stNumberInputStepUp"] {
  width: 100% !important;
  height: 15px !important;
  min-height: 0 !important;
  padding: 0 !important;
  border: 1px solid var(--fs-700) !important;
  border-radius: 4px !important;
  background: rgba(30, 41, 59, 0.55) !important;
  color: #94a3b8 !important;
  transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
}
.st-key-field-panel [data-testid="stNumberInput"] [data-testid="stNumberInputStepDown"]:hover,
.st-key-field-panel [data-testid="stNumberInput"] [data-testid="stNumberInputStepUp"]:hover {
  border-color: var(--fs-brand) !important;
  background: var(--fs-brand) !important;
  color: #020617 !important;
}
.st-key-field-panel [data-testid="stNumberInput"] [data-testid="stNumberInputStepDown"] svg,
.st-key-field-panel [data-testid="stNumberInput"] [data-testid="stNumberInputStepUp"] svg {
  width: 9px !important;
  height: 9px !important;
}

.st-key-field-panel .stButton > button,
.st-key-field-panel [data-testid="stButton"] > button {
  width: 100%;
  border: 0;
  border-radius: 11px;
  padding: 11px 16px;
  background: linear-gradient(90deg, #10b981, #059669);
  color: #020617;
  font-size: 12.5px;
  font-weight: 750;
  box-shadow: 0 10px 24px rgba(5, 150, 105, 0.22);
  transition: all 0.15s ease;
}
.st-key-field-panel .stButton > button:hover,
.st-key-field-panel [data-testid="stButton"] > button:hover {
  background: linear-gradient(90deg, #34d399, #10b981);
  color: #020617;
  box-shadow: 0 12px 28px rgba(16, 185, 129, 0.28);
  transform: translateY(-1px);
}
.fs-model-line {
  color: var(--fs-muted);
  font: 400 10px 'JetBrains Mono', monospace;
  text-align: center;
  line-height: 1.4;
}

/* ---------------------------------------------------------------- map card */
.st-key-map-card [data-testid="stVerticalBlock"] { gap: 0 !important; }
.st-key-map-header {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(30, 41, 59, 0.8);
  background: var(--fs-850);
}
.st-key-map-header [data-testid="stVerticalBlock"] { gap: 0 !important; }
.fs-map-coords { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; min-width: 0; }
.fs-live {
  width: 8px; height: 8px; border-radius: 50%;
  background: #34d399; position: relative; flex: 0 0 auto;
}
.fs-live::after {
  content: ''; position: absolute; inset: -4px; border-radius: 50%;
  border: 1px solid rgba(52, 211, 153, 0.6);
  animation: fs-ping 2.2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
}
@keyframes fs-ping {
  0% { transform: scale(0.68); opacity: 0.9; }
  70%, 100% { transform: scale(1.8); opacity: 0; }
}
.fs-map-title {
  color: #fff; font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.07em; text-transform: uppercase; white-space: nowrap;
}
.fs-coord-chip {
  display: inline-flex; align-items: center;
  padding: 2px 8px;
  border-radius: 5px;
  border: 1px solid var(--fs-750);
  background: var(--fs-bg);
  color: #34d399;
  font: 500 10.5px 'JetBrains Mono', monospace;
  white-space: nowrap;
}

.st-key-map-header [data-testid="stRadio"] [role="radiogroup"] {
  display: flex; flex-wrap: nowrap; align-items: center; gap: 1px;
  padding: 2px;
  border-radius: 8px;
  border: 1px solid var(--fs-750);
  background: var(--fs-bg);
  width: fit-content;
  margin-left: auto;
  min-height: 0 !important;
  height: auto !important;
}
.st-key-map-header [data-testid="stRadioOption"],
.st-key-map-header [data-testid="stRadioOption"] > div {
  min-height: 0 !important;
  height: auto !important;
}
.st-key-map-header [data-testid="stRadioOption"] {
  margin: 0 !important;
  padding: 3px 8px !important;
  border-radius: 6px;
  color: var(--fs-muted) !important;
  transition: all 0.15s ease;
  cursor: pointer;
}
.st-key-map-header [data-testid="stRadioOption"]:hover { color: #fff !important; }
.st-key-map-header [data-testid="stRadioOption"][data-selected="true"] {
  background: var(--fs-brand);
  color: #020617 !important;
}
.st-key-map-header [data-testid="stRadioOption"] > div > div:first-child { display: none !important; }
.st-key-map-header [data-testid="stRadioOption"] p {
  margin: 0 !important;
  color: inherit !important;
  font-size: 10px !important;
  line-height: 1.2 !important;
  white-space: nowrap;
}
.st-key-map-header [data-testid="stRadioOption"][data-selected="true"] p { font-weight: 700; }

.st-key-map-card { position: relative; }
.st-key-map-card iframe {
  display: block;
  border: 0;
  border-radius: 0;
  margin-top: -1px;
}
.st-key-map-card > div[data-testid="stElementContainer"]:last-child {
  position: absolute;
  left: 12px;
  bottom: 36px;
  z-index: 600;
  width: auto;
  height: auto;
  pointer-events: none;
}
.fs-map-legend {
  display: flex; align-items: center; gap: 7px;
  width: fit-content;
  padding: 5px 9px;
  border: 1px solid rgba(51, 65, 85, 0.7);
  border-radius: 7px;
  background: rgba(11, 15, 23, 0.86);
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.32);
  color: #cbd5e1;
  font-size: 10px;
  white-space: nowrap;
}
.fs-map-legend strong { color: #fff; }
.fs-map-legend .fs-dot { width: 8px; height: 8px; }

/* ----------------------------------------------------------- criteria card */
.st-key-criteria-head { padding: 16px 18px 12px; border-bottom: 1px solid rgba(30, 41, 59, 0.8); }
.st-key-criteria-head [data-testid="stVerticalBlock"] { gap: 0 !important; }
.fs-card-title-row { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.stApp .fs-card-title { margin: 0; color: #fff; font-size: 15px; font-weight: 750; letter-spacing: -0.015em; }
.fs-source-pill {
  display: inline-flex; align-items: center;
  padding: 2px 8px;
  border-radius: 5px;
  border: 1px solid rgba(59, 130, 246, 0.2);
  background: rgba(59, 130, 246, 0.1);
  color: #60a5fa;
  font-size: 10px; font-weight: 650;
}
.stApp .fs-card-sub { color: var(--fs-muted); font-size: 10.5px; line-height: 1.45; margin: 4px 0 0; }
.st-key-criteria-head .stButton > button,
.st-key-criteria-head [data-testid="stButton"] > button {
  border: 0; background: transparent !important; color: #34d399 !important;
  box-shadow: none !important; padding: 2px 0 !important;
  font-size: 11px !important; font-weight: 600 !important;
  white-space: nowrap;
}
.st-key-criteria-head .stButton > button:hover,
.st-key-criteria-head [data-testid="stButton"] > button:hover { color: #6ee7b7 !important; }

.fs-table-wrap { overflow-x: auto; }
.fs-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.fs-table thead th {
  padding: 9px 15px;
  background: rgba(11, 15, 23, 0.62);
  border-bottom: 1px solid var(--fs-750);
  color: var(--fs-muted);
  font: 500 9.5px 'JetBrains Mono', monospace;
  letter-spacing: 0.055em;
  text-transform: uppercase;
  text-align: left;
  white-space: nowrap;
}
.fs-table tbody td {
  padding: 9px 15px;
  border-bottom: 1px solid rgba(30, 41, 59, 0.62);
  vertical-align: middle;
}
.fs-table tbody tr:last-child td { border-bottom: 0; }
.fs-table tbody tr:hover { background: rgba(23, 32, 51, 0.45); }
.fs-name { color: #e2e8f0; font-weight: 550; line-height: 1.35; }
.fs-name .fs-dot { margin-right: 6px; }
.fs-sub { color: var(--fs-muted); font-weight: 400; }
.fs-val {
  color: #f1f5f9;
  font: 600 11px 'JetBrains Mono', monospace;
  white-space: nowrap;
}
.fs-unit { color: var(--fs-muted); font-weight: 400; font-size: 10px; }
.fs-src { color: var(--fs-muted); font: 400 9.5px 'JetBrains Mono', monospace; white-space: nowrap; }
.fs-src-inline { display: none; margin-top: 2px; color: var(--fs-muted); font: 400 9px 'JetBrains Mono', monospace; }
.fs-missing { color: #fda4af; font-family: 'JetBrains Mono', monospace; }
.fs-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.fs-tag {
  display: inline-flex; align-items: center;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--fs-700);
  background: var(--fs-bg);
  color: #cbd5e1;
  font: 400 9.5px 'JetBrains Mono', monospace;
  white-space: nowrap;
}
.fs-badge {
  display: inline-flex; align-items: center;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 9.5px;
  font-weight: 600;
  white-space: nowrap;
}
.fs-badge-green { background: rgba(16, 185, 129, 0.1); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.2); }
.fs-badge-amber { background: rgba(245, 158, 11, 0.1); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.2); }
.fs-badge-rose { background: rgba(244, 63, 94, 0.1); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.2); }
.fs-badge-sky { background: rgba(56, 189, 248, 0.1); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.2); }
.fs-badge-slate { background: rgba(51, 65, 85, 0.6); color: #cbd5e1; border: 1px solid rgba(71, 85, 105, 0.45); }

.fs-problem {
  display: flex; gap: 8px; align-items: flex-start;
  margin: 10px 15px 0;
  padding: 9px 11px;
  border-radius: 8px;
  border: 1px solid rgba(245, 158, 11, 0.2);
  background: rgba(245, 158, 11, 0.07);
  color: #fcd34d;
  font-size: 10.5px;
  line-height: 1.45;
}
.fs-problem strong { color: #fde68a; }
.fs-problem-red { border-color: rgba(244, 63, 94, 0.25); background: rgba(244, 63, 94, 0.07); color: #fda4af; }

.st-key-criteria-card [data-testid="stExpander"] {
  margin: 0 15px 15px;
  border: 1px solid rgba(51, 65, 85, 0.75);
  border-radius: 9px;
  background: var(--fs-bg);
}
.st-key-criteria-card [data-testid="stExpander"] summary {
  padding: 8px 11px;
  color: #cbd5e1;
  font-size: 11px;
}
.st-key-criteria-card [data-testid="stExpander"] summary:hover { color: #fff; background: var(--fs-800); }

/* --------------------------------------------------------- recommendations */
.fs-recs-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 12px; flex-wrap: wrap;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--fs-750);
  margin-bottom: 2px;
}
.fs-recs-title-row { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.stApp .fs-recs-title { margin: 0; color: #fff; font-size: 15px; font-weight: 750; letter-spacing: -0.015em; }
.fs-ranked-pill {
  display: inline-flex; align-items: center;
  padding: 2px 8px; border-radius: 5px;
  border: 1px solid rgba(16, 185, 129, 0.2);
  background: rgba(16, 185, 129, 0.1);
  color: #34d399;
  font-size: 10px; font-weight: 550;
}
.stApp .fs-recs-sub { color: var(--fs-muted); font-size: 10.5px; line-height: 1.45; margin: 4px 0 0; max-width: 660px; }
.fs-count { color: var(--fs-muted); font: 400 10px 'JetBrains Mono', monospace; white-space: nowrap; padding-top: 4px; }

.fs-baseline {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 10px 13px;
  border-radius: 10px;
  border: 1px solid rgba(51, 65, 85, 0.75);
  background: var(--fs-bg);
  flex-wrap: wrap;
}
.fs-baseline-main { display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; }
.fs-baseline-label { color: var(--fs-muted); font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 650; }
.fs-baseline-main strong { color: #fff; font-size: 13px; }
.fs-baseline-metrics { display: flex; gap: 13px; flex-wrap: wrap; color: var(--fs-muted); font-size: 10px; }
.fs-baseline-metrics b { color: #e2e8f0; font-family: 'JetBrains Mono', monospace; font-weight: 600; }

.fs-rec-card {
  position: relative;
  display: flex; flex-direction: column;
  min-height: 312px;
  height: 100%;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid rgba(51, 65, 85, 0.82);
  background: var(--fs-bg);
  overflow: hidden;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.fs-rec-card:hover { border-color: #64748b; }
.fs-rec-card.top {
  border-color: rgba(16, 185, 129, 0.42);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22), inset 0 0 60px rgba(16, 185, 129, 0.025);
}
.fs-rank {
  position: absolute; top: 0; right: 0;
  padding: 3px 9px 4px;
  border-bottom-left-radius: 8px;
  background: var(--fs-brand);
  color: #020617;
  font: 700 9px 'JetBrains Mono', monospace;
  letter-spacing: 0.045em;
  text-transform: uppercase;
}
.fs-rec-label { color: var(--fs-muted); font-size: 9.5px; font-weight: 650; letter-spacing: 0.08em; text-transform: uppercase; }
.stApp .fs-rec-title {
  margin: 3px 0 0;
  color: #fff;
  font-size: 15px;
  line-height: 1.28;
  font-weight: 750;
  letter-spacing: -0.01em;
}
.fs-arrow { color: #34d399; padding: 0 1px; }
.fs-score-row { display: flex; align-items: baseline; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.fs-big { color: #34d399; font: 800 28px 'JetBrains Mono', monospace; line-height: 1; letter-spacing: -0.05em; }
.fs-rec-card:not(.top) .fs-big { color: #a7f3d0; }
.fs-score-label { color: #cbd5e1; font-size: 10.5px; font-weight: 500; }
.fs-delta { font: 500 9.5px 'JetBrains Mono', monospace; padding: 1px 5px; border-radius: 4px; }
.fs-delta.up { color: #34d399; background: rgba(16, 185, 129, 0.1); }
.fs-delta.down { color: #fb7185; background: rgba(244, 63, 94, 0.1); }
.fs-delta.flat { color: var(--fs-muted); background: rgba(51, 65, 85, 0.5); }

.fs-metrics {
  margin-top: 11px;
  padding-top: 9px;
  border-top: 1px solid var(--fs-750);
  display: grid;
  gap: 4px;
}
.fs-metric-row { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; color: #cbd5e1; font-size: 10.5px; }
.fs-metric-row strong { color: #e2e8f0; font: 600 10.5px 'JetBrains Mono', monospace; }
.fs-metric-row .fs-good { color: #34d399; }
.fs-metric-row .fs-warn { color: #fbbf24; }
.stApp .fs-rec-why {
  margin: 10px 0 0;
  color: var(--fs-muted);
  font-size: 10.5px;
  line-height: 1.55;
}
.fs-rec-why strong { color: #cbd5e1; font-weight: 600; }

/* five ranked cards share one row set that reflows with the viewport */
.st-key-recs-card > div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] {
  flex-wrap: wrap !important;
  align-items: stretch !important;
  gap: 14px !important;
}
.st-key-recs-card > div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
  flex: 0 1 calc(33.333% - 9.34px) !important;
  width: auto !important;
  min-width: 0 !important;
}

/* per-card expander reads as the card's action row */
.st-key-recs-card > div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] [data-testid="stExpander"] {
  margin-top: 4px;
  border-radius: 9px;
  border: 1px solid rgba(51, 65, 85, 0.8);
  background: var(--fs-bg);
  overflow: hidden;
}
.st-key-recs-card [data-testid="stExpander"] summary {
  padding: 7px 11px;
  color: #cbd5e1;
  font-size: 10.5px;
  font-weight: 650;
}
.st-key-recs-card [data-testid="stExpander"] summary:hover { color: #fff; background: var(--fs-800); }
.st-key-recs-card [data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding: 0 11px 10px; }

.fs-checks { display: flex; flex-wrap: wrap; gap: 4px; margin: 2px 0 9px; }
.fs-check {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 6px; border-radius: 4px;
  font-size: 9.5px;
  background: rgba(16, 185, 129, 0.09);
  border: 1px solid rgba(16, 185, 129, 0.18);
  color: #6ee7b7;
}
.fs-check.no { background: rgba(51, 65, 85, 0.45); border-color: rgba(71, 85, 105, 0.4); color: #94a3b8; }
.fs-detail-table { width: 100%; border-collapse: collapse; font-size: 9.5px; }
.fs-detail-table th {
  padding: 4px 5px; text-align: left; color: var(--fs-muted);
  font: 500 8.5px 'JetBrains Mono', monospace; text-transform: uppercase;
  border-bottom: 1px solid var(--fs-750); white-space: nowrap;
}
.fs-detail-table td { padding: 4px 5px; border-bottom: 1px solid rgba(30, 41, 59, 0.6); color: #cbd5e1; }
.fs-detail-table td:first-child { color: #fff; font-weight: 550; }
.fs-detail-table td.num { font-family: 'JetBrains Mono', monospace; }
.fs-crop-note { margin-top: 5px; color: var(--fs-muted); font-size: 9px; line-height: 1.4; }
.fs-crop-note strong { color: #cbd5e1; }

.fs-info {
  padding: 12px 13px;
  border-radius: 9px;
  border: 1px solid rgba(245, 158, 11, 0.2);
  background: rgba(245, 158, 11, 0.07);
  color: #fcd34d;
  font-size: 11px;
  line-height: 1.5;
}

/* --------------------------------------------------------------- footer */
.st-key-method-card [data-testid="stExpander"] {
  border: 1px solid rgba(51, 65, 85, 0.72);
  border-radius: 12px;
  background: var(--fs-850);
}
.st-key-method-card [data-testid="stExpander"] summary {
  padding: 11px 14px;
  color: #cbd5e1;
  font-size: 11.5px;
  font-weight: 600;
}
.st-key-method-card [data-testid="stExpander"] summary:hover { color: #fff; }
.st-key-method-card [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
  padding: 0 14px 12px;
  color: var(--fs-muted);
  font-size: 11px;
  line-height: 1.6;
}
.st-key-method-card [data-testid="stExpanderDetails"] p,
.st-key-method-card [data-testid="stExpanderDetails"] li {
  color: var(--fs-muted) !important;
  font-size: 11px !important;
  line-height: 1.6 !important;
}
.st-key-method-card li { margin-bottom: 3px; color: var(--fs-muted); font-size: 11px; }
.st-key-method-card strong { color: #cbd5e1; }

.fs-footer {
  margin: 28px calc(50% - 50vw) -40px;
  padding: 17px max(24px, calc(50vw - 656px));
  border-top: 1px solid rgba(30, 41, 59, 0.8);
  background: var(--fs-850);
  text-align: center;
}
.fs-footer-inner {
  max-width: 1312px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; flex-wrap: wrap;
  color: var(--fs-muted); font-size: 10px;
}
.fs-footer-left { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.fs-footer-left strong { color: #cbd5e1; font-weight: 600; }
.fs-footer-links { display: flex; align-items: center; gap: 15px; flex-wrap: wrap; }
.fs-footer-links a { color: var(--fs-muted); text-decoration: none !important; transition: color 0.15s ease; }
.fs-footer-links a:hover { color: #34d399; }

@media (max-width: 1279px) {
  .st-key-recs-card > div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex-basis: calc(50% - 7px) !important;
  }
}

@media (max-width: 991px) {
  .fs-header { position: static; }
  .st-key-field-panel { position: static; }
  .fs-brand p { display: none; }
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-field-panel) {
    flex-direction: column !important;
    gap: 1.25rem !important;
  }
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-field-panel) > [data-testid="stColumn"] {
    flex: 1 1 100% !important;
    width: 100% !important;
    min-width: 0 !important;
  }
}

@media (max-width: 640px) {
  [data-testid="stAppViewBlockContainer"],
  [data-testid="stMainBlockContainer"],
  .block-container { padding-left: 12px; padding-right: 12px; }
  .fs-header { padding-left: 12px; padding-right: 12px; }
  .fs-footer { padding-left: 12px; padding-right: 12px; }
  .fs-header-actions .fs-top-btn span { display: none; }
  .st-key-map-card > div[data-testid="stElementContainer"]:last-child { bottom: 54px; }
  .st-key-recs-card > div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex-basis: 100% !important;
  }

  /* keep the four-column criteria table readable instead of clipped */
  .fs-table-wrap { overflow-x: auto; }
  .fs-table { min-width: 0; font-size: 10px; }
  .fs-table thead th {
    padding: 7px 6px;
    font-size: 8px;
    letter-spacing: 0.03em;
    white-space: normal;
  }
  .fs-table tbody td { padding: 8px 6px; }
  .fs-table thead th:last-child,
  .fs-table tbody td:last-child { display: none; }
  .fs-src-inline { display: block; }
  .fs-name { font-size: 10px; }
  .fs-name .fs-dot { margin-right: 4px; }
  .fs-val { font-size: 10px; white-space: normal; }
  .fs-unit { font-size: 9px; }
  .fs-badge { font-size: 8.5px; padding: 2px 5px; white-space: normal; line-height: 1.25; }
  .fs-tag { font-size: 9px; }
  .fs-table th:nth-child(2), .fs-table td:nth-child(2) { width: 68px; }
  .fs-table th:nth-child(3), .fs-table td:nth-child(3) { width: 86px; }
}
</style>
"""

ICON_GLOBE = """<svg width="21" height="21" viewBox="0 0 24 24" fill="none"
stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-.778.099-1.533.284-2.253"/></svg>"""
ICON_FORK = """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2"/></svg>"""
ICON_GITHUB = """<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/></svg>"""
ICON_INFO = """<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/></svg>"""
ICON_PIN = """<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>"""
ICON_ALERT = """<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>"""
ICON_BOLT = "⚡"


# --------------------------------------------------------------------- helpers
def esc(value) -> str:
    return html.escape(str(value), quote=True)


def fmt_num(value, digits: int = 1) -> str:
    if value is None:
        return '<span class="fs-missing">missing</span>'
    if isinstance(value, bool):
        return "yes" if value else "no"
    try:
        return f"{float(value):,.{digits}f}" if digits else f"{round(float(value)):,}"
    except (TypeError, ValueError):
        return esc(value)


def value_html(value, digits: int = 1, unit: str = "") -> str:
    out = fmt_num(value, digits)
    if unit and value is not None:
        out += f' <span class="fs-unit">{esc(unit)}</span>'
    return out


def badge(text: str, tone: str) -> str:
    return f'<span class="fs-badge fs-badge-{tone}">{esc(text)}</span>'


def dot(tone: str = "green") -> str:
    return f'<span class="fs-dot fs-dot-{tone}"></span>'


def ordinal_percentile(value) -> str:
    if value is None:
        return "missing"
    n = float(value)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(int(n) % 10, "th")
    return f"{n:.1f}{suffix} percentile"


def groundwater_now_status(value):
    if value is None:
        return "Missing", "slate", "slate"
    if value < 10:
        return "Severe Deficit", "rose", "rose"
    if value < 30:
        return "Deficit / Dry", "amber", "amber"
    if value <= 65:
        return "Normal Baseline", "green", "green"
    if value <= 80:
        return "Above Normal", "sky", "sky"
    return "Very Wet", "sky", "sky"


def groundwater_mean_status(value):
    if value is None:
        return "Missing", "slate", "slate"
    if value < 25:
        return "Below Normal", "amber", "amber"
    if value <= 75:
        return "Normal Baseline", "green", "green"
    return "Above Normal", "sky", "sky"


def slope_status(value):
    if value is None:
        return "Missing", "slate", "slate"
    if value < 2:
        return "Minimal Runoff Risk", "slate", "slate"
    if value <= 5:
        return "Moderate Slope", "amber", "amber"
    return "Erosion Risk", "rose", "rose"


def temp_change_status(value):
    if value is None:
        return "Missing", "slate", "slate"
    if value < 0:
        return "Cooling Trend", "sky", "sky"
    if value < 0.3:
        return "Stable", "slate", "slate"
    if value < 1.0:
        return "Warming Trend", "rose", "rose"
    return "Strong Warming", "rose", "rose"


def rain_change_status(value):
    if value is None:
        return "Missing", "slate", "slate"
    if value > 2:
        return "Wetter Trend", "green", "green"
    if value > -2:
        return "Near Normal", "slate", "slate"
    if value > -5:
        return "Slight Decrease", "amber", "amber"
    return "Drying Trend", "rose", "rose"


def clay_status(clay, sand):
    if clay is None:
        return "Missing", "slate", "slate"
    texture = texture_class(clay, sand)
    label = {"heavy": "Heavy texture", "light": "Light texture",
             "medium": "Medium texture"}.get(texture, "Texture unknown")
    return label, "slate", "slate"


def sand_status(value):
    if value is None:
        return "Missing", "slate", "slate"
    if value > 65:
        return "Fast drainage", "amber", "amber"
    if value >= 35:
        return "Balanced drainage", "slate", "slate"
    return "Slow drainage", "amber", "amber"


def soc_status(value):
    if value is None:
        return "Missing", "slate", "slate"
    if value < 10:
        return "Depleted / Needs Carbon", "amber", "amber"
    if value < 20:
        return "Moderate Carbon", "slate", "slate"
    return "Carbon-rich", "green", "green"


def ph_status(value):
    if value is None:
        return "Missing", "slate", "slate"
    if 5.5 <= value <= 7.5:
        return "Optimal Range", "green", "green"
    if 5.0 <= value <= 8.0:
        return "Acceptable", "amber", "amber"
    return "Out of Range", "rose", "rose"


def extra_status(key: str, value):
    if value is None:
        return "Missing", "slate"
    if key == "c03_heat_days_per_season":
        if value > 45:
            return "Heat Stress", "rose"
        if value > 25:
            return "Warm Season", "amber"
        return "Measured", "slate"
    if key == "c04_frost_free_days":
        if value >= 180:
            return "Long Season", "green"
        if value >= 120:
            return "Adequate Season", "slate"
        return "Short Season", "amber"
    if key == "c06_aridity_index":
        if value < 0.05:
            return "Hyper-arid", "rose"
        if value < 0.2:
            return "Arid", "rose"
        if value < 0.5:
            return "Semi-arid", "amber"
        if value < 0.65:
            return "Dry sub-humid", "amber"
        return "Humid / Sub-humid", "green"
    if key == "c07_season_rain_cv":
        if value < 0.2:
            return "Stable Rainfall", "green"
        if value < 0.3:
            return "Variable Rainfall", "amber"
        return "Highly Variable", "rose"
    if key == "c08_root_zone_wetness_0to1":
        if value < 0.3:
            return "Dry Root Zone", "amber"
        if value <= 0.6:
            return "Moderate Moisture", "slate"
        return "Wet Root Zone", "green"
    if key == "c09_dry_years":
        n = len(value) if isinstance(value, (list, tuple)) else 0
        return (f"{n} dry season{'s' if n != 1 else ''}", "amber" if n >= 3 else "slate")
    return "Measured", "slate"


def table_row(label, value, status, tone, source, *, note="", dot_tone=None) -> str:
    dot_html = dot(dot_tone) if dot_tone else ""
    note_html = f' <span class="fs-sub">{esc(note)}</span>' if note else ""
    return (
        f'<tr><td class="fs-name">{dot_html}{esc(label)}{note_html}'
        f'<span class="fs-src-inline">{esc(source)}</span></td>'
        f'<td class="fs-val">{value}</td>'
        f"<td>{badge(status, tone)}</td>"
        f'<td class="fs-src">{esc(source)}</td></tr>'
    )


def primary_criteria_html(fp: dict) -> str:
    c = fp["criteria"]
    rows: list[str] = []

    gw = c.get("c10_groundwater_percentile_latest")
    status, tone, dot_tone = groundwater_now_status(gw)
    rows.append(table_row(
        "Groundwater wetness now",
        fmt_num(gw, 1) + (f' <span class="fs-unit">percentile</span>' if gw is not None else ""),
        status, tone, "NASA GRACE-FO", note="(0 driest – 100 wettest)", dot_tone=dot_tone))

    gw10 = c.get("c10_groundwater_percentile_10yr_mean")
    status, tone, dot_tone = groundwater_mean_status(gw10)
    rows.append(table_row(
        "Groundwater wetness, 10-year average",
        fmt_num(gw10, 1) + (f' <span class="fs-unit">percentile</span>' if gw10 is not None else ""),
        status, tone, "NASA GRACE / GRACE-FO", dot_tone=dot_tone))

    slope = c.get("c11_slope_pct")
    status, tone, dot_tone = slope_status(slope)
    rows.append(table_row("Slope", value_html(slope, 1, "%"), status, tone, "NASA SRTM",
                          dot_tone=dot_tone))

    dt = c.get("c14_season_temp_change_2040_c")
    status, tone, dot_tone = temp_change_status(dt)
    rows.append(table_row("Projected temperature change by 2040",
                          value_html(dt, 2, "°C"), status, tone, "NASA NEX-GDDP-CMIP6",
                          dot_tone=dot_tone))

    dr = c.get("c15_annual_rain_change_2040_pct")
    status, tone, dot_tone = rain_change_status(dr)
    rows.append(table_row("Projected rainfall change by 2040",
                          value_html(dr, 1, "%"), status, tone, "NASA NEX-GDDP-CMIP6",
                          dot_tone=dot_tone))

    clay, sand = c.get("c16_clay_pct"), c.get("c16_sand_pct")
    status, tone, dot_tone = clay_status(clay, sand)
    rows.append(table_row("Soil clay", value_html(clay, 1, "%"), status, tone,
                          "ISRIC SoilGrids 250m", dot_tone=dot_tone))

    status, tone, dot_tone = sand_status(sand)
    rows.append(table_row("Soil sand", value_html(sand, 1, "%"), status, tone,
                          "ISRIC SoilGrids 250m", dot_tone=dot_tone))

    soc = c.get("c17_soil_organic_carbon_g_per_kg")
    status, tone, dot_tone = soc_status(soc)
    rows.append(table_row("Soil organic carbon (SOC)", value_html(soc, 1, "g/kg"), status, tone,
                          "ISRIC SoilGrids 250m", dot_tone=dot_tone))

    ph = c.get("c18_soil_ph")
    status, tone, dot_tone = ph_status(ph)
    rows.append(table_row("Soil pH in H₂O", value_html(ph, 1, ""), status, tone,
                          "ISRIC SoilGrids 250m", dot_tone=dot_tone))

    seq = c.get("c19_crop_sequence") or {}
    if seq:
        tags = "".join(
            f'<span class="fs-tag">{esc(year)}: {esc(name)}</span>'
            for year, name in sorted(seq.items(), reverse=True))
    else:
        tags = '<span class="fs-missing">No field crop registered at this pixel</span>'
    rows.append(
        '<tr><td class="fs-name">Crops grown here, last 5 years'
        '<span class="fs-src-inline">USDA Cropland Data Layer</span></td>'
        f'<td class="fs-val" colspan="2"><div class="fs-tags">{tags}</div></td>'
        '<td class="fs-src">USDA Cropland Data Layer</td></tr>')

    return "".join(rows)


def extra_criteria_html(fp: dict) -> str:
    c = fp["criteria"]
    rows = []
    for key, label, unit, source in CRITERIA:
        if key in PRIMARY_KEYS:
            continue
        value = c.get(key)
        digits, display_unit = EXTRA_SPECS.get(key, (1, unit))
        if key == "c09_dry_years":
            years = value or []
            value_html_str = esc(", ".join(str(y) for y in years)) if years else "none"
        else:
            value_html_str = value_html(value, digits, display_unit)
        status, tone = extra_status(key, value)
        rows.append(table_row(label, value_html_str, status, tone, source))
    return "".join(rows)


def criteria_summary(fp: dict) -> str:
    c = fp["criteria"]
    bits = []
    gw = c.get("c10_groundwater_percentile_latest")
    if gw is not None:
        bits.append(f"groundwater wetness at the {float(gw):.1f} percentile")
    texture = texture_class(c.get("c16_clay_pct"), c.get("c16_sand_pct"))
    if texture:
        bits.append(f"{texture}-textured soil")
    soc = c.get("c17_soil_organic_carbon_g_per_kg")
    if soc is not None:
        bits.append(f"organic carbon at {float(soc):.1f} g/kg")
    dt = c.get("c14_season_temp_change_2040_c")
    dr = c.get("c15_annual_rain_change_2040_pct")
    if dt is not None and dr is not None:
        bits.append(f"a projected 2040 shift of {dt:+.2f} °C and {dr:+.1f}% rain")
    if not bits:
        return "Ranked from the criteria measured for this field and the priorities you set."
    return "Calculated by aligning " + ", ".join(bits) + "."


def arrow_join(items) -> str:
    return ' <span class="fs-arrow">➔</span> '.join(esc(x) for x in items)


def pct(value) -> str:
    return f"{value * 100:.0f}%"


def delta_html(value, baseline_value, suffix: str = "vs now") -> str:
    if baseline_value is None:
        return ""
    diff = value - baseline_value
    if abs(diff) < 0.005:
        return '<span class="fs-delta flat">same as now</span>'
    tone = "up" if diff > 0 else "down"
    return f'<span class="fs-delta {tone}">{diff:+.2f} {esc(suffix)}</span>'


def why_text(r: dict) -> str:
    checks = r["soil_checks"]
    met = [k for k, v in checks.items() if v]
    unmet = [k for k, v in checks.items() if not v]
    if met and unmet:
        soil = (f"<strong>Meets {len(met)} of 4 soil-health checks</strong> "
                f"({esc('; '.join(met))}). Not met: {esc(', '.join(unmet))}.")
    elif met:
        soil = "<strong>Meets all 4 soil-health checks.</strong>"
    else:
        soil = "No soil-health checks are met."

    if r.get("fit_2040") is not None:
        climate = (f"Climate fit averages <strong>{r['fit_today']:.2f}</strong> today and "
                   f"<strong>{r['fit_2040']:.2f}</strong> under the projected 2040 climate.")
    else:
        climate = f"Climate fit averages <strong>{r['fit_today']:.2f}</strong> today."
    water = (f"Average optimal-minimum rainfall is "
             f"<strong>{r['mean_optimal_min_rain_mm']:.0f} mm</strong>.")
    return f"{soil} {climate} {water}"


def rec_card_html(r: dict, index: int, baseline: dict | None) -> str:
    top = index == 0
    labels = ["Recommended Cycle", "Alternative Option", "Additional Option",
              "Further Option", "Further Option"]
    label = labels[min(index, len(labels) - 1)]
    rank = '<div class="fs-rank">#1 Ranked</div>' if top else ""

    if baseline:
        score_delta = delta_html(r["score"], baseline["score"])
    else:
        score_delta = '<span class="fs-delta flat">weighted score</span>'

    fit_value = pct(r["fit"])
    if baseline:
        fit_value += " " + delta_html(r["fit"], baseline["fit"], suffix="")

    soil_checks = sum(1 for v in r["soil_checks"].values() if v)
    soil_value = f"{soil_checks}/4 checks"
    if r["soil_health"] >= 0.999:
        soil_tone = "fs-good"
    elif r["soil_health"] >= 0.5:
        soil_tone = "fs-warn"
    else:
        soil_tone = ""

    water_value = f"{r['water_saving'] * 100:.0f}/100"

    future_row = ""
    if r.get("fit_2040") is not None:
        future_row = (
            '<div class="fs-metric-row"><span>2040 climate fit</span>'
            f'<strong>{pct(r["fit_2040"])}</strong></div>')

    return f"""
<article class="fs-rec-card {'top' if top else ''}">
  {rank}
  <div>
    <div class="fs-rec-label">{label}</div>
    <h4 class="fs-rec-title">{arrow_join(r['rotation'])}</h4>
    <div class="fs-score-row">
      <span class="fs-big">{pct(r['score'])}</span>
      <span class="fs-score-label">Weighted rotation score</span>
    </div>
    <div style="margin-top:4px;">{score_delta}</div>
    <div class="fs-metrics">
      <div class="fs-metric-row"><span>Climate fit</span><strong>{fit_value}</strong></div>
      <div class="fs-metric-row"><span>Soil health</span><strong class="{soil_tone}">{soil_value}</strong></div>
      <div class="fs-metric-row"><span>Water saving</span><strong>{water_value}</strong></div>
      {future_row}
    </div>
    <p class="fs-rec-why">{why_text(r)}</p>
  </div>
</article>
"""


def crop_details_html(r: dict) -> str:
    checks = r["soil_checks"]
    check_tags = "".join(
        f'<span class="fs-check{" no" if not ok else ""}">{"✓" if ok else "×"} {esc(name)}</span>'
        for name, ok in checks.items())
    has_future = any(c.get("fit_2040") is not None for c in r["crops"].values())
    future_head = "<th>2040</th>" if has_future else ""
    rows = []
    notes = []
    for name, c in r["crops"].items():
        future_cell = f'<td class="num">{c["fit_2040"]:.2f}</td>' if has_future and c.get("fit_2040") is not None else ("<td>—</td>" if has_future else "")
        rows.append(
            f"<tr><td>{esc(name)}</td>"
            f'<td class="num">{c["fit"]:.2f}</td>'
            f'<td class="num">{c["dry_year_fit"]:.2f}</td>'
            f"{future_cell}"
            f"<td>{esc(c['limiting_factor'] or '—')}</td></tr>")
        if c["notes"]:
            notes.append(f'<div class="fs-crop-note"><strong>{esc(name)}:</strong> '
                         f'{esc("; ".join(c["notes"]))}</div>')
    return f"""
<div class="fs-checks">{check_tags}</div>
<div class="fs-table-wrap">
<table class="fs-detail-table">
  <thead><tr><th>Crop</th><th>Fit</th><th>Dry year</th>{future_head}<th>Limited by</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>
</div>
{''.join(notes)}
"""


def field_code(lat: float, lon: float) -> str:
    return f"GRID {abs(lat):.2f}{'N' if lat >= 0 else 'S'} {abs(lon):.2f}{'E' if lon >= 0 else 'W'}"


def coord_text(lat: float, lon: float) -> str:
    return f"{abs(lat):.3f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.3f}° {'E' if lon >= 0 else 'W'}"


# ---------------------------------------------------------------------- data
@st.cache_data(show_spinner=False, ttl=24 * 3600)
def site_data(lat: float, lon: float) -> dict:
    """One NASA POWER + SoilGrids fetch per location. Failures are not cached."""
    fp = fingerprint(lat, lon)
    if "annual_rain_mm" not in fp["criteria"]:
        raise RuntimeError("; ".join(fp["notes"]) or "climate data unavailable")
    return fp


def make_map(lat: float, lon: float, style: str) -> folium.Map:
    fmap = folium.Map(location=[lat, lon], zoom_start=10, tiles=None,
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

    # 160 acres is about a 454 m radius circle.
    folium.Circle(
        [lat, lon], radius=454, color="#10b981", weight=1.6,
        fill=True, fill_color="#10b981", fill_opacity=0.13).add_to(fmap)

    marker_html = """
<div style="position:relative;width:44px;height:44px;">
  <style>
    @keyframes fs-marker-ping {
      0% { transform: scale(0.55); opacity: 0.9; }
      70%, 100% { transform: scale(1.55); opacity: 0; }
    }
  </style>
  <span style="position:absolute;inset:3px;border-radius:50%;
    border:1.5px solid rgba(52,211,153,.9);
    animation:fs-marker-ping 2.4s cubic-bezier(.215,.61,.355,1) infinite;"></span>
  <span style="position:absolute;left:11px;top:11px;width:22px;height:22px;
    border-radius:50%;background:rgba(16,185,129,.22);
    border:2px solid #10b981;box-shadow:0 0 16px rgba(16,185,129,.65);"></span>
  <span style="position:absolute;left:20px;top:12px;width:2px;height:20px;background:#10b981;"></span>
  <span style="position:absolute;left:12px;top:20px;width:20px;height:2px;background:#10b981;"></span>
  <span style="position:absolute;left:19px;top:19px;width:6px;height:6px;
    border-radius:50%;background:#fff;box-shadow:0 0 5px rgba(0,0,0,.5);"></span>
</div>
"""
    folium.Marker(
        [lat, lon],
        tooltip="Your field",
        icon=folium.DivIcon(
            html=marker_html, icon_size=(44, 44), icon_anchor=(22, 22),
            class_name="fs-field-marker")).add_to(fmap)

    fmap.get_root().header.add_child(folium.Element("""
<style>
  .leaflet-container { background: #0b0f17 !important; font-family: Inter, sans-serif; }
  .leaflet-control-attribution {
    background: rgba(11, 15, 23, 0.82) !important;
    color: #94a3b8 !important;
    border: 1px solid rgba(51, 65, 85, 0.5) !important;
    border-radius: 4px !important;
    padding: 1px 5px !important;
    font-size: 9px !important;
    backdrop-filter: blur(6px);
  }
  .leaflet-control-attribution a { color: #cbd5e1 !important; }
  .leaflet-control-zoom {
    border: 1px solid rgba(51, 65, 85, 0.8) !important;
    border-radius: 7px !important;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35) !important;
  }
  .leaflet-control-zoom a {
    background: rgba(11, 15, 23, 0.92) !important;
    color: #cbd5e1 !important;
    border-color: rgba(51, 65, 85, 0.7) !important;
  }
  .leaflet-control-zoom a:hover { background: #172033 !important; color: #fff !important; }
  .leaflet-control-scale-line {
    background: rgba(11, 15, 23, 0.75) !important;
    border-color: #475569 !important;
    color: #94a3b8 !important;
    font-size: 9px !important;
  }
  .leaflet-tooltip {
    background: #0b0f17 !important;
    border: 1px solid #334155 !important;
    color: #e2e8f0 !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35) !important;
    font-size: 10px !important;
  }
  .leaflet-tooltip-top:before { border-top-color: #334155 !important; }
</style>
"""))
    return fmap


# ---------------------------------------------------------------------- state
st.session_state.setdefault("lat", 42.10)
st.session_state.setdefault("lon", -93.55)
st.session_state.setdefault("w_fit", 1)
st.session_state.setdefault("w_soil", 1)
st.session_state.setdefault("w_water", 1)
# a map click is applied here, before the coordinate boxes are drawn
if "pending_click" in st.session_state:
    st.session_state.lat, st.session_state.lon = st.session_state.pop("pending_click")
crop_names = [c["crop"] for c in load_crops()]

# --------------------------------------------------------------------- header
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f"""
<header class="fs-header">
  <div class="fs-header-inner">
    <div class="fs-brand">
      <div class="fs-logo">{ICON_GLOBE}</div>
      <div>
        <div class="fs-brand-line">
          <h1>Field Shift</h1>
          <span class="fs-version">NASA EarthData · Space Apps 2026</span>
        </div>
        <p>Synthesizing hyper-local satellite observations, climate projections &amp;
        soil matrices for resilient farming</p>
      </div>
    </div>
    <div class="fs-header-actions">
      <a class="fs-top-btn" href="{REPO_URL}/fork" target="_blank" rel="noopener">
        {ICON_FORK}<span>Fork</span>
      </a>
      <a class="fs-top-btn fs-icon-only" aria-label="GitHub repository"
         href="{REPO_URL}" target="_blank" rel="noopener">{ICON_GITHUB}</a>
      <span class="fs-top-sep"></span>
      <a class="fs-top-btn fs-icon-only" aria-label="Methodology and limits"
         href="{REPO_URL}#readme" target="_blank" rel="noopener">{ICON_INFO}</a>
    </div>
  </div>
</header>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ fetch data
LAT, LON = round(st.session_state.lat, 3), round(st.session_state.lon, 3)
fp = None
fetch_error = None
with st.spinner("Fetching NASA climate, groundwater, terrain and soil data for this location…"):
    try:
        fp = site_data(LAT, LON)
    except Exception as exc:  # keep the controls alive so the farmer can move the pin
        fetch_error = exc

# crops seen here by satellite become the starting answer for a new location
detected = detected_crops(fp) if fp else []
if fp and st.session_state.get("crops_for") != (LAT, LON):
    st.session_state.crops_for = (LAT, LON)
    if detected:
        st.session_state.current = detected[:3]
st.session_state.setdefault("current", ["corn", "soybean"])

# --------------------------------------------------------------------- layout
left, right = st.columns([4, 8], gap="large")

# ------------------------------------------------------------- left controls
with left, st.container(key="field-panel"):
    st.markdown(f"""
<div class="fs-panel-head">
  <div class="fs-panel-title"><span class="fs-dot fs-dot-green"></span>
    <h2>Field Parameters</h2></div>
  <span class="fs-code">{esc(field_code(LAT, LON))}</span>
</div>
""", unsafe_allow_html=True)

    st.markdown(f"""
<div class="fs-section">
  <div class="fs-section-head">
    <span class="fs-label">Your farm coordinates</span>
    <span class="fs-link">{ICON_PIN} Click map to pick</span>
  </div>
  <p class="fs-hint">Click on the satellite map or type high-precision decimal coordinates.</p>
</div>
""", unsafe_allow_html=True)

    lat_col, lon_col = st.columns(2, gap="small")
    lat_dir = "°S" if st.session_state.lat < 0 else "°N"
    lon_dir = "°E" if st.session_state.lon >= 0 else "°W"
    with lat_col, st.container(key="coord-lat"):
        st.markdown(f'<div class="fs-coord-head"><span>Latitude</span>'
                    f'<span class="fs-unit">{lat_dir}</span></div>', unsafe_allow_html=True)
        st.number_input("Latitude", -60.0, 75.0, step=0.001, format="%.3f", key="lat",
                        label_visibility="collapsed")
    with lon_col, st.container(key="coord-lon"):
        st.markdown(f'<div class="fs-coord-head"><span>Longitude</span>'
                    f'<span class="fs-unit">{lon_dir}</span></div>', unsafe_allow_html=True)
        st.number_input("Longitude", -180.0, 180.0, step=0.001, format="%.3f", key="lon",
                        label_visibility="collapsed")

    st.markdown('<div class="fs-section"><span class="fs-label">What do you grow now?</span></div>',
                unsafe_allow_html=True)
    current = st.multiselect("What do you grow now?", crop_names, key="current",
                             max_selections=3, label_visibility="collapsed",
                             placeholder="+ Add crop...")

    if detected:
        crop_note = ("Pre-filled from USDA satellite crop maps for this spot. "
                     "Change it if wrong.")
    elif fp and fp["criteria"].get("c19_crop_sequence"):
        crop_note = ("USDA crop maps show no primary field crop registered at this exact "
                     "spot. Pick what you currently manage.")
    else:
        crop_note = ("Crop history is not available at this spot. "
                     "Pick what you currently manage.")
    st.markdown(f'<p class="fs-note">{ICON_ALERT}<span>{esc(crop_note)}</span></p>',
                unsafe_allow_html=True)

    st.markdown("""
<div class="fs-section">
  <div class="fs-section-head">
    <span class="fs-label" style="text-transform:uppercase;letter-spacing:.055em;">Your priorities (0 – 5)</span>
    <span class="fs-link">Rank weight</span>
  </div>
</div>
""", unsafe_allow_html=True)

    def slider_label(text: str, key: str) -> None:
        st.markdown(
            f'<div class="fs-slider-label"><span>{esc(text)}</span>'
            f'<span class="fs-slider-value">{st.session_state[key]}</span></div>',
            unsafe_allow_html=True)

    slider_label("Climate fit", "w_fit")
    w_fit = st.slider("Climate fit", 0, 5, key="w_fit", label_visibility="collapsed")
    st.markdown('<div class="fs-slider-scale"><span>0</span><span>5</span></div>',
                unsafe_allow_html=True)
    slider_label("Soil health regeneration", "w_soil")
    w_soil = st.slider("Soil health regeneration", 0, 5, key="w_soil",
                       label_visibility="collapsed")
    st.markdown('<div class="fs-slider-scale"><span>0</span><span>5</span></div>',
                unsafe_allow_html=True)
    slider_label("Water saving & drought resistance", "w_water")
    w_water = st.slider("Water saving & drought resistance", 0, 5, key="w_water",
                        label_visibility="collapsed")
    st.markdown('<div class="fs-slider-scale"><span>0</span><span>5</span></div>',
                unsafe_allow_html=True)

    st.markdown('<div class="fs-section"><span class="fs-label">Correct auto-filled values</span></div>',
                unsafe_allow_html=True)
    irrigated = st.checkbox("This field is equipped with irrigation")
    use_ph = st.checkbox("I know my lab-tested soil pH")
    ph = None
    if use_ph:
        st.markdown('<div class="fs-coord-head" style="margin-top:6px;">'
                    '<span>Soil pH in H₂O</span><span class="fs-unit">pH</span></div>',
                    unsafe_allow_html=True)
        st.number_input("Soil pH", 3.0, 11.0, 6.5, 0.1, label_visibility="collapsed",
                        placeholder="e.g. 6.5")

    recalc = st.button("Re-Calculate Crop Rotations", icon=":material/bolt:",
                       use_container_width=True)
    st.markdown('<div class="fs-model-line">Models: NASA NEX-GDDP-CMIP6 + USDA CDL</div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- map panel
with right, st.container(key="map-card"):
    with st.container(key="map-header"):
        head_left, head_right = st.columns([7, 5], vertical_alignment="center")
        with head_left:
            st.markdown(f"""
<div class="fs-map-coords">
  <span class="fs-live"></span>
  <span class="fs-map-title">Active Field Coordinates:</span>
  <span class="fs-coord-chip">{esc(coord_text(LAT, LON))}</span>
</div>
""", unsafe_allow_html=True)
        with head_right:
            map_style = st.radio("Map style", ["Hybrid", "Satellite", "Terrain"],
                                 horizontal=True, label_visibility="collapsed",
                                 key="map_style")
    fmap = make_map(LAT, LON, map_style)
    clicked = st_folium(fmap, height=378, use_container_width=True,
                        returned_objects=["last_clicked"], key="map")
    st.markdown(f"""
<div class="fs-map-legend">
  <span class="fs-dot fs-dot-green"></span>
  <span>Target plot: <strong>160 acres</strong> (NASA 250 m pixel)</span>
</div>
""", unsafe_allow_html=True)

    click = (clicked or {}).get("last_clicked")
    if click:
        new = (round(click["lat"], 3), round(click["lng"], 3))
        # act on each click once, so typed coordinates are not overwritten later
        if new != st.session_state.get("handled_click"):
            st.session_state.handled_click = new
            st.session_state.pending_click = new
            st.rerun()

# ----------------------------------------------------------- criteria panel
if fp is None:
    with right, st.container(key="criteria-card"):
        st.markdown(f"""
<div style="padding:18px;">
  <div class="fs-card-title-row"><h3 class="fs-card-title">Auto-filled Environmental Criteria</h3></div>
  <div class="fs-problem fs-problem-red" style="margin:12px 0 0;">
    {ICON_ALERT}<span><strong>Could not fetch data for this location.</strong><br>{esc(fetch_error)}</span>
  </div>
</div>
""", unsafe_allow_html=True)
        if st.button("Retry the missing data", key="retry-all"):
            site_data.clear()
            st.rerun()
else:
    with right, st.container(key="criteria-card"):
        with st.container(key="criteria-head"):
            head_left, head_right = st.columns([9, 3], vertical_alignment="center")
            with head_left:
                st.markdown("""
<div>
  <div class="fs-card-title-row">
    <h3 class="fs-card-title">Auto-filled Environmental Criteria</h3>
    <span class="fs-source-pill">Satellite + In-situ</span>
  </div>
  <p class="fs-card-sub">Climate values come from a NASA grid cell about 50 km wide,
  so nearby fields share them. Soil values are local (250 m).</p>
</div>
""", unsafe_allow_html=True)
            with head_right:
                if st.button("Refresh Feeds", icon=":material/refresh:", key="refresh-feeds"):
                    site_data.clear()
                    st.rerun()

        st.markdown(f"""
<div class="fs-table-wrap">
<table class="fs-table" id="nasa-criteria-table">
  <thead><tr><th>Criterion</th><th>Observed / Projected Value</th>
  <th>Condition Status</th><th>Source &amp; Instrument</th></tr></thead>
  <tbody>{primary_criteria_html(fp)}</tbody>
</table>
</div>
""", unsafe_allow_html=True)

        for note in fp["notes"]:
            st.markdown(f'<div class="fs-problem">{ICON_ALERT}<span>{esc(note)}</span></div>',
                        unsafe_allow_html=True)
        if fp["notes"]:
            if st.button("Retry the missing data", key="retry-missing"):
                site_data.clear()
                st.rerun()

        with st.expander(f"All {len(CRITERIA)} auto-filled criteria"):
            st.markdown(f"""
<div class="fs-table-wrap">
<table class="fs-table">
  <thead><tr><th>Criterion</th><th>Value</th><th>Condition Status</th>
  <th>Source &amp; Instrument</th></tr></thead>
  <tbody>{extra_criteria_html(fp)}</tbody>
</table>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------- recommendations panel
with right, st.container(key="recs-card"):
    weights = {"fit": w_fit, "soil": w_soil, "water": w_water}
    res = None
    rec_error = None
    if fp is not None and sum(weights.values()) > 0:
        try:
            res = recommend(LAT, LON, weights, top=5, current=tuple(current),
                            fp=fp, overrides={"ph": ph,
                                              "irrigated": irrigated or None})
        except Exception as exc:
            rec_error = exc

    count = len(res["recommendations"]) if res else 0
    if res:
        sub = criteria_summary(fp)
    elif fp is not None and sum(weights.values()) == 0:
        sub = "Set at least one priority above zero to rank rotations."
    else:
        sub = "Ranked by your priority weights and the criteria measured for this field."
    count_text = (f"{count} recommendation{'s' if count != 1 else ''} generated"
                  if count else "No rotations ranked")

    st.markdown(f"""
<div class="fs-recs-head">
  <div>
    <div class="fs-recs-title-row">
      <h3 class="fs-recs-title">Optimal Crop Rotations</h3>
      <span class="fs-ranked-pill">Ranked by your weights</span>
    </div>
    <p class="fs-recs-sub">{esc(sub)}</p>
  </div>
  <span class="fs-count">{esc(count_text)}</span>
</div>
""", unsafe_allow_html=True)

    if fp is None:
        st.markdown(f'<div class="fs-info">{ICON_ALERT} Rotations will appear once the '
                    'NASA feeds for this location load.</div>', unsafe_allow_html=True)
    elif sum(weights.values()) == 0:
        st.markdown(f'<div class="fs-info">{ICON_ALERT} Set at least one priority above '
                    'zero in the panel on the left, then recalculate.</div>',
                    unsafe_allow_html=True)
    elif rec_error is not None:
        st.markdown(f'<div class="fs-info">{ICON_ALERT} {esc(rec_error)}</div>',
                    unsafe_allow_html=True)
    else:
        baseline = res["current_rotation"]
        if baseline:
            st.markdown(f"""
<div class="fs-baseline">
  <div class="fs-baseline-main">
    <span class="fs-baseline-label">Your rotation now</span>
    <strong>{arrow_join(baseline['rotation'])}</strong>
  </div>
  <div class="fs-baseline-metrics">
    <span>Overall <b>{baseline['score']:.2f}</b></span>
    <span>Climate <b>{baseline['fit']:.2f}</b></span>
    <span>Soil <b>{baseline['soil_health'] * 100:.0f}%</b></span>
    <span>Water <b>{baseline['water_saving'] * 100:.0f}/100</b></span>
  </div>
</div>
""", unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="fs-info">{ICON_ALERT} Pick the crops you grow now '
                        'to compare options against your current rotation.</div>',
                        unsafe_allow_html=True)

        recs = res["recommendations"]
        if not recs:
            st.markdown(f'<div class="fs-info">{ICON_ALERT} No rotation fits this field yet. '
                        'Try fewer current crops or move the pin.</div>',
                        unsafe_allow_html=True)
        else:
            cols = st.columns(len(recs), gap="medium")
            for index, r in enumerate(recs):
                with cols[index], st.container(key=f"rec-{index}"):
                    st.markdown(rec_card_html(r, index, baseline), unsafe_allow_html=True)
                    with st.expander("Crop details & reasons"):
                        st.markdown(crop_details_html(r), unsafe_allow_html=True)

        site = res["site"]
        st.markdown(f"""
<div style="margin-top:10px;color:#64748b;font:400 9.5px 'JetBrains Mono',monospace;line-height:1.5;">
  Dry-year check uses {esc(', '.join(f'{y} ({r:.0f} mm)' for y, r, _ in site['driest_years']))}.
  Soil texture: {esc(site['texture'] or 'missing')}.
  {'Not offered here: ' + esc(', '.join(res['crops_not_offered'])) + '.' if res['crops_not_offered'] else ''}
</div>
""", unsafe_allow_html=True)

# --------------------------------------------------------------- methodology
with right, st.container(key="method-card"):
    with st.expander("How scores are made, and what this tool cannot tell you"):
        st.markdown("""
- **Climate fit** compares each crop's published temperature, rainfall and soil pH
  ranges (FAO EcoCrop) with this location, for the ten-year average and for the
  three driest years.
- **Soil health** is the share of four checks met, from USDA NRCS Conservation
  Practice Standard 328: three or more functional groups, a legume, a perennial
  sod crop, and high-residue crops in at least half the sequence.
- **Water saving** reflects how little rainfall the rotation's crops need (FAO EcoCrop).
- **2040 fit** shifts today's temperature and rainfall by the change projected
  for 2035–2044 (NASA NEX-GDDP-CMIP6 ensemble, middle-of-the-road SSP2-4.5 pathway)
  and recomputes crop fit. It is shown for information and does not change the ranking.
- **Groundwater, slope and aridity** are shown for context and do not change the ranking.
- **This is not a yield or profit forecast.** Prices, markets, equipment and
  local practice are not considered. Talk to a local agronomist before changing
  a rotation.
""")

# -------------------------------------------------------------------- footer
st.markdown(f"""
<footer class="fs-footer">
  <div class="fs-footer-inner">
    <div class="fs-footer-left">
      <span class="fs-dot fs-dot-green"></span>
      <strong>Field Shift AgTech Intelligence</strong>
      <span>| Powered by NASA Earth Observation &amp; USDA CDL</span>
    </div>
    <div class="fs-footer-links">
      <a href="{REPO_URL}#readme" target="_blank" rel="noopener">Methodology</a>
      <a href="https://power.larc.nasa.gov/" target="_blank" rel="noopener">NASA Data</a>
      <a href="{REPO_URL}" target="_blank" rel="noopener">Source code</a>
    </div>
  </div>
</footer>
""", unsafe_allow_html=True)
