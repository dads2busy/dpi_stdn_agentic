"""
Test for country debate transcript integration
"""

import asyncio
import tempfile
from pathlib import Path


async def test_country_debate_transcript():
    """Test that country debates are appended to transcript."""

    print("=" * 80)
    print("TESTING COUNTRY DEBATE TRANSCRIPT INTEGRATION")
    print("=" * 80)

    # Setup
    from pydantic_ai import RunUsage

    from stdn_agentic.data.repository import CountryDataRepository
    from stdn_agentic.models import STDNDependencies

    # Create temp directory for test
    temp_dir = Path(tempfile.mkdtemp())
    transcript_file = temp_dir / "test_smartphone_20251121.txt"

    try:
        # Step 1: Create initial transcript (simulating component/material debate)
        print("\n1. Creating initial transcript...")
        with open(transcript_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("TEST TRANSCRIPT\n")
            f.write("=" * 80 + "\n\n")
            f.write("PHASE 1: COMPONENTS\n")
            f.write("  - display\n")
            f.write("  - battery\n\n")
            f.write("PHASE 2: MATERIALS\n")
            f.write("  - Glass\n")
            f.write("  - Lithium\n\n")

        initial_size = transcript_file.stat().st_size
        print(f"   ✓ Initial transcript size: {initial_size} bytes")

        # Step 2: Setup dependencies
        print("\n2. Setting up dependencies...")

        from ollama import Client  # ← CHANGE TO OLLAMA CLIENT

        from stdn_agentic.data.loaders import DataLoader

        # Load material ontology list from CSV
        material_ontology_list = DataLoader.load_csv(
            "./data/hs_codes_and_usgs_names.csv", column="Elements_Compounds"
        )

        # Create material ontology dict
        material_ontology_dict = {mat.lower(): mat for mat in material_ontology_list}

        # Create Ollama client
        ollama_client = Client()  # ← CREATE OLLAMA CLIENT

        # Create deps with all required parameters
        deps = STDNDependencies(
            model="ollama:qwen2.5:7b",
            material_ontology="./data/hs_codes_and_usgs_names.csv",
            material_ontology_list=material_ontology_list,
            material_ontology_dict=material_ontology_dict,
            years_to_query=[2024],
            top_p=0.0001,
            client=ollama_client,  # ← PASS OLLAMA CLIENT
        )
        print("   ✓ Dependencies created")

        # Step 3: Create repository
        print("\n3. Creating country data repository...")
        repo = CountryDataRepository(
            database_path="./data/world_mineral_commodity_reports_2022-2025_v8.db",
            deps=deps,
            top_n=5,
            use_llm_fallback=True,
        )
        print("   ✓ Repository created")

        # Step 4: Test country debate with transcript appending
        print("\n4. Running country debate for Lithium...")
        usage = RunUsage()

        country_data = await repo.get_country_data(
            material="Lithium",
            src_year=2024,
            meas_year=2024,
            usage=usage,
            use_debate=True,
            transcript_path=transcript_file,  # ← Key parameter
        )

        print(f"   ✓ Got {len(country_data)} countries")

        # Step 5: Verify transcript was appended
        print("\n5. Verifying transcript was updated...")
        final_size = transcript_file.stat().st_size
        print(f"   Initial size: {initial_size} bytes")
        print(f"   Final size: {final_size} bytes")
        print(f"   Added: {final_size - initial_size} bytes")

        if final_size <= initial_size:
            print("   ✗ FAIL: Transcript was not updated!")
            return False

        # Step 6: Check transcript content
        print("\n6. Checking transcript content...")
        with open(transcript_file, "r") as f:
            content = f.read()

        required_sections = [
            "COUNTRY PRODUCTION DEBATE: Lithium",
            "PHASE 1: EXPERT PROPOSALS",
            "PHASE 2: BORDA COUNT VOTING",
            "PHASE 3: FINAL CONSENSUS",
        ]

        missing = []
        for section in required_sections:
            if section in content:
                print(f"   ✓ Found: {section}")
            else:
                print(f"   ✗ Missing: {section}")
                missing.append(section)

        # Step 7: Show sample of appended content
        print("\n7. Sample of appended content:")
        print("-" * 80)
        lines = content.split("\n")
        # Show last 30 lines
        for line in lines[-30:]:
            print(line)
        print("-" * 80)

        # Final verdict
        print("\n" + "=" * 80)
        if missing:
            print("TEST FAILED - Missing sections:", missing)
            return False
        else:
            print("TEST PASSED - All sections found in transcript!")
            print(f"Transcript saved to: {transcript_file}")
            return True

    except Exception as e:
        print(f"\n✗ TEST ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup (comment out to keep transcript for inspection)
        # shutil.rmtree(temp_dir)
        print(f"\nTest transcript kept at: {transcript_file}")


if __name__ == "__main__":
    result = asyncio.run(test_country_debate_transcript())
    exit(0 if result else 1)
