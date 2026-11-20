#!/usr/bin/env python3
"""slitherFlow: draw any Snakemake pipeline as an nf-core-style subway (metro) map.

    slitherflow auto   PROJECT_DIR [-o map.svg] [--png] [--pdf] [-- SNAKEMAKE ARGS]
    slitherflow draft  PROJECT_DIR [-o spec.yaml] [--rulegraph FILE.dot] [-- SNAKEMAKE ARGS]
    slitherflow render SPEC.yaml   [-o map.svg] [--png] [--pdf] [--strict]

`auto` and `draft` run `snakemake --rulegraph --nolock` inside PROJECT_DIR; anything after `--` is passed
to Snakemake (e.g. `-- --configfile config/test.yaml`). Needs Python 3 + PyYAML; --png/--pdf need rsvg-convert.
"""
import argparse
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

# Okabe-Ito palette (colour-blind safe), in the order lines are given colours
PALETTE = ["#009E73", "#E69F00", "#CC79A7", "#D55E00", "#56B4E9", "#0072B2", "#F0E442", "#000000"]

STYLE = {
    "font": "'Helvetica Neue', Helvetica, Arial, sans-serif",
    "ink": "#1f2328", "muted": "#59636e", "faint": "#8c959f", "rule": "#d0d7de",
    "line_width": 7,        # width of every line
    "gap": 10,              # spacing between parallel lines on the trunk
    "spacing": 170,         # distance between trunk stations
    "branch_spacing": 140,  # distance between stations on a branch
    "row_height": 130,      # vertical distance per row (row 1 = one row below the trunk)
    "corner": 22,           # corner radius of 90-degree bends
    "dash": "16 9",         # optional lines
    "margin": 48,
    "station_radius": 11,
}

LABEL_OFFSET = 34            # station centre -> station name baseline
TOOL_OFFSET = 17             # station name -> tool line
ICON_W, ICON_H = 46, 58


def text_width(s, size, bold=False):
    """Rough rendered width of Helvetica text (good enough for layout and overlap checks)."""
    return len(s) * size * (0.58 if bold else 0.53)   # calibrated on rsvg-convert renders


class Canvas:
    """Collects SVG elements and remembers what was drawn where, for extents and overlap checks."""

    def __init__(self, style):
        self.s = style
        self.out = []
        self.texts, self.icons, self.lines, self.stations = [], [], [], []
        self.xmin = self.ymin = math.inf
        self.xmax = self.ymax = -math.inf

    def _extend(self, x0, y0, x1, y1):
        self.xmin, self.ymin = min(self.xmin, x0), min(self.ymin, y0)
        self.xmax, self.ymax = max(self.xmax, x1), max(self.ymax, y1)

    def text(self, x, y, s, size=15, bold=False, fill=None, anchor="middle", desc=None, track=True):
        if s is None or s == "":
            return
        s = str(s)
        w = text_width(s, size, bold)
        x0 = {"middle": x - w / 2, "start": x, "end": x - w}[anchor]
        box = (x0, y - size * 0.78, x0 + w, y + size * 0.22)
        if track:
            self.texts.append((box, desc or s))
            self._extend(*box)
        self.out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{self.s["font"]}" font-size="{size}" '
                        f'font-weight="{"700" if bold else "400"}" fill="{fill or self.s["ink"]}" '
                        f'text-anchor="{anchor}">{escape(s)}</text>')

    def polyline(self, pts, color, desc, dashed=False, casing=False, radius=None):
        r = self.s["corner"] if radius is None else radius
        d = rounded_path(pts, r)
        lw = self.s["line_width"]
        if casing:  # white halo so crossings read as a bridge
            self.out.append(f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="{lw + 8}" '
                            f'stroke-linecap="round" stroke-linejoin="round"/>')
        da = f' stroke-dasharray="{self.s["dash"]}"' if dashed else ""
        self.out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{lw}" '
                        f'stroke-linecap="round" stroke-linejoin="round"{da}/>')
        self.lines.append((pts, desc))
        for x, y in pts:
            self._extend(x - lw, y - lw, x + lw, y + lw)

    def station(self, x, y, members, optional=False, desc=""):
        r = self.s["station_radius"]
        da = ' stroke-dasharray="4 3"' if optional else ""
        self.out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#ffffff" stroke="{self.s["ink"]}" '
                        f'stroke-width="3.2"{da}/>')
        self.stations.append(((x - r, y - r, x + r, y + r), set(members), desc))

    def pill(self, x, y1, y2, members, w=26, desc=""):
        self.out.append(f'<rect x="{x - w / 2:.1f}" y="{y1 - w / 2:.1f}" width="{w}" height="{y2 - y1 + w:.1f}" '
                        f'rx="{w / 2}" fill="#ffffff" stroke="{self.s["ink"]}" stroke-width="3.2"/>')
        self.stations.append(((x - w / 2, y1 - w / 2, x + w / 2, y2 + w / 2), set(members), desc))
        self._extend(x - w / 2, y1 - w / 2, x + w / 2, y2 + w / 2)

    def file_icon(self, cx, cy, tag, color, desc):
        w, h, f = ICON_W, ICON_H, 13
        x, y = cx - w / 2, cy - h / 2
        ink = self.s["ink"]
        self.out.append(f'<path d="M{x:.1f},{y:.1f} H{x + w - f:.1f} L{x + w:.1f},{y + f:.1f} V{y + h:.1f} H{x:.1f} Z" '
                        f'fill="#ffffff" stroke="{ink}" stroke-width="2.2" stroke-linejoin="round"/>')
        self.out.append(f'<path d="M{x + w - f:.1f},{y:.1f} V{y + f:.1f} H{x + w:.1f}" fill="none" stroke="{ink}" '
                        f'stroke-width="2.2" stroke-linejoin="round"/>')
        tag_w = max(w + 10, text_width(tag, 11, True) + 10)
        self.out.append(f'<rect x="{cx - tag_w / 2:.1f}" y="{cy - 2:.1f}" width="{tag_w:.1f}" height="18" rx="3" fill="{color}"/>')
        self.text(cx, cy + 12, tag, 11, True, "#ffffff", track=False)
        box = (cx - tag_w / 2, y, cx + tag_w / 2, y + h)
        self.icons.append((box, desc))
        self._extend(*box)

    def connector(self, x1, y1, x2, y2):
        self.out.append(f'<path d="M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}" fill="none" stroke="{self.s["faint"]}" '
                        f'stroke-width="2" stroke-dasharray="2 4" stroke-linecap="round"/>')


