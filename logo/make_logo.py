"""Draw the slitherFlow hex logo: a snake whose body is a three-line subway trunk.

    python3 logo/make_logo.py                       -> logo/slitherflow_hex.svg
    rsvg-convert -w 1200 logo/slitherflow_hex.svg -o logo/slitherflow_hex.png
"""
import math
from pathlib import Path

W, H = 520, 600
CX, CY, R_HEX = 260, 300, 288
BG, INK, MUTED = "#1b2430", "#1f2328", "#9aa4b1"
GREEN, ORANGE, PINK, VERMILION = "#009E73", "#E69F00", "#CC79A7", "#D55E00"
FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"

out = []
add = out.append

# ---- hexagon (pointy top) ----
hexpts = [(CX + R_HEX * math.cos(math.radians(a)), CY + R_HEX * math.sin(math.radians(a)))
          for a in (-90, -30, 30, 90, 150, 210)]
hex_d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in hexpts) + " Z"

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
add(f'<defs><clipPath id="hex"><path d="{hex_d}"/></clipPath></defs>')
add(f'<path d="{hex_d}" fill="{BG}"/>')

# ---- faint map: street grid + a couple of "avenues" ----
add('<g clip-path="url(#hex)" stroke="#ffffff" fill="none">')
for x in range(-20, W + 40, 40):
    add(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke-opacity="0.045" stroke-width="1.2"/>')
for y in range(-20, H + 40, 40):
    add(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke-opacity="0.045" stroke-width="1.2"/>')
add('<path d="M-10,470 L120,340 L120,60" stroke-opacity="0.07" stroke-width="6" stroke-linejoin="round"/>')
add('<path d="M430,600 L430,480 L560,350" stroke-opacity="0.07" stroke-width="6" stroke-linejoin="round"/>')
add('</g>')


# ---- the snake: three parallel lines following one centreline with rounded 90-degree bends ----
def offset_path(pts, d, R):
    """Path parallel to polyline pts (offset d to the left of travel), corners rounded so all offsets stay parallel."""
    n = len(pts)
    segs = []
    for i in range(n - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        L = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        nx, ny = uy, -ux                       # left normal (screen coordinates, y down)
        segs.append(((x1 + nx * d, y1 + ny * d), (x2 + nx * d, y2 + ny * d), (ux, uy)))
    d_str = f"M{segs[0][0][0]:.1f},{segs[0][0][1]:.1f}"
    for i in range(len(segs) - 1):
        (_, b, u1), (a2, _, u2) = segs[i], segs[i + 1]
        cross = u1[0] * u2[1] - u1[1] * u2[0]   # < 0: left turn on screen
        r = R - d if cross < 0 else R + d       # inside of the bend gets the tighter radius
        # corner point = intersection of the two offset segments (90-degree bends)
        cx = b[0] if abs(u1[0]) < 1e-9 else a2[0]
        cy = b[1] if abs(u1[1]) < 1e-9 else a2[1]
        p1 = (cx - u1[0] * r, cy - u1[1] * r)
        p2 = (cx + u2[0] * r, cy + u2[1] * r)
        d_str += f" L{p1[0]:.1f},{p1[1]:.1f} Q{cx:.1f},{cy:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    end = segs[-1][1]
    d_str += f" L{end[0]:.1f},{end[1]:.1f}"
    return d_str


# tail (bottom left) -> right -> up -> left -> up -> right -> head (top right): an S
spine = [(146, 392), (360, 392), (360, 272), (142, 272), (142, 152), (362, 152)]
R_BEND, GAP, LW = 58, 14, 10
for d, color in [(GAP, ORANGE), (0, GREEN), (-GAP, PINK)]:
    add(f'<path d="{offset_path(spine, d, R_BEND)}" fill="none" stroke="{color}" stroke-width="{LW}" '
        f'stroke-linecap="butt" stroke-linejoin="round"/>')

# tail: the stripes end in a tapered, slightly upturned green tip
tx, ty = spine[0]
half = GAP + LW / 2
add(f'<path d="M{tx + 2},{ty - half} C{tx - 30},{ty - half + 2} {tx - 62},{ty - 4} {tx - 86},{ty - 14} '
    f'C{tx - 64},{ty + 6} {tx - 34},{ty + half} {tx + 2},{ty + half} Z" fill="{GREEN}"/>')

# head (top right), facing right, with eye and forked tongue
hx, hy = spine[-1]
add(f'<path d="M{hx + 60},{hy + 3} l20,0 l11,-9 M{hx + 80},{hy + 3} l11,9" fill="none" stroke="{VERMILION}" '
    f'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')
add(f'<path d="M{hx - 6},{hy - GAP - LW / 2} C{hx + 24},{hy - 36} {hx + 60},{hy - 24} {hx + 64},{hy + 2} '
    f'C{hx + 60},{hy + 26} {hx + 24},{hy + 36} {hx - 6},{hy + GAP + LW / 2} Z" fill="{GREEN}"/>')
add(f'<circle cx="{hx + 32}" cy="{hy - 9}" r="8" fill="#ffffff"/>')
add(f'<circle cx="{hx + 34.5}" cy="{hy - 9}" r="4" fill="{INK}"/>')

# stations: pills across the three lines, one per straight
def pill(x, y, vertical=True):
    w, h = (24, 2 * GAP + LW + 22) if vertical else (2 * GAP + LW + 22, 24)
    add(f'<rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="12" fill="#ffffff" '
        f'stroke="{INK}" stroke-width="4"/>')

pill(252, 392)
pill(250, 272)
pill(250, 152)

# ---- name ----
add(f'<text x="{CX}" y="490" font-family="{FONT}" font-size="50" font-weight="800" text-anchor="middle" '
    f'letter-spacing="-0.5"><tspan fill="#ffffff">slither</tspan><tspan fill="{GREEN}">Flow</tspan></text>')
add(f'<text x="{CX}" y="514" font-family="{FONT}" font-size="11.5" font-weight="600" text-anchor="middle" '
    f'fill="{MUTED}" letter-spacing="1.2">SNAKEMAKE · SUBWAY MAPS</text>')

# ---- border on top ----
add(f'<path d="{hex_d}" fill="none" stroke="{GREEN}" stroke-width="14" stroke-linejoin="round"/>')
add("</svg>")

dest = Path(__file__).with_name("slitherflow_hex.svg")
dest.write_text("\n".join(out))
print(f"wrote {dest}")
