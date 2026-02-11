"""
Importable wrapper module for the parallel runs launcher.

This exists so we can expose a clean console script entrypoint:

    uv run stdn-parallel --config-type d5v1v1 --num-runs 5 --base-config config.json

Instead of invoking the launcher as:

    uv run python scripts/parallel_runs.py ...

Implementation notes:
- We keep the existing implementation in `scripts/parallel_runs.py` as the source of truth.
- This wrapper imports and calls its `main()`.

Caveat:
- `scripts` is a namespace that can conflict with other modules named "scripts" on sys.path.
  We therefore import the file by path to avoid ambiguity.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import NoReturn


def _load_legacy_parallel_runs_module() -> ModuleType:
    """
    Load the repo-root `scripts/parallel_runs.py` by absolute path.

    Returns the loaded module object.
    """
    # This file lives at: <repo>/src/stdn_agentic/scripts/parallel_runs.py
    # Repo root is three parents up: scripts/ (this file) -> stdn_agentic/ -> src/ -> <repo>/
    repo_root = Path(__file__).resolve().parents[3]
    legacy_path = repo_root / "scripts" / "parallel_runs.py"

    if not legacy_path.exists():
        raise FileNotFoundError(
            f"Cannot find legacy parallel runs script at: {legacy_path}. "
            "Expected it at <repo>/scripts/parallel_runs.py"
        )

    module_name = "_stdn_agentic_legacy_parallel_runs"
    spec = importlib.util.spec_from_file_location(module_name, legacy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to create import spec for: {legacy_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> NoReturn:
    """
    Console entrypoint for `stdn-parallel`.

    Delegates to `scripts/parallel_runs.py:main`.
    """
    legacy = _load_legacy_parallel_runs_module()

    legacy_main = getattr(legacy, "main", None)
    if legacy_main is None or not callable(legacy_main):
        raise AttributeError(
            "Legacy parallel runs module does not define a callable `main()` function."
        )

    # The legacy script uses argparse and expects sys.argv to already contain the CLI args.
    # We simply call it; it may call sys.exit itself, but we handle return codes too.
    rc = legacy_main()
    raise SystemExit(rc if isinstance(rc, int) else 0)