def rounded_path(pts, r):
    """SVG path through pts with every corner rounded (radius r, limited by segment lengths)."""
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1, l2 = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
        if l1 == 0 or l2 == 0:
            continue
        rr = min(r, l1 / 2, l2 / 2)
        ax, ay = x1 - (x1 - x0) / l1 * rr, y1 - (y1 - y0) / l1 * rr
        bx, by = x1 + (x2 - x1) / l2 * rr, y1 + (y2 - y1) / l2 * rr
        d += f" L{ax:.1f},{ay:.1f} Q{x1:.1f},{y1:.1f} {bx:.1f},{by:.1f}"
    d += f" L{pts[-1][0]:.1f},{pts[-1][1]:.1f}"
    return d


def wrap_words(s, max_chars):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + ([cur] if cur else [])


def two_lines(label):
    """Split an output label over two lines at the space nearest the middle."""
    label = str(label)
    if "\n" in label:
        return label.split("\n")[:2]
    if len(label) <= 10 or " " not in label:
        return [label]
    mid = len(label) / 2
    cut = min((i for i, c in enumerate(label) if c == " "), key=lambda i: abs(i - mid))
    return [label[:cut], label[cut + 1:]]


# ----------------------------------------------------------------------------------------------------------------
# Layout + drawing
# ----------------------------------------------------------------------------------------------------------------
def render(spec):
    s = dict(STYLE, **(spec.get("style") or {}))
    cv = Canvas(s)
    m, lw, gap, rh = s["margin"], s["line_width"], s["gap"], s["row_height"]

    lines = spec.get("lines") or {}
    for i, (lid, ln) in enumerate(lines.items()):
        ln.setdefault("name", lid)
        ln.setdefault("color", PALETTE[i % len(PALETTE)])
        ln.setdefault("stations", [])
    trunk = spec.get("trunk") or {}
    trunk_stations = trunk.get("stations") or []
    trunk_lines = trunk.get("lines") or [lid for lid, ln in lines.items() if ln.get("from", "trunk") == "trunk"]
    for lid in trunk_lines:
        if lid not in lines:
            sys.exit(f"trunk.lines names '{lid}', which is not under lines:")
        lines[lid]["from"] = "trunk"
    for k, lid in enumerate(trunk_lines):  # default rows: spread trunk lines -1, 0, +1, ...
        lines[lid].setdefault("row", k - (len(trunk_lines) - 1) / 2)
    # stack trunk lines by the row they branch to (top row first), so they never cross when they split
    trunk_lines = sorted(trunk_lines, key=lambda lid: lines[lid]["row"])
    for lid, ln in lines.items():
        ln.setdefault("row", 0)
        ln.setdefault("to", "none")
    term = spec.get("terminus")

    # ---- vertical placement ----
    rows = [ln["row"] for ln in lines.values()] + ([term.get("row", 0)] if term else [])
    min_row = min(rows + [0])
    y0 = max(250, 160 - min_row * rh)
    if spec.get("title") is None:
        y0 -= 60
    ntl = max(len(trunk_lines), 1)
    trunk_y = {lid: y0 + (k - (ntl - 1) / 2) * gap for k, lid in enumerate(trunk_lines)}
    trunk_top, trunk_bot = y0 - (ntl - 1) / 2 * gap, y0 + (ntl - 1) / 2 * gap
    row_y = lambda row: y0 + row * rh

    # ---- trunk stations (x) ----
    inp = spec.get("input")
    x_in = m + 64 if inp else m
    pos = {}  # (line id or 'trunk', station name) -> (x, y)
    x = x_in + 0.8 * s["spacing"]
    for st in trunk_stations:
        x = st.get("x", x + st.get("gap", 0))
        st["_x"] = x
        pos[("trunk", st["name"])] = (x, y0)
        x += s["spacing"]
    last_trunk_x = trunk_stations[-1]["_x"] if trunk_stations else x_in
    if trunk_stations:
        st = trunk_stations[-1]
        half_label = max(text_width(st["name"], 15, True), text_width(st.get("tool", "") or "", 12.5)) / 2
        auto_gap = max(30, half_label - 14)
    else:
        auto_gap = 30
    split_x = last_trunk_x + trunk.get("split_gap", auto_gap)

    def place(ln, start_x, y):
        x = start_x
        for st in ln["stations"]:
            x = st.get("x", x + st.get("gap", 0))
            st["_x"], st["_y"] = x, y
            x += s["branch_spacing"]

    # ---- main (trunk) lines: geometry ----
    geo = {}
    widest_bend = max([abs(row_y(lines[l]["row"]) - trunk_y[l]) for l in trunk_lines] + [0])
    first_labels = [max(text_width(lines[l]["stations"][0]["name"], 15, True),
                        text_width(lines[l]["stations"][0].get("tool", "") or "", 12.5)) / 2
                    for l in trunk_lines if lines[l]["stations"]]
    branch_start = split_x + widest_bend + trunk.get("branch_gap", max([60] + [h - 20 for h in first_labels]))
    for lid in trunk_lines:
        ln = lines[lid]
        ty, ry = trunk_y[lid], row_y(ln["row"])
        pts = [(x_in, ty), (split_x, ty)]
        if abs(ry - ty) > 0.5:
            pts.append((split_x + abs(ry - ty), ry))
        place(ln, branch_start, ry)
        geo[lid] = pts

    # ---- side lines: origin + stations ----
    input_cx = m + 22
    for lid, ln in lines.items():
        if ln["from"] == "trunk":
            continue
        ry = row_y(ln["row"])
        if ln["from"] == "input":
            ox = input_cx + 16
            oy = y0 + (ICON_H / 2 + 5) * (1 if ry > y0 else -1)
        else:
            key = ("trunk", ln["from"])
            if key not in pos:
                sys.exit(f"line '{lid}': from '{ln['from']}' is not 'trunk', 'input' or a trunk station name")
            ox = pos[key][0]
            oy = (trunk_bot + 13) if ry > y0 else (trunk_top - 13)
        geo[lid] = [(ox, oy), (ox, ry)]
        place(ln, ox + 1.5 * s["spacing"], ry)
        # default station spacing for side lines is a little wider (they usually span a long stretch)
        xs = ox + 1.5 * s["spacing"]
        for st in ln["stations"]:
            if "x" not in st:
                st["_x"] = xs + st.get("gap", 0)
            xs = st["_x"] + 1.1 * s["spacing"]

    for lid, ln in lines.items():
        for st in ln["stations"]:
            pos[(lid, st["name"])] = (st["_x"], st["_y"] if "_y" in st else row_y(ln["row"]))
            st["_y"] = pos[(lid, st["name"])][1]

    # ---- terminus ----
    all_station_x = [p[0] for p in pos.values()]
    if term:
        tx = term.get("x", max(all_station_x + [split_x]) + 100)
        ty = row_y(term.get("row", 0))
        into = [lid for lid, ln in lines.items() if ln["to"] == "terminus"]
        above = [lid for lid in into if row_y(lines[lid]["row"]) < ty - 0.5]
        below = [lid for lid in into if row_y(lines[lid]["row"]) > ty + 0.5]
        level = [lid for lid in into if lid not in above and lid not in below]
        above.sort(key=lambda l: lines[l]["row"])                 # top line first -> rightmost track
        below.sort(key=lambda l: -lines[l]["row"])                # bottom line first -> rightmost track

        def tracks(group, single):
            if len(group) == 1:
                return {group[0]: single}
            return {lid: ((len(group) - 1) / 2 - i) * 12 for i, lid in enumerate(group)}
        offs = tracks(above, -7)
        offs.update(tracks(below, 7))
        pill_w = max(34, 2 * max([abs(v) for v in offs.values()] + [0]) + 22)
        half = 14 + 6 * max(len(level) - 1, 0)
    # ---- finish line geometry ----
    for lid, ln in lines.items():
        pts = geo[lid]
        ry = row_y(ln["row"])
        last_x = ln["stations"][-1]["_x"] if ln["stations"] else pts[-1][0]
        to = ln["to"]
        if to == "terminus":
            if not term:
                sys.exit(f"line '{lid}' goes to the terminus, but the spec has no terminus:")
            if lid in offs:
                vx = tx + offs[lid]
                pts += [(vx, ry), (vx, ty - (half + pill_w / 2 - 5) if ry < ty else ty + (half + pill_w / 2 - 5))]
            else:
                pts.append((tx - pill_w / 2 + 4, ry))
        elif isinstance(to, dict):
            key = (to["line"], to["station"])
            if key not in pos:
                sys.exit(f"line '{lid}': to {to} does not name a station on another line")
            sx, sy = pos[key]
            sgn = 1 if sy > ry else -1
            ex, ey = sx - 8, sy - 8 * sgn
            x_drop = ex - abs(ey - ry)
            behind = max(last_x, pts[-1][0]) + 30           # must leave after its own last station
            if x_drop >= behind:
                pts += [(x_drop, ry), (ex, ey)]
            elif sx >= behind:                               # no room for 45 degrees: run along, drop in vertically
                r_st = s["station_radius"]
                pts += [(sx, ry), (sx, sy - (r_st + 2) * sgn)]
            else:
                sys.exit(f"line '{lid}' joins '{to['station']}' (x={sx:.0f}), which is behind its own stations; "
                         f"move that station right (x:) or give this line's stations smaller x values")
            ln["_casing"] = True
            ln["_joins"] = key
        else:
            pts.append((last_x, ry))

    # ---- draw: title ----
    if spec.get("title"):
        cv.text(m, 56, spec["title"], 30, True, anchor="start")
    if spec.get("subtitle"):
        cv.text(m, 84, spec["subtitle"], 15, fill=s["muted"], anchor="start")

    # ---- draw: lines (plain side lines first, main lines, then side lines that bridge into a station) ----
    order = ([l for l in lines if lines[l]["from"] != "trunk" and not lines[l].get("_casing")]
             + list(reversed(trunk_lines))
             + [l for l in lines if lines[l].get("_casing")])
    for lid in order:
        ln = lines[lid]
        # white "bridge" casing only on side lines: on a trunk line it would also eat into its parallel neighbours
        cv.polyline(geo[lid], ln["color"], lid, dashed=bool(ln.get("optional")),
                    casing=bool(ln.get("_casing")) and ln["from"] != "trunk")

    # ---- draw: stations + labels ----
    def label(x, y, st, above):
        name = st["name"]
        tool = st.get("tool", "") or ""
        if st.get("optional"):
            tool = f"{tool} · optional" if tool else "optional"
        if above:
            cv.text(x, y - LABEL_OFFSET, name, 15, True, desc=f"label '{name}'")
            cv.text(x, y - LABEL_OFFSET + TOOL_OFFSET, tool, 12.5, fill=s["muted"], desc=f"label '{name}'")
        else:
            cv.text(x, y + LABEL_OFFSET + 2, name, 15, True, desc=f"label '{name}'")
            cv.text(x, y + LABEL_OFFSET + 2 + TOOL_OFFSET, tool, 12.5, fill=s["muted"], desc=f"label '{name}'")

    # Label side: explicit `label: above|below` wins; otherwise the default side, flipped when a line leaves or
    # arrives at the station on that side (so the line would cut through the label).
    trunk_above = trunk.get("labels", "below") == "above"
    for st in trunk_stations:
        x = st["_x"]
        leaving = [l for l in lines if lines[l]["from"] == st["name"]]
        above = trunk_above
        if "label" in st:
            above = st["label"] == "above"
        elif any((row_y(lines[l]["row"]) < y0) == above for l in leaving):
            above = not above
        cv.pill(x, trunk_top, trunk_bot, trunk_lines + leaving, desc=f"station '{st['name']}'")
        label(x, trunk_top if above else trunk_bot, st, above)

    for lid, ln in lines.items():
        for st in ln["stations"]:
            joiners = [l for l, o in lines.items() if o.get("_joins") == (lid, st["name"])]
            cv.station(st["_x"], st["_y"], {lid, *joiners}, st.get("optional", False), desc=f"station '{st['name']}'")
            above = st["_y"] < y0 - 0.5
            if "label" in st:
                above = st["label"] == "above"
            elif any((row_y(lines[j]["row"]) < st["_y"]) == above for j in joiners):
                above = not above
            st["_label_above"] = above
            st["_joined_above"] = any(row_y(lines[j]["row"]) < st["_y"] for j in joiners)
            st["_joined_below"] = any(row_y(lines[j]["row"]) > st["_y"] for j in joiners)
            label(st["_x"], st["_y"], st, above)

    if term:
        cv.pill(tx, ty - half, ty + half, into, w=pill_w, desc=f"station '{term['name']}'")
        cv.text(tx + pill_w / 2 + 13, ty - 4, term["name"], 17, True, anchor="start", desc=f"label '{term['name']}'")
        cv.text(tx + pill_w / 2 + 13, ty + 15, term.get("sublabel", ""), 12.5, fill=s["muted"], anchor="start",
                desc=f"label '{term['name']}'")

    # ---- draw: input ----
    if inp:
        cv.file_icon(input_cx, y0, inp.get("file", "IN"), inp.get("color", "#57606a"), "input icon")
        up = any(l["from"] == "input" and row_y(l["row"]) < y0 for l in lines.values())
        if up:   # a side line leaves the input upwards: put the input labels underneath
            cv.text(input_cx, y0 + ICON_H / 2 + 22, inp.get("label", "Input"), 15, True, desc="input label")
            cv.text(input_cx, y0 + ICON_H / 2 + 38, inp.get("sublabel", ""), 12.5, fill=s["muted"], desc="input label")
        else:
            cv.text(input_cx, y0 - 58, inp.get("label", "Input"), 15, True, desc="input label")
            cv.text(input_cx, y0 - 42, inp.get("sublabel", ""), 12.5, fill=s["muted"], desc="input label")

    # ---- draw: output icons ----
    def output(o, sx, sy, kind, color, edge, shift=0):
        """kind: trunk | above | below | end | terminus -> default icon placement relative to the station.
        shift moves the default sideways (used when a joining line already arrives on the icon's side)."""
        dx, dy, side = {"trunk": (-75, -(sy - trunk_top) - 69, "left"),
                        "above": (0, 62, "right"),
                        "below": (0, -62, "right"),
                        "end": (100, 0, "right"),
                        "terminus": (74, 84, "right")}[kind]
        dx, dy = o.get("dx", dx + shift), o.get("dy", dy)
        side = o.get("label_side", side)
        ix, iy = sx + dx, sy + dy
        vx, vy = ix - sx, iy - sy
        dist = math.hypot(vx, vy) or 1
        ux, uy = vx / dist, vy / dist
        # stop the connector at the icon's edge (box half-extent along the direction)
        t_icon = min((ICON_W / 2 + 4) / abs(ux) if ux else math.inf, (ICON_H / 2 + 4) / abs(uy) if uy else math.inf)
        if dist > edge + t_icon:
            cv.connector(sx + ux * edge, sy + uy * edge, ix - ux * t_icon, iy - uy * t_icon)
        cv.file_icon(ix, iy, o.get("file", "OUT"), o.get("color", color), f"output icon '{o.get('file')}'")
        for k, part in enumerate(two_lines(o.get("label", ""))):
            if side == "left":
                cv.text(ix - ICON_W / 2 - 11, iy + 4 + 16 * k, part, 12.5, fill=s["muted"], anchor="end",
                        desc=f"output label '{o.get('label')}'")
            else:
                cv.text(ix + ICON_W / 2 + 11, iy - 4 + 16 * k, part, 12.5, fill=s["muted"], anchor="start",
                        desc=f"output label '{o.get('label')}'")

    mid_color = lines[trunk_lines[len(trunk_lines) // 2]]["color"] if trunk_lines else s["ink"]
    for st in trunk_stations:
        for o in st.get("outputs") or []:
            output(o, st["_x"], trunk_top if trunk_above is False else trunk_bot, "trunk", mid_color, 14)
    for lid, ln in lines.items():
        for i, st in enumerate(ln["stations"]):
            for o in st.get("outputs") or []:
                terminal = i == len(ln["stations"]) - 1 and ln["to"] == "none"
                # icon goes on the side opposite the label ("above" kind = station whose label is above -> icon below)
                kind = "end" if terminal else ("above" if st["_label_above"] else "below")
                # joining lines arrive from the left; if one comes in on the icon's side, move the icon right
                taken = st["_joined_below"] if kind == "above" else st["_joined_above"] if kind == "below" else False
                output(o, st["_x"], st["_y"], kind, ln["color"], s["station_radius"] + 2, shift=60 if taken else 0)
    if term:
        level_color = lines[level[0]]["color"] if level else (lines[into[0]]["color"] if into else s["ink"])
        for o in term.get("outputs") or ([{"file": term["file"]}] if term.get("file") else []):
            output(o, tx, ty, "terminus", level_color, half + pill_w / 2 + 4)

    # ---- legend + footnote ----
    width = spec.get("width") or max(cv.xmax + m, 900)
    ly = cv.ymax + 62
    cv.out.append(f'<line x1="{m}" y1="{ly - 36:.1f}" x2="{width - m:.1f}" y2="{ly - 36:.1f}" stroke="{s["rule"]}" stroke-width="1.5"/>')
    items = []
    for lid, ln in lines.items():
        name = ln.get("legend", ln["name"])
        if ln.get("optional") and "optional" not in name.lower():
            name += " (optional)"
        items.append(("line", ln["color"], bool(ln.get("optional")), name))
    items.append(("station", None, False, "Step"))
    if any(st.get("optional") for ln in lines.values() for st in ln["stations"]) or any(st.get("optional") for st in trunk_stations):
        items.append(("station", None, True, "Optional step"))
    lx = m
    for kind, color, opt, name in items:
        w_item = (58 if kind == "line" else 27) + text_width(name, 14) + 30
        if lx + w_item > width - m and lx > m:
            lx, ly = m, ly + 30
        if kind == "line":
            da = f' stroke-dasharray="{s["dash"]}"' if opt else ""
            cv.out.append(f'<line x1="{lx}" y1="{ly:.1f}" x2="{lx + 46}" y2="{ly:.1f}" stroke="{color}" '
                          f'stroke-width="{lw}" stroke-linecap="round"{da}/>')
            cv.text(lx + 58, ly + 5, name, 14, anchor="start", track=False)
        else:
            da = ' stroke-dasharray="4 3"' if opt else ""
            cv.out.append(f'<circle cx="{lx + 10}" cy="{ly:.1f}" r="9" fill="#ffffff" stroke="{s["ink"]}" stroke-width="3"{da}/>')
            cv.text(lx + 27, ly + 5, name, 14, anchor="start", track=False)
        lx += w_item
    fy = ly + 34
    if spec.get("footnote"):
        for line in wrap_words(spec["footnote"], int((width - 2 * m) / (12.5 * 0.53))):
            cv.text(m, fy, line, 12.5, fill=s["muted"], anchor="start", track=False)
            fy += 18
    height = spec.get("height") or fy + 12

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
           f'width="{width:.0f}" height="{height:.0f}">', f'<rect width="{width:.0f}" height="{height:.0f}" fill="#ffffff"/>']
    return "\n".join(svg + cv.out + ["</svg>"]), cv


# ----------------------------------------------------------------------------------------------------------------
# Overlap check
# ----------------------------------------------------------------------------------------------------------------
def overlaps(a, b, pad=0):
    return a[0] - pad < b[2] and b[0] - pad < a[2] and a[1] - pad < b[3] and b[1] - pad < a[3]


def sample(pts, step=3):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) / step))
        for i in range(n + 1):
            yield x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n


