#!/usr/bin/env python3
"""
Verify component proposals using an LLM judge and produce a Markdown report.

Motivation
----------
You want evidence for whether debate improves component validity:
- `v1v1v1` has no filtering (single agent), so the "final components" are essentially unfiltered.
- Multi-agent debate configs (e.g. `d3v1v1`, `d5v1v1`) produce a final agreed-upon set that is implicitly filtered.

This script supports two complementary evaluations:
1) Judge "pruned / isolated" candidates (legacy behavior): items proposed by only one agent (low support).
2) Judge "final component lists": the components selected at the end of Stage 1 (what the pipeline would carry forward).

For a “final-only” comparison between configurations, use:
  --candidate-source final

What it does (high level)
-------------------------
- Reads debate transcripts (JSON preferred; TXT supported) under a directory.
- For selected technologies, extracts candidates from one of:
  - pruned/isolated proposals (single-support)
  - final Stage 1 component list (agreed/selected)
- Sends each (technology, component) item to a judge model via pydantic_ai.Agent.
- Writes a Markdown report (and optional JSONL raw results).

Requirements
------------
- Run via uv so dependencies are available:
    uv run python scripts/verify_pruned_components.py --help

- Needs OPENAI_API_KEY (or other provider key depending on the judge model).

Usage examples
--------------
Final-only comparison across configs for a technology:
    uv run python scripts/verify_pruned_components.py \
      --transcripts-dir output/transcripts \
      --technologies "Smartphone v1v1v1" "Smartphone d3v1v1" "Smartphone d5v1v1" \
      --candidate-source final \
      --judge-model openai:gpt-4.1 \
      --max-items 200 \
      --out-md output/analysis/final_component_verification_smartphone.md

Verify pruned/isolated candidates (legacy):
    uv run python scripts/verify_pruned_components.py \
      --transcripts-dir output/transcripts \
      --technologies "Solar Panel" "MRI Machine" "Bioreactor" \
      --candidate-source pruned \
      --judge-model openai:gpt-4.1 \
      --max-items 40 \
      --out-md output/analysis/pruned_component_verification.md

Notes / Caveats
---------------
- This is NOT ground truth. It is "LLM-as-judge" evidence. Treat as a proxy.
- To avoid bias, you should ideally:
  - use a different model for judging than for generation,
  - keep the judge prompt strict and consistent,
  - sample across multiple runs/configs.

- The transcript parsing is best-effort: transcripts vary across versions.
  This script targets multiple common transcript formats.
- IMPORTANT: A single-agent run may label everything as "consensus" in its printed support summary.
  That does not mean the items were filtered; it just reflects that there is only one proposer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from dotenv import load_dotenv

# Load environment variables from .env (if present) so provider keys like OPENAI_API_KEY are available.
load_dotenv()

# pydantic_ai is already a dependency of the project
from pydantic import BaseModel, Field
from pydantic_ai import Agent

# -----------------------------
# Data models
# -----------------------------


class JudgeVerdict(BaseModel):
    """
    Judge output schema.

    - plausible_primary_component:
        True if the item is plausibly a PRIMARY manufacturing component/subassembly for the technology.
        False if it is more like a raw material, tool, consumable, overly generic, or irrelevant.

    - confidence:
        Judge confidence in [0,1]. This is a *judge confidence*, not the pipeline confidence.

    - rationale:
        Short explanation. Should be crisp; 1-4 sentences.
    """

    plausible_primary_component: bool = Field(
        description=(
            "True if plausibly a primary manufacturing component/subassembly of the technology. "
            "False if it is likely not a primary component (e.g. raw material, tool, consumable, "
            "overly generic term, optional peripheral, or irrelevant)."
        )
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Judge confidence 0.0-1.0")
    rationale: str = Field(description="Short reasoning for the verdict")


@dataclass(frozen=True)
class CandidateItem:
    technology: str
    component: str
    group: str  # "pruned_single_support" | "final_components" | "consensus_kept" | "unknown"
    transcript_path: str
    transcript_kind: str  # "json" | "txt"


@dataclass(frozen=True)
class JudgedItem:
    technology: str
    component: str
    group: str
    transcript_path: str
    transcript_kind: str  # "json" | "txt"
    verdict: JudgeVerdict
    judge_model: str


# -----------------------------
# Transcript parsing
# -----------------------------


_ISOLATED_PATTERNS = [
    # Common system-generated feedback format
    re.compile(r"Isolated proposal\s+'([^']+)'\s+appears only once", re.IGNORECASE),
    # Some transcripts may omit quotes
    re.compile(r"Isolated proposal\s+([^;.\n]+?)\s+appears only once", re.IGNORECASE),
    # Materials-style isolated lines (sometimes reused)
    re.compile(r"❌\s*ISOLATED:\s*Only\s*1/3\s*agent\s*proposed\s*([^.]+)\.", re.IGNORECASE),
    re.compile(r"⚠\s*PARTIAL:\s*1/3\s*agents\s*proposed\s*([^.]+)\.", re.IGNORECASE),
]

# TXT transcript format support:
# Many saved transcripts include an "Initial Support Analysis" section with an explicit
# isolated list, e.g.:
#   Initial Support Analysis:
#     [I] Isolated (22 items):
#         • Steam Chamber (Vessel) (0.98) - needs peer support
#
# Some transcript variants may use different whitespace/punctuation, or slightly different
# wording (e.g., "item" vs "items"). Be permissive here; we'll still only accept bullet lines.
_ISOLATED_SECTION_HEADER_RX = re.compile(
    r"^\s*\[I\]\s+Isolated\s*\(\s*\d+\s+item(?:s)?\s*\)\s*:?\s*$",
    re.IGNORECASE,
)
_BULLET_RX = re.compile(r"^\s*[•\-\*]\s+(.+?)\s*$")

_CONSENSUS_PATTERNS = [
    # Typical consensus lines in feedback
    re.compile(r"Strong consensus on\s+'([^']+)'", re.IGNORECASE),
    # Materials-style consensus lines
    re.compile(r"✓\s*CONSENSUS:\s*3/3\s*agents\s*agree\s*on\s*([^(.\n]+)", re.IGNORECASE),
    # Alternate
    re.compile(r"CONSENSUS:\s*3/3\s*agents\s*agree\s*on\s*([^(.\n]+)", re.IGNORECASE),
]


def _normalize_component_name_for_reporting(name: str) -> str:
    name = (name or "").strip()
    # Keep original surface form mostly; just collapse whitespace.
    name = re.sub(r"\s+", " ", name)
    return name


def _extract_text_from_transcript_json(obj: Any) -> str:
    """
    Best-effort extraction of a text blob from a transcript JSON.
    Transcripts can vary; we try common keys and fallback to json.dumps.
    """
    if isinstance(obj, dict):
        # common possible fields
        for key in [
            "text",
            "content",
            "transcript_text",
            "pretty_text",
            "human_readable",
            "markdown",
        ]:
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                return v

        # sometimes stored as list of messages
        for key in ["messages", "events", "turns", "entries", "conversation"]:
            v = obj.get(key)
            if isinstance(v, list) and v:
                # attempt to concatenate message content fields
                parts: list[str] = []
                for item in v:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        for ck in ["content", "text", "message", "role_content"]:
                            cv = item.get(ck)
                            if isinstance(cv, str) and cv.strip():
                                parts.append(cv)
                                break
                if parts:
                    return "\n".join(parts)

    # fallback
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)


def extract_candidates_from_text(
    technology: str,
    text: str,
    transcript_path: str,
    transcript_kind: str,
    include_consensus: bool,
    include_final_components: bool,
    include_pruned_single_support: bool,
) -> list[CandidateItem]:
    """
    Extract candidate components from transcript text.

    Groups:
    - pruned_single_support:
        items that appear to be isolated / low-support (legacy; debate-specific)
    - final_components:
        items in the final Stage 1 component list (recommended for comparing configs)
    - consensus_kept:
        optional comparison group (pattern-based; legacy)

    TXT transcript support:
    - For .txt transcripts, first bound parsing to the Stage 1 (component extraction) section when possible.
    - Then parse:
        * "[I] Isolated (N items):" blocks with bullet lines (• ...)
        * "FINAL CONSENSUS: Components" numbered lists (1. ..., 2. ...)
        * Fallback: Agent_1 bullet proposals within Stage 1 (single-agent style)
    """
    items: list[CandidateItem] = []

    # Header-bounded parsing for TXT transcripts:
    # Many TXT transcripts include clear section headers. We restrict extraction to Stage 1 to avoid
    # picking up non-component artifacts (materials/countries) that can appear later in the transcript.
    if transcript_kind == "txt":
        # Start at the Stage 1 component extraction header if present
        start_idx = None
        end_idx = None
        lines_all = text.splitlines()
        for idx, line in enumerate(lines_all):
            if start_idx is None and line.strip() == "STAGE 1: COMPONENT EXTRACTION":
                start_idx = idx
                continue
            if start_idx is not None:
                # End at the end of component extraction (preferred)
                if line.strip() == "END OF COMPONENT EXTRACTION":
                    end_idx = idx
                    break
                # Or at materials extraction start (fallback)
                if line.strip() == "MATERIALS EXTRACTION DEBATE":
                    end_idx = idx
                    break

        if start_idx is not None:
            bounded = lines_all[start_idx : end_idx if end_idx is not None else len(lines_all)]
            text = "\n".join(bounded)

    # Final component list extraction (TXT-first): this is the most useful signal for
    # "how filtered is the final output" across configs (v1 vs d3 vs d5...).
    if include_final_components:
        # Parse numbered list under a header like:
        #   FINAL CONSENSUS: Components
        #     1. Display Module (OLED)
        #     2. Battery Pack (Lithium-ion)
        #
        # We search within the (possibly Stage-1 bounded) text.
        lines_all = text.splitlines()
        in_final_components = False
        found_any_final = False
        for line in lines_all:
            if line.strip().upper() == "FINAL CONSENSUS: COMPONENTS":
                in_final_components = True
                continue
            if in_final_components:
                # Stop if we hit another section divider / header block
                if (
                    line.strip().startswith("=====")
                    or line.strip().startswith("STAGE ")
                    or line.strip().startswith("END OF")
                ):
                    in_final_components = False
                    continue

                m_num = re.match(r"^\s*\d+\.\s+(.+?)\s*$", line)
                if not m_num:
                    continue
                comp = _normalize_component_name_for_reporting(m_num.group(1))
                if comp:
                    found_any_final = True
                    items.append(
                        CandidateItem(
                            technology=technology,
                            component=comp,
                            group="final_components",
                            transcript_path=transcript_path,
                            transcript_kind=transcript_kind,
                        )
                    )

        # Fallback for single-agent style TXT transcripts that may not include the numbered final list
        # (or if formatting changes): take Agent_1 bullet proposals as the "final" set proxy.
        if transcript_kind == "txt" and not found_any_final:
            in_agent1 = False
            for line in lines_all:
                if line.strip().startswith("Agent_1"):
                    in_agent1 = True
                    continue
                if in_agent1:
                    # stop at next header-ish line
                    if (
                        line.strip() == ""
                        or line.strip().startswith("Initial Support Analysis:")
                        or line.strip().startswith("ROUND ")
                    ):
                        # don't immediately stop on blank lines because bullets might have gaps,
                        # but this keeps us from drifting into later sections.
                        # We'll only stop on explicit Stage-1 markers below.
                        pass
                    if line.strip().startswith("Initial Support Analysis:"):
                        in_agent1 = False
                        continue
                    if line.strip().startswith("Agent_") and not line.strip().startswith("Agent_1"):
                        in_agent1 = False
                        continue

                    m_b = _BULLET_RX.match(line)
                    if not m_b:
                        continue
                    raw = m_b.group(1).strip()
                    core = raw.split(" - ", 1)[0].strip()
                    core = re.sub(r"\(\s*0\.\d+\s*\)\s*$", "", core).strip()
                    comp = _normalize_component_name_for_reporting(core)
                    if comp:
                        items.append(
                            CandidateItem(
                                technology=technology,
                                component=comp,
                                group="final_components",
                                transcript_path=transcript_path,
                                transcript_kind=transcript_kind,
                            )
                        )

    # isolated / pruned (pattern-based)
    if include_pruned_single_support:
        for rx in _ISOLATED_PATTERNS:
            for m in rx.findall(text):
                comp = _normalize_component_name_for_reporting(m)
                if comp:
                    items.append(
                        CandidateItem(
                            technology=technology,
                            component=comp,
                            group="pruned_single_support",
                            transcript_path=transcript_path,
                            transcript_kind=transcript_kind,
                        )
                    )

    # isolated / pruned (section-based, common in TXT transcripts)
    if include_pruned_single_support:
        lines = text.splitlines()
        in_isolated_section = False
        for line in lines:
            if _ISOLATED_SECTION_HEADER_RX.match(line):
                in_isolated_section = True
                continue
            # section ends when we hit another support header or a blank separator
            if in_isolated_section:
                if re.match(r"^\s*\[[A-Z]\]\s+\w+", line):
                    in_isolated_section = False
                    continue
                if line.strip() == "":
                    continue
                m = _BULLET_RX.match(line)
                if not m:
                    # If indentation/format changes, keep scanning but only accept bullet lines.
                    continue
                raw = m.group(1).strip()

                # Exclude non-component bullet lines that can appear in analysis sections, e.g.:
                #   "Removed: ...", "Added: ...", "Changes from Previous Round: ..."
                # These are meta summaries, not candidate components.
                lowered = raw.lower()
                if (
                    lowered.startswith("removed:")
                    or lowered.startswith("added:")
                    or lowered.startswith("changes from previous round:")
                ):
                    continue

                # Extract the component name from formats like:
                #   Steam Chamber (Vessel) (0.98) - needs peer support
                #   Control System (PLC/Microcontroller) (0.92) - needs peer support
                # Strategy: strip trailing "- ..." then strip trailing confidence "(0.xx)" if present.
                core = raw.split(" - ", 1)[0].strip()
                core = re.sub(r"\(\s*0\.\d+\s*\)\s*$", "", core).strip()
                comp = _normalize_component_name_for_reporting(core)
                if comp:
                    items.append(
                        CandidateItem(
                            technology=technology,
                            component=comp,
                            group="pruned_single_support",
                            transcript_path=transcript_path,
                            transcript_kind=transcript_kind,
                        )
                    )

    # consensus (optional comparison)
    if include_consensus:
        for rx in _CONSENSUS_PATTERNS:
            for m in rx.findall(text):
                comp = _normalize_component_name_for_reporting(m)
                if comp:
                    items.append(
                        CandidateItem(
                            technology=technology,
                            component=comp,
                            group="consensus_kept",
                            transcript_path=transcript_path,
                            transcript_kind=transcript_kind,
                        )
                    )

    # de-dup within transcript (technology+component+group)
    seen: set[tuple[str, str, str]] = set()
    deduped: list[CandidateItem] = []
    for it in items:
        k = (it.technology, it.component, it.group)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(it)
    return deduped


def detect_technology_from_filename(path: Path) -> str:
    """
    Infer technology name from transcript filename.

    Many transcript filenames follow the pattern:
      <Technology>_<YYYYMMDD_HHMMSS>.json
    with spaces replaced by underscores.
    """
    stem = path.stem
    # strip trailing timestamp if present: _YYYYMMDD_HHMMSS
    stem = re.sub(r"_\d{8}_\d{6}$", "", stem)
    # undo underscores to spaces (best effort)
    tech = stem.replace("_", " ").strip()
    return tech


def load_transcript_text(path: Path) -> str:
    if path.suffix.lower() == ".json":
        obj = json.loads(path.read_text(encoding="utf-8"))
        return _extract_text_from_transcript_json(obj)
    else:
        return path.read_text(encoding="utf-8", errors="replace")


def iter_transcript_files(transcripts_dir: Path) -> Iterable[Path]:
    # Prefer JSON but include TXT; both can exist.
    # We'll parse both (dedup later).
    for ext in ("*.json", "*.txt"):
        for p in sorted(transcripts_dir.glob(ext)):
            yield p


# -----------------------------
# Judge prompt / agent
# -----------------------------


def build_judge_prompt(technology: str, component: str) -> str:
    return (
        "You are a strict auditor of supply-chain decomposition.\n\n"
        "Your task is to identify PRIMARY MANUFACTURING COMPONENTS for the SPECIFIED technology product.\n\n"
        "PRIMARY COMPONENTS are major subassemblies or modules that:\n"
        "- Are procured or manufactured separately\n"
        "- Have distinct supply chains\n"
        "- Form the core functional or structural architecture\n"
        "- Are typically purchased as complete units\n\n"
        "INCLUDE:\n"
        "- Major functional modules (e.g., display, battery, processor)\n"
        "- Structural assemblies (e.g., chassis, enclosure)\n"
        "- Key subassemblies with separate suppliers\n"
        "- Electronic boards and subsystems\n\n"
        "EXCLUDE:\n"
        "- Raw materials (metals, plastics, chemicals) - these are inputs TO components\n"
        "- Manufacturing tools and equipment\n"
        "- Consumables (adhesives, fasteners, solvents, lubricants)\n"
        "- Generic supplies and packaging materials\n\n"
        "Decision rule:\n"
        "- Answer YES only if the item is clearly a major subassembly/module that fits the PRIMARY COMPONENT definition.\n"
        "- If the item is minor, a small part (e.g., tray, bracket), an internal part of a larger module, ambiguous, "
        "or could be considered a consumable/material/tool, answer NO.\n\n"
        f"Technology: {technology}\n"
        f"Candidate component: {component}\n\n"
        "Return your decision with a short rationale.\n"
    )


def make_judge_agent(judge_model: str, retries: int) -> Agent[Any, JudgeVerdict]:
    return Agent(
        model=judge_model,
        output_type=JudgeVerdict,
        system_prompt=(
            "You are an expert supply-chain analyst.\n"
            "You apply a strict definition of PRIMARY MANUFACTURING COMPONENTS (major subassemblies/modules).\n"
            "You must be conservative: if an item is not clearly a primary subassembly/module, mark it NOT plausible.\n"
            "You must produce outputs that strictly conform to the requested schema."
        ),
        retries=retries,
        output_retries=retries,
    )


# -----------------------------
# Report generation
# -----------------------------


def format_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def write_markdown_report(
    out_path: Path,
    judged: list[JudgedItem],
    title: str,
    notes: list[str],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # group by group name and overall stats
    by_group: dict[str, list[JudgedItem]] = {}
    for j in judged:
        by_group.setdefault(j.group, []).append(j)

    # also group by (group, technology) so we can compare configurations
    by_group_tech: dict[tuple[str, str], list[JudgedItem]] = {}
    for j in judged:
        by_group_tech.setdefault((j.group, j.technology), []).append(j)

    # and group by (group, configuration tag) across technologies, e.g. v1v1v1 vs d3v1v1 vs d5v1v1
    def configuration_from_technology_label(technology: str) -> str:
        t = (technology or "").strip()
        m = re.search(r"(?:^|\s)(v\d+v\d+v\d+|d\d+v\d+v\d+)(?:$|\s)", t)
        return m.group(1) if m else "unknown"

    by_group_cfg: dict[tuple[str, str], list[JudgedItem]] = {}
    for j in judged:
        cfg = configuration_from_technology_label(j.technology)
        by_group_cfg.setdefault((j.group, cfg), []).append(j)

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    if judged:
        lines.append(f"- Judge model: `{judged[0].judge_model}`")
    lines.append(f"- Items judged: {len(judged)}")
    lines.append("")
    lines.append("## Notes")
    for n in notes:
        lines.append(f"- {n}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Group | Items | Plausible primary | Not plausible | Mean judge confidence |")
    lines.append("|---|---:|---:|---:|---:|")
    for group, items in sorted(by_group.items(), key=lambda kv: kv[0]):
        yes = sum(1 for it in items if it.verdict.plausible_primary_component)
        no = len(items) - yes
        mean_conf = sum(it.verdict.confidence for it in items) / max(1, len(items))
        lines.append(f"| `{group}` | {len(items)} | {yes} | {no} | {mean_conf:.2f} |")
    lines.append("")

    lines.append("## Per-technology summary (technology-by-configuration)")
    lines.append("")
    lines.append(
        "Each row summarizes judge outcomes for a specific `(group, technology)` pair (where `technology` includes the configuration tag)."
    )
    lines.append("")
    lines.append(
        "| Group | Technology | Items | Plausible primary | Not plausible | Not-plausible rate | Mean judge confidence |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|")

    def _sort_key(kv: tuple[tuple[str, str], list[JudgedItem]]) -> tuple[str, str]:
        (group, tech), _items = kv
        return (group, tech)

    for (group, tech), items in sorted(by_group_tech.items(), key=_sort_key):
        yes = sum(1 for it in items if it.verdict.plausible_primary_component)
        no = len(items) - yes
        mean_conf = sum(it.verdict.confidence for it in items) / max(1, len(items))
        no_rate = (no / len(items)) if items else 0.0
        lines.append(
            f"| `{group}` | {tech.replace('|', '\\\\|')} | {len(items)} | {yes} | {no} | {format_pct(no_rate)} | {mean_conf:.2f} |"
        )

    lines.append("")
    lines.append("## Per-configuration averages (across all technologies)")
    lines.append("")
    lines.append(
        "This table aggregates all judged items by configuration tag (e.g. `v1v1v1`, `d3v1v1`, `d5v1v1`) across all technologies."
    )
    lines.append("")
    lines.append(
        "| Group | Configuration | Items | Plausible primary | Not plausible | Not-plausible rate | Mean judge confidence |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for (group, cfg), items in sorted(by_group_cfg.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        yes = sum(1 for it in items if it.verdict.plausible_primary_component)
        no = len(items) - yes
        mean_conf = sum(it.verdict.confidence for it in items) / max(1, len(items))
        no_rate = (no / len(items)) if items else 0.0
        lines.append(
            f"| `{group}` | `{cfg}` | {len(items)} | {yes} | {no} | {format_pct(no_rate)} | {mean_conf:.2f} |"
        )

    lines.append("")
    lines.append("## Detailed results")
    lines.append("")
    lines.append(
        "Each row is a (technology, component) candidate extracted from system-generated agreement-based feedback "
        "and judged for plausibility as a primary manufacturing component."
    )
    lines.append("")
    lines.append(
        "| Technology | Component | Group | Verdict | Judge conf | Rationale | Transcript |"
    )
    lines.append("|---|---|---|---|---:|---|---|")

    def verdict_str(v: JudgeVerdict) -> str:
        return "YES" if v.plausible_primary_component else "NO"

    # Sort: pruned first, then by tech, then by component
    sort_key = lambda it: (
        0 if it.group == "pruned_single_support" else 1,
        it.technology,
        it.component,
    )
    for it in sorted(judged, key=sort_key):
        tech = it.technology.replace("|", "\\|")
        comp = it.component.replace("|", "\\|")
        group = f"`{it.group}`"
        v = verdict_str(it.verdict)
        conf = f"{it.verdict.confidence:.2f}"
        rat = it.verdict.rationale.replace("\n", " ").replace("|", "\\|").strip()
        tr = Path(it.transcript_path).name
        lines.append(f"| {tech} | {comp} | {group} | {v} | {conf} | {rat} | {tr} |")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_jsonl(out_path: Path, judged: list[JudgedItem]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for it in judged:
            rec = {
                "technology": it.technology,
                "component": it.component,
                "group": it.group,
                "transcript_path": it.transcript_path,
                "transcript_kind": it.transcript_kind,
                "judge_model": it.judge_model,
                "verdict": it.verdict.model_dump(),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# -----------------------------
# CLI
# -----------------------------


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Verify pruned single-support components via an LLM judge and write a markdown report."
    )
    p.add_argument(
        "--transcripts-dir",
        required=True,
        help="Directory containing debate transcripts (JSON/TXT). Example: src/stdn_agentic/debate_transcripts/results",
    )
    p.add_argument(
        "--technologies",
        nargs="*",
        default=None,
        help=(
            "Optional list of technology names to include. If omitted, all technologies found in transcripts are used."
        ),
    )
    p.add_argument(
        "--filename-include",
        nargs="*",
        default=None,
        help=(
            "Optional list of case-insensitive substrings. If provided, only transcripts whose filename contains "
            "ANY of these substrings are considered (useful to restrict to specific run configs, e.g. v1v1v1)."
        ),
    )
    p.add_argument(
        "--filename-exclude",
        nargs="*",
        default=None,
        help=(
            "Optional list of case-insensitive substrings. If provided, transcripts whose filename contains "
            "ANY of these substrings are skipped."
        ),
    )
    p.add_argument(
        "--include-consensus",
        action="store_true",
        help="Also judge consensus/kept items as a comparison group (increases cost).",
    )
    p.add_argument(
        "--candidate-source",
        choices=["final", "pruned", "both"],
        default="pruned",
        help=(
            "Which candidates to judge. Use 'final' for final-only comparisons across configurations "
            "(e.g. v1v1v1 vs d3v1v1 vs d5v1v1)."
        ),
    )
    p.add_argument(
        "--judge-model",
        default="openai:gpt-4.1",
        help="Judge model identifier. Recommended: openai:gpt-4.1 (default).",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("STDN_AGENT_RETRIES", "5") or "5"),
        help="Agent retry count for the judge. Defaults to STDN_AGENT_RETRIES or 5.",
    )
    p.add_argument(
        "--max-items",
        type=int,
        default=50,
        help="Maximum number of candidate items to judge (after filtering/dedup).",
    )
    p.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle candidate items before selecting max-items (for sampling).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed used when --shuffle is enabled.",
    )
    p.add_argument(
        "--out-md",
        default="output/analysis/pruned_component_verification.md",
        help="Output Markdown report path.",
    )
    p.add_argument(
        "--out-jsonl",
        default=None,
        help="Optional output JSONL path containing raw judged items.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call the judge model; just list extracted candidates and exit.",
    )
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    transcripts_dir = Path(args.transcripts_dir)
    if not transcripts_dir.exists():
        print(f"ERROR: transcripts dir not found: {transcripts_dir}", file=sys.stderr)
        return 2

    tech_filter = (
        set(t.strip() for t in (args.technologies or []) if t.strip())
        if args.technologies
        else None
    )

    filename_include = [s.strip().lower() for s in (args.filename_include or []) if s.strip()]
    filename_exclude = [s.strip().lower() for s in (args.filename_exclude or []) if s.strip()]

    # Extract candidates
    candidates: list[CandidateItem] = []
    for p in iter_transcript_files(transcripts_dir):
        name_lc = p.name.lower()

        # Optional filename-based filtering (e.g., restrict to v1v1v1 transcripts only)
        if filename_include and not any(sub in name_lc for sub in filename_include):
            continue
        if filename_exclude and any(sub in name_lc for sub in filename_exclude):
            continue

        tech = detect_technology_from_filename(p)
        if tech_filter is not None and tech not in tech_filter:
            continue

        try:
            text = load_transcript_text(p)
        except Exception as e:
            print(f"WARNING: failed to read transcript {p}: {e}", file=sys.stderr)
            continue

        candidates.extend(
            extract_candidates_from_text(
                technology=tech,
                text=text,
                transcript_path=str(p),
                transcript_kind="json" if p.suffix.lower() == ".json" else "txt",
                include_consensus=bool(args.include_consensus),
                include_final_components=(args.candidate_source in ("final", "both")),
                include_pruned_single_support=(args.candidate_source in ("pruned", "both")),
            )
        )

    # Dedup globally (technology+component+group); keep first transcript reference
    seen: set[tuple[str, str, str]] = set()
    deduped: list[CandidateItem] = []
    for c in candidates:
        k = (c.technology, c.component, c.group)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(c)

    # Select which groups to keep based on candidate-source
    keep_groups: set[str] = set()
    if args.candidate_source in ("pruned", "both"):
        keep_groups.add("pruned_single_support")
    if args.candidate_source in ("final", "both"):
        keep_groups.add("final_components")
    if args.include_consensus:
        keep_groups.add("consensus_kept")
    deduped = [c for c in deduped if c.group in keep_groups]

    # Optional shuffle/sample
    if args.shuffle:
        import random

        random.seed(args.seed)
        random.shuffle(deduped)

    if args.max_items and len(deduped) > args.max_items:
        deduped = deduped[: args.max_items]

    if args.dry_run:
        print(f"Extracted {len(deduped)} candidate items (dry-run).")
        for i, c in enumerate(deduped, start=1):
            print(
                f"{i:03d} [{c.group}] {c.technology} :: {c.component}  ({Path(c.transcript_path).name})"
            )
        return 0

    # Judge
    judge = make_judge_agent(args.judge_model, retries=args.retries)
    judged: list[JudgedItem] = []

    for idx, c in enumerate(deduped, start=1):
        prompt = build_judge_prompt(c.technology, c.component)
        try:
            result = judge.run_sync(prompt)  # use sync wrapper for CLI simplicity
        except Exception as e:
            # Record failure as NOT plausible with low confidence, but keep evidence
            verdict = JudgeVerdict(
                plausible_primary_component=False,
                confidence=0.0,
                rationale=f"Judge call failed: {type(e).__name__}: {e}",
            )
            judged.append(
                JudgedItem(
                    technology=c.technology,
                    component=c.component,
                    group=c.group,
                    transcript_path=c.transcript_path,
                    transcript_kind=c.transcript_kind,
                    verdict=verdict,
                    judge_model=args.judge_model,
                )
            )
            print(
                f"[{idx}/{len(deduped)}] ERROR judging {c.technology} / {c.component}: {e}",
                file=sys.stderr,
            )
            continue

        verdict = result.output if hasattr(result, "output") else None
        if verdict is None:
            verdict = JudgeVerdict(
                plausible_primary_component=False,
                confidence=0.0,
                rationale="Judge returned no output.",
            )

        judged.append(
            JudgedItem(
                technology=c.technology,
                component=c.component,
                group=c.group,
                transcript_path=c.transcript_path,
                transcript_kind=c.transcript_kind,
                verdict=verdict,
                judge_model=args.judge_model,
            )
        )

        print(
            f"[{idx}/{len(deduped)}] {c.group} {c.technology} :: {c.component} -> "
            f"{'YES' if verdict.plausible_primary_component else 'NO'} (conf={verdict.confidence:.2f})"
        )

    # Write outputs
    notes = [
        "This report uses an LLM judge as a proxy; treat results as suggestive, not ground truth.",
        "Items were extracted from system-generated agreement-based feedback in debate transcripts.",
        "Candidate extraction is best-effort and transcript-format dependent.",
    ]
    title = "Pruned Component Verification Report"
    out_md = Path(args.out_md)
    write_markdown_report(out_md, judged, title=title, notes=notes)

    if args.out_jsonl:
        write_jsonl(Path(args.out_jsonl), judged)

    print(f"\nWrote report: {out_md}")
    if args.out_jsonl:
        print(f"Wrote JSONL: {args.out_jsonl}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
