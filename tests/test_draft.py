"""The drafter: from a saved `snakemake --rulegraph`, every rule gets a station and no connection is lost."""
import yaml

import slitherflow
from conftest import EXAMPLES, parse_rulegraph, drawn_connections


def test_every_rule_is_placed(rulegraph):
    rules, _ = parse_rulegraph(rulegraph["dot"])
    spec = rulegraph["spec"]
    stations = [st["name"] for st in spec.get("trunk", {}).get("stations", [])]
    stations += [st["name"] for ln in spec["lines"].values() for st in ln["stations"]]
    if spec.get("terminus"):
        stations.append(spec["terminus"]["name"])
    assert sorted(stations) == sorted(slitherflow.pretty(r) for r in rules)
    assert "could not place" not in rulegraph["spec_text"].lower()


def test_terminus_is_chosen_from_the_graph(rulegraph):
    expected = rulegraph["terminus"]
    terminus = rulegraph["spec"].get("terminus")
    if expected is None:
        assert terminus is None
    else:
        assert terminus["name"] == slitherflow.pretty(expected)


def test_every_connection_is_drawn_except_into_the_terminus(rulegraph):
    _, edges = parse_rulegraph(rulegraph["dot"])
    spec = rulegraph["spec"]
    term = (spec.get("terminus") or {}).get("name")
    drawn = drawn_connections(spec)
    missing = [(a, b) for a, b in edges
               if (slitherflow.pretty(a), slitherflow.pretty(b)) not in drawn and slitherflow.pretty(b) != term]
    assert missing == []


def test_draft_renders_without_overlaps(rulegraph):
    _, cv = slitherflow.render(rulegraph["spec"])
    assert slitherflow.check_overlaps(cv) == []


def test_drafts_match_committed_examples():
    """The example drafts are exactly what `draft` writes today. If a drafter change is intended, rebuild them
    with the commands in the README's Examples section and commit the new files."""
    for name, project in [("cutrun", "GDSC-CUT-RUN-pipeline"), ("mirnaseq", "GDSC-miRNAseq-analysis-pipeline")]:
        dot = (EXAMPLES / name / "rulegraph.dot").read_text()
        committed = (EXAMPLES / name / f"{name}_draft.yaml").read_text()
        assert slitherflow.spec_from_rulegraph(dot, title=project) == committed, f"{name}_draft.yaml is out of date"


def test_side_line_sits_on_the_side_it_feeds():
    """CUT&RUN: the spike-in line feeds 'Generate signal tracks', which is below the trunk, so it runs below."""
    dot = (EXAMPLES / "cutrun" / "rulegraph.dot").read_text()
    spec = yaml.safe_load(slitherflow.spec_from_rulegraph(dot))
    spike = next(ln for ln in spec["lines"].values()
                 if any(st["name"] == "Spikein alignment" for st in ln["stations"]))
    assert spike["row"] > 0


def test_branches_from_one_station_share_a_side():
    """DAC RNA-seq with every option on: RSEM and featureCounts both leave 'Alignment', on the same side as the
    pre-alignment line that joins it, so the station's label keeps one side free."""
    from conftest import DATA
    spec = yaml.safe_load(slitherflow.spec_from_rulegraph((DATA / "dac_rnaseq_all_options.dot").read_text()))
    lines = spec["lines"]
    leaving = [ln for ln in lines.values() if isinstance(ln.get("from"), dict)
               and ln["from"]["station"] == "Alignment"]
    joining = [ln for ln in lines.values() if isinstance(ln.get("to"), dict) and ln["to"]["station"] == "Alignment"]
    parent_row = lines[leaving[0]["from"]["line"]]["row"]
    sides = {ln["row"] > parent_row for ln in leaving + joining}
    assert len(leaving) == 2 and len(sides) == 1


def test_warnings_around_the_graph_are_ignored():
    """Snakemake can print warnings before the graph; only node and edge lines matter."""
    dot = (EXAMPLES / "mirnaseq" / "rulegraph.dot").read_text()
    noisy = "Building DAG of jobs...\nImportError: something unrelated\n" + dot + "\nDone.\n"
    assert slitherflow.spec_from_rulegraph(noisy) == slitherflow.spec_from_rulegraph(dot)
