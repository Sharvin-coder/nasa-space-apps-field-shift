"""Architecture diagram of the Farm Sight world model, as inline SVG.

A schematic in the style of a research-paper figure: the latent rollout is
drawn unrolled in time, with few labels. architecture_svg() returns one
self-contained <svg>. The app embeds it in the "The model" tab, and
`python -m fieldshift.diagram` writes docs/architecture.svg.
"""
from __future__ import annotations

import html
from pathlib import Path

W, H = 1200, 600
TEXT, MUTED, LINE, BG = "#202124", "#5F6368", "#9AA0A6", "#FFFFFF"
BLUE, BLUE_L, BLUE_BG = "#3B6FD4", "#DCE7FA", "#F4F7FD"      # learned
CORAL, CORAL_L = "#D9604A", "#FBE4DF"                        # rules
AMBER, AMBER_L = "#C98B12", "#FBEFCF"                        # decision
GREY_L = "#ECEEF1"                                           # observed
FONT = "'Libre Franklin', 'Helvetica Neue', Helvetica, Arial, sans-serif"


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _t(x, y, s, size=12, weight=400, fill=MUTED, anchor="middle", extra="") -> str:
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{_e(s)}</text>')


def _cap(x, y, s, fill=MUTED, anchor="start") -> str:
    """Small spaced capitals used as section captions."""
    return _t(x, y, s, 10.5, 700, fill, anchor, ' letter-spacing=".12em"')


