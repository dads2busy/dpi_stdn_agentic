#!/usr/bin/env python3
"""
Audit global normalization for "raw -> canonical" judge flips (laundering risk).

Goal
----
Detect whether global, LLM-driven component normalization is turning components that
are judged NOT plausible into canonical components that are judged plausible.

This script compares *raw* components from output/raw/stdns_output_<config>_<ts>.csv
to their *canonical primary-component* mappings from a global vocab JSON
(e.g., data/component_canonical_vocab_global_primary.json).

For each (technology, raw_component) pair:
  - raw_verdict = judge(technology, raw_component)
  - canonical = vocab[_norm_key(raw_component)] if present else raw_component
  - canonical_verdict = judge(technology, canonical)  (unless canonical is NON_PRIMARY sentinel)

We then categorize:
  - invalid_to_valid: raw false -> canonical true  (potential "laundering")
  - valid_to_invalid: raw true  -> canonical false (over-normalization risk)
  - same: both true or both false
  - filtered_non_primary: canonical maps to NON_PRIMARY sentinel (excluded from canonical judging)

Design choices
--------------
- Exclude canonical NON_PRIMARY sinks from canonical judging (option A).
  These are treated as "filtered_non_primary" outcomes.
- Use an LLM judge prompt aligned with the component agent's concept definition:
  subassemblies/modules are valid components; exclude raw materials, tools,
  consumables, and packaging.

Caching
-------
- Cache judgments by exact (technology, component) pair in a JSONL file so reruns are cheap.
  NOTE: If you change the judge prompt materially, delete/rotate the cache file.

Run (recommended via uv so .venv deps are used)
-----------------------------------------------
uv run python scripts/audit_global_normalization_judge_flips.py \
  --raw-dir output/raw \
  --configs v1v1v1 d2v1v1 d3v1v1 d4v1v1 d5v1v1 \
  --global-vocab data/component_canonical_vocab_global_primary.json \
  --judge-model openai:gpt-4.1 \
  --out-md output/analysis/global_norm_flip_audit.md \
  --out-jsonl output/analysis/global_norm_flip_audit.jsonl

Dry run
-------
uv run python scripts/audit_global_normalization_judge_flips.py --dry-run ...

Dependencies
------------
- python 3.10+
- pydantic, pydantic_ai
- python-dotenv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from dotenv import load_dotenv

# Load provider keys (OPENAI_API_KEY, etc.) if present.
load_dotenv()

from pydantic import BaseModel, Field
from pydantic_ai import Agent

# -----------------------------
# Constants / patterns
# -----------------------------

NON_PRIMARY_SENTINEL_DEFAULT = "__NON_PRIMARY__"

_RX_FILE = re.compile(
    r"^stdns_output_(?P<config>[a-z0-9]+)_(?P<ts>\d{8}_\d{6})\.csv$",
    re.IGNORECASE,
)

_WS_RE = re.compile(r"\s+")
_DASH_RE = re.compile(r"[\u2013\u2014]")  # en/em dash


# -----------------------------
# Models
# -----------------------------


class JudgeVerdict(BaseModel):
    plausible: bool = Field(
        description="True if the component is a plausible primary manufacturing component."
    )
    rationale: str = Field(
        description="Short justification for the plausibility decision (1-3 sentences)."
    )


@dataclass(frozen=True)
class RunFile:
    path: Path
    config: str
    timestamp: str


@dataclass(frozen=True)
class CacheKey:
    technology: str
    component: str

    def as_str(self) -> str:
        return f"{self.technology}|||{self.component}"


@dataclass(frozen=True)
class Judgment:
    technology: str
    component: str
    plausible: bool
    rationale: str
    judged_at_utc: str
    judge_model: str


@dataclass(frozen=True)
class RawCanonicalPair:
    technology: str
    raw_component: str
    canonical_component: str
    config: str
    run_timestamp: str
    source_csv: str


# -----------------------------
# Normalization helpers
# -----------------------------


def _strip(s: str) -> str:
    return _WS_RE.sub(" ", (s or "").strip())


def _norm_key(s: str) -> str:
    """
    Conservative key normalization for vocab lookup.
    Must be consistent with the global normalization script's keying.
    """
    t = _strip(s)
    t = _DASH_RE.sub("-", t)
    t = t.strip(" \t\r\n.,;:()[]{}")
    return t.lower()


def load_global_vocab(path: Path) -> Dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Global vocab not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    mappings = data.get("mappings", {})
    if not isinstance(mappings, dict):
        raise ValueError(f"Global vocab has no mappings dict: {path}")
    # Keys in the file are expected to already be normalized keys.
    return {str(k): str(v) for k, v in mappings.items()}


# -----------------------------
# Input loading
# -----------------------------


def iter_run_csvs(raw_dir: Path) -> Iterable[RunFile]:
    for p in sorted(raw_dir.glob("stdns_output_*.csv")):
        m = _RX_FILE.match(p.name)
        if not m:
            continue
        yield RunFile(path=p, config=m.group("config").lower(), timestamp=m.group("ts"))


def load_raw_components_by_run(csv_path: Path) -> Dict[str, Set[str]]:
    """
    Return per-technology set of unique raw components for this run.
    Dedup via set; CSV is denormalized over material/country.
    """
    tech_to_components: Dict[str, Set[str]] = defaultdict(set)

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Missing header row: {csv_path}")

        fields = {name.strip().lower(): name for name in reader.fieldnames}
        if "technology" not in fields or "component" not in fields:
            raise ValueError(
                f"CSV missing required columns technology/component: {csv_path} "
                f"(found {reader.fieldnames})"
            )
        tech_col = fields["technology"]
        comp_col = fields["component"]

        for row in reader:
            tech = _strip(row.get(tech_col, ""))
            comp = _strip(row.get(comp_col, ""))
            if not tech or not comp:
                continue
            tech_to_components[tech].add(comp)

    return tech_to_components


def build_pairs(
    run_files: Sequence[RunFile],
    configs: Set[str],
    technologies: Optional[Set[str]],
    vocab: Dict[str, str],
    non_primary_sentinel: str,
) -> List[RawCanonicalPair]:
    out: List[RawCanonicalPair] = []

    for rf in run_files:
        if configs and rf.config not in configs:
            continue

        tech_to_components = load_raw_components_by_run(rf.path)
        for tech, comps in tech_to_components.items():
            if technologies is not None and tech not in technologies:
                continue
            for raw in sorted(comps):
                k = _norm_key(raw)
                canonical = vocab.get(k, raw)
                canonical = _strip(canonical)

                # Canonical may legitimately map to sentinel (filtered sink)
                if not canonical:
                    canonical = raw

                out.append(
                    RawCanonicalPair(
                        technology=tech,
                        raw_component=raw,
                        canonical_component=canonical,
                        config=rf.config,
                        run_timestamp=rf.timestamp,
                        source_csv=str(rf.path),
                    )
                )

    return out


# -----------------------------
# Judge prompt + agent
# -----------------------------


def build_judge_prompt(technology: str, component: str) -> str:
    """
    Judge prompt aligned with the component agent concept definition:
    - subassemblies/modules are valid components
    - exclude raw materials, tools, consumables, packaging
    - do not reject merely because it is part of a larger assembly
    """
    return f"""You are an expert in technology manufacturing and supply chain analysis.

