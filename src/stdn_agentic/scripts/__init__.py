"""
Scripts subpackage.

This package exists primarily to host importable script entrypoints that can be
exposed via console scripts in `pyproject.toml`, e.g.:

    [project.scripts]
    stdn-parallel = "stdn_agentic.scripts.parallel_runs:main"

Keeping these modules importable under `stdn_agentic.*` avoids relying on
repo-root `scripts/` for entrypoint discovery.
"""

from __future__ import annotations

__all__ = [
    "parallel_runs",
]
