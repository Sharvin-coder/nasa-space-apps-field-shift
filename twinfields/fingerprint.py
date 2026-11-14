"""Field fingerprint: auto-fill the matching criteria for a location.

Usage:
    python -m twinfields.fingerprint 42.03 -93.47

Every value comes from a live API call. A criterion that could not be
fetched is returned as None with a reason in "notes" -- never a placeholder.

Sources wired so far:
    NASA POWER daily point API (no key needed)  -> criteria 1-5, 7-9
    ISRIC SoilGrids v2.0 point query (no key)   -> criteria 16-18
Not wired yet (see README): 6, 10-15, 19.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict

import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

START_YEAR, END_YEAR = 2015, 2024
# ASSUMPTION: Northern Hemisphere growing season, April-September.
SEASON_MONTHS = {4, 5, 6, 7, 8, 9}
GDD_BASE_C, GDD_CAP_C = 10.0, 30.0   # standard corn growing-degree-day bounds
HEAT_DAY_C = 32.0                    # daily max above this counts as a heat day
DRY_YEAR_FRACTION = 0.8              # season rain below 80% of the mean = dry year
POWER_FILL = -999.0


def fetch_power(lat: float, lon: float) -> dict:
    params = {
        "parameters": "PRECTOTCORR,T2M_MAX,T2M_MIN,ALLSKY_SFC_SW_DWN,GWETROOT",
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": f"{START_YEAR}0101",
        "end": f"{END_YEAR}1231",
        "format": "JSON",
    }
    r = requests.get(POWER_URL, params=params, timeout=120)
    r.raise_for_status()
    return r.json()["properties"]["parameter"]


def _ok(v) -> bool:
    return v is not None and v != POWER_FILL


def climate_criteria(p: dict) -> dict:
    rain, gdd, heat, solar, wet = (defaultdict(list) for _ in range(5))
    frost_run_best: dict[int, int] = defaultdict(int)
    run = 0
    run_year = None

    for day in sorted(p["T2M_MIN"]):
        year, month = int(day[:4]), int(day[4:6])
        tmax, tmin = p["T2M_MAX"][day], p["T2M_MIN"][day]

        # longest run of days with min temp above freezing, per calendar year
        if year != run_year:
            run, run_year = 0, year
        if _ok(tmin) and tmin > 0:
            run += 1
            frost_run_best[year] = max(frost_run_best[year], run)
        else:
            run = 0

        if month not in SEASON_MONTHS:
            continue
        if _ok(p["PRECTOTCORR"][day]):
            rain[year].append(p["PRECTOTCORR"][day])
        if _ok(tmax) and _ok(tmin):
            mean_t = (min(tmax, GDD_CAP_C) + max(min(tmin, GDD_CAP_C), GDD_BASE_C)) / 2
            gdd[year].append(max(mean_t - GDD_BASE_C, 0.0))
            heat[year].append(1 if tmax > HEAT_DAY_C else 0)
        if _ok(p["ALLSKY_SFC_SW_DWN"][day]):
            solar[year].append(p["ALLSKY_SFC_SW_DWN"][day])
        if _ok(p["GWETROOT"][day]):
            wet[year].append(p["GWETROOT"][day])

    years = sorted(rain)
    season_rain = [sum(rain[y]) for y in years]
    mean_rain = statistics.mean(season_rain)
    return {
        "c01_season_rain_mm": round(mean_rain, 1),
        "c02_season_gdd_c": round(statistics.mean(sum(gdd[y]) for y in years), 1),
        "c03_heat_days_per_season": round(statistics.mean(sum(heat[y]) for y in years), 1),
        "c04_frost_free_days": round(statistics.mean(frost_run_best[y] for y in years), 1),
        "c05_season_solar_mj_m2_day": round(
            statistics.mean(statistics.mean(solar[y]) for y in years), 2),
        "c07_season_rain_cv": round(statistics.stdev(season_rain) / mean_rain, 3),
        "c08_root_zone_wetness_0to1": round(
            statistics.mean(statistics.mean(wet[y]) for y in years), 3),
        "c09_dry_years": [y for y, r in zip(years, season_rain)
                          if r < DRY_YEAR_FRACTION * mean_rain],
        "_season_rain_by_year_mm": {y: round(r, 1) for y, r in zip(years, season_rain)},
    }


def soil_criteria(lat: float, lon: float) -> dict:
    params = [("lon", lon), ("lat", lat), ("depth", "0-5cm"), ("value", "mean")]
    params += [("property", name) for name in ("clay", "sand", "soc", "phh2o")]
    r = requests.get(SOILGRIDS_URL, params=params, timeout=60)
    r.raise_for_status()
    out = {}
    for layer in r.json()["properties"]["layers"]:
        raw = layer["depths"][0]["values"]["mean"]
        factor = layer["unit_measure"]["d_factor"]
        out[layer["name"]] = None if raw is None else raw / factor
    return {
        "c16_clay_pct": out.get("clay"),
        "c16_sand_pct": out.get("sand"),
        "c17_soil_organic_carbon_g_per_kg": out.get("soc"),
        "c18_soil_ph": out.get("phh2o"),
    }


def fingerprint(lat: float, lon: float) -> dict:
    result = {
        "lat": lat, "lon": lon,
        "period": f"{START_YEAR}-{END_YEAR}",
        "criteria": {}, "notes": [],
    }
    for name, fn in (("NASA POWER", lambda: climate_criteria(fetch_power(lat, lon))),
                     ("SoilGrids", lambda: soil_criteria(lat, lon))):
        try:
            result["criteria"].update(fn())
        except Exception as exc:  # report the failure, never fill in a guess
            result["notes"].append(f"{name} failed: {type(exc).__name__}: {exc}")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python -m twinfields.fingerprint <lat> <lon>")
    print(json.dumps(fingerprint(float(sys.argv[1]), float(sys.argv[2])), indent=2))
