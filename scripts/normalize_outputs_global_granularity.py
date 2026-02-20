#!/usr/bin/env python3
"""
Global, LLM-driven component normalization with granularity enforcement.

Purpose
-------
This script performs component normalization across selected runs and enforces a
consistent "primary manufacturing component" granularity level. It is intended to
reduce cross-run instability driven by:
- synonyms / near-synonyms ("Sparger" vs "Sparger System")
- varying abstraction levels ("Drive Motor Assembly" vs "Agitation System")
- inconsistent phrasing across runs and configurations

It rewrites normalized outputs (CSV + JSON) under `output/normalized/` by applying
a canonical mapping to the `component` column (and to component strings inside JSON
where found), and writes normalization manifests for auditability.

Key design choices
------------------
1) Pattern-driven scope with optional config filtering:
   Operates over input CSVs matched by a pattern (e.g., output/raw/*.csv). You can
   optionally restrict processing to a set of debate configuration tags (e.g.,
   v1v1v1, d2v1v1, d3v1v1).

2) LLM-driven canonicalization with granularity enforcement:
   The LLM is instructed to consolidate naming variants and map part/subassembly-level
   items to the nearest "primary manufacturing component" when appropriate.

3) Two modes:
   - v1 (default): global normalization over component names only (no technology context)
   - v2 (`--group-by technology`): normalize per-technology (chunked) with technology context,
     write per-technology manifests, and still update a shared global mapping.

4) Persistent mapping:
   Writes/updates a global canonical mapping JSON so future runs can reuse mappings without
   repeated LLM calls.

Requirements
------------
- Python 3.9+
- pandas
- pydantic + pydantic_ai
- Provider key configured for your chosen model (e.g., OPENAI_API_KEY)

Example usage
-------------
  # v2: Normalize with technology grouping (recommended):
  python scripts/normalize_outputs_global_granularity.py \
    --pattern "output/raw/stdns_output_*.csv" \
    --only-config v1v1v1 --only-config d2v1v1 --only-config d3v1v1 --only-config d4v1v1 --only-config d5v1v1 \
    --group-by technology \
    --output-dir "output/normalized" \
    --global-vocab "data/component_canonical_vocab_global_primary.json" \
    --model "openai:gpt-5.2" \
    --chunk-size 120

  # Dry run:
  python scripts/normalize_outputs_global_granularity.py \
    --pattern "output/raw/stdns_output_*.csv" \
    --only-config v1v1v1 --only-config d3v1v1 \
    --group-by technology \
    --dry-run

Notes
-----
- This script is intentionally conservative about touching non-component fields.
  It normalizes the `component` column; all other columns are preserved as-is.
- JSON normalization is best-effort: it will attempt to normalize fields that look
  like component names, but the CSV is treated as the source of truth.

"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent

# Load environment variables from .env (if present) so provider keys like OPENAI_API_KEY are available.
load_dotenv()

# -----------------------------
# Constants / heuristics
# -----------------------------

_RX_STDNS_OUTPUT_CFG = re.compile(
    r"^stdns_output_(?P<config>[a-z0-9]+)_\d{8}_\d{6}\.csv$", re.IGNORECASE
)

NON_PRIMARY_SENTINEL_DEFAULT = "__NON_PRIMARY__"

# Basic string cleanup. We keep this conservative because LLM does the real work.
_WS_RE = re.compile(r"\s+")
_DASH_RE = re.compile(r"[\u2013\u2014]")  # en/em dash

# Keys that commonly contain a component name in JSON structures (best-effort).
JSON_COMPONENT_KEYS = {
    "component",
    "component_name",
    "name",  # sometimes nested objects use generic "name"
}

# -----------------------------
# Models
# -----------------------------


class ComponentMappingResponse(BaseModel):
    """
    LLM output schema: map each raw input name to a canonical primary-component name.

    Rules:
    - Values should be Title Case canonical component names (primary granularity).
    - Non-primary items should map to NON_PRIMARY_SENTINEL_DEFAULT (or a provided sentinel).
    """

    mappings: Dict[str, str] = Field(
        description="Mapping from raw component name to canonical primary-component name."
    )


@dataclass(frozen=True)
class Manifest:
    version: str
    timestamp_utc: str
    pattern: str
    model: str
    output_dir: str
    global_vocab_path: str
    chunk_size: int
    non_primary_sentinel: str
    input_csvs: List[str]
    input_jsons: List[str]
    output_csvs: List[str]
    output_jsons: List[str]
    unique_components_total: int
    cached_components_count: int
    unknown_components_count: int
    new_mappings_added: int
    dropped_non_primary_count: int
    notes: List[str]


# -----------------------------
# Utility functions
# -----------------------------


def _norm_key(s: str) -> str:
    """
    Normalize a raw string for dictionary keying.

    This is NOT the canonicalization itself. It is only used to improve cache hits.
    """
    t = (s or "").strip()
    t = _DASH_RE.sub("-", t)
    t = _WS_RE.sub(" ", t)
    t = t.strip(" \t\r\n.,;:()[]{}")
    return t.lower()


def load_global_vocab(path: Path) -> Dict[str, str]:
    """
    Load a global vocab mapping file.

    Format:
      {
        "version": "1.0",
        "mappings": { "<raw_key>": "<canonical>", ... }
      }

    Where <raw_key> should be normalized via _norm_key(raw_name).
    """
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    mappings = data.get("mappings", {})
    if not isinstance(mappings, dict):
        return {}
    # Ensure keys are normalized; keep values as-is.
    return {str(k): str(v) for k, v in mappings.items()}


def save_global_vocab(path: Path, mappings: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "mappings": dict(sorted(mappings.items(), key=lambda kv: kv[0])),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _config_from_stdns_output_csv_name(path: Path) -> str | None:
    """
    Extract config tag from a normalized/raw output filename:
      stdns_output_<config>_YYYYMMDD_HHMMSS.csv
    Returns None if the filename does not match the expected pattern.
    """
    m = _RX_STDNS_OUTPUT_CFG.match(path.name)
    if not m:
        return None
    return m.group("config").lower()


def safe_filename_slug(s: str, max_len: int = 120) -> str:
    """
    Produce a filesystem-safe slug from an arbitrary string.

    - Lowercase
    - Replace slashes and other path separators with underscores
    - Replace runs of non [a-z0-9._-] with underscores
    - Trim underscores and cap length
    """
    t = (s or "").strip().lower()
    # Replace any path separators (including "/" which can appear in tech names) early
    t = t.replace("/", "_").replace("\\", "_")
    # Collapse whitespace to single spaces for stability
    t = _WS_RE.sub(" ", t)
    # Replace disallowed characters
    t = re.sub(r"[^a-z0-9._-]+", "_", t)
    t = t.strip("._-")
    if not t:
        t = "unknown"
    if len(t) > max_len:
        t = t[:max_len].rstrip("._-")
        if not t:
            t = "unknown"
    return t


def iter_csv_paths(pattern: str) -> List[Path]:
    return [Path(p) for p in sorted(glob.glob(pattern)) if p.lower().endswith(".csv")]


def filter_csv_paths_by_config(csv_paths: Sequence[Path], only_configs: Set[str]) -> List[Path]:
    """
    Filter CSV paths to only those whose filename encodes a config tag present in only_configs.
    If only_configs is empty, returns csv_paths unchanged.
    """
    if not only_configs:
        return list(csv_paths)

    out: List[Path] = []
    for p in csv_paths:
        cfg = _config_from_stdns_output_csv_name(p)
        if cfg is None:
            continue
        if cfg in only_configs:
            out.append(p)
    return out


def iter_json_paths_from_csvs(csv_paths: Sequence[Path]) -> List[Path]:
    """
    Given CSV paths, look for sidecar JSONs with the same basename.
    """
    out: List[Path] = []
    for csv_path in csv_paths:
        json_path = csv_path.with_suffix(".json")
        if json_path.exists():
            out.append(json_path)
    return out


def extract_unique_components_from_csvs(csv_paths: Sequence[Path]) -> Set[str]:
    """
    Extract all unique component strings across CSV files.
    """
    comps: Set[str] = set()
    for p in csv_paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "component" not in df.columns:
            continue
        series = df["component"].dropna().astype(str)
        for v in series.unique().tolist():
            v = str(v).strip()
            if v:
                comps.add(v)
    return comps


def chunked(seq: Sequence[str], n: int) -> Iterable[List[str]]:
    buf: List[str] = []
    for x in seq:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


def dedupe_by_norm_key_preserve_representative(
    names: Sequence[str],
) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Deduplicate a list of raw names by `_norm_key(name)`.

    Returns:
      - representatives: a list of representative raw strings (one per norm-key), in stable order
      - norm_key_to_variants: mapping from norm-key -> list of raw variants observed
    """
    norm_key_to_variants: Dict[str, List[str]] = {}
    representatives: List[str] = []

    for raw in names:
        r = (raw or "").strip()
        if not r:
            continue
        k = _norm_key(r)
        if k not in norm_key_to_variants:
            norm_key_to_variants[k] = [r]
            representatives.append(r)
        else:
            norm_key_to_variants[k].append(r)

    return representatives, norm_key_to_variants


