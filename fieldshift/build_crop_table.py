"""Build fieldshift/crops.csv from the FAO EcoCrop database.

Usage:
    python -m fieldshift.build_crop_table

Needs data/raw/ecocrop/EcoCrop_DB.csv (FAO EcoCrop, copy hosted at
https://github.com/OpenCLIM/ecocrop). Requirement ranges are copied from
EcoCrop unchanged. The three agronomic labels below are ours and should be
reviewed by an agronomist:
    group      functional group, as used in USDA NRCS Conservation Practice
               Standard 328 (warm/cool season x grass/broadleaf)
    residue    high or low crop residue
    perennial  multi-year sod/forage crop
Legume status is taken from the EcoCrop family name.
"""
import csv
from pathlib import Path

RAW = Path("data/raw/ecocrop/EcoCrop_DB.csv")
OUT = Path(__file__).with_name("crops.csv")

# EcoCrop scientific name -> (common name, functional group, residue, perennial)
CROPS = {
    "Zea mays ssp. mays":   ("corn",        "warm_grass",     "high", False),
    "Sorghum bicolor":      ("sorghum",     "warm_grass",     "high", False),
    "Panicum miliaceum":    ("proso millet", "warm_grass",    "high", False),
    "Triticum aestivum":    ("wheat",       "cool_grass",     "high", False),
    "Avena sativa":         ("oats",        "cool_grass",     "high", False),
    "Hordeum vulgare":      ("barley",      "cool_grass",     "high", False),
    "Secale cereale":       ("rye",         "cool_grass",     "high", False),
    "Glycine max":          ("soybean",     "warm_broadleaf", "low",  False),
    "Phaseolus vulgaris":   ("dry bean",    "warm_broadleaf", "low",  False),
    "Helianthus annuus":    ("sunflower",   "warm_broadleaf", "low",  False),
    "Gossypium hirsutum":   ("cotton",      "warm_broadleaf", "low",  False),
    "Pisum sativum":        ("field pea",   "cool_broadleaf", "low",  False),
    "Lens culinaris":       ("lentil",      "cool_broadleaf", "low",  False),
    "Cicer arietinum":      ("chickpea",    "cool_broadleaf", "low",  False),
    "Brassica napus":       ("canola",      "cool_broadleaf", "low",  False),
    "Medicago sativa":      ("alfalfa",     "cool_broadleaf", "high", True),
    "Trifolium pratense":   ("red clover",  "cool_broadleaf", "high", True),
}
NUMERIC = ["TOPMN", "TOPMX", "TMIN", "TMAX", "ROPMN", "ROPMX", "RMIN", "RMAX",
           "PHOPMN", "PHOPMX", "PHMIN", "PHMAX", "GMIN", "GMAX"]


def main():
    rows = {r["ScientificName"]: r
            for r in csv.DictReader(RAW.open(encoding="latin-1"))}
    fields = ["crop", "scientific_name", "group", "legume", "residue", "perennial",
              *NUMERIC, "TEXTR"]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for sci, (name, group, residue, perennial) in CROPS.items():
            r = rows[sci]                       # KeyError if the species is missing
            for k in NUMERIC:
                float(r[k])                     # fail loudly on a missing value
            w.writerow({"crop": name, "scientific_name": sci, "group": group,
                        "legume": "Leguminosae" in r["FAMNAME"],
                        "residue": residue, "perennial": perennial,
                        **{k: r[k] for k in NUMERIC}, "TEXTR": r["TEXTR"]})
    print(f"wrote {OUT} ({len(CROPS)} crops)")


if __name__ == "__main__":
    main()
