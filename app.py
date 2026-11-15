"""Field Shift -- Streamlit app.

Run from the repo root:
    streamlit run app.py
"""
from __future__ import annotations

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from fieldshift.fingerprint import fingerprint
from fieldshift.recommend import detected_crops, load_crops, recommend

st.set_page_config(page_title="Field Shift", page_icon="🌾", layout="wide")

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
    ("c16_clay_pct", "Soil clay", "%", "ISRIC SoilGrids"),
    ("c16_sand_pct", "Soil sand", "%", "ISRIC SoilGrids"),
    ("c17_soil_organic_carbon_g_per_kg", "Soil organic carbon", "g/kg", "ISRIC SoilGrids"),
    ("c18_soil_ph", "Soil pH", "", "ISRIC SoilGrids"),
    ("c19_crop_sequence", "Crops grown here, last 5 years", "", "USDA Cropland Data Layer"),
]


@st.cache_data(show_spinner=False, ttl=24 * 3600)
def site_data(lat: float, lon: float) -> dict:
    """One NASA POWER + SoilGrids fetch per location. Failures are not cached."""
    fp = fingerprint(lat, lon)
    if "annual_rain_mm" not in fp["criteria"]:
        raise RuntimeError("; ".join(fp["notes"]) or "climate data unavailable")
    return fp


def fmt(value, unit):
    if value is None:
        return "missing"
    if isinstance(value, dict):
        return ", ".join(f"{k} {v}" for k, v in value.items()) or "none"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or "none"
    return f"{value:g} {unit}".strip()


def rotation_card(label: str, r: dict, baseline: dict | None = None):
    with st.container(border=True):
        st.markdown(f"**{label}** &nbsp; {' → '.join(r['rotation'])}")
        cols = st.columns(4)
        for col, (name, key) in zip(cols, [("Overall", "score"), ("Climate fit", "fit"),
                                           ("Soil health", "soil_health"),
                                           ("Water saving", "water_saving")]):
            delta = None if baseline is None else (round(r[key] - baseline[key], 2) or 0.0)
            col.metric(name, f"{r[key]:.2f}", delta)
        if r["fit_2040"] is not None:
            st.caption(f"Average crop fit: {r['fit_today']:.2f} today → "
                       f"{r['fit_2040']:.2f} in the projected 2040 climate.")
        with st.expander("Why"):
            met = [k for k, v in r["soil_checks"].items() if v]
            unmet = [k for k, v in r["soil_checks"].items() if not v]
            st.markdown("**Soil checks met:** " + (", ".join(met) or "none"))
            if unmet:
                st.markdown("**Not met:** " + ", ".join(unmet))
            rows = []
            for name, c in r["crops"].items():
                rows.append({"Crop": name, "Fit": c["fit"], "Dry-year fit": c["dry_year_fit"],
                             "2040 fit": c.get("fit_2040"),
                             "Limited by": c["limiting_factor"] or "—",
                             "Notes": "; ".join(c["notes"])})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# ---------------------------------------------------------------- state
st.session_state.setdefault("lat", 42.10)
st.session_state.setdefault("lon", -93.55)
# a map click is applied here, before the coordinate boxes are drawn
if "pending_click" in st.session_state:
    st.session_state.lat, st.session_state.lon = st.session_state.pop("pending_click")
crop_names = [c["crop"] for c in load_crops()]

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Your farm")
    st.caption("Click the map or type coordinates.")
    st.number_input("Latitude", -60.0, 75.0, format="%.3f", key="lat")
    st.number_input("Longitude", -180.0, 180.0, format="%.3f", key="lon")
    LAT, LON = round(st.session_state.lat, 3), round(st.session_state.lon, 3)


# ---------------------------------------------------------------- main
st.title("Field Shift")
st.caption("Pick your field. We fill in the climate and soil criteria from NASA data "
           "and rank crop rotations, with the reasons for each.")

