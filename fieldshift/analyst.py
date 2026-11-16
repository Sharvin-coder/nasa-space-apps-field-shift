"""AI field analyst: a plain-language reading of one field's data.

The analyst (Claude, through the Anthropic API) is given only what the app
already fetched and computed for the pinned field. It interprets; it does not
rank. Rotation scores still come from the rules in recommend.py.

Guard rails
  - The model sees no data beyond the payload built here.
  - Every figure in its answer is checked against the payload; any that do
    not match are returned in "unverified_numbers" so the app can flag them.
  - A per-day cap on calls protects the API key on a public app.

Needs an Anthropic API key (ANTHROPIC_API_KEY). Without one the app simply
does not offer the analyst.
"""
from __future__ import annotations

import json
import re
from datetime import date

MODEL = "claude-opus-5-5"
MAX_CALLS_PER_DAY = 100          # across all visitors of one running app
_calls = {"day": None, "count": 0}

SYSTEM = """You are the field analyst inside Field Shift, a decision-support tool that helps \
farmers compare crop rotations. A farmer has pinned a field on a map. The app fetched \
measurements for that spot from NASA and open data, then scored crop rotations with fixed, \
published rules. You receive all of it as one JSON object.

Your job is to read that data the way a careful agronomy advisor would and tell the farmer \
what it means for their field, in plain words. The farmer can already see every number and \
every score on the page, so your value is interpretation: which few measurements matter most \
here, how they connect to each other, and what they imply for the rotation on offer.

How the scores work, so you can explain them accurately:
- Crop fit compares each crop's published temperature, annual rainfall and soil pH ranges \
(FAO EcoCrop) with this location. "dry_year_fit" repeats that for the three driest of the \
last ten years. "fit_2040" repeats it with temperature and rainfall shifted by the projected \
change for 2035-2044 (NASA NEX-GDDP-CMIP6 ensemble, SSP2-4.5).
- Soil health is the share of four checks met, from USDA NRCS Conservation Practice \
Standard 328: three or more crop functional groups, a legume, a perennial sod crop, and \
high-residue crops in at least half the years.
- Water saving reflects how little rainfall the rotation's crops need.
- Groundwater percentile, slope, aridity and the 2040 fit are shown to the farmer but do not \
change the ranking. That makes them the place where your reading adds the most.

What keeps this trustworthy:
- Use only figures that appear in the JSON, written as they appear there or rounded. Never \
supply a yield, price, cost, date or any other number of your own. If something the farmer \
would want to know is not in the data, say it is not in the data.
- The ranking is fixed. Explain it and point out what it does not account for; do not \
propose a different order or a rotation that is not listed.
- This tool does not forecast yield or profit and knows nothing about markets, equipment or \
local practice. Weather values come from a grid cell about 50 km wide; soil and crop history \
are local to the pin. A null value means the measurement could not be fetched.
- Say plainly when the data points in two directions, or when a result may be an artefact \
of the coarse crop ranges, instead of smoothing it over.

Write three short sections, each two to four sentences, in everyday language a farmer \
would use, with no markdown and no bullet points:
1. "What stands out here": the two or three measurements that most shape this field.
2. "What the shift changes": what the top-ranked rotation does that the current one does \
not, and what limits it.
3. "Before you act": the main risks or gaps for this field, and one or two specific \
questions to take to a local agronomist."""

SCHEMA = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
                "required": ["title", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["sections"],
    "additionalProperties": False,
}


