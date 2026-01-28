"""
E2E test: Single technology through pipeline with no debate.

This test runs a single technology through the complete STDN pipeline
with all debate options disabled (ENABLE_COMPONENT_DEBATE=false,
ENABLE_MATERIAL_DEBATE=false, ENABLE_COUNTRY_DEBATE=false).

The output file should use the new naming convention: stdns_output_v1v1v1_{timestamp}.csv
"""

from pathlib import Path

import pytest

from stdn_agentic.models import ConfigModel
from stdn_agentic.orchestrator.pipeline import STDNOrchestrator


@pytest.fixture
def test_config():
    """Create test configuration."""
    # Find project root
    current = Path(__file__).parent
    project_root = current
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            project_root = parent
            break

    output_dir = project_root / "output" / "test_no_debate"
    output_dir.mkdir(parents=True, exist_ok=True)

    return ConfigModel(
        import_tech_list=str(project_root / "data" / "tech_list.csv"),
        model="ollama:qwen2.5:7b",
        output_dir=str(output_dir),
        output_csv_filename="stdns_output",
        usgs_database=str(
            project_root / "data" / "world_mineral_commodity_reports_2022-2025_v8.db"
        ),
        years_to_query=[2023, 2024],
        top_n_countries=5,
        write_nulls_to_output=True,
    )


class TestSingleTechNoDebate:
    """Test single technology pipeline run with no debate."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_single_tech_no_debate_output_naming(self, test_config):
        """
        Test that running a single technology with all debates disabled:
        1. Produces an output file
        2. Output filename contains v1v1v1 (no debate config)
        3. Pipeline completes successfully
        """
        # Create orchestrator with all debates disabled
        orchestrator = STDNOrchestrator(
            config=test_config,
            enable_debate=False,
            enable_material_debate=False,
            enable_country_debate=False,
            num_agents_component=3,  # These won't be used since debate is disabled
            num_agents_material=3,
            num_agents_country=3,
            max_debate_rounds=3,
            convergence_threshold=0.8,
            save_transcripts=False,
        )

        # Verify output filename contains v1v1v1
        assert "v1v1v1" in orchestrator.output_file, (
            f"Expected 'v1v1v1' in output filename, got: {orchestrator.output_file}"
        )

        print(f"\n✓ Output file will be: {orchestrator.output_file}")

        # Run pipeline with a single technology
        result = await orchestrator.run_pipeline(
            technologies=["solar panel"],
            role="supply chain analyst",
            domain="renewable energy",
        )

        # Verify pipeline completed
        assert result is not None, "Pipeline returned None"
        assert "successful" in result, "Result missing 'successful' key"
        assert "failed" in result, "Result missing 'failed' key"

        print("\n✓ Pipeline completed:")
        print(f"  - Successful: {result['successful']}")
        print(f"  - Failed: {result['failed']}")

        # Verify output file was created
        output_path = Path(orchestrator.output_file)
        assert output_path.exists(), f"Output file not created: {output_path}"

        # Verify filename format
        filename = output_path.name
        assert filename.startswith("stdns_output_v1v1v1_"), (
            f"Filename should start with 'stdns_output_v1v1v1_', got: {filename}"
        )
        assert filename.endswith(".csv"), f"Filename should end with '.csv', got: {filename}"

        print(f"✓ Output file created: {filename}")

        # Read and display first few lines
        with open(output_path, "r") as f:
            lines = f.readlines()
            print(f"✓ Output file has {len(lines)} lines (including header)")
            if len(lines) > 1:
                print(f"  Header: {lines[0].strip()[:100]}...")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_debate_config_string_variations(self, test_config):
        """Test that different debate configurations produce correct filename patterns."""
        test_cases = [
            # (enable_debate, enable_material, enable_country, num_comp, num_mat, num_country, expected)
            (False, False, False, 3, 3, 3, "v1v1v1"),
            (True, False, False, 3, 3, 3, "d3v1v1"),
            (False, True, False, 3, 3, 3, "v1d3v1"),
            (False, False, True, 3, 3, 3, "v1v1v3"),
            (True, True, True, 3, 3, 3, "d3d3v3"),
            (True, True, True, 5, 4, 3, "d5d4v3"),
        ]

        for (
            enable_debate,
            enable_material,
            enable_country,
            num_comp,
            num_mat,
            num_country,
            expected,
        ) in test_cases:
            orchestrator = STDNOrchestrator(
                config=test_config,
                enable_debate=enable_debate,
                enable_material_debate=enable_material,
                enable_country_debate=enable_country,
                num_agents_component=num_comp,
                num_agents_material=num_mat,
                num_agents_country=num_country,
                save_transcripts=False,
            )

            assert expected in orchestrator.output_file, (
                f"Expected '{expected}' in filename for config "
                f"(debate={enable_debate}, mat={enable_material}, country={enable_country}, "
                f"agents={num_comp},{num_mat},{num_country}), "
                f"got: {orchestrator.output_file}"
            )

            print(
                f"✓ Config ({enable_debate}, {enable_material}, {enable_country}) "
                f"agents=({num_comp},{num_mat},{num_country}) -> {expected}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
