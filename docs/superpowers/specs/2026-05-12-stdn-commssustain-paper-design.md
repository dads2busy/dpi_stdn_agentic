# Design Spec — STDN-GEN paper for Communications Sustainability

**Date:** 2026-05-12
**Status:** Approved (brainstorm complete; ready for plan-writing)

## Goal

Adapt the existing STDN-GEN technical report (SIGIR draft) into an Article for the Nature Portfolio cross-journal collection **"Critical materials supply chain sustainability"** (collection ID `eaebjccaab`), submitting to **Communications Sustainability** by the collection deadline of **28 October 2026** (internal target **21 October 2026**).

## Context

- **Source paper:** SIGIR draft at `~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/` — full LaTeX paper on STDN-GEN, including layer-wise ablation across 60 microelectronic technologies, gold-standard validation on 4 technologies, and a smartphone case study.
- **Code repo:** `~/git/dpi_stdn_agentic/` — STDN-GEN pipeline implementation.
- **Collection:** [Critical materials supply chain sustainability](https://www.nature.com/collections/eaebjccaab) — participating journals are Communications Sustainability, Communications Earth & Environment, Nature Communications, Scientific Reports. Cross-journal scope tags: resilient supply chains, *digital transformation*, circularity in materials, governance for energy transition.

## Target journal: Communications Sustainability

Selected because:
- Scope explicitly invites "digital transformation" papers and "demonstrably effective technological advances" for sustainability.
- Comms-tier editorial bar is realistic for a methods-plus-application paper.
- Open access; broad sustainability readership.
- Article format fits a tool-and-evaluation paper better than a Perspective.

## Approach: Tool / Resource Article (Approach A)

Frame STDN-GEN as a digital-transformation tool *for the supply chain sustainability community*. Lead with the capability (rapid synthesis of layered critical-material dependency maps); keep the SIGIR ablation and gold-standard validation as the rigor backbone; broaden the sustainability footprint with two additional critical-material vignettes drawn from existing 60-tech microelectronics outputs.

**Explicit choice:** no new pipeline runs are required. All empirical content comes from existing SIGIR data and existing 60-tech outputs.

## Title and positioning

**Working title:** *STDN-GEN: rapid synthesis of layered critical-material dependency networks for supply-chain sustainability analysis*

**Abstract opening paragraph:**

> Vulnerability and sustainability analyses of critical-material supply chains are bottlenecked by the manual, fragmented work of mapping how a technology decomposes into components, materials, and producing countries. We present STDN-GEN, a multi-agent system that synthesizes auditable *shallow technology dependency networks* — layered DAGs from technology to component to material to country — from unstructured sources, grounded in a canonical vocabulary. Across 60 microelectronic technologies we attribute output quality to its sources. Ontology-backed normalization is the dominant lever, raising run-to-run stability from 0.146 to 0.756. Multi-agent debate is a complementary contributor that operates differently: rather than converging the system on a stable core, debate *broadens* the explored dependency space, roughly doubling pre-normalization stability (0.073 → 0.147) and lowering the invalid rate (0.063 → 0.049 at three agents). Gold-standard validation on four technologies confirms judge precision approaches 1.000. A smartphone case study and short critical-material vignettes demonstrate how layered networks surface processing-layer concentration bottlenecks that component-only analyses miss.

**Framing rules** (applies throughout the paper):
- Title leads with capability and use, not AI method.
- "STDN-GEN" is the named artifact (citable, brandable).
- The methods finding (normalization > debate) appears as the headline empirical lesson, but **both layers are credited as complementary, with debate's qualitative role (broadens exploration) always named alongside normalization's dominance.** Never let debate read as worthless. See `feedback_normalization_vs_debate_framing.md` in project memory.

## Section 0 — Repo setup

Create a new paper repo at `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/` following the naming convention used by sibling paper repos.

**Initial structure:**
```
~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/
├── CLAUDE.md                # cross-references to code + SIGIR repos + journal info
├── main.tex                 # Springer Nature LaTeX template, sn-nature style
├── sections/
│   ├── abstract.tex
│   ├── introduction.tex
│   ├── results.tex
│   ├── discussion.tex
│   ├── methods.tex
│   └── supplementary.tex
├── figures/                 # repurposed + new figures
├── references.bib
└── .git/
```

**Setup steps:**
1. Create directory and git-init.
2. Download the official [Springer Nature LaTeX template](https://www.overleaf.com/latex/templates/springer-nature-latex-template/myxmhdsbzkyd) and configure with the `sn-nature` style flag for Nature Portfolio.
3. Commit the clean template as the first commit.
4. Write `CLAUDE.md` containing: project blurb; pointer to code repo (`~/git/dpi_stdn_agentic/`) for empirical work; pointer to SIGIR repo (`~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/`) as the source draft; target journal info (Comms Sustainability, collection URL, deadline 2026-10-28, internal target 2026-10-21); per-project memory location once established.
5. Migrate SIGIR section contents as starting material for adapt steps.

## Paper section outline

Communications Sustainability uses Nature-style structure: Results lead; Methods at the back.

| § | Section | Target length | Source / Notes |
|---|---|---|---|
| 1 | Introduction | ~700 words | Adapted from SIGIR intro; opens with sustainability bottleneck; Related Work folded in as inline citations |
| 2 | Results | ~2,500 words | Five subsections, each leading with the finding |
| 2.1 | Layered STDNs surface processing-tier concentration | — | Smartphone case + EV inverter + 5G vignettes; capability before methods evidence |
| 2.2 | Ontology-backed normalization is the dominant quality lever | — | Ablation result |
| 2.3 | Multi-agent debate broadens dependency exploration | — | Ablation result; complementary contribution |
| 2.4 | Gold-standard validation confirms judge reliability | — | 4-tech manual study |
| 2.5 | Cost and convergence as a function of debate strength | — | Sweep N ∈ {1..5} |
| 3 | Discussion | ~1,000 words | New section |
| 3.1 | Sustainability implications | — | When to use STDNs; limits |
| 3.2 | Design lesson for automated sustainability-knowledge extraction | ~250 words | Reframes the normalization > debate finding as practitioner guidance for other groups building similar tools |
| 4 | Methods | ~1,500 words target (soft cap ~3,000 per Comms Sustainability guidelines; may exceed if necessary) | Condensed SIGIR Methodology |
| 5 | Data Availability / Code Availability | short | Journal-specific blurbs |
| — | Supplementary Information | unlimited | Extended ablation, prompts, per-tech tables, additional figures |
| — | References | — | SIGIR bib + 15-25 new sustainability/critical-minerals citations |

**Key structural moves from SIGIR:**
- Methods moves to the back.
- Smartphone case study is absorbed into Results §2.1 (no longer a standalone section).
- Related Work folded into Introduction.
- Discussion is a new section; SIGIR conflated it into Conclusion.

## Figure and table plan

### Main text (6 display items)

| # | Display item | Source | Status |
|---|---|---|---|
| Fig 1 | Smartphone STDN (lead) | SIGIR `case_study.tex` figure | Reuse with minor relabel |
| Fig 2 | Two critical-material vignettes (multi-panel A/B) | Repurposed from existing 60-tech outputs: **EV Traction Inverter** (rare earths + gallium/SiC) and **5G Base Station** (gallium + tantalum + rare earths) | New figure construction; no new pipeline runs |
| Fig 3 | Layer-wise ablation: stability and validity (multi-panel) | Combination of SIGIR ablation table + invalid-rate plots | New figure construction |
| Fig 4 | STDN representation + STDN-GEN overview (compact combined) | SIGIR `stdn_layer_schematic.png` + simplified pipeline | New combined figure |
| Tab 1 | Layer ablation (numerical) | SIGIR `validity_robustness_cost.tex` ln 149-152 | Reuse with light formatting |
| Tab 2 | Gold-standard validation summary | SIGIR manual study | Reuse |

### Supplementary Information

- Detailed STDN-GEN architecture diagram (3-layer)
- Multi-agent debate flow diagram
- `paired_invalid_rate_dedup_N1_vs_N3.png` (per-tech paired N=1 vs N=3)
- `stability_heatmap_by_tech_and_n.png` (stability heatmap)
- `validity_vs_n_dedup_invalid_and_k.png` (validity vs N detail)
- `tradeoff_runtime_vs_stability.png`
- `convergence_rounds_vs_n.png`
- `invalid_rate_occ_vs_dedup.png` (two counting schemes)
- Full 60-technology table
- Naive baseline vs pipeline table
- Extraction agent roles table
- Full STDN-GEN prompts

## Work scope

### Reuse (low cost; ~2 days)
- Smartphone STDN figure (cosmetic edits)
- Layer ablation table (numerical, light formatting)
- Gold-standard validation table
- SIGIR Methodology section (will be condensed, but content is reusable)
- All SI figures and tables
- 60-tech list
- `references.bib` (extend, don't replace)

### Adapt (moderate cost; ~13 days)
- Abstract — ~1 day
- Introduction — ~2-3 days
- Results section (5 subsections) — ~4-5 days
- Layer-wise ablation figure (Fig 3) — ~1 day
- STDN representation + pipeline overview figure (Fig 4) — ~1 day
- Methods section (condensed) — ~2 days
- Discussion section — ~2 days

### Add (highest cost; ~10 days)
- Two critical-material vignettes (EV Inverter + 5G Base Station) including text and Fig 2 panels — ~5 days
- Discussion §3.2 "Design lesson" subsection — ~1 day
- References additions (15-25 new citations) — ~2-3 days
- Data Availability / Code Availability statements — ~0.5 day
- Cover letter — ~1 day

### Out of scope for this submission
- No new pipeline runs.
- No new gold-standard annotation.
- No expansion of the 60-tech benchmark.
- No standalone Related Work section (folded into Introduction).
- No expansion to energy-transition tech list (Approach B option, deferred).

**Total drafting:** ~25 working days of focused writing.
**With buffer (revisions, co-author rounds, figure polish):** ~35 working days (~7 weeks).
**Available:** ~24 weeks. Comfortable margin if work starts in May/June.

## Timeline

Today: **2026-05-12**. Deadline: **2026-10-28**. Internal target: **2026-10-21**.

| Phase | Window | Duration | Milestone |
|---|---|---|---|
| 0 — Setup | May 12 – May 26 | ~2 weeks | Paper repo created; `CLAUDE.md` + Springer Nature template committed; SIGIR sections migrated; new abstract + intro outline drafted; figure plan locked |
| 1 — Results draft | May 27 – Jun 30 | ~5 weeks | Results section drafted (all 5 subsections); Fig 3 and Fig 4 regenerated; smartphone Fig 1 reformatted; Tables 1 and 2 finalized |
| 2 — Vignettes + Methods + Discussion | Jul 1 – Aug 4 | ~5 weeks | EV Inverter + 5G Base Station vignettes drafted (Fig 2); Methods condensed; Discussion drafted including §3.2 |
| 3 — Internal v1 + co-author review | Aug 5 – Aug 31 | ~4 weeks | v1 complete with all sections, main figures, tables, substantially populated references; circulate to co-authors; collect feedback |
| 4 — Revision + SI + references | Sep 1 – Sep 30 | ~4 weeks | Revisions to address co-author feedback; SI assembled; references completed; data/code availability statements; cover letter v1 |
| 5 — Polish + submission buffer | Oct 1 – Oct 28 | ~4 weeks | Final read-through; figure polish; cover letter finalized; submission by **Oct 21** |

**Critical checkpoints:**
- **End of June:** Results draft + all main figures regenerated. Slip >2 weeks puts Oct 21 internal target at risk.
- **End of August:** v1 to co-authors. Hard checkpoint — slip past Aug 31 makes Oct 28 deadline tight.

**Risks:**
- Co-author availability in August (vacation month). Flag early.
- Critical-mineral vignettes may need iteration if 60-tech outputs are weak for EV Inverter or 5G Base Station; fallback technologies identified: MRI Machine, Large-Format OLED Television, LiDAR Sensor System.

## Cross-references

- **Source draft:** `~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR/main.tex` and `sections/`
- **Code:** `~/git/dpi_stdn_agentic/`
- **60-tech list:** `~/git/dpi_stdn_agentic/data/tech_list_microelectronic_products.csv`
- **Existing outputs to repurpose for vignettes:** STDN outputs in `~/git/dpi_stdn_agentic/output/normalized/` for the 60-tech runs
- **Project memory (code side):** `~/.claude/projects/-Users-ads7fg-git-dpi-stdn-agentic/memory/MEMORY.md`
- **Project memory (SIGIR paper):** `~/.claude/projects/-Users-ads7fg-git-D-PI-2026-01-STDN-AGENTIC-SIGIR/memory/MEMORY.md`
- **Project memory (this paper, to be created):** `~/.claude/projects/-Users-ads7fg-git-D-PI-2026-05-STDN-COMMS-SUSTAIN/memory/` (will be created during Phase 0)

## Approval state

- Title and positioning: approved
- Paper section outline: approved
- Figure and table plan: approved
- Critical-material vignettes (EV Traction Inverter + 5G Base Station): approved
- Work scope: approved
- Timeline: approved
- LaTeX template choice (Springer Nature `sn-nature`): approved
- Repo structure and `CLAUDE.md` cross-reference pattern: approved
