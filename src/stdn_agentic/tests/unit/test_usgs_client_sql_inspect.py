"""
Inspect the exact SQL queries constructed by USGSClient.

This uses a capturing stub for the DuckDB connection so we see the SQL
without needing a real database file. Output is printed directly so
`pytest -s` will display it.
"""

from typing import List

import pandas as pd
import pytest

from stdn_agentic.data.usgs_client import USGSClient


class _DummyResult:
    """Minimal stub object returned from connection.sql()."""

    def __init__(self) -> None:
        self._df = pd.DataFrame()

    def df(self) -> pd.DataFrame:
        return self._df


class CapturingConnection:
    """Test double that records all SQL queries passed to sql()."""

    def __init__(self) -> None:
        self.queries: List[str] = []

    def sql(self, query: str) -> _DummyResult:
        self.queries.append(query)
        return _DummyResult()


def _make_client_with_capturing_conn() -> tuple[USGSClient, CapturingConnection]:
    """
    Helper to construct a USGSClient whose connection is a capturing stub.

    The database_path value is irrelevant here because we immediately
    override `client.connection`.
    """
    client = USGSClient(database_path=":memory:", top_n=5)
    capturing_conn = CapturingConnection()
    client.connection = capturing_conn  # type: ignore[assignment]
    return client, capturing_conn


@pytest.mark.parametrize(
    "material, src_year, meas_year",
    [
        ("Gold", 2025, 2024),
        ("Tin", 2024, 2023),
    ],
)
def test_print_top_countries_sql(material: str, src_year: int, meas_year: int) -> None:
    """Print the SQL used for top-countries queries for manual inspection."""
    client, conn = _make_client_with_capturing_conn()

    client.query_top_countries(material, src_year, meas_year)

    assert conn.queries, "Expected at least one SQL query to be recorded."
    sql = conn.queries[0]

    print("\n=== query_top_countries SQL ===")
    print(sql)


def test_print_world_totals_sql() -> None:
    """Print the SQL used for world-totals queries."""
    client, conn = _make_client_with_capturing_conn()

    client.query_world_totals("Aluminum", src_year=2023, meas_year=2024)

    assert conn.queries, "Expected at least one SQL query to be recorded."
    sql = conn.queries[0]

    print("\n=== query_world_totals SQL ===")
    print(sql)


def test_print_country_details_sql() -> None:
    """Print the SQL used for per-country detail queries."""
    client, conn = _make_client_with_capturing_conn()

    client.query_country_details(
        material="Cobalt",
        country="Chile",
        src_year=2024,
        meas_year=2023,
    )

    assert conn.queries, "Expected at least one SQL query to be recorded."
    sql = conn.queries[0]

    print("\n=== query_country_details SQL ===")
    print(sql)
