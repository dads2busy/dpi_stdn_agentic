"""
Tests for inspecting SQL queries constructed by USGSClient.

These tests replace the real DuckDB connection with a capturing stub so that
we can inspect the exact SQL passed to `connection.sql(...)` without needing
a real database file.
"""

from typing import List

import pandas as pd

from stdn_agentic.data import USGSClient


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


def test_query_top_countries_builds_expected_sql(capsys: "pytest.CaptureFixture[str]") -> None:
    """Capture and print the SQL used for top-countries queries."""
    client, conn = _make_client_with_capturing_conn()

    material = "Lithium"
    src_year = 2025
    meas_year = 2024

    # Exercise: this will call connection.sql(query).df()
    client.query_top_countries(material, src_year, meas_year)

    assert conn.queries, "Expected at least one SQL query to be recorded."
    sql = conn.queries[0]

    # Basic sanity checks on the constructed query
    assert "FROM world_mineral_commodity_report" in sql
    assert f"meas_yr = {meas_year}" in sql
    assert f"src_yr = {src_year}" in sql
    assert "UPPER(commodity)" in sql
    assert material.upper() in sql

    # Print for manual inspection during debugging
    print("Top countries SQL:\n", sql)

    captured = capsys.readouterr()
    assert "Top countries SQL:" in captured.out


def test_query_world_totals_builds_expected_sql(capsys: "pytest.CaptureFixture[str]") -> None:
    """Capture and print the SQL used for world-totals queries."""
    client, conn = _make_client_with_capturing_conn()

    material = "Copper"
    src_year = 2023
    meas_year = 2022

    client.query_world_totals(material, src_year, meas_year)

    assert conn.queries, "Expected at least one SQL query to be recorded."
    sql = conn.queries[0]

    assert "FROM world_mineral_commodity_report" in sql
    assert f"meas_yr = {meas_year}" in sql
    assert f"src_yr = {src_year}" in sql
    assert "UPPER(commodity)" in sql
    assert "UPPER(country) = 'WORLD'" in sql
    assert material.upper() in sql

    print("World totals SQL:\n", sql)

    captured = capsys.readouterr()
    assert "World totals SQL:" in captured.out


def test_query_country_details_builds_expected_sql(capsys: "pytest.CaptureFixture[str]") -> None:
    """Capture and print the SQL used for per-country detail queries."""
    client, conn = _make_client_with_capturing_conn()

    material = "Cobalt"
    country = "Chile"
    src_year = 2024
    meas_year = 2023

    client.query_country_details(material, country, src_year, meas_year)

    assert conn.queries, "Expected at least one SQL query to be recorded."
    sql = conn.queries[0]

    assert "FROM world_mineral_commodity_report" in sql
    assert f"meas_yr = {meas_year}" in sql
    assert f"src_yr = {src_year}" in sql
    assert "UPPER(commodity)" in sql
    assert f"UPPER(country) = '{country.upper()}'" in sql
    assert material.upper() in sql

    print("Country details SQL:\n", sql)

    captured = capsys.readouterr()
    assert "Country details SQL:" in captured.out
