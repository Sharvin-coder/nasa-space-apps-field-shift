"""Field fingerprint: auto-fill the matching criteria for a location.

Usage:
    python -m fieldshift.fingerprint 42.03 -93.47

Every value comes from a live API call. A criterion that could not be
fetched is returned as None with a reason in "notes" -- never a placeholder.

Sources (none needs a key or login):
    NASA POWER daily point API                  -> criteria 1-9
    NASA POWER climate projection API (NEX-GDDP-CMIP6 ensemble) -> 14-15
    NASA GRACE/GRACE-FO groundwater drought indicator (NDMC rasters) -> 10
    NASA SRTM 30 m elevation via OpenTopoData   -> 11
    ISRIC SoilGrids v2.0 (map server, point API as fallback) -> 16-18
    USDA Cropland Data Layer (USDA NASS image server, CropScape as
    fallback)                                -> 19 (contiguous US only)
Not wired (see README): 12-13 (MODIS greenness).
"""
from __future__ import annotations

import io
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PROJECTION_URL = "https://power.larc.nasa.gov/api/projection/daily/point"
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
GRACE_PAGE = "https://nasagrace.unl.edu/GlobalData.aspx"
GRACE_TIF = "https://nasagrace.unl.edu/globaldata/{d}/gws_perc_025deg_GL_{d}.tif"
ELEVATION_URL = "https://api.opentopodata.org/v1/srtm30m"
CDL_URL = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLValue"
CDL_USDA_URL = "https://pdi.scinet.usda.gov/image/rest/services/CDL_WM/ImageServer"
SOILGRIDS_WCS = "https://maps.isric.org/mapserv"

# The ten most recent complete calendar years (2016-2025 when run in 2026).
END_YEAR = date.today().year - 1
START_YEAR = END_YEAR - 9
# ASSUMPTION: Northern Hemisphere growing season, April-September.
SEASON_MONTHS = {4, 5, 6, 7, 8, 9}
GDD_BASE_C, GDD_CAP_C = 10.0, 30.0   # standard corn growing-degree-day bounds
HEAT_DAY_C = 32.0                    # daily max above this counts as a heat day
DRY_YEAR_FRACTION = 0.8              # season rain below 80% of the mean = dry year
POWER_FILL = -999.0

SCENARIO = "ssp245"                  # middle-of-the-road emissions pathway
FUTURE_START, FUTURE_END = 2035, 2044   # ten years centred on 2040
GRACE_YEARS = 10                     # one weekly map per year, same week of year
SLOPE_STEP_M = 90.0                  # spacing of the 3x3 elevation grid
CDL_YEARS = 5


def _first_working(*attempts):
    """Run (name, function) pairs in order; return the first result.
    If all fail, the error names every attempt."""
    errors = []
    for name, fn in attempts:
        try:
            return fn()
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__} {str(exc)[:120]}")
    raise RuntimeError(" | ".join(errors))


