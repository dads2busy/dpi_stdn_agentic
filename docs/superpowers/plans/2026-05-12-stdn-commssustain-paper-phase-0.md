# Communications Sustainability Paper — Phase 0 (Setup) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a new paper repository at `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/` configured with the Springer Nature LaTeX template, SIGIR source content migrated in, cross-references documented in `CLAUDE.md`, and per-project memory initialized — producing a buildable paper skeleton ready for Phase 1 drafting.

**Architecture:** A standalone LaTeX paper repository, separate from but cross-referencing the code repo (`~/git/dpi_stdn_agentic/`) and the SIGIR source paper repo (`~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/`). Uses Springer Nature's official LaTeX template with the `sn-nature` style flag for Nature Portfolio journals. SIGIR content is migrated as starting material to be progressively rewritten through later phases.

**Tech Stack:** LaTeX (Springer Nature template, `sn-jnl.cls`), BibTeX, `latexmk` for builds, `git` for version control.

**Out of scope for this plan:** Drafting Results, Methods, Discussion, vignettes, figures, or references (these belong to Phase 1+ plans). Spec: `docs/superpowers/specs/2026-05-12-stdn-commssustain-paper-design.md`.

---

## File Structure (final state after Phase 0)

```
~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/
├── .git/                              # initialized in Task 1
├── .gitignore                         # LaTeX-appropriate ignores (Task 1)
├── CLAUDE.md                          # cross-references (Task 9)
├── README.md                          # short repo blurb (Task 9)
├── main.tex                           # Springer Nature template entry (Task 2-4)
├── sn-jnl.cls                         # Springer Nature class file (Task 2)
├── sn-mathphys-num.bst                # BibTeX style from template (Task 2)
├── references.bib                     # migrated from SIGIR (Task 5)
├── sections/
│   ├── abstract.tex                   # new content (Task 7)
│   ├── introduction.tex               # outline only (Task 8)
│   ├── results.tex                    # SIGIR content migrated (Task 6)
│   ├── discussion.tex                 # SIGIR conclusions migrated (Task 6)
│   ├── methods.tex                    # SIGIR methodology migrated (Task 6)
│   └── supplementary.tex              # SIGIR appendix+supplementary migrated (Task 6)
└── figures/                           # SIGIR images migrated (Task 5)
    ├── smartphone_stdn.pdf
    ├── stdn_layer_schematic.png
    ├── invalid_rate_occ_vs_dedup.png
    └── ... (catalogue in Task 5)
```

Also created outside the repo:
- `~/.claude/projects/-Users-ads7fg-git-D-PI-2026-05-STDN-COMMS-SUSTAIN/memory/MEMORY.md` — per-project memory index (Task 10)

---

## Task 1: Create paper repository and initial commit

**Files:**
- Create: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/.gitignore`

- [ ] **Step 1: Create the directory and initialize git**

```bash
mkdir -p ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git init
```

Expected: "Initialized empty Git repository in /Users/ads7fg/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/.git/"

- [ ] **Step 2: Write a LaTeX-appropriate `.gitignore`**

Create `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/.gitignore` with the following exact contents:

```gitignore
# LaTeX build artifacts
*.aux
*.bbl
*.blg
*.fdb_latexmk
*.fls
*.log
*.out
*.synctex.gz
*.toc
*.lof
*.lot
*.nav
*.snm
*.vrb

# OS artifacts
.DS_Store
Thumbs.db

# Editor artifacts
*.swp
.vscode/
.idea/

# Keep the PDF in this repo? No — exclude built PDFs from git
main.pdf
```

- [ ] **Step 3: Initial commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add .gitignore
git commit -m "chore: initialize Comms Sustainability paper repo"
```

Expected: A single commit with `.gitignore` added.

---

## Task 2: Acquire and install the Springer Nature LaTeX template

**Files:**
- Create: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sn-jnl.cls`
- Create: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/main.tex` (will be reduced in Task 3)
- Create: associated `.bst`, `.def`, and example files from the template archive

The official template is hosted on Overleaf at https://www.overleaf.com/latex/templates/springer-nature-latex-template/myxmhdsbzkyd and as a download from https://support.nature.com/en/support/solutions/articles/6000250920-latex-template-package-for-article-book-submissions. The template archive contains a class file (`sn-jnl.cls`), a BibTeX style, and example `main.tex` files for several Springer Nature journal styles including `sn-nature` (the one we want).

