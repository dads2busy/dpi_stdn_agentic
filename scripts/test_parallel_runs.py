#!/usr/bin/env python3
"""
Test script for parallel_runs.py dynamic file creation functionality.

Tests:
1. Database copies are created correctly
2. Config files are generated with correct database paths
3. Cleanup removes temp files properly
"""

import json
import sys
import tempfile
from pathlib import Path

# Add the scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from parallel_runs import cleanup_temp_files, create_config_files, create_database_copies


def test_dynamic_file_creation():
    """Test that database copies and config files are created correctly."""
    print("=" * 60)
    print("Testing parallel_runs.py dynamic file creation")
    print("=" * 60)

    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Setup: Create a mock database file
        data_dir = tmpdir / "data"
        data_dir.mkdir()
        mock_db = data_dir / "test_database.db"
        mock_db.write_text("MOCK DATABASE CONTENT FOR TESTING")
        print(f"\n[Setup] Created mock database: {mock_db}")
        print(f"  Size: {mock_db.stat().st_size} bytes")

        # Setup: Create a mock base config
        base_config = {
            "import_tech_list": "./data/tech_list.csv",
            "model": "anthropic:claude-sonnet-4-20250514",
            "output_dir": "./output",
            "output_csv_filename": "stdns_output",
            "usgs_database": "./data/test_database.db",
            "top_n_countries": 5,
        }
        base_config_path = tmpdir / "config.json"
        with open(base_config_path, "w") as f:
            json.dump(base_config, f, indent=2)
        print(f"[Setup] Created base config: {base_config_path}")

        # Test 1: Create database copies
        print("\n" + "-" * 40)
        print("TEST 1: Database Copy Creation")
        print("-" * 40)

        num_runs = 3
        db_copies = create_database_copies(mock_db, num_runs, tmpdir)

        assert len(db_copies) == num_runs, f"Expected {num_runs} copies, got {len(db_copies)}"

        for i, db_copy in enumerate(db_copies, start=1):
            assert db_copy.exists(), f"Database copy {i} does not exist: {db_copy}"
            assert db_copy.name == f"test_database_run{i}.db", f"Wrong filename: {db_copy.name}"
            assert db_copy.stat().st_size == mock_db.stat().st_size, f"Size mismatch for {db_copy}"
            print(f"  PASS: {db_copy.name} exists with correct size")

        print("TEST 1: PASSED")

        # Test 2: Create config files
        print("\n" + "-" * 40)
        print("TEST 2: Config File Generation")
        print("-" * 40)

        config_type = "v1v1v1"
        config_files = create_config_files(base_config_path, config_type, db_copies, tmpdir)

        assert len(config_files) == num_runs, (
            f"Expected {num_runs} configs, got {len(config_files)}"
        )

        for i, config_path in enumerate(config_files, start=1):
            assert config_path.exists(), f"Config {i} does not exist: {config_path}"
            assert config_path.name == f"config_{config_type}_run{i}.json", (
                f"Wrong filename: {config_path.name}"
            )

            with open(config_path) as f:
                config = json.load(f)

            expected_db_path = f"./data/test_database_run{i}.db"
            assert config["usgs_database"] == expected_db_path, (
                f"Wrong database path in config {i}: {config['usgs_database']} != {expected_db_path}"
            )

            # Verify other config values are preserved
            assert config["model"] == base_config["model"], "Model not preserved"
            assert config["output_dir"] == base_config["output_dir"], "output_dir not preserved"
            assert config["output_csv_filename"] == base_config["output_csv_filename"], (
                "output_csv_filename not preserved"
            )

            print(
                f"  PASS: {config_path.name} has correct database path: {config['usgs_database']}"
            )

        print("TEST 2: PASSED")

        # Test 3: Cleanup
        print("\n" + "-" * 40)
        print("TEST 3: Cleanup")
        print("-" * 40)

        # Verify files exist before cleanup
        for db_copy in db_copies:
            assert db_copy.exists(), f"DB copy should exist before cleanup: {db_copy}"
        for config_path in config_files:
            assert config_path.exists(), f"Config should exist before cleanup: {config_path}"

        cleanup_temp_files(db_copies, config_files)

        # Verify files are removed after cleanup
        for db_copy in db_copies:
            assert not db_copy.exists(), f"DB copy should be removed after cleanup: {db_copy}"
            print(f"  PASS: {db_copy.name} removed")
        for config_path in config_files:
            assert not config_path.exists(), (
                f"Config should be removed after cleanup: {config_path}"
            )
            print(f"  PASS: {config_path.name} removed")

        # Verify original files are NOT removed
        assert mock_db.exists(), "Original database should NOT be removed"
        assert base_config_path.exists(), "Base config should NOT be removed"
        print("  PASS: Original database preserved")
        print("  PASS: Base config preserved")

        print("TEST 3: PASSED")

        # Test 4: Test with d3d3v3 config type
        print("\n" + "-" * 40)
        print("TEST 4: d3d3v3 Config Type")
        print("-" * 40)

        db_copies_2 = create_database_copies(mock_db, 2, tmpdir)
        config_files_2 = create_config_files(base_config_path, "d3d3v3", db_copies_2, tmpdir)

        for i, config_path in enumerate(config_files_2, start=1):
            assert config_path.name == f"config_d3d3v3_run{i}.json", (
                f"Wrong filename: {config_path.name}"
            )
            print(f"  PASS: {config_path.name} created correctly")

        cleanup_temp_files(db_copies_2, config_files_2)
        print("TEST 4: PASSED")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    return True


def test_with_real_files():
    """Test using actual project files (read-only verification)."""
    print("\n" + "=" * 60)
    print("Testing with real project files (read-only)")
    print("=" * 60)

    project_dir = Path(__file__).parent.parent
    base_db = project_dir / "data" / "world_mineral_commodity_reports_2022-2025_v8.db"
    base_config = project_dir / "config.json"

    if not base_db.exists():
        print(f"SKIP: Base database not found: {base_db}")
        return True

    if not base_config.exists():
        print(f"SKIP: Base config not found: {base_config}")
        return True

    print(f"Found base database: {base_db}")
    print(f"  Size: {base_db.stat().st_size:,} bytes")

    print(f"Found base config: {base_config}")
    with open(base_config) as f:
        config = json.load(f)
    print(f"  Database path in config: {config.get('usgs_database', 'NOT SET')}")

    # Verify the database path in config matches expected pattern
    db_path_in_config = config.get("usgs_database", "")
    assert "world_mineral_commodity_reports" in db_path_in_config, (
        f"Expected database path pattern not found in config: {db_path_in_config}"
    )

    print("\nREAL FILE VERIFICATION: PASSED")
    return True


if __name__ == "__main__":
    try:
        test_dynamic_file_creation()
        test_with_real_files()
        print("\n" + "=" * 60)
        print("SUCCESS: All tests passed!")
        print("=" * 60)
        sys.exit(0)
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
