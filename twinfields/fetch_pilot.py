"""Download the pilot-area data cube: MODIS greenness + USDA crop history.

Usage:
    python -m twinfields.fetch_pilot <region>     # region from twinfields/regions.py

Writes data/cache/<region>_cube.npz. Skips the download if the file exists.

Sources
    NASA MODIS MOD13Q1/MYD13Q1 v6.1 (250 m, 16-day NDVI/EVI) read from the
    Microsoft Planetary Computer mirror -- no login needed.
    USDA NASS Cropland Data Layer (30 m, yearly) via the CropScape WCS service.

Each MODIS pixel gets, per year, its majority CDL crop class and the share
of its 30 m CDL cells in that class ("purity"), so mixed pixels can be dropped.
"""
from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
import requests
from pyproj import Transformer
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from rasterio.windows import transform as window_transform

from twinfields.regions import REGIONS

FIRST_SEASON, LAST_SEASON = 2015, 2024
MODIS_RANGE = f"{FIRST_SEASON - 1}-10-01/{LAST_SEASON}-12-31"   # includes prior winter
CDL_YEARS = list(range(FIRST_SEASON - 1, LAST_SEASON + 1))
BANDS = ("250m_16_days_NDVI", "250m_16_days_EVI",
         "250m_16_days_pixel_reliability", "250m_16_days_composite_day_of_the_year")

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
CDL_WCS = "https://nassgeodata.gmu.edu/CropScapeService/wms_cdlall.cgi"
CACHE = Path("data/cache")


def fetch_modis(BBOX):
    cat = pystac_client.Client.open(STAC, modifier=pc.sign_inplace)
    items = list(cat.search(collections=["modis-13Q1-061"], bbox=BBOX,
                            datetime=MODIS_RANGE).items())
    # one tile covers the box; keep one item per (platform, composite start)
    seen, uniq = set(), []
    for it in sorted(items, key=lambda i: i.id):
        key = it.id.split(".")[0] + it.id.split(".")[1]
        if key not in seen:
            seen.add(key)
            uniq.append(it)
    items = sorted(uniq, key=lambda i: i.properties["start_datetime"])
    print(f"MODIS: {len(items)} composites", flush=True)

    with rasterio.open(items[0].assets[BANDS[0]].href) as ds:
        crs = ds.crs
        win = from_bounds(*transform_bounds("EPSG:4326", crs, *BBOX),
                          ds.transform).round_offsets().round_lengths()
        tfm = window_transform(win, ds.transform)

    def read(it):
        out = []
        for band in BANDS:
            with rasterio.open(it.assets[band].href) as ds:
                out.append(ds.read(1, window=win))
        return out

    with ThreadPoolExecutor(12) as pool:
        stacks = list(pool.map(read, items))
    arr = {b: np.stack([s[i] for s in stacks]) for i, b in enumerate(BANDS)}
    starts = np.array([it.properties["start_datetime"][:10] for it in items])
    ids = np.array([it.id for it in items])
    return arr, starts, ids, crs, tfm


def fetch_cdl(year: int, region: str, BBOX) -> Path:
    path = CACHE / f"cdl_{region}_{year}.tif"
    if path.exists():
        return path
    x0, y0, x1, y1 = transform_bounds("EPSG:4326", "EPSG:5070", *BBOX)
    # snap to whole 30 m cells so the service returns native-size pixels
    x0, y0 = np.floor(x0 / 30) * 30, np.floor(y0 / 30) * 30
    x1, y1 = np.ceil(x1 / 30) * 30, np.ceil(y1 / 30) * 30
    r = requests.get(CDL_WCS, params={
        "service": "wcs", "version": "1.0.0", "request": "getcoverage",
        "coverage": f"cdl_{year}", "crs": "epsg:5070",
        "bbox": f"{x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}",
        "resx": 30, "resy": 30, "format": "gtiff"}, timeout=180)
    r.raise_for_status()
    if "tiff" not in r.headers.get("content-type", ""):
        raise RuntimeError(f"CDL {year}: unexpected response {r.text[:200]}")
    path.write_bytes(r.content)
    return path


def cdl_per_modis_pixel(path, modis_crs, modis_tfm, shape):
    """Majority CDL class and purity for every MODIS pixel in the window."""
    with rasterio.open(path) as ds:
        cdl = ds.read(1)
        rows, cols = np.indices(cdl.shape)
        xs, ys = rasterio.transform.xy(ds.transform, rows.ravel(), cols.ravel())
        to_modis = Transformer.from_crs(ds.crs, modis_crs, always_xy=True)
    mx, my = to_modis.transform(np.asarray(xs), np.asarray(ys))
    inv = ~modis_tfm
    c, r = inv * (mx, my)
    r, c = np.floor(r).astype(int), np.floor(c).astype(int)
    ok = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
    pix = r[ok] * shape[1] + c[ok]
    cls = cdl.ravel()[ok].astype(np.int64)
    counts = np.zeros((shape[0] * shape[1], 256), dtype=np.int32)
    np.add.at(counts, (pix, cls), 1)
    total = counts.sum(1)
    major = counts.argmax(1)
    purity = np.where(total > 0, counts.max(1) / np.maximum(total, 1), 0.0)
    return (major.reshape(shape).astype(np.uint8),
            purity.reshape(shape).astype(np.float32),
            total.reshape(shape))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in REGIONS:
        sys.exit(f"usage: python -m twinfields.fetch_pilot <{'|'.join(REGIONS)}>")
    region = sys.argv[1]
    BBOX = REGIONS[region]["bbox"]
    OUT = CACHE / f"{region}_cube.npz"
    if OUT.exists():
        print(f"{OUT} exists, skipping")
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    for year in CDL_YEARS:          # small and fast; fail early if the service is down
        fetch_cdl(year, region, BBOX)
    print("CDL rasters cached", flush=True)
    arr, starts, ids, crs, tfm = fetch_modis(BBOX)
    shape = arr[BANDS[0]].shape[1:]

    # pixel-centre lon/lat, and a mask for pixels inside the lat/lon box
    rows, cols = np.indices(shape)
    xs, ys = rasterio.transform.xy(tfm, rows.ravel(), cols.ravel())
    lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(
        np.asarray(xs), np.asarray(ys))
    lon, lat = lon.reshape(shape), lat.reshape(shape)
    inside = ((lon >= BBOX[0]) & (lon <= BBOX[2]) & (lat >= BBOX[1]) & (lat <= BBOX[3]))

    major, purity, ncell = [], [], []
    for year in CDL_YEARS:
        m, p, n = cdl_per_modis_pixel(fetch_cdl(year, region, BBOX), crs, tfm, shape)
        major.append(m); purity.append(p); ncell.append(n)
        print(f"CDL {year}: done", flush=True)

    np.savez_compressed(
        OUT,
        ndvi=arr[BANDS[0]], evi=arr[BANDS[1]], reliability=arr[BANDS[2]],
        doy=arr[BANDS[3]], composite_start=starts, item_ids=ids,
        lon=lon, lat=lat, inside=inside,
        cdl_years=np.array(CDL_YEARS), cdl_major=np.stack(major),
        cdl_purity=np.stack(purity), cdl_cells=np.stack(ncell),
        bbox=np.array(BBOX))
    print(f"wrote {OUT}  cube {arr[BANDS[0]].shape}  inside-box pixels {int(inside.sum())}")


if __name__ == "__main__":
    sys.exit(main())
