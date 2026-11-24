"""--scan: build the rule graph by reading Snakefiles and .smk files, without running Snakemake.

tests/data/scan_project is a made-up workflow that uses each pattern the scanner follows; each test below names
the pattern it checks."""
import re

import pytest
import yaml

import slitherflow
from conftest import DATA, parse_rulegraph
from slitherflow.scan import can_match_same_file, rulegraph_from_files, tokens

PROJECT = DATA / "scan_project"


@pytest.fixture(scope="module")
def graph():
    """(rules, edges), keeping rule `all` and the edges into it (parse_rulegraph drops those)."""
    dot = rulegraph_from_files(PROJECT)
    names = dict(re.findall(r'(\d+)\s*\[\s*label\s*=\s*"([^"]+)"', dot))
    edges = {(names[a], names[b]) for a, b in re.findall(r"(\d+)\s*->\s*(\d+)", dot)}
    return set(names.values()), edges


def test_conditionally_included_rules_are_found(graph):
    rules, _ = graph
    assert "dedup" in rules                       # rules/dedup.smk is only included when `dedup` is on


def test_rules_that_never_lead_to_all_are_left_out(graph):
    rules, _ = graph
    assert "unused_helper" not in rules


def test_test_folders_are_skipped(graph):
    rules, _ = graph
    assert "make_test_data" not in rules


@pytest.mark.parametrize("edge, pattern", [
    (("trim", "filter"), "plain string input, temp() output"),
    (("trim", "align"), "variable set on both branches of an if/else"),
    (("filter", "align"), "f-string with a variable that has two possible values"),
    (("build_index", "align"), "keyword input"),
    (("align", "count"), "input function via unpack(), helper function, .format()"),
    (("dedup", "count"), "dict entry overwritten under an if inside the input function"),
    (("align", "dedup"), "helper function with a default argument"),
    (("trim", "trim_stats"), "log files count as outputs"),
    (("trim_stats", "report"), "rules.<name>.output"),
    (("report", "all"), "rules.<name>.output.<key> inside a list added with +="),
    (("dedup", "all"), "expand() added to a list under an if"),
])
def test_connection_is_found(graph, edge, pattern):
    _, edges = graph
    assert edge in edges, pattern


def test_no_extra_connections(graph):
    _, edges = graph
    expected = {("trim", "filter"), ("trim", "align"), ("filter", "align"), ("build_index", "align"),
                ("align", "count"), ("dedup", "count"), ("align", "dedup"), ("trim", "trim_stats"),
                ("trim_stats", "report"), ("count", "report"), ("count", "all"), ("report", "all"),
                ("dedup", "all")}
    assert edges == expected


def test_scanned_graph_drafts_and_renders():
    spec = yaml.safe_load(slitherflow.spec_from_rulegraph(rulegraph_from_files(PROJECT)))
    stations = [st["name"] for st in spec.get("trunk", {}).get("stations", [])]
    stations += [st["name"] for ln in spec["lines"].values() for st in ln["stations"]]
    if spec.get("terminus"):
        stations.append(spec["terminus"]["name"])
    rules, _ = parse_rulegraph(rulegraph_from_files(PROJECT))
    assert sorted(stations) == sorted(slitherflow.pretty(r) for r in rules)
    slitherflow.render(spec)


@pytest.mark.parametrize("a, b, same", [
    ("aligned/{sample}.bam", "aligned/{sample}.bam", True),
    ("aligned/{sample}.bam", "aligned/x.bam", True),
    ("aligned/{sample}.bam", "aligned/{sample}.bam.bai", False),
    ("peak-calling/{sample}_peaks.narrowPeak", "peak-calling/filtered/{s}_peaks.filtered.{t}", False),  # not across /
    ("peak-calling/filtered/{s}_peaks.filtered.{t}", "peak-calling/filtered/{x}_peaks.filtered.narrowPeak", True),
    ("qc/{sample}", "qc/{sample}", True),
    ("{sample,[A-Z]{2}}.txt", "AB.txt", True),
])
def test_patterns_match_the_same_file(a, b, same):
    assert can_match_same_file(tokens(a), tokens(b)) is same


def test_cli_scan_and_save_rulegraph(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    slitherflow.main(["auto", str(PROJECT), "--scan", "--save-rulegraph", "graph.dot"])
    assert (tmp_path / "scan_project_subway.svg").read_text(encoding="utf-8").startswith("<svg")
    assert "dedup" in (tmp_path / "graph.dot").read_text(encoding="utf-8")


def test_cli_scan_refuses_snakemake_arguments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="can't take Snakemake arguments"):
        slitherflow.main(["draft", str(PROJECT), "--scan", "--", "--configfile", "x.yaml"])
