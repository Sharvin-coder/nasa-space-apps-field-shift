"""Architecture diagram of the proposed Farm Sight world model, as inline SVG.

architecture_svg() returns one self-contained <svg>. The app embeds it in the
"The model" tab, and `python -m fieldshift.diagram` writes docs/architecture.svg.
"""
from __future__ import annotations

import html
from pathlib import Path

W, H = 1250, 1090
GUTTER = 30          # extra canvas each side for connectors
INK, INK2, PAPER, RULE = "#1F150D", "#5B4A39", "#F0EDE2", "#B9A98C"
# kind -> (accent, tint)
KINDS = {
    "data": ("#256B36", "#DDEBD3"),
    "neural": ("#1B4A7C", "#D5E4F3"),
    "symbolic": ("#D2452F", "#F6DAD3"),
    "search": ("#B9860B", "#FAE9B8"),
    "output": ("#39230F", "#E6D5B8"),
}
SANS = "'Libre Franklin', 'Helvetica Neue', Arial, sans-serif"
SERIF = "Besley, Georgia, serif"


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _text(x, y, s, size=11.5, weight=400, fill=INK, anchor="start", family=SANS, extra="") -> str:
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{_e(s)}</text>')


def _box(x, y, w, h, kind, title, lines=(), title_size=13.5) -> str:
    accent, tint = KINDS[kind]
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{tint}" stroke="{accent}" '
           f'stroke-width="1.5"/>',
           f'<rect x="{x}" y="{y}" width="6" height="{h}" fill="{accent}"/>',
           _text(x + 16, y + 21, title, title_size, 700)]
    for i, line in enumerate(lines):
        out.append(_text(x + 16, y + 39 + i * 15, line, 11.5, 400, INK2))
    return "".join(out)


def _frame(x, y, w, h, kind, label) -> str:
    accent, _ = KINDS[kind]
    tag_w = 14 + len(label) * 7.9
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{accent}" '
            f'stroke-width="1.5" stroke-dasharray="6 4"/>'
            f'<rect x="{x + 14}" y="{y - 10}" width="{tag_w:.0f}" height="20" fill="{accent}"/>'
            + _text(x + 19, y + 4, label, 11, 700, PAPER, extra=' letter-spacing=".06em"'))


def _arrow(points, kind="output", dashed=False, label="", label_at=None, anchor="start") -> str:
    accent = KINDS[kind][0] if kind in KINDS else kind
    d = " ".join(f"{x},{y}" for x, y in points)
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    out = (f'<polyline points="{d}" fill="none" stroke="{accent}" stroke-width="1.8"{dash} '
           f'marker-end="url(#arrow-{accent[1:]})"/>')
    if label and label_at:
        lw = len(label) * 6.1 + 10
        lx = label_at[0] - (lw / 2 if anchor == "middle" else 5 if anchor == "start" else lw - 5)
        out += (f'<rect x="{lx:.0f}" y="{label_at[1] - 12}" width="{lw:.0f}" height="17" '
                f'fill="{PAPER}"/>'
                + _text(label_at[0], label_at[1], label, 10.5, 650, accent, anchor))
    return out


