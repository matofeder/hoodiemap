import pytest

import ahp

C4 = ["kindergarten", "school", "playground", "doctors"]
J4 = {"kindergarten|school": 1, "kindergarten|playground": 3, "kindergarten|doctors": 5,
      "school|playground": 3, "school|doctors": 5, "playground|doctors": 2}


def test_perfectly_consistent_matrix_has_cr_zero_and_exact_weights():
    # weights 4:2:1 -> judgments are exact ratios
    r = ahp.weigh(["a", "b", "c"], {"a|b": 2, "a|c": 4, "b|c": 2})
    assert r.weights == pytest.approx({"a": 4 / 7, "b": 2 / 7, "c": 1 / 7})
    assert r.lambda_max == pytest.approx(3.0)
    assert r.cr == pytest.approx(0.0, abs=1e-9) and r.consistent


def test_worked_example_from_the_methodology():
    r = ahp.weigh(C4, J4)
    assert [round(r.weights[c], 3) for c in C4] == [0.394, 0.394, 0.137, 0.075]
    assert r.lambda_max == pytest.approx(4.0042, abs=1e-4)
    assert r.cr == pytest.approx(0.0015, abs=1e-4)


def test_contradictions_raise_cr_above_the_limit():
    # a > b, b > c, but c > a: circular
    r = ahp.weigh(["a", "b", "c"], {"a|b": 5, "a|c": 1 / 5, "b|c": 5})
    assert r.cr > ahp.CR_LIMIT and not r.consistent


def test_matrix_validation():
    with pytest.raises(ahp.AHPError, match="missing"):
        ahp.weigh(["a", "b", "c"], {"a|b": 2, "a|c": 4})
    with pytest.raises(ahp.AHPError, match="scale"):
        ahp.weigh(["a", "b"], {"a|b": 10})
    with pytest.raises(ahp.AHPError, match="scale"):
        ahp.weigh(["a", "b"], {"a|b": 2.5})
    with pytest.raises(ahp.AHPError, match="unknown"):
        ahp.weigh(["a", "b"], {"a|b": 2, "b|a": 1 / 2})
    assert ahp.on_scale(1 / 7) and not ahp.on_scale(0)


def test_pairs_cover_every_comparison_once():
    assert ahp.pairs(["a", "b", "c", "d"]) == [("a", "b"), ("a", "c"), ("a", "d"), ("b", "c"), ("b", "d"), ("c", "d")]


def test_group_combines_consistent_experts_by_geometric_mean():
    second = {**J4, "kindergarten|school": 2}
    contradictory = {**J4, "kindergarten|playground": 1 / 9, "playground|doctors": 9, "kindergarten|doctors": 9}
    g = ahp.group(C4, [J4, second, contradictory])
    assert g.used == [0, 1]
    assert not g.individual[2].consistent
    assert [round(g.result.weights[c], 3) for c in C4] == [0.428, 0.36, 0.137, 0.075]
    assert ahp.combine(C4, [J4, second])["kindergarten|school"] == pytest.approx(2 ** 0.5)


def test_group_without_any_consistent_expert():
    bad = {"a|b": 9, "a|c": 1 / 9, "b|c": 9}
    g = ahp.group(["a", "b", "c"], [bad])
    assert g.result is None and g.used == []


def test_equal_weights_default():
    assert ahp.equal(["a", "b", "c", "d"]) == {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}
