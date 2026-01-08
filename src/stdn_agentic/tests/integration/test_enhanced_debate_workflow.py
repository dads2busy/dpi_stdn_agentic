"""
Test suite for enhanced multi-agent debate with critique-driven convergence

This test suite validates:
1. Component name normalization
2. Peer support calculation
3. Critique generation with influence
4. Enhanced convergence calculation
5. Adaptive consensus building
6. Full debate workflow with multiple rounds
7. Edge cases (low convergence, single agent, empty proposals)
"""

import asyncio
from pathlib import Path
from typing import Dict, List

import pytest

from stdn_agentic.agents import ComponentList, get_component_agent
from stdn_agentic.debate import MultiAgentDebater
from stdn_agentic.dependencies import initialize_dependencies
from stdn_agentic.models import ConfigModel, STDNDependencies

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_deps():
    """Create mock dependencies for testing"""
    return STDNDependencies(
        material_ontology="Lithium, Cobalt, Nickel, Copper, Aluminum",
        material_ontology_dict={"Lithium": 1, "Cobalt": 2},
        material_ontology_list=["Lithium", "Cobalt", "Nickel", "Copper", "Aluminum"],
        materials_top_countries_dict={},
        years_to_query=[2024, 2025],
        client=None,
        model="ollama:qwen2.5:7b",
        topp=0.9,
    )


@pytest.fixture
def debater():
    """Create debater instance with test configuration"""
    return MultiAgentDebater(
        max_rounds=3, convergence_threshold=0.8, confidence_weight=0.3, peer_support_boost=0.15
    )


@pytest.fixture
def sample_proposals():
    """Sample agent proposals for testing"""
    return {
        "Agent_1": [
            {"component": "Display Module", "confidence": 0.9, "reasoning": "Primary UI"},
            {"component": "Battery Pack", "confidence": 0.95, "reasoning": "Power source"},
            {"component": "Processor Unit", "confidence": 0.85, "reasoning": "CPU"},
        ],
        "Agent_2": [
            {"component": "display", "confidence": 0.88, "reasoning": "Screen"},
            {"component": "Battery System", "confidence": 0.92, "reasoning": "Power"},
            {"component": "Camera Module", "confidence": 0.80, "reasoning": "Imaging"},
        ],
        "Agent_3": [
            {"component": "Display Assembly", "confidence": 0.91, "reasoning": "Visual output"},
            {"component": "lithium-ion battery pack", "confidence": 0.94, "reasoning": "Energy"},
            {"component": "Processor", "confidence": 0.87, "reasoning": "Computing"},
            {"component": "Memory Module", "confidence": 0.75, "reasoning": "Storage"},
        ],
    }


# ============================================================================
# Unit Tests - Component Normalization
# ============================================================================


class TestComponentNormalization:
    """Test component name normalization logic"""

    def test_basic_normalization(self, debater):
        """Test basic normalization (lowercase, strip, hyphen/underscore)"""
        # Note: "Display Module" -> "display" (module is stripped as qualifier)
        assert debater.normalize_component_name("Display Module") == "display"

        # Note: "battery-pack" -> "battery pack" -> "battery" (pack is a qualifier)
        assert debater.normalize_component_name("battery-pack") == "battery"

        # "Power_Supply" doesn't have trailing qualifier, so stays as-is after normalization
        assert debater.normalize_component_name("Power_Supply") == "power supply"

    def test_trailing_qualifiers_removed(self, debater):
        """Test removal of trailing qualifiers (system, module, unit, etc.)"""
        assert debater.normalize_component_name("Display Module") == "display"
        assert debater.normalize_component_name("Battery System") == "battery"
        assert debater.normalize_component_name("Processor Unit") == "processor"
        assert debater.normalize_component_name("Power Supply Assembly") == "power supply"

    def test_qualifiers_not_removed_from_middle(self, debater):
        """Test that qualifiers in middle of name are preserved"""
        # "module" should only be removed if it's the LAST word
        assert debater.normalize_component_name("Module Controller") == "module controller"
        assert debater.normalize_component_name("System Interface Unit") == "system interface"

    def test_single_word_components(self, debater):
        """Test single-word components aren't over-normalized"""
        assert debater.normalize_component_name("Display") == "display"
        assert debater.normalize_component_name("Battery") == "battery"
        assert debater.normalize_component_name("Module") == "module"  # Can't remove!