def _line(points, color=LINE, width=1.4, dashed=False, head=True) -> str:
    d = " ".join(f"{x},{y}" for x, y in points)
    dash = ' stroke-dasharray="4 4"' if dashed else ""
    end = f' marker-end="url(#h-{color[1:]})"' if head else ""
    return (f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linejoin="round" stroke-linecap="round"{dash}{end}/>')


def _pill(x, y, w, h, fill, stroke, r=12) -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.4"/>')


def architecture_svg() -> str:
    p = []
    heads = "".join(
        f'<marker id="h-{c[1:]}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" '
        f'markerHeight="6.5" orient="auto-start-reverse"><path d="M1 1.5L8.5 5L1 8.5" fill="none" '
        f'stroke="{c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker>'
        for c in (LINE, BLUE, CORAL, AMBER))
    p.append(f"<defs>{heads}</defs>")
    p.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

    # ------------------------------------------------------------ observations
    p.append(_cap(40, 92, "OBSERVATIONS"))
    tracks = [("satellite", 16, 150), ("weather", 5, 185), ("groundwater", 9, 220), ("soil, terrain", 0, 255)]
    for label, step, y in tracks:
        p.append(_t(128, y + 4, label, 12, 400, MUTED, "end"))
        p.append(f'<line x1="140" y1="{y}" x2="236" y2="{y}" stroke="{GREY_L}" stroke-width="7" '
                 f'stroke-linecap="round"/>')
        if step:
            x = 142
            while x <= 234:
                p.append(f'<circle cx="{x}" cy="{y}" r="2.1" fill="{MUTED}"/>')
                x += step
    p.append(_t(188, 284, "each at its own resolution and cadence", 10.5, 400, LINE))

    # ------------------------------------------------------------------ encoder
    p.append(f'<path d="M262 138L322 172V234L262 268Z" fill="{BLUE_L}" stroke="{BLUE}" '
             f'stroke-width="1.4" stroke-linejoin="round"/>')
    p.append(_t(292, 207, "Encoder", 12, 600, TEXT))
    p.append(_line([(240, 203), (258, 203)]))

    # -------------------------------------------------------------- world model
    p.append(f'<rect x="358" y="70" width="520" height="298" rx="18" fill="{BLUE_BG}"/>')
    p.append(_cap(378, 96, "WORLD MODEL", BLUE))
    slow_x, slow_y, fast_y, act_y = (470, 650, 830), 150, 250, 326
    fast_x = [410 + 60 * i for i in range(8)]

    # slow state: one step per year
    for i, x in enumerate(slow_x):
        p.append(f'<circle cx="{x}" cy="{slow_y}" r="21" fill="{BLUE_L}" stroke="{BLUE}" stroke-width="1.6"/>')
        p.append(_t(x, slow_y + 5, "s", 15, 600, BLUE, extra=' font-style="italic"'))
        if i:
            p.append(_line([(slow_x[i - 1] + 23, slow_y), (x - 24, slow_y)], BLUE))
    p.append(_t(slow_x[0], slow_y - 32, "slow state, yearly", 11.5, 600, TEXT))

    # fast state: one step per 16 days
    for i, x in enumerate(fast_x):
        p.append(f'<circle cx="{x}" cy="{fast_y}" r="11" fill="{BG}" stroke="{BLUE}" stroke-width="1.6"/>')
        if i:
            p.append(_line([(fast_x[i - 1] + 12, fast_y), (x - 13, fast_y)], BLUE))
    p.append(_t(398, fast_y - 22, "fast state", 11.5, 600, TEXT, "start"))
    p.append(_t(398, fast_y + 30, "16 days", 10.5, 400, MUTED, "start"))
    # slow conditions fast; the season's end updates slow
    for x in slow_x:
        p.append(_line([(x, slow_y + 22), (x, fast_y - 13)], BLUE, 1.1, dashed=True))
    for a, b in ((590, 650), (770, 830)):
        p.append(_line([(a + 4, fast_y - 11), (b - 17, slow_y + 17)], BLUE, 1.1))

    # actions: the crop planted each year
    for x in slow_x:
        p.append(f'<rect x="{x - 13}" y="{act_y - 13}" width="26" height="26" rx="6" fill="{AMBER_L}" '
                 f'stroke="{AMBER}" stroke-width="1.5"/>')
        p.append(_t(x, act_y + 5, "a", 14, 600, AMBER, extra=' font-style="italic"'))
        p.append(_line([(x, act_y - 14), (x, fast_y + 13)], AMBER))
    p.append(_t(378, act_y + 4, "action: crop", 12, 600, TEXT, "start"))

    p.append(_line([(322, 190), (350, 168), (444, 152)], BLUE))
    p.append(_line([(322, 216), (350, 240), (396, 249)], BLUE))

    # ------------------------------------------------------------------ decoder
    p.append(f'<path d="M898 232L954 204V296L898 268Z" fill="{BLUE_L}" stroke="{BLUE}" '
             f'stroke-width="1.4" stroke-linejoin="round"/>')
    p.append(_t(927, 254, "Dec", 12, 600, TEXT))
    p.append(_line([(842, fast_y), (894, fast_y)], BLUE))
    p.append(_cap(978, 222, "IMAGINED SEASONS"))
    for k, (dy, op) in enumerate(((0, 1), (9, .55), (18, .3))):
        d = f"M978 {262 + dy}C1010 {214 + dy} 1040 {226 + dy} 1066 {246 + dy}S1120 {282 + dy} 1150 {252 + dy}"
        p.append(f'<path d="{d}" fill="none" stroke="{BLUE}" stroke-width="1.8" opacity="{op}" '
                 f'stroke-linecap="round"/>')
    p.append(_line([(958, fast_y), (972, fast_y)], BLUE))

    # ------------------------------------------------------------- rule program
    p.append(_pill(420, 438, 360, 84, CORAL_L, CORAL))
    p.append(_t(600, 468, "Rule program", 14, 700, TEXT))
    p.append(_t(600, 488, "crop ranges · water balance · conservation rules", 11.5, 400, MUTED))
    p.append(_t(600, 505, "ranges may shift by a bounded, learned offset δ", 11.5, 400, CORAL))
    p.append(_line([(560, 438), (560, 372)], CORAL))
    p.append(_line([(640, 372), (640, 436)], BLUE, dashed=True))
    p.append(_t(548, 410, "anchor", 11.5, 600, CORAL, "end"))
    p.append(_t(652, 410, "learns δ", 11.5, 600, BLUE, "start"))

    # ------------------------------------------------------------------ planner
    p.append(_pill(910, 438, 250, 84, AMBER_L, AMBER))
    p.append(_t(1035, 468, "Planner", 14, 700, TEXT))
    p.append(_t(1035, 488, "search over rotations,", 11.5, 400, MUTED))
    p.append(_t(1035, 505, "across a climate ensemble", 11.5, 400, MUTED))
    p.append(_line([(784, 480), (906, 480)], CORAL))
    p.append(_t(845, 471, "mask · verify", 11.5, 600, CORAL))
    p.append(_line([(1064, 292), (1064, 434)], BLUE))
    p.append(_t(1074, 366, "rollouts", 11.5, 600, BLUE, "start"))
    # the planner chooses the action
    p.append(_line([(910, 458), (888, 458), (888, act_y), (847, act_y)], AMBER, dashed=True))
    p.append(_t(896, 398, "chooses", 11.5, 600, AMBER, "start"))
    # output
    p.append(_line([(1035, 522), (1035, 548)], AMBER))
    p.append(_t(1035, 568, "rotation plan, with a calibrated range", 12.5, 600, TEXT))

    # ------------------------------------------------------------------- legend
    lx, ly = 40, 548
    for fill, stroke, label in ((BLUE_L, BLUE, "learned"), (CORAL_L, CORAL, "rules"),
                                (AMBER_L, AMBER, "decision"), (GREY_L, LINE, "observed")):
        p.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="4" fill="{fill}" stroke="{stroke}" '
                 f'stroke-width="1.3"/>')
        p.append(_t(lx + 21, ly + 11.5, label, 11.5, 400, MUTED, "start"))
        lx += 34 + len(label) * 6.6

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="Schematic of the Farm Sight world model. Observations at different '
            f'resolutions are encoded into a latent state with a slow yearly part and a fast '
            f'16-day part. The state is rolled forward given the crop planted. A rule program '
            f'anchors the model and masks and verifies the planner, which searches rotations '
            f'across a climate ensemble and returns a plan with a calibrated range.">'
            f'{"".join(p)}</svg>')


if __name__ == "__main__":
    out = Path("docs/architecture.svg")
    out.parent.mkdir(exist_ok=True)
    out.write_text(architecture_svg(), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
