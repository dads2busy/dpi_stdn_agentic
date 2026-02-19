#!/usr/bin/env python3
"""
Generate an STDN layer schematic + tiny concrete example as a PNG for the paper.

This script draws:
1) A clean, labeled schematic of the STDN layers:
   Technology -> Components -> Materials -> Producing Countries
2) A small concrete example subgraph (Smartphone):
   Smartphone -> OLED Display Module / Lithium-ion Battery Pack
   -> Indium / Lithium / Cobalt (materials chosen from normalized Smartphone outputs)
   -> China / Australia / D.R. Congo (illustrative countries)

Output:
- PNG saved under output/analysis/ by default, suitable for copying into the paper's images/ folder.

Dependencies:
- matplotlib (no networkx/seaborn required)

Usage:
  uv run python3 scripts/plot_stdn_layer_schematic.py
  uv run python3 scripts/plot_stdn_layer_schematic.py --out output/analysis/stdn_layer_schematic.png

Notes:
- This is an explanatory schematic, not a computed network visualization.
- Keep the example intentionally small and readable.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


def _require_matplotlib() -> None:
    try:
        import matplotlib.pyplot as _  # noqa: F401
    except Exception as e:
        raise SystemExit(
            "matplotlib is required. Install it in your environment (e.g., `uv add --group viz matplotlib`). "
            f"Import error: {type(e).__name__}: {e}"
        )


@dataclass(frozen=True)
class NodeStyle:
    facecolor: str
    edgecolor: str = "#1a1a1a"
    linewidth: float = 1.2
    fontsize: int = 9


def _save(fig, out_path: Path, dpi: int = 250) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    print(f"Wrote: {out_path}")


def _box(
    ax,
    xy: Tuple[float, float],
    wh: Tuple[float, float],
    text: str,
    style: NodeStyle,
    *,
    radius: float = 0.02,
    align: str = "center",
):
    from matplotlib.patches import FancyBboxPatch

    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        facecolor=style.facecolor,
        edgecolor=style.edgecolor,
        linewidth=style.linewidth,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2.0,
        y + h / 2.0,
        text,
        ha=align,
        va="center",
        fontsize=style.fontsize,
        color="#111111",
        wrap=True,
    )
    return patch


def _arrow(ax, x0, y0, x1, y1, *, color="#333333", lw=1.2, ms=10):
    from matplotlib.patches import FancyArrowPatch

    arr = FancyArrowPatch(
        (x0, y0),
        (x1, y1),
        arrowstyle="-|>",
        mutation_scale=ms,
        linewidth=lw,
        color=color,
        shrinkA=0,
        shrinkB=0,
    )
    ax.add_patch(arr)
    return arr


def _label(ax, x, y, s, *, fontsize=9, color="#222222", weight="normal", ha="left"):
    ax.text(x, y, s, fontsize=fontsize, color=color, weight=weight, ha=ha, va="center")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default="output/analysis/stdn_layer_schematic.png",
        help="Output PNG path (default: output/analysis/stdn_layer_schematic.png).",
    )
    ap.add_argument(
        "--title",
        default="Shallow Technology Dependency Network (STDN): layers + example",
        help="Figure title.",
    )
    args = ap.parse_args()

    _require_matplotlib()
    import matplotlib.pyplot as plt

    # Figure canvas
    fig = plt.figure(figsize=(10.5, 5.5))
    ax = fig.add_subplot(111)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    # Styles (colorblind-friendly-ish palette)
    tech_style = NodeStyle(facecolor="#dbeafe")  # light blue
    comp_style = NodeStyle(facecolor="#dcfce7")  # light green
    mat_style = NodeStyle(facecolor="#fef9c3")  # light yellow
    ctry_style = NodeStyle(facecolor="#fce7f3")  # light pink
    note_style = NodeStyle(facecolor="#f3f4f6", fontsize=8)  # light gray

    # Title
    ax.text(
        0.5, 0.965, args.title, ha="center", va="top", fontsize=13, weight="bold", color="#111111"
    )

    # -----------------------------
    # (A) Layer schematic (top)
    # -----------------------------
    _label(
        ax,
        0.05,
        0.905,
        "A) STDN layers (directed acyclic dependencies)",
        fontsize=10,
        weight="bold",
    )

    # Box geometry
    w, h = 0.20, 0.10
    y_top = 0.75

    x_tech = 0.07
    x_comp = 0.30
    x_mat = 0.53
    x_cty = 0.76

    b_tech = _box(ax, (x_tech, y_top), (w, h), "Technology\n(T)", tech_style)
    b_comp = _box(ax, (x_comp, y_top), (w, h), "Components\n(C)", comp_style)
    b_mat = _box(ax, (x_mat, y_top), (w, h), "Materials\n(M)", mat_style)
    b_cty = _box(ax, (x_cty, y_top), (w, h), "Producing\nCountries (P)", ctry_style)

    # Arrows between layer boxes
    # from right edge center of previous to left edge center of next
    def mid_right(x, y, w_, h_):
        return (x + w_, y + h_ / 2.0)

    def mid_left(x, y, w_, h_):
        return (x, y + h_ / 2.0)

    x0, y0 = mid_right(x_tech, y_top, w, h)
    x1, y1 = mid_left(x_comp, y_top, w, h)
    _arrow(ax, x0, y0, x1, y1)

    x0, y0 = mid_right(x_comp, y_top, w, h)
    x1, y1 = mid_left(x_mat, y_top, w, h)
    _arrow(ax, x0, y0, x1, y1)

    x0, y0 = mid_right(x_mat, y_top, w, h)
    x1, y1 = mid_left(x_cty, y_top, w, h)
    _arrow(ax, x0, y0, x1, y1)

    # Small notes under schematic
    note_y = 0.705
    note_text = (
        "Edges represent dependency relations (not firm-to-firm supplier links).\n"
        "STDN-GEN canonicalizes names via ontology-backed normalization to support aggregation across runs."
    )
    _box(ax, (0.07, note_y), (0.89, 0.07), note_text, note_style, radius=0.015)

    # -----------------------------
    # (B) Tiny concrete example (bottom)
    # -----------------------------
    _label(
        ax, 0.05, 0.655, "B) Small illustrative example (Smartphone)", fontsize=10, weight="bold"
    )

    # Example nodes positions (hand-tuned for readability)
    # Technology (left)
    ex_tech = _box(ax, (0.07, 0.45), (0.22, 0.09), "Smartphone", tech_style)

    # Components (next column) - increased vertical spacing
    ex_comp1 = _box(ax, (0.33, 0.58), (0.22, 0.08), "OLED Display\nModule", comp_style)
    ex_comp2 = _box(ax, (0.33, 0.44), (0.22, 0.08), "Li-ion Battery\nPack", comp_style)

    # Materials (next column) - use only materials present in normalized Smartphone outputs
    # (e.g., Indium, Lithium, Cobalt appear in the normalized Smartphone material set)
    ex_mat1 = _box(ax, (0.60, 0.59), (0.18, 0.07), "Indium", mat_style)
    ex_mat2 = _box(ax, (0.60, 0.48), (0.18, 0.07), "Lithium", mat_style)
    ex_mat3 = _box(ax, (0.60, 0.37), (0.18, 0.07), "Cobalt", mat_style)

    # Countries (right column) - increased vertical spacing
    ex_cty1 = _box(ax, (0.82, 0.60), (0.14, 0.06), "China", ctry_style)
    ex_cty2 = _box(ax, (0.82, 0.48), (0.14, 0.06), "Australia", ctry_style)
    ex_cty3 = _box(ax, (0.82, 0.36), (0.14, 0.06), "D.R.\nCongo", ctry_style)

    # Arrows: Tech -> Components (updated for new y-positions)
    _arrow(ax, 0.29, 0.505, 0.33, 0.62)  # to display
    _arrow(ax, 0.29, 0.505, 0.33, 0.48)  # to battery

    # Arrows: Components -> Materials (updated for new y-positions)
    _arrow(ax, 0.55, 0.62, 0.60, 0.625)  # display -> indium
    _arrow(ax, 0.55, 0.48, 0.60, 0.515)  # battery -> lithium
    _arrow(ax, 0.55, 0.48, 0.60, 0.405)  # battery -> cobalt

    # Arrows: Materials -> Countries (updated for new y-positions)
    _arrow(ax, 0.78, 0.625, 0.82, 0.63)  # indium -> China
    _arrow(ax, 0.78, 0.515, 0.82, 0.51)  # lithium -> Australia
    _arrow(ax, 0.78, 0.405, 0.82, 0.39)  # cobalt -> DRC

    # Legend / note about example
    example_note = (
        "Example is illustrative (not exhaustive). In the paper, validity and robustness are evaluated across\n"
        "26 technologies using an independent LLM judge (precision proxy) and run-to-run stability metrics."
    )
    _box(ax, (0.07, 0.22), (0.89, 0.09), example_note, note_style, radius=0.015)

    # Save
    out_path = Path(args.out)
    _save(fig, out_path)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
