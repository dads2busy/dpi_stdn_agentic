# Communications Sustainability Paper — Phase 2 (Vignettes, Methods, Discussion, Introduction) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the paper to v1 (a fully-drafted submission-shaped manuscript) by drafting the four remaining placeholder/migrated sections — Introduction, Methods (condensed), Discussion, Fig 2 vignettes — plus the §2.1 update that ties Fig 2 into Results.

**Architecture:** Prose-heavy phase. Most tasks are draft-or-condense work in `sections/*.tex`. One figure-construction task (Fig 2 multi-panel for EV Traction Inverter and 5G Base Station vignettes) draws on existing 60-tech normalized outputs in `~/git/dpi_stdn_agentic/output/normalized/manifests_by_technology/`. Each subsection follows the same lead-with-finding pattern used in Phase 1 Results.

**Tech Stack:** LaTeX (`sn-jnl.cls`), `latexmk`. TikZ for vignette diagrams. No new pipeline runs required.

**Word and display-item constraints (per [Communications Sustainability guidelines](https://www.nature.com/commssustain/submit/submission-guidelines)):**
- Abstract: ~150 words (current ~210; trim deferred to Phase 4).
- Main text (Intro + Results + Discussion): ≤ 5,000 words.
- Methods: concise; typically ≤ 3,000 words, may be longer if necessary. Migrated SIGIR Methods is **2,692 words** — near the soft cap. **Target: condense to ~1,500 words.**
- Display items ≤ 10. After Phase 1 we have 7 (Figs 1, 3, 4 + Tables 1a, 1b, 2). Phase 2 adds **Fig 2** → 8 total, still well under cap.

**Word targets for this phase:**
- Introduction: ~700 words.
- Discussion: ~1,000 words (incl. §3.1 sustainability implications and §3.2 design-lesson subsection ~250 words).
- Methods condensed: ~1,500 words (~1,150 cut from 2,692).
- §2.1 update: +~150 words for the vignette paragraph.

**Spec:** `docs/superpowers/specs/2026-05-12-stdn-commssustain-paper-design.md`. Repo: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/`.

---

## Execution Order Rationale

1. **Introduction first (Task 1):** independent of all other work; can draft from the existing outline scaffold. Pulls forward content for §2.1 to reference.
2. **Methods condensing (Task 2):** independent; specialized editing work.
3. **Discussion (Task 3):** depends on Results (drafted) and Methods (condensed) being in their final shape.
4. **Fig 2 vignettes (Task 4):** independent of prose work; involves data extraction from code repo.
5. **§2.1 update (Task 5):** depends on Fig 2's label existing.
6. **Phase 2 verification (Task 6):** final word counts, label check, tag.

---

## Task 1: Draft the Introduction (~700 words)

**Files:**
- Modify: `sections/introduction.tex` (currently an outline scaffold)

The existing outline in `sections/introduction.tex` has five paragraph-purpose comments. Expand each comment into prose of the indicated length, preserving the framing rule and pulling facts from the migrated SIGIR introduction available at `~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/introduction.tex` (the original full SIGIR intro).

**Structure (paragraphs and target lengths from the scaffold):**

| Paragraph | Target | Content |
|---|---|---|
| 1 | ~150 words | Sustainability bottleneck: critical materials underpin energy-transition tech, semiconductors, medical devices, defense; vulnerability analysis requires linking products → components → materials → countries; today manual, days per tech, incomplete coverage. Concrete example to ground (semiconductor shortage, EV battery minerals). Cite IEA Critical Minerals Outlook, EU CRM Act, USGS reports. |
| 2 | ~150 words | What's been tried: IO tables, MFA, LCA tools and their limits. Recent LLM-based extraction work for materials/manufacturing (cite Nature Sust., npj Mat Sustain., Comms Earth Env papers). The gap: a representation + system that is fast, layered, and auditable. |
| 3 | ~150 words | What we contribute: define the STDN; introduce STDN-GEN (specialized extraction + ontology-backed canonical normalization + agreement-feedback debate); output is auditable layered DAGs. |
| 4 | ~150 words | What we show: layer-wise ablation across 60 microelectronic technologies attributes quality to its sources; canonical normalization is the dominant lever; debate is a complementary contributor that broadens explored space; gold-standard validation on four technologies; smartphone case study + EV inverter and 5G base station vignettes show layered networks surface processing-tier concentration. |
| 5 | ~100 words | Why it matters for sustainability practice: faster vulnerability screening, auditable structure, transferable design lesson. Bridge: "We describe the representation and system, then present results, then discuss implications." |

**Framing rule:** paragraph 4 must credit both normalization and debate as complementary; do not let debate read as marginal. Specifically, the sentence introducing the ablation result should say something like "*canonical normalization is the dominant lever for stability, while multi-agent debate plays a qualitatively distinct, complementary role*" rather than "normalization matters most and debate matters a little."

**Citations:** the SIGIR intro already cites foundational works (Graedel et al. on materials criticality). Reuse those citations. Add placeholders `\cite{TODO-iea-cm-2025}` for IEA Critical Minerals Outlook and `\cite{TODO-eu-crm-act-2023}` for the EU CRM Act — actual bib entries to be added in Phase 4.

**Steps:**

- [ ] **Step 1: Read the migrated SIGIR introduction for source material**

```bash
cat ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/introduction.tex
```

- [ ] **Step 2: Replace the outline in `sections/introduction.tex` with full prose**

Write the file to overwrite the scaffold. Keep the leading `% !TeX root = ../main.tex` directive.

- [ ] **Step 3: Build, word-count, verify, commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
python3 -c "
import re
content = open('sections/introduction.tex').read()
content = re.sub(r'%[^\n]*', '', content)
content = re.sub(r'\\\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})*', '', content)
content = re.sub(r'[\\\\\\{\\}\\[\\]]', '', content)
print(f'Introduction: {len(content.split())} words')
"
git add sections/introduction.tex
git commit -m "feat: draft Introduction (~700 words) from outline scaffold"
```

Expected: ~600-800 words. If outside that range, adjust.

---

## Task 2: Condense Methods (~2,692 → ~1,500 words)

**Files:**
- Modify: `sections/methods.tex` (currently 2,692 words from migrated SIGIR methodology)

The migrated content is comprehensive but verbose for the journal. Cut to ~1,500 words while preserving:
1. The STDN representation definition (semantic, not architectural — keep one paragraph).
2. The STDN-GEN three-stage pipeline (extract → debate → normalize) — keep a compact description.
3. The debate protocol (agreement-feedback mechanism, Jaccard convergence stopping criterion) — keep.
4. Canonical vocabulary methodology — keep a paragraph.
5. Judge protocol for validity estimation — keep.
6. Gold-standard annotation protocol — keep.
7. The 60-technology benchmark — keep one sentence reference; expand into supplementary if more detail needed.

**Cut targets:**
- Detailed architecture diagrams description (the figure does this work) — cut prose duplication.
- Step-by-step algorithm pseudocode for debate convergence — cut from main text, move to SI.
- Detailed implementation notes (model selection, retry logic, caching) — cut from main text, move to SI.
- Long examples of agent prompts — cut from main text, move to SI.
- Multiple examples of canonical mappings — keep one illustrative example, cut others.
- Lengthy discussion of design tradeoffs (these belong in Discussion) — cut.

**Forward-references:**
Add forward references to Supplementary Information where content is moving (e.g., "Full agent prompts are provided in Supplementary Methods S1; the convergence algorithm is detailed in Supplementary Methods S2."). Use `\ref{si:prompts}`, `\ref{si:convergence}` as placeholder labels; add `% TODO: confirm SI labels in Phase 4` markers.

**Steps:**

- [ ] **Step 1: Read current Methods**

```bash
cat ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/methods.tex
```

- [ ] **Step 2: Edit aggressively**

Use Edit with multiple targeted deletions and rewrites. Each cut should preserve technical correctness while shortening. After editing, re-count:

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
python3 -c "
import re
content = open('sections/methods.tex').read()
content_no_alg = re.sub(r'\\\\begin\\{algorithm\\}.*?\\\\end\\{algorithm\\}', '', content, flags=re.DOTALL)
content_no_alg = re.sub(r'\\\\begin\\{figure\\}.*?\\\\end\\{figure\\}', '', content_no_alg, flags=re.DOTALL)
content_no_alg = re.sub(r'\\\\begin\\{table\\}.*?\\\\end\\{table\\}', '', content_no_alg, flags=re.DOTALL)
content_clean = re.sub(r'%[^\n]*', '', content_no_alg)
content_clean = re.sub(r'\\\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})*', '', content_clean)
content_clean = re.sub(r'[\\\\\\{\\}\\[\\]]', '', content_clean)
print(f'Methods: {len(content_clean.split())} words')
"
```

Target: 1,400-1,700 words. If above 1,700, identify the longest remaining sections and cut further. If below 1,400, you may have cut too aggressively — restore key passages.

- [ ] **Step 3: Build and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -10
```

Expected: clean build. The Methods section in the PDF should be visibly shorter than the previous build. New `\ref` to SI labels will produce undefined-reference warnings; these are acceptable and tagged with `% TODO: confirm SI labels in Phase 4`.

- [ ] **Step 4: Commit**

```bash
git add sections/methods.tex
git commit -m "refactor: condense Methods from 2,692 to ~1,500 words; move detail to Supplementary"
```

---

## Task 3: Draft the Discussion (~1,000 words)

**Files:**
- Modify: `sections/discussion.tex` (currently SIGIR conclusions, ~580 words)

The migrated SIGIR conclusions provides a foundation but is shorter and conference-shaped. Restructure into two subsections matching the spec:

- **§3.1 Sustainability implications** (~700 words): when to use STDNs; what becomes possible; limits.
- **§3.2 Design lesson for automated sustainability-knowledge extraction** (~250 words): the normalization-vs-debate finding as practitioner guidance for groups building similar tools.

**Structure for §3.1 (no `\subsection{}` heading — combine the two paragraphs in single section, or use subsections; choose the cleaner option for Springer Nature style):**

Paragraph 1 (~200 words): What STDN-GEN enables. Rapid (~minutes per technology) vulnerability screening across many technologies; auditable (canonical vocab + judge-validated outputs) supporting downstream uses including concentration indices, stress tests, comparative analyses. The smartphone case study and the EV inverter / 5G base station vignettes exemplify the *kinds* of analyses now tractable. Forward-reference: this enables comparative critical-material analyses across the energy transition that were prohibitively expensive when each technology required manual mapping.

Paragraph 2 (~250 words): When this approach is and isn't right. Speed-vs-depth tradeoff: STDNs are intentionally shallow (not full BOM); appropriate for first-pass vulnerability screening and comparative analysis but not for design-level supply chain optimization. The country layer reports producer concentration, not refining vs mining decomposition (Stage 2b process consumables partly addresses this but is out of scope here). Future directions: variable-depth representations; time-indexed snapshots for tracking shifts; integration with explicit risk-scoring modules.

Paragraph 3 (~250 words): Limits and caveats. Outputs are bounded by source availability and timeliness — proprietary or weakly documented relationships may be missing or ambiguous. Judge-based validity is a useful scalable signal but does not capture correlated errors or systematic failure modes; calibration and error taxonomies are open work. Multi-language and non-Western-language sources are an underexplored frontier. Cross-source validation (e.g., reconciling LLM-extracted material lists against USGS commodity reports) is partially implemented; broader strengthening of evidence streams is a clear next step.

**Structure for §3.2 (with subsection heading):**

`\subsection{A design lesson for automated sustainability-knowledge extraction}\label{sec:design-lesson}`

(~250 words, 1-2 paragraphs):

Paragraph 1 (~150 words): Reframe the normalization-vs-debate finding as transferable guidance. "For teams building automated tools for analogous supply-chain or LCA-style knowledge tasks under a fixed engineering budget, canonical-vocabulary investment should come before multi-agent ensembling. We observed a ~5× stability improvement from normalization alone, versus a ~2× pre-normalization stability improvement from debate on top of structured extraction. The two are complementary, but the normalization layer absorbs the dominant source of run-to-run variance — surface-form differences in how the same component is named — that ensembling cannot."

Paragraph 2 (~100 words): Generalize the lesson. Many sustainability-knowledge tasks (lifecycle inventories, criticality assessments, material flow models) face the same surface-form variance problem. Domain ontologies and canonical vocabularies should be treated as first-class engineering artifacts in such systems, not afterthoughts. Multi-agent ensembling has its place — as we showed, it broadens the explored space and reduces validity errors — but it is not a substitute for getting the canonical vocabulary right.

**Steps:**

- [ ] **Step 1: Replace `sections/discussion.tex` content with the two-subsection draft**

Use Write to overwrite (the SIGIR conclusions content gets replaced wholesale; it's already preserved in git history if needed).

- [ ] **Step 2: Build, word-count, commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
python3 -c "
import re
content = open('sections/discussion.tex').read()
content = re.sub(r'%[^\n]*', '', content)
content = re.sub(r'\\\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})*', '', content)
content = re.sub(r'[\\\\\\{\\}\\[\\]]', '', content)
print(f'Discussion: {len(content.split())} words')
"
git add sections/discussion.tex
git commit -m "feat: draft Discussion (~1,000 words) including §3.2 design-lesson subsection"
```

Expected: ~900-1,100 words.

---

## Task 4: Build Fig 2 — Critical-material vignettes (EV Traction Inverter + 5G Base Station)

**Files:**
- Create: `figures/fig2_vignettes.tex`
- Create: `figures/fig2_vignettes_make.py` (optional — only if matplotlib is the right tool; otherwise TikZ-only inside `fig2_vignettes.tex`)

The figure has two panels (A: EV Traction Inverter; B: 5G Base Station), each a compact STDN diagram highlighting the critical-material concentration story for that technology. Data source: existing normalized outputs in `~/git/dpi_stdn_agentic/output/normalized/manifests_by_technology/`.

**Approach options (subagent picks based on what's cleanest):**

- **Option A — TikZ diagrams** in a single `.tex` file. Smaller and editable inline. Recommended if the data structure is small (~10 components × 3-5 materials × 3 countries per panel).
- **Option B — matplotlib** generating a PDF, similar to Fig 3. Use if the diagram benefits from networkx-style layout or programmatic rendering. Less editable but reproducible.

**Steps:**

- [ ] **Step 1: Locate and inspect the source data for each technology**

```bash
ls ~/git/dpi_stdn_agentic/output/normalized/manifests_by_technology/ | grep -iE "ev_traction|5g_base" | head -5
```

Pick the most recent normalization manifest for each technology (sort by timestamp suffix). For each, read the JSON and extract:
- Top ~10 components by confidence
- For each component, the constituent materials (top 3)
- For each material, the top 3 producing countries with HHI / share if available

Example:
```bash
ls -t ~/git/dpi_stdn_agentic/output/normalized/manifests_by_technology/normalization_manifest_ev_traction_inverter_* | head -1
ls -t ~/git/dpi_stdn_agentic/output/normalized/manifests_by_technology/normalization_manifest_5g_base_station_macro_cell_* | head -1
```

Read these files and identify what concentration story they tell. For EV Traction Inverter, the expected angle is rare-earth (NdFeB) magnets in associated motors + gallium/SiC power semis. For 5G Base Station, the angle is gallium (GaN power amps) + tantalum (capacitors) + rare earths (filters/duplexers).

If the actual extracted data doesn't surface these critical materials clearly, pick the most prominent concentration story actually present in the data. Do NOT invent components/materials/countries; use only what's in the manifest.

- [ ] **Step 2: Choose Option A (TikZ) or Option B (matplotlib) based on the data**

If the per-tech data is well-structured and small, use Option A. Create `figures/fig2_vignettes.tex` with a TikZ-based 2-panel figure (mirroring the smartphone STDN style but simpler and smaller, since vignettes are illustrative not exhaustive).

If matplotlib is cleaner, create `figures/fig2_vignettes_make.py` + generated PDF.

- [ ] **Step 3: Compose Fig 2**

Each panel should fit half-column width. Each panel's caption (use `subcaption`) should call out the critical-material concentration insight for that technology. The overall figure caption should summarize: "Layered STDN vignettes for two energy-transition / digital-infrastructure technologies showing critical-material concentration stories at the processing tier."

Use label `\label{fig:vignettes}` (this is the forward-reference target from §2.1 Phase 1).

- [ ] **Step 4: Insert into `sections/results.tex` §2.1**

Find the current `\input{figures/smartphone_stdn.tex}` line in §2.1. Insert `\input{figures/fig2_vignettes.tex}` immediately after it (the order should be: Fig 4 representation → Fig 1 smartphone → Fig 2 vignettes).

- [ ] **Step 5: Build and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C && latexmk -pdf main.tex 2>&1 | tail -10
```

Expected: clean build, both panels render, `fig:vignettes` reference from §2.1 resolves.

- [ ] **Step 6: Commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add figures/fig2_vignettes.tex figures/fig2_vignettes_make.py figures/fig2_vignettes.pdf sections/results.tex 2>/dev/null || git add figures/fig2_vignettes.tex sections/results.tex
git commit -m "feat: add Fig 2 (critical-material vignettes: EV Traction Inverter + 5G Base Station)"
```

---

## Task 5: Update Results §2.1 with vignette prose

**Files:**
- Modify: `sections/results.tex` (§2.1)

The §2.1 prose currently has a placeholder forward-reference to `fig:vignettes`. Replace the placeholder with a substantive paragraph (~150 words) that ties Fig 2 to the smartphone narrative.

**Target content:**

The existing §2.1 second paragraph likely contains the placeholder line `\emph{(Two short critical-material vignettes for EV Traction Inverter and 5G Base Station appear in Figure~\ref{fig:vignettes}; see Phase 2.)}` or similar. Replace this `\emph{}` placeholder with a real paragraph along these lines:

```
Two additional vignettes (Figure~\ref{fig:vignettes}) illustrate that the
same processing-tier concentration pattern appears across other strategic
technology classes. Panel~A shows an EV traction inverter, whose dependency
network exposes [insert actual finding from extracted data — e.g., rare-earth
concentration at the magnet-refining tier; gallium concentration at the
power-semiconductor refining tier]. Panel~B shows a 5G base station, whose
dependency network exposes [insert actual finding — e.g., gallium nitride
power amplifier dependence on Chinese gallium refining; tantalum-capacitor
dependence on DRC mining]. The energy-transition and digital-infrastructure
framings illustrate that processing-tier bottlenecks are not a quirk of
consumer-electronics dependency networks; they are a general feature of
layered STDNs across sectors policymakers actively discuss.
```

Replace the bracketed `[insert actual finding ...]` placeholders with the specific facts from the manifest data extracted in Task 4. Word count target: ~150 words for the new paragraph (existing §2.1 will rise from 482 to ~630 words; total Results section to ~2,450, still within target).

**Steps:**

- [ ] **Step 1: Read §2.1 in `sections/results.tex` to find the placeholder**

- [ ] **Step 2: Replace with the new paragraph, using actual findings from Task 4**

- [ ] **Step 3: Build, word-count §2.1, commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -pdf main.tex 2>&1 | tail -5
git add sections/results.tex
git commit -m "feat: expand Results §2.1 with EV inverter + 5G base station vignette prose"
```

---

## Task 6: Phase 2 final verification

- [ ] **Step 1: Clean rebuild from scratch**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C
latexmk -pdf main.tex 2>&1 | tail -15
```

- [ ] **Step 2: Word count across all main-text sections**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
python3 << 'PYEOF'
import re
def wc(path):
    content = open(path).read()
    for env in ['table', 'figure', 'algorithm']:
        content = re.sub(rf'\\begin\{{{env}\}}.*?\\end\{{{env}\}}', '', content, flags=re.DOTALL)
    content = re.sub(r'\\input\{[^}]+\}', '', content)
    content = re.sub(r'%[^\n]*', '', content)
    content = re.sub(r'\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})*', '', content)
    content = re.sub(r'[\\\{\}\[\]]', '', content)
    return len(content.split())
for s in ['abstract', 'introduction', 'results', 'discussion', 'methods']:
    print(f'{s:>14}: {wc(f"sections/{s}.tex"):>5} words')
PYEOF
```

Expected:
- abstract: ~210 (Phase 4 trim target ~150)
- introduction: ~700
- results: ~2,450 (after §2.1 expansion)
- discussion: ~1,000
- methods: ~1,500

Main-text total (intro + results + discussion) should be ~4,150 words, comfortably under 5,000.

- [ ] **Step 3: Label and reference consistency check**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
echo "=== Undefined references (should be limited to SI placeholders) ==="
grep -i "reference.*undefined\|reference.*on input" main.log | head -10
```

Acceptable undefined references: `si:prompts`, `si:convergence`, `SI-X`, `SI-Y` (all tagged `% TODO: confirm SI labels in Phase 4`).
Unacceptable: any other undefined reference; fix inline.

- [ ] **Step 4: Tag and push**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git tag phase-2-complete -m "Phase 2 v1 complete; ready for Phase 3 co-author review"
git push origin main
git push origin phase-2-complete
```

---

## What's next

Phase 3 (Aug 5 – Aug 31 per spec): circulate v1 to co-authors and revise based on feedback. Phase 4 (Sep 1 – Sep 30): SI assembly, references completion (replace `TODO-iea-cm-2025`, `TODO-eu-crm-act-2023`, `si:prompts`, `si:convergence`, `SI-X`, `SI-Y` placeholders), data/code availability statements, cover letter v1. Phase 5 (Oct 1 – Oct 21): polish, single-file inlining per Springer Nature submission requirement (see memory `project_commssustain_single_file_at_submission`), and submission.

---

## Known follow-ups deferred to later phases

- **Abstract trim** ~210 → ~150 words (Phase 4).
- **Bib entries** for `TODO-iea-cm-2025`, `TODO-eu-crm-act-2023`, any new sustainability/critical-minerals citations introduced in Intro/Discussion (Phase 4).
- **SI labels** `si:prompts`, `si:convergence`, `SI-X`, `SI-Y` to be defined once SI is finalized (Phase 4).
- **Co-author author-list verification** — confirm all 11 names, emails, affiliations remain current (Phase 3).
- **Single-file inlining** for submission per Springer Nature requirement (Phase 5).
- **Vignette refinement** — Phase 4 visual polish on Fig 2 (and Fig 1 smartphone scale=0.6) for final layout.
