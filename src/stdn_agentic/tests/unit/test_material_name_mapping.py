# test_material_name_mapping.py

from pathlib import Path

import ollama
import pandas as pd

from stdn_agentic.debate.material_debater import MaterialDebater, MaterialProposal
from stdn_agentic.models import STDNDependencies


def test_material_name_preservation():
    """Test that consensus preserves exact material names from ontology."""

    # Load real ontology from CSV
    csv_path = Path("./data/hs_codes_and_usgs_names.csv")
    df = pd.read_csv(csv_path)
    material_list = df["Elements_Compounds"].tolist()

    # Create minimal deps
    deps = STDNDependencies(
        material_ontology=", ".join(material_list),
        material_ontology_dict={},
        material_ontology_list=material_list,
        years_to_query=[2024],
        client=ollama.Client(),
        model="qwen2.5:7b",
        top_p=0.0001,
    )

    # Create debater
    debater = MaterialDebater(deps=deps, num_agents=3)

    # Build material name map (simulate what run_full_debate does)
    debater.material_name_map = {}
    for original_name in material_list:
        normalized = debater.normalize_material_name(original_name)
        debater.material_name_map[normalized] = original_name

    # Create mock proposals with NORMALIZED names
    # (simulating what LLM might return)
    proposals = [
        MaterialProposal(
            agentid="Agent1",
            component="Battery",
            material="lithium",  # lowercase (LLM output)
            confidence=0.9,
            reasoning="Test",
            normalizedcomponent="battery",
            normalizedmaterial="lithium",  # normalized
            round=1,
        ),
        MaterialProposal(
            agentid="Agent2",
            component="Battery",
            material="Lithium",  # Different case
            confidence=0.85,
            reasoning="Test",
            normalizedcomponent="battery",
            normalizedmaterial="lithium",  # same normalized
            round=1,
        ),
        MaterialProposal(
            agentid="Agent3",
            component="Battery",
            material="LITHIUM",  # All caps
            confidence=0.88,
            reasoning="Test",
            normalizedcomponent="battery",
            normalizedmaterial="lithium",  # same normalized
            round=1,
        ),
    ]

    # Build consensus
    consensus = debater.build_adaptive_consensus(
        proposals=proposals,
        convergence_score=0.9,
        expected_components=["Battery"],
    )

    # Verify consensus uses EXACT name from CSV
    battery_key = "Battery" if "Battery" in consensus else "battery"
    assert battery_key in consensus, "Battery not found in consensus"

    battery_materials = consensus[battery_key]  # ✅ Direct access, not .get()
    assert len(battery_materials) == 1, "Should have 1 consensus material"

    material_name = battery_materials[0]["name"]

    # Check that the output name matches EXACTLY what's in the CSV
    assert material_name in material_list, f"'{material_name}' not found in ontology"

    # Verify it's the properly-cased version from CSV, not lowercase
    assert material_name == "Lithium", f"Expected 'Lithium', got '{material_name}'"

    print(f"✓ Test passed: Consensus uses exact ontology name '{material_name}'")
    print("✓ LLM proposals were: 'lithium', 'Lithium', 'LITHIUM'")
    print(f"✓ Consensus normalized all to: '{material_name}' (from ontology)")


if __name__ == "__main__":
    test_material_name_preservation()
