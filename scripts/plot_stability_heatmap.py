#!/usr/bin/env python3
"""
Plot stability heatmap by technology and component-debate agent count N.

Reads the per-(tech,N) CSV produced by `scripts/analyze_sweet_spot_tradeoffs.py`
(e.g., `output/analysis/sweet_spot_tradeoffs_by_tech_n_for_plotting.csv`) and
produces a heatmap where:
- rows = technologies
- columns = N (component debate agent count)
- cell value = stability_mean_jaccard (mean pairwise Jaccard across runs)

Output:
- PNG saved to output/analysis/ by default.

Notes:
- This script uses pandas + matplotlib only (no seaborn dependency).
- Missing values are rendered as blank/white with an "NA" overlay.
- Technologies are sorted alphabetically by default.
- If you prefer to order technologies by baseline stability (N=1), pass
  `--sort-by baseline`.

Where to place in the paper:
- Best in Appendix (supports the text claim that stability improvements are
  heterogeneous by technology).
- In main text, it can fit naturally in the "Validity, Robustness, and Cost"
  section after you introduce stability as a robustness metric, but only if you
  have space; otherwise reference it as an appendix figure.

Example:
  uv run python3 scripts/plot_stability_heatmap.py \
    --per-tech-csv output/analysis/sweet_spot_tradeoffs_by_tech_n_for_plotting.csv \
    --out output/analysis/stability_heatmap_by_tech_and_n.png
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

import pandas as pd


def _require_matplotlib() -> None:
    try:
        import matplotlib.pyplot as _  # noqa: F401
    except Exception as e:
        raise SystemExit(
            "matplotlib is required. Install it in your environment (e.g., uv add --group viz matplotlib). "
            f"Import error: {type(e).__name__}: {e}"
        )


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"CSV not found: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise SystemExit(f"CSV is empty: {path}")
    return df


def _to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _save(fig, out_path: Path, dpi: int = 220) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    print(f"Wrote: {out_path}")


def _sort_technologies(
    pivot: pd.DataFrame,
    *,
    n_baseline: int = 1,
    mode: Literal["alpha", "baseline"] = "alpha",
) -> pd.DataFrame:
    if mode == "alpha":
        return pivot.sort_index()

    # Sort by baseline column if present, else fall back to alpha
    if n_baseline in pivot.columns:
        # Put NaNs at bottom
        order = pivot[n_baseline].fillna(-1.0).sort_values(ascending=False).index.tolist()
        return pivot.loc[order]
    return pivot.sort_index()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--per-tech-csv",
        default="output/analysis/sweet_spot_tradeoffs_by_tech_n_for_plotting.csv",
        help="Per-(tech,N) CSV produced by analyze_sweet_spot_tradeoffs.py",
    )
    ap.add_argument(
        "--out",
        default="output/analysis/stability_heatmap_by_tech_and_n.png",
        help="Output PNG path",
    )
    ap.add_argument(
        "--sort-by",
        choices=["alpha", "baseline"],
        default="alpha",
        help="Technology row ordering: alphabetical, or descending stability at N=1 if present.",
    )
    ap.add_argument(
        "--title",
        default="Stability by technology and component debate strength (N)",
        help="Figure title",
    )
    ap.add_argument(
        "--vmin",
        type=float,
        default=0.0,
        help="Color scale minimum (default: 0.0)",
    )
    ap.add_argument(
        "--vmax",
        type=float,
        default=1.0,
        help="Color scale maximum (default: 1.0)",
    )
    ap.add_argument(
        "--cmap",
        default="viridis",
        help="Matplotlib colormap name (default: viridis)",
    )
    ap.add_argument(
        "--annotate",
        action="store_true",
        help="Annotate each cell with numeric value (may be crowded).",
    )
    args = ap.parse_args()

    _require_matplotlib()
    import matplotlib.pyplot as plt

    per_path = Path(args.per_tech_csv)
    out_path = Path(args.out)

    df = _read_csv(per_path)
    needed = ["technology", "n", "stability_mean_jaccard"]
    for c in needed:
        if c not in df.columns:
            raise SystemExit(f"Missing column in per-tech CSV: {c}")

    df = _to_numeric(df, ["n", "stability_mean_jaccard"])
    df = df.dropna(subset=["technology", "n"])

    # Pivot to (tech x N)
    pivot = df.pivot_table(
        index="technology",
        columns="n",
        values="stability_mean_jaccard",
        aggfunc="mean",
    )

    # Ensure N columns are sorted numerically
    try:
        pivot = pivot.reindex(sorted(pivot.columns), axis=1)
    except Exception:
        pass

    pivot = _sort_technologies(pivot, n_baseline=1, mode=args.sort_by)

    # Plot
    # Heuristic sizing: scale height by #techs
    n_tech = len(pivot.index)
    n_cols = len(pivot.columns)
    fig_w = max(7.0, 1.0 + 0.9 * n_cols)
    fig_h = max(6.0, 1.5 + 0.26 * n_tech)

    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h))

    data = pivot.to_numpy()
    im = ax.imshow(
        data,
        aspect="auto",
        interpolation="nearest",
        vmin=args.vmin,
        vmax=args.vmax,
        cmap=args.cmap,
    )

    # Ticks/labels
    ax.set_title(args.title)
    ax.set_xlabel("Component debate agents (N)")
    ax.set_ylabel("Technology")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(x)) if pd.notna(x) else "" for x in pivot.columns])

    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())

    # Minor gridlines to separate cells
    ax.set_xticks([x - 0.5 for x in range(1, len(pivot.columns))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(pivot.index))], minor=True)
    ax.grid(which="minor", color="white", linewidth=0.6)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Optional annotation
    if args.annotate:
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                v = pivot.iat[i, j]
                if pd.isna(v):
                    txt = "NA"
                    color = "black"
                else:
                    txt = f"{float(v):.2f}"
                    # choose contrasting color
                    color = "white" if float(v) > (args.vmin + args.vmax) / 2 else "black"
                ax.text(j, i, txt, ha="center", va="center", fontsize=7, color=color)

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.026, pad=0.02)
    cbar.set_label("Stability (mean pairwise Jaccard)")

    _save(fig, out_path)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