# ------------------------------------------------------------ NASA POWER
def fetch_power(lat: float, lon: float) -> dict:
    params = {
        "parameters": "PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,ALLSKY_SFC_SW_DWN,GWETROOT,TOA_SW_DWN",
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


def hargreaves_pet_mm(tmax: float, tmin: float, toa_mj: float) -> float:
    """Reference evapotranspiration, mm/day (FAO-56 eq. 52, Hargreaves).
    toa_mj is top-of-atmosphere radiation in MJ/m2/day; 0.408 converts to mm."""
    tmean = (tmax + tmin) / 2
    return max(0.0023 * (tmean + 17.8) * math.sqrt(max(tmax - tmin, 0.0)) * 0.408 * toa_mj, 0.0)


def climate_criteria(p: dict) -> dict:
    rain, gdd, heat, solar, wet, temp, rain_all, pet_all = (defaultdict(list) for _ in range(8))
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

        if _ok(p["PRECTOTCORR"][day]):
            rain_all[year].append(p["PRECTOTCORR"][day])
        if _ok(tmax) and _ok(tmin) and _ok(p["TOA_SW_DWN"][day]):
            pet_all[year].append(hargreaves_pet_mm(tmax, tmin, p["TOA_SW_DWN"][day]))
        if month not in SEASON_MONTHS:
            continue
        if _ok(p["T2M"][day]):
            temp[year].append(p["T2M"][day])
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
    annual_rain = statistics.mean(sum(rain_all[y]) for y in years)
    annual_pet = statistics.mean(sum(pet_all[y]) for y in years)
    return {
        "c01_season_rain_mm": round(mean_rain, 1),
        "c02_season_gdd_c": round(statistics.mean(sum(gdd[y]) for y in years), 1),
        "c03_heat_days_per_season": round(statistics.mean(sum(heat[y]) for y in years), 1),
        "c04_frost_free_days": round(statistics.mean(frost_run_best[y] for y in years), 1),
        "c05_season_solar_mj_m2_day": round(
            statistics.mean(statistics.mean(solar[y]) for y in years), 2),
        # UNEP aridity index: annual rain / annual reference evapotranspiration
        "c06_aridity_index": round(annual_rain / annual_pet, 2) if annual_pet else None,
        "c06_annual_pet_mm": round(annual_pet, 0),
        "c07_season_rain_cv": round(statistics.stdev(season_rain) / mean_rain, 3),
        "c08_root_zone_wetness_0to1": round(
            statistics.mean(statistics.mean(wet[y]) for y in years), 3),
        "c09_dry_years": [y for y, r in zip(years, season_rain)
                          if r < DRY_YEAR_FRACTION * mean_rain],
        "_season_rain_by_year_mm": {y: round(r, 1) for y, r in zip(years, season_rain)},
        # extra values the recommender needs (EcoCrop ranges use annual rain
        # and growing-season mean temperature)
        "annual_rain_mm": round(annual_rain, 1),
        "season_mean_temp_c": round(statistics.mean(statistics.mean(temp[y]) for y in years), 2),
        "_annual_rain_by_year_mm": {y: round(sum(rain_all[y]), 1) for y in years},
        "_season_mean_temp_by_year_c": {y: round(statistics.mean(temp[y]), 2) for y in years},
    }


# ------------------------------------------------- climate projection (14-15)
def projection_criteria(lat: float, lon: float) -> dict:
    """Change between the last ten complete years and 2035-2044 in the NEX-GDDP-CMIP6 ensemble.

    Both periods come from the same model ensemble, so the difference is a
    model-to-model change, not model minus observation. The ensemble mean
    smooths daily extremes, so only mean temperature and total rain are used.
    """
    params = {"parameters": "T2M,PRECTOTCORR", "community": "ag",
              "latitude": lat, "longitude": lon,
              "start": f"{START_YEAR}0101", "end": f"{FUTURE_END}1231",
              "format": "json", "model": "ensemble", "scenario": SCENARIO}
    r = requests.get(PROJECTION_URL, params=params, timeout=120)
    r.raise_for_status()
    par = r.json()["properties"]["parameter"]
    t2m, pr = par["T2M"][SCENARIO], par["PRECTOTCORR"][SCENARIO]

    def period(y0, y1):
        temp = [v for d, v in t2m.items()
                if y0 <= int(d[:4]) <= y1 and int(d[4:6]) in SEASON_MONTHS and _ok(v)]
        rain = [v for d, v in pr.items() if y0 <= int(d[:4]) <= y1 and _ok(v)]
        if not temp or not rain:
            raise ValueError(f"no projection data for {y0}-{y1}")
        return statistics.mean(temp), sum(rain) / (y1 - y0 + 1)

    t_now, r_now = period(START_YEAR, END_YEAR)
    t_fut, r_fut = period(FUTURE_START, FUTURE_END)
    return {
        "c14_season_temp_change_2040_c": round(t_fut - t_now, 2),
        "c15_annual_rain_change_2040_pct": round(100 * (r_fut - r_now) / r_now, 1),
    }


# ---------------------------------------------------------- groundwater (10)
def _grace_value(day: str, lat: float, lon: float):
    from PIL import Image
    r = requests.get(GRACE_TIF.format(d=day), timeout=60)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content))
    sx, sy = im.tag_v2[33550][:2]            # pixel size, degrees
    tie = im.tag_v2[33922]                   # top-left corner: lon at [3], lat at [4]
    col, row = int((lon - tie[3]) / sx), int((tie[4] - lat) / sy)
    if not (0 <= col < im.width and 0 <= row < im.height):
        return None
    v = im.getpixel((col, row))
    return None if v < 0 else float(v)       # -999 = no data


