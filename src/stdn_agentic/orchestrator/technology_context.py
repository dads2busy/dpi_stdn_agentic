"""Per-technology isolated state for concurrent processing."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic_ai import RunUsage

from ..data.repository import CountryDataRepository
from .country_data_enricher import CountryDataEnricher


@dataclass
class TechnologyContext:
    """Holds per-technology mutable state to avoid shared-state races.

    Each concurrent technology task gets its own context with:
    - country_repo: own DuckDB connection and in-memory cache
    - country_enricher: own enricher wrapping the per-tech repo
    - usage: own token/request counters
    - transcript_path: own transcript file path
    """
    country_repo: CountryDataRepository
    country_enricher: CountryDataEnricher
    usage: RunUsage = field(default_factory=RunUsage)
    transcript_path: Optional[Path] = None