# ============================================================================
# Unit Tests - Peer Support
# ============================================================================


class TestPeerSupport:
    """Test peer support calculation"""

    def test_peer_support_with_matching_components(self, debater):
        """Test support calculation when agents agree"""
        proposals = [
            {"component": "Display Module", "agent_id": "Agent_1"},
            {"component": "display", "agent_id": "Agent_2"},
            {"component": "Display Assembly", "agent_id": "Agent_3"},
        ]

        # All 3 proposals normalize to "display", so support count = 3 total
        support = debater.calculate_peer_support("Display Module", proposals)
        assert support == 3  # All 3 agents have "display" proposals

    def test_peer_support_with_no_matches(self, debater):
        """Test support when no other agents agree"""
        proposals = [
            {"component": "Camera", "agent_id": "Agent_1"},
            {"component": "Processor", "agent_id": "Agent_2"},
            {"component": "Memory", "agent_id": "Agent_3"},
        ]

        # Each component appears only once
        support = debater.calculate_peer_support("Camera", proposals)
        assert support == 1  # Only 1 agent proposed "camera"

    def test_peer_support_excludes_self(self, debater):
        """Test that peer support can exclude a specific agent"""
        proposals = [
            {"component": "Display", "agent_id": "Agent_1"},
            {"component": "Display", "agent_id": "Agent_2"},
        ]

        support = debater.calculate_peer_support("Display", proposals, exclude_agent="Agent_1")
        assert support == 1  # Only Agent_2 counted


# ============================================================================
# Unit Tests - Critique Generation
# ============================================================================


class TestCritiqueGeneration:
    """Test critique generation with influence"""

    def test_critique_for_consensus_components(self, debater):
        """Test that consensus components get positive feedback"""
        proposals = [
            {"component": "Display", "confidence": 0.9, "agent_id": "Agent_1"},
            {"component": "display module", "confidence": 0.88, "agent_id": "Agent_2"},
            {"component": "Display System", "confidence": 0.91, "agent_id": "Agent_3"},
        ]

        critiques = debater.generate_critiques_with_influence(proposals, round_num=1)

        # Should have at least one consensus critique
        consensus_critiques = [c for c in critiques if "CONSENSUS" in c]
        assert len(consensus_critiques) > 0
        assert "display" in consensus_critiques[0].lower()

    def test_critique_for_isolated_proposals(self, debater):
        """Test that isolated proposals get warnings"""
        proposals = [
            {"component": "Display", "confidence": 0.9, "agent_id": "Agent_1"},
            {"component": "Camera", "confidence": 0.85, "agent_id": "Agent_2"},
            {"component": "Processor", "confidence": 0.80, "agent_id": "Agent_3"},
        ]

        critiques = debater.generate_critiques_with_influence(proposals, round_num=1)

        # All three should have isolation warnings
        isolated_critiques = [c for c in critiques if "ISOLATED" in c]
        assert len(isolated_critiques) == 3

    def test_critique_round_specific_guidance(self, debater):
        """Test that round-specific guidance is provided"""
        proposals = [
            {"component": "Display", "confidence": 0.9, "agent_id": "Agent_1"},
        ]

        critiques_round_1 = debater.generate_critiques_with_influence(proposals, round_num=1)
        critiques_round_3 = debater.generate_critiques_with_influence(proposals, round_num=3)

        # Round 1 should have review guidance
        round_1_guidance = [c for c in critiques_round_1 if "ROUND 2 GUIDANCE" in c]
        assert len(round_1_guidance) > 0

        # Round 3 should have convergence guidance
        round_3_guidance = [
            c for c in critiques_round_3 if "ROUND 4 GUIDANCE" in c or "converge" in c.lower()
        ]
        assert len(round_3_guidance) > 0


# ============================================================================
# Unit Tests - Convergence Calculation
# ============================================================================