def groundwater_criteria(lat: float, lon: float) -> dict:
    """Groundwater wetness percentile from the GRACE/GRACE-FO data-assimilation
    drought indicator (0 = driest on record for that week, 100 = wettest)."""
    r = requests.get(GRACE_PAGE, timeout=60)
    r.raise_for_status()
    days = sorted(set(re.findall(r"GlobalData\.aspx\?p=(\d{8})", r.text)))
    if not days:
        raise ValueError("no GRACE map dates listed")
    latest = datetime.strptime(days[-1], "%Y%m%d").date()
    as_dates = {datetime.strptime(d, "%Y%m%d").date(): d for d in days}
    picks = []
    for k in range(GRACE_YEARS):             # same week of the year, k years back
        target = latest - timedelta(days=364 * k)
        nearest = min(as_dates, key=lambda d: abs(d - target))
        if abs(nearest - target) <= timedelta(days=14):
            picks.append(as_dates[nearest])
    with ThreadPoolExecutor(5) as ex:
        values = list(ex.map(lambda d: _grace_value(d, lat, lon), picks))
    by_date = {d: round(v, 1) for d, v in zip(picks, values) if v is not None}
    if not by_date:
        return {"c10_groundwater_percentile_latest": None,
                "c10_groundwater_percentile_10yr_mean": None}
    return {
        "c10_groundwater_percentile_latest": by_date.get(picks[0]),
        "c10_groundwater_percentile_10yr_mean": round(statistics.mean(by_date.values()), 1),
        "_groundwater_latest_date": picks[0],
        "_groundwater_percentile_by_date": by_date,
    }


# ------------------------------------------------------------------ slope (11)
def slope_criteria(lat: float, lon: float) -> dict:
    """Slope from a 3x3 grid of SRTM elevations (Horn method)."""
    dlat = SLOPE_STEP_M / 111_320
    dlon = SLOPE_STEP_M / (111_320 * math.cos(math.radians(lat)))
    pts = [(lat + i * dlat, lon + j * dlon) for i in (1, 0, -1) for j in (-1, 0, 1)]
    r = requests.get(ELEVATION_URL, timeout=60, params={
        "locations": "|".join(f"{a:.6f},{b:.6f}" for a, b in pts)})
    r.raise_for_status()
    z = [p["elevation"] for p in r.json()["results"]]
    if any(v is None for v in z):
        return {"c11_slope_pct": None, "c11_elevation_m": z[4]}
    a, b, c, d, _, f, g, h, i = z            # rows north to south, west to east
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * SLOPE_STEP_M)
    dzdy = ((a + 2 * b + c) - (g + 2 * h + i)) / (8 * SLOPE_STEP_M)
    return {"c11_slope_pct": round(100 * math.hypot(dzdx, dzdy), 1),
            "c11_elevation_m": z[4]}


# --------------------------------------------------------------------- soil
SOIL_PROPS = {"clay": "c16_clay_pct", "sand": "c16_sand_pct",
              "soc": "c17_soil_organic_carbon_g_per_kg", "phh2o": "c18_soil_ph"}
SOIL_SCALE = 10      # SoilGrids stores all four as integers, ten times the unit


