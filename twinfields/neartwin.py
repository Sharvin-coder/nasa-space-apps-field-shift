"""Near-twin analysis: do winter-green fields hold up differently in summer?

Usage:
    python -m twinfields.neartwin <region>   # needs data/cache/<region>_cube.npz

Writes results/neartwin_<region>.json. All numbers are computed from the cube.

Method (one MODIS 250 m pixel = one "field sample")
  1. Eligible pixel-year: the pixel is >= PURITY corn or soy in that year AND
     in the year before (so spring greenness is not hay, pasture or wheat).
  2. Winter-green flag: the pixel's best spring NDVI (composites starting
     16 Mar - 15 Apr, before the cash crop emerges) is at least GREEN_MARGIN
     above that year's median for eligible pixels. This is a PROXY for a
     cover crop. It has not been checked against ground truth.
  3. Outcome: summer EVI (peak, and July-August mean) relative to the median
     of eligible pixels with the same crop in the same year.
  4. Difference-in-differences: a flagged pixel-year's relative outcome minus
     the same pixel's average relative outcome in its unflagged years. This
     removes fixed differences between pixels (soil, drainage, mixed edges).
  5. Uncertainty: bootstrap over ~1 km blocks, because neighbouring pixels
     share a field and are not independent.

Limits: correlation only; 250 m pixels can mix field edges; the flag also
fires on weeds or early growth; one 20 km box per region.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np

from twinfields.regions import REGIONS

CONFIG = {
    "seasons": [2015, 2024],
    "crops": {"corn": 1, "soybeans": 5},
    "purity_min": 0.95,
    "spring_window_start_doy": [75, 105],     # composite start day-of-year (0-based)
    "summer_window_start_doy": [175, 235],    # composites covering ~25 Jun - 8 Sep
    "green_margin_ndvi": 0.10,
    "min_unflagged_years": 3,
    "block_px": 4,                            # 4 x 4 pixels = ~1 km bootstrap blocks
    "bootstrap_reps": 2000,
    "seed": 0,
}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def load(cube):
    d = np.load(cube)
    good = (d["reliability"] == 0) | (d["reliability"] == 1)   # drop snow/ice and cloud
    ndvi = np.where(good, d["ndvi"] / 1e4, np.nan)
    evi = np.where(good, d["evi"] / 1e4, np.nan)
    starts = d["composite_start"].astype("datetime64[D]")
    year = starts.astype("datetime64[Y]").astype(int) + 1970
    doy0 = (starts - starts.astype("datetime64[Y]")).astype(int)
    return d, ndvi, evi, year, doy0


def build_panel(cube, cfg=CONFIG):
    """Per-season arrays (season, row, col): eligible, crop, flag, rel outcomes."""
    d, ndvi, evi, year, doy0 = load(cube)
    seasons = np.arange(cfg["seasons"][0], cfg["seasons"][1] + 1)
    cdl_years = list(d["cdl_years"])
    crop_ids = list(cfg["crops"].values())
    shape = (len(seasons),) + d["inside"].shape
    eligible = np.zeros(shape, bool)
    crop = np.zeros(shape, np.uint8)
    spring = np.full(shape, np.nan)
    flag = np.zeros(shape, bool)
    rel = {"peak_evi": np.full(shape, np.nan), "mean_evi": np.full(shape, np.nan)}
    raw = {"peak_evi": np.full(shape, np.nan), "mean_evi": np.full(shape, np.nan)}

    s0, s1 = cfg["spring_window_start_doy"]
    p0, p1 = cfg["summer_window_start_doy"]
    for k, season in enumerate(seasons):
        i = cdl_years.index(season)
        ok = d["inside"].copy()
        for j in (i, i - 1):
            ok &= np.isin(d["cdl_major"][j], crop_ids) & (d["cdl_purity"][j] >= cfg["purity_min"])
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN pixels stay NaN
            spr = np.nanmax(ndvi[(year == season) & (doy0 >= s0) & (doy0 <= s1)], axis=0)
            summer = evi[(year == season) & (doy0 >= p0) & (doy0 <= p1)]
            peak = np.nanmax(summer, axis=0)
            mean = np.nanmean(summer, axis=0)
        ok &= np.isfinite(spr) & np.isfinite(peak)
        eligible[k], crop[k], spring[k] = ok, d["cdl_major"][i], spr
        flag[k] = ok & (spr >= np.median(spr[ok]) + cfg["green_margin_ndvi"])
        raw["peak_evi"][k], raw["mean_evi"][k] = peak, mean
        for cid in crop_ids:
            sel = ok & (crop[k] == cid)
            for name in rel:
                rel[name][k][sel] = raw[name][k][sel] - np.median(raw[name][k][sel])
    return {"seasons": seasons, "eligible": eligible, "crop": crop, "spring": spring,
            "flag": flag, "rel": rel, "raw": raw, "lon": d["lon"], "lat": d["lat"]}


def did_effects(panel, outcome, cfg=CONFIG):
    """One row per flagged pixel-year: (season_idx, row, col, effect)."""
    el, fl, rel = panel["eligible"], panel["flag"], panel["rel"][outcome]
    unflagged = el & ~fl
    n_base = unflagged.sum(0)
    base = np.where(n_base >= cfg["min_unflagged_years"],
                    np.nansum(np.where(unflagged, rel, 0.0), 0) / np.maximum(n_base, 1),
                    np.nan)
    k, r, c = np.nonzero(fl & np.isfinite(base)[None])
    return k, r, c, rel[k, r, c] - base[r, c]


def block_bootstrap(effect, r, c, cfg=CONFIG):
    """Mean effect with a 95% interval, resampling ~1 km blocks."""
    if len(effect) == 0:
        return None
    b = cfg["block_px"]
    block = (r // b) * 10_000 + (c // b)
    ids, inv = np.unique(block, return_inverse=True)
    sums = np.bincount(inv, weights=effect, minlength=len(ids))
    counts = np.bincount(inv, minlength=len(ids))
    rng = np.random.default_rng(cfg["seed"])
    pick = rng.integers(0, len(ids), size=(cfg["bootstrap_reps"], len(ids)))
    means = sums[pick].sum(1) / counts[pick].sum(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"mean": round(float(effect.mean()), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "n_pixel_years": int(len(effect)), "n_blocks": int(len(ids))}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in REGIONS:
        sys.exit(f"usage: python -m twinfields.neartwin <{'|'.join(REGIONS)}>")
    region = sys.argv[1]
    cube = Path(f"data/cache/{region}_cube.npz")
    out = Path(f"results/neartwin_{region}.json")
    config = {**CONFIG, "region": region, **REGIONS[region]}
    t0 = time.time()
    panel = build_panel(cube)
    seasons = panel["seasons"]
    dry = np.isin(seasons, config["dry_years"])

    per_season = []
    for k, season in enumerate(seasons):
        el, fl = panel["eligible"][k], panel["flag"][k]
        per_season.append({
            "season": int(season), "dry": bool(dry[k]),
            "eligible_pixels": int(el.sum()), "winter_green_pixels": int(fl.sum()),
            "median_spring_ndvi": round(float(np.median(panel["spring"][k][el])), 3),
            "median_peak_evi": round(float(np.median(panel["raw"]["peak_evi"][k][el])), 3),
            "median_mean_evi": round(float(np.median(panel["raw"]["mean_evi"][k][el])), 3),
        })

    estimates = {}
    for outcome in panel["rel"]:
        k, r, c, eff = did_effects(panel, outcome)
        groups = {"all_years": np.ones(len(k), bool), "dry_years": dry[k], "other_years": ~dry[k]}
        estimates[outcome] = {g: block_bootstrap(eff[m], r[m], c[m]) for g, m in groups.items()}
        estimates[outcome]["by_season"] = {
            int(s): block_bootstrap(eff[k == i], r[k == i], c[k == i])
            for i, s in enumerate(seasons)}

    result = {
        "experiment": f"neartwin_{region}",
        "config": config,
        "data": {"cube": str(cube), "sources": [
            "NASA MODIS MOD13Q1/MYD13Q1 v6.1 (Planetary Computer mirror)",
            "USDA NASS Cropland Data Layer (CropScape WCS)"]},
        "per_season": per_season,
        "estimates_evi_units": estimates,
        "caveats": [
            "Winter-green flag is an unvalidated proxy for cover crops.",
            "Difference-in-differences on observational data: correlation, not proof.",
            "250 m pixels; one 20 km box.",
        ],
        "runtime_seconds": round(time.time() - t0, 2),
        "git_commit": git_commit(),
    }
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps({"per_season": per_season, "estimates": estimates}, indent=1))


if __name__ == "__main__":
    main()
