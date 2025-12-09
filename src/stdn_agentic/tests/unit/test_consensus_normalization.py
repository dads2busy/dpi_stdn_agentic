"""
Unit tests for build_adaptive_consensus_semantic to verify:
1. No double normalization of component names
2. Confidence scores are preserved (not 0.0)
3. Original component names are preserved
4. Keys match between consensus list and component_details
"""

import pytest

from stdn_agentic.debate import MultiAgentDebater


class TestConsensusNormalization:
    """Test that consensus building preserves names and confidence."""

    @pytest.fixture
    def debater(self):
        """Create a MultiAgentDebater instance."""
        return MultiAgentDebater(
            max_rounds=3,
            convergence_threshold=0.75,
            confidence_weight=0.3,
            peer_support_boost=0.15,
        )

    def test_preserves_llm_normalized_names(self, debater):
        """Test that LLM-normalized names are used directly without rule-based mangling."""
        proposals = [
            {
                "agent_id": "Agent_1",
                "component": "Solar Cells (monocrystalline silicon)",
                "normalized_component": "Solar Cells",  # ✅ LLM normalized
                "confidence": 0.98,
                "reasoning": "Core PV element",
                "round": 1,
            },
            {
                "agent_id": "Agent_2",
                "component": "Solar Cells Monocrystalline Silicon",
                "normalized_component": "Solar Cells",  # ✅ Same normalized name
                "confidence": 0.97,
                "reasoning": "Essential component",
                "round": 1,
            },
            {
                "agent_id": "Agent_3",
                "component": "Monocrystalline Silicon Solar Cells",
                "normalized_component": "Solar Cells",  # ✅ Same normalized name
                "confidence": 0.98,
                "reasoning": "Primary photovoltaic unit",
                "round": 1,
            },
        ]

        consensus, component_details = debater.build_adaptive_consensus_semantic(
            proposals, convergence_score=0.8
        )

        # ✅ Should have consensus
        assert len(consensus) > 0, "Consensus should not be empty"

        # ✅ Check that normalized name is preserved (not mangled by rules)
        assert "Solar Cells" in consensus, f"Expected 'Solar Cells' in consensus, got: {consensus}"

        # ✅ All consensus items should have details
        for norm_name in consensus:
            assert norm_name in component_details, (
                f"Normalized name '{norm_name}' not in component_details. "
                f"Available keys: {list(component_details.keys())}"
            )

        # ✅ Check component_details structure
        assert "Solar Cells" in component_details
        details = component_details["Solar Cells"]

        assert "original_name" in details
        assert "confidence" in details
        assert "reasoning" in details

        # ✅ Confidence should be averaged, NOT 0.0
        assert details["confidence"] > 0.0, "Confidence should not be 0.0"
        assert details["confidence"] >= 0.97, (
            f"Expected confidence ~0.98, got {details['confidence']}"
        )

        # ✅ Original name should be preserved (one of the original proposals)
        original_names = [
            "Solar Cells (monocrystalline silicon)",
            "Solar Cells Monocrystalline Silicon",
            "Monocrystalline Silicon Solar Cells",
        ]
        assert details["original_name"] in original_names, (
            f"Original name '{details['original_name']}' not found in proposals"
        )

        print(f"\n✅ Test passed!")
        print(f"   Consensus: {consensus}")
        print(f"   Details: {component_details}")

    def test_handles_display_oled_case(self, debater):
        """Test the smartphone display (OLED) case that was showing 0.0 confidence."""
        proposals = [
            {
                "agent_id": "Agent_1",
                "component": "Display Module (OLED)",
                "normalized_component": "Display Module",
                "confidence": 0.95,
                "reasoning": "Essential UI component",
                "round": 1,
            },
            {
                "agent_id": "Agent_2",
                "component": "OLED Display",
                "normalized_component": "Display Module",
                "confidence": 0.93,
                "reasoning": "Primary visual output",
                "round": 1,
            },
            {
                "agent_id": "Agent_3",
                "component": "Display (OLED)",
                "normalized_component": "Display Module",
                "confidence": 0.94,
                "reasoning": "Screen component",
                "round": 1,
            },
        ]

        consensus, component_details = debater.build_adaptive_consensus_semantic(
            proposals, convergence_score=0.75
        )

        assert len(consensus) > 0
        assert "Display Module" in consensus
        assert "Display Module" in component_details

        details = component_details["Display Module"]
        assert details["confidence"] > 0.0, "Display confidence should not be 0.0"
        assert details["confidence"] >= 0.93, f"Expected ~0.94, got {details['confidence']}"

        print(f"\n✅ Display (OLED) test passed!")
        print(f"   Confidence: {details['confidence']:.2f}")

    def test_requires_minimum_support(self, debater):
        """Test that components need minimum agent support."""
        proposals = [
            # 3 agents agree on Battery
            {
                "agent_id": "Agent_1",
                "component": "Battery Pack",
                "normalized_component": "Battery Pack",
                "confidence": 0.95,
                "reasoning": "Power source",
                "round": 1,
            },
            {
                "agent_id": "Agent_2",
                "component": "Battery",
                "normalized_component": "Battery Pack",
                "confidence": 0.93,
                "reasoning": "Energy storage",
                "round": 1,
            },
            {
                "agent_id": "Agent_3",
                "component": "Li-ion Battery",
                "normalized_component": "Battery Pack",
                "confidence": 0.94,
                "reasoning": "Power module",
                "round": 1,
            },
            # Only 1 agent proposes Camera (should be excluded with high convergence)
            {
                "agent_id": "Agent_1",
                "component": "Camera Module",
                "normalized_component": "Camera Module",
                "confidence": 0.85,
                "reasoning": "Optional component",
                "round": 1,
            },
        ]

        # High convergence requires 2/3 support
        consensus, component_details = debater.build_adaptive_consensus_semantic(
            proposals, convergence_score=0.9
        )

        # Battery should be included (3/3 agents)
        assert "Battery Pack" in consensus
        assert "Battery Pack" in component_details
        assert component_details["Battery Pack"]["confidence"] > 0.0

        # Camera should be excluded (1/3 agents, below 2/3 threshold)
        assert "Camera Module" not in consensus

        print(f"\n✅ Minimum support test passed!")
        print(f"   Included: {consensus}")
        print(f"   Camera excluded (only 1/3 support)")

    def test_keys_always_match(self, debater):
        """Test that ALL consensus names have matching component_details keys."""
        proposals = [
            {
                "agent_id": f"Agent_{i}",
                "component": comp,
                "normalized_component": norm,
                "confidence": conf,
                "reasoning": "Test component",
                "round": 1,
            }
            for i, (comp, norm, conf) in enumerate(
                [
                    ("Display OLED", "Display", 0.95),
                    ("Display Module", "Display", 0.93),
                    ("Battery Li-ion", "Battery", 0.94),
                    ("Battery Pack", "Battery", 0.92),
                    ("Processor CPU", "Processor", 0.88),
                    ("CPU Module", "Processor", 0.87),
                ],
                start=1,
            )
        ]

        consensus, component_details = debater.build_adaptive_consensus_semantic(
            proposals, convergence_score=0.7
        )

        # ✅ CRITICAL TEST: Every consensus name MUST be in component_details
        missing_keys = [name for name in consensus if name not in component_details]

        assert len(missing_keys) == 0, (
            f"❌ Key mismatch! {len(missing_keys)} consensus names missing from component_details:\n"
            f"   Missing: {missing_keys}\n"
            f"   Consensus: {consensus}\n"
            f"   Details keys: {list(component_details.keys())}"
        )

        # ✅ All details should have required fields and non-zero confidence
        for norm_name, details in component_details.items():
            assert "original_name" in details, f"Missing 'original_name' for {norm_name}"
            assert "confidence" in details, f"Missing 'confidence' for {norm_name}"
            assert "reasoning" in details, f"Missing 'reasoning' for {norm_name}"
            assert details["confidence"] > 0.0, f"Zero confidence for {norm_name}"

        print(f"\n✅ Keys match test passed!")
        print(f"   All {len(consensus)} consensus items have matching details")

    def test_without_normalized_component_field(self, debater):
        """Test fallback when normalized_component field is missing (uses raw name)."""
        proposals = [
            {
                "agent_id": "Agent_1",
                "component": "Battery Pack",  # No normalized_component field
                "confidence": 0.95,
                "reasoning": "Power source",
                "round": 1,
            },
            {
                "agent_id": "Agent_2",
                "component": "Battery Pack",  # Exact same name
                "confidence": 0.93,
                "reasoning": "Energy storage",
                "round": 1,
            },
        ]

        consensus, component_details = debater.build_adaptive_consensus_semantic(
            proposals, convergence_score=0.7
        )

        # Should still work, using raw component name
        assert len(consensus) > 0
        assert "Battery Pack" in consensus
        assert "Battery Pack" in component_details
        assert component_details["Battery Pack"]["confidence"] > 0.0

        print(f"\n✅ Fallback to raw name test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