def _soil_wcs_value(prop: str, lat: float, lon: float):
    """One SoilGrids pixel from the ISRIC map server (WCS), 0-5 cm mean."""
    from PIL import Image
    d = 0.002        # a window about two 250 m pixels wide, centred on the point
    crs = "http://www.opengis.net/def/crs/EPSG/0/4326"
    r = requests.get(SOILGRIDS_WCS, timeout=20, params=[
        ("map", f"/map/{prop}.map"), ("SERVICE", "WCS"), ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"), ("COVERAGEID", f"{prop}_0-5cm_mean"),
        ("FORMAT", "image/tiff"),
        ("SUBSET", f"long({lon - d},{lon + d})"), ("SUBSET", f"lat({lat - d},{lat + d})"),
        ("SUBSETTINGCRS", crs), ("OUTPUTCRS", crs)])
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content))
    sx, sy = im.tag_v2[33550][:2]            # pixel size, degrees
    tie = im.tag_v2[33922]                   # top-left corner: lon at [3], lat at [4]
    col = min(max(int((lon - tie[3]) / sx), 0), im.width - 1)
    row = min(max(int((tie[4] - lat) / sy), 0), im.height - 1)
    v = im.getpixel((col, row))
    return None if v <= 0 else v / SOIL_SCALE    # 0 or negative = no data


def _soil_wcs(lat: float, lon: float) -> dict:
    with ThreadPoolExecutor(len(SOIL_PROPS)) as ex:
        values = list(ex.map(lambda prop: _soil_wcs_value(prop, lat, lon), SOIL_PROPS))
    return dict(zip(SOIL_PROPS.values(), values))


def _soil_rest(lat: float, lon: float) -> dict:
    params = [("lon", lon), ("lat", lat), ("depth", "0-5cm"), ("value", "mean")]
    params += [("property", name) for name in SOIL_PROPS]
    r = requests.get(SOILGRIDS_URL, params=params, timeout=25)
    r.raise_for_status()
    out = {}
    for layer in r.json()["properties"]["layers"]:
        raw = layer["depths"][0]["values"]["mean"]
        factor = layer["unit_measure"]["d_factor"]
        out[layer["name"]] = None if raw is None else raw / factor
    return {key: out.get(prop) for prop, key in SOIL_PROPS.items()}


def soil_criteria(lat: float, lon: float) -> dict:
    """SoilGrids 0-5 cm values: map server first, point API as a fallback."""
    return _first_working(("ISRIC map server", lambda: _soil_wcs(lat, lon)),
                          ("SoilGrids point API", lambda: _soil_rest(lat, lon)))


