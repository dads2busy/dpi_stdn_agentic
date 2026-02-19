#!/usr/bin/env python3
"""
Generate plotting-ready figures for validity, robustness, and cost findings.

Inputs:
- A by-N CSV produced by scripts/analyze_sweet_spot_tradeoffs.py (recommended):
    output/analysis/sweet_spot_tradeoffs_by_n_for_plotting.csv
- A per-(tech,N) CSV (optional; for per-technology paired plots):
    output/analysis/sweet_spot_tradeoffs_by_tech_n_for_plotting.csv

Outputs:
- PNG files in output/analysis/ by default.

Figures generated (proposed set):
1) validity_vs_n_dedup_invalid_and_k.png
   - Panel A: deduped-canonical invalid rate (median) vs N
   - Panel B: #components (median) vs N
2) tradeoff_runtime_vs_stability.png
   - scatter: runtime (median, minutes) vs stability (median), labeled by N
3) convergence_rounds_vs_n.png
   - Panel A: final convergence (median) vs N
   - Panel B: rounds (median) vs N
4) invalid_rate_occ_vs_dedup.png
   - occurrence-based vs deduped-canonical invalid rate (median) vs N
5) paired_invalid_rate_dedup_n1_vs_n3.png (optional, if per-tech CSV provided)
   - paired dot plot per technology: deduped invalid rate at N=1 vs N=3

Notes:
- This script intentionally uses only the macro *median* series for primary plots
  (robust to outliers). CIs in the by-N CSV are for means/deltas; you can extend
  to plot those if desired.
- Runtime uncertainty across technologies is degenerate in the current pipeline
  (runtime is per config-run log), so we show runtime point estimates only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def _require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # noqa: F401

        return True
    except Exception as e:
        raise SystemExit(
            "matplotlib is required. Install dependencies via your project env (e.g., uv/pip). "
            f"Import error: {type(e).__name__}: {e}"
        )


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"CSV not found: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise SystemExit(f"CSV is empty: {path}")
    return df


def _as_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _save(fig, out_path: Path, dpi: int = 200) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    print(f"Wrote: {out_path}")


def _n_label(n: int) -> str:
    return f"N={int(n)}"


def fig_validity_vs_n_dedup_invalid_and_k(by_n: pd.DataFrame, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    needed = [
        "n",
        "not_plausible_dedup_canon_median",
        "produced_components_median",
    ]
    for c in needed:
        if c not in by_n.columns:
            raise SystemExit(f"Missing column in by-N CSV: {c}")

    df = by_n.sort_values("n").copy()
    df = _as_numeric(df, needed)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    # Panel A: invalid rate (dedup-canon)
    ax = axes[0]
    ax.plot(df["n"], df["not_plausible_dedup_canon_median"], marker="o", linewidth=2)
    ax.set_title("Validity (precision proxy)\nDeduped-canonical invalid rate (median)")
    ax.set_xlabel("Component debate agents (N)")
    ax.set_ylabel("Invalid rate (lower is better)")
    ax.set_xticks(df["n"].tolist())
    ax.grid(True, alpha=0.3)

    # Panel B: component count
    ax = axes[1]
    ax.plot(df["n"], df["produced_components_median"], marker="o", linewidth=2, color="#2a7")
    ax.set_title("Not just shorter lists\n# Components produced (median)")
    ax.set_xlabel("Component debate agents (N)")
    ax.set_ylabel("# components (canonical)")
    ax.set_xticks(df["n"].tolist())
    ax.grid(True, alpha=0.3)

    fig.suptitle("Validity vs N (with component-count control)", y=1.03, fontsize=12)
    _save(fig, out_dir / "validity_vs_n_dedup_invalid_and_k.png")
    plt.close(fig)


def fig_tradeoff_runtime_vs_stability(by_n: pd.DataFrame, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    needed = ["n", "runtime_median_seconds", "stability_median"]
    for c in needed:
        if c not in by_n.columns:
            raise SystemExit(f"Missing column in by-N CSV: {c}")

    df = by_n.sort_values("n").copy()
    df = _as_numeric(df, needed)
    df["runtime_median_minutes"] = df["runtime_median_seconds"] / 60.0

    fig, ax = plt.subplots(1, 1, figsize=(6.5, 4.5))
    ax.scatter(df["runtime_median_minutes"], df["stability_median"], s=80)

    for _, row in df.iterrows():
        x = row["runtime_median_minutes"]
        y = row["stability_median"]
        if pd.isna(x) or pd.isna(y):
            continue
        ax.annotate(_n_label(int(row["n"])), (x, y), textcoords="offset points", xytext=(6, 6))

    ax.set_title("Tradeoff: Robustness vs Cost")
    ax.set_xlabel("Runtime (median, minutes)")
    ax.set_ylabel("Stability (median pairwise Jaccard)")
    ax.grid(True, alpha=0.3)
    _save(fig, out_dir / "tradeoff_runtime_vs_stability.png")
    plt.close(fig)


def fig_convergence_rounds_vs_n(by_n: pd.DataFrame, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    needed = ["n", "final_convergence_median", "rounds_median"]
    for c in needed:
        if c not in by_n.columns:
            raise SystemExit(f"Missing column in by-N CSV: {c}")

    df = by_n.sort_values("n").copy()
    df = _as_numeric(df, needed)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    ax = axes[0]
    ax.plot(df["n"], df["final_convergence_median"], marker="o", linewidth=2, color="#06c")
    ax.set_title("Final convergence (median)")
    ax.set_xlabel("Component debate agents (N)")
    ax.set_ylabel("Final convergence")
    ax.set_xticks(df["n"].tolist())
    ax.set_ylim(0.0, 1.0)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(df["n"], df["rounds_median"], marker="o", linewidth=2, color="#c60")
    ax.set_title("Rounds completed (median)")
    ax.set_xlabel("Component debate agents (N)")
    ax.set_ylabel("Rounds")
    ax.set_xticks(df["n"].tolist())
    ax.grid(True, alpha=0.3)

    fig.suptitle("Convergence / rounds vs N", y=1.03, fontsize=12)
    _save(fig, out_dir / "convergence_rounds_vs_n.png")
    plt.close(fig)


def fig_invalid_rate_occ_vs_dedup(by_n: pd.DataFrame, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    needed = ["n", "not_plausible_occ_median", "not_plausible_dedup_canon_median"]
    for c in needed:
        if c not in by_n.columns:
            raise SystemExit(f"Missing column in by-N CSV: {c}")

    df = by_n.sort_values("n").copy()
    df = _as_numeric(df, needed)

    fig, ax = plt.subplots(1, 1, figsize=(7.0, 4.5))
    ax.plot(
        df["n"], df["not_plausible_occ_median"], marker="o", linewidth=2, label="Occurrence-based"
    )
    ax.plot(
        df["n"],
        df["not_plausible_dedup_canon_median"],
        marker="o",
        linewidth=2,
        label="Deduped-canonical",
    )
    ax.set_title("Invalid rate vs N (two counting schemes)")
    ax.set_xlabel("Component debate agents (N)")
    ax.set_ylabel("Invalid rate (lower is better)")
    ax.set_xticks(df["n"].tolist())
    ax.grid(True, alpha=0.3)
    ax.legend()
    _save(fig, out_dir / "invalid_rate_occ_vs_dedup.png")
    plt.close(fig)


def fig_paired_invalid_rate_dedup_n1_vs_n3(
    per_tech: pd.DataFrame, out_dir: Path, n_a: int = 1, n_b: int = 3
) -> None:
    import matplotlib.pyplot as plt

    needed = ["technology", "n", "not_plausible_rate_dedup_canon"]
    for c in needed:
        if c not in per_tech.columns:
            raise SystemExit(f"Missing column in per-tech CSV: {c}")

    df = per_tech.copy()
    df = _as_numeric(df, ["n", "not_plausible_rate_dedup_canon"])
    df = df[df["n"].isin([n_a, n_b])].copy()

    # pivot: technology -> values at n_a and n_b
    pivot = df.pivot_table(
        index="technology",
        columns="n",
        values="not_plausible_rate_dedup_canon",
        aggfunc="mean",
    )
    if n_a not in pivot.columns or n_b not in pivot.columns:
        print(f"Skipping paired plot: missing N={n_a} or N={n_b} in per-tech CSV")
        return

    pivot = pivot.dropna(subset=[n_a, n_b]).sort_index()
    if pivot.empty:
        print("Skipping paired plot: no paired technologies after filtering")
        return

    # Plot as slopegraph-ish: x=0 and x=1
    fig, ax = plt.subplots(1, 1, figsize=(8.5, max(4.5, 0.18 * len(pivot) + 2)))
    x0, x1 = 0.0, 1.0

    ys0 = pivot[n_a].tolist()
    ys1 = pivot[n_b].tolist()

    for y0, y1 in zip(ys0, ys1, strict=False):
        ax.plot([x0, x1], [y0, y1], color="gray", alpha=0.5, linewidth=1)

    ax.scatter([x0] * len(ys0), ys0, color="#b33", label=_n_label(n_a), s=25)
    ax.scatter([x1] * len(ys1), ys1, color="#3b7", label=_n_label(n_b), s=25)

    ax.set_xticks([x0, x1])
    ax.set_xticklabels([_n_label(n_a), _n_label(n_b)])
    ax.set_ylabel("Deduped-canonical invalid rate (lower is better)")
    ax.set_title(f"Per-technology invalid rate: {_n_label(n_a)} vs {_n_label(n_b)}")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="upper right")
    _save(fig, out_dir / f"paired_invalid_rate_dedup_{_n_label(n_a)}_vs_{_n_label(n_b)}.png")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--by-n-csv",
        default="output/analysis/sweet_spot_tradeoffs_by_n_for_plotting.csv",
        help="By-N macro summary CSV produced by analyze_sweet_spot_tradeoffs.py",
    )
    ap.add_argument(
        "--per-tech-csv",
        default="output/analysis/sweet_spot_tradeoffs_by_tech_n_for_plotting.csv",
        help="Optional per-(tech,N) CSV produced by analyze_sweet_spot_tradeoffs.py",
    )
    ap.add_argument(
        "--out-dir",
        default="output/analysis",
        help="Directory to write figures into",
    )
    ap.add_argument(
        "--paired-n-a",
        type=int,
        default=1,
        help="First N for paired per-technology plot (default: 1)",
    )
    ap.add_argument(
        "--paired-n-b",
        type=int,
        default=3,
        help="Second N for paired per-technology plot (default: 3)",
    )
    args = ap.parse_args()

    _require_matplotlib()

    out_dir = Path(args.out_dir)
    by_n = _read_csv(Path(args.by_n_csv))
    fig_validity_vs_n_dedup_invalid_and_k(by_n, out_dir)
    fig_tradeoff_runtime_vs_stability(by_n, out_dir)
    fig_convergence_rounds_vs_n(by_n, out_dir)
    fig_invalid_rate_occ_vs_dedup(by_n, out_dir)

    per_tech_path = Path(args.per_tech_csv)
    if per_tech_path.exists():
        per_tech = _read_csv(per_tech_path)
        fig_paired_invalid_rate_dedup_n1_vs_n3(
            per_tech, out_dir, n_a=args.paired_n_a, n_b=args.paired_n_b
        )
    else:
        print(f"Per-tech CSV not found; skipping paired plot: {per_tech_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