def architecture_svg() -> str:
    p = []
    markers = "".join(
        f'<marker id="arrow-{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{c}"/></marker>'
        for c in {a for a, _t in KINDS.values()})
    p.append(f'<defs>{markers}</defs>')
    p.append(f'<rect x="{-GUTTER}" width="{W + 2 * GUTTER}" height="{H}" fill="{PAPER}"/>')

    # ---------------------------------------------------------------- header
    p.append(_text(20, 32, "The Farm Sight world model", 21, 800, INK, family=SERIF))
    p.append(_text(20, 51, "Proposed neurosymbolic architecture",
                   12, 500, INK2))
    lx = 690
    for kind, name in (("data", "data"), ("neural", "neural (learned)"),
                       ("symbolic", "symbolic (rules)"), ("search", "search"),
                       ("output", "output")):
        accent, tint = KINDS[kind]
        p.append(f'<rect x="{lx}" y="22" width="13" height="13" fill="{tint}" stroke="{accent}" '
                 f'stroke-width="1.5"/>')
        p.append(_text(lx + 19, 33, name, 11.5, 600))
        lx += 32 + len(name) * 6.6

    # ---------------------------------------------------------- 1 observations
    p.append(_frame(10, 82, W - 20, 112, "data", "1  OBSERVATIONS, EACH AT ITS OWN SHARPNESS AND TEMPO"))
    chips = [
        ("Greenness", "MODIS 250 m, HLS 30 m", "every 16 days"),
        ("Weather", "NASA POWER, ~50 km", "daily"),
        ("Groundwater", "GRACE-FO, ~25 km", "weekly"),
        ("Soil moisture", "SMAP, ~9 km (planned)", "every 2 to 3 days"),
        ("Soil", "SoilGrids, 250 m", "fixed"),
        ("Terrain", "SRTM, 30 m", "fixed"),
        ("Crop planted", "USDA crop maps, 30 m", "yearly: the action"),
    ]
    cw, gap, x0 = 164, 10, 22
    for i, (title, a, b) in enumerate(chips):
        x = x0 + i * (cw + gap)
        p.append(_box(x, 102, cw, 78, "search" if i == 6 else "data", title, (a, b), 13))
        if i < 6:
            p.append(_arrow([(x + cw / 2, 180), (x + cw / 2, 226)], "data"))

    # ------------------------------------------------- 2 harmonizer + encoders
    p.append(_frame(10, 218, 1042, 92, "neural", "2  ONE GRID, THEN ENCODE"))
    p.append(_box(22, 236, 330, 62, "data", "Harmonizer",
                  ("one row per field per 16 days; every value",
                   "tagged with its native cell size and cadence")))
    p.append(_box(364, 236, 330, 62, "neural", "Imagery encoder (frozen)",
                  ("geospatial foundation model of the",
                   "Prithvi-EO-2.0 class, on 30 m patches")))
    p.append(_box(706, 236, 334, 62, "neural", "Forcing and static encoders",
                  ("temporal network for weather and water;",
                   "embedding for soil and terrain")))
    p.append(_arrow([(352, 267), (364, 267)], "neural"))
    p.append(_arrow([(694, 267), (706, 267)], "neural"))
    p.append(_arrow([(530, 310), (530, 362)], "neural"))

    # --------------------------------------------------------- 3 world model
    p.append(_frame(250, 352, 660, 250, "neural", "3  WORLD MODEL: HOW THE FIELD CHANGES"))
    p.append(_box(268, 374, 300, 92, "neural", "Slow state  z_slow",
                  ("soil condition, water table, and the residue",
                   "and nitrogen legacy of earlier crops",
                   "clock: one step per year")))
    p.append(_box(592, 374, 300, 92, "neural", "Fast state  z_fast",
                  ("canopy and root-zone water",
                   "",
                   "clock: one step per 16 days")))
    p.append(_arrow([(568, 408), (592, 408)], "neural"))
    p.append(_arrow([(592, 432), (568, 432)], "neural"))
    p.append(_box(268, 490, 624, 96, "neural", "Action-conditioned transition (stochastic), rolled forward step by step",
                  ("z_fast(t+1) ~ p( · | z_fast(t), z_slow(y), weather(t), crop(y) )",
                   "z_slow(y+1) = g( z_slow(y), season summary, crop(y) )",
                   "trained in latent space (JEPA style): predict the encoding of the next observation")))
    p.append(_arrow([(418, 466), (418, 490)], "neural"))
    p.append(_arrow([(742, 490), (742, 466)], "neural"))
    # roll-forward loop on the right edge of the frame
    p.append(_arrow([(892, 538), (902, 538), (902, 420), (892, 420)], "neural"))

    # left: what drives it
    p.append(_box(20, 374, 206, 92, "search", "Action  a",
                  ("the crop planted each year;", "known from crop maps in training,",
                   "chosen by the planner afterwards")))
    p.append(_box(20, 490, 206, 96, "data", "Forcing  w",
                  ("observed weather in training;", "afterwards one climate model at",
                   "a time, or a replayed past year")))
    p.append(_arrow([(226, 420), (250, 420), (250, 520), (268, 520)], "search"))
    p.append(_arrow([(226, 550), (268, 550)], "data"))
    # the crop-planted chip feeds the action box
    crop_x = x0 + 6 * (cw + gap) + cw / 2
    p.append(_arrow([(crop_x, 180), (crop_x, 330), (122, 330), (122, 374)], "search", dashed=True,
                    label="the crop label becomes the action", label_at=(860, 334), anchor="middle"))

    # right: decoders and training signals
    p.append(_box(934, 374, 296, 62, "neural", "Decoders",
                  ("predicted greenness curve and soil", "moisture, one rollout per possible season")))
    p.append(_arrow([(910, 405), (934, 405)], "neural"))
    p.append(_box(934, 452, 296, 150, "neural", "Training signals",
                  ("1  latent prediction of the next step",
                   "2  error against the next observation",
                   "3  water-balance violation (physics)",
                   "4  twin-field contrast: neighbours with",
                   "    different crops, same weather and soil",
                   "5  sparsity on the rule offsets",
                   "all labels are public; no yield records")))

    # ---------------------------------------------------------- 4 rule program
    p.append(_frame(10, 648, W - 20, 124, "symbolic", "4  RULE PROGRAM: PUBLISHED KNOWLEDGE, EXECUTABLE"))
    rw, rgap = 296, 10
    rules = [
        ("Crop envelopes", ("FAO EcoCrop ranges as fuzzy predicates:",
                            "1 inside optimal, 0 outside absolute;",
                            "fit is the minimum over factors")),
        ("Bounded offsets  δ  (learned)", ("per region, crop and factor;",
                                           "|δ| ≤ β × range width, pushed to zero;",
                                           "the only learnable rule, and readable")),
        ("Physical checks", ("water balance: rain − evapotranspiration",
                             "− runoff; frost-free season at least",
                             "as long as the crop's cycle")),
        ("Conservation and farmer rules", ("USDA NRCS 328: plant groups, legume,",
                                           "sod crop, residue; plus crops the",
                                           "farmer cannot grow")),
    ]
    for i, (title, lines) in enumerate(rules):
        p.append(_box(22 + i * (rw + rgap), 668, rw, 90, "symbolic", title, lines))
    # anchor: rules <-> world model
    p.append(_arrow([(170, 668), (170, 622), (420, 622), (420, 586)], "symbolic",
                    label="ANCHOR: the network predicts only a correction to the rule fit",
                    label_at=(190, 626)))
    p.append(_arrow([(640, 586), (640, 630), (476, 630), (476, 668)], "neural", dashed=True,
                    label="gradient moves δ", label_at=(650, 634)))

    # -------------------------------------------------------------- 5 planner
    p.append(_frame(10, 818, W - 20, 108, "search", "5  PLANNER"))
    steps = [
        ("Candidate rotations", ("2 to 4 crops, keeping what is", "grown now")),
        ("Ensemble rollouts", ("each climate model separately,", "plus replayed past years")),
        ("Risk-aware score", ("farmer priorities on the average", "and on the bad tail (CVaR)")),
        ("Calibration", ("conformal intervals tested on", "held-out years")),
    ]
    for i, (title, lines) in enumerate(steps):
        x = 22 + i * (rw + rgap)
        p.append(_box(x, 838, rw, 74, "search", title, lines))
        if i:
            p.append(_arrow([(x - rgap, 875), (x, 875)], "search"))
    p.append(_arrow([(200, 758), (200, 838)], "symbolic",
                    label="MASK: never propose a crop the rules exclude", label_at=(210, 788)))
    p.append(_arrow([(1230, 405), (1266, 405), (1266, 796), (476, 796), (476, 838)],
                    "neural", label="rollouts: many possible seasons", label_at=(990, 800)))

    # -------------------------------------------------------------- 6 outputs
    p.append(_frame(10, 972, W - 20, 104, "output", "6  WHAT THE FARMER AND THE AGRONOMIST GET"))
    ow = 398
    outs = [
        ("Rule trace and evidence", ("rules that fired, the correction applied,", "and similar past field-years")),
        ("Revised envelope table", ("which crop ranges the data moved,", "where, and by how much")),
        ("Ranked rotations, with ranges", ("an expected outcome and a calibrated", "interval for each option")),
    ]
    for i, (title, lines) in enumerate(outs):
        p.append(_box(22 + i * (ow + 6), 992, ow, 70, "output", title, lines))
    p.append(_arrow([(956, 912), (956, 992)], "search"))
    p.append(_arrow([(1236, 740), (1252, 740), (1252, 1027), (1228, 1027)], "symbolic",
                    label="VERIFY: a plan that breaks a rule is rejected", label_at=(1244, 950),
                    anchor="end"))
    # feedback: agronomist reviews corrections
    p.append(_arrow([(620, 992), (620, 946), (-14, 946), (-14, 712), (22, 712)], "output", dashed=True,
                    label="agronomist accepts or strikes out each correction", label_at=(30, 950)))

    body = "".join(p)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-GUTTER} 0 {W + 2 * GUTTER} {H}" role="img" '
            f'aria-label="Architecture of the proposed Farm Sight world model: observations are '
            f'harmonized and encoded, a two-clock world model predicts how the field changes '
            f'given the crop and the weather, a rule program anchors, masks and verifies it, '
            f'and a planner searches rotations across climate models.">{body}</svg>')


if __name__ == "__main__":
    out = Path("docs/architecture.svg")
    out.parent.mkdir(exist_ok=True)
    out.write_text(architecture_svg(), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