def check_overlaps(cv):
    half = cv.s["line_width"] / 2 + 1
    found = []
    labels = {}
    for box, desc in cv.texts:   # merge the two lines of one label into one box
        b = labels.get(desc)
        labels[desc] = box if b is None else (min(b[0], box[0]), min(b[1], box[1]), max(b[2], box[2]), max(b[3], box[3]))
    items = list(labels.items())
    for i, (d1, b1) in enumerate(items):
        for d2, b2 in items[i + 1:]:
            if overlaps(b1, b2, 1):
                found.append(f"{d1} overlaps {d2}")
        for b2, d2 in cv.icons:
            if overlaps(b1, b2, 1):
                found.append(f"{d1} overlaps {d2}")
        for pts, lid in cv.lines:
            if any(b1[0] - half < x < b1[2] + half and b1[1] - half < y < b1[3] + half for x, y in sample(pts)):
                found.append(f"{d1} overlaps line '{lid}'")
    for b1, d1 in cv.icons:
        for pts, lid in cv.lines:
            if any(b1[0] - half < x < b1[2] + half and b1[1] - half < y < b1[3] + half for x, y in sample(pts)):
                found.append(f"{d1} sits on line '{lid}'")
    for b1, members, d1 in cv.stations:
        for pts, lid in cv.lines:
            if lid in members:
                continue
            if any(b1[0] - half < x < b1[2] + half and b1[1] - half < y < b1[3] + half for x, y in sample(pts)):
                found.append(f"{d1} sits on line '{lid}' (looks like a shared stop)")
    return sorted(set(found))


