"""Small pieces: picking the terminus, prettifying rule names, path helpers."""
import pytest

import slitherflow


def graph(edges, nodes):
    succ = {n: [] for n in nodes}
    pred = {n: [] for n in nodes}
    for a, b in edges:
        succ[a].append(b)
        pred[b].append(a)
    return succ, pred


def test_terminus_is_the_end_rule_with_most_inputs():
    succ, pred = graph([("a", "b"), ("a", "c"), ("a", "d"), ("b", "r"), ("c", "r"), ("d", "r"), ("b", "s"), ("c", "s")],
                       "abcdrs")
    assert slitherflow.find_terminus(succ, pred) == "r"


def test_terminus_needs_at_least_two_inputs():
    succ, pred = graph([("a", "b"), ("b", "c"), ("a", "d")], "abcd")
    assert slitherflow.find_terminus(succ, pred) is None


def test_terminus_ignores_rules_with_something_downstream():
    succ, pred = graph([("a", "m"), ("b", "m"), ("m", "z")], "abmz")
    assert slitherflow.find_terminus(succ, pred) is None


def test_terminus_tie_goes_to_more_upstream_rules():
    # r and s both collect from two rules; r has more rules upstream of it
    succ, pred = graph([("a", "b"), ("b", "c"), ("c", "r"), ("b", "r"), ("x", "s"), ("y", "s")], "abcrsxy")
    assert slitherflow.find_terminus(succ, pred) == "r"


@pytest.mark.parametrize("rule, pretty", [
    ("calc_frip", "Calc frip"),
    ("multiqc", "Multiqc"),
    ("genome_featureCounts", "Genome featureCounts"),
    ("peak-calling", "Peak calling"),
])
def test_pretty(rule, pretty):
    assert slitherflow.pretty(rule) == pretty


def test_trim_path_shortens_both_ends():
    pts = slitherflow.trim_path([(0, 0), (100, 0)], 18, 18)
    assert pts[0] == pytest.approx((18, 0)) and pts[-1] == pytest.approx((82, 0))
