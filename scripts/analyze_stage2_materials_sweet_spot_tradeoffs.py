#!/usr/bin/env python3
"""
Stage 2 Materials "sweet-spot" tradeoff analysis.

This is a clean, from-scratch Stage 2 analogue of:
  scripts/analyze_sweet_spot_tradeoffs.py   (Stage 1 components)

It aggregates metrics by *materials agent-count N* and produces:
- A per-(tech, N) table
- A macro summary by N (macro-median/macro-mean across technologies, bootstrap CIs,
  and deltas vs N=1)
- A recommended "sweet-spot" N using the same constraint + near-best stability heuristic
- Optional CSVs for plotting:
    --out-techn-csv  (per-(tech,N))
    --out-by-n-csv   (macro summary by N)

Inputs (defaults aligned with this repo):
- Transcripts: output/transcripts/*.txt
  (Used for Stage 2 FINAL "Materials by Component:" extraction + stability/convergence best-effort)
- Judge JSONL: output/analysis/final_only_material_verification_ALL_by_config.jsonl
  (Produced by scripts/verify_pruned_materials.py; used for plausibility + silver reference)

Notes / assumptions:
- Config tags are 3 concatenated tokens like:
    d2v1v1, v1d3v1, d3d3v3
  where the *materials token is the 2nd token*, and N is its numeric part.
  Example: v1d5v1 -> materials N=5
- This script is robust to partial data. Missing metrics are excluded from aggregates.
- Judge rows with status != ok (or inferred timeout/error) are excluded from plausibility.
- Guardrail: the sweet-spot recommendation can optionally be computed using only Ns that have
  non-NA macro plausibility (i.e., not_plausible_median is present). This prevents N=1 from
  distorting recommendation constraints in mixed runs where N=1 may correspond to configs that
  were never judged for Stage 2 plausibility.

Example:
  uv run python scripts/analyze_stage2_materials_sweet_spot_tradeoffs.py \\
    --judge-jsonl output/analysis/final_only_material_verification_ALL_by_config.jsonl \\
    --out-md output/analysis/stage2_materials_sweet_spot_tradeoffs.md \\
    --out-techn-csv output/analysis/stage2_materials_by_tech_n.csv \\
    --out-by-n-csv output/analysis/stage2_materials_by_n_macro.csv

"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import random
import re
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# -----------------------------
# Config parsing / agent-count
# -----------------------------

# Matches entire config tag like d2v1v1, v1d3v1, d3d3v3.
# Use \b boundaries; transcript filenames contain underscores, so we will match against
# a normalized filename where "_" is replaced by " " before searching.
_RX_CFG_TAG = re.compile(r"\b(?:[vd]\d+){3}\b", re.IGNORECASE)

# Tokenizer for a config tag.
_RX_CFG_TOKEN = re.compile(r"[vd]\d+", re.IGNORECASE)

# Used for transcript round parsing / optional convergence best-effort.
_RX_ROUND_HEADER = re.compile(r"(?im)^\s*Round\s+\d+.*$")

# Used to find config tag in judge "label" strings if needed.
# (For Stage 2 judge JSONL we expect separate fields technology/config.)
_RX_CFG_TOKEN_IN_TEXT = re.compile(r"\b(?:[vd]\d+){3}\b", re.IGNORECASE)

_LOG_DT_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
]


def materials_agent_count_from_config_tag(cfg: str) -> Optional[int]:
    """
    Extract materials agent-count N from a config tag with 3 tokens.

    The materials token is the 2nd token, so:
      v1d5v1 -> ["v1","d5","v1"] -> N=5
      d2v1v1 -> ["d2","v1","v1"] -> N=1

    Returns None if parse fails.
    """
    if not cfg:
        return None
    tag = cfg.strip().lower()
    toks = _RX_CFG_TOKEN.findall(tag)
    if len(toks) != 3:
        # Might be embedded; try to search for the full tag first.
        m = _RX_CFG_TAG.search(tag)
        if not m:
            return None
        toks = _RX_CFG_TOKEN.findall(m.group(0).lower())
        if len(toks) != 3:
            return None

    materials_tok = toks[1].lower()
    m2 = re.match(r"[vd](\d+)$", materials_tok)
    if not m2:
        return None
    return int(m2.group(1))


def parse_transcript_filename_to_tech_cfg(path: str) -> Tuple[str, str]:
    """
    Transcript filenames look like:
      Autoclave_(Steam_Sterilizer)_d2v1v1_20260212_131256.txt

    We parse:
      cfg = the config tag
      tech = everything before cfg, underscores -> spaces, strip.

    Returns (tech, cfg). If cfg not found, cfg="unknown"; tech best-effort.
    """
    name = os.path.basename(path)
    name_for_match = name.replace("_", " ")
    m = _RX_CFG_TAG.search(name_for_match)
    if not m:
        # best-effort tech
        tech = name.replace("_", " ").rsplit(".", 1)[0]
        return tech.strip() or "unknown", "unknown"

    cfg = m.group(0).lower()
    tech_part = name_for_match[: m.start()].rstrip(" -")
    tech = tech_part.replace("_", " ").strip() or "unknown"
    return tech, cfg


# -----------------------------
# Normalization / canonicalization
# -----------------------------


def normalize_material_name_for_matching(s: str) -> str:
    """
    Conservative normalization for materials.
    You can extend this if needed.
    """
    t = (s or "").strip().lower()
    t = re.sub(r"[\u2013\u2014]", "-", t)  # en/em dash -> hyphen
    t = re.sub(r"\s+", " ", t)
    t = t.strip(" .,:;()[]{}")
    return t


def canonicalize_material(s: str) -> str:
    # Hook point for a future materials vocab; keep conservative for now.
    return normalize_material_name_for_matching(s)


# -----------------------------
# Stage 2 extraction: final materials from transcripts
# -----------------------------


def extract_stage2_final_materials_from_transcript_txt(txt: str) -> List[str]:
    """
    Best-effort parser for Stage 2 transcript .txt files.

    It looks for the last occurrence of a header like:
      "Materials by Component:"

    Then collects material strings from subsequent lines until a plausible section boundary.

    Returns a list of raw material tokens (not canonicalized).
    """
    if not txt:
        return []

    header_rx = re.compile(r"^\s*Materials by Component\s*:\s*$", re.IGNORECASE | re.MULTILINE)
    m_last: Optional[re.Match[str]] = None
    for m in header_rx.finditer(txt):
        m_last = m
    if not m_last:
        return []

    tail = txt[m_last.end() :]
    lines = tail.splitlines()

    mats: List[str] = []
    for line in lines:
        # Stop at markdown-style headers or strong section markers.
        if re.match(r"^\s*#{1,6}\s+\S+", line):
            break
        if re.match(r"^\s*(Final|Consensus|Debate|Round)\b.*:\s*$", line, flags=re.IGNORECASE):
            break

        s = line.strip()
        if not s:
            continue

        # Remove bullets
        s = re.sub(r"^\s*[-*]\s*", "", s)

        # If line looks like "Component: A, B, C", keep only RHS
        if ":" in s:
            _, rhs = s.split(":", 1)
            s = rhs.strip()

        # Split by common separators
        parts = re.split(r"[;,/]|(?:\s+\|\s+)", s)
        for p in parts:
            tok = p.strip()
            if not tok:
                continue
            if len(tok) < 2:
                continue
            mats.append(tok)

    return mats


def jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def pairwise_jaccards(sets: Sequence[Sequence[str]]) -> List[float]:
    out: List[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            out.append(jaccard(sets[i], sets[j]))
    return out


# -----------------------------
# Convergence parsing (best-effort)
# -----------------------------


def parse_round_chunks_best_effort(transcript_text: str) -> List[str]:
    if not transcript_text:
        return []
    matches = list(_RX_ROUND_HEADER.finditer(transcript_text))
    if not matches:
        return []
    chunks: List[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(transcript_text)
        chunks.append(transcript_text[start:end])
    return chunks


def parse_convergence_scores_best_effort(transcript_text: str) -> List[float]:
    """
    Best-effort: look for 'convergence: 0.85' patterns within rounds.
    """
    rx = re.compile(r"(?i)\bconvergence\b\s*[:=]\s*([01](?:\.\d+)?)\b")
    scores: List[float] = []
    for chunk in parse_round_chunks_best_effort(transcript_text):
        m = rx.search(chunk)
        if not m:
            continue
        try:
            scores.append(float(m.group(1)))
        except ValueError:
            pass
    return scores


# -----------------------------
# Judge JSONL parsing (materials)
# -----------------------------


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            rows.append(json.loads(s))
    return rows


def infer_judge_status(row: Dict[str, Any]) -> str:
    verdict = row.get("verdict") if isinstance(row.get("verdict"), dict) else {}
    st = verdict.get("status")
    if isinstance(st, str) and st.strip():
        return st.strip().lower()

    rationale = str(verdict.get("rationale") or "").lower()
    if "timed out" in rationale or "timeout" in rationale or "watchdog" in rationale:
        return "timeout"
    if "traceback" in rationale or "exception" in rationale or rationale.startswith("error"):
        return "error"
    return "ok"


def extract_plausible_material_from_judge_row(
    row: Dict[str, Any],
) -> Optional[Tuple[str, str, str, bool]]:
    """
    Extract (technology, config, material_raw, plausible_bool) from a materials judge row.

    Expected fields from verify_pruned_materials.py:
      technology: base technology name (string)
      config: config tag (string)
      material: raw material string
      verdict.plausible_primary_material: bool
      verdict.status: optional; else inferred from rationale
    """
    tech = row.get("technology")
    cfg = row.get("config")
    mat = row.get("material")
    if tech in (None, "") or cfg in (None, "") or mat in (None, ""):
        return None

    if infer_judge_status(row) != "ok":
        return None

    verdict = row.get("verdict") if isinstance(row.get("verdict"), dict) else {}
    plausible = verdict.get("plausible_primary_material", None)
    if not isinstance(plausible, bool):
        return None

    mat_s = str(mat).strip()
    if not mat_s:
        return None

    return str(tech).strip(), str(cfg).strip().lower(), mat_s, plausible


# -----------------------------
# Runtime parsing (optional, from logs)
# -----------------------------


def parse_log_datetime(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    for fmt in _LOG_DT_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def parse_runtime_seconds_from_log_text(log_text: str) -> Optional[float]:
    """
    Best-effort parser for runtime.
    Searches for lines like:
      "STDN Generation Started: <dt>"
      "STDN Generation Completed: <dt>"
    """
    if not log_text:
        return None

    start_rx = re.compile(r"STDN Generation Started\s*:\s*(.+)$", re.MULTILINE)
    done_rx = re.compile(r"STDN Generation Completed\s*:\s*(.+)$", re.MULTILINE)

    ms = start_rx.search(log_text)
    md = done_rx.search(log_text)
    if not ms or not md:
        return None

    start_dt = parse_log_datetime(ms.group(1))
    done_dt = parse_log_datetime(md.group(1))
    if not start_dt or not done_dt:
        return None

    delta = (done_dt - start_dt).total_seconds()
    return float(delta) if delta >= 0 else None


def parse_config_from_filename_anywhere(path: str) -> str:
    name = os.path.basename(path).replace("_", " ")
    m = _RX_CFG_TAG.search(name)
    return m.group(0).lower() if m else "unknown"


# -----------------------------
# Stats helpers (bootstrap + formatting)
# -----------------------------


def safe_mean(xs: Sequence[float]) -> Optional[float]:
    xs2 = [float(x) for x in xs if isinstance(x, (int, float)) and not math.isnan(x)]
    return (sum(xs2) / len(xs2)) if xs2 else None


def safe_median(xs: Sequence[float]) -> Optional[float]:
    xs2 = [float(x) for x in xs if isinstance(x, (int, float)) and not math.isnan(x)]
    return statistics.median(xs2) if xs2 else None


def bootstrap_mean_ci(
    xs: Sequence[float], *, seed: int = 0, iters: int = 2000, alpha: float = 0.05
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    xs2 = [float(x) for x in xs if isinstance(x, (int, float)) and not math.isnan(x)]
    if not xs2:
        return None, None, None
    rng = random.Random(seed)
    n = len(xs2)
    means: List[float] = []
    for _ in range(iters):
        samp = [xs2[rng.randrange(n)] for _ in range(n)]
        means.append(sum(samp) / n)
    means.sort()
    lo = means[int((alpha / 2) * (iters - 1))]
    hi = means[int((1 - alpha / 2) * (iters - 1))]
    return sum(xs2) / n, lo, hi


def bootstrap_median_ci(
    xs: Sequence[float], *, seed: int = 0, iters: int = 2000, alpha: float = 0.05
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    xs2 = [float(x) for x in xs if isinstance(x, (int, float)) and not math.isnan(x)]
    if not xs2:
        return None, None, None
    rng = random.Random(seed)
    n = len(xs2)
    meds: List[float] = []
    for _ in range(iters):
        samp = [xs2[rng.randrange(n)] for _ in range(n)]
        meds.append(statistics.median(samp))
    meds.sort()
    lo = meds[int((alpha / 2) * (iters - 1))]
    hi = meds[int((1 - alpha / 2) * (iters - 1))]
    return statistics.median(xs2), lo, hi


def bootstrap_mean_diff_ci(
    a: Sequence[float], b: Sequence[float], *, seed: int = 0, iters: int = 2000, alpha: float = 0.05
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Bootstrap CI on mean(a) - mean(b).
    """
    a2 = [float(x) for x in a if isinstance(x, (int, float)) and not math.isnan(x)]
    b2 = [float(x) for x in b if isinstance(x, (int, float)) and not math.isnan(x)]
    if not a2 or not b2:
        return None, None, None
    rng = random.Random(seed)
    na = len(a2)
    nb = len(b2)
    diffs: List[float] = []
    for _ in range(iters):
        sa = [a2[rng.randrange(na)] for _ in range(na)]
        sb = [b2[rng.randrange(nb)] for _ in range(nb)]
        diffs.append((sum(sa) / na) - (sum(sb) / nb))
    diffs.sort()
    lo = diffs[int((alpha / 2) * (iters - 1))]
    hi = diffs[int((1 - alpha / 2) * (iters - 1))]
    return (sum(a2) / na) - (sum(b2) / nb), lo, hi