def extract_components_by_technology_from_csvs(csv_paths: Sequence[Path]) -> Dict[str, Set[str]]:
    """
    Extract per-technology unique component names from denormalized CSVs.

    Returns:
      technology -> set(raw component names)

    Notes:
    - The CSVs are at (technology, component, material, country) granularity, so we
      dedupe by (technology, component).
    - We treat the raw `technology` string as the grouping key; it is expected to be
      consistent within a given evaluation corpus.
    """
    tech_to_components: Dict[str, Set[str]] = {}
    for p in csv_paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "technology" not in df.columns or "component" not in df.columns:
            continue

        # Deduplicate early to avoid repeated component strings from material/country rows.
        sub = df[["technology", "component"]].dropna()
        if sub.empty:
            continue
        sub = sub.astype(str)
        sub["technology"] = sub["technology"].str.strip()
        sub["component"] = sub["component"].str.strip()
        sub = sub[(sub["technology"] != "") & (sub["component"] != "")]
        if sub.empty:
            continue
        sub = sub.drop_duplicates()

        for tech, comp in zip(sub["technology"].tolist(), sub["component"].tolist(), strict=False):
            tech_to_components.setdefault(tech, set()).add(comp)

    return tech_to_components


# -----------------------------
# LLM normalization (granularity-aware)
# -----------------------------


