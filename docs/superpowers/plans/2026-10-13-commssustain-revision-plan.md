# Communications Sustainability Revision Plan (Round 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a revised manuscript, point-by-point response, marked-up PDF, and clean PDF that fully address all three reviewers and the editors' two stated bars, resubmitted by **2026-12-19** (internal) ahead of the **~2027-01-05** twelve-week window.

**Architecture:** Three phases, critical path first. Phase 0 (week 1) launches every new pipeline run and the materials-ontology work, because those are the only items with multi-day latency. Phase 1 (weeks 2–5) runs post-hoc analyses on existing transcripts and country shares, which need no new runs. Phase 2 (weeks 4–9) rewrites the manuscript against the new evidence. Phase 3 (weeks 10–11) packages the response letter, latexdiff markup, and clean PDF.

**Tech Stack:** Python 3 via `uv` in `~/git/dpi_stdn_agentic` (pipeline, analyses); LaTeX (`latexmk`, `latexdiff`) in `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN` (paper). Pipeline model stays `openai:gpt-4.1-mini` for extraction and `openai:gpt-4.1` for normalization and judging, so new runs are comparable with the submitted benchmark.

**Spec:** The reviewer decision email (2026-10-13) and the assessment in paper-repo memory `project_revision_round1.md`. Original design spec: `docs/superpowers/specs/2026-05-12-stdn-commssustain-paper-design.md`.

## Global Constraints

- Editors' bar (a): "clearer relevance and utility for the critical-materials research community, including how the framework generates actionable insights and interfaces with established assessment approaches."
- Editors' bar (b): "stronger evidence of methodological robustness and validation, including justification of key design choices, assessment of underlying assumptions, and evaluation of sensitivity to methodological decisions."
- Framing rule (CLAUDE.md): credit ontology-backed normalization and multi-agent debate as complementary; normalization is the dominant stability lever; debate must not read as worthless.
- Main text soft cap ~5,000 words (Methods, captions, references excluded); currently ~5,705. New Results content must be offset by cuts or moved to Supplementary.
- At most 10 display items in main text.
- Every new pipeline run uses the same model configuration as the submitted benchmark (`component_model`, `materials_model`, `country_model` = `openai:gpt-4.1-mini`; `component_normalization_model` = `openai:gpt-4.1`).
- The convergence threshold actually used in all submitted benchmark runs is **τ = 0.7**, round cap **R = 3** (verified from `.env` and every transcript). The manuscript's "τ = 0.95" is an error and must be corrected and disclosed.
- Paper build: `main.tex` `\input`s `sections/*.tex` (Overleaf pulls it from GitHub as-is). Edit sections directly. Only at resubmission run `python3 scripts/inline_sections.py` to write the gitignored single-file `main_flat.tex` for upload (changed 2026-10-26).
- Resubmission package: point-by-point response, marked-up PDF (changes in a different colour), clean PDF, and the editors' formatting/policy table with the right-hand column filled in.

## Review Focus

Failure modes a reader of the revised paper is most likely to hit, each pinned to the task that tests it:

1. **The τ correction is read as "the sensitivity analysis was run at the wrong setting."** Task 0.1 writes the disclosure so the correction and the new sensitivity sweep are presented together, and Task 1.1 reports both the reconstructed (post hoc) and the rerun (τ = 0.85, 0.95) results side by side.
2. **Country-name mismatch silently drops shares before WGI/HDI weighting.** USGS rows are upper-case ("CHINA", "KOREA, REPUBLIC OF", "CONGO", "BURMA"); LLM-inferred rows are title-case. Task 1.3 includes a name-normalization table and asserts that every share row maps to an ISO3 code or to the documented `OTHER` bucket.
3. **Materials resolution inflates CRM coverage by fiat.** Expanding "ceramic" to Al/Ba/Ti/Zr could look like coverage was manufactured. Task 0.3 tags every resolved row with `resolution_provenance` and reports coverage with and without resolved rows.
4. **The N = 5 cross-domain runs contradict the submitted N = 3 story.** Task 0.2 is launched first so results are known before Task 2.3 rewrites the Results; the framing rule governs how a reversal is written up.
5. **The marked-up PDF misses changes in `\input` files.** Task 3.2 runs `latexdiff --flatten` against the tagged submitted commit and visually checks that Results and Methods diffs appear.

---

## Phase 0 — Critical path (start week 1, in this order)

### Task 0.1: Correct τ in Methods and tag the submitted version

**Files:**
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/methods.tex` (convergence subsection, the paragraph beginning "In all experiments we use")
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/supplementary.tex` (S.4 if it repeats 0.95)

**Interfaces:**
- Produces: git tag `submitted-v1` on the paper repo that Task 3.2 diffs against.

