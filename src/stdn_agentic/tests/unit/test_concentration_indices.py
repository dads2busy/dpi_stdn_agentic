import importlib.util
from pathlib import Path

import pytest

_p = Path(__file__).resolve().parents[4] / "scripts" / "concentration_indices.py"
_spec = importlib.util.spec_from_file_location("concentration_indices", _p)
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)


def test_hhi_percent_scale():
    assert ci.hhi({"CHN": 75, "USA": 10, "AUS": 7, "RUS": 5, "IND": 3}) == 5808


def test_weighted_hhi_eu_scale():
    # single producer with the worst score -> 10; with the best score -> 0
    assert ci.weighted_hhi({"X": 100}, {"X": 10.0}) == pytest.approx(10.0)
    assert ci.weighted_hhi({"X": 100}, {"X": 0.0}) == pytest.approx(0.0)
    assert ci.weighted_hhi({"A": 50, "B": 50}, {"A": 10.0, "B": 0.0}) == pytest.approx(2.5)


def test_score_rescaling():
    assert ci.wgi_to_score(2.5) == 0.0 and ci.wgi_to_score(-2.5) == 10.0 and ci.wgi_to_score(-3.0) == 10.0
    assert ci.hdi_to_score(1.0) == 0.0 and ci.hdi_to_score(0.5) == pytest.approx(5.0)


def test_impute_uses_share_weighted_mean_of_named_producers():
    w, missing = ci.impute({"A": 60, "B": 20, "OTHER": 20}, {"A": 2.0, "B": 6.0})
    assert missing == ["OTHER"]
    assert w["OTHER"] == pytest.approx((2.0 * 60 + 6.0 * 20) / 80)
