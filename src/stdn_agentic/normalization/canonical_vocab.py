"""
Canonical Vocabulary for Component Normalization.

This module provides a persistent vocabulary that maps raw component names
to canonical forms. It grows over time as new components are encountered,
reducing LLM calls on subsequent runs.

The vocab is stored as a JSON file with structure:
{
    "version": "1.0",
    "mappings": {
        "raw_name_lowercase": "Canonical Name",
        ...
    },
    "metadata": {
        "created_at": "2026-01-28T12:00:00",
        "updated_at": "2026-01-28T12:00:00",
        "total_mappings": 42
    }
}
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CanonicalVocab:
    """
    Persistent vocabulary for component name canonicalization.

    Manages a JSON file that maps raw component names to their canonical forms.
    Unknown names are returned as needing LLM normalization, and new mappings
    can be added after LLM processing.

    Attributes:
        vocab_path: Path to the JSON vocabulary file
        mappings: Dict mapping lowercase raw names to canonical names

    Example:
        >>> vocab = CanonicalVocab("data/component_vocab.json")
        >>>
        >>> # Check which names need LLM normalization
        >>> raw_names = ["Battery", "Li-ion Battery", "LCD Panel", "NewComponent"]
        >>> cached, unknown = vocab.lookup_batch(raw_names)
        >>> # cached = {"battery": "Lithium-ion Battery", "li-ion battery": "Lithium-ion Battery", ...}
        >>> # unknown = ["NewComponent"]
        >>>
        >>> # After LLM normalizes unknown names, add them
        >>> vocab.add_mappings({"newcomponent": "New Component Type"})
        >>> vocab.save()
    """

    VERSION = "1.0"

    def __init__(self, vocab_path: str = "data/component_canonical_vocab.json"):
        """
        Initialize canonical vocabulary.

        Args:
            vocab_path: Path to JSON vocabulary file. Created if doesn't exist.
        """
        self.vocab_path = Path(vocab_path)
        self.mappings: Dict[str, str] = {}
        self.metadata: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Load vocabulary from JSON file, or initialize empty if not exists."""
        if self.vocab_path.exists():
            try:
                with open(self.vocab_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.mappings = data.get("mappings", {})
                self.metadata = data.get("metadata", {})
                logger.info(
                    f"Loaded canonical vocab: {len(self.mappings)} mappings from {self.vocab_path}"
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error loading vocab file, starting fresh: {e}")
                self._init_empty()
        else:
            logger.info(f"No vocab file found at {self.vocab_path}, starting fresh")
            self._init_empty()

    def _init_empty(self) -> None:
        """Initialize empty vocabulary."""
        self.mappings = {}
        self.metadata = {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "total_mappings": 0,
        }

    def save(self) -> None:
        """Save vocabulary to JSON file."""
        self.metadata["updated_at"] = datetime.now().isoformat()
        self.metadata["total_mappings"] = len(self.mappings)

        # Ensure directory exists
        self.vocab_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self.VERSION,
            "mappings": self.mappings,
            "metadata": self.metadata,
        }

        with open(self.vocab_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved canonical vocab: {len(self.mappings)} mappings to {self.vocab_path}")

    def _normalize_key(self, name: str) -> str:
        """Normalize a name for use as lookup key."""
        return name.lower().strip()

    def lookup(self, raw_name: str) -> Optional[str]:
        """
        Look up canonical name for a raw component name.

        Args:
            raw_name: Raw component name from output

        Returns:
            Canonical name if found, None if unknown
        """
        key = self._normalize_key(raw_name)
        return self.mappings.get(key)

    def lookup_batch(self, raw_names: List[str]) -> Tuple[Dict[str, str], List[str]]:
        """
        Look up multiple names, separating cached from unknown.

        Args:
            raw_names: List of raw component names

        Returns:
            Tuple of (cached_mappings, unknown_names)
            - cached_mappings: Dict of raw_name -> canonical_name for known names
            - unknown_names: List of names not in vocab (need LLM)
        """
        cached: Dict[str, str] = {}
        unknown: List[str] = []

        for name in raw_names:
            canonical = self.lookup(name)
            if canonical is not None:
                cached[name] = canonical
            else:
                unknown.append(name)

        return cached, unknown

    def add_mapping(self, raw_name: str, canonical_name: str) -> None:
        """
        Add a single mapping to the vocabulary.

        Args:
            raw_name: Raw component name
            canonical_name: Canonical form to map to
        """
        key = self._normalize_key(raw_name)
        self.mappings[key] = canonical_name

    def add_mappings(self, mappings: Dict[str, str]) -> None:
        """
        Add multiple mappings to the vocabulary.

        Args:
            mappings: Dict of raw_name -> canonical_name
        """
        for raw_name, canonical_name in mappings.items():
            self.add_mapping(raw_name, canonical_name)

    def get_stats(self) -> Dict:
        """Get vocabulary statistics."""
        # Count unique canonical names
        unique_canonicals = set(self.mappings.values())

        return {
            "total_mappings": len(self.mappings),
            "unique_canonical_names": len(unique_canonicals),
            "vocab_path": str(self.vocab_path),
            "created_at": self.metadata.get("created_at"),
            "updated_at": self.metadata.get("updated_at"),
        }

    def get_canonical_names(self) -> List[str]:
        """Get list of all unique canonical names."""
        return sorted(set(self.mappings.values()))

    def get_mappings_for_canonical(self, canonical_name: str) -> List[str]:
        """Get all raw names that map to a given canonical name."""
        return [raw for raw, canon in self.mappings.items() if canon == canonical_name]


__all__ = ["CanonicalVocab"]