- [ ] **Step 1: Confirm the template archive is in place**

The template has already been downloaded by the user to `~/Downloads/Springer_Nature_LaTeX_Template.zip`. Verify:

```bash
ls -la ~/Downloads/Springer_Nature_LaTeX_Template.zip
```

Expected: the file exists with a non-zero size.

- [ ] **Step 2: Unpack the template into a scratch directory**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
unzip ~/Downloads/Springer_Nature_LaTeX_Template.zip -d /tmp/sn-template
ls /tmp/sn-template
```

Expected: a directory listing showing `sn-jnl.cls`, several `.bst` files, several `sn-*.tex` example files, and possibly a `Bibliography` subdirectory.

- [ ] **Step 3: Copy required template files into the repo root**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
cp /tmp/sn-template/sn-jnl.cls .
cp /tmp/sn-template/sn-*.bst .
cp /tmp/sn-template/sn-nature.tex main.tex
```

If `sn-nature.tex` is not present in the archive (templates do evolve), use the closest Nature Portfolio example (typically `sn-basic.tex` with the `sn-nature` style flag enabled). Inspect the example file's documentclass line and confirm the style:

```bash
head -5 main.tex
```

Expected: a `\documentclass[sn-nature,...]{sn-jnl}` line or similar. If the style flag is missing, add `sn-nature` to the documentclass options manually.

- [ ] **Step 4: Build the template to verify it compiles**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex
```

Expected: `main.pdf` is generated. Any errors at this step indicate a missing class file dependency — re-check that all `sn-*.cls` and `sn-*.bst` files were copied.

- [ ] **Step 5: Commit the template files**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add sn-jnl.cls sn-*.bst main.tex
git commit -m "chore: add Springer Nature LaTeX template (sn-nature style)"
```

---

## Task 3: Replace the template's example body with our paper skeleton

**Files:**
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/main.tex`

- [ ] **Step 1: Read the current `main.tex` to identify the body region**

Open `main.tex` and locate the region between `\begin{document}` and `\end{document}`. This is the example content shipped with the Springer Nature template (placeholder authors, abstract, sections). Keep the preamble (everything before `\begin{document}`).

- [ ] **Step 2: Replace the body with our paper skeleton**

Replace the content between `\begin{document}` and `\end{document}` with the following exact content. Preserve the existing preamble above `\begin{document}`.

```latex
\begin{document}

\title{STDN-GEN: rapid synthesis of layered critical-material dependency networks for supply-chain sustainability analysis}

\author*[1]{\fnm{Aaron} \sur{Schroeder}}\email{ads7fg@virginia.edu}

\affil*[1]{\orgdiv{Biocomplexity Institute}, \orgname{University of Virginia}, \city{Charlottesville}, \state{VA}, \country{USA}}

\abstract{\input{sections/abstract}}

\keywords{critical materials, supply chain, multi-agent systems, large language models, sustainability, dependency networks}

\maketitle

\section{Introduction}\label{sec:intro}
\input{sections/introduction}

\section{Results}\label{sec:results}
\input{sections/results}

\section{Discussion}\label{sec:discussion}
\input{sections/discussion}

\section{Methods}\label{sec:methods}
\input{sections/methods}

\backmatter

\bmhead{Data availability} \emph{To be completed in Phase 4.}
\bmhead{Code availability} \emph{To be completed in Phase 4.}
\bmhead{Acknowledgements} \emph{To be completed in Phase 4.}

\bibliography{references}

\input{sections/supplementary}

\end{document}
```

Note: the author and affiliation entries above are a placeholder using the spec's git user (Aaron Schroeder). Full author list (11 authors per the SIGIR `authors_db.tex`) will be migrated in a later phase.

- [ ] **Step 3: Build to verify the skeleton compiles (will fail because sections/ doesn't exist yet — expected)**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex
```

Expected: `latexmk` errors because `sections/abstract.tex` etc. do not exist yet. This is expected — Task 6 will create them. Do not commit yet.

- [ ] **Step 4: Create empty section placeholder files so the build succeeds**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
mkdir -p sections figures
for f in abstract introduction results discussion methods supplementary; do
  printf "%% Placeholder — content migrated in subsequent tasks.\n" > "sections/$f.tex"