def build_payload(res: dict) -> dict:
    """Everything the analyst is allowed to see, taken from recommend()'s result."""
    c = res["criteria"]

    def rotation(r):
        if r is None:
            return None
        return {
            "rotation": r["rotation"], "overall_score": r["score"],
            "climate_fit": r["fit"], "soil_health": r["soil_health"],
            "water_saving": r["water_saving"],
            "average_crop_fit_today": r["fit_today"], "average_crop_fit_2040": r["fit_2040"],
            "soil_checks": r["soil_checks"],
            "crops": {name: {"fit": s["fit"], "dry_year_fit": s["dry_year_fit"],
                             "fit_2040": s.get("fit_2040"),
                             "limited_by": s["limiting_factor"], "notes": s["notes"]}
                      for name, s in r["crops"].items()},
        }

    site = res["site"]
    return {
        "location": {"lat": res["lat"], "lon": res["lon"]},
        "farmer_priorities_0_to_5": res["weights"],
        "farmer_corrections": site.get("overrides", {}),
        "measurements": {k: v for k, v in c.items() if not k.startswith("_")},
        "growing_season_rain_by_year_mm": c.get("_season_rain_by_year_mm"),
        "groundwater_percentile_by_week": c.get("_groundwater_percentile_by_date"),
        "peak_greenness_ndvi_by_year": c.get("_peak_ndvi_by_year"),
        "three_driest_years_annual_rain_mm": {str(y): r for y, r, _ in site["driest_years"]},
        "soil_texture_class": site["texture"],
        "climate_used_for_2040_fit": site.get("future"),
        "data_sources_that_failed": res["notes"],
        "crops_not_offered_poor_climate_fit": res["crops_not_offered"],
        "current_rotation": rotation(res["current_rotation"]),
        "ranked_options": [rotation(r) for r in res["recommendations"]],
    }


def _numbers_in(obj) -> set[float]:
    found = set()
    if isinstance(obj, bool) or obj is None:
        return found
    if isinstance(obj, (int, float)):
        found.add(float(obj))
    elif isinstance(obj, str):
        found.update(float(m) for m in re.findall(r"-?\d+(?:\.\d+)?", obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            found |= _numbers_in(str(k)) | _numbers_in(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found |= _numbers_in(v)
    return found


# figures the system prompt itself supplies, plus small counts ("two", "3 of 4")
_KNOWN = {50.0, 328.0, 2015.0, 2024.0, 2035.0, 2040.0, 2044.0, 245.0, 4.5, 100.0}


def unverified_numbers(text: str, payload: dict) -> list[str]:
    """Figures in the text that match nothing in the payload, even after rounding."""
    known = _numbers_in(payload)
    flagged = []
    for token in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        clean = token.replace(",", "").rstrip(".")
        value = float(clean)
        decimals = len(clean.split(".")[1]) if "." in clean else 0
        if value in _KNOWN or (decimals == 0 and value <= 10):
            continue
        if any(round(abs(k), decimals) == value or round(abs(k) * 100, decimals) == value
               for k in known):
            continue
        if token not in flagged:
            flagged.append(token)
    return flagged


def analyse(res: dict, api_key: str) -> dict:
    """Ask the model for a reading of this field. Returns
    {"sections": [{"title", "text"}], "unverified_numbers": [...], "model": str}."""
    import anthropic

    today = date.today().isoformat()
    if _calls["day"] != today:
        _calls.update(day=today, count=0)
    if _calls["count"] >= MAX_CALLS_PER_DAY:
        raise RuntimeError("The AI analyst has reached its daily limit. Try again tomorrow.")
    _calls["count"] += 1

    payload = build_payload(res)
    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium",
                           "format": {"type": "json_schema", "schema": SCHEMA}},
            # if a safety classifier declines, re-run on Anthropic's recommended fallback
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": json.dumps(payload, sort_keys=True)}],
        )
    except anthropic.AuthenticationError as exc:
        raise RuntimeError("The AI analyst's API key was rejected.") from exc
    except anthropic.RateLimitError as exc:
        raise RuntimeError("The AI analyst is busy. Try again in a minute.") from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(f"The AI service returned an error ({exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise RuntimeError("Could not reach the AI service.") from exc

    if response.stop_reason == "refusal":
        raise RuntimeError("The AI analyst declined to answer for this field.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("The AI analyst's answer was cut off. Try again.")
    text = next(b.text for b in response.content if b.type == "text")
    sections = json.loads(text)["sections"]
    body = " ".join(s["title"] + " " + s["text"] for s in sections)
    return {"sections": sections,
            "unverified_numbers": unverified_numbers(body, payload),
            "model": response.model}