# ----------------------------------------------------------------------------------------------------------------
# Starter spec from `snakemake --rulegraph`
# ----------------------------------------------------------------------------------------------------------------
def pretty(rule):
    words = rule.replace("-", "_").split("_")
    return " ".join([words[0].capitalize()] + words[1:]) if words else rule


def spec_from_rulegraph(dot_text, title="My pipeline"):
    names, edges = {}, []
    for line in dot_text.splitlines():
        m = re.match(r'\s*(\d+)\s*\[\s*label\s*=\s*"([^"]+)"', line)
        if m:
            names[m.group(1)] = m.group(2)
            continue
        m = re.match(r"\s*(\d+)\s*->\s*(\d+)", line)
        if m:
            edges.append((m.group(1), m.group(2)))
    if not names:
        sys.exit("no rules found: is this the output of `snakemake --rulegraph`?")
    rules = {i: n for i, n in names.items() if n != "all"}
    succ = {i: [] for i in rules}
    pred = {i: [] for i in rules}
    for a, b in edges:
        if a in rules and b in rules and b not in succ[a]:
            succ[a].append(b)
            pred[b].append(a)
    term = next((i for i, n in rules.items() if "multiqc" in n.lower()), None)
    feeds_term = set(pred[term]) if term else set()
    nodes = [i for i in rules if i != term]
    S = {i: [j for j in succ[i] if j != term] for i in nodes}
    P = {i: [j for j in pred[i] if j != term] for i in nodes}

    def descendants(i, seen=None):
        seen = set() if seen is None else seen
        for j in S[i]:
            if j not in seen:
                seen.add(j)
                descendants(j, seen)
        return seen

    def longest_path(i, memo={}):
        if i not in memo:
            memo[i] = [i] + max((longest_path(j) for j in S[i]), key=len, default=[])
        return memo[i]

    sources = [i for i in nodes if not P[i]]
    if not sources:
        sys.exit("the rule graph has no source rule")
    main = max(sources, key=lambda i: len(descendants(i)))
    # trunk: follow the longest path while the next rule has a single input; stop after a hub (3+ successors)
    trunk, path = [], longest_path(main)
    for k, i in enumerate(path):
        trunk.append(i)
        nxt = path[k + 1] if k + 1 < len(path) else None
        if nxt is None or len(S[i]) >= 3 or len(P[nxt]) != 1:
            break
    assigned = {i: ("trunk", None) for i in trunk}

    def chain(start):
        c, i = [], start
        while i is not None and i not in assigned:
            c.append(i)
            assigned[i] = None
            nxt = [j for j in S[i] if j not in assigned]
            i = nxt[0] if len(S[i]) == 1 and nxt else None
        return c

    def tail_target(c, lid):
        last = c[-1]
        if last in feeds_term:
            return "terminus"
        for j in S[last]:
            if assigned.get(j) and assigned[j][0] != "trunk" and assigned[j][0] != lid:
                return {"line": assigned[j][0], "station": pretty(rules[j])}
        return "none"

    lines, row_cycle = {}, [-1, 1, 0, -2, 2, -3, 3]
    hub = trunk[-1]
    for k, j in enumerate(S[hub]):
        if j in assigned:
            continue
        c = chain(j)
        lid = f"line{len(lines) + 1}"
        for i in c:
            assigned[i] = (lid, None)
        lines[lid] = {"name": pretty(rules[c[0]]), "row": row_cycle[len(lines) % len(row_cycle)], "_chain": c}
    for t in trunk[:-1]:
        for j in S[t]:
            if j in assigned:
                continue
            c = chain(j)
            lid = f"side{len(lines) + 1}"
            for i in c:
                assigned[i] = (lid, None)
            lines[lid] = {"name": pretty(rules[c[0]]), "from": pretty(rules[t]), "optional": True, "_chain": c}
    for src in sources:
        if src in assigned:
            continue
        c = chain(src)
        lid = f"side{len(lines) + 1}"
        for i in c:
            assigned[i] = (lid, None)
        lines[lid] = {"name": pretty(rules[c[0]]), "from": "input", "optional": True, "_chain": c}
    for lid, ln in lines.items():
        ln["to"] = tail_target(ln["_chain"], lid)
    # side-line rows: just outside the line they join; otherwise outside all main lines (above, then below)
    main_rows = [ln["row"] for ln in lines.values() if "from" not in ln] or [0]
    used = set(main_rows)
    outside = max(abs(r) for r in main_rows) + 0.6
    flip = -1
    for lid, ln in lines.items():
        if "from" not in ln:
            continue
        to = ln["to"]
        if isinstance(to, dict) and "row" in lines.get(to["line"], {}):
            base = lines[to["line"]]["row"]
            direction = 1 if base >= 0 else -1
            row = base + 0.6 * direction
        else:
            direction = 1 if ln["from"] == "input" else flip
            flip = -flip
            row = outside * direction
        while round(row, 1) in used:
            row += 0.5 * direction
        ln["row"] = round(row, 1)
        used.add(ln["row"])
    unplaced = [rules[i] for i in nodes if i not in assigned]

    # ---- write YAML with comments ----
    q = lambda v: '"' + str(v).replace('"', '\\"') + '"'
    out = ["# Starter slitherFlow spec generated from `snakemake --rulegraph`.",
           "# Rename stations, add tools/outputs, regroup lines and tune rows, then render with:",
           "#   slitherflow render this.yaml -o map.svg --png --pdf",
           "",
           f'title: {q(title)}',
           'subtitle: "v1.0  ·  Snakemake"',
           'input: {label: "Input", sublabel: "", file: "FASTQ"}',
           "",
           "trunk:                      # steps every sample goes through",
           "  stations:"]
    out += [f"    - {{name: {q(pretty(rules[i]))}, tool: \"\"}}" for i in trunk]
    trunk_ids = sorted((l for l, v in lines.items() if "from" not in v), key=lambda l: lines[l]["row"])
    out += ["  lines: [" + ", ".join(trunk_ids) + "]   # top -> bottom on the trunk",
            "", "lines:"]
    for lid, ln in lines.items():
        out.append(f"  {lid}:")
        out.append(f"    name: {q(ln['name'])}")
        if "from" in ln:
            out.append(f"    from: {q(ln['from'])}")
        out.append(f"    row: {ln['row']}" + ("            # negative = above the trunk" if ln['row'] < 0 else ""))
        if ln.get("optional"):
            out.append("    optional: true         # dashed; delete if the step always runs")
        to = ln["to"]
        out.append(f"    to: {q(to) if isinstance(to, str) else '{line: ' + to['line'] + ', station: ' + q(to['station']) + '}'}")
        out.append("    stations:")
        out += [f"      - {{name: {q(pretty(rules[i]))}, tool: \"\"}}" for i in ln["_chain"]]
    if term:
        feeding = [ln["row"] for ln in lines.values() if ln["to"] == "terminus" and "from" not in ln]
        trow = min(feeding, key=abs) if feeding else 0
        out += ["", f'terminus: {{name: {q(pretty(rules[term]))}, sublabel: "QC report", row: {trow}, file: "HTML"}}']
    out += ["", 'footnote: ""']
    if unplaced:
        out += ["", "# Rules not placed automatically (add them to a line by hand):"] + [f"#   - {r}" for r in unplaced]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------------------------------------------