def build_granularity_prompt(
    names: Sequence[str],
    non_primary_sentinel: str,
    existing_canonicals: Sequence[str] | None = None,
    technology: str | None = None,
) -> str:
    """
    Build a strict prompt that enforces primary-component granularity.
    Optionally include technology context (v2 mode) to reduce ambiguity.
    """
    # Provide a small sample of existing canonical names to bias toward consistency.
    canonical_examples = ""
    if existing_canonicals:
        uniq = sorted(set(existing_canonicals))
        sample = uniq[: min(60, len(uniq))]
        canonical_examples = (
            "\nEXISTING CANONICAL PRIMARY COMPONENT NAMES (use exact spelling when applicable):\n"
            + ", ".join(sample)
            + ("\n..." if len(uniq) > len(sample) else "")
            + "\n"
        )

    numbered = "\n".join(f"{i + 1}. {n}" for i, n in enumerate(names))
    tech_line = f"TARGET TECHNOLOGY: {technology}\n\n" if technology else ""

    return f"""You are a component normalization system for supply chain dependency mapping.

{tech_line}Goal: Map each RAW component name to a CANONICAL *PRIMARY MANUFACTURING COMPONENT* name.
Primary components are major modules/subsystems that plausibly have distinct supply chains.
Your output will be used to compare runs across configurations, so consistency matters.

IMPORTANT: Enforce granularity.
- If a raw name is a *part* or *subassembly* of a primary component, map it to the nearest primary component.
  Examples:
  - "Drive Motor Assembly" -> "Agitation System"
  - "Impeller" -> "Agitation System"
  - "Sampling Port Assembly" -> "Sampling and Addition Ports"
  - "pH Sensor Probe" -> "Sensors and Instrumentation"
- If a raw name is overly generic ("Module", "Unit", "System" without function), choose a more specific canonical name if possible.
- If a raw name is NOT a primary manufacturing component (packaging, shipping items, optional accessories,
  downstream consumables, or obviously wrong-domain items), map it to the sentinel: {non_primary_sentinel}

Also:
- Consolidate synonyms/variants:
  - casing/punctuation differences
  - qualifiers like "assembly", "module", "system" when they don't change meaning

- HARD RULE: Preserve material-relevant primary-component distinctions.
  If a distinction implies meaningfully different bill-of-materials inputs, DO NOT collapse it.
  Examples (do not merge these into a generic "Battery" or "Display"):
  - "Lead-acid Battery" ≠ "Lithium-ion Battery" (different chemistry/material inputs)
  - "LFP Battery" ≠ "NMC Battery" when specified at the pack/module level
  - "OLED Display Module" ≠ "LCD Display Module"
  - "SiC Power Module" ≠ "Silicon Power Module" when specified as the primary power electronics module

- Merge when the difference is not material-relevant at the primary-component level.
  Examples (these SHOULD typically collapse):
  - "Sparger" / "Sparger System" / "Gas Dispersion System" → a single primary aeration component
  - "Sampling Port Assembly" / "Sterile Sampling Port" → a single primary sampling/ports component

- Use Title Case for canonical names.
- Output MUST be valid JSON with a single top-level key "mappings".

{canonical_examples}

RAW NAMES TO NORMALIZE:
{numbered}

Return JSON:
{{
  "mappings": {{
    "<raw_name_1>": "<canonical_primary_component_or_sentinel>",
    "<raw_name_2>": "<canonical_primary_component_or_sentinel>",
    ...
  }}
}}
"""


