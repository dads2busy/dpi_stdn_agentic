"""
Debug script for DuckDB USGS database connection issues

This script tests:
1. Database file exists and is accessible
2. DuckDB can connect to the file
3. Tables are visible after connection
4. Sample queries work correctly
5. Connection lifecycle and persistence

Run with: uv run python debug_duckdb.py
"""

import os
import sys
from pathlib import Path

import duckdb


def test_duckdb_connection():
    """Comprehensive DuckDB connection debugging"""

    print("=" * 80)
    print("DuckDB Connection Debugging")
    print("=" * 80)
    print()

    # Test 1: File existence
    print("TEST 1: Database File Existence")
    print("-" * 80)
    db_path = "./data/world_mineral_commodity_reports_2022-2025_v8.db"
    abs_path = Path(db_path).resolve()

    print(f"Database path (relative): {db_path}")
    print(f"Database path (absolute): {abs_path}")
    print(f"File exists: {abs_path.exists()}")

    if abs_path.exists():
        file_size = abs_path.stat().st_size
        print(f"File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    else:
        print("❌ ERROR: Database file does not exist!")
        print(f"Current directory: {Path.cwd()}")
        print(f"Expected location: {abs_path}")
        return False

    print("✓ Database file exists\n")

    # Test 2: DuckDB connection
    print("TEST 2: DuckDB Connection")
    print("-" * 80)

    try:
        # Try different connection methods
        print("Method 1: Direct path connection")
        conn1 = duckdb.connect(str(abs_path), read_only=True)
        print(f"✓ Connected successfully (read-only): {conn1}")

        # Check what tables are visible
        tables1 = conn1.execute("SHOW TABLES").fetchall()
        print(f"Tables visible: {tables1}")
        conn1.close()

        print("\nMethod 2: Read-write connection")
        conn2 = duckdb.connect(str(abs_path), read_only=False)
        print(f"✓ Connected successfully (read-write): {conn2}")

        tables2 = conn2.execute("SHOW TABLES").fetchall()
        print(f"Tables visible: {tables2}")

        # Use this connection for remaining tests
        conn = conn2

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("✓ Connection successful\n")

    # Test 3: Table inspection
    print("TEST 3: Table Inspection")
    print("-" * 80)

    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        print(f"Found {len(tables)} table(s):")
        for table in tables:
            print(f"  - {table[0]}")

        if not tables:
            print("❌ ERROR: No tables found in database!")

            # Try alternative queries
            print("\nTrying alternative queries...")
            try:
                info_tables = conn.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'main'
                """).fetchall()
                print(f"information_schema.tables: {info_tables}")
            except Exception as e:
                print(f"information_schema query failed: {e}")

            return False

        # Inspect first table schema
        table_name = tables[0][0]
        print(f"\nSchema for '{table_name}':")
        schema = conn.execute(f"DESCRIBE {table_name}").fetchall()
        for col in schema:
            print(f"  {col[0]:<30} {col[1]:<20} {'NULL' if col[2] else 'NOT NULL'}")

        # Count rows
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"\nTotal rows: {count:,}")

    except Exception as e:
        print(f"❌ Table inspection failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("✓ Table inspection successful\n")

    # Test 4: Sample queries
    print("TEST 4: Sample Queries")
    print("-" * 80)

    try:
        # Query 1: Check for specific materials
        test_materials = ["Aluminum", "Copper", "Lithium", "Cobalt"]

        for material in test_materials:
            query = f"""
            SELECT DISTINCT commodity, country
            FROM world_mineral_commodity_report
            WHERE UPPER(commodity) LIKE '%{material.upper()}%'
            LIMIT 3
            """
            results = conn.execute(query).fetchall()
            print(f"  {material}: {len(results)} records found")
            if results:
                print(f"    Sample: {results[0]}")

        # Query 2: Check year columns
        print("\nYear columns check:")
        year_query = """
        SELECT DISTINCT meas_yr, src_yr
        FROM world_mineral_commodity_report
        ORDER BY meas_yr DESC, src_yr DESC
        LIMIT 5
        """
        years = conn.execute(year_query).fetchall()
        print(f"  Available year combinations: {years}")

        # Query 3: Full material query (matching your actual use case)
        print("\nFull material query test:")
        full_query = """
        SELECT meas_type, meas_unit, value, country
        FROM world_mineral_commodity_report
        WHERE meas_yr = 2024
            AND src_yr = 2023
            AND UPPER(commodity) = 'ALUMINUM'
            AND value_type = 'Number'
            AND UPPER(meas_type) IN ('PRODUCTION', 'RESERVES', 'RESERVE BASE')
        LIMIT 5
        """
        results = conn.execute(full_query).fetchall()
        print(f"  Aluminum query returned {len(results)} rows")
        for row in results:
            print(f"    {row}")

    except Exception as e:
        print(f"❌ Query failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("✓ Sample queries successful\n")

    # Test 5: Connection persistence
    print("TEST 5: Connection Persistence")
    print("-" * 80)

    try:
        # Simulate multiple queries like your code does
        for i in range(3):
            result = conn.execute("SELECT COUNT(*) FROM world_mineral_commodity_report").fetchone()
            print(f"  Query {i + 1}: {result[0]:,} rows")

        # Check if connection is still alive
        conn.execute("SELECT 1").fetchone()
        print("✓ Connection persists across multiple queries")

    except Exception as e:
        print(f"❌ Connection persistence failed: {e}")
        return False

    print()

    # Cleanup
    conn.close()

    print("=" * 80)
    print("✅ All tests passed!")
    print("=" * 80)
    print()

    return True


def test_usgs_client():
    """Test the actual USGSMineralClient class"""

    print("=" * 80)
    print("Testing Actual USGSMineralClient")
    print("=" * 80)
    print()

    try:
        from stdn_agentic.data.usgs_client import USGSMineralClient

        db_path = "./data/world_mineral_commodity_reports_2022-2025_v8.db"
        client = USGSMineralClient(database_path=db_path)

        print(f"✓ USGSMineralClient initialized")
        print(f"  Database: {client.db_path}")
        print(f"  Connection: {client.conn}")

        # Test table visibility through client
        tables = client.conn.execute("SHOW TABLES").fetchall()
        print(f"  Tables visible through client: {tables}")

        # Test a sample query
        print("\nTesting sample query through client:")
        results = client.query_material_production("Aluminum", 2023, 2024)
        print(f"  Query returned: {len(results)} results")
        if results:
            print(f"  Sample result: {results[0]}")

    except ImportError as e:
        print(f"⚠️  Could not import USGSMineralClient: {e}")
        print("   This is expected if running outside the package directory")
    except Exception as e:
        print(f"❌ USGSMineralClient test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print(f"\nCurrent directory: {Path.cwd()}\n")

    # Run basic connection tests
    if test_duckdb_connection():
        # If basic tests pass, test the actual client
        print()
        test_usgs_client()
    else:
        print("\n❌ Basic connection tests failed!")
        sys.exit(1)
