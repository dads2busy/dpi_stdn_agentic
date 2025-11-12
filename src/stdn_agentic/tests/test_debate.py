"""
Test suite for ACTUAL multi-agent debate on BOTH components AND materials

This test file runs the MultiAgentDebater for:
1. Component selection with agent critiques
2. Material selection with agent critiques (per component)
"""

from pathlib import Path

import pytest

from stdn_agentic.orchestrator import DebateReporter, MultiAgentDebater

# Define persistent output directory for transcripts
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEBATE_TRANSCRIPT_DIR = PROJECT_ROOT / "debate_transcripts"
DEBATE_RESULTS_DIR = DEBATE_TRANSCRIPT_DIR / "results"
DEBATE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

print(f"\n{'=' * 80}")
print(f"DEBATE TRANSCRIPTS WILL BE SAVED TO:")
print(f"  {DEBATE_RESULTS_DIR.resolve()}")
print(f"{'=' * 80}\n")


class TestComponentDebate:
    """Test component selection debate"""

    def test_component_debate_with_critiques(self):
        """Test actual component debate execution"""

        print("\n" + "=" * 80)
        print("TEST: COMPONENT DEBATE WITH AGENT CRITIQUES")
        print("=" * 80)

        debater = MultiAgentDebater(max_rounds=3, convergence_threshold=0.75)

        agent_proposals = {
            "Agent_1_Engineer": [
                {"component": "display", "confidence": 0.90, "reasoning": "Visual output"},
                {"component": "battery", "confidence": 0.95, "reasoning": "Power delivery"},
                {"component": "processor", "confidence": 0.85, "reasoning": "Computing"},
            ],
            "Agent_2_SupplyChain": [
                {"component": "display", "confidence": 0.88, "reasoning": "Procurable"},
                {"component": "battery", "confidence": 0.92, "reasoning": "Standard"},
                {"component": "camera", "confidence": 0.75, "reasoning": "Optional"},
            ],
            "Agent_3_Materials": [
                {"component": "display", "confidence": 0.85, "reasoning": "Glass"},
                {"component": "battery", "confidence": 0.93, "reasoning": "Lithium"},
                {"component": "processor", "confidence": 0.88, "reasoning": "Silicon"},
                {"component": "microphone", "confidence": 0.70, "reasoning": "Audio"},
            ],
        }

        print("\nRunning component debate...\n")
        result = debater.run_debate("smartphone_components", agent_proposals)

        assert len(debater.debate_history) > 0
        print(f"\n✓ Component debate completed")
        print(f"  Rounds: {result['num_rounds']}")
        print(f"  Convergence: {result['final_convergence']:.1%}")
        print(f"  Consensus: {[c['component'] for c in result['final_consensus']['components']]}")