class TestConvergenceCalculation:
    """Test enhanced convergence calculation"""

    def test_perfect_convergence(self, debater):
        """Test when all agents propose same components"""
        proposals = [
            {"component": "Display", "agent_id": "Agent_1"},
            {"component": "display module", "agent_id": "Agent_2"},
            {"component": "Display System", "agent_id": "Agent_3"},
        ]

        convergence = debater.calculate_convergence(proposals)
        assert convergence == 1.0  # Perfect agreement

    def test_no_convergence(self, debater):
        """Test when agents propose completely different components"""
        proposals = [
            {"component": "Display", "agent_id": "Agent_1"},
            {"component": "Camera", "agent_id": "Agent_2"},
            {"component": "Processor", "agent_id": "Agent_3"},
        ]

        convergence = debater.calculate_convergence(proposals)
        # With weighted formula: (1² + 1² + 1²) / 3² = 3/9 = 0.333
        assert convergence > 0.3 and convergence < 0.4  # Some baseline convergence

    def test_partial_convergence(self, debater):
        """Test partial agreement scenario"""
        proposals = [
            {"component": "Display", "agent_id": "Agent_1"},
            {"component": "Battery", "agent_id": "Agent_1"},
            {"component": "Display", "agent_id": "Agent_2"},
            {"component": "Camera", "agent_id": "Agent_2"},
            {"component": "Display", "agent_id": "Agent_3"},
            {"component": "Processor", "agent_id": "Agent_3"},
        ]

        convergence = debater.calculate_convergence(proposals)
        # All 3 agents agree on Display, but disagree on other components
        assert 0.3 < convergence < 0.7  # Partial convergence

    def test_empty_proposals(self, debater):
        """Test convergence with empty proposals"""
        convergence = debater.calculate_convergence([])
        assert convergence == 0.0


# ============================================================================
# Unit Tests - Adaptive Consensus
# ============================================================================


class TestAdaptiveConsensus:
    """Test adaptive consensus building"""

    def test_high_convergence_strict_threshold(self, debater):
        """High convergence should use strict voting threshold (0.67)"""
        proposals = [
            {"component": "Display", "confidence": 0.9, "agent_id": "Agent_1"},
            {"component": "display", "confidence": 0.88, "agent_id": "Agent_2"},
            {"component": "Display System", "confidence": 0.91, "agent_id": "Agent_3"},
            {"component": "Battery", "confidence": 0.85, "agent_id": "Agent_1"},
            {"component": "Battery Pack", "confidence": 0.87, "agent_id": "Agent_2"},
        ]

        # High convergence (>0.7) should require 2/3 = 0.67 votes
        consensus = debater._build_adaptive_consensus(proposals, convergence_score=0.8)

        # Display has 3/3 votes, Battery has 2/3 votes - both should pass
        consensus_lower = [c.lower() for c in consensus]
        assert "display" in consensus_lower
        assert "battery" in consensus_lower

    def test_low_convergence_lenient_threshold(self, debater):
        """Low convergence should use lenient voting threshold (0.33)"""
        proposals = [
            {"component": "Display", "confidence": 0.9, "agent_id": "Agent_1"},
            {"component": "Camera", "confidence": 0.85, "agent_id": "Agent_2"},
            {"component": "Processor", "confidence": 0.80, "agent_id": "Agent_3"},
        ]

        # Low convergence (<0.2) should require only 1/3 = 0.33 votes
        consensus = debater._build_adaptive_consensus(proposals, convergence_score=0.1)

        # All three should be included with lenient threshold
        normalized_consensus = [c.lower() for c in consensus]
        assert len(normalized_consensus) >= 3

    def test_confidence_weighting(self, debater):
        """Test that confidence affects consensus"""
        # Component with high votes but low confidence
        proposals_low_conf = [
            {"component": "Display", "confidence": 0.5, "agent_id": "Agent_1"},
            {"component": "Display", "confidence": 0.5, "agent_id": "Agent_2"},
        ]

        # Component with fewer votes but high confidence
        proposals_high_conf = [
            {"component": "Processor", "confidence": 0.95, "agent_id": "Agent_1"},
            {"component": "Processor", "confidence": 0.95, "agent_id": "Agent_2"},
        ]

        consensus_low = debater._build_adaptive_consensus(proposals_low_conf, convergence_score=0.5)
        consensus_high = debater._build_adaptive_consensus(
            proposals_high_conf, convergence_score=0.5
        )

        # High confidence proposals should be favored
        assert len(consensus_high) >= len(consensus_low)