- [x] **Step 1: Tag the submitted commit before any edit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git tag -a submitted-v1 dc4ad2a -m "Version submitted to Communications Sustainability"
git tag
```
Expected: `submitted-v1` listed.

- [x] **Step 2: Confirm every stated 0.95 location**

```bash
grep -n "0\.95\|tau" sections/*.tex | grep -v "confidence"
```
Expected: hits in `methods.tex` (convergence paragraph) and possibly `supplementary.tex` S.4. Note each.

- [x] **Step 3: Replace the convergence paragraph**

Replace from "In all experiments we use $\tau = 0.95$ and $R = 3$." through "Sensitivity to these choices is an open question for future ablation." with:

```latex
In all benchmark experiments we use $\tau = 0.7$ and $R = 3$. Because
candidate sets are compared after canonical normalization, a 0.7 overlap
already corresponds to near-identical canonical lists; the round cap bound
in only 1 of 1{,}018 three-agent runs. The submitted version of this
manuscript misreported $\tau$ as 0.95; the value used in every run is
0.7, as recorded in each debate transcript. Section~\ref{sec:sensitivity}
reports sensitivity to both $\tau$ and $R$.
```
(`sec:sensitivity` is created in Task 2.3.)

- [x] **Step 4: Build and commit**

```bash
latexmk -pdf main.tex >/dev/null 2>&1; grep -c "Undefined" main.log
git add sections/methods.tex sections/supplementary.tex
git commit -m "fix: correct convergence threshold to tau=0.7 as used in all runs"
```
Expected: one undefined reference (`sec:sensitivity`) until Task 2.3; no other errors.

### Task 0.2: Launch all new pipeline runs

**Files:**
- Create: `~/git/dpi_stdn_agentic/config_biotech_d5v1v1.json`, `config_pharma_d5v1v1.json` (copies of the `_d3v1v1` files)
- Create: `~/git/dpi_stdn_agentic/data/tech_list_micro_tau_subset.csv` (20 technologies)
- Create: `~/git/dpi_stdn_agentic/config_micro_tau_subset.json`
- Create: `~/git/dpi_stdn_agentic/scripts/run_revision_batch.sh`

**Interfaces:**
- Produces raw CSVs under `output/raw/` named `stdns_output_{biotech,pharma}_d5v1v1_*.csv`, `stdns_output_tau085_d3v1v1_*.csv`, `stdns_output_tau095_d3v1v1_*.csv`, `stdns_output_r5_d3v1v1_*.csv`; transcripts under `output/transcripts/`. Consumed by Tasks 1.1, 1.2, 2.3.

Wall-clock reference: the 2026-04-14 microelectronics rerun completed each five-run config batch across 60 technologies in about one hour. The full batch below is roughly 7 batches, so under one working day of machine time. API cost is well under $20 at the measured $0.004 per technology.

- [x] **Step 1: Build the 20-technology τ subset, stratified by sub-domain**

```bash
cd ~/git/dpi_stdn_agentic
uv run python - <<'EOF'
import csv, random
rows = list(csv.DictReader(open("data/tech_list_microelectronic_products.csv")))
random.seed(20261013)
by_dom = {}
for r in rows: by_dom.setdefault(r["domain"], []).append(r)
pick = []
for dom, rs in sorted(by_dom.items()):
    pick += random.sample(rs, 2)          # 12 sub-domains x 2 = 24; trim to 20 below
pick = sorted(pick, key=lambda r: r["tech"])[:20]
with open("data/tech_list_micro_tau_subset.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(pick)
print(len(pick), "technologies written")
EOF
```
Expected: `20 technologies written`. Record the seed in the Methods text (Task 2.3).

- [x] **Step 2: Create the config files**

```bash
cd ~/git/dpi_stdn_agentic
cp config_biotech_d3v1v1.json config_biotech_d5v1v1.json
cp config_pharma_d3v1v1.json  config_pharma_d5v1v1.json
cp config_micro_d3v1v1.json   config_micro_tau_subset.json
sed -i '' 's#tech_list_microelectronic_products.csv#tech_list_micro_tau_subset.csv#' config_micro_tau_subset.json
grep -n "tech_list\|num_agents" config_biotech_d5v1v1.json config_micro_tau_subset.json
```
Expected: the subset config points to the new CSV. Agent counts are set by `--config-type` in the launcher, not by the JSON, so the d5 copies need no further edit.

- [x] **Step 3: Write the batch script**

```bash
cat > scripts/run_revision_batch.sh <<'EOF'
#!/usr/bin/env bash
# Revision round-1 runs. Usage:
#   nohup bash scripts/run_revision_batch.sh > logs/revision_batch.log 2>&1 &
set -e; export PYTHONUNBUFFERED=1
cd "$(dirname "$0")/.."; mkdir -p logs
log(){ echo "[$(date '+%F %T')] $*"; }
run(){ # tag config_type base_config [env assignments...]
  local tag=$1 ct=$2 cfg=$3; shift 3
  log "START $tag ($ct, $cfg) $*"
  env "$@" uv run python scripts/parallel_runs.py --config-type "$ct" --num-runs 5 --base-config "$cfg"
  log "DONE  $tag: $(ls output/raw/stdns_output_${ct}_*.csv | wc -l) raw files total for $ct"
}
# A. Cross-domain N=5 (Reviewer 1.2)
run biotech_d5 d5v1v1 config_biotech_d5v1v1.json
run pharma_d5  d5v1v1 config_pharma_d5v1v1.json
# B. tau / R sensitivity on 20-tech micro subset (Reviewer 1.5)
run tau085 d3v1v1 config_micro_tau_subset.json CONVERGENCE_THRESHOLD=0.85
run tau095 d3v1v1 config_micro_tau_subset.json CONVERGENCE_THRESHOLD=0.95
run r5     d3v1v1 config_micro_tau_subset.json MAX_DEBATE_ROUNDS=5
log "ALL DONE"
EOF
chmod +x scripts/run_revision_batch.sh
```

Note: `load_dotenv()` in `src/stdn_agentic/__init__.py` does not override variables already in the environment, so the `env` assignments win over `.env`. The `d6d6v6` max-cost run used the same mechanism.

- [x] **Step 4: Verify env override on a one-technology smoke test before the full batch**

```bash
cd ~/git/dpi_stdn_agentic
CONVERGENCE_THRESHOLD=0.95 uv run stdn -i config_test_smartphone.json --save-transcripts
f=$(ls -t output/transcripts/Smartphone_*.json | head -1)
uv run python -c "import json,sys; d=json.load(open('$f')); print(d['component_stage']['phase2_debate_rounds'][0]['threshold'])"
```
Expected: `0.95`. If it prints `0.7`, stop and fix the override before launching.

- [x] **Step 5: Launch and record**

```bash
nohup bash scripts/run_revision_batch.sh > logs/revision_batch.log 2>&1 &
echo $! > logs/revision_batch.pid
```
Raw files for the τ and R batches share the `d3v1v1` config-type name. Immediately after each batch finishes, rename them so later analyses can tell them apart:

```bash
# run once after the tau085 batch's DONE line appears; adjust the timestamp glob to that batch
for f in output/raw/stdns_output_d3v1v1_<ts>*.csv; do mv "$f" "${f/d3v1v1/tau085_d3v1v1}"; done
```
Repeat for `tau095` and `r5`. Transcripts carry `threshold` and round count internally and need no rename.

- [x] **Step 6: Normalize the new raw outputs with the frozen vocabulary**

Use the same script and arguments as the April rerun (`scripts/run_micro_rerun.sh` lines 50–56), adding `--freeze-vocab` so the vocabulary is not grown by the new runs:

```bash
cd ~/git/dpi_stdn_agentic
for pat in biotech_d5v1v1 pharma_d5v1v1 "tau085_d3v1v1" "tau095_d3v1v1" "r5_d3v1v1"; do
  uv run python scripts/normalize_outputs_global_granularity.py \
    --pattern "output/raw/stdns_output_${pat}_*.csv" \
    --group-by technology \
    --output-dir output/normalized \
    --global-vocab data/component_canonical_vocab_global_primary.json \
    --model openai:gpt-4.1 \
    --chunk-size 120 \
    --freeze-vocab
done
ls output/normalized | grep -c -E "biotech_d5|pharma_d5|tau0|r5_"
```
Expected: 25 normalized files. `--freeze-vocab` keeps the comparison on the same vocabulary as the submitted analysis (the Supplementary vocab-maturity argument); unseen names still get mapped, but the mapping is not persisted.

- [x] **Step 7: Commit configs, script, and tech subset**

```bash
git add config_biotech_d5v1v1.json config_pharma_d5v1v1.json config_micro_tau_subset.json data/tech_list_micro_tau_subset.csv scripts/run_revision_batch.sh
git commit -m "feat(revision): configs and batch script for N=5 cross-domain and tau/R sensitivity runs"
```

**As run (done 2026-10-27):** 7 batches incl. `gold_d5`, 35 normalized files. Tech subset is `data/tech_list_tau_subset.csv` (20 micro + 4 gold-standard). Deviations to protect submitted data: `--defer-shared-postprocess`; new files renamed `_<tag>_<config_type>_`; normalized against a copy (`data/component_canonical_vocab_global_primary_revision.json`) without `--freeze-vocab` (the flag passes unknown names through raw). Replicates shared one `parallel_checkpoint.json`, so biotech run 5 and pharma runs 4–5 skipped techs; fixed with per-run checkpoints, the three replicates rerun, the short ones quarantined in `output/aborted/checkpoint_race_20261027/`.

### Task 0.3: Materials resolution to elemental/compound forms (Reviewer 2 main concern)

**Files:**
- Create: `~/git/dpi_stdn_agentic/data/material_resolution_map.csv`
- Create: `~/git/dpi_stdn_agentic/scripts/resolve_materials.py`
- Create: `~/git/dpi_stdn_agentic/src/stdn_agentic/tests/unit/test_resolve_materials.py`
- Create: `~/git/dpi_stdn_agentic/output/analysis/material_resolution_report.md`

**Interfaces:**
- Consumes: normalized CSVs in `output/normalized/` (columns `technology, component, material, country, percentage, ...`); `data/hs_codes_and_usgs_names.csv` (388 entries, column `Elements_Compounds`).
- Produces: `output/resolved/<same filename>.csv` with added columns `material_resolved`, `material_level` ∈ {`element`,`compound`,`generic`,`not_material`}, `resolution_provenance` ∈ {`identity`,`map`}. Function `resolve_rows(rows: list[dict], mapping: dict[str, list[tuple[str,str]]]) -> list[dict]`. Consumed by Tasks 1.3, 2.3, 2.5.

Design decision: a post-pass, not a Stage 2 rerun. Stage 2 hard-filters materials against the ontology (`_filter_materials_not_in_ontology`), so the ontology is the lever; the post-pass applies the tightened ontology to every existing output without re-spending the benchmark. A small end-to-end rerun on the three vignette technologies (Step 8) shows the same tightening working inside the pipeline.

- [x] **Step 1: Author the resolution map**

One row per ontology entry. Columns: `source,level,resolved,resolved_level,note`. `level` classifies the source entry; `resolved` lists constituents separated by `|`. Examples that must be present:

```csv
source,level,resolved,resolved_level,note
Copper,element,Copper,element,identity
Gallium arsenide,compound,Gallium arsenide,compound,identity
Ceramic,generic,Aluminum oxide|Barium titanate|Zirconium oxide,compound,dominant electronic ceramics
Glass,generic,Silicon dioxide|Boron,compound|element,soda-lime and borosilicate
Epoxy resins,generic,Epoxy resins,generic,petrochemical; no CRM exposure; kept generic
Steel ingots,generic,Iron|Chromium|Nickel|Manganese,element,alloying elements
Stainless steel (SS 304/316),generic,Iron|Chromium|Nickel|Molybdenum,element,
Solder paste,generic,Tin|Silver|Copper,element,SAC305
Strain gauge,not_material,,,component mislabelled as material
Peltier elements,not_material,Bismuth telluride,compound,component; resolved to active material
```
Every one of the 388 entries must appear (Step 3 tests this). Compounds additionally resolve to elements in a second column `elements` (e.g. `Barium titanate` → `Barium|Titanium`), so analyses can be run at compound or element level.

- [x] **Step 2: Write the failing test**

```python
# src/stdn_agentic/tests/unit/test_resolve_materials.py
import csv
from pathlib import Path
from scripts.resolve_materials import load_map, resolve_rows

def test_map_covers_entire_ontology():
    onto = {r["Elements_Compounds"] for r in csv.DictReader(open("data/hs_codes_and_usgs_names.csv"))}
    mapping = load_map("data/material_resolution_map.csv")
    assert onto - set(mapping) == set()

def test_generic_row_expands_and_keeps_provenance():
    mapping = load_map("data/material_resolution_map.csv")
    rows = [{"technology": "5G", "component": "Antenna", "material": "ceramic", "country": "CHINA", "percentage": "60"}]
    out = resolve_rows(rows, mapping)
    assert {r["material_resolved"] for r in out} == {"Aluminum oxide", "Barium titanate", "Zirconium oxide"}
    assert all(r["resolution_provenance"] == "map" for r in out)
    assert all(r["country"] == "" for r in out)   # country shares do NOT carry over; refetched in Step 5

def test_identity_row_untouched():
    mapping = load_map("data/material_resolution_map.csv")
    rows = [{"technology": "x", "component": "c", "material": "copper", "country": "CHILE", "percentage": "24"}]
    out = resolve_rows(rows, mapping)
    assert len(out) == 1 and out[0]["resolution_provenance"] == "identity" and out[0]["country"] == "CHILE"
```

- [x] **Step 3: Run it to verify it fails**

```bash
cd ~/git/dpi_stdn_agentic && uv run pytest src/stdn_agentic/tests/unit/test_resolve_materials.py -v
```
Expected: FAIL with `ModuleNotFoundError: scripts.resolve_materials`.

- [x] **Step 4: Implement `scripts/resolve_materials.py`**

```python
#!/usr/bin/env python3
"""Expand generic material labels to elemental/compound constituents (post-pass).
Usage: uv run python scripts/resolve_materials.py --pattern "output/normalized/stdns_output_*.csv" --out output/resolved
"""
import argparse, csv, glob, os
from collections import defaultdict

def load_map(path):
    m = {}
    for r in csv.DictReader(open(path)):
        if r["level"] == "not_material" and not r["resolved"]:
            m[r["source"]] = []
        else:
            res = r["resolved"].split("|"); lv = r["resolved_level"].split("|")
            if len(lv) == 1: lv = lv * len(res)
            m[r["source"]] = list(zip(res, lv))
    return m

def _key(s): return s.strip().lower()

def resolve_rows(rows, mapping):
    lower = {_key(k): v for k, v in mapping.items()}
    out = []
    for r in rows:
        tgt = lower.get(_key(r["material"]))
        if tgt is None or (len(tgt) == 1 and _key(tgt[0][0]) == _key(r["material"])):
            lvl = tgt[0][1] if tgt else "unmapped"
            out.append({**r, "material_resolved": r["material"], "material_level": lvl, "resolution_provenance": "identity"})
            continue
        for name, lvl in tgt:
            out.append({**r, "material_resolved": name, "material_level": lvl, "resolution_provenance": "map",
                        "country": "", "percentage": "", "country_confidence": "", "country_reasoning": ""})
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--pattern", required=True); ap.add_argument("--out", default="output/resolved")
    ap.add_argument("--map", default="data/material_resolution_map.csv"); a = ap.parse_args()
    mapping = load_map(a.map); os.makedirs(a.out, exist_ok=True)
    for f in sorted(glob.glob(a.pattern)):
        rows = list(csv.DictReader(open(f))); out = resolve_rows(rows, mapping)
        fields = list(rows[0].keys()) + ["material_resolved", "material_level", "resolution_provenance"]
        with open(os.path.join(a.out, os.path.basename(f)), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(out)
        print(f, len(rows), "->", len(out))

if __name__ == "__main__": main()
```

- [x] **Step 5: Re-fetch USGS country shares for mapped rows**

Mapped rows have blank `country`. Fill them by calling the existing repository the pipeline uses:

```bash
cd ~/git/dpi_stdn_agentic
uv run python - <<'EOF'
import csv, glob, asyncio
from stdn_agentic.data.repository import *   # use the same class the pipeline uses; see country_data_enricher.py:65 for the call pattern
EOF
```
Follow `src/stdn_agentic/orchestrator/country_data_enricher.py` lines 65–235 for the exact call (USGS-first, LLM fallback cache second). Write the result as `output/resolved/<file>.csv` in place. Materials with no USGS coverage after resolution are left with `country=""` and counted in the report.

- [x] **Step 6: Run tests; run the pass on all normalized outputs**

```bash
uv run pytest src/stdn_agentic/tests/unit/test_resolve_materials.py -v
uv run python scripts/resolve_materials.py --pattern "output/normalized/stdns_output_*.csv"
```
Expected: 3 tests PASS; one resolved CSV per normalized CSV.

- [x] **Step 7: Write the resolution report**

```bash
uv run python - <<'EOF' > output/analysis/material_resolution_report.md
import csv, glob
from collections import Counter
before, after = Counter(), Counter()
for f in glob.glob("output/resolved/stdns_output_d5v1v1_*.csv"):
    for r in csv.DictReader(open(f)):
        after[r["material_level"]] += 1
        before["generic" if r["resolution_provenance"]=="map" else r["material_level"]] += 1
tot = sum(after.values())
print("# Material resolution report (micro d5v1v1, 5 runs)\n")
print("| level | before | after |"); print("|---|---|---|")
for k in ["element","compound","generic","not_material","unmapped"]:
    print(f"| {k} | {before[k]} | {after[k]} ({after[k]/tot:.1%}) |")
EOF
cat output/analysis/material_resolution_report.md
```
Expected: `element + compound` share rises substantially; `not_material` rows are now flagged rather than silently counted.

- [x] **Step 8: End-to-end check on the three vignette technologies with a tightened ontology**

Create `data/hs_codes_and_usgs_names_strict.csv` by dropping every `generic` and `not_material` source row from the ontology, then rerun the vignette config against it:

```bash
uv run python - <<'EOF'
import csv
keep = {r["source"] for r in csv.DictReader(open("data/material_resolution_map.csv")) if r["level"] in ("element","compound")}
rows = [r for r in csv.DictReader(open("data/hs_codes_and_usgs_names.csv")) if r["Elements_Compounds"] in keep]
with open("data/hs_codes_and_usgs_names_strict.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
print(len(rows))
EOF
cp config_vignettes_v1.1.json config_vignettes_strict.json
sed -i '' 's#hs_codes_and_usgs_names.csv#hs_codes_and_usgs_names_strict.csv#' config_vignettes_strict.json
uv run python scripts/parallel_runs.py --config-type d5v1v1 --num-runs 3 --base-config config_vignettes_strict.json
```
Expected: the 5G antenna row no longer reads "ceramic"; record what it reads instead for Fig. 3b (Task 2.5).

- [x] **Step 9: Commit**

```bash
git add data/material_resolution_map.csv data/hs_codes_and_usgs_names_strict.csv scripts/resolve_materials.py src/stdn_agentic/tests/unit/test_resolve_materials.py output/analysis/material_resolution_report.md config_vignettes_strict.json
git commit -m "feat(revision): materials resolution post-pass to elemental/compound forms (Reviewer 2)"
```

**As run (done 2026-10-27):** map has 388 rows (212 compound, 105 generic, 69 element, 2 not_material) plus an `elements` column; output adds `material_elements`. Country shares for mapped rows are refetched inside `resolve_materials.py` (USGS, then LLM fallback cache, no live LLM): 419,525 rows filled, 90 left blank (Potassium, Beryllium oxide, Cesium antimonide). Report (`scripts/material_resolution_report.py`, material-node counts): element+compound share 71.8%→93.3% micro, 64.5%→96.0% biotech, 61.7%→98.1% pharma. Step 8 ran at d3v1v1 (the submitted vignette config) on Cobot Arm + 5G Base Station, tagged `vigstrict_`, with the Task 0.2 safety pattern; 5G antenna now reads Aluminum/Copper plus Silicon dioxide, Silver/Silicon carbide, or Silver/Silicon/PET across 3 runs. Caution for Task 2.5: Neodymium (cobot) appeared in 1/3 strict runs and GaAs (5G) in 2/3. Deviations are ledgered in `.superpowers/sdd/2026-10-13-commssustain-revision-plan/progress.md`.

### Task 0.4: Ask the user for the biotech/pharma list provenance (blocks Task 2.1 only)

- [x] **Step 1:** Send the user the single question: "How were `data/tech_list_biotechnology_products.csv` and `data/tech_list_pharmaceutical_products.csv` constructed (source lists, LLM-assisted, expert-curated), and what inclusion criteria were applied?" Record the answer in paper-repo memory `project_tech_list_provenance.md`.

---

## Phase 1 — Post-hoc analyses (no new runs; weeks 2–5)

### Task 1.1: τ and R sensitivity from existing transcripts, merged with the reruns

**Files:**
- Create: `~/git/dpi_stdn_agentic/scripts/sensitivity_tau_rounds.py`
- Create: `~/git/dpi_stdn_agentic/output/analysis/sensitivity_tau_rounds.md`
- Create: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/scripts/sensitivity_tau_rounds.py` (copy, for reproducibility, as with `cross_domain_stability_analysis.py`)

**Interfaces:**
- Consumes: `output/transcripts/*_d3v1v1_*.json` (fields `component_stage.phase2_debate_rounds[i].{convergence, proposals}`, `phase3_final_consensus.components`); `data/component_canonical_vocab.json`; after Task 0.2, normalized CSVs for `tau085`, `tau095`, `r5`.
- Produces: table of per-technology median pairwise Jaccard under: actual (τ=0.7,R=3); reconstructed stop-at-round-1; stop-at-round-2; reconstructed τ'∈{0.5,0.6}; rerun τ=0.85; τ=0.95; R=5.

Reconstruction rule: for round *r*, apply the same consensus rule the pipeline uses, `ComponentDebater.build_adaptive_consensus` (`src/stdn_agentic/debate/component_debater.py:583`), to that round's proposals with that round's `convergence` score; the min-support fraction is 2/3 at high convergence and 1/3 at low (see `_compute_min_support`, line 737). Import and call it rather than re-implementing.

- [ ] **Step 1: Write the failing test**

```python
# src/stdn_agentic/tests/unit/test_sensitivity_tau_rounds.py
from scripts.sensitivity_tau_rounds import stop_round_for_tau, consensus_at_round

def test_stop_round_for_tau_picks_first_round_meeting_threshold():
    rounds = [{"convergence": 0.55}, {"convergence": 0.72}, {"convergence": 0.9}]
    assert stop_round_for_tau(rounds, 0.5) == 1
    assert stop_round_for_tau(rounds, 0.7) == 2
    assert stop_round_for_tau(rounds, 0.95) == 3   # cap reached

def test_consensus_at_round_matches_pipeline_final_when_last_round_used(sample_transcript):
    t = sample_transcript
    rebuilt = consensus_at_round(t, len(t["component_stage"]["phase2_debate_rounds"]))
    assert set(rebuilt) == {c["name"] for c in t["component_stage"]["phase3_final_consensus"]["components"]}
```
Add a `sample_transcript` fixture loading one real `d3v1v1` transcript from `output/transcripts/`.

- [ ] **Step 2: Run to verify it fails** — `uv run pytest src/stdn_agentic/tests/unit/test_sensitivity_tau_rounds.py -v` → FAIL, module missing.

- [ ] **Step 3: Implement**

```python
# scripts/sensitivity_tau_rounds.py
import glob, json, re, csv
from collections import defaultdict
from itertools import combinations
from statistics import median
from stdn_agentic.debate.component_debater import ComponentDebater

def stop_round_for_tau(rounds, tau):
    for i, r in enumerate(rounds, 1):
        if r["convergence"] >= tau: return i
    return len(rounds)

def consensus_at_round(t, r):
    rd = t["component_stage"]["phase2_debate_rounds"][r-1]
    props = [{"agent_id": a, "components": comps} for a, comps in rd["proposals"].items()]
    d = ComponentDebater(convergence_threshold=0.7)          # constructor takes no agent count
    return list(d.build_adaptive_consensus(props, rd["convergence"]))   # returns List[str] of names

def jaccard(a, b): return len(a & b) / len(a | b) if (a | b) else 1.0

def per_tech_median_jaccard(sets_by_tech):
    return {t: median(jaccard(a, b) for a, b in combinations(s, 2)) for t, s in sets_by_tech.items() if len(s) >= 2}
```
Then a `main()` that groups the five `d3v1v1` runs per technology, builds sets for each scenario, normalizes names by direct lookup in `data/component_canonical_vocab_global_primary.json` (the same frozen vocabulary the Step 6 normalization used; names absent from it are kept verbatim and counted), writes the markdown table, and reads the rerun normalized CSVs for the τ=0.85/0.95/R=5 columns.

- [ ] **Step 4: Run tests, run analysis, inspect**

```bash
uv run pytest src/stdn_agentic/tests/unit/test_sensitivity_tau_rounds.py -v
uv run python scripts/sensitivity_tau_rounds.py > output/analysis/sensitivity_tau_rounds.md; cat output/analysis/sensitivity_tau_rounds.md
```
Expected: the "stop at final round" column reproduces the submitted d3 micro median (0.327) within rounding; the sign of the micro debate effect (Δ vs v1 = 0.500) is reported for every scenario.

- [ ] **Step 5: Commit** — `git add scripts/sensitivity_tau_rounds.py src/stdn_agentic/tests/unit/test_sensitivity_tau_rounds.py output/analysis/sensitivity_tau_rounds.md && git commit -m "feat(revision): tau/R sensitivity analysis (Reviewer 1.5)"`

### Task 1.2: Mechanism analysis for the domain-dependent debate effect

**Files:**
- Create: `~/git/dpi_stdn_agentic/scripts/debate_mechanism_by_domain.py`
- Create: `~/git/dpi_stdn_agentic/data/tech_type_labels.csv` (177 rows: `domain,tech,type` with `type` ∈ {`instrument`,`consumer_product`,`infrastructure`,`component`})
- Create: `~/git/dpi_stdn_agentic/output/analysis/debate_mechanism_by_domain.md`

**Interfaces:**
- Consumes: `d3v1v1` transcripts for all 177 paired technologies; per-technology paired Δ from `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/scripts/cross_domain_stability_analysis.py` (expose its per-tech dict as a function `paired_deltas() -> dict[(domain,tech), float]`).
- Produces: per-domain medians and Spearman ρ with Δ for four transcript-derived metrics: round-1 inter-agent agreement (`phase2_debate_rounds[0].convergence`), rounds to termination, round-1 pooled candidate count, fraction of round-1 candidates pruned by final consensus; plus Δ by hand-coded technology type with a Kruskal–Wallis test.

- [ ] **Step 1: Hand-label `tech_type_labels.csv`** from the three tech lists (user or executor; 177 rows; commit).
- [ ] **Step 2: Write the test** asserting `metrics_for_transcript(t)` returns the four keys with values in [0,1] or positive ints on a real transcript.
- [ ] **Step 3: Implement** metrics extraction and the correlation/KW tests with `scipy.stats.spearmanr` and `kruskal`; 10,000-resample bootstrap CIs with `numpy.random.default_rng(42)` to match the submitted analyses.
- [ ] **Step 4: Run; write markdown; commit.** Expected output answers Reviewer 1.4 either way: either a metric with |ρ| clearly above the 0.13 ceiling of the vocabulary metrics, or a documented null that lets the Discussion say which mechanisms were tested and excluded.

### Task 1.3: Concentration indices beyond HHI (WGI- and HDI-weighted), Reviewer 3

**Files:**
- Create: `~/git/dpi_stdn_agentic/data/country_name_map.csv` (`raw,iso3,display`)
- Create: `~/git/dpi_stdn_agentic/data/wgi_political_stability_<year>.csv`, `data/hdi_<year>.csv` (downloaded; cite World Bank WGI and UNDP HDR in `references.bib`)
- Create: `~/git/dpi_stdn_agentic/scripts/concentration_indices.py`
- Create: `~/git/dpi_stdn_agentic/output/analysis/concentration_indices.md`
- Create: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/figures/fig5_indices_make.py` (replaces `fig5_nd_hhi_make.py`)

**Interfaces:**
- Consumes: `output/resolved/*.csv` from Task 0.3 (columns `material_resolved, country, percentage, country_confidence, extraction_provenance`).
- Produces: per-material table with `HHI`, `HHI_WGI` (EU CRM Act convention: Σ sᵢ²·WGIᵢ with WGI rescaled to [0,10] so higher = worse governance), `HHI_HDI` (same with 1−HDI), the US-DOJ 2,500 flag, and the rank change between indices; one row per material with USGS-authoritative shares, plus a per-technology roll-up for the seven neodymium technologies.

- [ ] **Step 1: Build the country-name map and assert full coverage**

```python
# test: every distinct `country` value across output/resolved maps to an iso3 or to OTHER
import csv, glob
names = {r["country"] for f in glob.glob("output/resolved/*.csv") for r in csv.DictReader(open(f)) if r["country"]}
mapped = {r["raw"] for r in csv.DictReader(open("data/country_name_map.csv"))}
assert names - mapped == set(), names - mapped
```
Known cases to include: `CHINA`/`China`, `KOREA, REPUBLIC OF`/`South Korea`, `CONGO`→COD, `BURMA`→MMR, `RUSSIA`/`Russia`, `OTHER`→`OTHER`. `OTHER` is treated as a single residual with share sᵢ and WGI/HDI set to the production-weighted mean of named producers; report sensitivity with `OTHER` excluded.

- [ ] **Step 2: Implement indices**

```python
def hhi(shares): return sum(s*s for s in shares.values())          # shares in percent, 0–10,000
def weighted_hhi(shares, w): return sum(s*s*w[c] for c, s in shares.items())
```
with `w` = rescaled WGI political-stability (0 best … 10 worst) or `1−HDI` rescaled identically; document the rescaling in Methods.

- [ ] **Step 3: Run across all materials; write table; list materials whose "highly concentrated" verdict or top-10 rank differs between HHI and HHI_WGI.** Expected: neodymium remains top-tier under all three; the interesting rows are materials with mid-range HHI whose weighted index moves (this is the point Reviewer 3 raised from Bucciarelli et al.). Cite Bucciarelli (10.1016/j.eneco.2025.108208) and Cho et al. (10.1140/epjqt/s40507-026-00486-y) in `references.bib`.

- [ ] **Step 4: Regenerate Fig. 5 as a two-panel figure** (HHI vs HHI_WGI per material, with the Nd technologies highlighted); commit both repos.

### Task 1.4: Substitutability and bottleneck attributes as edge metadata (Reviewer 3, weighting)

**Files:**
- Create: `~/git/dpi_stdn_agentic/data/eu_crm_2023_substitution_index.csv` (SI(SR), SI(EI), EoL-RIR per material; source: EU 2023 criticality assessment)
- Modify: `scripts/concentration_indices.py` to left-join these columns onto the material table.

- [ ] **Step 1:** Add the join and a column `bottleneck_score = HHI_WGI × (1 − EoL_RIR) × SI_SR` with its definition in Methods; this is a demonstration of attaching established weighting inputs, not a new criticality index.
- [ ] **Step 2:** Produce the neodymium row as the worked example for the response (monopoly, no substitute, low recycling).
- [ ] **Step 3:** Commit.

### Task 1.5: Model-portability evidence (Reviewer 2.3)

**Files:**
- Modify: `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/sections/supplementary.tex` (new S.13 "Model dependence")
- Optional create: `~/git/dpi_stdn_agentic/config_micro_tau_subset_newmodel.json`

- [ ] **Step 1: Surface the existing qwen2.5:32b experiment** from `output/analysis/stage1_judge_experiment_comparison.md` and code-repo memory `experiment-results.md` (4 technologies: debate helps with gpt-4.1-mini, hurts with qwen2.5:32b; macro median 0.554 vs 0.250). Write it up as S.13 with the table.
- [ ] **Step 2 (optional, ≤1 day machine time): newer-model pilot.** Copy `config_micro_tau_subset.json`, set the three extraction models to the current OpenAI general model per `~/git/dpi_stdn_agentic` memory `model-compatibility.md` (Anthropic models mostly do not work with the pipeline), run `v1v1v1` and `d3v1v1` × 5 on the 20-tech subset, normalize with the Task 0.2 Step 6 command (`--freeze-vocab`), compute paired Δ with `cross_domain_stability_analysis.py`. Report alongside S.13.
- [ ] **Step 3:** Commit.

---

## Phase 2 — Manuscript revision (weeks 4–9)

### Task 2.1: Methods — technology selection and comparability (Reviewer 1.1)

**Files:** Modify `sections/methods.tex` (new subsection "Benchmark construction" before "LLM Judge"); modify `sections/supplementary.tex` Appendix A preamble.

- [x] **Step 1:** Write the subsection from the Task 0.4 answer: per-domain source, inclusion criteria (sub-domain stratification 12 × 5, product-level technologies with documented bills of materials, exclusion of pure services and raw materials), the role-prompt column, and an explicit comparability caveat (microelectronics list predates the other two; the sub-domain structure was matched).
- [x] **Step 2:** Add a three-column table of sub-domains per domain to Appendix A.
- [x] **Step 3:** Build; commit.

### Task 2.2: Methods — evaluation-metrics summary table (Reviewer 1.3)

**Files:** Modify `sections/methods.tex` (new table `tab:metrics`).

- [x] **Step 1:** Add a four-column table: metric, definition, what it measures (stability vs validity vs cost), where reported. Rows: post-normalization pairwise Jaccard; pre-normalization (transcript-level) Jaccard; core ratio; occurrence-based invalid rate; deduped-canonical invalid rate; judge recall and lower-bound precision vs gold standard; final convergence score; rounds; runtime; cost. Cross-reference every metric's first use to this table.
- [x] **Step 2:** Build; commit.

### Task 2.3: Results — new evidence (Reviewers 1.2, 1.5, 2.1, 3)

**Files:** Modify `sections/results.tex`; modify `sections/supplementary.tex`.

- [ ] **Step 1: Cross-domain N = 5.** Extend `tab:ablation-debate` with `d5` columns for all three domains (run `scripts/cross_domain_stability_analysis.py` after adding a `d5v1v1` config argument). Rewrite the subsection opening so the claim matches the data under the framing rule.
- [ ] **Step 2: New subsection `\label{sec:sensitivity}` "Sensitivity to convergence threshold and round cap"** reporting Task 1.1's table in ≤150 words of main text plus a Supplementary table; state the seed and subset construction.
- [ ] **Step 3: Materials resolution.** In `sec:layered-stdn-capability`, replace the "ceramics 60% concentrated in China" sentence with the resolved constituents from Task 0.3 Step 8, and add two sentences on the resolution pass with the before/after element-plus-compound share from `material_resolution_report.md`. Refresh `tab:crm-coverage` with and without resolved rows (Review Focus 3).
- [ ] **Step 4: Downstream analysis.** Rewrite `sec:downstream-sustainability` around Task 1.3: HHI, WGI-weighted, HDI-weighted; where verdicts agree and where they diverge; the neodymium row with substitutability and recycling attached (Task 1.4).
- [ ] **Step 5: Word budget.** `texcount -inc -sum main.tex` on main-text sections only; cut to ≤5,200 by moving the vocabulary-correlation detail and the engineered-baseline paragraph to Supplementary.
- [ ] **Step 6:** Build; commit.

### Task 2.4: Discussion — heterogeneity, roadmap, model portability, weighting (Reviewers 1.4, 2.2, 2.3, 3)

**Files:** Modify `sections/discussion.tex`.

- [ ] **Step 1:** Replace "A note on domain-dependent debate behavior" with a systematic paragraph: candidate mechanisms tested (vocabulary cardinality, round-1 agreement, rounds, pruning fraction, technology type), which were excluded, which (if any) survived, and the resulting deployment guidance.
- [ ] **Step 2:** New paragraph "Development roadmap": dynamic updating (re-run cost per refresh, what is cached, what must be refetched), material grades and purities, specialty compounds not indexed by USGS (SiC example: resolve to compound, flag as unindexed, prefer false positive), and model portability (what changes when porting: prompt-format adherence, ontology filtering rate, debate benefit sign; point to S.13).
- [ ] **Step 3:** Paragraph on layer weighting: STDN-GEN emits the map; weights, substitutability, and monopoly structure are attributes attached at analysis time (Task 1.4 demonstration); no equal-weighting assumption is made.
- [ ] **Step 4:** Build; commit.

### Task 2.5: Figures (Reviewer 2.4 and refreshes)

**Files:** Modify `sections/results.tex`, `sections/supplementary.tex`, `figures/fig2_vignettes.tex`, `figures/fig5_indices_make.py`.

- [ ] **Step 1:** Move the `fig6_cross_domain_debate.pdf` figure environment from `results.tex` to `supplementary.tex` and update references to `Supplementary Figure`.
- [ ] **Step 2:** Update Fig. 3 panel B (5G antenna) material nodes from Task 0.3 Step 8 output; update the data-source comment in `fig2_vignettes.tex`.
- [ ] **Step 3:** Replace Fig. 5 with the two-index figure from Task 1.3.
- [ ] **Step 4:** Confirm ≤10 main-text display items: `grep -c "begin{figure}\|begin{table}" sections/results.tex sections/discussion.tex sections/introduction.tex`.
- [ ] **Step 5:** Build; commit.

---

## Phase 3 — Packaging (weeks 10–11)

### Task 3.1: Point-by-point response

**Files:** Create `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/response_to_reviewers.tex`.

- [ ] **Step 1:** One numbered entry per reviewer comment (R1.1–R1.5, R2.main, R2.1–R2.4, R3.HHI, R3.weighting) and per editor bar. Each entry: reviewer text verbatim in italics; response; "Changes made" with section and page references.
- [ ] **Step 2:** The R1.5 entry opens with the τ correction and its disclosure (Review Focus 1).
- [ ] **Step 3:** The R3.weighting entry explains the misreading without condescension and points to the Task 1.4 demonstration.
- [ ] **Step 4:** Build to PDF; commit.

### Task 3.2: Marked-up and clean PDFs

- [ ] **Step 1:** `git show submitted-v1:main.tex > /tmp/old_main.tex` plus each `sections/*.tex` and `figures/*.tex` at that tag into `/tmp/old/`; run `latexdiff --flatten /tmp/old/main.tex main.tex > main_diff.tex` from a copy where `\input` paths resolve; `latexmk -pdf main_diff.tex`.
- [ ] **Step 2:** Visually confirm Methods τ change and new Results subsections show in colour (Review Focus 5).
- [ ] **Step 3:** `latexmk -C && latexmk -pdf main.tex` for the clean PDF.
- [ ] **Step 4:** Fill the editors' formatting table right-hand column; verify single-file requirement (paper-repo memory `project_commssustain_single_file_at_submission`).
- [ ] **Step 5:** Commit; tag `revision-v1`.

### Task 3.3: Update memories

- [ ] **Step 1:** Paper-repo memory: record outcome of N = 5 cross-domain runs, τ/R sensitivity headline numbers, and the resolution-pass coverage shift. Update `project_revision_round1.md` status.

---

## Schedule

| Week (from 2026-10-13) | Tasks | Gate |
|---|---|---|
| 1 | 0.1, 0.2 (launch), 0.3, 0.4 | runs complete; resolution tests green |
| 2–3 | 1.1, 1.2, 1.3 | three analysis markdowns written |
| 4–5 | 1.4, 1.5, 2.1, 2.2 | Methods sections build |
| 6–8 | 2.3, 2.4, 2.5 | full paper builds; ≤5,200 main-text words |
| 9 | internal read-through; humanize pass on new prose | co-author sign-off |
| 10 | 3.1, 3.2 | response + diff PDFs |
| 11 (ends 2026-12-19) | 3.3; submit | resubmitted |

Twelve-week deadline from the editors falls ~2027-01-05; the schedule leaves two weeks of slack.