async def llm_normalize_chunk(
    names: Sequence[str],
    model: str,
    non_primary_sentinel: str,
    existing_canonicals: Sequence[str] | None,
    retries: int,
    technology: str | None = None,
) -> Dict[str, str]:
    """
    Normalize a chunk via LLM with a strict schema.
    Optionally pass technology context (v2 mode).
    """
    prompt = build_granularity_prompt(
        names=names,
        non_primary_sentinel=non_primary_sentinel,
        existing_canonicals=existing_canonicals,
        technology=technology,
    )

    agent = Agent(
        model=model,
        output_type=ComponentMappingResponse,
        system_prompt=(
            "You normalize component names to canonical primary manufacturing components. "
            "Always respond with valid JSON conforming to the schema."
        ),
        retries=retries,
        output_retries=retries,
    )

    result = await agent.run(prompt)
    if not result or not getattr(result, "output", None):
        return {}

    mapping = dict(result.output.mappings)
    # Ensure all inputs are present; if missing, map to itself (best-effort).
    out: Dict[str, str] = {}
    for raw in names:
        v = mapping.get(raw)
        if v is None or not str(v).strip():
            out[raw] = raw.strip()
        else:
            out[raw] = str(v).strip()
    return out


# -----------------------------
# Rewrite outputs
# -----------------------------


def apply_mapping_to_csv(
    csv_path: Path,
    out_dir: Path,
    mapping_by_norm_key: Dict[str, str],
    non_primary_sentinel: str,
    drop_non_primary: bool,
) -> Tuple[Path, int, int]:
    """
    Apply canonical mapping to a CSV's `component` column.

    Returns:
      (output_path, changed_count, dropped_rows_count)
    """
    df = pd.read_csv(csv_path)
    if "component" not in df.columns:
        # Just copy through.
        out_path = out_dir / csv_path.name
        out_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        return out_path, 0, 0

    original = df["component"].copy()

    def map_comp(x: object) -> object:
        if pd.isna(x):
            return x
        s = str(x).strip()
        if not s:
            return x
        k = _norm_key(s)
        return mapping_by_norm_key.get(k, s)

    df["component"] = df["component"].apply(map_comp)
    changed = int((original != df["component"]).sum())

    dropped = 0
    if drop_non_primary:
        before = len(df)
        df = df[df["component"] != non_primary_sentinel]
        dropped = before - len(df)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / csv_path.name
    df.to_csv(out_path, index=False)
    return out_path, changed, dropped