**CRITICAL: Always respond in English.**

**STEP 1: TECHNOLOGY SPECIFICATION**
First, identify the MOST COMMON, INDUSTRY-STANDARD form of the technology requested.
- Use precise industry terminology and technical nomenclature
- Identify the dominant market variant by production volume or market adoption
- Consider current market standards (as of 2024-2025)
- ALWAYS validate the user's term, even if already specific

You do NOT need to output the technology specification, but you MUST use it when judging the candidate component below.

**STEP 2: COMPONENT IDENTIFICATION (VALIDITY CHECK)**
Your task is to determine whether the candidate below is a PRIMARY MANUFACTURING COMPONENT for the SPECIFIED technology product.

PRIMARY COMPONENTS are major subassemblies or modules that:
- Are procured or manufactured separately
- Have distinct supply chains
- Form the core functional or structural architecture
- Are typically purchased as complete units

INCLUDE:
- Major functional modules (e.g., display, battery, processor, control system)
- Structural assemblies (e.g., chassis, enclosure, vessel body)
- Key subassemblies with separate suppliers
- Electronic boards and subsystems

EXCLUDE:
- Raw materials (metals, plastics, chemicals) - these are inputs TO components
- Manufacturing tools and equipment
- Consumables (adhesives, fasteners, solvents, lubricants)
- Generic supplies and packaging materials
- Overly generic labels without function (e.g., "Module", "Unit", "System" without a clear function)

CRITICAL INTERPRETATION NOTE:
- Subassemblies are valid components when they represent meaningful dependency boundaries (i.e., manufactured/assembled as discrete units and integrated into the final product).
- Do NOT reject a candidate simply because it is part of a larger assembly; reject it only if it is a raw material, consumable, packaging, a tool, or an overly generic/non-functional label.

Now evaluate:

Technology: {technology}
Candidate component: {component}