done
touch references.bib
```

- [ ] **Step 5: Rebuild and verify a clean compile**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C  # clean build artifacts
latexmk -pdf main.tex
```

Expected: `main.pdf` builds without errors. The PDF will be largely empty (placeholder content only), but the build must succeed.

- [ ] **Step 6: Commit the skeleton**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add main.tex sections/ references.bib
git commit -m "feat: skeleton main.tex and empty section placeholders"
```

---

## Task 4: Migrate SIGIR section contents as starting material

The intent of this task is to **copy SIGIR sources verbatim into our new section files** so we have working starting material to rewrite from. The actual rewrite happens in Phases 1-2.

**Files:**
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/abstract.tex`
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/results.tex`
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/discussion.tex`
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/methods.tex`
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/supplementary.tex`

- [ ] **Step 1: Copy abstract**

```bash
cp ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/abstract.tex \
   ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/abstract.tex
```

- [ ] **Step 2: Combine SIGIR validity_robustness_cost.tex + case_study.tex into results.tex**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
{
  echo "% Migrated from SIGIR validity_robustness_cost.tex + case_study.tex — to be restructured per spec §2 (5 subsections)"
  echo ""
  echo "% === BEGIN SIGIR validity_robustness_cost.tex ==="
  cat ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/validity_robustness_cost.tex
  echo ""
  echo "% === BEGIN SIGIR case_study.tex ==="
  cat ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/case_study.tex
} > sections/results.tex
```

- [ ] **Step 3: Copy SIGIR conclusions.tex into discussion.tex**

```bash
cp ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/conclusions.tex \
   ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/discussion.tex
```

- [ ] **Step 4: Copy SIGIR methodology.tex into methods.tex**

```bash
cp ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/methodology.tex \
   ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/methods.tex
```

- [ ] **Step 5: Combine SIGIR appendix.tex + supplementary.tex into supplementary.tex**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
{
  echo "% Migrated from SIGIR appendix.tex + supplementary.tex"
  echo ""
  echo "% === BEGIN SIGIR appendix.tex ==="
  cat ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/appendix.tex
  echo ""
  echo "% === BEGIN SIGIR supplementary.tex ==="
  cat ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/supplementary.tex
} > sections/supplementary.tex
```

- [ ] **Step 6: Copy SIGIR introduction.tex (will be heavily rewritten in Phase 1)**

```bash
cp ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/introduction.tex \
   ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/introduction.tex
```

- [ ] **Step 7: Build to confirm migrated content compiles under sn-jnl.cls**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C
latexmk -pdf main.tex 2>&1 | tail -40
```

Expected: Build may emit warnings about missing figure files (figures haven't been migrated yet — Task 5 handles that). The build may complete with a warning about missing graphics, or may fail; in either case capture the output. Some structural complaints (e.g., `\includegraphics` paths that point at the SIGIR layout `images/...`) will appear and are expected — we will fix those references in a later phase.

- [ ] **Step 8: Commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add sections/
git commit -m "feat: migrate SIGIR section contents as starting material"
```

---

## Task 5: Migrate figures and bibliography from SIGIR

