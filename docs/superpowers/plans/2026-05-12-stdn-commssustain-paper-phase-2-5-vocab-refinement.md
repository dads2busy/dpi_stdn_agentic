# Communications Sustainability Paper — Phase 2.5 (Targeted Canonical-Vocab Refinement + Vignette Re-run) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Refine the canonical vocabulary at narrow points where it over-collapses dependency-relevant sub-types, re-run just the two vignette technologies (EV Traction Inverter, 5G Base Station Macro Cell) with the refined vocab, regenerate Fig 2 + §2.1 prose, and add a brief Discussion note about the targeted refinement.

**Why this phase exists:** the existing canonical vocab maps "permanent magnet rotor assembly" → "Rotor Assembly", which loses the NdFeB/rare-earth signal needed for EV Traction Inverter's dependency story. Similar over-collapses are suspected for GaN power amplifiers and tantalum capacitors in the 5G Base Station vignette. Phase 2 surfaced this; we fix it for the two vignette technologies without churning the 60-tech ablation results.

**Architecture:** Targeted vocab refinement (vocab v1.0 → v1.1) only at the variant→canonical mappings that matter for the two vignette technologies. The 60-tech ablation in Tables 1a/1b and Fig 3 was run with vocab v1.0 and stays untouched; we document this clearly. Vignettes are re-run against vocab v1.1.

**Scope discipline:** do NOT broaden vocab changes beyond what's required for these two technologies. Do NOT re-run the 60-tech benchmark. Do NOT touch the ablation results, Tables 1a/1b, or Fig 3.

**Tech Stack:** Python (vocab edits), `uv run stdn` (pipeline re-run), LaTeX (paper edits).

**Cost estimate:** 1-2 weeks of focused work. Pipeline re-runs are the longest single step (~30-60 min per tech depending on config).

---

## File structure (changes)

### Code repo `~/git/dpi_stdn_agentic/`
- Modify: `data/component_canonical_vocab_global_primary.json` (v1.0 → v1.1; targeted mapping changes; bump version + updated_at)
- New: `data/component_canonical_vocab_v1.0.snapshot.json` (frozen copy of v1.0 for the 60-tech ablation provenance)
- Modify: `output/normalized/manifests_by_technology/normalization_manifest_ev_traction_inverter_*.json` (new run output)
- Modify: same for 5g_base_station_macro_cell
- Document changes in `docs/canonical_vocab_v1.1_changelog.md`

### Paper repo `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/`
- Modify: `figures/fig2_vignettes.tex` (regenerated from new data)
- Modify: `sections/results.tex` §2.1 (updated prose grounded in new data)
- Modify: `sections/discussion.tex` (add ~150-word paragraph on the targeted refinement and what it teaches)

---

## Task 1: Diagnose what each vignette technology's canonical components are

**Repo:** `~/git/dpi_stdn_agentic/`

Identify which canonical labels were assigned to the EV Inverter and 5G Base Station components in the existing (v1.0) run, and identify the specific over-collapses that suppressed the critical-material story.

- [ ] **Step 1: Locate the most recent STDN output CSV that contains both technologies**

```bash
cd ~/git/dpi_stdn_agentic
ls -t output/normalized/stdns_output_*.csv | head -5
# Pick the most recent that includes both techs:
grep -l "EV Traction Inverter\|5G Base Station Macro Cell" $(ls -t output/normalized/stdns_output_*.csv | head -5)
```

- [ ] **Step 2: Extract the canonical components for each tech**

```bash
cd ~/git/dpi_stdn_agentic
python3 << 'PYEOF'
import csv
# Substitute the CSV path identified in Step 1
PATH = "output/normalized/stdns_output_d5v1v1_20260414_165728.csv"
techs = {"EV Traction Inverter": set(), "5G Base Station Macro Cell": set()}
with open(PATH) as f:
    for row in csv.DictReader(f):
        if row.get("technology") in techs:
            techs[row["technology"]].add(row.get("component", ""))
for tech, comps in techs.items():
    print(f"\n=== {tech} ({len(comps)} canonical components) ===")
    for c in sorted(comps):
        print(f"  {c}")
PYEOF
```

- [ ] **Step 3: Identify over-collapses**

For each canonical component, the question is: "does this canonical label preserve the dependency-relevant sub-type?" Specifically:

- **EV Inverter:** Does "Rotor Assembly" or equivalent appear? If yes, does the canonical preserve "permanent magnet" / "NdFeB" qualifier? If not — that's an over-collapse to fix.
- **5G Base Station:** Does a "Power Amplifier" or "Radio Frequency Amplifier" canonical appear? Does it preserve "GaN" / "gallium nitride"? Does any canonical preserve "tantalum"?

