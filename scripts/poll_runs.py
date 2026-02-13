#!/usr/bin/env python3
"""
Poll parallel run logs and report completion status.

This is intended to complement `stdn-parallel` runs, which produce per-run logs
like:

  output/v1v1v1_run1.log
  output/d3v1v1_run2.log
  output/d5v1v1_run3.log

The script prints a status table every N seconds until all runs are complete
(or until you stop it).

Stale detection:
- If a run is not DONE and its log file hasn't been modified in N seconds,
  the run is flagged as STALE so stalled runs are obvious.

Examples:
  # Default: poll all 3x3 runs every 120s
  python scripts/poll_runs.py

  # Poll only v1v1v1 (3 runs) every 30s
  python scripts/poll_runs.py --configs v1v1v1 --runs 3 --interval 30

  # Custom log directory (if you later move logs under output/logs/)
  python scripts/poll_runs.py --log-dir output/logs

  # Flag as STALE if no log updates for 10 minutes
  python scripts/poll_runs.py --stale-seconds 600
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DONE_MARKER = "✓ Successfully processed 5/5 technologies"


@dataclass(frozen=True)
class RunTarget:
    config: str
    run_num: int

    def log_path(self, log_dir: Path) -> Path:
        return log_dir / f"{self.config}_run{self.run_num}.log"


def _read_text(p: Path) -> str:
    try:
        return p.read_text(errors="ignore")
    except FileNotFoundError:
        return ""
    except Exception as e:
        # If file is being written while reading, keep going and show error.
        return f"<error reading {p}: {e}>"


def _is_done(log_text: str) -> bool:
    return DONE_MARKER in log_text


def _last_nonempty_line(log_text: str) -> str:
    if not log_text:
        return "<missing>"
    lines = log_text.splitlines()
    for line in reversed(lines):
        s = line.strip()
        if s:
            return s
    return "<empty>"


def iter_targets(configs: Iterable[str], runs: int) -> list[RunTarget]:
    targets: list[RunTarget] = []
    for cfg in configs:
        for n in range(1, runs + 1):
            targets.append(RunTarget(cfg, n))
    return targets


def _fmt_age(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def format_table(rows: list[tuple[str, str, str, str]]) -> str:
    """
    rows: list of (name, status, age, last_line)
    """
    name_w = max(len(r[0]) for r in rows) if rows else 0
    status_w = max(len(r[1]) for r in rows) if rows else 0
    age_w = max(len(r[2]) for r in rows) if rows else 0

    out = []
    out.append(f"{'run':<{name_w}}  {'status':<{status_w}}  {'age':<{age_w}}  last")
    out.append(f"{'-' * name_w}  {'-' * status_w}  {'-' * age_w}  {'-' * 4}")
    for name, status, age, last in rows:
        out.append(f"{name:<{name_w}}  {status:<{status_w}}  {age:<{age_w}}  {last}")
    return "\n".join(out)


def poll_once(
    targets: list[RunTarget],
    log_dir: Path,
    *,
    stale_seconds: int | None = None,
) -> tuple[bool, str]:
    """
    Returns: (all_done, formatted_report)

    stale_seconds:
      If set, runs that are not DONE and whose log file mtime is older than this
      threshold will be flagged as STALE.
    """
    rows: list[tuple[str, str, str, str]] = []
    all_done = True
    now = time.time()

    for t in targets:
        p = t.log_path(log_dir)
        txt = _read_text(p)
        done = _is_done(txt) if txt and not txt.startswith("<error reading") else False
        all_done = all_done and done

        # Age since last modification
        age_s: float | None = None
        try:
            age_s = now - p.stat().st_mtime
        except FileNotFoundError:
            age_s = None
        except Exception:
            age_s = None

        name = f"{t.config} run{t.run_num}"

        status = "DONE" if done else "RUNNING"
        if (
            (not done)
            and stale_seconds is not None
            and age_s is not None
            and age_s >= stale_seconds
        ):
            status = "STALE"

        last = _last_nonempty_line(txt)
        rows.append((name, status, _fmt_age(age_s), last))

    report = format_table(rows)
    return all_done, report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Poll parallel run log files and report completion status."
    )
    p.add_argument(
        "--configs",
        nargs="*",
        default=["v1v1v1", "d3v1v1", "d5v1v1"],
        help="Config types to poll (default: v1v1v1 d3v1v1 d5v1v1).",
    )
    p.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per config (default: 3).",
    )
    p.add_argument(
        "--log-dir",
        default="output",
        help="Directory containing per-run logs (default: output).",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=120,
        help="Polling interval in seconds (default: 120).",
    )
    p.add_argument(
        "--stale-seconds",
        type=int,
        default=600,
        help="Flag a run as STALE if its log hasn't been modified in this many seconds (default: 600).",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="Print one status snapshot and exit.",
    )
    p.add_argument(
        "--done-marker",
        default=DONE_MARKER,
        help="String that indicates completion in logs.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    global DONE_MARKER
    DONE_MARKER = args.done_marker

    log_dir = Path(args.log_dir)
    targets = iter_targets(args.configs, args.runs)

    stale_seconds = args.stale_seconds if args.stale_seconds and args.stale_seconds > 0 else None

    if args.once:
        all_done, report = poll_once(targets, log_dir, stale_seconds=stale_seconds)
        print(report)
        return 0 if all_done else 1

    print(f"Polling every {args.interval}s for completion of {len(targets)} runs...")
    print(f"Log dir: {log_dir.resolve()}")
    print(f"Done marker: {DONE_MARKER!r}")
    print(
        f"Stale threshold: {stale_seconds}s"
        if stale_seconds is not None
        else "Stale threshold: disabled"
    )
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            all_done, report = poll_once(targets, log_dir, stale_seconds=stale_seconds)
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}]\n{report}\n")

            if all_done:
                print("ALL DONE")
                return 0

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
