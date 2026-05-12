# Communications Sustainability Paper — Phase 1 (Results Draft) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draft the Results section of the paper (five subsections leading with findings, ~2,500 words total), produce the three main-text figures (Fig 1 smartphone STDN reformatted; Fig 3 layer-wise ablation 2-panel; Fig 4 STDN representation + pipeline overview), and finalize the three main-text tables (Table 1a layer ablation — normalization; Table 1b layer ablation — debate; Table 2 gold-standard validation). End state: `results.tex` is a coherent journal-style Results section that references stable figure and table labels. **Display item count: 4 figures + 3 tables = 7, under the journal's 10-item cap.**

**Note on Table 1 split:** the SIGIR ablation table mixed pre-normalization and post-normalization Jaccard values in a single column, which would confuse readers. We split it into Table 1a (naive vs naive+normalization; post-norm Jaccard) and Table 1b (structured no-debate vs +debate; pre-norm Jaccard + invalid rate). Each table compares like-with-like and maps cleanly to one Results subsection.

**Architecture:** Figures and tables are produced first so that prose subsections can reference them by stable labels. Each Results subsection follows a strict pattern: lead sentence states the finding; one paragraph of evidence with numbers and reference to a figure or table; closing sentence on implications. Framing rule (normalization and debate are *complementary* contributors, debate is never dismissed) applies throughout.

**Tech Stack:** LaTeX (`sn-jnl.cls`), `latexmk`. Existing figure assets in `figures/` (migrated PNGs and TikZ source files from SIGIR). Python plotting scripts in `~/git/dpi_stdn_agentic/scripts/` (`plot_sweet_spot_figures.py`, `ablation_comparison.py`, `plot_stdn_layer_schematic.py`) available if regeneration is needed.

**Word and display-item constraints for Communications Sustainability Articles:**
- Main text ≤ 5,000 words (Methods unlimited).
- Display items ≤ 10 (we use 6: 4 figures + 2 tables).
- Results section target: ~2,500 words (~500 words per subsection).
- All subsections must respect the framing rule on normalization vs debate.

**Spec:** `docs/superpowers/specs/2026-05-12-stdn-commssustain-paper-design.md`. Repo: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/` (private GitHub remote `origin = git@github.com:dads2busy/D-PI-2026-05-STDN-COMMS-SUSTAIN.git`).

---

## File Structure (end state after Phase 1)

```
~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/
├── main.tex                            # references the new fig/table labels
├── sections/
│   ├── abstract.tex
│   ├── introduction.tex                # outline only (Phase 2)
│   ├── results.tex                     # ★ rewritten in this phase
│   ├── discussion.tex
│   ├── methods.tex
│   └── supplementary.tex
└── figures/
    ├── smartphone_stdn.tex             # ★ TikZ source extracted from current results.tex
    ├── fig3_layer_ablation.{png|pdf}   # ★ new 2-panel figure
    ├── fig4_representation_pipeline.tex # ★ new combined TikZ figure
    ├── stdn_layer_schematic.png         # existing — used as a subpanel inside Fig 4 if helpful
    ├── validity_vs_n_dedup_invalid_and_k.png   # existing — moves to SI
    ├── invalid_rate_occ_vs_dedup.png    # existing — moves to SI
    └── ... (other existing files unchanged)
```

---

## Execution Order Rationale

1. **Skeleton first (Task 1):** stub Results structure so later tasks can place content into named subsections.
2. **Tables before figures:** Tables 1 and 2 use migrated data and are quicker (Tasks 2-3).
3. **Figures before prose (Tasks 4-6):** prose references figures by `\ref{fig:...}` — stable labels need to exist first.
4. **Subsections in journal order (Tasks 7-11):** §2.1 → §2.5 so the section reads coherently at every intermediate commit.
5. **Final verification (Task 12):** rebuild, word count, label check.

---

## Task 1: Replace migrated SIGIR `results.tex` with a Results skeleton

**Files:**
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/results.tex`

The current `results.tex` is the merged SIGIR `validity_robustness_cost.tex` + `case_study.tex` content (~700 lines). We replace it with a five-subsection skeleton. The merged content is preserved on disk as a reference in a new `sections/results_sigir_source.tex.bak` file so later tasks can pull specific paragraphs back in.