def apply_mapping_to_json(
    json_path: Path,
    out_dir: Path,
    mapping_by_norm_key: Dict[str, str],
    non_primary_sentinel: str,
    drop_non_primary: bool,
) -> Tuple[Path, int]:
    """
    Best-effort JSON rewrite. We normalize string values found under keys
    in JSON_COMPONENT_KEYS. If drop_non_primary is enabled, we attempt to
    remove objects where a component field maps to the sentinel.

    Returns:
      (output_path, changed_count)
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))

    changed = 0

    def normalize_value(v: object) -> object:
        nonlocal changed
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return v
            k = _norm_key(s)
            mapped = mapping_by_norm_key.get(k)
            if mapped and mapped != v:
                changed += 1
                return mapped
        return v

    def walk(obj: object) -> object:
        nonlocal changed
        if isinstance(obj, dict):
            # Optionally drop dicts that are explicitly a non-primary component record.
            if drop_non_primary:
                for key in JSON_COMPONENT_KEYS:
                    if key in obj and isinstance(obj[key], str):
                        mapped = normalize_value(obj[key])
                        if mapped == non_primary_sentinel:
                            return None
            new = {}
            for k, v in obj.items():
                if k in JSON_COMPONENT_KEYS:
                    new_v = normalize_value(v)
                else:
                    new_v = walk(v)
                if new_v is None:
                    continue
                new[k] = new_v
            return new
        if isinstance(obj, list):
            new_list = []
            for item in obj:
                new_item = walk(item)
                if new_item is None:
                    continue
                new_list.append(new_item)
            return new_list
        return obj

    out_data = walk(data)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / json_path.name
    out_path.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path, changed


# -----------------------------
# Main
# -----------------------------


async def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "LLM-driven component normalization across selected runs, enforcing "
            "primary-component granularity. Supports an optional v2 mode to group "
            "normalization by technology for added context."
        )
    )
    p.add_argument(
        "--pattern",
        required=True,
        help="Glob for input CSVs (recommended: output/raw/stdns_output_*.csv).",
    )
    p.add_argument(
        "--only-config",
        action="append",
        default=[],
        help=(
            "If provided, restrict processing to these configuration tags "
            "(e.g., v1v1v1, d3v1v1). May be repeated."
        ),
    )
    p.add_argument(
        "--group-by",
        choices=["none", "technology"],
        default="none",
        help=(
            "v2 mode: group normalization calls by technology to reduce ambiguity "
            "and improve granularity enforcement. Default: none (v1 global names-only)."
        ),
    )
    p.add_argument(
        "--manifest-dir",
        default="",
        help=(
            "Optional directory to write per-technology manifests when --group-by technology. "
            "If not provided, uses <output-dir>/manifests_by_technology/."
        ),
    )
    p.add_argument(
        "--output-dir",
        default="output/normalized",
        help="Directory to write normalized outputs (CSV + JSON).",
    )
    p.add_argument(
        "--global-vocab",
        default="data/component_canonical_vocab_global_primary.json",
        help="Path to global canonical mapping vocab JSON (raw_key -> canonical primary).",
    )
    p.add_argument(
        "--model",
        default="openai:gpt-4.1",
        help="LLM model identifier (provider-specific).",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=120,
        help="How many unique component names to send per LLM call.",
    )
    p.add_argument(
        "--non-primary-sentinel",
        default=NON_PRIMARY_SENTINEL_DEFAULT,
        help="Sentinel value for non-primary components.",
    )
    p.add_argument(
        "--drop-non-primary",
        action="store_true",
        help="If set, drop rows/objects mapped to the non-primary sentinel.",
    )
    p.add_argument(
        "--manifest-path",
        default="",
        help="Optional explicit path for the global normalization manifest JSON.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call the LLM or write outputs; just report what would happen.",
    )
    p.add_argument(
        "--max-unique-components",
        type=int,
        default=0,
        help="Optional cap on number of unique components (for testing). 0 = no cap.",
    )
    args = p.parse_args()

    csv_paths_all = iter_csv_paths(args.pattern)
    if not csv_paths_all:
        print(f"ERROR: No CSV files found for pattern: {args.pattern}", file=sys.stderr)
        raise SystemExit(1)

    only_configs = {c.strip().lower() for c in args.only_config if c and c.strip()}
    csv_paths = filter_csv_paths_by_config(csv_paths_all, only_configs)

    if not csv_paths:
        msg = (
            f"ERROR: No CSV files selected after config filtering. "
            f"pattern={args.pattern}, only_configs={sorted(only_configs)}"
        )
        print(msg, file=sys.stderr)
        raise SystemExit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Sidecar JSONs (optional)
    json_paths = iter_json_paths_from_csvs(csv_paths)

    global_vocab_path = Path(args.global_vocab)
    existing_vocab = load_global_vocab(global_vocab_path)

    retries_env = os.environ.get("STDN_AGENT_RETRIES")
    retries = 5
    if retries_env is not None:
        try:
            retries = int(retries_env)
        except ValueError:
            retries = 5

    # -------------------------
    # v2: group-by technology
    # -------------------------
    if args.group_by == "technology":
        tech_to_components = extract_components_by_technology_from_csvs(csv_paths)
        techs = sorted(tech_to_components.keys())
        if args.max_unique_components and args.max_unique_components > 0:
            # Apply cap by truncating technologies deterministically (keeps per-tech grouping intact).
            techs = techs[: min(len(techs), args.max_unique_components)]
            tech_to_components = {t: tech_to_components[t] for t in techs}

        manifest_dir = (
            Path(args.manifest_dir)
            if args.manifest_dir.strip()
            else (out_dir / "manifests_by_technology")
        )
        manifest_dir.mkdir(parents=True, exist_ok=True)

        # We keep a single global mapping keyed by normalized raw string.
        mapping_by_norm_key: Dict[str, str] = dict(existing_vocab)

        total_unique = 0
        total_cached = 0
        total_unknown_raw = 0
        total_unknown_reps = 0

        existing_canonicals: List[str] = list(existing_vocab.values())

        if args.dry_run:
            # Dry-run: compute counts per technology and overall.
            per_tech_reports: Dict[str, Dict[str, object]] = {}
            for tech in techs:
                raw_names = sorted(tech_to_components.get(tech, set()))
                total_unique += len(raw_names)

                cached_raw: List[str] = []
                unknown_raw: List[str] = []
                for raw in raw_names:
                    if _norm_key(raw) in mapping_by_norm_key:
                        cached_raw.append(raw)
                    else:
                        unknown_raw.append(raw)

                reps, _ = dedupe_by_norm_key_preserve_representative(unknown_raw)

                total_cached += len(cached_raw)
                total_unknown_raw += len(unknown_raw)
                total_unknown_reps += len(reps)

                per_tech_reports[tech] = {
                    "technology": tech,
                    "unique_components": len(raw_names),
                    "cached_raw": len(cached_raw),
                    "unknown_raw": len(unknown_raw),
                    "unknown_reps": len(reps),
                }

            print("=== DRY RUN (group-by technology) ===")
            print(f"pattern: {args.pattern}")
            print(f"csv_files: {len(csv_paths)}")
            if only_configs:
                print(f"only_configs: {sorted(only_configs)}")
            print(f"json_files: {len(json_paths)}")
            print(f"technologies: {len(techs)}")
            print(f"unique_components_total: {total_unique}")
            print(f"cached_components_raw_total: {total_cached}")
            print(f"unknown_components_raw_total: {total_unknown_raw}")
            print(f"unknown_components_normkey_total: {total_unknown_reps}")
            # Print a small sample of per-tech summaries (stable order)
            sample = techs[: min(10, len(techs))]
            print("\nPer-technology summary (sample):")
            for t in sample:
                r = per_tech_reports[t]
                print(
                    f"  - {t}: unique={r['unique_components']}, cached={r['cached_raw']}, "
                    f"unknown_raw={r['unknown_raw']}, unknown_reps={r['unknown_reps']}"
                )
            return

        # Non-dry-run: call LLM per technology (chunked) with progress output.
        total_techs = len(techs)
        print(f"Starting v2 normalization (group-by technology): {total_techs} technologies")
        sys.stdout.flush()

        for tech_idx, tech in enumerate(techs, start=1):
            raw_names = sorted(tech_to_components.get(tech, set()))
            total_unique += len(raw_names)

            cached_raw: List[str] = []
            unknown_raw: List[str] = []
            for raw in raw_names:
                if _norm_key(raw) in mapping_by_norm_key:
                    cached_raw.append(raw)
                else:
                    unknown_raw.append(raw)

            reps, norm_key_to_variants = dedupe_by_norm_key_preserve_representative(unknown_raw)
            total_cached += len(cached_raw)
            total_unknown_raw += len(unknown_raw)
            total_unknown_reps += len(reps)

            total_chunks = (len(reps) + args.chunk_size - 1) // args.chunk_size if reps else 0
            print(
                f"[{tech_idx}/{total_techs}] {tech}: unique={len(raw_names)} "
                f"cached_raw={len(cached_raw)} unknown_reps={len(reps)} chunks={total_chunks}"
            )
            sys.stdout.flush()

            new_mappings_raw: Dict[str, str] = {}
            if reps:
                for chunk_idx, chunk in enumerate(chunked(reps, args.chunk_size), start=1):
                    print(f"  - chunk {chunk_idx}/{total_chunks} ({len(chunk)} names)")
                    sys.stdout.flush()

                    chunk_map = await llm_normalize_chunk(
                        names=chunk,
                        model=args.model,
                        non_primary_sentinel=args.non_primary_sentinel,
                        existing_canonicals=existing_canonicals,
                        retries=retries,
                        technology=tech,
                    )
                    new_mappings_raw.update(chunk_map)
                    existing_canonicals.extend(chunk_map.values())

            # Expand rep mappings to all variants and update global mapping.
            new_added = 0
            for rep_raw, canon in new_mappings_raw.items():
                rep_key = _norm_key(rep_raw)
                if rep_key not in mapping_by_norm_key or mapping_by_norm_key[rep_key] != canon:
                    mapping_by_norm_key[rep_key] = canon
                    new_added += 1
                for variant_raw in norm_key_to_variants.get(rep_key, []):
                    k = _norm_key(variant_raw)
                    if k not in mapping_by_norm_key or mapping_by_norm_key[k] != canon:
                        mapping_by_norm_key[k] = canon
                        new_added += 1

            # Write per-technology manifest (audit)
            per_tech_manifest = {
                "version": "1.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "technology": tech,
                "model": args.model,
                "chunk_size": args.chunk_size,
                "non_primary_sentinel": args.non_primary_sentinel,
                "unique_components_total": len(raw_names),
                "cached_components_raw_count": len(cached_raw),
                "unknown_components_raw_count": len(unknown_raw),
                "unknown_components_normkey_count": len(reps),
                "new_mappings_added": new_added,
                "notes": [
                    "Per-technology normalization (v2).",
                    "LLM prompted with TARGET TECHNOLOGY context to reduce ambiguity.",
                    "Mappings expanded from norm-key representatives to all observed variants.",
                ],
            }
            manifest_path = (
                manifest_dir
                / f"normalization_manifest_{safe_filename_slug(tech)}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            )
            manifest_path.write_text(
                json.dumps(per_tech_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            print(f"  ✓ wrote per-tech manifest; new_mappings_added={new_added}")
            sys.stdout.flush()

        # Persist global vocab after all technologies
        print("Persisting global vocab...")
        sys.stdout.flush()
        save_global_vocab(global_vocab_path, mapping_by_norm_key)

        # Rewrite CSVs + JSONs (global mapping applied everywhere) with progress output
        print(f"Rewriting {len(csv_paths)} CSVs to {out_dir}...")
        sys.stdout.flush()
        output_csvs: List[str] = []
        output_jsons: List[str] = []
        dropped_total = 0

        for i, pth in enumerate(csv_paths, start=1):
            out_path, changed, dropped = apply_mapping_to_csv(
                csv_path=pth,
                out_dir=out_dir,
                mapping_by_norm_key=mapping_by_norm_key,
                non_primary_sentinel=args.non_primary_sentinel,
                drop_non_primary=args.drop_non_primary,
            )
            dropped_total += dropped
            output_csvs.append(str(out_path))
            if i == 1 or i % 10 == 0 or i == len(csv_paths):
                print(
                    f"  - CSV {i}/{len(csv_paths)}: {pth.name} changed={changed} dropped={dropped}"
                )
                sys.stdout.flush()

        if json_paths:
            print(f"Rewriting {len(json_paths)} JSONs to {out_dir} (best-effort)...")
            sys.stdout.flush()
        for i, pth in enumerate(json_paths, start=1):
            out_path, changed = apply_mapping_to_json(
                json_path=pth,
                out_dir=out_dir,
                mapping_by_norm_key=mapping_by_norm_key,
                non_primary_sentinel=args.non_primary_sentinel,
                drop_non_primary=args.drop_non_primary,
            )
            output_jsons.append(str(out_path))
            if i == 1 or i % 10 == 0 or i == len(json_paths):
                print(f"  - JSON {i}/{len(json_paths)}: {pth.name} changed={changed}")
                sys.stdout.flush()

        # Write global manifest
        notes = [
            "v2 mode enabled: group-by technology.",
            "Per-technology manifests written for auditability.",
            "Global mapping is keyed by normalized raw string (_norm_key).",
            "Granularity enforced via LLM prompt; parts/subassemblies promoted to primary components.",
            (
                "If the same raw string appears in multiple technologies, the global mapping will unify it. "
                "This is intentional; use the per-technology manifests to audit domain-specific decisions."
            ),
        ]
        manifest = Manifest(
            version="1.0",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            pattern=args.pattern,
            model=args.model,
            output_dir=str(out_dir),
            global_vocab_path=str(global_vocab_path),
            chunk_size=args.chunk_size,
            non_primary_sentinel=args.non_primary_sentinel,
            input_csvs=[str(p) for p in csv_paths],
            input_jsons=[str(p) for p in json_paths],
            output_csvs=output_csvs,
            output_jsons=output_jsons,
            unique_components_total=total_unique,
            cached_components_count=total_cached,
            unknown_components_count=total_unknown_reps,
            new_mappings_added=0,  # detailed per-tech; global additions are in vocab diff + per-tech manifests
            dropped_non_primary_count=dropped_total,
            notes=notes,
        )

        if args.manifest_path.strip():
            manifest_path = Path(args.manifest_path)
        else:
            manifest_path = (
                out_dir
                / f"normalization_manifest_global_primary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            )

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.__dict__, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print("\n=== GLOBAL GRANULARITY NORMALIZATION COMPLETE (group-by technology) ===")
        print(f"Input CSVs: {len(csv_paths)}")
        print(f"Input JSONs: {len(json_paths)}")
        print(f"Technologies: {len(techs)}")
        print(f"Unique components (sum over techs): {total_unique}")
        print(f"Cached (raw sum over techs): {total_cached}")
        print(f"Unknown normalized by LLM (norm-key reps sum over techs): {total_unknown_reps}")
        print(f"Dropped non-primary rows/objects: {dropped_total}")
        print(f"Wrote normalized CSVs to: {out_dir}")
        print(f"Wrote global vocab: {global_vocab_path}")
        print(f"Wrote per-technology manifests to: {manifest_dir}")
        print(f"Wrote global manifest: {manifest_path}")
        return

    # -------------------------
    # v1: global names-only
    # -------------------------

    # Extract unique components
    unique_components = sorted(extract_unique_components_from_csvs(csv_paths))
    if args.max_unique_components and args.max_unique_components > 0:
        unique_components = unique_components[: args.max_unique_components]

    # Cache hits based on normalized keys
    cached: Dict[str, str] = {}
    unknown_raw: List[str] = []
    existing_canonicals: List[str] = []

    for raw in unique_components:
        key = _norm_key(raw)
        if key in existing_vocab:
            cached[raw] = existing_vocab[key]
            existing_canonicals.append(existing_vocab[key])
        else:
            unknown_raw.append(raw)

    # Deduplicate unknowns by normalized key to reduce LLM cost and improve consistency
    unknown_reps, unknown_norm_key_to_variants = dedupe_by_norm_key_preserve_representative(
        unknown_raw
    )

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"pattern: {args.pattern}")
        print(f"csv_files: {len(csv_paths)}")
        if only_configs:
            print(f"only_configs: {sorted(only_configs)}")
        print(f"json_files: {len(json_paths)}")
        print(f"unique_components_total: {len(unique_components)}")
        print(f"cached_components_count: {len(cached)}")
        print(f"unknown_components_raw_count: {len(unknown_raw)}")
        print(f"unknown_components_normkey_count: {len(unknown_reps)}")
        if unknown_reps:
            print("\nExamples of unknown component names (representatives):")
            for s in unknown_reps[: min(30, len(unknown_reps))]:
                print(f"  - {s}")
        return

    # LLM normalize unknown names in chunks
    new_mappings_raw: Dict[str, str] = {}
    if unknown_reps:
        for chunk in chunked(unknown_reps, args.chunk_size):
            chunk_map = await llm_normalize_chunk(
                names=chunk,
                model=args.model,
                non_primary_sentinel=args.non_primary_sentinel,
                existing_canonicals=existing_canonicals,
                retries=retries,
            )
            new_mappings_raw.update(chunk_map)
            # Update canonical examples to improve consistency across chunks
            existing_canonicals.extend(chunk_map.values())

    # Build global mapping keyed by normalized key
    #
    # NOTE: we expand representative mappings to all variants sharing the same norm-key.
    mapping_by_norm_key: Dict[str, str] = dict(existing_vocab)
    new_added = 0

    for rep_raw, canon in new_mappings_raw.items():
        rep_key = _norm_key(rep_raw)
        # Apply to the rep key itself
        if rep_key not in mapping_by_norm_key or mapping_by_norm_key[rep_key] != canon:
            mapping_by_norm_key[rep_key] = canon
            new_added += 1

        # Also apply to all observed variants for that key (defensive: should be same key)
        for variant_raw in unknown_norm_key_to_variants.get(rep_key, []):
            k = _norm_key(variant_raw)
            if k not in mapping_by_norm_key or mapping_by_norm_key[k] != canon:
                mapping_by_norm_key[k] = canon
                new_added += 1

    # Persist global vocab
    save_global_vocab(global_vocab_path, mapping_by_norm_key)

    # Rewrite CSVs + JSONs
    output_csvs: List[str] = []
    output_jsons: List[str] = []

    dropped_total = 0

    for pth in csv_paths:
        out_path, _, dropped = apply_mapping_to_csv(
            csv_path=pth,
            out_dir=out_dir,
            mapping_by_norm_key=mapping_by_norm_key,
            non_primary_sentinel=args.non_primary_sentinel,
            drop_non_primary=args.drop_non_primary,
        )
        dropped_total += dropped
        output_csvs.append(str(out_path))

    for pth in json_paths:
        out_path, _ = apply_mapping_to_json(
            json_path=pth,
            out_dir=out_dir,
            mapping_by_norm_key=mapping_by_norm_key,
            non_primary_sentinel=args.non_primary_sentinel,
            drop_non_primary=args.drop_non_primary,
        )
        output_jsons.append(str(out_path))

    # Write manifest
    notes = [
        "Global normalization is applied across all configs (pattern-driven).",
        "Granularity enforced via LLM prompt: map parts/subassemblies to primary components.",
        "Non-primary items mapped to sentinel; optionally dropped with --drop-non-primary.",
        "CSV treated as source of truth; JSON rewritten best-effort.",
    ]

    manifest = Manifest(
        version="1.0",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        pattern=args.pattern,
        model=args.model,
        output_dir=str(out_dir),
        global_vocab_path=str(global_vocab_path),
        chunk_size=args.chunk_size,
        non_primary_sentinel=args.non_primary_sentinel,
        input_csvs=[str(p) for p in csv_paths],
        input_jsons=[str(p) for p in json_paths],
        output_csvs=output_csvs,
        output_jsons=output_jsons,
        unique_components_total=len(unique_components),
        cached_components_count=len(cached),
        unknown_components_count=len(unknown_reps),
        new_mappings_added=new_added,
        dropped_non_primary_count=dropped_total,
        notes=notes
        + [
            (
                "Unknown component names were deduplicated by normalized key prior to LLM calls: "
                f"raw_unknown={len(unknown_raw)}, normkey_unknown={len(unknown_reps)}."
            )
        ],
    )

    if args.manifest_path.strip():
        manifest_path = Path(args.manifest_path)
    else:
        manifest_path = (
            out_dir
            / f"normalization_manifest_global_primary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest.__dict__, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== GLOBAL GRANULARITY NORMALIZATION COMPLETE ===")
    print(f"Input CSVs: {len(csv_paths)}")
    print(f"Input JSONs: {len(json_paths)}")
    print(f"Unique components: {len(unique_components)}")
    print(f"Cached: {len(cached)}")
    print(f"Unknown normalized by LLM (norm-key deduped reps): {len(unknown_reps)}")
    print(f"New mappings added: {new_added}")
    print(f"Dropped non-primary rows/objects: {dropped_total}")
    print(f"Wrote normalized CSVs to: {out_dir}")
    print(f"Wrote global vocab: {global_vocab_path}")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    # Run as an async entrypoint without adding additional dependencies.
    import asyncio

    asyncio.run(main())
