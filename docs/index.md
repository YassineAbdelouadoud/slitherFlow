---
hide:
  - navigation
---

# slitherFlow <img src="logo/slitherflow_hex.png" alt="slitherFlow logo" align="right" width="140"/>

**Subway maps for Snakemake pipelines.**

slitherFlow turns a Snakemake pipeline into a subway-map figure, in the style of the nf-core pipeline diagrams. It reads your pipeline's rule graph, writes a first draft of the map as a YAML file, and draws it as an SVG (plus PNG or PDF if you want them). You then edit the YAML until the map is to your liking.

![miRNA-seq pipeline map](examples/mirnaseq/mirnaseq.png)

*The GDSC miRNA-seq pipeline, drawn with slitherFlow. The first draft came from `--scan`, so every optional step is on the map.*

## In three commands

```shell
pixi global install -c conda-forge -c bioconda --git https://github.com/mikemartinez99/slitherFlow.git --expose slitherflow
slitherflow auto /path/to/my-pipeline --png        # draft a map
slitherflow render my-pipeline_subway.yaml --png   # re-draw after editing the YAML
```

No pixi? See [Installation](installation.md) for installing with pip.

## Where to next

<div class="grid cards" markdown>

- **[Installation](installation.md)**: install slitherFlow and the optional tools it uses.
- **[Quick start](quickstart.md)**: draw your first map, or try the bundled example.
- **[Customizing your map](guide/customizing.md)**: rename steps, add tools and outputs, connect lines.
- **[Spec reference](reference/spec.md)**: every option the YAML file accepts.

</div>
