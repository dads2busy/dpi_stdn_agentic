# test_hscode_debug.py

import asyncio
from pathlib import Path

import pandas as pd


def test_hscode_lookup_direct():
    """Test HS_Code lookup directly."""

    print("\n" + "=" * 60)
    print("DEBUG: HS_Code LOOKUP")
    print("=" * 60)

    # 1. Load the CSV
    csv_path = Path("./data/hs_codes_and_usgs_names.csv")
    print(f"\n1. Loading CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"   ✓ Loaded {len(df)} rows")
    print(f"   ✓ Columns: {df.columns.tolist()}")

    # 2. Check if HS_Code column exists
    if "HS_Code" not in df.columns:
        print("   ❌ ERROR: 'HS_Code' column not found!")
        return

    # 3. Test with known materials
    test_materials = ["Lithium", "Gold", "Silicon", "Copper"]

    for material in test_materials:
        print(f"\n2. Testing material: '{material}'")

        # Try exact match
        material_clean = material.lower().strip()
        match = df[df["Elements_Compounds"].str.lower().str.strip() == material_clean]

        if not match.empty:
            hs_code_value = match.iloc[0]["HS_Code"]
            print(f"   ✓ Found exact match")
            print(f"   ✓ Raw HS_Code value: {hs_code_value} (type: {type(hs_code_value)})")

            if pd.notna(hs_code_value):
                hs_code = str(int(hs_code_value))
                print(f"   ✓ Formatted HS_Code: {hs_code}")
            else:
                print(f"   ❌ HS_Code is NaN")
        else:
            print(f"   ❌ No match found for '{material}'")
            # Show what's actually in the CSV
            similar = df[df["Elements_Compounds"].str.contains(material, case=False, na=False)]
            if not similar.empty:
                print(f"   📋 Similar materials in CSV:")
                for idx, row in similar.head(3).iterrows():
                    print(f"      - {row['Elements_Compounds']}")


def test_enricher_output():
    """Test that hs_code makes it to enriched output."""

    print("\n" + "=" * 60)
    print("DEBUG: ENRICHER OUTPUT")
    print("=" * 60)

    # Simulate what enricher does
    country_info = {
        "hs_code": "280520",  # Correct HS code for Lithium
        "country": "China",
        "meas_unit": "MT",
        "amount": 100000.0,
        "percentage": 65.0,
        "confidence": 0.95,
        "reasoning": "Test data",
    }

    print(f"\n6. Simulating enricher dict creation:")
    print(f"   country_info keys: {country_info.keys()}")

    enriched_row = {
        "technology": "Smartphone",
        "component": "Battery",
        "material": "Lithium",
        "hs_code": country_info.get("hs_code"),
    }

    print(f"\n7. Enriched row:")
    print(f"   hs_code value: {enriched_row['hs_code']}")

    if enriched_row["hs_code"]:
        print(f"   ✓ hs_code present in enriched row")
    else:
        print(f"   ❌ hs_code is None in enriched row")


async def test_full_pipeline():
    """Test the complete pipeline with get_country_data."""

    print("\n" + "=" * 60)
    print("DEBUG: FULL PIPELINE TEST (ASYNC)")
    print("=" * 60)

    from stdn_agentic.data.repository import CountryDataRepository
    from stdn_agentic.dependencies import initialize_dependencies
    from stdn_agentic.models import ConfigModel
    from stdn_agentic.utils import read_json_to_dict, validate_config

    # Load config
    config_data = read_json_to_dict("config.json")
    config_data = validate_config(config_data)
    config = ConfigModel(**config_data)

    assert config.usgs_database is not None, "usgs_database must be configured"

    # Initialize dependencies
    deps = initialize_dependencies(config)

    # Create repository
    repo = CountryDataRepository(
        database_path=config.usgs_database,
        deps=deps,
        top_n=5,
        use_llm_fallback=False,
    )

    # Test with years that exist in the database
    print("\n🔍 Testing: Lithium with get_country_data(2022, 2020)")
    data = await repo.get_country_data("Lithium", 2022, 2020)

    print(f"\n📊 Results:")
    print(f"   Returned {len(data)} countries")

    if data and len(data) > 0:
        first = data[0]
        print(f"\n   First country record:")
        print(f"   - Keys: {list(first.keys())}")
        print(f"   - Country: {first.get('country')}")
        print(f"   - hs_code: {first.get('hs_code')}")
        print(f"   - confidence: {first.get('confidence')}")

        if first.get("hs_code"):
            print(f"\n   ✅ SUCCESS: hs_code is present in output!")
            print(f"   ✅ HS_Code value: {first['hs_code']}")
        else:
            print(f"\n   ❌ FAILURE: hs_code is missing!")
            print(f"   Full record: {first}")
    else:
        print(f"   ❌ No data returned")


if __name__ == "__main__":
    test_hscode_lookup_direct()
    test_enricher_output()

    # Run async test
    asyncio.run(test_full_pipeline())

    print("\n" + "=" * 60)
    print("DEBUG COMPLETE")
    print("=" * 60)