# ----------------------------------------------------- crop sequence (19)
def albers_conus(lat: float, lon: float) -> tuple[float, float]:
    """lat/lon -> USA Contiguous Albers Equal Area (EPSG:5070), metres.
    Snyder, Map Projections: A Working Manual, eq. 14-1 to 14-6 (GRS80)."""
    a, e2 = 6378137.0, 0.00669438002290
    e = math.sqrt(e2)

    def q(phi):
        s = math.sin(phi)
        return (1 - e2) * (s / (1 - e2 * s * s)
                           - math.log((1 - e * s) / (1 + e * s)) / (2 * e))

    def m(phi):
        return math.cos(phi) / math.sqrt(1 - e2 * math.sin(phi) ** 2)

    p1, p2, p0, l0 = (math.radians(v) for v in (29.5, 45.5, 23.0, -96.0))
    n = (m(p1) ** 2 - m(p2) ** 2) / (q(p2) - q(p1))
    c = m(p1) ** 2 + n * q(p1)
    rho = a * math.sqrt(c - n * q(math.radians(lat))) / n
    rho0 = a * math.sqrt(c - n * q(p0)) / n
    theta = n * (math.radians(lon) - l0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


_CDL_NAMES: dict = {}


def _cdl_names() -> dict:
    """CDL class code -> class name, from the USDA image server's own table."""
    if not _CDL_NAMES:
        r = requests.get(CDL_USDA_URL + "/rasterAttributeTable", params={"f": "json"}, timeout=20)
        r.raise_for_status()
        _CDL_NAMES.update({int(f["attributes"]["Value"]): f["attributes"]["Class_Names"]
                           for f in r.json()["features"]})
    return _CDL_NAMES


def _cdl_usda(year: int, lat: float, lon: float):
    """Crop class at a point for one year, from USDA NASS's image server."""
    r = requests.get(CDL_USDA_URL + "/identify", timeout=20, params={
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "mosaicRule": json.dumps({"mosaicMethod": "esriMosaicAttribute",
                                  "where": f"Year={year}"}),
        "returnGeometry": "false", "returnCatalogItems": "false", "f": "json"})
    r.raise_for_status()
    value = r.json().get("value")
    if value is None or not str(value).isdigit() or int(value) == 0:
        return None                          # NoData: year not published or off the map
    return _cdl_names().get(int(value))


def _cdl_cropscape(year: int, lat: float, lon: float):
    x, y = albers_conus(lat, lon)
    r = requests.get(CDL_URL, params={"year": year, "x": round(x), "y": round(y)}, timeout=15)
    r.raise_for_status()
    found = re.search(r'category:\s*"([^"]*)"', r.text)
    return found.group(1) if found and found.group(1) else None


def crop_sequence_criteria(lat: float, lon: float) -> dict:
    """Crop type at this exact pixel for the last few years (USDA CDL).
    USDA NASS image server first, the CropScape service as a fallback."""
    if not (24 <= lat <= 50 and -125 <= lon <= -66):
        raise ValueError("USDA Cropland Data Layer covers the contiguous US only")
    last = date.today().year - 1             # newest year may not be published yet,
    years = list(range(last - CDL_YEARS, last + 1))   # so ask for one extra

    def fetch(lookup):
        with ThreadPoolExecutor(len(years)) as ex:
            cats = list(ex.map(lambda yr: lookup(yr, lat, lon), years))
        return {yr: cat for yr, cat in zip(years, cats) if cat}

    def usda():
        _cdl_names()
        return fetch(_cdl_usda)

    seq = _first_working(("USDA image server", usda),
                         ("CropScape", lambda: fetch(_cdl_cropscape)))
    return {"c19_crop_sequence": {yr: seq[yr] for yr in sorted(seq)[-CDL_YEARS:]}}


# ---------------------------------------------------------------- assemble
# Successful fetches are kept in memory per source and location, so a retry
# after one service fails only asks that service again.
_CACHE: dict = {}
_CACHE_MAX = 2000


def fingerprint(lat: float, lon: float) -> dict:
    result = {
        "lat": lat, "lon": lon,
        "period": f"{START_YEAR}-{END_YEAR}",
        "criteria": {}, "notes": [],
    }
    sources = (
        ("NASA POWER", lambda: climate_criteria(fetch_power(lat, lon))),
        ("NASA GRACE groundwater", lambda: groundwater_criteria(lat, lon)),
        ("SRTM slope", lambda: slope_criteria(lat, lon)),
        ("NEX-GDDP-CMIP6 projection", lambda: projection_criteria(lat, lon)),
        ("SoilGrids", lambda: soil_criteria(lat, lon)),
        ("USDA crop sequence", lambda: crop_sequence_criteria(lat, lon)),
    )

    def run(source):
        name, fn = source
        key = (name, lat, lon)
        if key in _CACHE:
            return _CACHE[key], None
        try:
            values = fn()
        except Exception as exc:  # report the failure, never fill in a guess
            return {}, f"{type(exc).__name__}: {exc}"
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = values
        return values, None

    with ThreadPoolExecutor(len(sources)) as ex:
        outcomes = list(ex.map(run, sources))
    for (name, _), (values, error) in zip(sources, outcomes):
        result["criteria"].update(values)
        if error:
            result["notes"].append(f"{name} unavailable: {error}")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python -m fieldshift.fingerprint <lat> <lon>")
    print(json.dumps(fingerprint(float(sys.argv[1]), float(sys.argv[2])), indent=2))
