import json

import pytest

from scripts.sensitivity_tau_rounds import (
    canonical_set,
    consensus_at_round,
    per_tech_median_jaccard,
    stop_round,
    stop_round_for_tau,
)

SAMPLE = "output/transcripts/5G_Base_Station_(Macro_Cell)_d3v1v1_20260414_140920.json"


@pytest.fixture
def sample_transcript():
    return json.load(open(SAMPLE))


def test_stop_round_for_tau_picks_first_round_meeting_threshold():
    rounds = [{"convergence": 0.55}, {"convergence": 0.72}, {"convergence": 0.9}]
    assert stop_round_for_tau(rounds, 0.5) == 1
    assert stop_round_for_tau(rounds, 0.7) == 2
    assert stop_round_for_tau(rounds, 0.95) == 3  # cap reached


def test_stop_round_applies_round_cap_after_tau():
    rounds = [{"convergence": 0.55}, {"convergence": 0.62}, {"convergence": 0.9}]
    assert stop_round(rounds, tau=0.7, cap=2) == 2
    assert stop_round(rounds, tau=0.6, cap=3) == 2
    assert stop_round(rounds, tau=0.7, cap=1) == 1


def test_consensus_at_round_matches_pipeline_final_when_last_round_used(sample_transcript):
    t = sample_transcript
    rebuilt = consensus_at_round(t, len(t["component_stage"]["phase2_debate_rounds"]))
    assert set(rebuilt) == set(t["component_stage"]["phase3_final_consensus"]["components"])


def test_canonical_set_drops_non_primary_and_keeps_unknown_verbatim():
    vocab = {"radio unit": "Radio Unit (RU)", "fan tray": "__NON_PRIMARY__"}
    s, unmapped = canonical_set(["Radio Unit", "Fan Tray", "Mystery Box"], vocab)
    assert s == {"Radio Unit (RU)", "Mystery Box"} and unmapped == 1


def test_per_tech_median_jaccard_skips_single_run_techs():
    sets = {"a": [{"x", "y"}, {"x"}, {"x", "y"}], "b": [{"z"}]}
    assert per_tech_median_jaccard(sets) == {"a": 0.5}


def test_unmapped_names_by_tech_dedupes_by_vocab_key():
    from scripts.sensitivity_tau_rounds import unmapped_names_by_tech
    vocab = {"radio unit": "Radio Unit (RU)"}
    picked = [("5G", ["Radio Unit", "Fan Tray", "fan tray"]), ("5G", ["Fan  Tray."]), ("Phone", ["Battery"])]
    assert unmapped_names_by_tech(picked, vocab) == {"5G": ["Fan Tray"], "Phone": ["Battery"]}
