#!/usr/bin/env python3
"""
Analyze debate convergence metrics grouped by agent-count configuration from transcripts.

This script is designed for the transcript format produced by STDN Agentic and focuses on:
- extracting per-transcript convergence scores across rounds
- grouping transcripts by configuration tag (e.g., d2v1v1, d3v1v1, d5v1v1, v1v1v1, v1d12d19, d5v1d9, etc.)
- summarizing convergence outcomes per configuration

Key outputs:
- Console summary tables
- Optional CSV written under output/analysis/

Expected inputs:
- Transcript TXT files under: output/transcripts/
  Filenames typically include config tags and timestamps, e.g.:
    Smartphone_d3v1v1_20260211_170612.txt
    Electric_Vehicle_Motor_v1v1v1_20260211_165842.txt

Usage:
  uv run python scripts/analyze_convergence_by_agent_count.py

  uv run python scripts/analyze_convergence_by_agent_count.py \
    --transcripts-dir output/transcripts \
    --out-csv output/analysis/convergence_by_config.csv

Notes:
- Convergence extraction is best-effort:
  We look for "Convergence:" patterns in the transcript text and interpret values as either
  percentages (e.g. "86.4%") or decimals (e.g. "0.864").
- Some transcripts (especially non-debate / single-agent configs) may not include convergence
  lines; those are counted but excluded from convergence-stat aggregates unless you pass
  --include-missing.
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable

# Config tag token: 'v' or 'd' + 1-2 digits, repeated 3 times (stage order).
# Examples: v1v1v1, d3v1v1, v1d12d19, d5v1d9
_RX_CFG_TOKEN = re.compile(r"(?:^|[_\s])((?:[vd]\d{1,2}){3})(?:$|[_\s])", re.IGNORECASE)

# Convergence patterns in transcripts.
# We support either:
#   "Convergence: 86.4%"
#   "Final Convergence: 0.864"
#   "Final Convergence: 86.4%"
_RX_CONV = re.compile(r"Convergence[:\s]+(\d+(?:\.\d+)?)%?", re.IGNORECASE)


@dataclass(frozen=True)
class TranscriptRecord:
    path: Path
    technology_label: str  # as inferred from filename
    config: str  # extracted config tag or "unknown"
    convergence_scores: list[float]  # decimals in [0,1], one per match
    rounds: int  # inferred rounds completed (best-effort)


def iter_transcript_files(transcripts_dir: Path) -> Iterable[Path]:
    yield from sorted(transcripts_dir.glob("*.txt"))


def parse_config_from_filename(path: Path) -> str:
    """
    Extract config tag from filename using the token rule (3 tokens, each [vd][1-2 digits]).
    We treat underscores and spaces as token boundaries.
    """
    name = path.stem  # without .txt
    m = _RX_CFG_TOKEN.search(name)
    return m.group(1).lower() if m else "unknown"


def infer_technology_label_from_filename(path: Path) -> str:
    """
    Best-effort "technology label" for grouping/inspection.

    Typical filenames:
      <Tech>_<cfg>_<YYYYMMDD_HHMMSS>.txt
    We remove trailing timestamp and keep the rest.
    """
    stem = path.stem
    stem = re.sub(r"_\d{8}_\d{6}$", "", stem)  # strip timestamp
    # Convert underscores to spaces for readability
    return stem.replace("_", " ").strip()


def parse_rounds_best_effort(text: str) -> int:
    """
    Try to infer how many rounds occurred.
    - Prefer 'Rounds Completed: N' if present.
    - Else look for 'ROUND N' lines and take max.
    """
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
    """
    Extract convergence scores and normalize to decimals in [0,1].
    """
    scores: list[float] = []
    for raw in _RX_CONV.findall(text):
        try:
            v = float(raw)
        except ValueError:
            continue
        # Heuristic: if v > 1, assume it's a percent
        if v > 1.0:
            v = v / 100.0
        # Clip to [0,1] (best-effort)
        if v < 0.0:
            v = 0.0
        if v > 1.0:
            v = 1.0
        scores.append(v)
    return scores


def load_transcript(path: Path) -> TranscriptRecord:
    text = path.read_text(encoding="utf-8", errors="replace")
    tech_label = infer_technology_label_from_filename(path)
    cfg = parse_config_from_filename(path)
    conv = parse_convergence_scores(text)
    rounds = parse_rounds_best_effort(text)
    return TranscriptRecord(
        path=path,
        technology_label=tech_label,
        config=cfg,
        convergence_scores=conv,
        rounds=rounds,
    )


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def safe_mean(xs: list[float]) -> float:
    return mean(xs) if xs else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--transcripts-dir",
        default="output/transcripts",
        help="Directory containing transcript .txt files (default: output/transcripts).",
    )
    ap.add_argument(
        "--out-csv",
        default=None,
        help="Optional CSV output path (e.g., output/analysis/convergence_by_config.csv).",
    )
    ap.add_argument(
        "--include-missing",
        action="store_true",
        help="Include transcripts with no extracted convergence scores in aggregates (as zeros).",
    )
    args = ap.parse_args()

    transcripts_dir = Path(args.transcripts_dir)
    if not transcripts_dir.exists():
        raise SystemExit(f"Transcripts dir not found: {transcripts_dir}")

    records: list[TranscriptRecord] = []
    for p in iter_transcript_files(transcripts_dir):
        try:
            records.append(load_transcript(p))
        except Exception as e:
            print(f"ERROR reading {p}: {type(e).__name__}: {e}")

    if not records:
        print(f"No .txt transcripts found under {transcripts_dir}")
        return 0

    # Group by config
    by_cfg: dict[str, list[TranscriptRecord]] = {}
    for r in records:
        by_cfg.setdefault(r.config, []).append(r)

    # Summarize
    summary_rows: list[dict[str, object]] = []
    print("\nConvergence summary by config\n" + "-" * 40)
    for cfg, rs in sorted(by_cfg.items(), key=lambda kv: kv[0]):
        n_total = len(rs)
        n_with_scores = sum(1 for r in rs if r.convergence_scores)
        n_missing = n_total - n_with_scores

        initial_scores: list[float] = []
        final_scores: list[float] = []
        improvement: list[float] = []
        rounds: list[int] = []

        for r in rs:
            if r.convergence_scores:
                initial = r.convergence_scores[0]
                final = r.convergence_scores[-1]
            else:
                if not args.include_missing:
                    continue
                initial = 0.0
                final = 0.0

            initial_scores.append(initial)
            final_scores.append(final)
            improvement.append(final - initial)
            if r.rounds:
                rounds.append(r.rounds)

        avg_initial = safe_mean(initial_scores)
        avg_final = safe_mean(final_scores)
        avg_impr = safe_mean(improvement)
        avg_rounds = safe_mean([float(x) for x in rounds]) if rounds else 0.0

        print(
            f"{cfg:>8} | transcripts={n_total:>4} | with_scores={n_with_scores:>4} | "
            f"missing={n_missing:>4} | avg_initial={fmt_pct(avg_initial):>6} | "
            f"avg_final={fmt_pct(avg_final):>6} | avg_impr={fmt_pct(avg_impr):>7} | "
            f"avg_rounds={avg_rounds:.2f}"
        )

        summary_rows.append(
            {
                "config": cfg,
                "transcripts_total": n_total,
                "transcripts_with_convergence": n_with_scores,
                "transcripts_missing_convergence": n_missing,
                "avg_initial_convergence": avg_initial,
                "avg_final_convergence": avg_final,
                "avg_convergence_improvement": avg_impr,
                "avg_rounds": avg_rounds,
            }
        )

    # Optional CSV output
    if args.out_csv:
        out_path = Path(args.out_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "config",
            "transcripts_total",
            "transcripts_with_convergence",
            "transcripts_missing_convergence",
            "avg_initial_convergence",
            "avg_final_convergence",
            "avg_convergence_improvement",
            "avg_rounds",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for row in summary_rows:
                w.writerow(row)

        print(f"\nWrote CSV: {out_path}")

    # Helpful note for unknown configs
    if "unknown" in by_cfg:
        print(
            "\nNote: Some transcripts were grouped under config=unknown because their filenames "
            "did not contain a 3-token config tag like (v1v1v1, d3v1v1, v1d12d19, ...)."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