class TestMaterialDebate:
    """Test material selection debate"""

    def test_material_debate_for_display(self):
        """Test debate for materials of a single component"""

        print("\n" + "=" * 80)
        print("TEST: MATERIAL DEBATE FOR DISPLAY COMPONENT")
        print("=" * 80)

        debater = MultiAgentDebater(max_rounds=3, convergence_threshold=0.75)
        reporter = DebateReporter(output_dir=str(DEBATE_RESULTS_DIR))

        # Materials for display component - agents disagree
        agent_proposals = {
            "Agent_1_Mining": [
                {"component": "glass", "confidence": 0.95, "reasoning": "Primary substrate"},
                {"component": "aluminum", "confidence": 0.88, "reasoning": "Frame backing"},
                {"component": "copper", "confidence": 0.82, "reasoning": "Conductors"},
                {"component": "rare_earth", "confidence": 0.75, "reasoning": "Phosphors"},
            ],
            "Agent_2_Electronics": [
                {"component": "silicon", "confidence": 0.92, "reasoning": "Controller substrate"},
                {"component": "glass", "confidence": 0.90, "reasoning": "Display cover"},
                {"component": "indium", "confidence": 0.85, "reasoning": "ITO layer"},
                {"component": "tin", "confidence": 0.83, "reasoning": "ITO partner"},
            ],
            "Agent_3_SupplyChain": [
                {"component": "glass", "confidence": 0.93, "reasoning": "Available everywhere"},
                {"component": "aluminum", "confidence": 0.87, "reasoning": "Cost effective"},
                {"component": "silver", "confidence": 0.72, "reasoning": "Optional coating"},
                {"component": "cobalt", "confidence": 0.65, "reasoning": "Trace element"},
            ],
        }

        print("\nRunning materials debate for Display...\n")
        result = debater.run_debate("smartphone_display_materials", agent_proposals)

        assert len(debater.debate_history) > 0

        # Save material debate transcript
        agent_responses = [
            {"agent_id": agent_id, "persona": "Material Expert", "components": proposals}
            for agent_id, proposals in agent_proposals.items()
        ]

        debate_rounds = [
            {
                "round_number": round_data.round_number,
                "convergence_score": round_data.convergence_score,
                "consensus_so_far": round_data.consensus_so_far,
                "agent_responses": [
                    {
                        "agent_id": agent_id,
                        "components": [],
                        "critique_of_others": "\n".join(critiques),
                    }
                    for agent_id, critiques in round_data.critiques.items()
                ],
            }
            for round_data in debater.debate_history
        ]

        text_file = reporter.save_debate_transcript(
            technology="smartphone_display_materials",
            agent_responses=agent_responses,
            debate_rounds=debate_rounds,
            final_consensus=result["final_consensus"],
            file_format="txt",
        )

        json_file = reporter.save_debate_transcript(
            technology="smartphone_display_materials",
            agent_responses=agent_responses,
            debate_rounds=debate_rounds,
            final_consensus=result["final_consensus"],
            file_format="json",
        )

        print(f"\n✓ Material debate completed")
        print(f"  Text transcript: {text_file}")
        print(f"  JSON transcript: {json_file}")
        print(f"  Rounds: {result['num_rounds']}")
        print(f"  Convergence: {result['final_convergence']:.1%}")
        print(
            f"  Consensus materials: {[c['component'] for c in result['final_consensus']['components']]}"
        )

        # Verify files exist
        assert text_file.exists()
        assert json_file.exists()

        # Verify content
        content = text_file.read_text()
        assert "PHASE 1: INDEPENDENT COMPONENT EXTRACTION" in content
        assert "PHASE 2: DEBATE AND CRITIQUE" in content
        assert "PHASE 3: FINAL CONSENSUS" in content
        assert "Critique:" in content or "🤔" in content or "❌" in content

        print("✓ Material debate transcript verified")


