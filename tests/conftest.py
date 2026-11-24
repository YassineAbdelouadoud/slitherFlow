import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))          # test the checkout, installed or not

import slitherflow  # noqa: E402

EXAMPLES = ROOT / "examples"
DATA = Path(__file__).resolve().parent / "data"

# Every saved rule graph, with the rule the drafter should pick as the terminus (None = no terminus).
RULEGRAPHS = {
    "cutrun": (EXAMPLES / "cutrun" / "rulegraph.dot", "multiqc"),
    "mirnaseq": (EXAMPLES / "mirnaseq" / "rulegraph.dot", "alignment_metrics_counts"),
    "dac_rnaseq_default": (DATA / "dac_rnaseq_default.dot", None),
    "dac_rnaseq_all_options": (DATA / "dac_rnaseq_all_options.dot", None),
}


def parse_rulegraph(dot_text):
    """(rule names, edges between real rules) from `snakemake --rulegraph` output; rule `all` is dropped."""
    names = dict(re.findall(r'(\d+)\s*\[\s*label\s*=\s*"([^"]+)"', dot_text))
    edges = [(names[a], names[b]) for a, b in re.findall(r"(\d+)\s*->\s*(\d+)", dot_text)
             if names[a] != "all" and names[b] != "all"]
    return [n for n in names.values() if n != "all"], edges


def drawn_connections(spec):
    """Every (from station, to station) pair the map draws: along the trunk and each line, where a line leaves
    its start, where it ends (terminus or another line's station), and every `feeds:` connector."""
    trunk = [st["name"] for st in spec.get("trunk", {}).get("stations", [])]
    term = (spec.get("terminus") or {}).get("name")
    drawn = set(zip(trunk, trunk[1:]))
    stations = list(spec.get("trunk", {}).get("stations", []))
    for ln in spec["lines"].values():
        names = [st["name"] for st in ln["stations"]]
        stations += ln["stations"]
        frm = ln.get("from", "trunk")
        if frm == "trunk":
            start = trunk[-1] if trunk else None
        elif isinstance(frm, dict):
            start = frm["station"]
        else:
            start = None if frm == "input" else frm
        chain = ([start] if start else []) + names
        drawn |= set(zip(chain, chain[1:]))
        to = ln.get("to")
        if to == "terminus":
            drawn.add((names[-1], term))
        elif isinstance(to, dict):
            drawn.add((names[-1], to["station"]))
    for st in stations:
        for ref in st.get("feeds") or []:
            drawn.add((st["name"], ref["station"]))
    return drawn


@pytest.fixture(params=sorted(RULEGRAPHS), ids=sorted(RULEGRAPHS))
def rulegraph(request):
    path, terminus = RULEGRAPHS[request.param]
    dot = path.read_text(encoding="utf-8")
    spec_text = slitherflow.spec_from_rulegraph(dot, title=request.param)
    return {"name": request.param, "dot": dot, "terminus": terminus,
            "spec_text": spec_text, "spec": yaml.safe_load(spec_text)}