def rulegraph_from_project(project, snakemake="snakemake", extra=()):
    """Run `snakemake --rulegraph` in a project directory and return the DOT text."""
    exe = shutil.which(snakemake) or (snakemake if Path(snakemake).is_file() else None)
    if not exe:
        sys.exit(f"cannot find '{snakemake}': activate the environment that has Snakemake, or pass --snakemake PATH")
    project = Path(project)
    if not project.is_dir():
        sys.exit(f"project directory not found: {project}")
    cmd = [exe, "--rulegraph", "--nolock", *extra]
    print(f"running: {' '.join(cmd)}  (in {project})", file=sys.stderr)
    res = subprocess.run(cmd, cwd=project, capture_output=True, text=True)
    if res.returncode != 0 or "digraph" not in res.stdout:
        tail = "\n".join((res.stderr or res.stdout).strip().splitlines()[-15:])
        sys.exit(f"`snakemake --rulegraph` failed in {project} (exit {res.returncode}):\n{tail}\n\n"
                 "If the workflow needs a config or profile to resolve, pass it after `--`, "
                 "e.g. `-- --configfile config/test.yaml`.")
    return res.stdout[res.stdout.index("digraph"):]


def write_draft(dot_text, project_name, out):
    spec_text = spec_from_rulegraph(dot_text, title=project_name)
    Path(out).write_text(spec_text)
    print(f"wrote {out}")