**Files:**
- Create (copies): `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/figures/*`
- Create: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/references.bib` (replace stub from Task 3)

- [ ] **Step 1: Copy all figures from SIGIR images/ to new figures/**

```bash
cp -R ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/images/* \
      ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/figures/
```

- [ ] **Step 2: Verify the six main-text figures from the spec are present**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/figures
for f in stdn_layer_schematic.png \
         invalid_rate_occ_vs_dedup.png \
         paired_invalid_rate_dedup_N1_vs_N3.png \
         stability_heatmap_by_tech_and_n.png \
         validity_vs_n_dedup_invalid_and_k.png \
         tradeoff_runtime_vs_stability.png \
         convergence_rounds_vs_n.png; do
  test -f "$f" && echo "OK: $f" || echo "MISSING: $f"
done
```

Expected: all seven files report `OK`. (The smartphone STDN figure is built from TikZ inside `case_study.tex`, not a static image — that's why it's not listed here.)

- [ ] **Step 3: Copy SIGIR references.bib**

```bash
cp ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/references.bib \
   ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/references.bib
```

- [ ] **Step 4: Rewrite `\includegraphics` paths in section files (`images/` → `figures/`)**

The migrated SIGIR sections reference figures under `images/` but our repo uses `figures/`. Use `sed` to rewrite:

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
sed -i.bak 's|{images/|{figures/|g' sections/results.tex
sed -i.bak 's|{images/|{figures/|g' sections/methods.tex
sed -i.bak 's|{images/|{figures/|g' sections/supplementary.tex
rm sections/*.bak
```

- [ ] **Step 5: Verify build now succeeds with figures present**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C
latexmk -pdf main.tex 2>&1 | tail -20
```

Expected: Build completes. There may be warnings about figure size or content that doesn't match Nature Portfolio's column layout, but no fatal errors. If a fatal error remains, it is most likely a TikZ figure (e.g., the smartphone STDN figure inline in `case_study.tex` content) requiring additional package imports; fix the preamble in `main.tex` by adding `\usepackage{tikz}` and any required TikZ libraries to match what SIGIR used.

- [ ] **Step 6: Commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add figures/ references.bib sections/
git commit -m "feat: migrate figures and bibliography from SIGIR"
```

---

## Task 6: Add `\usepackage` imports needed by migrated SIGIR content

The Springer Nature template provides a baseline preamble that may not include all packages used by SIGIR content (TikZ, algorithm, ctable, etc.). This task harmonizes the preamble.

**Files:**
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/main.tex`

- [ ] **Step 1: Identify packages used by SIGIR `main.tex`**

```bash
grep -h "^\\\\usepackage" ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/main.tex
```

Expected output (or similar):
```
\usepackage[margin=1in]{geometry}
\usepackage{balance}
\usepackage{algorithm}
\usepackage{algorithmic}
\usepackage{float}
\usepackage{tikz}
\usepackage{ctable}
\usepackage{array}
\usepackage{longtable}
\usepackage{ulem}
\usepackage{ragged2e}
\usepackage{natbib}
\usepackage{url}
\usepackage{etoolbox}
\usepackage{fancyhdr}
\usepackage{xcolor}
\usepackage{enumitem}
```

- [ ] **Step 2: Add the necessary subset to `main.tex` preamble**

Open `main.tex` and locate the preamble (between the existing `\documentclass{}` line and `\begin{document}`). Insert the following block after the existing `sn-jnl` preamble, but **omit packages already provided by `sn-jnl.cls`** (you may need to comment one out and rebuild to check). The safe additions are:

```latex
% Packages required by migrated SIGIR content
\usepackage{algorithm}
\usepackage{algorithmic}
\usepackage{float}
\usepackage{tikz}
\usetikzlibrary{positioning, arrows.meta, shadows, shapes.geometric, fit}
\usepackage{ctable}
\usepackage{array}
\usepackage{longtable}
\usepackage{ulem}
\usepackage{ragged2e}
\usepackage{enumitem}

% Custom column type used by SIGIR tables
\newcolumntype{R}[1]{>{\raggedleft\arraybackslash}p{#1}}

% Helper macros from SIGIR
\newcommand{\tcedge}{\texttt{T}$\to$\texttt{C}}
\newcommand{\cmedge}{\texttt{C}$\to$\texttt{M}}
\newcommand{\mnedge}{\texttt{M}$\to$\texttt{P}}
\newcommand{\todo}[1]{\textcolor{red}{[[#1]]}}
```

Do **not** add `geometry`, `natbib`, `xcolor`, `fancyhdr`, `etoolbox`, or `url` — these are typically provided by `sn-jnl.cls` and re-adding them will cause "option clash" errors. If a build error names one of these, comment out the corresponding line in `main.tex` and rebuild.

- [ ] **Step 3: Rebuild and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C
latexmk -pdf main.tex 2>&1 | tail -30
```

Expected: Clean build, possibly with a few `LaTeX Warning: Reference ... undefined` (citations or labels) which are non-fatal. If a fatal error names a package, address it per the comment in Step 2.

- [ ] **Step 4: Commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add main.tex
git commit -m "chore: add LaTeX packages required by migrated SIGIR content"
```

---

## Task 7: Write the new abstract

Replace the migrated SIGIR abstract with the new positioning paragraph from the spec.

**Files:**
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/abstract.tex`

- [ ] **Step 1: Replace the abstract content**

Overwrite `sections/abstract.tex` with the following exact content:

```latex
Vulnerability and sustainability analyses of critical-material supply chains are bottlenecked by the manual, fragmented work of mapping how a technology decomposes into components, materials, and producing countries. We present STDN-GEN, a multi-agent system that synthesizes auditable \emph{shallow technology dependency networks}---layered DAGs from technology to component to material to country---from unstructured sources, grounded in a canonical vocabulary. Across 60 microelectronic technologies we attribute output quality to its sources. Ontology-backed normalization is the dominant lever, raising run-to-run stability from $0.146$ to $0.756$. Multi-agent debate is a complementary contributor that operates differently: rather than converging the system on a stable core, debate \emph{broadens} the explored dependency space, roughly doubling pre-normalization stability ($0.073 \to 0.147$) and lowering the invalid rate ($0.063 \to 0.049$ at three agents). Gold-standard validation on four technologies confirms judge precision approaches $1.000$. A smartphone case study and short critical-material vignettes demonstrate how layered networks surface processing-layer concentration bottlenecks that component-only analyses miss.
```

- [ ] **Step 2: Rebuild and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -10
```

Expected: build succeeds; abstract appears in the PDF.

- [ ] **Step 3: Commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add sections/abstract.tex
git commit -m "feat: write Comms Sustainability abstract"
```

---

## Task 8: Replace introduction with a structured outline

The migrated SIGIR introduction needs to be replaced with an outline reflecting the new sustainability framing. The outline gives Phase 1 a concrete scaffold to flesh out.

**Files:**
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/introduction.tex`

- [ ] **Step 1: Replace the introduction content with the outline**

Overwrite `sections/introduction.tex` with:

```latex
% === INTRODUCTION OUTLINE (~700 words target) ===
% This is a scaffold to be filled in during Phase 1. Each paragraph below
% describes the intended content, not the final prose. Related Work is folded
% into this section as inline citations rather than carrying its own section.

% Paragraph 1 (~150 words): The sustainability bottleneck.
% - Critical materials underpin energy transition technologies, semiconductors,
%   medical devices, defense systems.
% - Vulnerability analysis requires linking finished products to components,
%   materials, and producing countries.
% - Today: manual, fragmented across sources, days per technology, incomplete
%   coverage. Cite Graedel, IEA Critical Minerals, EU CRM Act, USGS reports.
% - Concrete example to ground the problem (semiconductor shortage, EV battery
%   minerals).

% Paragraph 2 (~150 words): What's been tried.
% - Existing automated approaches (IO tables, MFA, LCA tools) and their limits.
% - Recent LLM-based extraction work for materials/manufacturing (cite Nature
%   Sust., npj Mat Sustain., Comms Earth Env papers); none produces auditable
%   layered representations at the speed required for time-constrained analysis.
% - The gap: a representation + system that is fast, layered, and auditable.

% Paragraph 3 (~150 words): What we contribute.
% - Define the shallow technology dependency network (STDN).
% - STDN-GEN: a multi-agent system that combines (a) structured extraction +
%   ontology-backed canonical normalization with (b) agreement-feedback-driven
%   debate for component extraction.
% - Output: auditable layered DAGs from technology to producing country.

% Paragraph 4 (~150 words): What we show.
% - Layer-wise ablation across 60 microelectronic technologies attributes
%   quality to its sources; canonical normalization is the dominant lever and
%   debate is a complementary contributor that broadens the explored space.
% - Gold-standard validation on four technologies confirms judge reliability.
% - Smartphone case study + two critical-material vignettes (EV traction
%   inverter, 5G base station) demonstrate how layered networks surface
%   processing-tier concentration bottlenecks that component-only analyses miss.

% Paragraph 5 (~100 words): Why it matters for sustainability practice.
% - Faster, broader vulnerability screening across critical-material technologies.
% - Auditable structure (canonical vocabulary, judge-validated outputs) supports
%   downstream uses (concentration indices, stress tests, comparative analysis).
% - A transferable design lesson for the broader community building automated
%   sustainability-knowledge extraction tools.
% - Bridge into the rest of the paper: layered STDNs and the STDN-GEN system,
%   followed by results and a discussion of implications.

\emph{Introduction content to be drafted in Phase 1 against this outline.}
```

- [ ] **Step 2: Rebuild and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -10
```

Expected: clean build.

- [ ] **Step 3: Commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add sections/introduction.tex
git commit -m "feat: introduction outline scaffold for Phase 1 drafting"
```

---

## Task 9: Write `CLAUDE.md` and `README.md`

Document the paper's relationship to the code repo, the SIGIR source repo, target journal, and deadline.

**Files:**
- Create: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/CLAUDE.md`
- Create: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/README.md`

- [ ] **Step 1: Write `CLAUDE.md`**

Create `CLAUDE.md` with the following exact content:

````markdown
# STDN-GEN — Communications Sustainability Paper

This repository contains the LaTeX source for an Article submission to **Communications Sustainability**, part of the Nature Portfolio cross-journal collection [Critical materials supply chain sustainability](https://www.nature.com/collections/eaebjccaab).

## Deadline

**Collection deadline:** 2026-10-28
**Internal submission target:** 2026-10-21

## Related repositories

- **Code:** `~/git/dpi_stdn_agentic/` — STDN-GEN pipeline implementation. Empirical work, experiment configs, validation scripts, and per-technology outputs all live here.
- **Source paper:** `~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/` — the SIGIR draft from which this Communications Sustainability paper is adapted. SIGIR is the source of truth for figures and prose that have not yet been rewritten here.

## Paper structure

- `main.tex` — entry point; uses Springer Nature LaTeX template (`sn-jnl.cls`) with `sn-nature` style flag for Nature Portfolio journals.
- `sections/` — body sections (abstract, introduction, results, discussion, methods, supplementary).
- `figures/` — all figure source files; main-text figures are listed in the design spec.
- `references.bib` — bibliography (extends the SIGIR `references.bib`; sustainability/critical-minerals citations to be added in Phase 4).

## Build

```bash
latexmk -pdf main.tex
```

## Design spec

`~/git/dpi_stdn_agentic/docs/superpowers/specs/2026-05-12-stdn-commssustain-paper-design.md`

## Memory

Per-project Claude memory: `~/.claude/projects/-Users-ads7fg-git-D-PI-2026-05-STDN-COMMS-SUSTAIN/memory/MEMORY.md`

## Framing rule

When summarizing the ablation results, credit both **ontology-backed normalization** and **multi-agent debate** as complementary contributors. Normalization is the dominant lever for stability; debate has a qualitatively different role (broadens exploration rather than converging on a stable core). Do not let debate read as worthless. See the design spec for full framing language and the feedback memory `feedback_normalization_vs_debate_framing` in code-repo memory.
````

- [ ] **Step 2: Write `README.md`**

Create `README.md` with:

```markdown
# STDN-GEN — Communications Sustainability Paper

LaTeX source for an Article submission to Communications Sustainability (Nature Portfolio cross-journal collection "Critical materials supply chain sustainability"), deadline 2026-10-28.

See `CLAUDE.md` for relationships to companion repositories and `main.pdf` (after building) for the rendered paper.

## Build

```bash
latexmk -pdf main.tex
```
```

- [ ] **Step 3: Commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add CLAUDE.md README.md
git commit -m "docs: add CLAUDE.md and README cross-referencing code and SIGIR repos"
```

---

## Task 10: Initialize per-project Claude memory

Set up a memory directory for the new paper repo so future Claude sessions opening the paper repo have a starting context.

**Files:**
- Create: `~/.claude/projects/-Users-ads7fg-git-D-PI-2026-05-STDN-COMMS-SUSTAIN/memory/MEMORY.md`

- [ ] **Step 1: Create the memory directory**

```bash
mkdir -p ~/.claude/projects/-Users-ads7fg-git-D-PI-2026-05-STDN-COMMS-SUSTAIN/memory
```

- [ ] **Step 2: Write the initial `MEMORY.md` index**

Create `~/.claude/projects/-Users-ads7fg-git-D-PI-2026-05-STDN-COMMS-SUSTAIN/memory/MEMORY.md` with:

```markdown
# Communications Sustainability Paper — Memory Index

## Cross-project memory

This paper is adapted from the SIGIR draft at `~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/` (memory: `~/.claude/projects/-Users-ads7fg-git-D-PI-2026-01-STDN-AGENTIC-SIGIR/memory/MEMORY.md`). The underlying code lives at `~/git/dpi_stdn_agentic/` (memory: `~/.claude/projects/-Users-ads7fg-git-dpi-stdn-agentic/memory/MEMORY.md`). Consult both indexes when working on this paper — the SIGIR memory covers paper-side decisions on Stage 2b features and figure choices; the code memory covers empirical results, model configs, and rerun history.

## Project overview

Article submission to Communications Sustainability (Nature Portfolio) for the cross-journal collection "Critical materials supply chain sustainability" (collection ID `eaebjccaab`).

- **Collection deadline:** 2026-10-28
- **Internal target:** 2026-10-21
- **Approach:** Tool/Resource article framing STDN-GEN as a digital-transformation tool for supply-chain sustainability analysis. No new pipeline runs; all empirical content adapted from existing SIGIR data and 60-tech microelectronics outputs.

## Key framing rule

Credit both ontology-backed normalization and multi-agent debate as complementary contributors. Normalization is the dominant lever for stability; debate broadens the explored dependency space. Do not let debate read as worthless.

## Repository structure

- `main.tex` — entry point; Springer Nature LaTeX template, `sn-nature` style.
- `sections/abstract.tex`, `introduction.tex`, `results.tex`, `discussion.tex`, `methods.tex`, `supplementary.tex`.
- `figures/` — all figures (migrated from SIGIR `images/`).
- `references.bib` — extends SIGIR references; sustainability literature added in Phase 4.

## Design spec

`~/git/dpi_stdn_agentic/docs/superpowers/specs/2026-05-12-stdn-commssustain-paper-design.md`

## Memory index

(Add entries here as project-specific memories accrue.)
```

- [ ] **Step 3: Verify the memory directory layout**

```bash
ls -la ~/.claude/projects/-Users-ads7fg-git-D-PI-2026-05-STDN-COMMS-SUSTAIN/memory/
```

Expected: `MEMORY.md` is present. (No git commit — this directory lives outside the repo.)

---

## Task 11: Final Phase 0 verification and checkpoint commit

**Files:**
- None modified; this task verifies the cumulative state.

- [ ] **Step 1: Clean and rebuild from scratch**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C
latexmk -pdf main.tex 2>&1 | tail -15
```

Expected: clean build to `main.pdf`. Warnings about undefined references or missing critical-material citations are acceptable at this stage (they belong to later phases). Fatal errors should be zero.

- [ ] **Step 2: Verify expected files exist**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
for f in main.tex sn-jnl.cls CLAUDE.md README.md references.bib .gitignore \
         sections/abstract.tex sections/introduction.tex sections/results.tex \
         sections/discussion.tex sections/methods.tex sections/supplementary.tex; do
  test -f "$f" && echo "OK: $f" || echo "MISSING: $f"
done
test -d figures && echo "OK: figures/ dir" || echo "MISSING: figures/ dir"
test -f ~/.claude/projects/-Users-ads7fg-git-D-PI-2026-05-STDN-COMMS-SUSTAIN/memory/MEMORY.md \
     && echo "OK: per-project memory" || echo "MISSING: per-project memory"
```

Expected: every line reports `OK`.

- [ ] **Step 3: Verify the PDF contains the new abstract**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
# A simple grep is unreliable on PDFs; visually inspect main.pdf and confirm:
# - Title reads "STDN-GEN: rapid synthesis of layered critical-material..."
# - Abstract begins with "Vulnerability and sustainability analyses..."
# - Introduction shows the outline scaffold (placeholder text)
open main.pdf
```

Expected: the PDF opens; title and abstract match the spec.

- [ ] **Step 4: Tag the Phase 0 completion**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git tag phase-0-complete -m "Phase 0 setup complete; ready for Phase 1 drafting"
git log --oneline
```

Expected: the tag appears in the commit history; commits visible for each of Tasks 1-9.

---

## What's next

Phase 0 is complete when this plan finishes. The next plan to write covers **Phase 1 — Results draft** (May 27 – Jun 30). It will decompose into per-subsection drafting tasks:

- Results §2.1 — Layered STDNs surface processing-tier concentration (smartphone + vignettes intro)
- Results §2.2 — Ontology-backed normalization is the dominant quality lever
- Results §2.3 — Multi-agent debate broadens dependency exploration
- Results §2.4 — Gold-standard validation confirms judge reliability
- Results §2.5 — Cost and convergence as a function of debate strength
- Figure 3 (layer-wise ablation, 2-panel) regeneration
- Figure 4 (STDN representation + pipeline overview) regeneration
- Figure 1 (smartphone STDN) reformatting

Phase 1 plan to be authored once Phase 0 is verified complete and any setup issues are resolved.
