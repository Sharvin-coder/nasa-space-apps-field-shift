"""Location -> ranked crop rotations, with the reasons behind each.

Usage:
    python -m fieldshift.recommend <lat> <lon> [--fit 1] [--soil 1] [--water 1]
                                   [--current corn,soybean] [--top 5] [--json]

--current is what the farmer grows now. It is scored as the baseline, and
only rotations that keep those crops are offered (a shift, not a restart).

The three weights are the farmer's priorities. There is no profit score:
that needs real price and yield data, which is not wired in.

How scores are made (nothing here is a yield forecast)
  Crop fit     FAO EcoCrop method: for temperature, rainfall and soil pH a
               crop scores 1 inside its optimal range, 0 outside its absolute
               range, and a straight line in between. Crop fit is the lowest
               of the three. Warm-season crops also need the frost-free
               season to cover their minimum crop cycle, and every crop
               needs the soil texture to be in its tolerated list.
  Dry-year fit the same score using each of the site's three driest years
               (annual rain) out of the last ten, averaged.
  Rotation fit average of crop fit and dry-year fit over the rotation's crops.
  Soil health  share of four checks met, taken from USDA NRCS Conservation
               Practice Standard 328 (Conservation Crop Rotation):
               3+ functional groups, a legume, a perennial sod crop, and
               high-residue crops in at least half the sequence.
               ("3+" is our threshold; the standard says to rotate groups.)
  Water saving how low the rotation's average optimal-minimum rainfall
               (EcoCrop ROPMN) is, scaled across the crop table.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
from pathlib import Path

from fieldshift.fingerprint import fingerprint

CROP_TABLE = Path(__file__).with_name("crops.csv")
MIN_CROP_FIT = 0.2          # crops below this fit are not offered
N_DRIEST = 3
ROTATION_LENGTHS = (2, 3, 4)


def load_crops():
    crops = []
    for r in csv.DictReader(CROP_TABLE.open(encoding="utf-8")):
        for k, v in r.items():
            if k.isupper() and k != "TEXTR":
                r[k] = float(v)
        r["legume"] = r["legume"] == "True"
        r["perennial"] = r["perennial"] == "True"
        crops.append(r)
    return crops


def trapezoid(x, lo, opt_lo, opt_hi, hi):
    if x <= lo or x >= hi:
        return 0.0
    if x < opt_lo:
        return (x - lo) / (opt_lo - lo)
    if x > opt_hi:
        return (hi - x) / (hi - opt_hi)
    return 1.0


def texture_class(clay, sand):
    """FAO-style class: heavy (fine), light (coarse) or medium."""
    if clay is None or sand is None:
        return None
    if clay > 35:
        return "heavy"
    if sand > 65 and clay < 18:
        return "light"
    return "medium"


def crop_fit(crop, temp, rain, site):
    """Return (score, {factor: score}, notes) for one crop at one climate."""
    parts = {
        "temperature": trapezoid(temp, crop["TMIN"], crop["TOPMN"], crop["TOPMX"], crop["TMAX"]),
        "rainfall": trapezoid(rain, crop["RMIN"], crop["ROPMN"], crop["ROPMX"], crop["RMAX"]),
    }
    notes = []
    if site["ph"] is not None:
        parts["soil pH"] = trapezoid(site["ph"], crop["PHMIN"], crop["PHOPMN"],
                                     crop["PHOPMX"], crop["PHMAX"])
    else:
        notes.append("soil pH missing, not checked")
    if crop["group"].startswith("warm") and site["frost_free_days"] is not None:
        parts["season length"] = 1.0 if site["frost_free_days"] >= crop["GMIN"] else 0.0
    tex = site["texture"]
    if tex is not None and "wide" not in crop["TEXTR"]:
        parts["soil texture"] = 1.0 if tex in crop["TEXTR"] else 0.0
    if parts["rainfall"] < 1 and rain > crop["ROPMX"]:
        notes.append("limited by too much rain per EcoCrop; drainage may change this")
    return min(parts.values()), parts, notes


def site_from_fingerprint(fp):
    c = fp["criteria"]
    need = ["annual_rain_mm", "season_mean_temp_c", "_annual_rain_by_year_mm",
            "_season_mean_temp_by_year_c"]
    missing = [k for k in need if c.get(k) is None]
    if missing:
        raise RuntimeError(f"cannot recommend: missing climate criteria {missing}; "
                           f"notes: {fp['notes']}")
    rain_by_year = c["_annual_rain_by_year_mm"]
    driest = sorted(rain_by_year, key=rain_by_year.get)[:N_DRIEST]
    return {
        "temp": c["season_mean_temp_c"], "rain": c["annual_rain_mm"],
        "ph": c.get("c18_soil_ph"),
        "frost_free_days": c.get("c04_frost_free_days"),
        "texture": texture_class(c.get("c16_clay_pct"), c.get("c16_sand_pct")),
        "driest_years": [(y, rain_by_year[y], c["_season_mean_temp_by_year_c"][y])
                         for y in driest],
    }


def score_crops(crops, site):
    out = {}
    for crop in crops:
        fit, parts, notes = crop_fit(crop, site["temp"], site["rain"], site)
        dry = [crop_fit(crop, t, r, site)[0] for _, r, t in site["driest_years"]]
        out[crop["crop"]] = {
            "fit": round(fit, 3), "dry_year_fit": round(sum(dry) / len(dry), 3),
            "factors": {k: round(v, 3) for k, v in parts.items()},
            "limiting_factor": min(parts, key=parts.get) if fit < 1 else None,
            "notes": notes,
        }
    return out


def soil_checks(rotation):
    groups = {c["group"] for c in rotation}
    return {
        "3+ functional groups": len(groups) >= 3,
        "includes a legume": any(c["legume"] for c in rotation),
        "includes a perennial sod crop": any(c["perennial"] for c in rotation),
        "high-residue crops in at least half": sum(c["residue"] == "high" for c in rotation)
                                              >= len(rotation) / 2,
    }


def order_rotation(rotation):
    """Order so neighbouring crops differ in functional group where possible."""
    best = min(itertools.permutations(rotation),
               key=lambda p: (sum(p[i]["group"] == p[(i + 1) % len(p)]["group"]
                                  for i in range(len(p))),
                              [c["crop"] for c in p]))
    return list(best)


def recommend(lat, lon, weights, top=5, current=()):
    fp = fingerprint(lat, lon)
    site = site_from_fingerprint(fp)
    crops = load_crops()
    scores = score_crops(crops, site)
    usable = [c for c in crops if scores[c["crop"]]["fit"] >= MIN_CROP_FIT]
    need_lo = min(c["ROPMN"] for c in crops)
    need_hi = max(c["ROPMN"] for c in crops)
    wsum = sum(weights.values())
    if wsum <= 0:
        raise ValueError("at least one priority weight must be above zero")

    by_name = {c["crop"]: c for c in crops}
    unknown = [n for n in current if n not in by_name]
    if unknown:
        raise ValueError(f"unknown crop(s) {unknown}; choose from {sorted(by_name)}")
    keep = [by_name[n] for n in current]

    def score(combo):
        n = len(combo)
        fit = sum((scores[c["crop"]]["fit"] + scores[c["crop"]]["dry_year_fit"]) / 2
                  for c in combo) / n
        checks = soil_checks(combo)
        soil = sum(checks.values()) / len(checks)
        mean_need = sum(c["ROPMN"] for c in combo) / n
        water = (need_hi - mean_need) / (need_hi - need_lo)
        total = (weights["fit"] * fit + weights["soil"] * soil
                 + weights["water"] * water) / wsum
        return (total, fit, soil, water, mean_need, checks, combo)

    def describe(row):
        total, fit, soil, water, mean_need, checks, combo = row
        seq = order_rotation(combo)
        return {
            "rotation": [c["crop"] for c in seq],
            "score": round(total, 3),
            "fit": round(fit, 3), "soil_health": round(soil, 3), "water_saving": round(water, 3),
            "soil_checks": checks,
            "mean_optimal_min_rain_mm": round(mean_need, 0),
            "crops": {c["crop"]: scores[c["crop"]] for c in seq},
        }

    # offered rotations keep every current crop and add at least one more
    pool = usable + [c for c in keep if c not in usable]
    ranked = []
    for n in ROTATION_LENGTHS:
        for combo in itertools.combinations(pool, n):
            if all(k in combo for k in keep) and len(combo) > len(keep):
                ranked.append(score(combo))
    ranked.sort(key=lambda r: (-r[0], [c["crop"] for c in r[6]]))
    recs = [describe(r) for r in ranked[:top]]
    baseline = describe(score(tuple(keep))) if keep else None
    return {
        "lat": lat, "lon": lon, "weights": weights,
        "site": site,
        "criteria": fp["criteria"], "notes": fp["notes"],
        "crop_scores": scores,
        "crops_not_offered": sorted(c["crop"] for c in crops if c not in usable),
        "rotations_considered": len(ranked),
        "current_rotation": baseline,
        "recommendations": recs,
    }


def print_report(res):
    s = res["site"]
    print(f"Site {res['lat']}, {res['lon']}: season mean {s['temp']} C, "
          f"annual rain {s['rain']} mm, soil pH {s['ph']}, texture {s['texture']}, "
          f"frost-free {s['frost_free_days']} days")
    print("Driest years used for the dry-year check: "
          + ", ".join(f"{y} ({r:.0f} mm)" for y, r, _ in s["driest_years"]))
    print(f"Not offered (fit below {MIN_CROP_FIT}): {', '.join(res['crops_not_offered']) or 'none'}")
    print(f"Rotations considered: {res['rotations_considered']}\n")
    rows = [(f"{i}.", r) for i, r in enumerate(res["recommendations"], 1)]
    if res["current_rotation"]:
        rows.insert(0, ("NOW:", res["current_rotation"]))
    for label, r in rows:
        print(f"{label} {' -> '.join(r['rotation'])}   score {r['score']}")
        print(f"   fit {r['fit']} | soil health {r['soil_health']} | water saving {r['water_saving']}")
        met = [k for k, v in r["soil_checks"].items() if v]
        unmet = [k for k, v in r["soil_checks"].items() if not v]
        print(f"   soil checks met: {', '.join(met) or 'none'}")
        if unmet:
            print(f"   not met: {', '.join(unmet)}")
        for name, c in r["crops"].items():
            why = f", limited by {c['limiting_factor']}" if c["limiting_factor"] else ""
            print(f"   - {name}: fit {c['fit']}, dry-year fit {c['dry_year_fit']}{why}")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("lat", type=float)
    ap.add_argument("lon", type=float)
    ap.add_argument("--fit", type=float, default=1.0)
    ap.add_argument("--soil", type=float, default=1.0)
    ap.add_argument("--water", type=float, default=1.0)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--current", default="",
                    help="comma-separated crops grown now, e.g. corn,soybean")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    current = tuple(c.strip() for c in a.current.split(",") if c.strip())
    res = recommend(a.lat, a.lon, {"fit": a.fit, "soil": a.soil, "water": a.water},
                    a.top, current)
    print(json.dumps(res, indent=2) if a.json else "", end="")
    if not a.json:
        print_report(res)


if __name__ == "__main__":
    main()