Return JSON with:
- plausible: true/false
- rationale: 1-3 sentences, concise and technical
"""


def make_judge_agent(judge_model: str, retries: int) -> Agent[None, JudgeVerdict]:
    return Agent(
        model=judge_model,
        output_type=JudgeVerdict,
        system_prompt=(
            "You judge whether a candidate is a plausible primary manufacturing component. "
            "Output valid JSON only."
        ),
        retries=retries,
        output_retries=retries,
    )


# -----------------------------
# Cache (JSONL)
# -----------------------------


def load_cache_jsonl(cache_path: Path) -> Dict[str, Judgment]:
    cache: Dict[str, Judgment] = {}
    if not cache_path.exists():
        return cache
    with cache_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            key = str(o["key"])
            cache[key] = Judgment(
                technology=str(o["technology"]),
                component=str(o["component"]),
                plausible=bool(o["plausible"]),
                rationale=str(o.get("rationale", "")),
                judged_at_utc=str(o.get("judged_at_utc", "")),
                judge_model=str(o.get("judge_model", "")),
            )
    return cache


def append_cache_jsonl(cache_path: Path, key: CacheKey, j: Judgment) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "key": key.as_str(),
        "technology": j.technology,
        "component": j.component,
        "plausible": j.plausible,
        "rationale": j.rationale,
        "judged_at_utc": j.judged_at_utc,
        "judge_model": j.judge_model,
    }
    with cache_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


# -----------------------------
# Flip computation + reporting
# -----------------------------


def categorize_flip(
    raw_plausible: Optional[bool],
    canonical_plausible: Optional[bool],
    canonical_filtered_non_primary: bool,
) -> str:
    if canonical_filtered_non_primary:
        return "filtered_non_primary"
    if raw_plausible is None or canonical_plausible is None:
        return "missing"
    if raw_plausible is False and canonical_plausible is True:
        return "invalid_to_valid"
    if raw_plausible is True and canonical_plausible is False:
        return "valid_to_invalid"
    if raw_plausible == canonical_plausible:
        return "same"
    return "other"


def md_table(headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> str:
    def fmt(x: Any) -> str:
        if x is None:
            return "NA"
        if isinstance(x, float):
            return f"{x:.3f}"
        return str(x)

    lines: List[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(fmt(r.get(h)) for h in headers) + " |")
    return "\n".join(lines) + "\n"


def write_md_report(
    out_path: Path,
    *,
    raw_dir: Path,
    configs: List[str],
    global_vocab_path: Path,
    judge_model: str,
    cache_path: Path,
    counts: Counter,
    examples: Dict[str, List[Dict[str, Any]]],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = sum(counts.values())
    parts: List[str] = []
    parts.append("# Global Normalization Flip Audit (Raw vs Canonical)\n\n")
    parts.append(
        "This report audits whether global component normalization introduces judge flips between:\n"
        "- raw components extracted from `output/raw/*.csv`, and\n"
        "- canonical components produced by the global vocab mapping.\n\n"
        "Canonical mappings to the NON_PRIMARY sentinel are excluded from canonical judging and counted as `filtered_non_primary`.\n\n"
    )
    parts.append(f"- raw_dir: `{raw_dir}`\n")
    parts.append(f"- configs: {', '.join(configs)}\n")
    parts.append(f"- global_vocab: `{global_vocab_path}`\n")
    parts.append(f"- judge_model: `{judge_model}`\n")
    parts.append(f"- cache: `{cache_path}`\n\n")

    rows = []
    for cat in [
        "invalid_to_valid",
        "valid_to_invalid",
        "same",
        "filtered_non_primary",
        "missing",
        "other",
    ]:
        c = int(counts.get(cat, 0))
        rows.append({"category": cat, "count": c, "pct": (c / total) if total else None})
    parts.append("## Flip counts\n\n")
    parts.append(md_table(["category", "count", "pct"], rows))

    def write_examples(cat: str) -> None:
        ex = examples.get(cat, [])
        if not ex:
            return
        parts.append(f"\n## Examples: {cat}\n\n")
        parts.append(
            md_table(
                [
                    "technology",
                    "raw_component",
                    "raw_plausible",
                    "canonical_component",
                    "canonical_plausible",
                    "canonical_filtered_non_primary",
                    "raw_rationale",
                    "canonical_rationale",
                ],
                ex,
            )
        )

    # Show the most important categories first
    write_examples("invalid_to_valid")
    write_examples("valid_to_invalid")
    write_examples("filtered_non_primary")

    out_path.write_text("".join(parts), encoding="utf-8")


# -----------------------------
# CLI
# -----------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Audit judge flips introduced by global normalization (raw vs canonical)."
    )
    p.add_argument("--raw-dir", default="output/raw", help="Directory containing raw output CSVs.")
    p.add_argument(
        "--configs",
        nargs="+",
        required=True,
        help="Config tags to include (e.g., v1v1v1 d2v1v1 d3v1v1 d4v1v1 d5v1v1).",
    )
    p.add_argument(
        "--technologies",
        nargs="*",
        default=None,
        help="Optional list of technologies to include (if omitted, all are included).",
    )
    p.add_argument(
        "--global-vocab",
        required=True,
        help="Path to global canonical vocab JSON (data/component_canonical_vocab_global_primary.json).",
    )
    p.add_argument(
        "--non-primary-sentinel",
        default=NON_PRIMARY_SENTINEL_DEFAULT,
        help="Sentinel used by the global normalizer for non-primary items.",
    )
    p.add_argument("--judge-model", default="openai:gpt-4.1", help="Judge model identifier.")
    p.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("STDN_AGENT_RETRIES", "5") or "5"),
        help="Judge agent retry count (default: STDN_AGENT_RETRIES or 5).",
    )
    p.add_argument(
        "--cache-jsonl",
        default="output/analysis/global_norm_flip_judge_cache.jsonl",
        help="JSONL cache for judge calls keyed by (technology, component).",
    )
    p.add_argument(
        "--max-new-judgments",
        type=int,
        default=0,
        help="Optional cap on NEW (uncached) judgments to run (0 = no cap).",
    )
    p.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle missing judgments before applying max-new-judgments (sampling).",
    )
    p.add_argument("--seed", type=int, default=0, help="Seed for --shuffle.")
    p.add_argument(
        "--prioritize-non-sentinel-canonicals",
        action="store_true",
        help="When sampling under --max-new-judgments, prioritize missing canonical (non-sentinel) keys first (better laundering sensitivity).",
    )
    p.add_argument(
        "--out-md",
        default="output/analysis/global_norm_flip_audit.md",
        help="Markdown report output path.",
    )
    p.add_argument(
        "--out-jsonl",
        default="output/analysis/global_norm_flip_audit.jsonl",
        help="JSONL output of per-item audit results.",
    )
    p.add_argument(
        "--max-examples",
        type=int,
        default=30,
        help="Max example rows to include per category in the markdown report.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call judge model; just compute candidate counts and required judgments.",
    )
    return p.parse_args(argv)


# -----------------------------
# Main
# -----------------------------


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists():
        print(f"ERROR: raw dir not found: {raw_dir}", file=sys.stderr)
        return 2

    configs = [c.strip().lower() for c in args.configs if c.strip()]
    cfg_set = set(configs)
    if not cfg_set:
        print("ERROR: at least one config required", file=sys.stderr)
        return 2

    tech_filter = (
        set(t.strip() for t in (args.technologies or []) if t.strip())
        if args.technologies
        else None
    )

    vocab_path = Path(args.global_vocab)
    vocab = load_global_vocab(vocab_path)

    run_files = [rf for rf in iter_run_csvs(raw_dir) if rf.config in cfg_set]
    if not run_files:
        print(
            f"ERROR: no raw run files found for configs={configs} under {raw_dir}", file=sys.stderr
        )
        return 2

    pairs = build_pairs(
        run_files=run_files,
        configs=cfg_set,
        technologies=tech_filter,
        vocab=vocab,
        non_primary_sentinel=args.non_primary_sentinel,
    )

    # Dedup to unique (technology, raw_component, canonical_component)
    uniq: Dict[Tuple[str, str, str], RawCanonicalPair] = {}
    for p in pairs:
        k = (p.technology, p.raw_component, p.canonical_component)
        uniq[k] = p
    unique_pairs = list(uniq.values())

    cache_path = Path(args.cache_jsonl)
    cache = load_cache_jsonl(cache_path)

    # Determine which judgments are missing
    needed_keys: Dict[str, CacheKey] = {}
    for p in unique_pairs:
        raw_key = CacheKey(p.technology, p.raw_component)
        needed_keys[raw_key.as_str()] = raw_key
        # canonical may be sentinel; we still may need to judge raw
        if p.canonical_component != args.non_primary_sentinel:
            canon_key = CacheKey(p.technology, p.canonical_component)
            needed_keys[canon_key.as_str()] = canon_key

    missing: List[CacheKey] = [k for kstr, k in needed_keys.items() if kstr not in cache]

    # Optional targeted sampling:
    # If you cap new judgments, you'll get far better sensitivity to invalid_to_valid flips by
    # prioritizing missing canonical (non-sentinel) keys over raw keys and sentinel canonicals.
    if args.prioritize_non_sentinel_canonicals:
        non_sentinel_canon_needed: Dict[str, CacheKey] = {}
        for p in unique_pairs:
            if p.canonical_component == args.non_primary_sentinel:
                continue
            canon_key = CacheKey(p.technology, p.canonical_component)
            kstr = canon_key.as_str()
            if kstr not in cache:
                non_sentinel_canon_needed[kstr] = canon_key

        prioritized: List[CacheKey] = list(non_sentinel_canon_needed.values())
        remainder: List[CacheKey] = [
            k for k in missing if k.as_str() not in non_sentinel_canon_needed
        ]
        missing = prioritized + remainder

    if args.shuffle:
        random.seed(args.seed)
        random.shuffle(missing)

    if (
        args.max_new_judgments
        and args.max_new_judgments > 0
        and len(missing) > args.max_new_judgments
    ):
        missing = missing[: args.max_new_judgments]

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"raw_dir: {raw_dir}")
        print(f"configs: {configs}")
        if tech_filter:
            print(f"technologies: {sorted(tech_filter)}")
        print(f"run_files: {len(run_files)}")
        print(f"raw->canonical pairs (per-run): {len(pairs)}")
        print(f"unique pairs (technology, raw, canonical): {len(unique_pairs)}")
        print(f"needed judge keys (raw+canonical): {len(needed_keys)}")
        print(f"cached: {len(cache)}")
        print(f"missing (to judge): {len(missing)}")
        print(f"judge_model: {args.judge_model}")
        print(f"cache: {cache_path}")
        return 0

    agent = make_judge_agent(args.judge_model, retries=args.retries)

    judged_new = 0
    for idx, key in enumerate(missing, start=1):
        prompt = build_judge_prompt(key.technology, key.component)
        try:
            result = agent.run_sync(prompt)
            verdict = result.output
            rec = Judgment(
                technology=key.technology,
                component=key.component,
                plausible=bool(verdict.plausible),
                rationale=str(verdict.rationale),
                judged_at_utc=datetime.now(timezone.utc).isoformat(),
                judge_model=args.judge_model,
            )
            append_cache_jsonl(cache_path, key, rec)
            cache[key.as_str()] = rec
            judged_new += 1
        except Exception as e:
            print(f"WARNING: judge failed for {key.as_str()}: {e}", file=sys.stderr)
            continue

        if idx == 1 or idx % 25 == 0 or idx == len(missing):
            print(f"Judged {idx}/{len(missing)} new items...")
            sys.stdout.flush()

    # Compute flips
    counts: Counter = Counter()
    examples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    audit_rows: List[Dict[str, Any]] = []

    for p in unique_pairs:
        raw_key = CacheKey(p.technology, p.raw_component).as_str()
        raw_rec = cache.get(raw_key)

        canonical_filtered = p.canonical_component == args.non_primary_sentinel
        canon_rec = None
        if not canonical_filtered:
            canon_key = CacheKey(p.technology, p.canonical_component).as_str()
            canon_rec = cache.get(canon_key)

        raw_pl = raw_rec.plausible if raw_rec is not None else None
        canon_pl = canon_rec.plausible if canon_rec is not None else None

        cat = categorize_flip(raw_pl, canon_pl, canonical_filtered)
        counts[cat] += 1

        row = {
            "technology": p.technology,
            "raw_component": p.raw_component,
            "raw_plausible": raw_pl,
            "canonical_component": p.canonical_component,
            "canonical_plausible": canon_pl,
            "canonical_filtered_non_primary": canonical_filtered,
            "raw_rationale": raw_rec.rationale if raw_rec else None,
            "canonical_rationale": canon_rec.rationale if canon_rec else None,
            "category": cat,
            "config": p.config,
            "run_timestamp": p.run_timestamp,
            "source_csv": p.source_csv,
        }
        audit_rows.append(row)

        # Save limited examples per category
        if len(examples[cat]) < args.max_examples:
            examples[cat].append(row)

    # Write JSONL
    out_jsonl = Path(args.out_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in audit_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write_md_report(
        out_path=Path(args.out_md),
        raw_dir=raw_dir,
        configs=configs,
        global_vocab_path=vocab_path,
        judge_model=args.judge_model,
        cache_path=cache_path,
        counts=counts,
        examples=examples,
    )

    print("\n=== COMPLETE ===")
    print(f"run_files: {len(run_files)}")
    print(f"unique pairs (technology, raw, canonical): {len(unique_pairs)}")
    print(f"judged_new: {judged_new}")
    print(f"cache: {cache_path}")
    print(f"report: {args.out_md}")
    print(f"audit_jsonl: {args.out_jsonl}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
