# Multi-Agent Debate Evidence Report (Updated: Validity / Robustness / Cost)

This document consolidates:
- the **paper-aligned evaluation summary** from `D-PI-2026-01-STDN_AGENTIC_SIGIR/sections/validity_robustness_cost.tex`, and
- the former internal “agent count plan/recommendation” notes (merged here to avoid duplication).

Scope: **Stage 1 (component extraction)** debate strength, because component extraction drives downstream materials and producing-country dependencies.

---

## Executive Summary (Headline Finding)

Across **26 technologies** (see paper Appendix A for the technology list), increasing **component-stage debate strength** reduces an **LLM-judge invalid rate** (a precision proxy) relative to a no-debate baseline, **without evidence that improvements are driven solely by shorter component lists**. We also quantify:

- **Robustness** via **run-to-run stability** (set overlap)
- **Cost** via **runtime** and **convergence** behavior

A practical “sweet spot” emerges around **N = 3** debating agents for the component stage.

---

## Configurations (What “N” Means)

We compare a no-debate baseline to multi-agent debate configurations, tagged like:

- `v1v1v1` (no debate at component stage; single component agent)
- `d2v1v1`, `d3v1v1`, `d4v1v1`, `d5v1v1` (N-agent debate for **component extraction**, downstream stages held fixed here)

In these tags, the **first token** is the component-extraction stage:
- `v1` = single agent (no debate)
- `dN` = N-agent debate

---

## Aggregation + Uncertainty (How We Summarize)

Unless stated otherwise:

- Results are **aggregated across repeated runs per configuration**
- Then **macro-aggregated across technologies** (equal weight per technology)
- We report **macro-median** and **macro-mean** across technologies
- Uncertainty is computed using **nonparametric bootstrap 95% CIs** by resampling technologies with replacement
- For comparisons vs baseline `N=1`, we report **paired bootstrap CIs** for differences
- We also report a **sign-test style** summary: the % of technologies that improve vs baseline

---

## Validity: LLM-Judge Precision Proxy and “Hallucination-like Errors”

### Operational definition (paper-aligned)

Direct correctness measurement at scale is difficult because ground-truth component lists are unavailable for most technologies. We therefore use an **independent LLM judge** to label whether each extracted final component is a plausible **primary manufacturing component** for the target technology.

> **Hallucination-like errors** = **components judged not plausible by an independent LLM judge**.

From these binary labels we compute:

- `InvalidRate` = fraction judged **not plausible**
- `PrecisionProxy = 1 - InvalidRate`

### Occurrence-based vs deduped-canonical invalid rate

Because the pipeline is run multiple times per configuration, the same concept may reappear across runs. We report two complementary invalid-rate estimates:

1. **Occurrence-based invalid rate**  
   Counts every judged output instance (repeats count multiple times).  
   Interpretable as: how often the pipeline emits invalid items during repeated use.

2. **Deduped-canonical invalid rate**  
   Deduplicates within each `(technology, configuration)` by canonical component name before computing invalid rate.  
   Interpretable as: how “clean” the unique component vocabulary is.

### Concrete validity results (key numbers)

Across technologies (macro-median):

- **Occurrence-based invalid rate**
  - **N=1:** 0.065  
  - **N=3:** 0.046  
  - (equivalently, precision proxy increases from **0.935 → 0.954**)

- **Deduped-canonical invalid rate**
  - **N=1:** 0.091  
  - **N=3:** 0.035  
  - (equivalently, deduped-canonical precision proxy increases from **0.909 → 0.965**)

**Difference vs baseline (paired bootstrap):**
- For deduped-canonical *median* invalid-rate difference at **N=3 vs N=1**, the 95% CI is:  
  `[-0.092, -0.008]`  
  (negative indicates improvement; CI excluding 0 indicates robust reduction for the “typical” technology)

**Directional consistency (sign-test style):**
- For deduped-canonical invalid rate, **58.3%** of technologies improve at **N=3 vs N=1**.

---

## Not Simply Shorter Lists: Component Count Control

A potential confound is that a configuration could look “more precise” simply by producing fewer components.

We therefore track the number of **unique canonical components produced** per technology/configuration (computed per run and summarized per technology).

**Concrete control result:**
- Macro-median produced component count is **7.00** at **N=1** and **7.00** at **N=3**

So the validity improvements above are **not explained solely by shorter component lists**.

---

## Robustness: Run-to-Run Stability of Final Component Sets

Analysts also need **repeatable** outputs under reruns.

We quantify robustness by measuring run-to-run stability of Stage 1 final component sets within each `(technology, configuration)`:

- Compute **pairwise set similarity** (Jaccard similarity) between runs
- Summarize per technology and configuration
- Macro-aggregate across technologies

### Concrete robustness results (key numbers)

Across technologies (macro-median):

- **Stability (Jaccard)**
  - **N=1:** 0.100  
  - **N=3:** 0.145

Stability gains are **heterogeneous** across technologies; the paper includes a per-technology heatmap in the appendix to visualize this.

Interpretation: Increasing debate strength can improve reproducibility, but gains may plateau and should be weighed against additional cost.

---

## Cost: Runtime and Convergence Tradeoffs

Multi-agent debate increases computational cost. We characterize cost using:

1. **End-to-end runtime** per configuration (wall-clock, from run logs)
2. **Convergence behavior** (e.g., convergence score trajectories and rounds completed)

### Concrete cost + convergence results (key numbers)

**Runtime (median):**
- **N=1:** 10.6 minutes  
- **N=3:** 31.9 minutes  
- **N=5:** 49.3 minutes

**Convergence (macro-median final convergence):**
- **N=1:** 0.896  
- **N=3:** 0.926

**Rounds completed (macro-median):**
- **N=1:** 1.00  
- **N=3:** 2.20

Interpretation: runtime grows strongly with N; convergence improves, but with additional rounds and cost.

---

## Agent Count Recommendation (Merged Here)

### Default recommendation (Stage 1 / components)
Use **`d3v1v1` (N = 3)** as the default component-stage debate strength.

**Why:**
- Validity improves meaningfully by N=3 (both occurrence-based and deduped-canonical invalid rates drop).
- Improvements are not explained by “shorter lists” (macro-median unique canonical components stays **7.00** at N=1 and N=3).
- Robustness improves (Jaccard **0.100 → 0.145** macro-median).
- N=3 avoids the much higher runtimes seen at stronger debate (e.g., N=5).

### When to use N=1 instead
Choose `v1v1v1` (N=1 at component stage) when:
- you need fast turnaround / exploratory runs
- cost/latency constraints dominate and you can tolerate higher judged invalid rates and lower stability

### When to consider N>3
Consider `d4v1v1` / `d5v1v1` only if:
- you have a high-stakes technology where additional gains justify runtime increases, and
- you have empirical evidence for your subset that gains beyond N=3 are worth it (diminishing returns are plausible)

---

## Relationship to Manual Study

The paper’s manual study (see `Section~\ref{sec:manual_study}` in the paper) complements these large-scale metrics by providing gold-standard recall estimates on five technologies. This helps validate that improvements in judged validity and robustness do not come at the expense of missing key components.

---

## Notes on Scope (What This Report Covers)

This report is intentionally aligned to the paper’s **large-scale component-stage evaluation** and its operationalization of hallucination reduction as **LLM-judge “not plausible”** labels.

Older evidence items (e.g., “isolated proposals”, support distributions, and full-pipeline `d3d3v3` comparisons) are not the focus here and have been superseded by the validity/robustness/cost analysis summarized above.