# Spec reference

A map is described by a YAML file, called the spec. `slitherflow draft` writes a starter spec for you; this page lists everything it can contain.

## Example

Here's a small spec that uses most of the options. Everything except `lines` is optional.

```yaml
title: "My pipeline"
subtitle: "v1.0  ·  Snakemake"
input: {label: "Input", sublabel: "Paired-end", file: "FASTQ"}

trunk:
  stations:
    - {name: "Trimming", tool: "cutadapt"}
    - {name: "Alignment", tool: "Bowtie2", outputs: [{file: "BAM", label: "Aligned reads"}]}
  lines: [peaks, qc]           # lines that run along the trunk, top to bottom

lines:
  peaks:
    name: "Peak calling"
    color: "#009E73"
    row: -1
    to: terminus
    stations:
      - {name: "Peak calling", tool: "MACS3"}
      - {name: "Peak filtering", tool: "bedtools", outputs: [{file: "BED", label: "Filtered peaks"}]}
  qc:
    name: "Quality control"
    row: 1
    to: terminus
    stations: [{name: "Fingerprints", tool: "deepTools"}]
  spike:
    name: "Spike-in normalization"
    optional: true
    from: "Trimming"           # leaves a trunk station (or use `input`)
    row: -1.6
    to: {line: peaks, station: "Peak filtering"}
    stations: [{name: "Spike-in alignment", tool: "Bowtie2"}]
  fragments:
    from: {line: qc, station: "Fingerprints"}   # a branch
    row: 1.6
    stations: [{name: "Fragment sizes", tool: "deepTools"}]

terminus: {name: "MultiQC", sublabel: "QC report", row: 1, file: "HTML"}
footnote: "One line of explanation under the legend."
```

## Top level

| Key | Meaning |
|---|---|
| `title`, `subtitle` | Text at the top of the map |
| `input` | The start of the map: `{label, sublabel, file}` |
| `trunk` | The shared steps every sample goes through (see [below](#trunk)) |
| `lines` | **Required.** A mapping of line ID → line (see [below](#lines)) |
| `terminus` | The end station (see [below](#terminus)) |
| `footnote` | One line of explanation under the legend |
| `style` | Overrides for the default look (see [below](#style)) |

## Trunk

| Key | Meaning |
|---|---|
| `stations` | The trunk's stations, drawn as pills spanning its lines |
| `lines` | The line IDs that run along the trunk, top to bottom |
| `labels: above` | Put the trunk's station labels above it |
| `split_gap` | Extra space before the lines split apart |
| `branch_gap` | Extra space before the first station after the split |

## Lines

| Key | Meaning |
|---|---|
| `name` | The name shown in the legend (defaults to the line ID) |
| `color` | Line colour (defaults to the next [palette](#default-colours) colour) |
| `row` | Vertical position. Negative is above the trunk, positive below, and fractions are fine |
| `optional: true` | Draw the line dashed, and add "(optional)" to its legend entry |
| `from` | Where the line starts: a trunk station's name, `input`, or `{line, station}` to make it a branch |
| `to` | Where the line ends: `terminus`, or `{line, station}` to join another line. By default it just stops |
| `stations` | The line's stations, left to right |

## Stations

| Key | Meaning |
|---|---|
| `name`, `tool` | The label, and the smaller grey text under it |
| `optional: true` | Dashed station circle, with "optional" added to the tool text |
| `x` | Exact horizontal position |
| `gap` | Extra space before this station |
| `label: above` / `below` | Which side the label goes on. By default it goes away from the trunk (or, on a branch, away from its parent line), and moves to the other side if a line is in the way |
| `outputs` | File icons: a list of `{file, label, color, dx, dy, label_side}` |
| `feeds` | A list of `{line, station}` that this step also feeds into. The target has to be further right, on a different line |

## Terminus

| Key | Meaning |
|---|---|
| `name`, `sublabel` | The end station's label |
| `row` | Vertical position |
| `file` | Draw an output icon with this file type |
| `x` | Exact horizontal position |
| `outputs` | Extra file icons, as for stations |

## Style

Anything under `style` overrides these defaults:

| Key | Default | Meaning |
|---|---|---|
| `font` | `'Helvetica Neue', Helvetica, Arial, sans-serif` | Font family |
| `line_width` | `7` | Width of every line |
| `gap` | `10` | Spacing between parallel lines on the trunk |
| `spacing` | `170` | Distance between trunk stations |
| `branch_spacing` | `140` | Distance between stations on a branch |
| `row_height` | `130` | Vertical distance per row |
| `corner` | `22` | Corner radius of 90° bends |
| `dash` | `16 9` | Dash pattern for optional lines |
| `margin` | `48` | Space around the map |

## Default colours

Lines are coloured in this order, from the colour-blind-friendly Okabe-Ito palette:

<span style="color:#009E73">■</span> `#009E73`
<span style="color:#E69F00">■</span> `#E69F00`
<span style="color:#CC79A7">■</span> `#CC79A7`
<span style="color:#D55E00">■</span> `#D55E00`
<span style="color:#56B4E9">■</span> `#56B4E9`
<span style="color:#0072B2">■</span> `#0072B2`
<span style="color:#F0E442">■</span> `#F0E442`
<span style="color:#000000">■</span> `#000000`
