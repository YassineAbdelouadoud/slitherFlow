# Installation

## With pixi (recommended)

Install slitherFlow with [pixi](https://pixi.sh), a package manager for conda environments. You don't need to clone the repository:

```shell
pixi global install -c conda-forge -c bioconda --git https://github.com/mikemartinez99/slitherFlow.git --expose slitherflow
```

Pixi builds slitherFlow and installs it into its own environment, together with Python, PyYAML, Snakemake and rsvg-convert. Only the `slitherflow` command goes on your `PATH`, so you can run it from any folder. You don't need to install anything else.

Check it worked with:

```shell
slitherflow --version
```

!!! note "Using your own Snakemake"
    slitherFlow uses the Snakemake that pixi installed. If your pipeline needs a specific Snakemake version or plugins, pass your own with `--snakemake PATH`.

## With pip

```shell
pip install git+https://github.com/mikemartinez99/slitherFlow.git
```

This installs the `slitherflow` command. slitherFlow needs Python 3.9 or later, and its only Python dependency is PyYAML. You'll also want these tools, which pixi would otherwise have installed for you:

| Tool | Needed for | How to get it |
|---|---|---|
| **Snakemake** | Reading your pipeline's rule graph | Usually already in your pipeline's environment. Not needed if you use `--scan` or a saved rule graph (`--rulegraph`). |
| **rsvg-convert** | PNG and PDF output | macOS: `brew install librsvg`. Debian/Ubuntu: `apt install librsvg2-bin`. SVG output works without it. |

## From a clone, for development

To change the code or run the tests, clone the repository and let pixi set up its environment:

```shell
git clone https://github.com/mikemartinez99/slitherFlow.git
cd slitherFlow
pixi install
```

Pixi installs slitherFlow and its dependencies into a `.pixi` folder inside `slitherFlow`. Your changes to the code take effect without reinstalling.

Run slitherFlow with the `slitherflow` task. Pixi runs it in the folder you call it from, so relative paths work as usual. From any other folder, point pixi at the `slitherFlow` folder with `--manifest-path`:

```shell
cd /path/to/my-pipeline
pixi run --manifest-path /path/to/slitherFlow slitherflow auto . --png
```

!!! tip "Commands in these docs"
    The rest of these docs write commands as `slitherflow ...`. In a clone, put `pixi run` in front of them, or run `pixi shell` once to put `slitherflow` on your `PATH`.

See [Development](development.md) for running the tests and building these docs.