def render_file(spec_path, out, png=False, pdf=False, strict=False):
    spec = yaml.safe_load(Path(spec_path).read_text())
    svg, cv = render(spec)
    out = Path(out) if out else Path(spec_path).with_suffix(".svg")
    out.write_text(svg)
    print(f"wrote {out}")
    for flag, args, suffix in [(png, ["-z", "3"], ".png"), (pdf, ["-f", "pdf"], ".pdf")]:
        if not flag:
            continue
        if not shutil.which("rsvg-convert"):
            print(f"rsvg-convert not found: cannot write {suffix} (install librsvg, e.g. `brew install librsvg` "
                  f"or `apt install librsvg2-bin`)", file=sys.stderr)
            continue
        dest = out.with_suffix(suffix)
        subprocess.run(["rsvg-convert", *args, str(out), "-o", str(dest)], check=True)
        print(f"wrote {dest}")
    problems = check_overlaps(cv)
    if problems:
        print(f"\n{len(problems)} possible overlap(s):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("Move stations with x: / gap:, change row:, or nudge outputs with dx:/dy: in the spec.", file=sys.stderr)
        if strict:
            sys.exit(1)
    else:
        print("no overlaps found")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = []
    if "--" in argv:                        # everything after `--` goes to snakemake
        k = argv.index("--")
        argv, extra = argv[:k], argv[k + 1:]

    ap = argparse.ArgumentParser(prog="slitherflow", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def render_opts(p):
        p.add_argument("--png", action="store_true", help="also write a PNG (3x) with rsvg-convert")
        p.add_argument("--pdf", action="store_true", help="also write a vector PDF with rsvg-convert")
        p.add_argument("--strict", action="store_true", help="exit 1 if any overlaps are found (for CI)")

    def project_opts(p):
        p.add_argument("project", help="Snakemake project directory (where `snakemake` normally runs)")
        p.add_argument("--snakemake", default="snakemake", help="snakemake executable (default: on PATH)")
        p.add_argument("--rulegraph", metavar="DOT", help="use a saved `snakemake --rulegraph` file instead of running it")

    p = sub.add_parser("auto", help="rule graph -> starter spec -> map, in one step")
    project_opts(p)
    p.add_argument("-o", "--output", help="map .svg (default: <project>_subway.svg); the spec is written next to it")
    p.add_argument("--overwrite-spec", action="store_true", help="replace an existing spec (default: keep your edits)")
    render_opts(p)

    p = sub.add_parser("draft", help="write a starter spec from the project's rule graph")
    project_opts(p)
    p.add_argument("-o", "--output", help="spec .yaml (default: <project>_subway.yaml)")

    p = sub.add_parser("render", help="draw a map from a spec")
    p.add_argument("spec", help="YAML spec")
    p.add_argument("-o", "--output", help="map .svg (default: next to the spec)")
    render_opts(p)

    a = ap.parse_args(argv)
    if a.cmd == "render":
        render_file(a.spec, a.output, a.png, a.pdf, a.strict)
        return

    name = Path(a.project).resolve().name
    dot = Path(a.rulegraph).read_text() if a.rulegraph else rulegraph_from_project(a.project, a.snakemake, extra)
    if a.cmd == "draft":
        write_draft(dot, name, a.output or f"{name}_subway.yaml")
        return
    svg_out = Path(a.output or f"{name}_subway.svg")
    spec_out = svg_out.with_suffix(".yaml")
    if spec_out.exists() and not a.overwrite_spec:
        print(f"keeping existing spec {spec_out} (use --overwrite-spec to redraft it)")
    else:
        write_draft(dot, name, spec_out)
    render_file(spec_out, svg_out, a.png, a.pdf, a.strict)


if __name__ == "__main__":
    main()