class TestFullPipeline:
    """Test full component + materials debate pipeline"""

    def test_component_and_material_debates(self):
        """Test complete pipeline: components then materials"""

        print("\n" + "=" * 80)
        print("TEST: FULL PIPELINE - COMPONENTS + MATERIALS DEBATE")
        print("=" * 80)

        reporter = DebateReporter(output_dir=str(DEBATE_RESULTS_DIR))

        # STEP 1: Component debate
        print("\n📋 STEP 1: Component Debate")
        print("-" * 80)

        component_debater = MultiAgentDebater(max_rounds=3, convergence_threshold=0.75)

        component_proposals = {
            "Agent_1_Engineer": [
                {"component": "display", "confidence": 0.92, "reasoning": "Visual output"},
                {"component": "battery", "confidence": 0.95, "reasoning": "Power source"},
                {"component": "processor", "confidence": 0.87, "reasoning": "Computing core"},
            ],
            "Agent_2_SupplyChain": [
                {"component": "display", "confidence": 0.88, "reasoning": "Procurable"},
                {"component": "battery", "confidence": 0.91, "reasoning": "Standard part"},
                {"component": "camera", "confidence": 0.78, "reasoning": "Optional module"},
            ],
            "Agent_3_Materials": [
                {"component": "display", "confidence": 0.86, "reasoning": "Glass substrate"},
                {"component": "battery", "confidence": 0.93, "reasoning": "Lithium pack"},
                {"component": "processor", "confidence": 0.89, "reasoning": "Silicon die"},
                {"component": "heatsink", "confidence": 0.72, "reasoning": "Thermal mgmt"},
            ],
        }

        component_result = component_debater.run_debate("smartphone", component_proposals)
        consensus_components = [
            c["component"].lower() for c in component_result["final_consensus"]["components"]
        ]

        print(f"\n✓ Component consensus: {consensus_components}")
        print(f"  Convergence: {component_result['final_convergence']:.1%}")

        # STEP 2: Material debate for each component
        print("\n🎤 STEP 2: Material Debate (per component)")
        print("-" * 80)

        all_material_transcripts = []

        for component in consensus_components:
            print(f"\n  Processing: {component.upper()}")

            material_debater = MultiAgentDebater(max_rounds=3, convergence_threshold=0.75)

            # Different material proposals per component
            if component == "display":
                material_proposals = {
                    "Agent_1_Mining": [
                        {"component": "glass", "confidence": 0.95},
                        {"component": "aluminum", "confidence": 0.88},
                        {"component": "copper", "confidence": 0.82},
                    ],
                    "Agent_2_Electronics": [
                        {"component": "glass", "confidence": 0.90},
                        {"component": "silicon", "confidence": 0.92},
                        {"component": "indium", "confidence": 0.85},
                    ],
                    "Agent_3_SupplyChain": [
                        {"component": "glass", "confidence": 0.93},
                        {"component": "aluminum", "confidence": 0.87},
                        {"component": "copper", "confidence": 0.80},
                    ],
                }
            elif component == "battery":
                material_proposals = {
                    "Agent_1_Mining": [
                        {"component": "lithium", "confidence": 0.95},
                        {"component": "cobalt", "confidence": 0.92},
                        {"component": "nickel", "confidence": 0.88},
                    ],
                    "Agent_2_Electronics": [
                        {"component": "lithium", "confidence": 0.93},
                        {"component": "cobalt", "confidence": 0.90},
                        {"component": "manganese", "confidence": 0.85},
                    ],
                    "Agent_3_SupplyChain": [
                        {"component": "lithium", "confidence": 0.94},
                        {"component": "cobalt", "confidence": 0.91},
                        {"component": "nickel", "confidence": 0.87},
                    ],
                }
            else:  # processor
                material_proposals = {
                    "Agent_1_Mining": [
                        {"component": "silicon", "confidence": 0.96},
                        {"component": "copper", "confidence": 0.88},
                        {"component": "gold", "confidence": 0.80},
                    ],
                    "Agent_2_Electronics": [
                        {"component": "silicon", "confidence": 0.95},
                        {"component": "copper", "confidence": 0.90},
                        {"component": "aluminum", "confidence": 0.85},
                    ],
                    "Agent_3_SupplyChain": [
                        {"component": "silicon", "confidence": 0.94},
                        {"component": "copper", "confidence": 0.89},
                        {"component": "tungsten", "confidence": 0.75},
                    ],
                }

            material_result = material_debater.run_debate(
                f"smartphone_{component}_materials", material_proposals
            )

            # Save material transcript
            agent_responses = [
                {
                    "agent_id": agent_id,
                    "persona": f"Material Expert for {component}",
                    "components": proposals,
                }
                for agent_id, proposals in material_proposals.items()
            ]

            debate_rounds = [
                {
                    "round_number": round_data.round_number,
                    "convergence_score": round_data.convergence_score,
                    "consensus_so_far": round_data.consensus_so_far,
                    "agent_responses": [
                        {
                            "agent_id": agent_id,
                            "components": [],
                            "critique_of_others": "\n".join(critiques),
                        }
                        for agent_id, critiques in round_data.critiques.items()
                    ],
                }
                for round_data in material_debater.debate_history
            ]

            transcript = reporter.save_debate_transcript(
                technology=f"smartphone_{component}_materials",
                agent_responses=agent_responses,
                debate_rounds=debate_rounds,
                final_consensus=material_result["final_consensus"],
                file_format="txt",
            )

            all_material_transcripts.append(transcript)

            consensus_materials = [
                c["component"] for c in material_result["final_consensus"]["components"]
            ]
            print(f"    Materials consensus: {consensus_materials}")
            print(f"    Convergence: {material_result['final_convergence']:.1%}")

        # STEP 3: Summary
        print("\n" + "=" * 80)
        print("SUMMARY: FULL COMPONENT + MATERIAL DEBATE PIPELINE")
        print("=" * 80)

        print(f"\n✓ Component consensus: {consensus_components}")
        print(f"✓ Material transcripts generated: {len(all_material_transcripts)}")

        for transcript_file in all_material_transcripts:
            print(f"  - {transcript_file.name}")

        print(f"\n✓ All transcripts available at:")
        print(f"  {DEBATE_RESULTS_DIR.resolve()}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