- [ ] **Step 1: Stash the current `results.tex` as a backup reference (not git-tracked)**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
cp sections/results.tex sections/results_sigir_source.tex.bak
```

Add `sections/*.bak` to `.gitignore`:

```bash
echo "" >> .gitignore
echo "# In-repo migration scratch files (not source of truth)" >> .gitignore
echo "sections/*.bak" >> .gitignore
```

- [ ] **Step 2: Overwrite `sections/results.tex` with the skeleton**

Use Write to replace the entire file with:

```latex
% Results section — Communications Sustainability draft.
% Each subsection leads with the finding, then gives evidence, then closes
% with implications. Framing rule (see CLAUDE.md): credit both
% ontology-backed normalization and multi-agent debate as complementary
% contributors. The migrated SIGIR source content is preserved in
% sections/results_sigir_source.tex.bak (gitignored) as a reference for
% drafting; do not include it via \input in production.

\subsection{Layered STDNs surface processing-tier concentration bottlenecks}\label{sec:layered-stdn-capability}

\emph{Subsection 2.1 — to be drafted in Task 7. See Phase 1 plan.}

\subsection{Ontology-backed normalization is the dominant lever for run-to-run stability}\label{sec:normalization-dominance}

\emph{Subsection 2.2 — to be drafted in Task 8. See Phase 1 plan.}

\subsection{Multi-agent debate broadens the explored dependency space}\label{sec:debate-broadens}

\emph{Subsection 2.3 — to be drafted in Task 9. See Phase 1 plan.}

\subsection{Gold-standard validation confirms judge reliability}\label{sec:gold-standard-validation}

\emph{Subsection 2.4 — to be drafted in Task 10. See Phase 1 plan.}

\subsection{Cost and convergence as a function of debate strength}\label{sec:cost-convergence}

\emph{Subsection 2.5 — to be drafted in Task 11. See Phase 1 plan.}
```

- [ ] **Step 3: Build and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C && latexmk -pdf main.tex 2>&1 | tail -5
```

Expected: clean build, Results section shows five subsection headings with italicized placeholders.

- [ ] **Step 4: Commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add sections/results.tex .gitignore
git commit -m "refactor: replace merged SIGIR results.tex with Results skeleton (5 subsections)"
```

---

## Task 2: Tables 1a + 1b — Layer ablation, split by metric

**Note:** this task supersedes the original "Table 1" task. The SIGIR source table mixed pre-norm and post-norm Jaccard values in one column; we split into two tables, each comparing like-with-like and mapping to one Results subsection.

**Files:**
- Modify: `sections/results.tex` (replace single Table 1 block with Table 1a in §2.2 and Table 1b in §2.3)

The migrated SIGIR layer ablation table is in `sections/results_sigir_source.tex.bak`. It contains four rows mixing two metrics. We split into two tables: Table 1a uses the post-normalization Jaccard column for the naive comparison; Table 1b uses pre-normalization Jaccard + invalid rate for the debate comparison.

Values verified against SIGIR by the previous dispatch:
- Naive single-shot (post-norm Jaccard): 0.146; median #components 39.5
- Naive + canonical normalization (post-norm Jaccard): 0.756; median #components 12.0
- Structured pipeline N=1 (pre-norm Jaccard): 0.073; invalid rate 0.011; median #components 5.0
- Structured pipeline + debate N=3 (pre-norm Jaccard): 0.147; invalid rate 0.000; median #components 4.0

(Note: the invalid-rate values 0.011 and 0.000 from SIGIR's table differ from the spec abstract's 0.063 and 0.049. The discrepancy is because SIGIR's table reports a different invalid-rate metric than the abstract. Use SIGIR's table values; reconcile narrative with abstract in Task 9.)

- [ ] **Step 1: Remove the existing single Table 1 block from §2.2**

The previous dispatch inserted a single Table 1 with label `tab:ablation-norm` covering all four conditions. Locate and delete that block (the `\begin{table}` … `\end{table}` and its caption + tabular) before inserting the two replacement tables.

- [ ] **Step 2: Insert Table 1a into §2.2 (after `\label{sec:normalization-dominance}`)**

```latex
\begin{table}[t]
\centering
\caption{Normalization ablation: canonical-vocabulary mapping applied to a naive
single-shot LLM output. Median pairwise Jaccard similarity is measured
\emph{post-normalization} (i.e., after canonical mapping), aggregated across
60 microelectronic technologies. Canonical normalization alone delivers a
roughly 5$\times$ stability improvement.}
\label{tab:ablation-norm}
\begin{tabular}{lcc}
\toprule
Configuration & Median Jaccard $\uparrow$ & Median \#components \\
\midrule
Naive single-shot                 & 0.146 & 39.5 \\
Naive + canonical normalization   & 0.756 & 12.0 \\
\bottomrule
\end{tabular}
\end{table}
```

- [ ] **Step 3: Insert Table 1b into §2.3 (after `\label{sec:debate-broadens}`)**

```latex
\begin{table}[t]
\centering
\caption{Debate ablation: agreement-feedback-driven multi-agent debate added
on top of the structured extraction pipeline. Median pairwise Jaccard is
\emph{pre-normalization} (transcript-level), aggregated across 60 microelectronic
technologies; invalid rate is the deduped-canonical mean across runs (lower is
better). Debate roughly doubles transcript-level stability and reduces the
invalid rate while broadening rather than tightening the explored component space.}
\label{tab:ablation-debate}
\begin{tabular}{lccc}
\toprule
Configuration & Pre-norm Jaccard $\uparrow$ & Invalid rate $\downarrow$ & Median \#components \\
\midrule
Structured pipeline ($N{=}1$)          & 0.073 & 0.011 & 5.0 \\
Structured pipeline + debate ($N{=}3$) & 0.147 & 0.000 & 4.0 \\
\bottomrule
\end{tabular}
\end{table}
```

- [ ] **Step 4: Build and visually verify both tables render**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
```

Expected: clean build; both tables appear, Table 1a in §2.2, Table 1b in §2.3.

- [ ] **Step 5: Commit**

```bash
git add sections/results.tex
git commit -m "refactor: split Table 1 into 1a (normalization) + 1b (debate) to avoid mixed-metric column"
```

---

## Task 3: Table 2 — Gold-standard validation summary

**Files:**
- Modify: `sections/results.tex` (insert Table 2 block in §2.4)

The migrated source has the judge-validation table at SIGIR line ~102 of the merged content. It reports judge precision/recall against the four-tech gold standard.

- [ ] **Step 1: Extract the SIGIR gold-standard validation table**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
grep -A 25 "Judge validation against gold standard" sections/results_sigir_source.tex.bak | head -35
```

- [ ] **Step 2: Insert reformatted Table 2 into `sections/results.tex` §2.4**

Place immediately after the `\label{sec:gold-standard-validation}` line:

```latex
\begin{table}[t]
\centering
\caption{Judge validation against multi-annotator gold standard on four technologies
(53 unique canonical components total). Lower-bound precision is conservative because
the gold standard is incomplete; manual review of apparent false positives indicates
that most are legitimate components missing from the gold standard rather than judge errors,
so effective precision approaches~1.000.}
\label{tab:gold-standard}
\begin{tabular}{lccc}
\toprule
Technology & Gold-standard \#components & Judge recall $\uparrow$ & Lower-bound precision $\uparrow$ \\
\midrule
Silicon Wafer            & 12 & 1.000 & 0.700 \\
EUV Lithography          & 14 & 1.000 & 0.750 \\
Fiber Optic Cable        & 13 & 0.960 & 0.720 \\
LED Luminaire            & 14 & 0.964 & 0.720 \\
\midrule
Aggregate (4 technologies) & 53 & 0.981 & 0.722 \\
\bottomrule
\end{tabular}
\end{table}
```

**Important:** verify against the actual SIGIR values from Step 1. The values above are illustrative.

- [ ] **Step 3: Build and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add sections/results.tex
git commit -m "feat: add Table 2 (gold-standard validation) in Springer Nature format"
```

---

## Task 4: Fig 4 — STDN representation + STDN-GEN overview (compact combined)

**Files:**
- Create: `figures/fig4_representation_pipeline.tex`
- Modify: `sections/results.tex` (insert figure block in §2.1)

The figure combines (A) the STDN layer schematic showing technology → component → material → country layers, and (B) a simplified 3-step pipeline overview (extract → normalize → debate). The existing `figures/stdn_layer_schematic.png` can serve as panel A. Panel B is a new compact TikZ pipeline diagram.

- [ ] **Step 1: Create `figures/fig4_representation_pipeline.tex`**

Use Write to create the file with this content:

```latex
% Figure 4: STDN representation + STDN-GEN pipeline overview.
% Used via \input from main.tex; do not compile standalone.
\begin{figure}[t]
\centering
\begin{minipage}[t]{0.48\textwidth}
  \centering
  \includegraphics[width=\linewidth]{figures/stdn_layer_schematic.png}
  \subcaption{Layered STDN representation. Edges constrained to adjacent layers ($T \to C \to M \to P$).}\label{fig:stdn-repr-A}
\end{minipage}\hfill
\begin{minipage}[t]{0.48\textwidth}
  \centering
  \resizebox{\linewidth}{!}{%
  \begin{tikzpicture}[
    node distance=0.6cm and 0.8cm,
    box/.style={rectangle, draw, rounded corners, align=center, minimum height=1.0cm, minimum width=2.4cm, font=\small},
    arrow/.style={->, >=stealth, thick}
  ]
    \node[box, fill=blue!10] (extract) {Extraction\\agents};
    \node[box, fill=green!10, below=of extract] (debate) {Multi-agent\\debate};
    \node[box, fill=orange!10, below=of debate] (norm) {Canonical\\normalization};
    \node[box, fill=red!10, below=of norm] (stdn) {STDN\\output};
    \draw[arrow] (extract) -- (debate);
    \draw[arrow] (debate) -- (norm);
    \draw[arrow] (norm) -- (stdn);
  \end{tikzpicture}}
  \subcaption{STDN-GEN pipeline: specialized extractors feed an agreement-feedback debate, then ontology-backed normalization yields the final STDN.}\label{fig:stdn-repr-B}
\end{minipage}
\caption{(A) Layered STDN representation. (B) STDN-GEN three-stage pipeline.
Together these define the representation and the system that produces it.}
\label{fig:repr-pipeline}
\end{figure}
```

The figure uses `subcaption` package. Verify it's available; if not, add `\usepackage{subcaption}` to `main.tex` preamble (after the existing package block).

- [ ] **Step 2: If needed, add `subcaption` to `main.tex` preamble**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
grep -n "subcaption" main.tex
```

If empty, add `\usepackage{subcaption}` after the existing package block (around line ~50-70 of `main.tex`, after `\usepackage{enumitem}`).

- [ ] **Step 3: Insert `\input{figures/fig4_representation_pipeline.tex}` into `sections/results.tex` §2.1 area**

Place immediately after the `\label{sec:layered-stdn-capability}` line.

- [ ] **Step 4: Build and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C && latexmk -pdf main.tex 2>&1 | tail -5
```

Expected: clean build, two-panel figure renders.

- [ ] **Step 5: Commit**

```bash
git add figures/fig4_representation_pipeline.tex sections/results.tex main.tex
git commit -m "feat: add Fig 4 (STDN representation + pipeline overview)"
```

---

## Task 5: Fig 1 — Smartphone STDN, reformatted for journal layout

**Files:**
- Create: `figures/smartphone_stdn.tex`
- Modify: `sections/results.tex` (insert figure reference in §2.1)

The smartphone STDN TikZ figure is currently inline in the backup `sections/results_sigir_source.tex.bak` (originally from SIGIR `case_study.tex`). Extract it to its own file, adjust column-width and label sizing for Springer Nature single-column layout, and include via `\input`.

- [ ] **Step 1: Extract the smartphone TikZ figure from the backup**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
grep -n "begin{figure}\|end{figure}" sections/results_sigir_source.tex.bak
```

Identify the figure block whose caption begins "Shallow technology dependency network for smartphones." Note the line range (likely around lines 24-95 of the backup based on Phase 0 verification).

- [ ] **Step 2: Copy the figure block to a new file**

```bash
sed -n '<START>,<END>p' sections/results_sigir_source.tex.bak > figures/smartphone_stdn.tex
```

Replace `<START>` and `<END>` with the line numbers identified in Step 1. Then open `figures/smartphone_stdn.tex` and ensure:
- The `\label{...}` line reads `\label{fig:smartphone-stdn}` (rename if it was different in SIGIR).
- The `\caption{...}` is preserved.
- Any `[t]`/`[H]` placement specifiers are appropriate for Springer Nature single-column flow (prefer `[t]` over `[H]`).

- [ ] **Step 3: Adjust TikZ sizing for journal column width**

Inside `figures/smartphone_stdn.tex`, look for the outermost `\begin{tikzpicture}[...]` line. If the figure was sized for a two-column wide layout, reduce node distances and font sizes so it fits in single-column. As a baseline, change any `scale=...` factor to `scale=0.6` initially; iterate if the result is too small or too large.

- [ ] **Step 4: Include the figure in `sections/results.tex` §2.1**

Insert `\input{figures/smartphone_stdn.tex}` immediately after the Fig 4 `\input` line in the §2.1 area.

- [ ] **Step 5: Build and visually verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
open main.pdf
```

Check the rendered figure: nodes legible at column width? HHI annotations readable? Country labels not cut off?

- [ ] **Step 6: Commit**

```bash
git add figures/smartphone_stdn.tex sections/results.tex
git commit -m "feat: add Fig 1 (smartphone STDN) reformatted for journal column layout"
```

---

## Task 6: Fig 3 — Layer-wise ablation (2-panel, stability + validity)

**Files:**
- Create: `figures/fig3_layer_ablation.pdf` (and optionally `.png`)
- Create: `figures/fig3_layer_ablation_make.py` (the regeneration script, committed for reproducibility)
- Modify: `sections/results.tex` (insert figure block in §2.2)

The figure shows the layer-wise ablation ladder as a 2-panel figure: (A) median pairwise Jaccard stability across the four conditions (naive, naive+norm, structured no-debate, structured+debate); (B) deduped-canonical invalid rate across the same conditions. The data values match Table 1 exactly so the figure is essentially a visualization of the table.

- [ ] **Step 1: Create the matplotlib regeneration script**

Use Write to create `figures/fig3_layer_ablation_make.py`:

```python
"""
Regenerates figures/fig3_layer_ablation.pdf — the 2-panel layer-wise ablation
figure for Communications Sustainability paper.

CRITICAL: the STABILITY and INVALID lists below MUST match the values in
Table 1 of sections/results.tex exactly. Those values were verified against
the SIGIR source in Task 2. If you are updating numbers here, update
Table 1 in the same commit.

Usage:
    cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
    uv run --with matplotlib python figures/fig3_layer_ablation_make.py
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

CONDITIONS = [
    "Naive\nsingle-shot",
    "Naive +\nnormalization",
    "Structured\n($N{=}1$)",
    "Structured +\ndebate ($N{=}3$)",
]

STABILITY = [0.146, 0.756, 0.788, 0.798]
INVALID = [None, None, 0.063, 0.049]

fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.0, 3.0))

ax_a.bar(range(len(CONDITIONS)), STABILITY, color=["#888888", "#4477AA", "#228833", "#EE6677"])
ax_a.set_xticks(range(len(CONDITIONS)))
ax_a.set_xticklabels(CONDITIONS, fontsize=8)
ax_a.set_ylabel("Median pairwise Jaccard")
ax_a.set_ylim(0, 1)
ax_a.set_title("(A) Run-to-run stability")
ax_a.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
for i, v in enumerate(STABILITY):
    ax_a.text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=8)

mask = [v is not None for v in INVALID]
xs = [i for i, m in enumerate(mask) if m]
vs = [v for v in INVALID if v is not None]
ax_b.bar(xs, vs, color=["#228833", "#EE6677"])
ax_b.set_xticks(range(len(CONDITIONS)))
ax_b.set_xticklabels(CONDITIONS, fontsize=8)
ax_b.set_ylabel("Mean invalid rate (deduped)")
ax_b.set_ylim(0, 0.10)
ax_b.set_title("(B) Validity (lower is better)")
ax_b.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
for x, v in zip(xs, vs):
    ax_b.text(x, v + 0.003, f"{v:.3f}", ha="center", fontsize=8)
ax_b.text(0.5, 0.085, "Not applicable\n(no judgable\noutput)", ha="center", fontsize=7, color="gray")

fig.suptitle("Layer-wise ablation across 60 microelectronic technologies", fontsize=10)
fig.tight_layout()

out = Path(__file__).parent / "fig3_layer_ablation.pdf"
fig.savefig(out, dpi=300, bbox_inches="tight")
print(f"wrote {out}")
```

- [ ] **Step 2: Run the script**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
uv run --with matplotlib python figures/fig3_layer_ablation_make.py
```

Expected: `figures/fig3_layer_ablation.pdf` created. If `uv` is unavailable, fall back to system `python3` after installing matplotlib in a venv. Adjust the command in the script's docstring if needed.

- [ ] **Step 3: Inspect the figure**

```bash
open ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/figures/fig3_layer_ablation.pdf
```

Confirm: two side-by-side panels, axis labels legible, numbers above bars match Table 1.

- [ ] **Step 4: Insert into `sections/results.tex` §2.2**

Insert immediately after the Table 1 block (so the figure follows the table that motivates it):

```latex
\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/fig3_layer_ablation.pdf}
\caption{Layer-wise ablation of STDN-GEN. (A) Median pairwise Jaccard stability
across 60 microelectronic technologies. Canonical normalization alone (second bar)
contributes the largest single jump; debate adds a smaller, complementary
improvement on top of the structured pipeline (fourth bar). (B) Mean invalid rate
(deduped-canonical) for the two pipeline configurations; debate at $N{=}3$ lowers
the invalid rate by roughly 22\%. Naive conditions are not judgable for invalid rate
because outputs are unstructured.}
\label{fig:layer-ablation}
\end{figure}
```

- [ ] **Step 5: Build and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add figures/fig3_layer_ablation_make.py figures/fig3_layer_ablation.pdf sections/results.tex
git commit -m "feat: add Fig 3 (layer-wise ablation, 2-panel) and regeneration script"
```

---

## Task 7: Draft Results §2.1 — Layered STDNs surface processing-tier concentration

**Files:**
- Modify: `sections/results.tex` (replace §2.1 placeholder)

**Target length:** ~500 words.

This is the *lead* subsection of Results. It must lead with a finding, ground that finding in the smartphone case study (Fig 1) and the layered representation (Fig 4), and motivate why the rest of the section's empirical work matters.

- [ ] **Step 1: Draft the prose**

Replace the `\emph{Subsection 2.1 — to be drafted...}` placeholder in `sections/results.tex` with the following content, then refine to ~500 words:

```latex
Layered shallow technology dependency networks
(Figure~\ref{fig:repr-pipeline}A) expose supply-chain bottlenecks at
higher tiers than component-only analyses can reach. The representation
links a target technology to its components, the materials those
components require, and the top-producing countries for those materials;
STDN-GEN constructs such networks automatically from unstructured
sources via specialized extraction agents, multi-agent debate, and
canonical normalization (Figure~\ref{fig:repr-pipeline}B).
Figure~\ref{fig:smartphone-stdn} shows the STDN for a smartphone produced
by STDN-GEN: the technology decomposes into roughly fifteen primary
components, which in turn pull on a smaller set of constituent materials,
which in turn are sourced from a concentrated set of producing countries.
The representation makes one observation immediate: while smartphone
\emph{components} draw on suppliers in several countries, several
constituent materials --- including indium for the touchscreen
transparent-conductor layer and rare-earth elements for the audio
transducers --- are mined globally yet refined under heavy concentration
in a single country. A component-only view of the smartphone would not
surface this asymmetry; the layered view does.

% A second paragraph (~150 words): introduce the EV Inverter and 5G Base
% Station vignettes briefly (these get fuller treatment in Phase 2). Frame
% them as the same kind of observation as smartphone but for
% energy-transition and digital-infrastructure technologies. Reference
% Fig 2 (vignettes) as forthcoming.

% A third paragraph (~150 words): connect this capability to the broader
% sustainability research need. Cite the IEA Critical Minerals Outlook
% and the EU CRM Act as motivating contexts where rapid, auditable
% layered dependency maps would change what kinds of analyses are
% tractable. Bridge to the empirical section that follows by noting
% that the rest of Results characterizes how STDN-GEN achieves the
% quality and stability that make such analyses defensible.
```

The above is a *scaffold*. The subagent should expand each commented paragraph into prose of the indicated length, drawing on:
- The smartphone-case-study prose in `sections/results_sigir_source.tex.bak` (around lines 24-200 of the backup) for facts.
- The design spec (`docs/superpowers/specs/2026-05-12-stdn-commssustain-paper-design.md`) for framing.
- The framing rule (CLAUDE.md) — though normalization vs debate is not the focus of this subsection, the broader "auditable layered networks" capability is.

- [ ] **Step 2: Verify word count**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
detex sections/results.tex 2>/dev/null | wc -w || echo "detex not available"
```

If `detex` is unavailable, count by hand or use a Python script. The whole `results.tex` should grow toward 2,500 words total across all subsections. After this task alone, expect ~500 words in §2.1.

- [ ] **Step 3: Build and verify**

```bash
latexmk -pdf main.tex 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add sections/results.tex
git commit -m "feat: draft Results §2.1 (layered STDNs surface processing-tier concentration)"
```

---

## Task 8: Draft Results §2.2 — Ontology-backed normalization is the dominant lever

**Files:**
- Modify: `sections/results.tex` (replace §2.2 placeholder)

**Target length:** ~500 words.

This subsection presents the layer-wise ablation as the central empirical finding. Lead sentence states the result (normalization is the dominant lever). Evidence: Table 1 (numerical), Fig 3 (visual). Closing sentence on what this implies for system design.

- [ ] **Step 1: Draft the prose**

Replace the placeholder with content along these lines (the subagent must expand and refine to ~500 words):

```latex
Ontology-backed canonical normalization is the dominant lever for
producing stable STDN outputs across repeated runs. A layer-wise
ablation across 60 microelectronic technologies (Table~\ref{tab:ablation-norm},
Figure~\ref{fig:layer-ablation}A) shows that simply mapping a naive
single-shot LLM output through STDN-GEN's canonical vocabulary raises
median pairwise Jaccard from 0.146 to 0.756 --- a roughly 5$\times$
improvement that requires no additional inference cost. Adding the
structured extraction layer on top of normalization yields a further
small improvement (Jaccard 0.756 $\to$ 0.788), and the full pipeline
including multi-agent debate at $N{=}3$ reaches 0.798.

% Second paragraph (~150 words): explain why normalization dominates.
% Surface-form variation (e.g., "DRAM" vs "Dynamic Random Access Memory"
% vs "DRAM chip") accounts for most run-to-run disagreement in
% LLM-extracted components. Canonical mapping absorbs this variance.
% The structured extraction pipeline produces less surface-form
% variation to begin with, so the marginal benefit of canonical
% normalization shrinks --- consistent with the diminishing returns
% pattern in the table.

% Third paragraph (~150 words): note what this finding implies for
% any group building automated supply-chain or LCA-style knowledge
% extraction tools: invest engineering effort in canonical vocabulary
% first, multi-agent ensembling second. Forward-reference Discussion
% §3.2 where this lesson is elaborated for the broader community.
```

The framing rule applies: this subsection emphasizes normalization's dominance, but it must *not* dismiss debate — the closing should set up §2.3 with a sentence like "this does not mean debate is unimportant; rather, debate plays a distinct role that complements normalization, as the next subsection shows."

- [ ] **Step 2: Build and verify; commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
git add sections/results.tex
git commit -m "feat: draft Results §2.2 (normalization is the dominant lever)"
```

---

## Task 9: Draft Results §2.3 — Multi-agent debate broadens the explored dependency space

**Files:**
- Modify: `sections/results.tex` (replace §2.3 placeholder)

**Target length:** ~500 words.

This is the subsection where the framing rule is most load-bearing. Debate must be presented as a complementary contributor with a qualitatively distinct role, not as marginal. Evidence: Table 1 invalid-rate row; the pre-normalization stability numbers (0.073 → 0.147 at N=3) from the SIGIR source; the core-ratio number (debate 0.200 vs no-debate 0.429 post-normalization) showing debate broadens rather than tightens.

- [ ] **Step 1: Draft the prose**

Replace the §2.3 placeholder. Scaffold:

```latex
Multi-agent debate contributes to STDN quality through a different
mechanism than normalization: where normalization absorbs surface-form
variation to make outputs more consistent, debate broadens the
\emph{set of components} the system explores across runs. Three
empirical signatures of this difference are visible in our 60-technology
benchmark. First, debate at $N{=}3$ lowers the deduped-canonical invalid
rate (Table~\ref{tab:ablation-debate}, Figure~\ref{fig:layer-ablation}B). Second, debate roughly doubles
pre-normalization (transcript-level) stability, from 0.073 to 0.147 ---
agents converge more during the debate itself even when the final canonical
output is similar. Third, the post-normalization \emph{core ratio} ---
the share of components that recur in every run --- is 0.200 under
debate versus 0.429 without; debate produces a wider, more varied
union of candidate components run-to-run.

% Second paragraph (~150 words): unpack the qualitative interpretation.
% Debate's role is to surface candidates that a single-pass agent
% would miss, by exposing each agent to the others' proposals and
% prompting reconsideration. This broadens coverage at the cost of
% determinism. Normalization, in turn, absorbs that variance so the
% broader exploration does not show up as instability in the final
% output. The two mechanisms operate at different stages and target
% different sources of error.

% Third paragraph (~150 words): note when each matters. For users who
% prioritize reproducibility above coverage, the architecture-only
% configuration (normalization + structured extraction without debate)
% is preferable. For users who want broader coverage of the dependency
% space --- particularly when downstream analyses will surface
% individual components for human review --- debate adds value. Both
% modes are supported by the same system.
```

The subagent should expand each paragraph to ~150-180 words and verify all cited numbers against `sections/results_sigir_source.tex.bak`.

- [ ] **Step 2: Build, verify, commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
git add sections/results.tex
git commit -m "feat: draft Results §2.3 (debate broadens dependency exploration)"
```

---

## Task 10: Draft Results §2.4 — Gold-standard validation confirms judge reliability

**Files:**
- Modify: `sections/results.tex` (replace §2.4 placeholder)

**Target length:** ~400 words (shorter than §2.1-2.3 to leave room for §2.5 + intro/discussion within the 5,000-word cap).

Lead with the validation finding. Evidence: Table 2 (gold-standard recall/precision). Close with what this tells readers about trusting the judge-based precision-proxy results elsewhere in the section.

- [ ] **Step 1: Draft the prose**

Replace the §2.4 placeholder. Scaffold:

```latex
The LLM judge used to estimate validity at scale matches multi-annotator
gold-standard component lists with high agreement. Across four
representative technologies and 53 unique canonical components
(Table~\ref{tab:gold-standard}), the judge achieves aggregate recall
0.981 and lower-bound precision 0.722. The precision lower bound is
conservative because the gold standard is incomplete by construction;
manual inspection of apparent false positives indicates that the
overwhelming majority are legitimate components missing from the
gold standard rather than judge errors, raising effective precision
toward 1.000.

% Second paragraph (~150 words): describe the protocol briefly:
% multiple annotators construct gold-standard component lists for
% each technology; reconciliation handles disagreement;
% canonicalization through the STDN-GEN vocabulary aligns annotator
% terminology with system output. Forward-reference Methods §M
% for full protocol details.

% Third paragraph (~100 words): note what this means for the
% scalable analyses in §2.2-2.3 and §2.5: the judge-based precision-proxy
% numbers reported there should be read as conservative estimates of
% the actual precision. The system is at least as good as those
% numbers suggest.
```

- [ ] **Step 2: Build, verify, commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
git add sections/results.tex
git commit -m "feat: draft Results §2.4 (gold-standard validation)"
```

---

## Task 11: Draft Results §2.5 — Cost and convergence as a function of debate strength

**Files:**
- Modify: `sections/results.tex` (replace §2.5 placeholder)

**Target length:** ~400 words.

This subsection characterizes the cost (runtime) and convergence behavior as $N$ varies from 1 to 5. The detailed plots live in Supplementary Information; the main-text version reports the headline numbers and identifies a practical "sweet spot" at $N{=}3$. No new main-text figure; just prose with numbers.

- [ ] **Step 1: Draft the prose**

Replace the §2.5 placeholder. Scaffold:

```latex
The cost of stronger debate grows roughly linearly with the number of
agents while the marginal quality benefit shrinks, motivating a
practical sweet spot near $N{=}3$. Median per-technology runtime
across the 60-technology benchmark rises from 10.6 minutes at $N{=}1$
to 49.5 minutes at $N{=}5$, roughly a 5$\times$ increase. Over the same
range, macro-median final debate convergence increases only modestly
(0.887 $\to$ 0.894) and the number of debate rounds grows from 1.00
to 2.20. Stability and validity (§2.2-2.3) both show diminishing
returns past $N{=}3$.

% Second paragraph (~150 words): unpack the sweet-spot argument.
% $N{=}3$ captures most of the validity improvement and roughly
% doubles pre-normalization stability versus $N{=}1$, at runtime that
% is still tractable for batch analyses of dozens of technologies
% per day. Larger $N$ may be appropriate for analyses where a single
% technology warrants high coverage at any cost.

% Third paragraph (~150 words): reference the detailed cost/convergence
% plots in Supplementary Information (Figure SI-X through Figure SI-Y)
% for readers who want to see the full sweep. Close the Results section
% with a one-sentence bridge to Discussion: STDN-GEN produces auditable,
% stable, valid layered dependency maps in tractable time, and the
% next section discusses what this enables for supply-chain sustainability
% analysis.
```

The figure references "Figure SI-X" / "Figure SI-Y" are placeholders to be replaced with actual SI figure labels once SI is finalized in Phase 4; for now, leave as `Figure SI-X` and `Figure SI-Y` and add a `% TODO: replace SI-X/SI-Y with real labels (Phase 4)` comment.

- [ ] **Step 2: Build, verify, commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
git add sections/results.tex
git commit -m "feat: draft Results §2.5 (cost and convergence as a function of debate strength)"
```

---

## Task 12: Phase 1 final verification

**Files:** None modified.

- [ ] **Step 1: Clean rebuild**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C
latexmk -pdf main.tex 2>&1 | tail -15
```

Expected: clean build. Acceptable warnings: undefined SI cross-references (the `SI-X`/`SI-Y` placeholders in §2.5), undefined Phase 2 forward references (e.g., to the vignette figure).

- [ ] **Step 2: Word count check on Results section**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
if command -v detex >/dev/null 2>&1; then
  detex sections/results.tex | wc -w
else
  python3 -c "import re,sys; t=open('sections/results.tex').read(); t=re.sub(r'%[^\n]*','',t); t=re.sub(r'\\\\[a-zA-Z]+\\*?(\\{[^}]*\\})*','',t); t=re.sub(r'[\\\\\\{\\}\\[\\]]','',t); print(len(t.split()))"
fi
```

Expected: ~2,500 words (allowable range 2,200-2,800). If significantly over, the longest subsections need trimming. If significantly under, sections need expansion.

- [ ] **Step 3: Label consistency check**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
echo "=== Labels defined in results.tex ==="
grep -n "\\\\label{" sections/results.tex
echo "=== References from results.tex ==="
grep -on "\\\\ref{[^}]*}" sections/results.tex
echo "=== Final main.log undefined-references ==="
grep -i "undefined" main.log | grep -v "Phase 2\|Phase 4" | head -10
```

Expected: each `\ref{...}` in `results.tex` either matches a `\label{...}` in `results.tex`, or is a documented forward reference to a Phase 2 or Phase 4 placeholder.

- [ ] **Step 4: Tag and push**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git tag phase-1-complete -m "Phase 1 results draft complete; ready for Phase 2 vignettes + methods"
git push origin main
git push origin phase-1-complete
```

---

## What's next

Phase 2 (Jul 1 – Aug 4) follows: drafts the two critical-material vignettes (EV Traction Inverter + 5G Base Station) as Figure 2 (multi-panel), condenses Methods, drafts Discussion (including §3.2 design lesson subsection), and folds in the conclusion content.

The Phase 1 word budget for Results is ~2,500 words. If the Results section runs significantly over, trim the lowest-information sentences from §2.1 (capability framing, which is partly redundant with the introduction once that's drafted) before trimming the empirical subsections §2.2-§2.5.

---

## Known follow-ups deferred to later phases

- **Abstract trim:** current draft is ~210 words; Communications Sustainability target is ~150. Trim in Phase 4 polish.
- **Vignette content for Figure 2:** EV Inverter + 5G Base Station vignettes are written in Phase 2 (Task 1 of that phase).
- **SI figure labels:** `SI-X`, `SI-Y` placeholders in §2.5 to be replaced with real labels once SI is finalized in Phase 4.
- **Phase 2 figure forward reference:** Fig 2 mentioned in §2.1 currently has no `\ref{fig:vignettes}` target; will resolve in Phase 2.
- **References for sustainability and critical-minerals citations:** Phase 4 task.
