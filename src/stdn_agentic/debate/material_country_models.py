from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CountryProposal:
    """A country production proposal from an agent."""

    agent_id: str
    country: str
    meas_unit: str
    amount: float
    percentage: float
    rank: int  # Cardinal rank (1-10)
    round_num: int
    confidence: float = 0.8
    reasoning: str = ""