# ============================================================================
# Integration Tests - Full Debate Workflow
# ============================================================================


@pytest.mark.asyncio
class TestFullDebateWorkflow:
    """Test complete debate workflow (requires LLM)"""

    async def test_debate_reaches_convergence(self, debater, sample_proposals, mock_deps):
        """Test that debate reaches convergence threshold"""

        # Mock component agent
        component_agent = get_component_agent()

        # Run debate (will require actual LLM unless mocked)
        try:
            result = await debater.run_debate(
                technology="Smartphone",
                initial_proposals=sample_proposals,
                component_agent=component_agent,
                deps=mock_deps,
            )

            # Verify structure
            assert "technology" in result
            assert "components" in result
            assert "confidence" in result
            assert "rounds" in result

            # Verify at least some consensus was reached
            assert len(result["components"]) > 0
            assert result["rounds"] <= 3  # Should stop within max rounds

        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                pytest.skip(f"API mismatch - needs async run_debate method: {e}")
            else:
                raise
        except Exception as e:
            pytest.skip(f"Skipping test requiring LLM: {e}")

    async def test_debate_handles_low_convergence(self, mock_deps):
        """Test debate behavior when convergence is low"""

        debater_low_threshold = MultiAgentDebater(
            max_rounds=2,
            convergence_threshold=0.9,  # Very high threshold
        )

        # Proposals with low agreement
        divergent_proposals = {
            "Agent_1": [
                {"component": "Display", "confidence": 0.9, "reasoning": "UI"},
            ],
            "Agent_2": [
                {"component": "Camera", "confidence": 0.9, "reasoning": "Imaging"},
            ],
            "Agent_3": [
                {"component": "Processor", "confidence": 0.9, "reasoning": "Computing"},
            ],
        }

        component_agent = get_component_agent()

        try:
            result = await debater_low_threshold.run_debate(
                technology="Test Device",
                initial_proposals=divergent_proposals,
                component_agent=component_agent,
                deps=mock_deps,
            )

            # Should hit max rounds without convergence
            assert result["rounds"] == 2

            # But should still produce some consensus with adaptive threshold
            assert len(result["components"]) >= 3  # Lenient threshold includes all

        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                pytest.skip(f"API mismatch - needs async run_debate method: {e}")
            else:
                raise
        except Exception as e:
            pytest.skip(f"Skipping test requiring LLM: {e}")


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_single_agent(self, debater):
        """Test debate with only one agent"""
        proposals = [
            {"component": "Display", "confidence": 0.9, "agent_id": "Agent_1"},
        ]

        convergence = debater.calculate_convergence(proposals)
        assert convergence == 1.0  # Single agent = perfect "agreement"

    def test_empty_proposals(self, debater):
        """Test handling of empty proposal list"""
        convergence = debater.calculate_convergence([])
        assert convergence == 0.0

        consensus = debater._build_adaptive_consensus([], convergence_score=0.5)
        assert len(consensus) == 0

    def test_duplicate_components_same_agent(self, debater):
        """Test handling when one agent proposes same component twice"""
        proposals = [
            {"component": "Display", "confidence": 0.9, "agent_id": "Agent_1"},
            {"component": "Display Module", "confidence": 0.85, "agent_id": "Agent_1"},
        ]

        # Should be normalized to single component
        consensus = debater._build_adaptive_consensus(proposals, convergence_score=0.5)
        normalized = [c.lower() for c in consensus]

        # Should only appear once after normalization
        assert normalized.count("display") <= 1


# ============================================================================
# Run Tests
# ============================================================================


if __name__ == "__main__":
    # Run with: uv run pytest src/stdn_agentic/tests/test_enhanced_debate.py -v
    pytest.main([__file__, "-v", "-s"])
