"""Process consumables extraction agent and judge for Stage 2b.

Extracts materials consumed during manufacturing but not physically
present in the final product (e.g., process gases, etchants, solvents).
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class ProcessConsumable(BaseModel):
    """A single process consumable with provenance tracking."""

    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    extraction_provenance: str = Field(default="extractor")  # "extractor" or "judge_addition"


class ProcessConsumablesList(BaseModel):
    """Extraction agent output: list of proposed process consumables."""

    materials: List[ProcessConsumable]


class JudgeAction(str, Enum):
    KEEP = "keep"
    REMOVE = "remove"
    ADJUST = "adjust"
    ADD = "add"


class JudgeVerdict(BaseModel):
    """A single judge decision on a process consumable."""

    name: str
    action: JudgeAction
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str


class JudgeOutput(BaseModel):
    """Judge agent output: verdicts on each proposed item plus additions."""

    verdicts: List[JudgeVerdict]

    @property
    def kept_and_added(self) -> List[JudgeVerdict]:
        """Return only items that survive the judge (keep, adjust, add)."""
        return [v for v in self.verdicts if v.action != JudgeAction.REMOVE]


__all__ = [
    "ProcessConsumable",
    "ProcessConsumablesList",
    "JudgeAction",
    "JudgeVerdict",
    "JudgeOutput",
]
