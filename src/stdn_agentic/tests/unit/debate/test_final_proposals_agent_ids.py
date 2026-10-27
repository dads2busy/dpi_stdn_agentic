from stdn_agentic.debate.component_debater import MultiAgentDebater


def _debater():
    return MultiAgentDebater(max_rounds=3, convergence_threshold=0.7, confidence_weight=0.3, peer_support_boost=0.15)


def test_flatten_final_proposals_tags_each_proposal_with_its_agent():
    # Round-1 proposals (from _normalize_initial_proposals) carry no agent_id.
    current = {"Agent_1": [{"component": "Battery"}], "Agent_2": [{"component": "Display", "agent_id": "Agent_2"}]}
    flat = _debater()._flatten_final_proposals(current)
    assert [p["agent_id"] for p in flat] == ["Agent_1", "Agent_2"]
    assert current["Agent_1"][0]["agent_id"] == "Agent_1"  # in place, so the transcript records it


def test_one_round_consensus_requires_multi_agent_support():
    current = {
        "Agent_1": [{"component": "Battery", "normalized_component": "battery", "confidence": 0.9},
                    {"component": "Laser", "normalized_component": "laser", "confidence": 0.9}],
        "Agent_2": [{"component": "Battery", "normalized_component": "battery", "confidence": 0.9}],
        "Agent_3": [{"component": "Battery", "normalized_component": "battery", "confidence": 0.9}],
    }
    d = _debater()
    consensus, _ = d.build_adaptive_consensus_semantic(d._flatten_final_proposals(current), convergence_score=0.95)
    assert consensus == ["Battery"]  # "Laser" has 1 of 3 agents, below the 2/3 support needed at high convergence
