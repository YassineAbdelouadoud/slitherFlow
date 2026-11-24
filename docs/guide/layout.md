# Layout tips

slitherFlow spaces stations automatically, but you can take control when you need to.

## Moving things around

| Key | Applies to | Effect |
|---|---|---|
| `row` | line | Moves a whole line up or down. Negative rows are above the trunk, and fractions are fine. |
| `x` | station | Pins a station to an exact horizontal position. Stations with an `x` are never moved automatically. |
| `gap` | station | Adds extra space before a station, while keeping the automatic spacing. |
| `label: above` / `below` | station | Forces the side of a station's label. |
| `dx`, `dy` | output icon | Nudges a file icon. |

## Overlap check

Every render checks for overlapping labels, icons and lines, and prints anything it finds. With `--strict`, it exits with an error instead, which is useful in CI.

!!! note
    The check estimates text widths, so always look at the final image too.

## Tips

- A line that joins another line comes in at 45° if there's room. Give it a `row` just outside the line it joins. Where lines cross, the joining line gets a white outline so the crossing reads like a bridge.
- If branches crowd each other, spread them out with `row`, or space out their stations with `x` or `gap`.
- To change spacing across the whole map, override `spacing`, `branch_spacing` or `row_height` under [`style`](../reference/spec.md#style).
- PNGs are rendered at 3× resolution, so they're good enough for print. The SVG and PDF are vector files, and the text in them stays editable.
