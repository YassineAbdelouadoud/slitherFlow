"""Colours, layout constants and the text-width estimate shared by the renderer and overlap check."""

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
FEED_LANE = 90               # shortest straight run of a `feeds:` connector between its two bends


def text_width(s, size, bold=False):
    """Rough rendered width of Helvetica text (good enough for layout and overlap checks)."""
    return len(s) * size * (0.58 if bold else 0.53)   # calibrated on rsvg-convert renders