For each over-collapse found, grep the source vocab to find which variants currently collapse to the generic canonical:

```bash
cd ~/git/dpi_stdn_agentic
python3 << 'PYEOF'
import json
m = json.load(open('data/component_canonical_vocab_global_primary.json'))['mappings']
# Substitute the canonical label you want to inspect:
target = "Rotor Assembly"
variants = [k for k, v in m.items() if v == target]
print(f"Canonical '{target}' has {len(variants)} variant mappings:")
for v in variants:
    print(f"  '{v}'")
PYEOF
```

- [ ] **Step 4: Produce a written list of refinements needed**

Output a list like:
```
# Vocab v1.0 → v1.1 refinements (targeted; vignette technologies only)

## EV Traction Inverter
- 'permanent magnet rotor assembly' → currently 'Rotor Assembly';
  CHANGE TO 'Permanent Magnet Rotor Assembly'
- 'rotor assembly (permanent magnet rotor' → currently 'Rotor Assembly';
  CHANGE TO 'Permanent Magnet Rotor Assembly'

## 5G Base Station Macro Cell
- [if applicable: 'gallium nitride power amplifier' → 'Power Amplifier';
  CHANGE TO 'Gallium Nitride Power Amplifier']
- [if applicable: 'tantalum capacitor' → 'Capacitor';
  CHANGE TO 'Tantalum Capacitor']
```

Save this list as `docs/canonical_vocab_v1.1_changelog.md` and commit it before making vocab changes.