left, right = st.columns([1, 1])
with left:
    fmap = folium.Map([LAT, LON], zoom_start=9, tiles="OpenStreetMap")
    folium.CircleMarker([LAT, LON], radius=9, color="#b91c1c", weight=3,
                        fill=True, fill_opacity=0.35).add_to(fmap)
    clicked = st_folium(fmap, height=380, use_container_width=True,
                        returned_objects=["last_clicked"], key="map")
    click = (clicked or {}).get("last_clicked")
    if click:
        new = (round(click["lat"], 3), round(click["lng"], 3))
        # act on each click once, so typed coordinates are not overwritten later
        if new != st.session_state.get("handled_click"):
            st.session_state.handled_click = new
            st.session_state.pending_click = new
            st.rerun()

try:
    with st.spinner("Fetching NASA climate, groundwater, terrain and soil data for this location…"):
        fp = site_data(LAT, LON)
except Exception as exc:
    st.error(f"Could not fetch data for this location: {exc}")
    st.stop()

# crops seen here by satellite become the starting answer for a new location
detected = detected_crops(fp)
if st.session_state.get("crops_for") != (LAT, LON):
    st.session_state.crops_for = (LAT, LON)
    if detected:
        st.session_state.current = detected[:3]
st.session_state.setdefault("current", ["corn", "soybean"])

with st.sidebar:
    current = st.multiselect("What do you grow now?", crop_names, key="current",
                             max_selections=3)
    if detected:
        st.caption("Pre-filled from USDA satellite crop maps of this spot. Change it if wrong.")
    elif fp["criteria"].get("c19_crop_sequence"):
        st.caption("USDA crop maps show no field crop at this spot. Pick what you grow.")
    else:
        st.caption("Crop history not available here. Pick what you grow.")
    st.header("Your priorities")
    w_fit = st.slider("Climate fit", 0, 5, 1)
    w_soil = st.slider("Soil health", 0, 5, 1)
    w_water = st.slider("Water saving", 0, 5, 1)

    st.header("Correct the auto-filled values")
    irrigated = st.checkbox("This field is irrigated")
    use_ph = st.checkbox("I know my soil pH")
    ph = st.number_input("Soil pH", 3.0, 11.0, 6.5, 0.1) if use_ph else None

with right:
    st.subheader("Auto-filled criteria")
    st.caption("Climate values come from a NASA grid cell about 50 km wide, so nearby "
               "fields share them. Soil values are local (250 m).")
    crit = fp["criteria"]
    table = pd.DataFrame(
        [{"Criterion": label, "Value": fmt(crit.get(key), unit), "Source": src}
         for key, label, unit, src in CRITERIA])
    st.dataframe(table, hide_index=True, width="stretch", height=380)
    for note in fp["notes"]:
        st.warning(note)
    if fp["notes"] and st.button("Retry the missing data"):
        site_data.clear()
        st.rerun()

if w_fit + w_soil + w_water == 0:
    st.warning("Set at least one priority above zero.")
    st.stop()

try:
    res = recommend(LAT, LON,
                    {"fit": w_fit, "soil": w_soil, "water": w_water},
                    top=5, current=tuple(current), fp=fp,
                    overrides={"ph": ph, "irrigated": irrigated or None})
except Exception as exc:
    st.error(str(exc))
    st.stop()

site = res["site"]
st.caption(
    "Dry-year check uses this location's three driest years: "
    + ", ".join(f"{y} ({r:.0f} mm)" for y, r, _ in site["driest_years"]) + ". "
    + (f"Soil texture class: {site['texture']}. " if site["texture"] else
       "Soil texture missing, not checked. ")
    + (f"Not offered here (poor climate fit): {', '.join(res['crops_not_offered'])}."
       if res["crops_not_offered"] else ""))

st.subheader("Recommended rotations")
baseline = res["current_rotation"]
if baseline:
    rotation_card("Your rotation now", baseline)
if not res["recommendations"]:
    st.info("No rotation fits. Try fewer current crops.")
for i, r in enumerate(res["recommendations"], 1):
    rotation_card(f"Option {i}", r, baseline)

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
