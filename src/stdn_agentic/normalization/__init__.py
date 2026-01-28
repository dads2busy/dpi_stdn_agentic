"""
STDN Normalization Module

This module provides semantic normalization capabilities for STDN run outputs.
It performs cross-run semantic reconciliation without deduplication, preserving
all individual run records while normalizing names and attributes.

Key Components:
- models: Pydantic data models for normalized components and semantic groups
- run_loader: Load and parse existing run files (CSV/JSON)
- embeddings: Generate semantic embeddings for component comparison
- clustering: Cluster semantically similar components
- canonical_selector: Use LLM to determine canonical representations
- manager: Orchestrate the full normalization workflow
"""

from stdn_agentic.normalization.canonical_vocab import CanonicalVocab
from stdn_agentic.normalization.models import (
    ConsolidatedNormalizedSTDN,
    NormalizedComponent,
    NormalizedDependency,
    SemanticGroup,
)

__all__ = [
    "CanonicalVocab",
    "NormalizedComponent",
    "NormalizedDependency",
    "SemanticGroup",
    "ConsolidatedNormalizedSTDN",
]
