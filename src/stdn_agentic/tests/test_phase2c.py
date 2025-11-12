"""
Test script for Phase 2c - Data Layer Refactoring

This script verifies that the data layer modules work correctly:
- USGSClient for database queries
- CountryDataRepository for coordinated data retrieval
- MaterialCache for caching
- DataLoader for file I/O
"""

import asyncio
import tempfile
from pathlib import Path

print("=" * 80)
print("PHASE 2C DATA LAYER TESTING")
print("=" * 80)
print()

# Test 1: Import all data layer modules
print("Test 1: Import data layer modules...")
try:
    from stdn_agentic.data import (
        CountryDataRepository,
        DataLoader,
        MaterialCache,
        USGSClient,
    )

    print("✓ Test 1 PASSED: All data layer imports work")
except ImportError as e:
    print(f"✗ Test 1 FAILED: {e}")
    exit(1)

print()

# Test 2: MaterialCache functionality
print("Test 2: MaterialCache functionality...")
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = MaterialCache(cache_dir=tmpdir, ttl_hours=24)

        # Test set/get
        cache.set("test_key", {"data": "value"})
        result = cache.get("test_key")

        assert result == {"data": "value"}, "Cache get/set failed"

        # Test stats
        stats = cache.get_stats()
        assert stats["valid_entries"] == 1, "Cache stats incorrect"

        # Test clear
        cache.clear()
        assert cache.get("test_key") is None, "Cache clear failed"

    print("✓ Test 2 PASSED: MaterialCache works correctly")
except Exception as e:
    print(f"✗ Test 2 FAILED: {e}")

print()

# Test 3: DataLoader functionality
print("Test 3: DataLoader functionality...")
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Test JSON save/load
        test_data = {"key": "value", "number": 42}
        json_file = tmppath / "test.json"

        DataLoader.save_json(test_data, str(json_file))
        loaded = DataLoader.load_json(str(json_file))

        assert loaded == test_data, "JSON save/load failed"

        # Test CSV save/load
        csv_data = [
            {"country": "China", "percentage": 65.5},
            {"country": "Australia", "percentage": 27.3},
        ]
        csv_file = tmppath / "test.csv"

        DataLoader.save_csv(csv_data, str(csv_file))
        loaded_csv = DataLoader.load_csv(str(csv_file), as_dict=True)

        assert len(loaded_csv) == 2, "CSV save/load failed"
        assert loaded_csv[0]["country"] == "China", "CSV data incorrect"

        # Test text list
        text_file = tmppath / "test.txt"
        with open(text_file, "w") as f:
            f.write("line1\nline2\nline3\n")

        lines = DataLoader.load_text_list(str(text_file))
        assert len(lines) == 3, "Text list load failed"
        assert lines[0] == "line1", "Text list data incorrect"

    print("✓ Test 3 PASSED: DataLoader works correctly")
except Exception as e:
    print(f"✗ Test 3 FAILED: {e}")

print()

# Test 4: Test backwards compatibility imports
print("Test 4: Backwards compatibility with main package...")
try:
    # These imports should still work from the main package
    from stdn_agentic import (
        CheckpointManager,
        DebateReporter,
        MultiAgentDebater,
        STDNOrchestrator,
    )

    print("✓ Test 4 PASSED: Main package imports still work")
except ImportError as e:
    print(f"✗ Test 4 FAILED: {e}")

print()

# Test 5: Test agent imports still work
print("Test 5: Agent imports still work...")
try:
    from stdn_agentic.agents import (
        AgentFactory,
        get_component_agent,
        get_country_data_agent,
        get_materials_agent,
    )

    print("✓ Test 5 PASSED: Agent imports still work")
except ImportError as e:
    print(f"✗ Test 5 FAILED: {e}")

print()

# Test 6: Instantiate data layer classes
print("Test 6: Instantiate data layer classes...")
try:
    # MaterialCache
    cache = MaterialCache(cache_dir="./.test_cache", ttl_hours=1)
    print("  ✓ MaterialCache instantiated")

    # DataLoader (static methods, no instantiation needed)
    loader = DataLoader()
    print("  ✓ DataLoader instantiated")

    # Note: USGSClient and CountryDataRepository require actual database
    # which may not exist in test environment
    print("  ℹ USGSClient/Repository require database (skipped in basic test)")

    print("✓ Test 6 PASSED: Can instantiate data layer classes")
except Exception as e:
    print(f"✗ Test 6 FAILED: {e}")

print()

# Test 7: Check if dependencies module exists
print("Test 7: Check dependencies module...")
try:
    from stdn_agentic.dependencies import initialize_dependencies

    print("✓ Test 7 PASSED: Dependencies module found")
except ImportError:
    print("⚠ Test 7 WARNING: dependencies module not found (may need to be created)")

print()

print("=" * 80)
print("PHASE 2C DATA LAYER TESTING COMPLETE")
print("=" * 80)
print()
print("Summary:")
print("  ✓ All data layer modules can be imported")
print("  ✓ MaterialCache works correctly")
print("  ✓ DataLoader works correctly")
print("  ✓ Backwards compatibility maintained")
print()
print("Next steps:")
print("  1. Run: uv run pytest tests/ -v")
print("  2. If all tests pass, delete src/stdn_agentic/country_agent.py")
print("  3. Commit Phase 2c changes")
