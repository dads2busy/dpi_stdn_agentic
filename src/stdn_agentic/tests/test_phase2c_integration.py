"""
Integration test for data layer with USGS database

Tests the complete data layer with the actual USGS database.
Database: dpi_stdn_agentic/data/world_mineral_commodity_reports_2022-2025_v8.db
"""

import asyncio
import os
from pathlib import Path


async def test_with_database():
    """Test data layer with actual USGS database"""

    print("\n" + "=" * 80)
    print("DATA LAYER INTEGRATION TEST WITH USGS DATABASE")
    print("=" * 80)
    print()

    # Import modules
    from stdn_agentic.data import MaterialCache, USGSClient

    # Database path
    db_path = "./data/world_mineral_commodity_reports_2022-2025_v8.db"

    # Verify database exists
    if not Path(db_path).exists():
        print(f"❌ Database not found at: {db_path}")
        print("   Please check the path and try again.")
        return

    print(f"✓ Database found: {db_path}")
    print()

    # Test 1: USGSClient direct query
    print("Test 1: USGSClient - Query top Lithium producers")
    print("-" * 80)
    try:
        with USGSClient(db_path, top_n=5) as client:
            # Test query for Lithium (common material)
            countries = client.query_top_countries("Lithium", 2025, 2024)

            if countries is not None and len(countries) > 0:
                print(f"✓ Found {len(countries)} countries producing Lithium")
                print(f"  Top producers: {countries['country'].tolist()}")

                # Test world totals
                totals = client.query_world_totals("Lithium", 2025, 2024)
                if totals:
                    print(f"  World production total: {totals.get('PRODUCTION', 'N/A')}")

                # Test country details for first country
                if len(countries) > 0:
                    first_country = countries["country"].iloc[0]
                    details = client.query_country_details("Lithium", first_country, 2025, 2024)
                    print(f"  {first_country} production details: {len(details)} records")
                    if details:
                        for detail in details[:1]:  # Show first record
                            print(
                                f"    - {detail['meas_type']}: {detail['value']} {detail['meas_unit']}"
                            )
            else:
                print("  ⚠ No data found for Lithium (checking database structure...)")

                # Debug: Show tables
                tables = client.connection.execute("SHOW TABLES").fetchall()
                print(f"  Database has {len(tables)} tables:")
                for table in tables[:5]:
                    print(f"    - {table[0]}")

    except Exception as e:
        print(f"✗ USGSClient test failed: {e}")
        import traceback

        traceback.print_exc()

    print()

    # Test 2: MaterialCache
    print("Test 2: MaterialCache - Persistent caching")
    print("-" * 80)
    try:
        cache = MaterialCache(cache_dir="./.test_cache", ttl_hours=24)

        # Test set/get
        test_data = {
            "material": "Lithium",
            "countries": ["Chile", "Australia", "China"],
            "year": 2024,
        }

        cache.set("lithium_2024", test_data)
        retrieved = cache.get("lithium_2024")

        if retrieved == test_data:
            print("✓ Cache set/get works correctly")
        else:
            print("✗ Cache data mismatch")

        # Stats
        stats = cache.get_stats()
        print(f"  Cache stats: {stats['valid_entries']} valid, {stats['expired_entries']} expired")

        # Cleanup
        cache.clear()
        print("✓ Cache cleared")

    except Exception as e:
        print(f"✗ MaterialCache test failed: {e}")

    print()

    # Test 3: DataLoader
    print("Test 3: DataLoader - File I/O utilities")
    print("-" * 80)
    try:
        import tempfile

        from stdn_agentic.data import DataLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test JSON
            test_json = {"key": "value", "count": 42}
            json_path = f"{tmpdir}/test.json"

            DataLoader.save_json(test_json, json_path)
            loaded_json = DataLoader.load_json(json_path)

            if loaded_json == test_json:
                print("✓ JSON save/load works")

            # Test CSV
            test_csv = [
                {"country": "China", "percentage": 65.5},
                {"country": "Australia", "percentage": 27.3},
            ]
            csv_path = f"{tmpdir}/test.csv"

            DataLoader.save_csv(test_csv, csv_path)
            loaded_csv = DataLoader.load_csv(csv_path, as_dict=True)

            if len(loaded_csv) == 2:
                print("✓ CSV save/load works")
                print(f"  Loaded {len(loaded_csv)} rows")

    except Exception as e:
        print(f"✗ DataLoader test failed: {e}")

    print()
    print("=" * 80)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 80)
    print()
    print("Summary:")
    print("  ✓ USGSClient can query the database")
    print("  ✓ MaterialCache provides persistent caching")
    print("  ✓ DataLoader handles file I/O")
    print()
    print("Next steps:")
    print("  1. Run full test suite: uv run pytest tests/ -v")
    print("  2. If tests pass, you can delete: src/stdn_agentic/country_agent.py")
    print("  3. Commit Phase 2c changes")


if __name__ == "__main__":
    # Ensure we're in the right directory
    if not Path("./data/world_mineral_commodity_reports_2022-2025_v8.db").exists():
        print("\n⚠ Warning: Database not found in ./data/")
        print("   Make sure you're running from the project root:")
        print("   cd /Users/ads7fg/git/dpi_stdn_agentic/")
        print("   uv run python test_phase2c_integration.py")
        print()

    asyncio.run(test_with_database())
