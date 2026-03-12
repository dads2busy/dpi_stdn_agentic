#!/usr/bin/env python3
"""
Combined sweet-spot tradeoff analysis for Stage 1 component extraction.

This script joins five families of metrics by component agent-count N:
1) Stability: Stage 1 FINAL CONSENSUS component-set stability across runs (pairwise Jaccard)
2) Plausibility: LLM-judge not-plausible rate (from verify_pruned_components.py JSONL)
3) Silver recall proxy: canonical coverage of a per-technology "reference set" built from judged-plausible components
4) Convergence: round-level convergence extracted from transcripts (like analyze_convergence_by_agent_count.py)
5) Runtime: wall-clock runtime inferred from per-run log files (STDN Generation Started/Completed)

Plausibility (precision-proxy) reporting
----------------------------------------
We report TWO not-plausible rates:
- Occurrence-based: counts every judged JSONL row (so repeat appearances across runs count multiple times)
- Deduped-canonical: dedupes by (technology, config, canonical_component) before computing the rate

And we also report explicit precision proxies for each:
- precision_proxy_occurrence = 1 - not_plausible_rate_occurrence
- precision_proxy_dedup_canon = 1 - not_plausible_rate_dedup_canon

This helps distinguish:
- "how often the pipeline emits invalid items" (occurrence-based) vs
- "how dirty the unique component vocabulary is" (deduped)

Confidence intervals (bootstrap across technologies)
---------------------------------------------------
To quantify uncertainty in macro summaries, we optionally compute nonparametric bootstrap confidence
intervals across technologies for key macro-mean metrics by N. This treats technologies as the unit
of resampling (equal weight per technology) and is appropriate for small-n comparisons where
technology-to-technology variability dominates.

We also compute:
- bootstrap confidence intervals for differences vs a baseline (N=1), and
- bootstrap confidence intervals for macro-median differences vs N=1, plus a simple sign test
  (% technologies improved) for key per-technology deltas.

It produces:
- a per-N macro-summary table (macro-median and macro-mean across technologies)
- optional per-(tech,N) CSV for downstream plotting
- optional by-N plotting CSV containing macro summary values + CI/delta fields (new)
- optional "recommended N" under simple constraint + knee heuristics

Inputs (defaults are set to current repo conventions):
- Transcripts: output/transcripts/*.txt (for stability + convergence)
- Normalized outputs: output/normalized/stdns_output_<cfg>_<YYYYMMDD_HHMMSS>.csv (for produced canonical component sets)
- Canonical vocab: data/component_canonical_vocab.json (for canonical mapping)
- Judge JSONL: output/analysis/final_only_component_verification_ALL_by_config.jsonl (for plausibility + silver reference)
- Logs: output/logs/*.log (for runtime)

Agent-count N mapping:
- v1v1v1 => N=1
- d2v1v1 => N=2
- d3v1v1 => N=3
- ...

Silver recall proxy definition (canonical, normalized-output based)
----------------------------------------------------------------
We treat `data/component_canonical_vocab.json` as a canonicalization mapping:
  input_string -> canonical_component_name

For each technology, we construct a silver "reference set" as the union of all components that were
judged plausible_primary_component==True anywhere in the judge JSONL (across configs/runs), after
canonicalization via the vocab:

  ReferencePlausibleCanonical(tech) = { canon(component) | judged_plausible(component, tech) }

For each (technology, config/N), we construct the produced canonical set from normalized outputs
(deduping by (technology, component) and canonicalizing via the vocab):

  ProducedCanonical(tech, cfg) = { canon(component) | component appears in normalized stdns_output for (tech,cfg) }

Then:

  silver_recall_proxy = |ProducedCanonical(tech, cfg) ∩ ReferencePlausibleCanonical(tech)| / |ReferencePlausibleCanonical(tech)|

This is not ground-truth recall; it is "coverage of the plausible component space discovered (and judged plausible)
across the experiment suite", expressed on canonical names.

Notes / caveats:
- "Not-plausible" here is LLM-as-judge proxy, not ground truth.
- The silver recall proxy is conditioned on what was judged at all; it will be biased by sampling/judge coverage.
- Canonical mapping depends on vocab coverage; unmapped components are excluded from canonical-set coverage.
- Runtime is per config-run log file (e.g. d2v1v1_run1.log). It is NOT per technology.
  We attach the same runtime to all technologies of that (config, run) when aggregating to (tech,N),
  and then macro-reduce across techs. This is good enough for sweet-spot comparisons by N
  when runtime is dominated by agent-count rather than technology choice.
- Convergence is extracted from transcripts; some transcripts may not contain convergence lines.
  Those are excluded from convergence aggregates by default (configurable).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Optional

# -----------------------------
# Shared parsing utilities
# -----------------------------

# Config tag token: 3 tokens, each token is [vd][1-2 digits], concatenated.
_RX_CFG_TOKEN = re.compile(r"(?:^|[_\s])((?:[vd]\d{1,2}){3})(?:$|[_\s])", re.IGNORECASE)

# Timestamp suffix in filenames
_RX_TIMESTAMP_SUFFIX = re.compile(r"_\d{8}_\d{6}$")

# Convergence patterns in transcripts (same as analyze_convergence_by_agent_count.py)
_RX_CONV = re.compile(r"Convergence[:\s]+(\d+(?:\.\d+)?)%?", re.IGNORECASE)

# Runtime markers in logs (observed in output/logs/*.log)
_RX_STARTED = re.compile(r"STDN Generation Started:\s*(.+)$", re.IGNORECASE)
_RX_COMPLETED = re.compile(r"STDN Generation Completed:\s*(.+)$", re.IGNORECASE)

# Datetime format in logs (example: 2026-02-12 13:12:56.174190)
_LOG_DT_FORMATS = [
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
]


def iter_files(dir_path: Path, glob_pat: str) -> Iterable[Path]:
    if not dir_path.exists():
        return []
    return sorted(dir_path.glob(glob_pat))


def parse_config_from_filename(path: Path) -> str:
    m = _RX_CFG_TOKEN.search(path.stem)
    return m.group(1).lower() if m else "unknown"


def parse_base_technology_from_filename(path: Path) -> str:
    """
    Convert a transcript filename stem into a base technology name by:
    - removing trailing timestamp
    - removing config tag token (if present)
    - converting underscores to spaces
    """
    stem = path.stem
    stem = _RX_TIMESTAMP_SUFFIX.sub("", stem)

    m = _RX_CFG_TOKEN.search(stem)
    if m:
        stem = (stem[: m.start(1)] + stem[m.end(1) :]).strip("_ ")

    stem = stem.replace("_", " ").strip()
    stem = re.sub(r"\s+", " ", stem)
    return stem


def component_agent_count_from_config_tag(cfg: str) -> Optional[int]:
    """
    Map a config tag to the number of component agents N.

    Conventions:
      - v1v1v1 => N=1
      - d2v1v1 => N=2
      - d3v1v1 => N=3
      - ...

    Only the first token encodes component-stage agent count.
    """
    cfg = (cfg or "").lower().strip()
    m = re.fullmatch(r"([vd])(\d{1,2})([vd]\d{1,2})([vd]\d{1,2})", cfg)
    if not m:
        return None
    prefix = m.group(1)
    n = int(m.group(2))
    if prefix not in ("v", "d"):
        return None
    return n


def safe_mean(xs: list[float]) -> Optional[float]:
    return mean(xs) if xs else None


def median(xs: list[float]) -> Optional[float]:
    if not xs:
        return None
    ys = sorted(xs)
    mid = len(ys) // 2
    if len(ys) % 2 == 1:
        return ys[mid]
    return (ys[mid - 1] + ys[mid]) / 2.0


def nearest_rank_percentile(xs_sorted: list[float], p: float) -> Optional[float]:
    """
    Simple nearest-rank percentile for small n.
    xs_sorted must be sorted ascending.
    p in [0,1].
    """
    if not xs_sorted:
        return None
    p = 0.0 if p < 0.0 else (1.0 if p > 1.0 else p)
    k = int((len(xs_sorted) - 1) * p + 0.5)
    return xs_sorted[k]


def bootstrap_mean_ci(
    values: list[float],
    *,
    iters: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[Optional[float], Optional[float]]:
    """
    Nonparametric bootstrap CI for the mean.

    Resamples `values` with replacement `iters` times and returns the
    (lower, upper) percentiles at alpha/2 and 1-alpha/2.

    Returns (None, None) if there is insufficient data.
    """
    if not values:
        return None, None
    if len(values) == 1:
        # Degenerate CI; return the point value.
        return values[0], values[0]

    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(iters):
        sample = [values[rng.randrange(0, n)] for _ in range(n)]
        means.append(sum(sample) / n)

    means.sort()
    lo = nearest_rank_percentile(means, alpha / 2.0)
    hi = nearest_rank_percentile(means, 1.0 - alpha / 2.0)
    return lo, hi


def bootstrap_median_ci(
    values: list[float],
    *,
    iters: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[Optional[float], Optional[float]]:
    """
    Nonparametric bootstrap CI for the median.

    Returns (None, None) if there is insufficient data.
    """
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]

    rng = random.Random(seed)
    n = len(values)
    meds: list[float] = []
    for _ in range(iters):
        sample = [values[rng.randrange(0, n)] for _ in range(n)]
        m = median(sample)
        if m is not None:
            meds.append(m)

    if not meds:
        return None, None
    meds.sort()
    lo = nearest_rank_percentile(meds, alpha / 2.0)
    hi = nearest_rank_percentile(meds, 1.0 - alpha / 2.0)
    return lo, hi


def bootstrap_median_diff_ci(
    a: list[float],
    b: list[float],
    *,
    iters: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[Optional[float], Optional[float]]:
    """
    Bootstrap CI for difference in medians: median(a) - median(b), resampling technologies.

    Uses paired bootstrap resampling when lengths match; otherwise falls back to independent bootstrap.
    """
    if not a or not b:
        return None, None

    rng = random.Random(seed)

    if len(a) == len(b):
        n = len(a)
        diffs: list[float] = []
        for _ in range(iters):
            idxs = [rng.randrange(0, n) for _ in range(n)]
            sa = [a[i] for i in idxs]
            sb = [b[i] for i in idxs]
            ma = median(sa)
            mb = median(sb)
            if ma is None or mb is None:
                continue
            diffs.append(ma - mb)
        if not diffs:
            return None, None
        diffs.sort()
        lo = nearest_rank_percentile(diffs, alpha / 2.0)
        hi = nearest_rank_percentile(diffs, 1.0 - alpha / 2.0)
        return lo, hi

    # Independent fallback
    lo_a, hi_a = bootstrap_median_ci(a, iters=iters, alpha=alpha, seed=seed + 23)
    lo_b, hi_b = bootstrap_median_ci(b, iters=iters, alpha=alpha, seed=seed + 29)
    if lo_a is None or hi_a is None or lo_b is None or hi_b is None:
        return None, None
    return lo_a - hi_b, hi_a - lo_b


def bootstrap_mean_diff_ci(
    a: list[float],
    b: list[float],
    *,
    iters: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[Optional[float], Optional[float]]:
    """
    Bootstrap CI for difference in means: mean(a) - mean(b), resampling technologies.

    This uses *paired* bootstrap resampling when lengths match (treating indices as technologies).
    If lengths differ, falls back to independent bootstrap over each list.
    """
    if not a or not b:
        return None, None

    rng = random.Random(seed)

    if len(a) == len(b):
        n = len(a)
        diffs: list[float] = []
        for _ in range(iters):
            idxs = [rng.randrange(0, n) for _ in range(n)]
            ma = sum(a[i] for i in idxs) / n
            mb = sum(b[i] for i in idxs) / n
            diffs.append(ma - mb)
        diffs.sort()
        lo = nearest_rank_percentile(diffs, alpha / 2.0)
        hi = nearest_rank_percentile(diffs, 1.0 - alpha / 2.0)
        return lo, hi

    # Independent fallback
    lo_a, hi_a = bootstrap_mean_ci(a, iters=iters, alpha=alpha, seed=seed + 11)
    lo_b, hi_b = bootstrap_mean_ci(b, iters=iters, alpha=alpha, seed=seed + 17)
    if lo_a is None or hi_a is None or lo_b is None or hi_b is None:
        return None, None
    return lo_a - hi_b, hi_a - lo_b


def fmt_opt(x: Optional[float], digits: int = 3) -> str:
    if x is None:
        return "NA"
    return f"{x:.{digits}f}"


def normalize_component_name_for_matching(name: str) -> str:
    """
    Normalize a raw component string into a key suitable for lookup in the canonical vocab mappings.

    We keep this conservative:
    - lowercase
    - trim
    - collapse whitespace
    - strip trailing parenthetical numeric confidence like "(1.00)" when present
    """
    s = (name or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*\(\s*\d+(?:\.\d+)?\s*\)\s*$", "", s).strip()
    return s


def load_component_canonical_vocab(vocab_path: Path) -> dict[str, str]:
    """
    Load data/component_canonical_vocab.json and return its `mappings` dict:
      normalized_input_string -> canonical_component_name

    Empty-string mappings are treated as "unmapped" and excluded by callers.
    """
    obj = json.loads(vocab_path.read_text(encoding="utf-8", errors="replace"))
    mappings = obj.get("mappings", {})
    if not isinstance(mappings, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in mappings.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        out[normalize_component_name_for_matching(k)] = v.strip()
    return out


def canonicalize_component(name: str, vocab: dict[str, str]) -> Optional[str]:
    """
    Canonicalize a component name using the vocab mappings.
    Returns canonical name, or None if unmapped/empty.
    """
    key = normalize_component_name_for_matching(name)
    if not key:
        return None
    canon = vocab.get(key)
    if canon is None:
        return None
    canon = canon.strip()
    if not canon:
        return None
    return canon


# -----------------------------
# Stability (Stage 1 final components)
# -----------------------------

_RX_STAGE1_HEADER = re.compile(r"^STAGE 1:\s*COMPONENT EXTRACTION\s*$", re.IGNORECASE)
_RX_STAGE1_END = re.compile(
    r"^END OF COMPONENT EXTRACTION\s*$|^END OF COMPONENTS EXTRACTION\s*$", re.IGNORECASE
)
_RX_FINAL_HEADER = re.compile(r"^FINAL CONSENSUS:\s*Component(?:s)?\s*$", re.IGNORECASE)
_RX_NUM_ITEM = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_RX_NUM_ITEM_BULLET = re.compile(r"^\s*[-*•]\s+(.+?)\s*$")


def extract_stage1_final_components(transcript_text: str) -> set[str]:
    """
    Extract the Stage 1 FINAL CONSENSUS: Components numbered list as a set of component strings.
    """
    lines = transcript_text.splitlines()

    # Bound to Stage 1 block if possible
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    for idx, line in enumerate(lines):
        s = line.strip()
        if start_idx is None and _RX_STAGE1_HEADER.match(s):
            start_idx = idx
            continue
        if start_idx is not None and _RX_STAGE1_END.match(s):
            end_idx = idx
            break

    if start_idx is not None:
        lines = lines[start_idx : (end_idx if end_idx is not None else len(lines))]

    in_final = False
    comps: list[str] = []

    for line in lines:
        s = line.strip()

        if _RX_FINAL_HEADER.match(s):
            in_final = True
            continue

        if not in_final:
            continue

        # Skip blank lines / metadata lines commonly present in the final block
        if not s:
            continue
        if any(
            s.lower().startswith(prefix)
            for prefix in (
                "rounds completed:",
                "final convergence:",
                "components selected:",
            )
        ):
            continue

        # Stop on explicit section boundaries.
        if s.upper().startswith("END OF") or s.upper().startswith("STAGE "):
            break

        m = _RX_NUM_ITEM.match(line) or _RX_NUM_ITEM_BULLET.match(line)
        if m:
            comp = m.group(1).strip()
            if comp:
                comps.append(comp)

    return set(comps)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def pairwise_jaccards(sets: list[set[str]]) -> list[float]:
    scores: list[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            scores.append(jaccard(sets[i], sets[j]))
    return scores


def stability_mean_pairwise_jaccard(run_sets: list[set[str]]) -> Optional[float]:
    if len(run_sets) < 2:
        return None
    scores = pairwise_jaccards(run_sets)
    return safe_mean(scores)


# -----------------------------
# Convergence (from transcripts)
# -----------------------------


def parse_rounds_best_effort(text: str) -> int:
    m = re.search(r"Rounds Completed:\s*(\d+)", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return 0

    round_nums = re.findall(r"\bROUND\s+(\d+)\b", text, flags=re.IGNORECASE)
    if not round_nums:
        return 0
    try:
        return max(int(x) for x in round_nums)
    except ValueError:
        return 0


def parse_convergence_scores(text: str) -> list[float]:
    scores: list[float] = []
    for raw in _RX_CONV.findall(text):
        try:
            v = float(raw)
        except ValueError:
            continue
        if v > 1.0:
            v = v / 100.0
        if v < 0.0:
            v = 0.0
        if v > 1.0:
            v = 1.0
        scores.append(v)
    return scores


# -----------------------------
# Plausibility (judge JSONL)
# -----------------------------


def parse_technology_and_config_from_judge_label(label: str) -> tuple[str, str]:
    """
    Judge JSONL uses technology field like:
      "Autoclave (Steam Sterilizer) d2v1v1"
    i.e., base technology name + space + config tag.
    """
    s = (label or "").strip()
    m = _RX_CFG_TOKEN.search(s)
    if not m:
        return s, "unknown"
    cfg = m.group(1).lower()
    tech = (s[: m.start(1)] + s[m.end(1) :]).strip()
    tech = re.sub(r"\s+", " ", tech)
    return tech, cfg


def load_judge_jsonl(jsonl_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def extract_plausible_component_from_judge_row(
    row: dict[str, Any],
) -> Optional[tuple[str, str, str, bool]]:
    """
    Extract (technology, config, raw_component_string, plausible_bool) from a judge JSONL row.
    Supports two schemas:
    - verify_pruned_components.py: {technology: "<tech> <cfg>", component, verdict:{plausible_primary_component: bool}}
    - judge_stage1_components_from_normalized_outputs.py: {technology, component, plausible: bool}
    """
    label = row.get("technology", "")
    tech, cfg = parse_technology_and_config_from_judge_label(str(label))
    if cfg == "unknown":
        cfg = str(row.get("config", "unknown") or "unknown").strip().lower()

    if "plausible" in row:
        plausible = row.get("plausible", None)
    else:
        verdict = (row.get("verdict") or {}) if isinstance(row.get("verdict"), dict) else {}
        plausible = verdict.get("plausible_primary_component", None)

    comp_raw = row.get("component", None)
    if plausible is None or comp_raw is None:
        return None
    comp_raw_s = str(comp_raw).strip()
    if not comp_raw_s:
        return None
    return tech, cfg.lower(), comp_raw_s, bool(plausible)


# -----------------------------
# Runtime (from logs)
# -----------------------------


def parse_log_datetime(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    for fmt in _LOG_DT_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def parse_runtime_seconds_from_log_text(text: str) -> Optional[float]:
    """
    Parse wall-clock runtime in seconds from a run log containing:
      STDN Generation Started: <datetime>
      STDN Generation Completed: <datetime>
    """
    started: Optional[datetime] = None
    completed: Optional[datetime] = None
    for line in text.splitlines():
        m1 = _RX_STARTED.search(line)
        if m1:
            started = parse_log_datetime(m1.group(1))
        m2 = _RX_COMPLETED.search(line)
        if m2:
            completed = parse_log_datetime(m2.group(1))
    if not started or not completed:
        return None
    delta = completed - started
    return max(0.0, delta.total_seconds())


def parse_config_from_log_filename(path: Path) -> str:
    """
    Log filenames look like:
      d2v1v1_run1.log
      v1v1v1_run10.log
    """
    name = path.stem
    # config is before "_run"
    m = re.match(r"^([a-z0-9]+)_run\d+$", name, flags=re.IGNORECASE)
    if not m:
        return "unknown"
    return m.group(1).lower()


# -----------------------------
# Data structures + aggregation
# -----------------------------


@dataclass(frozen=True)
class TechNRow:
    technology: str
    config: str
    n: int

    # Stability
    stability_mean_jaccard: Optional[float]

    # Plausibility (precision proxies)
    # - occurrence-based: counts every judged row (repeats across runs count multiple times)
    # - deduped-canonical: dedupes by canonical component within (technology, config)
    not_plausible_rate_occurrence: Optional[float]  # fraction in [0,1]
    not_plausible_rate_dedup_canon: Optional[float]  # fraction in [0,1]

    # Explicit precision proxies (1 - not-plausible)
    precision_proxy_occurrence: Optional[float]  # fraction in [0,1]
    precision_proxy_dedup_canon: Optional[float]  # fraction in [0,1]

    # Produced component count control (canonical, per-run median across runs for this tech/config)
    produced_components_median: Optional[float]

    # Silver recall proxy (coverage of plausible reference set)
    silver_recall_proxy: Optional[float]  # fraction in [0,1]

    # Convergence
    final_convergence_mean: Optional[float]
    rounds_mean: Optional[float]

    # Runtime (seconds)
    runtime_seconds: Optional[float]


@dataclass(frozen=True)
class MacroSummaryRow:
    n: int
    technologies: int

    stability_median: Optional[float]
    stability_mean: Optional[float]
    stability_mean_ci_lo: Optional[float]
    stability_mean_ci_hi: Optional[float]
    stability_mean_diff_vs_n1_ci_lo: Optional[float]
    stability_mean_diff_vs_n1_ci_hi: Optional[float]
    stability_median_diff_vs_n1_ci_lo: Optional[float]
    stability_median_diff_vs_n1_ci_hi: Optional[float]

    not_plausible_occ_median: Optional[float]
    not_plausible_occ_mean: Optional[float]
    not_plausible_occ_mean_ci_lo: Optional[float]
    not_plausible_occ_mean_ci_hi: Optional[float]
    not_plausible_occ_mean_diff_vs_n1_ci_lo: Optional[float]
    not_plausible_occ_mean_diff_vs_n1_ci_hi: Optional[float]
    not_plausible_occ_median_diff_vs_n1_ci_lo: Optional[float]
    not_plausible_occ_median_diff_vs_n1_ci_hi: Optional[float]
    not_plausible_occ_pct_techs_improved_vs_n1: Optional[float]

    not_plausible_dedup_canon_median: Optional[float]
    not_plausible_dedup_canon_mean: Optional[float]
    not_plausible_dedup_canon_mean_ci_lo: Optional[float]
    not_plausible_dedup_canon_mean_ci_hi: Optional[float]
    not_plausible_dedup_canon_mean_diff_vs_n1_ci_lo: Optional[float]
    not_plausible_dedup_canon_mean_diff_vs_n1_ci_hi: Optional[float]
    not_plausible_dedup_canon_median_diff_vs_n1_ci_lo: Optional[float]
    not_plausible_dedup_canon_median_diff_vs_n1_ci_hi: Optional[float]
    not_plausible_dedup_canon_pct_techs_improved_vs_n1: Optional[float]

    produced_components_median: Optional[float]
    produced_components_mean: Optional[float]
    produced_components_mean_ci_lo: Optional[float]
    produced_components_mean_ci_hi: Optional[float]
    produced_components_mean_diff_vs_n1_ci_lo: Optional[float]
    produced_components_mean_diff_vs_n1_ci_hi: Optional[float]
    produced_components_median_diff_vs_n1_ci_lo: Optional[float]
    produced_components_median_diff_vs_n1_ci_hi: Optional[float]

    silver_recall_median: Optional[float]
    silver_recall_mean: Optional[float]
    silver_recall_mean_ci_lo: Optional[float]
    silver_recall_mean_ci_hi: Optional[float]
    silver_recall_mean_diff_vs_n1_ci_lo: Optional[float]
    silver_recall_mean_diff_vs_n1_ci_hi: Optional[float]
    silver_recall_median_diff_vs_n1_ci_lo: Optional[float]
    silver_recall_median_diff_vs_n1_ci_hi: Optional[float]

    final_convergence_median: Optional[float]
    final_convergence_mean: Optional[float]
    final_convergence_mean_ci_lo: Optional[float]
    final_convergence_mean_ci_hi: Optional[float]
    final_convergence_mean_diff_vs_n1_ci_lo: Optional[float]
    final_convergence_mean_diff_vs_n1_ci_hi: Optional[float]
    final_convergence_median_diff_vs_n1_ci_lo: Optional[float]
    final_convergence_median_diff_vs_n1_ci_hi: Optional[float]

    rounds_median: Optional[float]
    rounds_mean: Optional[float]
    rounds_mean_ci_lo: Optional[float]
    rounds_mean_ci_hi: Optional[float]
    rounds_mean_diff_vs_n1_ci_lo: Optional[float]
    rounds_mean_diff_vs_n1_ci_hi: Optional[float]
    rounds_median_diff_vs_n1_ci_lo: Optional[float]
    rounds_median_diff_vs_n1_ci_hi: Optional[float]

    runtime_median_seconds: Optional[float]
    runtime_mean_seconds: Optional[float]
    runtime_mean_ci_lo: Optional[float]
    runtime_mean_ci_hi: Optional[float]
    runtime_mean_diff_vs_n1_ci_lo: Optional[float]
    runtime_mean_diff_vs_n1_ci_hi: Optional[float]
    runtime_median_diff_vs_n1_ci_lo: Optional[float]
    runtime_median_diff_vs_n1_ci_hi: Optional[float]


def macro_summarize(rows: list[TechNRow], n: int) -> MacroSummaryRow:
    rs = [r for r in rows if r.n == n]
    techs = sorted({r.technology for r in rs})

    stab = [r.stability_mean_jaccard for r in rs if r.stability_mean_jaccard is not None]
    np_occ = [
        r.not_plausible_rate_occurrence for r in rs if r.not_plausible_rate_occurrence is not None
    ]
    np_dedup = [
        r.not_plausible_rate_dedup_canon for r in rs if r.not_plausible_rate_dedup_canon is not None
    ]
    produced_k = [
        r.produced_components_median for r in rs if r.produced_components_median is not None
    ]
    silver_recall = [r.silver_recall_proxy for r in rs if r.silver_recall_proxy is not None]
    conv = [r.final_convergence_mean for r in rs if r.final_convergence_mean is not None]
    rounds = [r.rounds_mean for r in rs if r.rounds_mean is not None]
    runtime = [r.runtime_seconds for r in rs if r.runtime_seconds is not None]

    stab_ci_lo, stab_ci_hi = bootstrap_mean_ci(stab, seed=1000 + n)
    np_occ_ci_lo, np_occ_ci_hi = bootstrap_mean_ci(np_occ, seed=2000 + n)
    np_dedup_ci_lo, np_dedup_ci_hi = bootstrap_mean_ci(np_dedup, seed=3000 + n)
    produced_ci_lo, produced_ci_hi = bootstrap_mean_ci(produced_k, seed=4000 + n)
    silver_ci_lo, silver_ci_hi = bootstrap_mean_ci(silver_recall, seed=5000 + n)
    conv_ci_lo, conv_ci_hi = bootstrap_mean_ci(conv, seed=6000 + n)
    rounds_ci_lo, rounds_ci_hi = bootstrap_mean_ci(rounds, seed=7000 + n)
    runtime_ci_lo, runtime_ci_hi = bootstrap_mean_ci(runtime, seed=8000 + n)

    # Differences vs N=1 (computed in main, using paired bootstrap by technology)
    return MacroSummaryRow(
        n=n,
        technologies=len(techs),
        stability_median=median(stab),
        stability_mean=safe_mean(stab),
        stability_mean_ci_lo=stab_ci_lo,
        stability_mean_ci_hi=stab_ci_hi,
        stability_mean_diff_vs_n1_ci_lo=None,
        stability_mean_diff_vs_n1_ci_hi=None,
        stability_median_diff_vs_n1_ci_lo=None,
        stability_median_diff_vs_n1_ci_hi=None,
        not_plausible_occ_median=median(np_occ),
        not_plausible_occ_mean=safe_mean(np_occ),
        not_plausible_occ_mean_ci_lo=np_occ_ci_lo,
        not_plausible_occ_mean_ci_hi=np_occ_ci_hi,
        not_plausible_occ_mean_diff_vs_n1_ci_lo=None,
        not_plausible_occ_mean_diff_vs_n1_ci_hi=None,
        not_plausible_occ_median_diff_vs_n1_ci_lo=None,
        not_plausible_occ_median_diff_vs_n1_ci_hi=None,
        not_plausible_occ_pct_techs_improved_vs_n1=None,
        not_plausible_dedup_canon_median=median(np_dedup),
        not_plausible_dedup_canon_mean=safe_mean(np_dedup),
        not_plausible_dedup_canon_mean_ci_lo=np_dedup_ci_lo,
        not_plausible_dedup_canon_mean_ci_hi=np_dedup_ci_hi,
        not_plausible_dedup_canon_mean_diff_vs_n1_ci_lo=None,
        not_plausible_dedup_canon_mean_diff_vs_n1_ci_hi=None,
        not_plausible_dedup_canon_median_diff_vs_n1_ci_lo=None,
        not_plausible_dedup_canon_median_diff_vs_n1_ci_hi=None,
        not_plausible_dedup_canon_pct_techs_improved_vs_n1=None,
        produced_components_median=median(produced_k),
        produced_components_mean=safe_mean(produced_k),
        produced_components_mean_ci_lo=produced_ci_lo,
        produced_components_mean_ci_hi=produced_ci_hi,
        produced_components_mean_diff_vs_n1_ci_lo=None,
        produced_components_mean_diff_vs_n1_ci_hi=None,
        produced_components_median_diff_vs_n1_ci_lo=None,
        produced_components_median_diff_vs_n1_ci_hi=None,
        silver_recall_median=median(silver_recall),
        silver_recall_mean=safe_mean(silver_recall),
        silver_recall_mean_ci_lo=silver_ci_lo,
        silver_recall_mean_ci_hi=silver_ci_hi,
        silver_recall_mean_diff_vs_n1_ci_lo=None,
        silver_recall_mean_diff_vs_n1_ci_hi=None,
        silver_recall_median_diff_vs_n1_ci_lo=None,
        silver_recall_median_diff_vs_n1_ci_hi=None,
        final_convergence_median=median(conv),
        final_convergence_mean=safe_mean(conv),
        final_convergence_mean_ci_lo=conv_ci_lo,
        final_convergence_mean_ci_hi=conv_ci_hi,
        final_convergence_mean_diff_vs_n1_ci_lo=None,
        final_convergence_mean_diff_vs_n1_ci_hi=None,
        final_convergence_median_diff_vs_n1_ci_lo=None,
        final_convergence_median_diff_vs_n1_ci_hi=None,
        rounds_median=median(rounds),
        rounds_mean=safe_mean(rounds),
        rounds_mean_ci_lo=rounds_ci_lo,
        rounds_mean_ci_hi=rounds_ci_hi,
        rounds_mean_diff_vs_n1_ci_lo=None,
        rounds_mean_diff_vs_n1_ci_hi=None,
        rounds_median_diff_vs_n1_ci_lo=None,
        rounds_median_diff_vs_n1_ci_hi=None,
        runtime_median_seconds=median(runtime),
        runtime_mean_seconds=safe_mean(runtime),
        runtime_mean_ci_lo=runtime_ci_lo,
        runtime_mean_ci_hi=runtime_ci_hi,
        runtime_mean_diff_vs_n1_ci_lo=None,
        runtime_mean_diff_vs_n1_ci_hi=None,
        runtime_median_diff_vs_n1_ci_lo=None,
        runtime_median_diff_vs_n1_ci_hi=None,
    )


def fmt_seconds(sec: Optional[float]) -> str:
    if sec is None:
        return "NA"
    # prefer minutes with 1 decimal when large
    if sec >= 120:
        return f"{sec / 60.0:.1f}m"
    return f"{sec:.0f}s"


def render_macro_md_table(summaries: list[MacroSummaryRow]) -> str:
    lines: list[str] = []
    lines.append("# Sweet-spot tradeoff summary (Stage 1)")
    lines.append("")
    lines.append(
        "Macro-summary across technologies (equal weight; values are macro-median and macro-mean across (tech,N))."
    )
    lines.append("")
    lines.append(
        "| N | Techs | Stability (median) | Stability (mean) | Stability mean 95% CI | Δ Stability mean vs N=1 (95% CI) | Δ Stability median vs N=1 (95% CI) | Not-plausible occ (median) | Not-plausible occ (mean) | Not-plausible occ mean 95% CI | Δ Not-plausible occ mean vs N=1 (95% CI) | Δ Not-plausible occ median vs N=1 (95% CI) | % techs improved (occ invalid) | Precision occ (median) | Precision occ (mean) | Not-plausible dedup-canon (median) | Not-plausible dedup-canon (mean) | Not-plausible dedup-canon mean 95% CI | Δ Not-plausible dedup-canon mean vs N=1 (95% CI) | Δ Not-plausible dedup-canon median vs N=1 (95% CI) | % techs improved (dedup invalid) | Precision dedup-canon (median) | Precision dedup-canon (mean) | #Components (median) | #Components (mean) | #Components mean 95% CI | Δ #Components mean vs N=1 (95% CI) | Δ #Components median vs N=1 (95% CI) | Silver recall (median) | Silver recall (mean) | Silver recall mean 95% CI | Δ Silver recall mean vs N=1 (95% CI) | Δ Silver recall median vs N=1 (95% CI) | Final conv (median) | Final conv (mean) | Final conv mean 95% CI | Δ Final conv mean vs N=1 (95% CI) | Δ Final conv median vs N=1 (95% CI) | Rounds (median) | Rounds (mean) | Rounds mean 95% CI | Δ Rounds mean vs N=1 (95% CI) | Δ Rounds median vs N=1 (95% CI) | Runtime (median) | Runtime (mean) | Runtime mean 95% CI | Δ Runtime mean vs N=1 (95% CI) | Δ Runtime median vs N=1 (95% CI) |"
    )
    lines.append(
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )

    for s in summaries:
        stability_ci = (
            "NA"
            if s.stability_mean_ci_lo is None or s.stability_mean_ci_hi is None
            else f"[{s.stability_mean_ci_lo:.3f}, {s.stability_mean_ci_hi:.3f}]"
        )
        stability_diff_ci = (
            "NA"
            if s.stability_mean_diff_vs_n1_ci_lo is None
            or s.stability_mean_diff_vs_n1_ci_hi is None
            else f"[{s.stability_mean_diff_vs_n1_ci_lo:.3f}, {s.stability_mean_diff_vs_n1_ci_hi:.3f}]"
        )
        stability_median_diff_ci = (
            "NA"
            if s.stability_median_diff_vs_n1_ci_lo is None
            or s.stability_median_diff_vs_n1_ci_hi is None
            else f"[{s.stability_median_diff_vs_n1_ci_lo:.3f}, {s.stability_median_diff_vs_n1_ci_hi:.3f}]"
        )

        np_occ_ci = (
            "NA"
            if s.not_plausible_occ_mean_ci_lo is None or s.not_plausible_occ_mean_ci_hi is None
            else f"[{s.not_plausible_occ_mean_ci_lo:.3f}, {s.not_plausible_occ_mean_ci_hi:.3f}]"
        )
        np_occ_diff_ci = (
            "NA"
            if s.not_plausible_occ_mean_diff_vs_n1_ci_lo is None
            or s.not_plausible_occ_mean_diff_vs_n1_ci_hi is None
            else f"[{s.not_plausible_occ_mean_diff_vs_n1_ci_lo:.3f}, {s.not_plausible_occ_mean_diff_vs_n1_ci_hi:.3f}]"
        )
        np_occ_median_diff_ci = (
            "NA"
            if s.not_plausible_occ_median_diff_vs_n1_ci_lo is None
            or s.not_plausible_occ_median_diff_vs_n1_ci_hi is None
            else f"[{s.not_plausible_occ_median_diff_vs_n1_ci_lo:.3f}, {s.not_plausible_occ_median_diff_vs_n1_ci_hi:.3f}]"
        )
        np_occ_pct_improved = (
            "NA"
            if s.not_plausible_occ_pct_techs_improved_vs_n1 is None
            else f"{s.not_plausible_occ_pct_techs_improved_vs_n1:.1f}%"
        )

        np_dedup_ci = (
            "NA"
            if s.not_plausible_dedup_canon_mean_ci_lo is None
            or s.not_plausible_dedup_canon_mean_ci_hi is None
            else f"[{s.not_plausible_dedup_canon_mean_ci_lo:.3f}, {s.not_plausible_dedup_canon_mean_ci_hi:.3f}]"
        )
        np_dedup_diff_ci = (
            "NA"
            if s.not_plausible_dedup_canon_mean_diff_vs_n1_ci_lo is None
            or s.not_plausible_dedup_canon_mean_diff_vs_n1_ci_hi is None
            else f"[{s.not_plausible_dedup_canon_mean_diff_vs_n1_ci_lo:.3f}, {s.not_plausible_dedup_canon_mean_diff_vs_n1_ci_hi:.3f}]"
        )
        np_dedup_median_diff_ci = (
            "NA"
            if s.not_plausible_dedup_canon_median_diff_vs_n1_ci_lo is None
            or s.not_plausible_dedup_canon_median_diff_vs_n1_ci_hi is None
            else f"[{s.not_plausible_dedup_canon_median_diff_vs_n1_ci_lo:.3f}, {s.not_plausible_dedup_canon_median_diff_vs_n1_ci_hi:.3f}]"
        )
        np_dedup_pct_improved = (
            "NA"
            if s.not_plausible_dedup_canon_pct_techs_improved_vs_n1 is None
            else f"{s.not_plausible_dedup_canon_pct_techs_improved_vs_n1:.1f}%"
        )

        produced_ci = (
            "NA"
            if s.produced_components_mean_ci_lo is None or s.produced_components_mean_ci_hi is None
            else f"[{s.produced_components_mean_ci_lo:.2f}, {s.produced_components_mean_ci_hi:.2f}]"
        )
        produced_diff_ci = (
            "NA"
            if s.produced_components_mean_diff_vs_n1_ci_lo is None
            or s.produced_components_mean_diff_vs_n1_ci_hi is None
            else f"[{s.produced_components_mean_diff_vs_n1_ci_lo:.2f}, {s.produced_components_mean_diff_vs_n1_ci_hi:.2f}]"
        )
        produced_median_diff_ci = (
            "NA"
            if s.produced_components_median_diff_vs_n1_ci_lo is None
            or s.produced_components_median_diff_vs_n1_ci_hi is None
            else f"[{s.produced_components_median_diff_vs_n1_ci_lo:.2f}, {s.produced_components_median_diff_vs_n1_ci_hi:.2f}]"
        )

        silver_ci = (
            "NA"
            if s.silver_recall_mean_ci_lo is None or s.silver_recall_mean_ci_hi is None
            else f"[{s.silver_recall_mean_ci_lo:.3f}, {s.silver_recall_mean_ci_hi:.3f}]"
        )
        silver_diff_ci = (
            "NA"
            if s.silver_recall_mean_diff_vs_n1_ci_lo is None
            or s.silver_recall_mean_diff_vs_n1_ci_hi is None
            else f"[{s.silver_recall_mean_diff_vs_n1_ci_lo:.3f}, {s.silver_recall_mean_diff_vs_n1_ci_hi:.3f}]"
        )
        silver_median_diff_ci = (
            "NA"
            if s.silver_recall_median_diff_vs_n1_ci_lo is None
            or s.silver_recall_median_diff_vs_n1_ci_hi is None
            else f"[{s.silver_recall_median_diff_vs_n1_ci_lo:.3f}, {s.silver_recall_median_diff_vs_n1_ci_hi:.3f}]"
        )

        conv_ci = (
            "NA"
            if s.final_convergence_mean_ci_lo is None or s.final_convergence_mean_ci_hi is None
            else f"[{s.final_convergence_mean_ci_lo:.3f}, {s.final_convergence_mean_ci_hi:.3f}]"
        )
        conv_diff_ci = (
            "NA"
            if s.final_convergence_mean_diff_vs_n1_ci_lo is None
            or s.final_convergence_mean_diff_vs_n1_ci_hi is None
            else f"[{s.final_convergence_mean_diff_vs_n1_ci_lo:.3f}, {s.final_convergence_mean_diff_vs_n1_ci_hi:.3f}]"
        )
        conv_median_diff_ci = (
            "NA"
            if s.final_convergence_median_diff_vs_n1_ci_lo is None
            or s.final_convergence_median_diff_vs_n1_ci_hi is None
            else f"[{s.final_convergence_median_diff_vs_n1_ci_lo:.3f}, {s.final_convergence_median_diff_vs_n1_ci_hi:.3f}]"
        )

        rounds_ci = (
            "NA"
            if s.rounds_mean_ci_lo is None or s.rounds_mean_ci_hi is None
            else f"[{s.rounds_mean_ci_lo:.2f}, {s.rounds_mean_ci_hi:.2f}]"
        )
        rounds_diff_ci = (
            "NA"
            if s.rounds_mean_diff_vs_n1_ci_lo is None or s.rounds_mean_diff_vs_n1_ci_hi is None
            else f"[{s.rounds_mean_diff_vs_n1_ci_lo:.2f}, {s.rounds_mean_diff_vs_n1_ci_hi:.2f}]"
        )
        rounds_median_diff_ci = (
            "NA"
            if s.rounds_median_diff_vs_n1_ci_lo is None or s.rounds_median_diff_vs_n1_ci_hi is None
            else f"[{s.rounds_median_diff_vs_n1_ci_lo:.2f}, {s.rounds_median_diff_vs_n1_ci_hi:.2f}]"
        )

        runtime_ci = (
            "NA"
            if s.runtime_mean_ci_lo is None or s.runtime_mean_ci_hi is None
            else f"[{s.runtime_mean_ci_lo / 60.0:.1f}m, {s.runtime_mean_ci_hi / 60.0:.1f}m]"
        )
        runtime_diff_ci = (
            "NA"
            if s.runtime_mean_diff_vs_n1_ci_lo is None or s.runtime_mean_diff_vs_n1_ci_hi is None
            else f"[{s.runtime_mean_diff_vs_n1_ci_lo / 60.0:.1f}m, {s.runtime_mean_diff_vs_n1_ci_hi / 60.0:.1f}m]"
        )
        runtime_median_diff_ci = (
            "NA"
            if s.runtime_median_diff_vs_n1_ci_lo is None
            or s.runtime_median_diff_vs_n1_ci_hi is None
            else f"[{s.runtime_median_diff_vs_n1_ci_lo / 60.0:.1f}m, {s.runtime_median_diff_vs_n1_ci_hi / 60.0:.1f}m]"
        )

        lines.append(
            "| "
            + " | ".join(
                [
                    str(s.n),
                    str(s.technologies),
                    fmt_opt(s.stability_median, 3),
                    fmt_opt(s.stability_mean, 3),
                    stability_ci,
                    stability_diff_ci,
                    stability_median_diff_ci,
                    fmt_opt(s.not_plausible_occ_median, 3),
                    fmt_opt(s.not_plausible_occ_mean, 3),
                    np_occ_ci,
                    np_occ_diff_ci,
                    np_occ_median_diff_ci,
                    np_occ_pct_improved,
                    fmt_opt(
                        None
                        if s.not_plausible_occ_median is None
                        else (1.0 - s.not_plausible_occ_median),
                        3,
                    ),
                    fmt_opt(
                        None
                        if s.not_plausible_occ_mean is None
                        else (1.0 - s.not_plausible_occ_mean),
                        3,
                    ),
                    fmt_opt(s.not_plausible_dedup_canon_median, 3),
                    fmt_opt(s.not_plausible_dedup_canon_mean, 3),
                    np_dedup_ci,
                    np_dedup_diff_ci,
                    np_dedup_median_diff_ci,
                    np_dedup_pct_improved,
                    fmt_opt(
                        None
                        if s.not_plausible_dedup_canon_median is None
                        else (1.0 - s.not_plausible_dedup_canon_median),
                        3,
                    ),
                    fmt_opt(
                        None
                        if s.not_plausible_dedup_canon_mean is None
                        else (1.0 - s.not_plausible_dedup_canon_mean),
                        3,
                    ),
                    fmt_opt(s.produced_components_median, 2),
                    fmt_opt(s.produced_components_mean, 2),
                    produced_ci,
                    produced_diff_ci,
                    produced_median_diff_ci,
                    fmt_opt(s.silver_recall_median, 3),
                    fmt_opt(s.silver_recall_mean, 3),
                    silver_ci,
                    silver_diff_ci,
                    silver_median_diff_ci,
                    fmt_opt(s.final_convergence_median, 3),
                    fmt_opt(s.final_convergence_mean, 3),
                    conv_ci,
                    conv_diff_ci,
                    conv_median_diff_ci,
                    fmt_opt(s.rounds_median, 2),
                    fmt_opt(s.rounds_mean, 2),
                    rounds_ci,
                    rounds_diff_ci,
                    rounds_median_diff_ci,
                    fmt_seconds(s.runtime_median_seconds),
                    fmt_seconds(s.runtime_mean_seconds),
                    runtime_ci,
                    runtime_diff_ci,
                    runtime_median_diff_ci,
                ]
            )
            + " |"
        )

    lines.append("")
    return "\n".join(lines)


def recommend_n(
    summaries: list[MacroSummaryRow],
    max_not_plausible: Optional[float],
    min_final_convergence: Optional[float],
    max_runtime_seconds: Optional[float],
    stability_within_frac_of_best: Optional[float],
) -> tuple[Optional[int], str]:
    """
    Simple, defensible selector:
    1) Filter by constraints (on macro-median metrics where available)
    2) Choose smallest N whose stability is within X% of best feasible stability,
       breaking ties by lower runtime then lower N.

    Returns:
      (recommended_n, explanation_markdown)
    """
    reasons: list[str] = []
    reasons.append("### Why this N was picked")
    reasons.append("")
    reasons.append("Constraints (macro-median metrics):")
    reasons.append(
        f"- not_plausible_median <= {max_not_plausible if max_not_plausible is not None else 'NA (no constraint)'}"
    )
    reasons.append(
        f"- final_convergence_median >= {min_final_convergence if min_final_convergence is not None else 'NA (no constraint)'}"
    )
    reasons.append(
        f"- runtime_median_seconds <= {max_runtime_seconds if max_runtime_seconds is not None else 'NA (no constraint)'}"
    )
    reasons.append("")
    reasons.append(
        f"Near-best stability requirement: stability_median >= best_feasible_stability * {stability_within_frac_of_best if stability_within_frac_of_best is not None else 1.0}"
    )

    feasible: list[MacroSummaryRow] = []
    excluded: list[tuple[int, str]] = []

    for s in summaries:
        if max_not_plausible is not None and s.not_plausible_occ_median is not None:
            if s.not_plausible_occ_median > max_not_plausible:
                excluded.append((s.n, "not_plausible_occ_median"))
                continue
        if min_final_convergence is not None and s.final_convergence_median is not None:
            if s.final_convergence_median < min_final_convergence:
                excluded.append((s.n, "final_convergence_median"))
                continue
        if max_runtime_seconds is not None and s.runtime_median_seconds is not None:
            if s.runtime_median_seconds > max_runtime_seconds:
                excluded.append((s.n, "runtime_median_seconds"))
                continue
        feasible.append(s)

    if not feasible:
        reasons.append("")
        if excluded:
            reasons.append(
                "Feasible set: (empty) — excluded Ns: "
                + ", ".join(f"N={n} ({why})" for n, why in excluded)
                + "."
            )
        else:
            reasons.append("Feasible set: (empty).")
        reasons.append("")
        reasons.append("Result: no recommendation (insufficient feasible data).")
        return None, "\n".join(reasons) + "\n"

    reasons.append("")
    reasons.append(
        "Feasible Ns: "
        + ", ".join(
            f"N={s.n} (stability_median={fmt_opt(s.stability_median, 3)}, not_plausible_occ_median={fmt_opt(s.not_plausible_occ_median, 3)}, not_plausible_dedup_canon_median={fmt_opt(s.not_plausible_dedup_canon_median, 3)}, final_conv_median={fmt_opt(s.final_convergence_median, 3)}, runtime_median={fmt_seconds(s.runtime_median_seconds)})"
            for s in feasible
        )
        + "."
    )

    # best stability among feasible
    stabs = [s.stability_median for s in feasible if s.stability_median is not None]
    if not stabs:
        reasons.append("")
        reasons.append("Result: no recommendation (feasible set has no stability_median values).")
        return None, "\n".join(reasons) + "\n"

    best = max(stabs)
    frac = stability_within_frac_of_best if stability_within_frac_of_best is not None else 1.0
    threshold = best * frac
    reasons.append("")
    reasons.append(f"Best feasible stability_median: {best:.3f}")
    reasons.append(f"Stability threshold (near-best): {threshold:.3f}")

    candidates = [
        s for s in feasible if s.stability_median is not None and s.stability_median >= threshold
    ]
    if not candidates:
        reasons.append("")
        reasons.append(
            "Result: no recommendation (no feasible N meets the near-best stability threshold)."
        )
        return None, "\n".join(reasons) + "\n"

    reasons.append("")
    reasons.append(
        "Near-best candidates: "
        + ", ".join(
            f"N={s.n} (stability_median={s.stability_median:.3f}, runtime_median={fmt_seconds(s.runtime_median_seconds)})"
            for s in sorted(candidates, key=lambda x: x.n)
        )
        + "."
    )

    # prefer smallest N, but also consider runtime: sort by (N, runtime_median_seconds)
    def key(s: MacroSummaryRow) -> tuple[int, float]:
        rt = s.runtime_median_seconds if s.runtime_median_seconds is not None else float("inf")
        return (s.n, rt)

    chosen = sorted(candidates, key=key)[0]
    reasons.append("")
    reasons.append(
        f"Selected: N={chosen.n} (smallest N among near-best candidates; runtime_median={fmt_seconds(chosen.runtime_median_seconds)})."
    )

    return chosen.n, "\n".join(reasons) + "\n"


# -----------------------------
# Main: load + join
# -----------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--transcripts-dir", default="output/transcripts", help="Transcript TXT directory."
    )
    ap.add_argument(
        "--normalized-dir",
        default="output/normalized",
        help="Directory containing normalized output CSVs (stdns_output_<cfg>_<timestamp>.csv).",
    )
    ap.add_argument(
        "--canonical-vocab",
        default="data/component_canonical_vocab_global_primary.json",
        help="Canonical vocab JSON used to map components to canonical names.",
    )
    ap.add_argument(
        "--judge-jsonl",
        default="output/analysis/stage1_component_judge_normalized.jsonl",
        help="Judge JSONL from normalized runs (stage1_component_judge_normalized.jsonl).",
    )
    ap.add_argument("--logs-dir", default="output/logs", help="Run log directory.")
    ap.add_argument(
        "--configs",
        nargs="+",
        default=["v1v1v1", "d2v1v1", "d3v1v1", "d4v1v1", "d5v1v1", "d6v1v1"],
        help="Config tags to include (space-separated).",
    )
    ap.add_argument(
        "--include-missing-convergence",
        action="store_true",
        help="If set, treat missing convergence lines as zeros in aggregates. Default: exclude.",
    )
    ap.add_argument(
        "--out-md",
        default="output/analysis/sweet_spot_tradeoffs.md",
        help="Markdown output path.",
    )
    ap.add_argument(
        "--out-techn-csv",
        default=None,
        help="Optional per-(tech,N) CSV output path (for plotting).",
    )
    ap.add_argument(
        "--out-by-n-csv",
        default=None,
        help="Optional by-N CSV output path containing macro summaries, CIs, and deltas vs N=1 (for plotting).",
    )

    # Recommendation constraints
    ap.add_argument(
        "--max-not-plausible",
        type=float,
        default=None,
        help="Constraint on macro-median not-plausible rate.",
    )
    ap.add_argument(
        "--min-final-convergence",
        type=float,
        default=None,
        help="Constraint on macro-median final convergence.",
    )
    ap.add_argument(
        "--max-runtime-seconds",
        type=float,
        default=None,
        help="Constraint on macro-median runtime seconds.",
    )
    ap.add_argument(
        "--stability-within-frac-of-best",
        type=float,
        default=0.98,
        help="Choose smallest N within this fraction of best feasible macro-median stability (default: 0.98).",
    )

    args = ap.parse_args()

    transcripts_dir = Path(args.transcripts_dir)
    normalized_dir = Path(args.normalized_dir)
    canonical_vocab_path = Path(args.canonical_vocab)
    judge_jsonl = Path(args.judge_jsonl)
    logs_dir = Path(args.logs_dir)

    configs = [c.lower() for c in args.configs]
    configs_set = set(configs)

    vocab = (
        load_component_canonical_vocab(canonical_vocab_path)
        if canonical_vocab_path.exists()
        else {}
    )

    # Map cfg -> N
    cfg_to_n: dict[str, int] = {}
    for cfg in configs:
        n = component_agent_count_from_config_tag(cfg)
        if n is None:
            continue
        cfg_to_n[cfg] = n
    agent_counts_order = sorted(set(cfg_to_n.values()))

    if not agent_counts_order:
        raise SystemExit(
            "No valid component agent-counts inferred from --configs. Example configs: v1v1v1 d2v1v1 ..."
        )

    # --- Load stability + convergence from transcripts ---
    # Group transcript-derived values by (tech, cfg)
    stage1_sets: dict[tuple[str, str], list[set[str]]] = {}
    conv_final_scores: dict[tuple[str, str], list[float]] = {}
    rounds_values: dict[tuple[str, str], list[int]] = {}

    for fp in iter_files(transcripts_dir, "*.txt"):
        cfg = parse_config_from_filename(fp)
        if cfg not in configs_set:
            continue
        tech = parse_base_technology_from_filename(fp)

        txt = fp.read_text(encoding="utf-8", errors="replace")

        # Stability: stage1 final component sets
        comps = extract_stage1_final_components(txt)
        if comps:
            stage1_sets.setdefault((tech, cfg), []).append(comps)

        # Convergence: final score and rounds
        conv_scores = parse_convergence_scores(txt)
        if conv_scores:
            conv_final_scores.setdefault((tech, cfg), []).append(conv_scores[-1])
        else:
            if args.include_missing_convergence:
                conv_final_scores.setdefault((tech, cfg), []).append(0.0)

        r = parse_rounds_best_effort(txt)
        if r:
            rounds_values.setdefault((tech, cfg), []).append(r)

    # --- Load plausibility inputs from judge JSONL ---
    # Build a tech+component plausibility map, and a per-tech plausible reference set.
    judge_plausible_by_tech_comp: dict[tuple[str, str], bool] = {}

    # Occurrence-based counts by (tech, cfg) of judged FINAL components (populated from normalized outputs):
    judged_counts_occ: dict[tuple[str, str], tuple[int, int]] = {}  # (total, not_plausible)

    # Deduped-canonical counts by (tech, cfg):
    # We dedupe by canonical component name within (tech,cfg), using the canonical vocab.
    judged_dedup_seen: dict[tuple[str, str], set[str]] = {}
    judged_counts_dedup_canon: dict[
        tuple[str, str], tuple[int, int]
    ] = {}  # (unique_total, unique_not_plausible)

    # Silver recall proxy reference set: per-tech union of all judged-plausible components (across configs/runs),
    # canonicalized via the vocab.
    plausible_reference_by_tech_canon: dict[str, set[str]] = {}

    if judge_jsonl.exists():
        for row in load_judge_jsonl(judge_jsonl):
            extracted = extract_plausible_component_from_judge_row(row)
            if extracted is None:
                continue
            tech, _cfg, comp_raw, plausible = extracted

            judge_plausible_by_tech_comp[(tech, comp_raw)] = plausible

            # Canonicalize once for reference set
            canon = canonicalize_component(comp_raw, vocab)
            if plausible is True and canon:
                plausible_reference_by_tech_canon.setdefault(tech, set()).add(canon)
    else:
        # keep going; plausibility/recall will be NA
        pass

    # --- Load runtime from logs (config-run level) ---
    # For sweet-spot by N, we compute per-config median runtime and attach to all techs under that config.
    runtime_by_cfg_samples: dict[str, list[float]] = {}
    if logs_dir.exists():
        for lp in iter_files(logs_dir, "*.log"):
            cfg = parse_config_from_log_filename(lp)
            if cfg not in configs_set:
                continue
            txt = lp.read_text(encoding="utf-8", errors="replace")
            sec = parse_runtime_seconds_from_log_text(txt)
            if sec is None:
                continue
            runtime_by_cfg_samples.setdefault(cfg, []).append(sec)

    runtime_by_cfg_median: dict[str, Optional[float]] = {}
    for cfg in configs:
        secs = runtime_by_cfg_samples.get(cfg, [])
        runtime_by_cfg_median[cfg] = median(secs)

    # --- Load produced component sets from normalized outputs (canonicalized) ---
    # Build produced canonical sets per (tech,cfg) by scanning stdns_output_<cfg>_<timestamp>.csv
    produced_canon_by_tech_cfg: dict[tuple[str, str], set[str]] = {}
    produced_canon_sizes_by_tech_cfg: dict[tuple[str, str], list[int]] = {}
    if normalized_dir.exists():
        rx_norm = re.compile(r"^stdns_output_([a-z0-9]+)_\d{8}_\d{6}\.csv$", re.IGNORECASE)
        for fp in sorted(normalized_dir.glob("stdns_output_*.csv")):
            m = rx_norm.match(fp.name)
            if not m:
                continue
            cfg = m.group(1).lower()
            if cfg not in configs_set:
                continue
            try:
                per_file_sets: dict[str, set[str]] = {}
                per_file_raw: dict[str, set[str]] = {}
                with fp.open("r", encoding="utf-8", errors="replace", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tech = (row.get("technology") or "").strip()
                        comp = (row.get("component") or "").strip()
                        if not tech or not comp:
                            continue
                        per_file_raw.setdefault(tech, set()).add(comp)
                        canon = canonicalize_component(comp, vocab)
                        if not canon:
                            continue
                        per_file_sets.setdefault(tech, set()).add(canon)

                # Update union sets and per-run sizes
                for tech, s in per_file_sets.items():
                    produced_canon_by_tech_cfg.setdefault((tech, cfg), set()).update(s)
                    produced_canon_sizes_by_tech_cfg.setdefault((tech, cfg), []).append(len(s))

                # Update plausibility counts using judge map (per-run occurrence, plus deduped canonical)
                for tech, comps in per_file_raw.items():
                    key = (tech, cfg)
                    for comp in comps:
                        plausible = judge_plausible_by_tech_comp.get((tech, comp))
                        if plausible is None:
                            continue

                        total, not_plaus = judged_counts_occ.get(key, (0, 0))
                        total += 1
                        if plausible is False:
                            not_plaus += 1
                        judged_counts_occ[key] = (total, not_plaus)

                        canon = canonicalize_component(comp, vocab)
                        if not canon:
                            continue
                        seen = judged_dedup_seen.setdefault(key, set())
                        if canon in seen:
                            continue
                        seen.add(canon)
                        utotal, unot_plaus = judged_counts_dedup_canon.get(key, (0, 0))
                        utotal += 1
                        if plausible is False:
                            unot_plaus += 1
                        judged_counts_dedup_canon[key] = (utotal, unot_plaus)
            except Exception:
                # Best-effort: skip unreadable files
                continue

    # --- Build joined per-(tech,N) rows ---
    # Technologies considered are union across sources (transcripts + judge + normalized outputs).
    techs: set[str] = set()
    techs |= {k[0] for k in stage1_sets.keys()}
    techs |= {k[0] for k in judged_counts_occ.keys()}
    techs |= {k[0] for k in judged_counts_dedup_canon.keys()}
    techs |= {k[0] for k in conv_final_scores.keys()}
    techs |= {k[0] for k in rounds_values.keys()}
    techs |= {k[0] for k in produced_canon_by_tech_cfg.keys()}
    techs |= set(plausible_reference_by_tech_canon.keys())

    rows: list[TechNRow] = []
    for tech in sorted(techs):
        for cfg in configs:
            if cfg not in cfg_to_n:
                continue
            n = cfg_to_n[cfg]
            key = (tech, cfg)

            run_sets = stage1_sets.get(key, [])
            stab = stability_mean_pairwise_jaccard(run_sets)

            # Occurrence-based not-plausible rate
            occ = judged_counts_occ.get(key, None)
            np_rate_occ: Optional[float] = None
            if occ is not None:
                total, not_plaus = occ
                if total > 0:
                    np_rate_occ = not_plaus / total

            # Deduped-canonical not-plausible rate
            ded = judged_counts_dedup_canon.get(key, None)
            np_rate_dedup: Optional[float] = None
            if ded is not None:
                utotal, unot_plaus = ded
                if utotal > 0:
                    np_rate_dedup = unot_plaus / utotal

            # Explicit precision proxies (1 - not-plausible)
            precision_occ: Optional[float] = None if np_rate_occ is None else (1.0 - np_rate_occ)
            precision_dedup: Optional[float] = (
                None if np_rate_dedup is None else (1.0 - np_rate_dedup)
            )

            # Produced component count control: per-run median |ProducedCanonical(tech,cfg,run)|
            produced_components_median: Optional[float] = None
            sizes = produced_canon_sizes_by_tech_cfg.get(key, [])
            if sizes:
                produced_components_median = median([float(x) for x in sizes])

            # Silver recall proxy: canonical coverage of per-tech plausible reference by produced canonical components.
            silver_recall: Optional[float] = None
            ref = plausible_reference_by_tech_canon.get(tech, None)
            if ref:
                produced = produced_canon_by_tech_cfg.get(key, set())
                silver_recall = len(produced & ref) / len(ref) if len(ref) > 0 else None

            convs = conv_final_scores.get(key, [])
            conv_mean = safe_mean(convs)

            rds = rounds_values.get(key, [])
            rds_mean = safe_mean([float(x) for x in rds]) if rds else None

            rt = runtime_by_cfg_median.get(cfg)

            # Only include rows where we have at least one metric (avoid empty tech/cfg artifacts)
            if (
                stab is None
                and np_rate_occ is None
                and np_rate_dedup is None
                and silver_recall is None
                and conv_mean is None
                and rds_mean is None
                and rt is None
            ):
                continue

            rows.append(
                TechNRow(
                    technology=tech,
                    config=cfg,
                    n=n,
                    stability_mean_jaccard=stab,
                    not_plausible_rate_occurrence=np_rate_occ,
                    not_plausible_rate_dedup_canon=np_rate_dedup,
                    precision_proxy_occurrence=precision_occ,
                    precision_proxy_dedup_canon=precision_dedup,
                    produced_components_median=produced_components_median,
                    silver_recall_proxy=silver_recall,
                    final_convergence_mean=conv_mean,
                    rounds_mean=rds_mean,
                    runtime_seconds=rt,
                )
            )

    # --- Macro summarize by N ---
    summaries = [macro_summarize(rows, n) for n in agent_counts_order]

    # Populate bootstrap CIs for differences vs N=1 across technologies (paired where possible).
    # We treat technologies as the unit of resampling (equal weight per technology).
    by_n: dict[int, dict[str, TechNRow]] = {}
    for r in rows:
        by_n.setdefault(r.n, {})[r.technology] = r

    if 1 in by_n:
        baseline = by_n[1]
        for i, n in enumerate(agent_counts_order):
            if n == 1:
                continue

            current = by_n.get(n, {})
            common_techs = sorted(set(baseline.keys()) & set(current.keys()))
            if not common_techs:
                continue

            # Build paired vectors (current vs baseline) per metric
            stab_cur = [
                current[t].stability_mean_jaccard
                for t in common_techs
                if current[t].stability_mean_jaccard is not None
                and baseline[t].stability_mean_jaccard is not None
            ]
            stab_base = [
                baseline[t].stability_mean_jaccard
                for t in common_techs
                if current[t].stability_mean_jaccard is not None
                and baseline[t].stability_mean_jaccard is not None
            ]

            np_occ_cur = [
                current[t].not_plausible_rate_occurrence
                for t in common_techs
                if current[t].not_plausible_rate_occurrence is not None
                and baseline[t].not_plausible_rate_occurrence is not None
            ]
            np_occ_base = [
                baseline[t].not_plausible_rate_occurrence
                for t in common_techs
                if current[t].not_plausible_rate_occurrence is not None
                and baseline[t].not_plausible_rate_occurrence is not None
            ]

            np_dedup_cur = [
                current[t].not_plausible_rate_dedup_canon
                for t in common_techs
                if current[t].not_plausible_rate_dedup_canon is not None
                and baseline[t].not_plausible_rate_dedup_canon is not None
            ]
            np_dedup_base = [
                baseline[t].not_plausible_rate_dedup_canon
                for t in common_techs
                if current[t].not_plausible_rate_dedup_canon is not None
                and baseline[t].not_plausible_rate_dedup_canon is not None
            ]

            k_cur = [
                current[t].produced_components_median
                for t in common_techs
                if current[t].produced_components_median is not None
                and baseline[t].produced_components_median is not None
            ]
            k_base = [
                baseline[t].produced_components_median
                for t in common_techs
                if current[t].produced_components_median is not None
                and baseline[t].produced_components_median is not None
            ]

            silver_cur = [
                current[t].silver_recall_proxy
                for t in common_techs
                if current[t].silver_recall_proxy is not None
                and baseline[t].silver_recall_proxy is not None
            ]
            silver_base = [
                baseline[t].silver_recall_proxy
                for t in common_techs
                if current[t].silver_recall_proxy is not None
                and baseline[t].silver_recall_proxy is not None
            ]

            conv_cur = [
                current[t].final_convergence_mean
                for t in common_techs
                if current[t].final_convergence_mean is not None
                and baseline[t].final_convergence_mean is not None
            ]
            conv_base = [
                baseline[t].final_convergence_mean
                for t in common_techs
                if current[t].final_convergence_mean is not None
                and baseline[t].final_convergence_mean is not None
            ]

            rounds_cur = [
                current[t].rounds_mean
                for t in common_techs
                if current[t].rounds_mean is not None and baseline[t].rounds_mean is not None
            ]
            rounds_base = [
                baseline[t].rounds_mean
                for t in common_techs
                if current[t].rounds_mean is not None and baseline[t].rounds_mean is not None
            ]

            runtime_cur = [
                current[t].runtime_seconds
                for t in common_techs
                if current[t].runtime_seconds is not None
                and baseline[t].runtime_seconds is not None
            ]
            runtime_base = [
                baseline[t].runtime_seconds
                for t in common_techs
                if current[t].runtime_seconds is not None
                and baseline[t].runtime_seconds is not None
            ]

            # Mean diffs vs N=1
            stab_dlo, stab_dhi = bootstrap_mean_diff_ci(stab_cur, stab_base, seed=11000 + n)
            np_occ_dlo, np_occ_dhi = bootstrap_mean_diff_ci(np_occ_cur, np_occ_base, seed=12000 + n)
            np_dedup_dlo, np_dedup_dhi = bootstrap_mean_diff_ci(
                np_dedup_cur, np_dedup_base, seed=13000 + n
            )
            k_dlo, k_dhi = bootstrap_mean_diff_ci(k_cur, k_base, seed=14000 + n)
            silver_dlo, silver_dhi = bootstrap_mean_diff_ci(silver_cur, silver_base, seed=15000 + n)
            conv_dlo, conv_dhi = bootstrap_mean_diff_ci(conv_cur, conv_base, seed=16000 + n)
            rounds_dlo, rounds_dhi = bootstrap_mean_diff_ci(rounds_cur, rounds_base, seed=17000 + n)
            runtime_dlo, runtime_dhi = bootstrap_mean_diff_ci(
                runtime_cur, runtime_base, seed=18000 + n
            )

            # Median diffs vs N=1
            stab_mdlo, stab_mdhi = bootstrap_median_diff_ci(stab_cur, stab_base, seed=21000 + n)
            np_occ_mdlo, np_occ_mdhi = bootstrap_median_diff_ci(
                np_occ_cur, np_occ_base, seed=22000 + n
            )
            np_dedup_mdlo, np_dedup_mdhi = bootstrap_median_diff_ci(
                np_dedup_cur, np_dedup_base, seed=23000 + n
            )
            k_mdlo, k_mdhi = bootstrap_median_diff_ci(k_cur, k_base, seed=24000 + n)
            silver_mdlo, silver_mdhi = bootstrap_median_diff_ci(
                silver_cur, silver_base, seed=25000 + n
            )
            conv_mdlo, conv_mdhi = bootstrap_median_diff_ci(conv_cur, conv_base, seed=26000 + n)
            rounds_mdlo, rounds_mdhi = bootstrap_median_diff_ci(
                rounds_cur, rounds_base, seed=27000 + n
            )
            runtime_mdlo, runtime_mdhi = bootstrap_median_diff_ci(
                runtime_cur, runtime_base, seed=28000 + n
            )

            # Sign test style summaries (% techs improved):
            # For invalid rate, "improved" means current < baseline.
            np_occ_pct_improved: Optional[float] = None
            if len(np_occ_cur) == len(np_occ_base) and np_occ_cur:
                improved = sum(1 for a, b in zip(np_occ_cur, np_occ_base, strict=False) if a < b)
                np_occ_pct_improved = 100.0 * improved / len(np_occ_cur)

            np_dedup_pct_improved: Optional[float] = None
            if len(np_dedup_cur) == len(np_dedup_base) and np_dedup_cur:
                improved = sum(
                    1 for a, b in zip(np_dedup_cur, np_dedup_base, strict=False) if a < b
                )
                np_dedup_pct_improved = 100.0 * improved / len(np_dedup_cur)

            s0 = summaries[i]
            summaries[i] = MacroSummaryRow(
                **{
                    **s0.__dict__,
                    "stability_mean_diff_vs_n1_ci_lo": stab_dlo,
                    "stability_mean_diff_vs_n1_ci_hi": stab_dhi,
                    "stability_median_diff_vs_n1_ci_lo": stab_mdlo,
                    "stability_median_diff_vs_n1_ci_hi": stab_mdhi,
                    "not_plausible_occ_mean_diff_vs_n1_ci_lo": np_occ_dlo,
                    "not_plausible_occ_mean_diff_vs_n1_ci_hi": np_occ_dhi,
                    "not_plausible_occ_median_diff_vs_n1_ci_lo": np_occ_mdlo,
                    "not_plausible_occ_median_diff_vs_n1_ci_hi": np_occ_mdhi,
                    "not_plausible_occ_pct_techs_improved_vs_n1": np_occ_pct_improved,
                    "not_plausible_dedup_canon_mean_diff_vs_n1_ci_lo": np_dedup_dlo,
                    "not_plausible_dedup_canon_mean_diff_vs_n1_ci_hi": np_dedup_dhi,
                    "not_plausible_dedup_canon_median_diff_vs_n1_ci_lo": np_dedup_mdlo,
                    "not_plausible_dedup_canon_median_diff_vs_n1_ci_hi": np_dedup_mdhi,
                    "not_plausible_dedup_canon_pct_techs_improved_vs_n1": np_dedup_pct_improved,
                    "produced_components_mean_diff_vs_n1_ci_lo": k_dlo,
                    "produced_components_mean_diff_vs_n1_ci_hi": k_dhi,
                    "produced_components_median_diff_vs_n1_ci_lo": k_mdlo,
                    "produced_components_median_diff_vs_n1_ci_hi": k_mdhi,
                    "silver_recall_mean_diff_vs_n1_ci_lo": silver_dlo,
                    "silver_recall_mean_diff_vs_n1_ci_hi": silver_dhi,
                    "silver_recall_median_diff_vs_n1_ci_lo": silver_mdlo,
                    "silver_recall_median_diff_vs_n1_ci_hi": silver_mdhi,
                    "final_convergence_mean_diff_vs_n1_ci_lo": conv_dlo,
                    "final_convergence_mean_diff_vs_n1_ci_hi": conv_dhi,
                    "final_convergence_median_diff_vs_n1_ci_lo": conv_mdlo,
                    "final_convergence_median_diff_vs_n1_ci_hi": conv_mdhi,
                    "rounds_mean_diff_vs_n1_ci_lo": rounds_dlo,
                    "rounds_mean_diff_vs_n1_ci_hi": rounds_dhi,
                    "rounds_median_diff_vs_n1_ci_lo": rounds_mdlo,
                    "rounds_median_diff_vs_n1_ci_hi": rounds_mdhi,
                    "runtime_mean_diff_vs_n1_ci_lo": runtime_dlo,
                    "runtime_mean_diff_vs_n1_ci_hi": runtime_dhi,
                    "runtime_median_diff_vs_n1_ci_lo": runtime_mdlo,
                    "runtime_median_diff_vs_n1_ci_hi": runtime_mdhi,
                }
            )

    md = render_macro_md_table(summaries)

    # Recommendation
    rec, why_md = recommend_n(
        summaries,
        max_not_plausible=args.max_not_plausible,
        min_final_convergence=args.min_final_convergence,
        max_runtime_seconds=args.max_runtime_seconds,
        stability_within_frac_of_best=args.stability_within_frac_of_best,
    )
    md += "## Recommendation (heuristic)\n\n"
    if rec is None:
        md += "No recommended N (insufficient data after applying constraints).\n\n"
    else:
        md += f"Recommended component agent-count: **N={rec}**\n\n"
    md += why_md

    # Write outputs
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")

    if args.out_techn_csv:
        out_csv = Path(args.out_techn_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "technology",
                    "config",
                    "n",
                    "stability_mean_jaccard",
                    "not_plausible_rate_occurrence",
                    "precision_proxy_occurrence",
                    "not_plausible_rate_dedup_canon",
                    "precision_proxy_dedup_canon",
                    "produced_components_median",
                    "silver_recall_proxy",
                    "final_convergence_mean",
                    "rounds_mean",
                    "runtime_seconds",
                ],
            )
            w.writeheader()
            for r in rows:
                w.writerow(
                    {
                        "technology": r.technology,
                        "config": r.config,
                        "n": r.n,
                        "stability_mean_jaccard": ""
                        if r.stability_mean_jaccard is None
                        else f"{r.stability_mean_jaccard:.6f}",
                        "not_plausible_rate_occurrence": ""
                        if r.not_plausible_rate_occurrence is None
                        else f"{r.not_plausible_rate_occurrence:.6f}",
                        "precision_proxy_occurrence": ""
                        if r.precision_proxy_occurrence is None
                        else f"{r.precision_proxy_occurrence:.6f}",
                        "not_plausible_rate_dedup_canon": ""
                        if r.not_plausible_rate_dedup_canon is None
                        else f"{r.not_plausible_rate_dedup_canon:.6f}",
                        "precision_proxy_dedup_canon": ""
                        if r.precision_proxy_dedup_canon is None
                        else f"{r.precision_proxy_dedup_canon:.6f}",
                        "produced_components_median": ""
                        if r.produced_components_median is None
                        else f"{r.produced_components_median:.6f}",
                        "silver_recall_proxy": ""
                        if r.silver_recall_proxy is None
                        else f"{r.silver_recall_proxy:.6f}",
                        "final_convergence_mean": ""
                        if r.final_convergence_mean is None
                        else f"{r.final_convergence_mean:.6f}",
                        "rounds_mean": "" if r.rounds_mean is None else f"{r.rounds_mean:.6f}",
                        "runtime_seconds": ""
                        if r.runtime_seconds is None
                        else f"{r.runtime_seconds:.3f}",
                    }
                )

    if args.out_by_n_csv:
        out_csv = Path(args.out_by_n_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "n",
                    "technologies",
                    "stability_median",
                    "stability_mean",
                    "stability_mean_ci_lo",
                    "stability_mean_ci_hi",
                    "stability_mean_diff_vs_n1_ci_lo",
                    "stability_mean_diff_vs_n1_ci_hi",
                    "stability_median_diff_vs_n1_ci_lo",
                    "stability_median_diff_vs_n1_ci_hi",
                    "not_plausible_occ_median",
                    "not_plausible_occ_mean",
                    "not_plausible_occ_mean_ci_lo",
                    "not_plausible_occ_mean_ci_hi",
                    "not_plausible_occ_mean_diff_vs_n1_ci_lo",
                    "not_plausible_occ_mean_diff_vs_n1_ci_hi",
                    "not_plausible_occ_median_diff_vs_n1_ci_lo",
                    "not_plausible_occ_median_diff_vs_n1_ci_hi",
                    "not_plausible_occ_pct_techs_improved_vs_n1",
                    "not_plausible_dedup_canon_median",
                    "not_plausible_dedup_canon_mean",
                    "not_plausible_dedup_canon_mean_ci_lo",
                    "not_plausible_dedup_canon_mean_ci_hi",
                    "not_plausible_dedup_canon_mean_diff_vs_n1_ci_lo",
                    "not_plausible_dedup_canon_mean_diff_vs_n1_ci_hi",
                    "not_plausible_dedup_canon_median_diff_vs_n1_ci_lo",
                    "not_plausible_dedup_canon_median_diff_vs_n1_ci_hi",
                    "not_plausible_dedup_canon_pct_techs_improved_vs_n1",
                    "produced_components_median",
                    "produced_components_mean",
                    "produced_components_mean_ci_lo",
                    "produced_components_mean_ci_hi",
                    "produced_components_mean_diff_vs_n1_ci_lo",
                    "produced_components_mean_diff_vs_n1_ci_hi",
                    "produced_components_median_diff_vs_n1_ci_lo",
                    "produced_components_median_diff_vs_n1_ci_hi",
                    "silver_recall_median",
                    "silver_recall_mean",
                    "silver_recall_mean_ci_lo",
                    "silver_recall_mean_ci_hi",
                    "silver_recall_mean_diff_vs_n1_ci_lo",
                    "silver_recall_mean_diff_vs_n1_ci_hi",
                    "silver_recall_median_diff_vs_n1_ci_lo",
                    "silver_recall_median_diff_vs_n1_ci_hi",
                    "final_convergence_median",
                    "final_convergence_mean",
                    "final_convergence_mean_ci_lo",
                    "final_convergence_mean_ci_hi",
                    "final_convergence_mean_diff_vs_n1_ci_lo",
                    "final_convergence_mean_diff_vs_n1_ci_hi",
                    "final_convergence_median_diff_vs_n1_ci_lo",
                    "final_convergence_median_diff_vs_n1_ci_hi",
                    "rounds_median",
                    "rounds_mean",
                    "rounds_mean_ci_lo",
                    "rounds_mean_ci_hi",
                    "rounds_mean_diff_vs_n1_ci_lo",
                    "rounds_mean_diff_vs_n1_ci_hi",
                    "rounds_median_diff_vs_n1_ci_lo",
                    "rounds_median_diff_vs_n1_ci_hi",
                    "runtime_median_seconds",
                    "runtime_mean_seconds",
                    "runtime_mean_ci_lo",
                    "runtime_mean_ci_hi",
                    "runtime_mean_diff_vs_n1_ci_lo",
                    "runtime_mean_diff_vs_n1_ci_hi",
                    "runtime_median_diff_vs_n1_ci_lo",
                    "runtime_median_diff_vs_n1_ci_hi",
                ],
            )
            w.writeheader()
            for s in summaries:
                w.writerow({k: getattr(s, k) for k in w.fieldnames})

    print(f"Wrote: {out_md}")
    if args.out_techn_csv:
        print(f"Wrote: {args.out_techn_csv}")
    if args.out_by_n_csv:
        print(f"Wrote: {args.out_by_n_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