def bootstrap_median_diff_ci(
    a: Sequence[float], b: Sequence[float], *, seed: int = 0, iters: int = 2000, alpha: float = 0.05
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Bootstrap CI on median(a) - median(b).
    """
    a2 = [float(x) for x in a if isinstance(x, (int, float)) and not math.isnan(x)]
    b2 = [float(x) for x in b if isinstance(x, (int, float)) and not math.isnan(x)]
    if not a2 or not b2:
        return None, None, None
    rng = random.Random(seed)
    na = len(a2)
    nb = len(b2)
    diffs: List[float] = []
    for _ in range(iters):
        sa = [a2[rng.randrange(na)] for _ in range(na)]
        sb = [b2[rng.randrange(nb)] for _ in range(nb)]
        diffs.append(statistics.median(sa) - statistics.median(sb))
    diffs.sort()
    lo = diffs[int((alpha / 2) * (iters - 1))]
    hi = diffs[int((1 - alpha / 2) * (iters - 1))]
    return statistics.median(a2) - statistics.median(b2), lo, hi


def fmt_opt(x: Optional[float], digits: int = 3) -> str:
    if x is None:
        return "NA"
    return f"{x:.{digits}f}"


def fmt_seconds(sec: Optional[float]) -> str:
    if sec is None:
        return "NA"
    if sec >= 120:
        return f"{sec / 60.0:.1f}m"
    return f"{sec:.0f}s"


# -----------------------------
# Data model
# -----------------------------


@dataclass
class TechNRow:
    tech: str
    n: int

    stability_mean_pairwise_jaccard: Optional[float] = None
    stability_mean_pairwise_jaccard_ci_lo: Optional[float] = None
    stability_mean_pairwise_jaccard_ci_hi: Optional[float] = None

    final_set_size_mean: Optional[float] = None
    final_set_size_median: Optional[float] = None

    judge_plausible_rate: Optional[float] = None
    judge_not_plausible_rate: Optional[float] = None
    judge_n: int = 0

    silver_recall_proxy: Optional[float] = None
    silver_ref_size: int = 0

    convergence_mean: Optional[float] = None
    runtime_seconds_mean: Optional[float] = None


@dataclass
class MacroSummaryRow:
    n: int
    technologies: int

    stability_median: Optional[float] = None
    stability_mean: Optional[float] = None
    stability_mean_ci_lo: Optional[float] = None
    stability_mean_ci_hi: Optional[float] = None
    stability_mean_diff_vs_n1_ci_lo: Optional[float] = None
    stability_mean_diff_vs_n1_ci_hi: Optional[float] = None
    stability_median_diff_vs_n1_ci_lo: Optional[float] = None
    stability_median_diff_vs_n1_ci_hi: Optional[float] = None

    not_plausible_median: Optional[float] = None
    not_plausible_mean: Optional[float] = None
    not_plausible_mean_ci_lo: Optional[float] = None
    not_plausible_mean_ci_hi: Optional[float] = None
    not_plausible_mean_diff_vs_n1_ci_lo: Optional[float] = None
    not_plausible_mean_diff_vs_n1_ci_hi: Optional[float] = None
    not_plausible_median_diff_vs_n1_ci_lo: Optional[float] = None
    not_plausible_median_diff_vs_n1_ci_hi: Optional[float] = None
    not_plausible_pct_techs_improved_vs_n1: Optional[float] = None

    produced_materials_median: Optional[float] = None
    produced_materials_mean: Optional[float] = None
    produced_materials_mean_ci_lo: Optional[float] = None
    produced_materials_mean_ci_hi: Optional[float] = None
    produced_materials_mean_diff_vs_n1_ci_lo: Optional[float] = None
    produced_materials_mean_diff_vs_n1_ci_hi: Optional[float] = None
    produced_materials_median_diff_vs_n1_ci_lo: Optional[float] = None
    produced_materials_median_diff_vs_n1_ci_hi: Optional[float] = None

    silver_recall_median: Optional[float] = None
    silver_recall_mean: Optional[float] = None
    silver_recall_mean_ci_lo: Optional[float] = None
    silver_recall_mean_ci_hi: Optional[float] = None
    silver_recall_mean_diff_vs_n1_ci_lo: Optional[float] = None
    silver_recall_mean_diff_vs_n1_ci_hi: Optional[float] = None
    silver_recall_median_diff_vs_n1_ci_lo: Optional[float] = None
    silver_recall_median_diff_vs_n1_ci_hi: Optional[float] = None

    convergence_median: Optional[float] = None
    convergence_mean: Optional[float] = None
    convergence_mean_ci_lo: Optional[float] = None
    convergence_mean_ci_hi: Optional[float] = None
    convergence_mean_diff_vs_n1_ci_lo: Optional[float] = None
    convergence_mean_diff_vs_n1_ci_hi: Optional[float] = None
    convergence_median_diff_vs_n1_ci_lo: Optional[float] = None
    convergence_median_diff_vs_n1_ci_hi: Optional[float] = None

    runtime_median_seconds: Optional[float] = None
    runtime_mean_seconds: Optional[float] = None
    runtime_mean_ci_lo: Optional[float] = None
    runtime_mean_ci_hi: Optional[float] = None
    runtime_mean_diff_vs_n1_ci_lo: Optional[float] = None
    runtime_mean_diff_vs_n1_ci_hi: Optional[float] = None
    runtime_median_diff_vs_n1_ci_lo: Optional[float] = None
    runtime_median_diff_vs_n1_ci_hi: Optional[float] = None


# -----------------------------
# Metric computations
# -----------------------------


def compute_stability_and_size_from_transcripts(
    transcript_paths: Sequence[str],
    *,
    seed: int,
    iters: int,
    alpha: float,
) -> Tuple[
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
]:
    """
    Returns:
      (mean_pairwise_jaccard, ci_lo, ci_hi, mean_set_size, median_set_size)
    """
    sets: List[List[str]] = []
    sizes: List[float] = []

    for p in transcript_paths:
        try:
            txt = Path(p).read_text(encoding="utf-8")
        except Exception:
            continue
        mats = extract_stage2_final_materials_from_transcript_txt(txt)
        canon = sorted({canonicalize_material(m) for m in mats if canonicalize_material(m)})
        sets.append(canon)
        sizes.append(float(len(canon)))

    mean_size = safe_mean(sizes)
    median_size = safe_median(sizes)

    if len(sets) < 2:
        return None, None, None, mean_size, median_size

    js = pairwise_jaccards(sets)
    m, lo, hi = bootstrap_mean_ci(js, seed=seed, iters=iters, alpha=alpha)
    return m, lo, hi, mean_size, median_size


def compute_convergence_mean_from_transcripts(transcript_paths: Sequence[str]) -> Optional[float]:
    scores: List[float] = []
    for p in transcript_paths:
        try:
            txt = Path(p).read_text(encoding="utf-8")
        except Exception:
            continue
        scores.extend(parse_convergence_scores_best_effort(txt))
    return safe_mean(scores)


def compute_runtime_mean_from_logs(log_paths: Sequence[str]) -> Optional[float]:
    vals: List[float] = []
    for p in log_paths:
        try:
            txt = Path(p).read_text(encoding="utf-8")
        except Exception:
            continue
        rt = parse_runtime_seconds_from_log_text(txt)
        if rt is not None:
            vals.append(rt)
    return safe_mean(vals)


def compute_plausibility_for_tech_cfgs(
    judge_rows: Sequence[Dict[str, Any]],
    tech: str,
    cfgs: Sequence[str],
) -> Tuple[Optional[float], Optional[float], int]:
    cfg_set = {c.lower() for c in cfgs}
    used = 0
    plausible_true = 0
    for r in judge_rows:
        t = str(r.get("technology") or "").strip()
        c = str(r.get("config") or "").strip().lower()
        if t != tech or c not in cfg_set:
            continue
        tup = extract_plausible_material_from_judge_row(r)
        if not tup:
            continue
        _, _, _, plausible = tup
        used += 1
        if plausible:
            plausible_true += 1
    if used == 0:
        return None, None, 0
    pr = plausible_true / used
    return pr, 1.0 - pr, used


def build_silver_reference_by_tech(judge_rows: Sequence[Dict[str, Any]]) -> Dict[str, set]:
    """
    Build per-tech silver reference: union of judged-plausible materials across all configs.
    """
    ref: Dict[str, set] = {}
    for r in judge_rows:
        tup = extract_plausible_material_from_judge_row(r)
        if not tup:
            continue
        tech, _, mat_raw, plausible = tup
        if not plausible:
            continue
        ref.setdefault(tech, set()).add(canonicalize_material(mat_raw))
    return ref


def compute_silver_recall_proxy(
    transcript_paths: Sequence[str],
    silver_ref: set,
) -> Optional[float]:
    if not silver_ref:
        return None
    union_set: set = set()
    for p in transcript_paths:
        try:
            txt = Path(p).read_text(encoding="utf-8")
        except Exception:
            continue
        mats = extract_stage2_final_materials_from_transcript_txt(txt)
        for m in mats:
            cm = canonicalize_material(m)
            if cm:
                union_set.add(cm)
    if not union_set:
        return 0.0
    return len(union_set & silver_ref) / len(silver_ref)


# -----------------------------
# Macro aggregation & recommendation
# -----------------------------


def macro_summarize(
    tech_rows: Sequence[TechNRow],
    *,
    seed: int,
    iters: int,
    alpha: float,
) -> List[MacroSummaryRow]:
    by_n: Dict[int, List[TechNRow]] = {}
    for r in tech_rows:
        by_n.setdefault(r.n, []).append(r)

    ns = sorted(by_n.keys())
    summaries: Dict[int, MacroSummaryRow] = {}

    def vals(
        rows: Sequence[TechNRow], getter: Callable[[TechNRow], Optional[float]]
    ) -> List[float]:
        out: List[float] = []
        for rr in rows:
            v = getter(rr)
            if isinstance(v, (int, float)) and not math.isnan(v):
                out.append(float(v))
        return out

    for n in ns:
        rows_n = by_n[n]
        s = MacroSummaryRow(n=n, technologies=len({r.tech for r in rows_n}))

        st = vals(rows_n, lambda r: r.stability_mean_pairwise_jaccard)
        np = vals(rows_n, lambda r: r.judge_not_plausible_rate)
        prod = vals(rows_n, lambda r: r.final_set_size_mean)
        silv = vals(rows_n, lambda r: r.silver_recall_proxy)
        conv = vals(rows_n, lambda r: r.convergence_mean)
        rt = vals(rows_n, lambda r: r.runtime_seconds_mean)

        s.stability_median = safe_median(st)
        s.stability_mean, s.stability_mean_ci_lo, s.stability_mean_ci_hi = bootstrap_mean_ci(
            st, seed=seed, iters=iters, alpha=alpha
        )

        s.not_plausible_median = safe_median(np)
        s.not_plausible_mean, s.not_plausible_mean_ci_lo, s.not_plausible_mean_ci_hi = (
            bootstrap_mean_ci(np, seed=seed, iters=iters, alpha=alpha)
        )

        s.produced_materials_median = safe_median(prod)
        (
            s.produced_materials_mean,
            s.produced_materials_mean_ci_lo,
            s.produced_materials_mean_ci_hi,
        ) = bootstrap_mean_ci(prod, seed=seed, iters=iters, alpha=alpha)

        s.silver_recall_median = safe_median(silv)
        s.silver_recall_mean, s.silver_recall_mean_ci_lo, s.silver_recall_mean_ci_hi = (
            bootstrap_mean_ci(silv, seed=seed, iters=iters, alpha=alpha)
        )

        s.convergence_median = safe_median(conv)
        s.convergence_mean, s.convergence_mean_ci_lo, s.convergence_mean_ci_hi = bootstrap_mean_ci(
            conv, seed=seed, iters=iters, alpha=alpha
        )

        s.runtime_median_seconds = safe_median(rt)
        s.runtime_mean_seconds, s.runtime_mean_ci_lo, s.runtime_mean_ci_hi = bootstrap_mean_ci(
            rt, seed=seed, iters=iters, alpha=alpha
        )

        summaries[n] = s

    # Deltas vs N=1
    if 1 in by_n:
        base_rows = by_n[1]
        base_st = vals(base_rows, lambda r: r.stability_mean_pairwise_jaccard)
        base_np = vals(base_rows, lambda r: r.judge_not_plausible_rate)
        base_prod = vals(base_rows, lambda r: r.final_set_size_mean)
        base_silv = vals(base_rows, lambda r: r.silver_recall_proxy)
        base_conv = vals(base_rows, lambda r: r.convergence_mean)
        base_rt = vals(base_rows, lambda r: r.runtime_seconds_mean)

        base_np_by_tech: Dict[str, float] = {}
        for rr in base_rows:
            if rr.judge_not_plausible_rate is not None:
                base_np_by_tech[rr.tech] = float(rr.judge_not_plausible_rate)

        for n in ns:
            if n == 1:
                continue
            s = summaries[n]
            rows_n = by_n[n]
            st = vals(rows_n, lambda r: r.stability_mean_pairwise_jaccard)
            np = vals(rows_n, lambda r: r.judge_not_plausible_rate)
            prod = vals(rows_n, lambda r: r.final_set_size_mean)
            silv = vals(rows_n, lambda r: r.silver_recall_proxy)
            conv = vals(rows_n, lambda r: r.convergence_mean)
            rt = vals(rows_n, lambda r: r.runtime_seconds_mean)

            _, s.stability_mean_diff_vs_n1_ci_lo, s.stability_mean_diff_vs_n1_ci_hi = (
                bootstrap_mean_diff_ci(st, base_st, seed=seed, iters=iters, alpha=alpha)
            )
            _, s.not_plausible_mean_diff_vs_n1_ci_lo, s.not_plausible_mean_diff_vs_n1_ci_hi = (
                bootstrap_mean_diff_ci(np, base_np, seed=seed, iters=iters, alpha=alpha)
            )
            (
                _,
                s.produced_materials_mean_diff_vs_n1_ci_lo,
                s.produced_materials_mean_diff_vs_n1_ci_hi,
            ) = bootstrap_mean_diff_ci(prod, base_prod, seed=seed, iters=iters, alpha=alpha)
            _, s.silver_recall_mean_diff_vs_n1_ci_lo, s.silver_recall_mean_diff_vs_n1_ci_hi = (
                bootstrap_mean_diff_ci(silv, base_silv, seed=seed, iters=iters, alpha=alpha)
            )
            _, s.convergence_mean_diff_vs_n1_ci_lo, s.convergence_mean_diff_vs_n1_ci_hi = (
                bootstrap_mean_diff_ci(conv, base_conv, seed=seed, iters=iters, alpha=alpha)
            )
            _, s.runtime_mean_diff_vs_n1_ci_lo, s.runtime_mean_diff_vs_n1_ci_hi = (
                bootstrap_mean_diff_ci(rt, base_rt, seed=seed, iters=iters, alpha=alpha)
            )

            _, s.stability_median_diff_vs_n1_ci_lo, s.stability_median_diff_vs_n1_ci_hi = (
                bootstrap_median_diff_ci(st, base_st, seed=seed, iters=iters, alpha=alpha)
            )
            _, s.not_plausible_median_diff_vs_n1_ci_lo, s.not_plausible_median_diff_vs_n1_ci_hi = (
                bootstrap_median_diff_ci(np, base_np, seed=seed, iters=iters, alpha=alpha)
            )
            (
                _,
                s.produced_materials_median_diff_vs_n1_ci_lo,
                s.produced_materials_median_diff_vs_n1_ci_hi,
            ) = bootstrap_median_diff_ci(prod, base_prod, seed=seed, iters=iters, alpha=alpha)
            _, s.silver_recall_median_diff_vs_n1_ci_lo, s.silver_recall_median_diff_vs_n1_ci_hi = (
                bootstrap_median_diff_ci(silv, base_silv, seed=seed, iters=iters, alpha=alpha)
            )
            _, s.convergence_median_diff_vs_n1_ci_lo, s.convergence_median_diff_vs_n1_ci_hi = (
                bootstrap_median_diff_ci(conv, base_conv, seed=seed, iters=iters, alpha=alpha)
            )
            _, s.runtime_median_diff_vs_n1_ci_lo, s.runtime_median_diff_vs_n1_ci_hi = (
                bootstrap_median_diff_ci(rt, base_rt, seed=seed, iters=iters, alpha=alpha)
            )

            # % techs improved in not-plausible rate (lower is better)
            improved = 0
            comparable = 0
            for rr in rows_n:
                if rr.judge_not_plausible_rate is None:
                    continue
                b = base_np_by_tech.get(rr.tech)
                if b is None:
                    continue
                comparable += 1
                if float(rr.judge_not_plausible_rate) < b:
                    improved += 1
            if comparable:
                s.not_plausible_pct_techs_improved_vs_n1 = 100.0 * improved / comparable

    return [summaries[n] for n in ns]


def recommend_n(
    summaries: Sequence[MacroSummaryRow],
    *,
    max_not_plausible: Optional[float],
    min_final_convergence: Optional[float],
    max_runtime_seconds: Optional[float],
    stability_within_frac_of_best: float,
    require_plausibility_present: bool,
) -> Tuple[Optional[int], str]:
    """
    Same idea as Stage 1:
    1) Filter by constraints (macro-median metrics when present)
    2) Choose smallest N whose stability_median is within frac-of-best of best feasible stability_median,
       breaking ties by lower runtime then smaller N.

    Guardrail:
      If require_plausibility_present is True, we restrict consideration to Ns where
      not_plausible_median is non-NA (i.e., plausibility exists at the macro level).
      This prevents N=1 from distorting constraints in mixed runs where N=1 may map to
      configs that were not judged for Stage 2 materials plausibility.
    """
    reasons: List[str] = []
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
        f"Near-best stability requirement: stability_median >= best_feasible_stability * {stability_within_frac_of_best:.3f}"
    )
    reasons.append(
        f"Guardrail: require plausibility present (not_plausible_median non-NA): {require_plausibility_present}"
    )
    reasons.append("")

    candidates_pool: List[MacroSummaryRow] = list(summaries)
    if require_plausibility_present:
        candidates_pool = [s for s in candidates_pool if s.not_plausible_median is not None]

    feasible: List[MacroSummaryRow] = []
    excluded: List[Tuple[int, str]] = []

    for s in candidates_pool:
        if max_not_plausible is not None and s.not_plausible_median is not None:
            if s.not_plausible_median > max_not_plausible:
                excluded.append((s.n, "not_plausible_median"))
                continue
        if min_final_convergence is not None and s.convergence_median is not None:
            if s.convergence_median < min_final_convergence:
                excluded.append((s.n, "final_convergence_median"))
                continue
        if max_runtime_seconds is not None and s.runtime_median_seconds is not None:
            if s.runtime_median_seconds > max_runtime_seconds:
                excluded.append((s.n, "runtime_median_seconds"))
                continue
        feasible.append(s)

    if not feasible:
        if require_plausibility_present:
            reasons.append(
                "Feasible set after plausibility guardrail: (empty). "
                "This likely means no N has judge-based plausibility at the macro level."
            )
        else:
            reasons.append("Feasible set: (empty).")

        if excluded:
            reasons.append(
                "Excluded Ns: " + ", ".join(f"N={n} ({why})" for n, why in excluded) + "."
            )
        reasons.append("")
        reasons.append("Result: no recommendation (insufficient feasible data).")
        return None, "\n".join(reasons) + "\n"

    stabs = [s.stability_median for s in feasible if s.stability_median is not None]
    if not stabs:
        reasons.append("")
        reasons.append("Result: no recommendation (feasible set has no stability_median values).")
        return None, "\n".join(reasons) + "\n"

    best = max(stabs)
    threshold = best * stability_within_frac_of_best
    reasons.append(f"Best feasible stability_median: {best:.3f}")
    reasons.append(f"Stability threshold (near-best): {threshold:.3f}")

    near_best = [
        s for s in feasible if s.stability_median is not None and s.stability_median >= threshold
    ]
    if not near_best:
        reasons.append("")
        reasons.append(
            "Result: no recommendation (no feasible N meets near-best stability threshold)."
        )
        return None, "\n".join(reasons) + "\n"

    # Prefer smallest N, break ties by runtime.
    def key(s: MacroSummaryRow) -> Tuple[int, float]:
        rt = s.runtime_median_seconds if s.runtime_median_seconds is not None else float("inf")
        return (s.n, rt)

    chosen = sorted(near_best, key=key)[0]
    reasons.append("")
    reasons.append(
        "Near-best candidates: "
        + ", ".join(
            f"N={s.n} (stability_median={fmt_opt(s.stability_median, 3)}, runtime_median={fmt_seconds(s.runtime_median_seconds)})"
            for s in sorted(near_best, key=lambda x: x.n)
        )
        + "."
    )
    reasons.append("")
    reasons.append(
        f"Selected: N={chosen.n} (smallest N among near-best candidates; runtime_median={fmt_seconds(chosen.runtime_median_seconds)})."
    )

    return chosen.n, "\n".join(reasons) + "\n"


# -----------------------------
# Rendering: Markdown tables
# -----------------------------


def render_per_tech_md_table(rows: Sequence[TechNRow]) -> str:
    cols: List[Tuple[str, Callable[[TechNRow], str]]] = [
        ("Technology", lambda r: r.tech),
        ("N", lambda r: str(r.n)),
        ("Stability Jaccard (mean)", lambda r: fmt_opt(r.stability_mean_pairwise_jaccard, 3)),
        ("Stability CI lo", lambda r: fmt_opt(r.stability_mean_pairwise_jaccard_ci_lo, 3)),
        ("Stability CI hi", lambda r: fmt_opt(r.stability_mean_pairwise_jaccard_ci_hi, 3)),
        ("#Materials mean", lambda r: fmt_opt(r.final_set_size_mean, 2)),
        ("#Materials median", lambda r: fmt_opt(r.final_set_size_median, 2)),
        ("Not-plausible rate", lambda r: fmt_opt(r.judge_not_plausible_rate, 3)),
        ("Plausible rate", lambda r: fmt_opt(r.judge_plausible_rate, 3)),
        ("Judge n", lambda r: str(r.judge_n)),
        ("Silver recall proxy", lambda r: fmt_opt(r.silver_recall_proxy, 3)),
        ("Silver ref size", lambda r: str(r.silver_ref_size)),
        ("Convergence mean", lambda r: fmt_opt(r.convergence_mean, 3)),
        ("Runtime mean", lambda r: fmt_seconds(r.runtime_seconds_mean)),
    ]

    lines: List[str] = []
    lines.append("| " + " | ".join(c[0] for c in cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for r in rows:
        lines.append("| " + " | ".join(c[1](r) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def render_macro_md_table(summaries: Sequence[MacroSummaryRow]) -> str:
    """
    Macro-summary table patterned after Stage 1 (but with materials metrics).
    """
    header = (
        "| N | Techs | Stability (median) | Stability (mean) | Stability mean 95% CI | "
        "Δ Stability mean vs N=1 (95% CI) | Δ Stability median vs N=1 (95% CI) | "
        "Not-plausible (median) | Not-plausible (mean) | Not-plausible mean 95% CI | "
        "Δ Not-plausible mean vs N=1 (95% CI) | Δ Not-plausible median vs N=1 (95% CI) | "
        "% techs improved (invalid) | Precision (median) | Precision (mean) | "
        "#Materials (median) | #Materials (mean) | #Materials mean 95% CI | "
        "Δ #Materials mean vs N=1 (95% CI) | Δ #Materials median vs N=1 (95% CI) | "
        "Silver recall (median) | Silver recall (mean) | Silver recall mean 95% CI | "
        "Δ Silver recall mean vs N=1 (95% CI) | Δ Silver recall median vs N=1 (95% CI) | "
        "Final conv (median) | Final conv (mean) | Final conv mean 95% CI | "
        "Δ Final conv mean vs N=1 (95% CI) | Δ Final conv median vs N=1 (95% CI) | "
        "Runtime (median) | Runtime (mean) | Runtime mean 95% CI | "
        "Δ Runtime mean vs N=1 (95% CI) | Δ Runtime median vs N=1 (95% CI) |"
    )
    sep = "|---:|---:|" + "|".join(["---:"] * (header.count("|") - 3)) + "|"

    lines: List[str] = []
    lines.append(header)
    lines.append(sep)

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

        np_ci = (
            "NA"
            if s.not_plausible_mean_ci_lo is None or s.not_plausible_mean_ci_hi is None
            else f"[{s.not_plausible_mean_ci_lo:.3f}, {s.not_plausible_mean_ci_hi:.3f}]"
        )
        np_diff_ci = (
            "NA"
            if s.not_plausible_mean_diff_vs_n1_ci_lo is None
            or s.not_plausible_mean_diff_vs_n1_ci_hi is None
            else f"[{s.not_plausible_mean_diff_vs_n1_ci_lo:.3f}, {s.not_plausible_mean_diff_vs_n1_ci_hi:.3f}]"
        )
        np_median_diff_ci = (
            "NA"
            if s.not_plausible_median_diff_vs_n1_ci_lo is None
            or s.not_plausible_median_diff_vs_n1_ci_hi is None
            else f"[{s.not_plausible_median_diff_vs_n1_ci_lo:.3f}, {s.not_plausible_median_diff_vs_n1_ci_hi:.3f}]"
        )
        np_pct = (
            "NA"
            if s.not_plausible_pct_techs_improved_vs_n1 is None
            else f"{s.not_plausible_pct_techs_improved_vs_n1:.1f}%"
        )

        prod_ci = (
            "NA"
            if s.produced_materials_mean_ci_lo is None or s.produced_materials_mean_ci_hi is None
            else f"[{s.produced_materials_mean_ci_lo:.2f}, {s.produced_materials_mean_ci_hi:.2f}]"
        )
        prod_diff_ci = (
            "NA"
            if s.produced_materials_mean_diff_vs_n1_ci_lo is None
            or s.produced_materials_mean_diff_vs_n1_ci_hi is None
            else f"[{s.produced_materials_mean_diff_vs_n1_ci_lo:.2f}, {s.produced_materials_mean_diff_vs_n1_ci_hi:.2f}]"
        )
        prod_median_diff_ci = (
            "NA"
            if s.produced_materials_median_diff_vs_n1_ci_lo is None
            or s.produced_materials_median_diff_vs_n1_ci_hi is None
            else f"[{s.produced_materials_median_diff_vs_n1_ci_lo:.2f}, {s.produced_materials_median_diff_vs_n1_ci_hi:.2f}]"
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
            if s.convergence_mean_ci_lo is None or s.convergence_mean_ci_hi is None
            else f"[{s.convergence_mean_ci_lo:.3f}, {s.convergence_mean_ci_hi:.3f}]"
        )
        conv_diff_ci = (
            "NA"
            if s.convergence_mean_diff_vs_n1_ci_lo is None
            or s.convergence_mean_diff_vs_n1_ci_hi is None
            else f"[{s.convergence_mean_diff_vs_n1_ci_lo:.3f}, {s.convergence_mean_diff_vs_n1_ci_hi:.3f}]"
        )
        conv_median_diff_ci = (
            "NA"
            if s.convergence_median_diff_vs_n1_ci_lo is None
            or s.convergence_median_diff_vs_n1_ci_hi is None
            else f"[{s.convergence_median_diff_vs_n1_ci_lo:.3f}, {s.convergence_median_diff_vs_n1_ci_hi:.3f}]"
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

        precision_median = (
            None if s.not_plausible_median is None else (1.0 - s.not_plausible_median)
        )
        precision_mean = None if s.not_plausible_mean is None else (1.0 - s.not_plausible_mean)

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
                    fmt_opt(s.not_plausible_median, 3),
                    fmt_opt(s.not_plausible_mean, 3),
                    np_ci,
                    np_diff_ci,
                    np_median_diff_ci,
                    np_pct,
                    fmt_opt(precision_median, 3),
                    fmt_opt(precision_mean, 3),
                    fmt_opt(s.produced_materials_median, 2),
                    fmt_opt(s.produced_materials_mean, 2),
                    prod_ci,
                    prod_diff_ci,
                    prod_median_diff_ci,
                    fmt_opt(s.silver_recall_median, 3),
                    fmt_opt(s.silver_recall_mean, 3),
                    silver_ci,
                    silver_diff_ci,
                    silver_median_diff_ci,
                    fmt_opt(s.convergence_median, 3),
                    fmt_opt(s.convergence_mean, 3),
                    conv_ci,
                    conv_diff_ci,
                    conv_median_diff_ci,
                    fmt_seconds(s.runtime_median_seconds),
                    fmt_seconds(s.runtime_mean_seconds),
                    runtime_ci,
                    runtime_diff_ci,
                    runtime_median_diff_ci,
                ]
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


# -----------------------------
# CSV writers
# -----------------------------


def write_techn_csv(path: str, rows: Sequence[TechNRow]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "technology",
                "n",
                "stability_mean_pairwise_jaccard",
                "stability_mean_pairwise_jaccard_ci_lo",
                "stability_mean_pairwise_jaccard_ci_hi",
                "final_set_size_mean",
                "final_set_size_median",
                "judge_plausible_rate",
                "judge_not_plausible_rate",
                "judge_n",
                "silver_recall_proxy",
                "silver_ref_size",
                "convergence_mean",
                "runtime_seconds_mean",
            ],
        )
        w.writeheader()
        for r in rows:
            d = asdict(r)
            d["technology"] = d.pop("tech")
            w.writerow(d)


def write_by_n_csv(path: str, rows: Sequence[MacroSummaryRow]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()) if rows else ["n"])
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


# -----------------------------
# Main
# -----------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 2 materials sweet-spot tradeoff analysis.")
    ap.add_argument(
        "--transcripts-dir", default="output/transcripts", help="Transcript TXT directory."
    )
    ap.add_argument(
        "--judge-jsonl",
        default="output/analysis/final_only_material_verification_ALL_by_config.jsonl",
        help="Materials judge JSONL (from verify_pruned_materials.py).",
    )
    ap.add_argument(
        "--logs-glob", default="output/logs/*.log", help="Glob for run logs (optional runtime)."
    )

    ap.add_argument(
        "--configs",
        nargs="*",
        default=[],
        help="Optional filter of config tags to include (space-separated). If omitted, inferred from transcripts.",
    )
    ap.add_argument(
        "--tech",
        action="append",
        default=[],
        help="Optional technology filter (repeatable). If omitted, include all discovered techs.",
    )

    ap.add_argument(
        "--no-stability",
        action="store_true",
        help="Disable stability computation (from transcripts).",
    )
    ap.add_argument(
        "--no-silver",
        action="store_true",
        help="Disable silver recall proxy computation.",
    )
    ap.add_argument(
        "--no-convergence",
        action="store_true",
        help="Disable convergence computation (best-effort from transcripts).",
    )
    ap.add_argument(
        "--no-runtime",
        action="store_true",
        help="Disable runtime computation (from logs).",
    )

    ap.add_argument("--seed", type=int, default=0, help="Random seed for bootstraps.")
    ap.add_argument("--bootstrap-iters", type=int, default=2000, help="Bootstrap iterations.")
    ap.add_argument(
        "--bootstrap-alpha",
        type=float,
        default=0.05,
        help="Bootstrap alpha for 95%% CI (default 0.05).",
    )

    ap.add_argument(
        "--out-md",
        default="output/analysis/stage2_materials_sweet_spot_tradeoffs.md",
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
        help="Optional by-N macro summary CSV output path (for plotting).",
    )

    # Recommendation constraints (macro-median metrics)
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
        help="Choose smallest N within this fraction of best feasible macro-median stability (default 0.98).",
    )
    ap.add_argument(
        "--recommend-require-plausibility-present",
        action="store_true",
        help=(
            "Guardrail: compute recommendation using only Ns where macro not_plausible_median is non-NA "
            + "(i.e., plausibility exists). This avoids N=1 distorting constraints when it has no judged plausibility."
        ),
    )

    ap.add_argument(
        "--debug-discovery",
        action="store_true",
        help="Print discovered technologies/configs and derived N mapping.",
    )

    args = ap.parse_args()
    random.seed(args.seed)

    transcripts_dir = Path(args.transcripts_dir)
    judge_path = Path(args.judge_jsonl)

    # Load judge rows (optional but expected)
    judge_rows: List[Dict[str, Any]] = []
    if judge_path.exists():
        judge_rows = load_jsonl(judge_path)

    # Discover transcripts and index by (tech, cfg)
    transcript_paths = sorted(glob.glob(str(transcripts_dir / "*.txt")))
    by_tech_cfg: Dict[Tuple[str, str], List[str]] = {}
    for p in transcript_paths:
        tech, cfg = parse_transcript_filename_to_tech_cfg(p)
        by_tech_cfg.setdefault((tech, cfg), []).append(p)

    discovered_techs = sorted({t for (t, _) in by_tech_cfg.keys() if t and t != "unknown"})
    discovered_cfgs = sorted({c for (_, c) in by_tech_cfg.keys() if c and c != "unknown"})

    techs = discovered_techs
    if args.tech:
        allow = set(args.tech)
        techs = [t for t in discovered_techs if t in allow]

    cfgs = [c.lower() for c in (args.configs or discovered_cfgs)]
    cfgs_set = set(cfgs)

    # Map N -> configs, but only configs present in transcripts (or specified)
    cfgs_by_n: Dict[int, List[str]] = {}
    unparseable: List[str] = []
    for c in sorted(cfgs_set):
        n = materials_agent_count_from_config_tag(c)
        if n is None:
            unparseable.append(c)
            continue
        cfgs_by_n.setdefault(n, []).append(c)

    if args.debug_discovery:
        print("[debug] discovered technologies:", len(discovered_techs))
        for t in discovered_techs:
            print("  -", t)
        print("[debug] discovered configs:", discovered_cfgs)
        if args.configs:
            print("[debug] using --configs filter:", cfgs)
        if unparseable:
            print("[debug] unparseable configs:", unparseable)
        print("[debug] materials N -> configs:")
        for n in sorted(cfgs_by_n.keys()):
            print(f"  N={n}: {sorted(cfgs_by_n[n])}")

    if not cfgs_by_n:
        raise SystemExit(
            "No parseable configs for materials N. Check transcript filenames or pass --configs."
        )

    # Silver reference per tech (optional)
    silver_ref_by_tech: Dict[str, set] = {}
    if (not args.no_silver) and judge_rows:
        silver_ref_by_tech = build_silver_reference_by_tech(judge_rows)

    # Logs by config (optional)
    logs_by_cfg: Dict[str, List[str]] = {}
    if not args.no_runtime and args.logs_glob:
        for lp in sorted(glob.glob(args.logs_glob)):
            cfg = parse_config_from_filename_anywhere(lp)
            logs_by_cfg.setdefault(cfg, []).append(lp)

    # Compute per-(tech,N)
    tech_rows: List[TechNRow] = []
    for tech in techs:
        for n in sorted(cfgs_by_n.keys()):
            cfgs_for_n = cfgs_by_n[n]

            # Gather transcripts for this (tech, any cfg in cfgs_for_n)
            tps: List[str] = []
            for c in cfgs_for_n:
                tps.extend(by_tech_cfg.get((tech, c), []))

            row = TechNRow(tech=tech, n=n)

            if not args.no_stability:
                m, lo, hi, sz_mean, sz_med = compute_stability_and_size_from_transcripts(
                    tps, seed=args.seed, iters=args.bootstrap_iters, alpha=args.bootstrap_alpha
                )
                row.stability_mean_pairwise_jaccard = m
                row.stability_mean_pairwise_jaccard_ci_lo = lo
                row.stability_mean_pairwise_jaccard_ci_hi = hi
                row.final_set_size_mean = sz_mean
                row.final_set_size_median = sz_med
            else:
                # Still compute sizes if stability disabled? Keep consistent with Stage 1: stability block also did size.
                pass

            if judge_rows:
                pr, npr, used = compute_plausibility_for_tech_cfgs(judge_rows, tech, cfgs_for_n)
                row.judge_plausible_rate = pr
                row.judge_not_plausible_rate = npr
                row.judge_n = used

            if not args.no_silver:
                ref = silver_ref_by_tech.get(tech, set())
                row.silver_ref_size = len(ref)
                row.silver_recall_proxy = compute_silver_recall_proxy(tps, ref)

            if not args.no_convergence:
                row.convergence_mean = compute_convergence_mean_from_transcripts(tps)

            if not args.no_runtime:
                lps: List[str] = []
                for c in cfgs_for_n:
                    lps.extend(logs_by_cfg.get(c, []))
                row.runtime_seconds_mean = compute_runtime_mean_from_logs(lps)

            tech_rows.append(row)

    tech_rows.sort(key=lambda r: (r.tech, r.n))

    # Macro summaries + recommendation
    summaries = macro_summarize(
        tech_rows, seed=args.seed, iters=args.bootstrap_iters, alpha=args.bootstrap_alpha
    )
    rec_n, rec_md = recommend_n(
        summaries,
        max_not_plausible=args.max_not_plausible,
        min_final_convergence=args.min_final_convergence,
        max_runtime_seconds=args.max_runtime_seconds,
        stability_within_frac_of_best=args.stability_within_frac_of_best,
        require_plausibility_present=args.recommend_require_plausibility_present
        or (args.max_not_plausible is not None),
    )

    # Write optional CSVs
    if args.out_techn_csv:
        write_techn_csv(args.out_techn_csv, tech_rows)
        print(f"Wrote: {args.out_techn_csv}")
    if args.out_by_n_csv:
        write_by_n_csv(args.out_by_n_csv, summaries)
        print(f"Wrote: {args.out_by_n_csv}")

    # Markdown report
    md: List[str] = []
    md.append("# Stage 2 Materials Sweet-Spot Tradeoffs")
    md.append("")
    md.append(
        "This report summarizes stability, plausibility, silver recall proxy, convergence, and runtime by materials agent-count `N`."
    )
    md.append("")
    md.append("## Per-technology metrics by N")
    md.append("")
    md.append(render_per_tech_md_table(tech_rows))
    md.append("")
    md.append("## Macro summary by N")
    md.append("")
    md.append(render_macro_md_table(summaries))
    md.append("")
    md.append("## Recommended sweet-spot N")
    md.append("")
    md.append(f"Recommended N: {rec_n if rec_n is not None else 'NA'}")
    md.append("")
    md.append(rec_md)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote: {out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
