"""The command line, end to end (no Snakemake needed: every test uses a saved rule graph)."""
import pytest

import slitherflow
from conftest import EXAMPLES

DOT = str(EXAMPLES / "mirnaseq" / "rulegraph.dot")


def test_auto_writes_spec_and_map(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    slitherflow.main(["auto", "my-pipeline", "--rulegraph", DOT])
    assert (tmp_path / "my-pipeline_subway.yaml").exists()
    assert (tmp_path / "my-pipeline_subway.svg").read_text().startswith("<svg")


def test_auto_keeps_an_edited_spec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    slitherflow.main(["auto", "my-pipeline", "--rulegraph", DOT])
    spec = tmp_path / "my-pipeline_subway.yaml"
    spec.write_text(spec.read_text().replace('title: "my-pipeline"', 'title: "Edited title"'))
    slitherflow.main(["auto", "my-pipeline", "--rulegraph", DOT])
    assert "Edited title" in spec.read_text()
    assert "Edited title" in (tmp_path / "my-pipeline_subway.svg").read_text()

    slitherflow.main(["auto", "my-pipeline", "--rulegraph", DOT, "--overwrite-spec"])
    assert "Edited title" not in spec.read_text()


def test_draft_and_render(tmp_path):
    spec, svg = tmp_path / "spec.yaml", tmp_path / "map.svg"
    slitherflow.main(["draft", "my-pipeline", "--rulegraph", DOT, "-o", str(spec)])
    slitherflow.main(["render", str(spec), "-o", str(svg)])
    assert svg.read_text().startswith("<svg")


def test_strict_fails_on_overlaps(tmp_path):
    spec = tmp_path / "crowded.yaml"
    spec.write_text(
        'trunk: {stations: [{name: "Trimming"}], lines: [a]}\n'
        'lines:\n'
        '  a: {row: 0, stations: [{name: "A long station name", x: 600}, {name: "Another long name", x: 610}]}\n')
    slitherflow.main(["render", str(spec)])                       # without --strict: warns, carries on
    with pytest.raises(SystemExit) as exc:
        slitherflow.main(["render", str(spec), "--strict"])
    assert exc.value.code == 1
