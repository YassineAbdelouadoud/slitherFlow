"""slitherFlow: subway maps for Snakemake pipelines."""

__version__ = "1.0.0"

from .canvas import trim_path                                  # noqa: E402,F401
from .cli import main                                          # noqa: E402,F401
from .draft import find_terminus, pretty, spec_from_rulegraph  # noqa: E402,F401
from .overlaps import check_overlaps                           # noqa: E402,F401
from .render import render                                     # noqa: E402,F401
from .style import PALETTE, STYLE, text_width                  # noqa: E402,F401

__all__ = ["__version__", "main", "render", "spec_from_rulegraph", "check_overlaps", "find_terminus", "pretty",
           "trim_path", "PALETTE", "STYLE", "text_width"]