**Reporting:**
- The list of canonical components for each tech.
- The specific over-collapses identified (variant → current canonical → proposed new canonical).
- If there are NO over-collapses for one of the techs (e.g., the 5G tech's canonicals already preserve the dependency-relevant info), say so and don't fabricate refinements.

---

## Task 2: Snapshot vocab v1.0; apply v1.1 refinements

**Repo:** `~/git/dpi_stdn_agentic/`

- [ ] **Step 1: Snapshot v1.0**

```bash
cd ~/git/dpi_stdn_agentic
cp data/component_canonical_vocab_global_primary.json data/component_canonical_vocab_v1.0.snapshot.json
```

This snapshot is the provenance record for the 60-tech ablation. Never modify it.

- [ ] **Step 2: Edit vocab to apply v1.1 refinements**

Use Python to edit the JSON cleanly:

```python
import json
from datetime import datetime, timezone

path = "data/component_canonical_vocab_global_primary.json"
with open(path) as f:
    d = json.load(f)

# Apply refinements from Task 1's changelog.
# Example pattern (replace with actual refinements):
refinements = {
    # variant → new canonical
    "permanent magnet rotor assembly": "Permanent Magnet Rotor Assembly",
    "rotor assembly (permanent magnet rotor": "Permanent Magnet Rotor Assembly",
    # ... add other refinements from Task 1
}

for variant, new_canonical in refinements.items():
    if variant in d["mappings"]:
        old = d["mappings"][variant]
        d["mappings"][variant] = new_canonical
        print(f"  '{variant}' : '{old}' → '{new_canonical}'")
    else:
        print(f"  WARNING: variant '{variant}' not in vocab; skipping")

d["version"] = "1.1"
d["updated_at"] = datetime.now(timezone.utc).isoformat()
d.setdefault("changelog", []).append({
    "version": "1.1",
    "date": d["updated_at"],
    "description": "Targeted refinements to preserve dependency-relevant sub-types for Communications Sustainability paper vignettes (EV Traction Inverter, 5G Base Station). See docs/canonical_vocab_v1.1_changelog.md.",
    "refinements_count": len(refinements),
})

with open(path, "w") as f:
    json.dump(d, f, indent=2)
```

- [ ] **Step 3: Verify the changes**

```bash
cd ~/git/dpi_stdn_agentic
python3 -c "
import json
d = json.load(open('data/component_canonical_vocab_global_primary.json'))
print(f'version: {d[\"version\"]}')
print(f'updated_at: {d[\"updated_at\"]}')
print(f'mappings: {len(d[\"mappings\"])}')
print(f'canonicals: {len(set(d[\"mappings\"].values()))}')
# Spot-check
print()
for k in ['permanent magnet rotor assembly', 'rotor assembly (permanent magnet rotor']:
    print(f'  {k!r} → {d[\"mappings\"].get(k)!r}')
"
```

- [ ] **Step 4: Commit**

```bash
cd ~/git/dpi_stdn_agentic
git add data/component_canonical_vocab_global_primary.json \
        data/component_canonical_vocab_v1.0.snapshot.json \
        docs/canonical_vocab_v1.1_changelog.md
git commit -m "refactor: canonical vocab v1.0→v1.1 with targeted refinements for paper vignettes"
```

---

## Task 3: Re-run EV Traction Inverter and 5G Base Station with vocab v1.1

**Repo:** `~/git/dpi_stdn_agentic/`

- [ ] **Step 1: Identify the config used for the 60-tech run**

Look at `output/normalized/stdns_output_*.csv` filenames for the config marker (e.g., `d5v1v1`, `d3v1v1`). Match that config for the re-run so the vignettes are comparable to the rest of the paper. If unclear, default to `d3v1v1` (the spec's recommended config).

- [ ] **Step 2: Create a focused tech list with just the two vignette techs**

```bash
cd ~/git/dpi_stdn_agentic
mkdir -p data/tmp
cat > data/tmp/tech_list_vignettes.csv << 'EOF'
domain,tech,role
Automotive,EV Traction Inverter,
Telecommunications,5G Base Station (Macro Cell),
EOF
```

(Confirm the exact tech-name spellings match the 60-tech list; the implementer should grep `data/tech_list_microelectronic_products.csv` to verify before writing this file.)

- [ ] **Step 3: Prepare a config for the re-run**

Reuse the existing config file used by the most recent 60-tech run, but override the tech list. Inspect the existing config:

```bash
cd ~/git/dpi_stdn_agentic
ls config*.json
cat config.json  # or whichever was used for d5v1v1 / d3v1v1
```

Create `config_vignettes_v1.1.json` with the same parameters but `"import_tech_list": "./data/tmp/tech_list_vignettes.csv"`.

- [ ] **Step 4: Run the pipeline**

```bash
cd ~/git/dpi_stdn_agentic
uv run stdn -i config_vignettes_v1.1.json
```

This will produce new STDN outputs under `output/normalized/`. Wait for completion (likely 20-60 min for two techs at d3v1v1 or d5v1v1).

- [ ] **Step 5: Verify the new outputs contain the expected critical-material story**

```bash
cd ~/git/dpi_stdn_agentic
# Look at the new CSV
ls -t output/normalized/stdns_output_*.csv | head -3
# For each tech, list the canonical components and their materials/countries
python3 << 'PYEOF'
import csv
PATH = "<path to new CSV from step 4>"
techs = {"EV Traction Inverter": [], "5G Base Station (Macro Cell)": []}
with open(PATH) as f:
    for row in csv.DictReader(f):
        if row["technology"] in techs:
            techs[row["technology"]].append({
                "component": row["component"],
                "material": row.get("material"),
                "country": row.get("country"),
                "percentage": row.get("percentage"),
                "hs_code": row.get("hs_code"),
            })
for tech, rows in techs.items():
    print(f"\n=== {tech} ({len(rows)} STDN rows) ===")
    for r in rows[:30]:
        print(f"  {r['component'][:40]:>40} | {str(r['material'])[:30]:>30} | {str(r['country'])[:20]:>20} | {r['percentage']}%")
PYEOF
```

Confirm:
- "Permanent Magnet Rotor Assembly" (or equivalent canonical) appears under EV Inverter.
- Materials for that component include neodymium / dysprosium / NdFeB / rare-earth-related entries.
- 5G base station shows whatever critical-material story emerges (GaN if gallium nitride was added; tantalum if tantalum capacitors was added).

**If the new STDNs still don't surface the expected critical materials**, this is a fail-fast signal: the canonical refinement alone isn't sufficient, and the materials extraction stage may need separate work. Pause and report BLOCKED rather than continuing.

- [ ] **Step 6: Commit the new outputs**

```bash
cd ~/git/dpi_stdn_agentic
git add output/normalized/stdns_output_*_v1.1*.csv \
        output/normalized/manifests_by_technology/normalization_manifest_ev_traction_inverter*.json \
        output/normalized/manifests_by_technology/normalization_manifest_5g_base_station*.json \
        config_vignettes_v1.1.json \
        data/tmp/tech_list_vignettes.csv
git commit -m "feat: re-run EV Inverter + 5G Base Station vignettes with vocab v1.1"
```

---

## Task 4: Regenerate Fig 2 + update §2.1 prose with new data

**Repo:** `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/`

- [ ] **Step 1: Read the new vignette data**

Use the paths from Task 3 Step 6 to load the new STDN rows for both techs.

- [ ] **Step 2: Regenerate `figures/fig2_vignettes.tex`**

Use the same TikZ structure as the current Fig 2 but with the new data. Each panel: top components → materials → top-3 countries with percentages. Confirm the new figure tells the targeted critical-material story (rare earths for EV; GaN/tantalum for 5G).

- [ ] **Step 3: Update §2.1 prose in `sections/results.tex`**

Find the vignette paragraph in §2.1 (currently mentions SiC and GaAs). Replace with prose grounded in the new data. Keep the structure: panel A finding sentence, panel B finding sentence, closing sentence. Target ~150 words.

- [ ] **Step 4: Build and verify**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C && latexmk -pdf main.tex 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git add figures/fig2_vignettes.tex sections/results.tex
git commit -m "feat: regenerate Fig 2 + update §2.1 prose with vocab-v1.1 vignette data"
```

---

## Task 5: Add Discussion paragraph documenting the targeted refinement

**Repo:** `~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/`

- [ ] **Step 1: Insert a new paragraph in §3.1 (speed-vs-depth tradeoff paragraph)**

After the existing §3.1 paragraph on speed-vs-depth, add ~150 words that documents:

- The original canonical vocabulary (v1.0) over-collapsed some dependency-relevant sub-types: e.g., "permanent magnet rotor assembly" mapped to a generic "Rotor Assembly" canonical, which suppressed the NdFeB/rare-earth signal at the materials layer.
- We surfaced this during Phase 2 vignette construction, refined the vocabulary at the over-collapse points (vocab v1.1), and re-ran just the two vignette technologies (EV Traction Inverter and 5G Base Station). The 60-tech ablation results in Tables 1a/1b and Figure 3 were unchanged — those ran on vocab v1.0 and are the empirical record we report.
- This itself illustrates the paper's core lesson: canonical-vocab investment is the high-leverage place to put engineering effort. The original vocab was good for stability, but it suppressed dependency signal where dependency-relevant qualifiers were collapsed. Future vocab work should preserve such qualifiers as canonical-variant sub-types.

Frame this as an honest mid-study observation that strengthens, rather than undermines, the paper's overall argument.

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
git commit -m "feat: add Discussion paragraph on targeted canonical-vocab refinement for vignettes"
```

Discussion is expected to grow from ~890 to ~1,030 words; still within the ~1,000 target band.

---

## Task 6: Verification and tag

- [ ] **Step 1: Final paper rebuild + word counts**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
latexmk -C && latexmk -pdf main.tex 2>&1 | tail -10
python3 << 'PYEOF'
import re
def wc(p):
    c = open(p).read()
    for e in ['table', 'figure', 'algorithm']:
        c = re.sub(rf'\\begin\{{{e}\}}.*?\\end\{{{e}\}}', '', c, flags=re.DOTALL)
    c = re.sub(r'\\input\{[^}]+\}', '', c)
    c = re.sub(r'%[^\n]*', '', c)
    c = re.sub(r'\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})*', '', c)
    c = re.sub(r'[\\\{\}\[\]]', '', c)
    return len(c.split())
for s in ['abstract', 'introduction', 'results', 'discussion', 'methods']:
    print(f'{s:>14}: {wc(f"sections/{s}.tex"):>5} words')
PYEOF
```

- [ ] **Step 2: Sanity-check that the 60-tech ablation results are unchanged**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
grep -A 5 "ablation-norm\|ablation-debate" sections/results.tex | head -30
```

Tables 1a and 1b should still show the same numbers as Phase 1. If anything looks different, that's a fail.

- [ ] **Step 3: Tag and push both repos**

```bash
cd ~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN
git tag phase-2.5-complete -m "Targeted vocab-v1.1 refinement; vignettes regenerated; Discussion paragraph added"
git push origin main && git push origin phase-2.5-complete

cd ~/git/dpi_stdn_agentic
git tag commssustain-vocab-v1.1 -m "Vocab v1.1 with targeted refinements for Comms Sustainability paper vignettes"
git push origin main && git push origin commssustain-vocab-v1.1
```

(Note: pushing the code repo may include unrelated pre-existing uncommitted work; only push the new commits from this phase. If pre-existing dirty state interferes, use `git stash` first or push only the specific commits.)

---

## Self-Review

- vocab v1.0 snapshot preserved as `component_canonical_vocab_v1.0.snapshot.json`?
- vocab v1.1 mapping count = v1.0 mapping count (no additions/deletions, only re-targeting)?
- New vignette STDN outputs surface rare-earth / NdFeB / gallium / tantalum where expected?
- Tables 1a, 1b, Fig 3 unchanged from Phase 1 (same numbers)?
- Discussion paragraph honestly documents the targeted refinement?
- Two tags (one per repo) created and pushed?

## Known follow-ups (still deferred to later phases)

- Bib entries for TODO citation stubs (Phase 4)
- SI labels (Phase 4)
- Cover letter, data/code availability statements (Phase 4)
- Single-file inlining for submission (Phase 5)

## Out of scope

- Broader vocab-quality work beyond these targeted refinements
- Re-running the 60-tech benchmark
- Re-doing the ablation analysis
- New gold-standard annotations
