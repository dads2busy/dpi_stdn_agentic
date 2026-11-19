import csv
import json

from scripts.debate_mechanism_by_domain import TYPES, metrics_for_transcript

MULTI_ROUND = "output/transcripts/5G_Base_Station_(Macro_Cell)_d3v1v1_20260414_140920.json"
ONE_ROUND = "output/transcripts/Automotive_ECU_(Engine_Control_Unit)_d3v1v1_20260414_140920.json"


def test_metrics_for_transcript_returns_bounded_values():
    m = metrics_for_transcript(json.load(open(MULTI_ROUND)))
    assert set(m) == {"r1_agreement", "rounds", "r1_candidates", "consolidation", "stopped_r1"}
    assert 0.0 <= m["r1_agreement"] <= 1.0 and 0.0 <= m["consolidation"] <= 1.0
    assert isinstance(m["rounds"], int) and m["rounds"] >= 2
    assert isinstance(m["r1_candidates"], int) and m["r1_candidates"] > 0
    assert m["stopped_r1"] is False


def test_metrics_flag_one_round_debates():
    m = metrics_for_transcript(json.load(open(ONE_ROUND)))
    assert m["rounds"] == 1 and m["stopped_r1"] is True


def test_type_labels_cover_the_benchmark_with_known_types():
    rows = list(csv.DictReader(open("data/tech_type_labels.csv")))
    assert len(rows) == 180 and {r["type"] for r in rows} <= set(TYPES)
    assert len({(r["domain"], r["tech"]) for r in rows}) == 180
