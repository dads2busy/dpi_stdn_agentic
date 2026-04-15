# Microelectronics 61-tech rerun implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the technical report's 26-tech results with fresh pipeline runs on the 61-tech microelectronics product list, then regenerate all analysis tables and figures.

**Architecture:** Archive existing output data, create 5 debate-variant configs pointing at the microelectronics tech list, run 25 pipeline instances (5 configs x 5 runs), normalize outputs, then run the same analysis scripts that produced the technical report's results.

**Tech Stack:** Python (pydantic-ai), openai:gpt-4.1-mini (extraction), openai:gpt-4.1 (judge), uv, parallel_runs.py

---

### Task 1: Archive existing output data

**Files:**
- Move: `output/raw/*.csv` -> `output/archive_26tech/raw/`
- Move: `output/normalized/*.csv` -> `output/archive_26tech/normalized/`
- Move: `output/normalized/*.json` -> `output/archive_26tech/normalized/`
- Move: `output/transcripts/*` -> `output/archive_26tech/transcripts/`

- [ ] **Step 1: Create archive directories and move data**

```bash
mkdir -p output/archive_26tech/raw
mkdir -p output/archive_26tech/normalized
mkdir -p output/archive_26tech/transcripts
mv output/raw/*.csv output/archive_26tech/raw/
mv output/normalized/*.csv output/archive_26tech/normalized/
mv output/normalized/*.json output/archive_26tech/normalized/
mv output/normalized/manifests_by_technology output/archive_26tech/normalized/
mv output/transcripts/* output/archive_26tech/transcripts/
```

Do NOT move:
- `output/analysis/` (analysis reports are reference, not pipeline outputs)
- `data/component_canonical_vocab_global_primary.json` (canonical vocab is an input)
- `data/goldstndrd.csv` (gold standard is an input)
- `data/llm_fallback_cache/` (LLM cache speeds up country lookups)

- [ ] **Step 2: Verify archive and clean state**

```bash
ls output/archive_26tech/raw/ | wc -l       # expect ~90
ls output/archive_26tech/normalized/ | wc -l # expect ~100
ls output/raw/ | wc -l                       # expect 0
ls output/normalized/ | wc -l                # expect 0
ls output/transcripts/ | wc -l               # expect 0
```

---

### Task 2: Create config files for microelectronics runs

**Files:**
- Create: `config_micro_v1v1v1.json`
- Create: `config_micro_d2v1v1.json`
- Create: `config_micro_d3v1v1.json`
- Create: `config_micro_d4v1v1.json`
- Create: `config_micro_d5v1v1.json`

All configs share the same base settings. Only `enable_component_debate` and agent counts differ, but those are overridden by `parallel_runs.py` via the `--config-type` flag. So the base config just needs the right tech list, model, and generation parameters.

- [ ] **Step 1: Create the v1v1v1 base config**

Create `config_micro_v1v1v1.json` with these contents:

```json
{
  "_comment": "Microelectronics 61-tech rerun - v1v1v1 baseline",
  "import_tech_list": "./data/tech_list_microelectronic_products.csv",
  "model": "openai:gpt-4.1-mini",
  "output_dir": "./output",
  "output_csv_filename": "stdns_output",
  "component_normalization_model": "openai:gpt-4.1",
  "materials_hs_codes_listing": "./data/hs_codes_and_usgs_names.csv",
  "materials_column_name": "Elements_Compounds",
  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "top_n_countries": 5,
  "enable_llm_fallback_cache": true,
  "llm_fallback_cache_dir": "./data/llm_fallback_cache",
  "llm_fallback_cache_ttl_hours": 720,
  "generate_country_data": false,
  "country_data_mode": "incremental",
  "materials_to_update": null,
  "years_to_query": [2024, 2023],
  "write_nulls_to_output": true,
  "component_debate_top_p": 0.0001,
  "component_no_debate_top_p": 0.0001,
  "component_debate_temperature": 0.03,
  "component_no_debate_temperature": 0.03,
  "component_debate_use_personas": false,
  "material_debate_top_p": 0.0001,
  "material_no_debate_top_p": 0.0001,
  "materials_use_topp": true,
  "materials_iteration_count": 10,
  "materials_count_threshold": 5,
  "enable_checkpoints": true,
  "checkpoint_interval": 5,
  "model_provider": "ollama",
  "model_base_url": "http://localhost:11434/v1",
  "model_api_key": null,
  "model_temperature": 0.1,
  "component_model": "openai:gpt-4.1-mini",
  "materials_model": "openai:gpt-4.1-mini",
  "country_model": "openai:gpt-4.1-mini",
  "enable_process_consumables": false,
  "agent_retries": 5,
  "generate_visualizations": false,
  "fuzzy_material_matching": true,
  "material_match_threshold": 0.75,
  "component_validation_strict": false,
  "parallel_processing": false,
  "max_parallel_jobs": 3,
  "log_level": "INFO",
  "log_file": "./logs/stdn_agentic.log",
  "log_agent_responses": false,
  "component_timeout": 180,
  "materials_timeout": 180,
  "country_timeout": 120,
  "request_limit": 50,
  "total_tokens_limit": 100000
}
```

- [ ] **Step 2: Create debate variant configs**

Copy the v1v1v1 config to create the 4 debate variants. The only change is the `_comment` field (for readability). `parallel_runs.py` overrides debate settings via CLI `--config-type`, so the JSON does not need debate-specific fields.

```bash
cp config_micro_v1v1v1.json config_micro_d2v1v1.json
cp config_micro_v1v1v1.json config_micro_d3v1v1.json
cp config_micro_v1v1v1.json config_micro_d4v1v1.json
cp config_micro_v1v1v1.json config_micro_d5v1v1.json
```

Then update the `_comment` field in each:
- `config_micro_d2v1v1.json`: `"Microelectronics 61-tech rerun - d2v1v1"`
- `config_micro_d3v1v1.json`: `"Microelectronics 61-tech rerun - d3v1v1"`
- `config_micro_d4v1v1.json`: `"Microelectronics 61-tech rerun - d4v1v1"`
- `config_micro_d5v1v1.json`: `"Microelectronics 61-tech rerun - d5v1v1"`

- [ ] **Step 3: Verify configs**

```bash
for f in config_micro_*.json; do
  echo "=== $f ==="
  python3 -c "import json; d=json.load(open('$f')); print(d['import_tech_list'], d['model'], d['_comment'])"
done
```

Expected: all 5 show `./data/tech_list_microelectronic_products.csv`, `openai:gpt-4.1-mini`, and their respective comment.

---

### Task 3: Run v1v1v1 pipeline (5 runs)

**Files:**
- Output: `output/raw/stdns_output_v1v1v1_*.csv` (5 files)
- Output: `output/normalized/stdns_output_v1v1v1_*.csv` (5 files)
- Output: `output/transcripts/*v1v1v1*` (transcript files)

- [ ] **Step 1: Launch parallel runs**

```bash
uv run python scripts/parallel_runs.py \
  --config-type v1v1v1 \
  --num-runs 5 \
  --base-config config_micro_v1v1v1.json
```

This handles: launching 5 pipeline instances, monitoring file growth, renaming outputs, running shared normalization, and generating JSON.

- [ ] **Step 2: Verify outputs**

```bash
ls output/raw/stdns_output_v1v1v1_*.csv | wc -l     # expect 5
ls output/normalized/stdns_output_v1v1v1_*.csv | wc -l  # expect 5
```

Check that each CSV has rows for all 61 technologies:

```bash
for f in output/raw/stdns_output_v1v1v1_*.csv; do
  echo "$f: $(cut -d, -f1 "$f" | sort -u | wc -l) technologies"
done
```

---

### Task 4: Run d2v1v1 pipeline (5 runs)

- [ ] **Step 1: Launch parallel runs**

```bash
uv run python scripts/parallel_runs.py \
  --config-type d2v1v1 \
  --num-runs 5 \
  --base-config config_micro_d2v1v1.json
```

- [ ] **Step 2: Verify outputs**

```bash
ls output/raw/stdns_output_d2v1v1_*.csv | wc -l        # expect 5
ls output/normalized/stdns_output_d2v1v1_*.csv | wc -l  # expect 5
```

---

### Task 5: Run d3v1v1 pipeline (5 runs)

- [ ] **Step 1: Launch parallel runs**

```bash
uv run python scripts/parallel_runs.py \
  --config-type d3v1v1 \
  --num-runs 5 \
  --base-config config_micro_d3v1v1.json
```

- [ ] **Step 2: Verify outputs**

```bash
ls output/raw/stdns_output_d3v1v1_*.csv | wc -l        # expect 5
ls output/normalized/stdns_output_d3v1v1_*.csv | wc -l  # expect 5
```

---

### Task 6: Run d4v1v1 pipeline (5 runs)

- [ ] **Step 1: Launch parallel runs**

```bash
uv run python scripts/parallel_runs.py \
  --config-type d4v1v1 \
  --num-runs 5 \
  --base-config config_micro_d4v1v1.json
```

- [ ] **Step 2: Verify outputs**

```bash
ls output/raw/stdns_output_d4v1v1_*.csv | wc -l        # expect 5
ls output/normalized/stdns_output_d4v1v1_*.csv | wc -l  # expect 5
```

---

### Task 7: Run d5v1v1 pipeline (5 runs)

- [ ] **Step 1: Launch parallel runs**

```bash
uv run python scripts/parallel_runs.py \
  --config-type d5v1v1 \
  --num-runs 5 \
  --base-config config_micro_d5v1v1.json
```

- [ ] **Step 2: Verify outputs**

```bash
ls output/raw/stdns_output_d5v1v1_*.csv | wc -l        # expect 5
ls output/normalized/stdns_output_d5v1v1_*.csv | wc -l  # expect 5
```

---

### Task 8: Run supplementary pharma runs for gold standard validation

**Files:**
- Create: `data/tech_list_goldstandard_supplement.csv`
- Create: `config_goldstandard_supplement.json`
- Output: `output/raw/stdns_output_v1v1v1_*_supplement.csv` (5 files)
- Output: `output/raw/stdns_output_d3v1v1_*_supplement.csv` (5 files)
- Output: `output/normalized/stdns_output_v1v1v1_*_supplement.csv` (5 files)
- Output: `output/normalized/stdns_output_d3v1v1_*_supplement.csv` (5 files)

The gold standard covers 4 technologies: Smartphone, Pharmaceutical Lyophilizer, Rotary Tablet Press, Single-use Bioreactor. Only Smartphone is in the microelectronics list. We need supplementary runs for the other 3 so gold standard validation can use all 4 techs.

- [ ] **Step 1: Create supplementary tech list**

Create `data/tech_list_goldstandard_supplement.csv`:

```csv
domain,tech,role
Pharmaceutical,Pharmaceutical Lyophilizer,an expert in pharmaceutical manufacturing equipment
Pharmaceutical,Rotary Tablet Press,an expert in pharmaceutical manufacturing equipment
Biotechnology,Single-use Bioreactor,an expert in bioprocess and biomanufacturing equipment
```

- [ ] **Step 2: Create supplementary config**

Copy `config_micro_v1v1v1.json` to `config_goldstandard_supplement.json` and change:
- `_comment`: `"Gold standard supplement - 3 pharma/biotech techs for judge validation"`
- `import_tech_list`: `"./data/tech_list_goldstandard_supplement.csv"`

- [ ] **Step 3: Run v1v1v1 (5 runs)**

```bash
uv run python scripts/parallel_runs.py \
  --config-type v1v1v1 \
  --num-runs 5 \
  --base-config config_goldstandard_supplement.json
```

- [ ] **Step 4: Run d3v1v1 (5 runs)**

```bash
uv run python scripts/parallel_runs.py \
  --config-type d3v1v1 \
  --num-runs 5 \
  --base-config config_goldstandard_supplement.json
```

- [ ] **Step 5: Verify outputs**

The supplementary outputs land in the same `output/raw/` and `output/normalized/` directories. They will contain only the 3 pharma/biotech techs. The gold standard validation script (Task 11) will find all 4 gold standard techs across the combined microelectronics + supplement normalized files.

```bash
# Check that supplement files exist and contain the 3 techs
for f in output/normalized/stdns_output_v1v1v1_*.csv; do
  grep -l "Pharmaceutical Lyophilizer\|Rotary Tablet Press\|Single-use Bioreactor" "$f" && echo "  -> has supplement techs"
done
```

---

### Task 9: Run naive baseline (gold standard techs only)

**Files:**
- Output: `output/analysis/micro_naive_baseline.md`
- Output: `output/analysis/micro_naive_baseline.jsonl`

The naive baseline runs on the 4 gold standard technologies only (not all 61). This is unchanged from the paper.

- [ ] **Step 1: Run naive baseline**

```bash
uv run python scripts/naive_component_baseline.py \
  --extraction-model openai:gpt-4.1-mini \
  --runs 5 \
  --goldstandard data/goldstndrd.csv \
  --global-vocab data/component_canonical_vocab_global_primary.json \
  --analysis-dir output/analysis
```

- [ ] **Step 2: Verify output**

```bash
ls output/analysis/micro_naive_baseline* 2>/dev/null || ls output/analysis/naive_baseline*
```

Note: the script may use default output names rather than `micro_` prefix. Check what it actually writes and rename if needed for consistency.

---

### Task 10: Run judge validity analysis

**Files:**
- Output: `output/analysis/micro_stage1_judge.md`
- Output: `output/analysis/micro_stage1_judge.jsonl`

- [ ] **Step 1: Run judge on all configs**

```bash
uv run python scripts/judge_stage1_components_from_normalized_outputs.py \
  --normalized-dir output/normalized/ \
  --configs v1v1v1 d2v1v1 d3v1v1 d4v1v1 d5v1v1 \
  --judge-model openai:gpt-4.1 \
  --out-md output/analysis/micro_stage1_judge.md \
  --out-jsonl output/analysis/micro_stage1_judge.jsonl
```

- [ ] **Step 2: Verify output**

```bash
cat output/analysis/micro_stage1_judge.md | head -40
```

Check that the report shows all 5 configs with per-N invalid rates.

---

### Task 11: Run gold standard judge validation

**Files:**
- Output: `output/analysis/micro_judge_validation_vs_goldstandard.md`

This uses normalized outputs from both the microelectronics runs (Smartphone) and the supplementary pharma runs (Task 8: Lyophilizer, Tablet Press, Bioreactor) to validate the judge against all 4 gold standard technologies.

- [ ] **Step 1: Run judge validation against gold standard**

```bash
uv run python scripts/validate_judge_against_goldstandard.py \
  --goldstandard data/goldstndrd.csv \
  --normalized-dir output/normalized/ \
  --configs v1v1v1 d3v1v1 \
  --judge-model openai:gpt-4.1 \
  --out-md output/analysis/micro_judge_validation_vs_goldstandard.md
```

- [ ] **Step 2: Verify all 4 gold standard techs appear**

```bash
grep -E "Smartphone|Lyophilizer|Tablet Press|Bioreactor" output/analysis/micro_judge_validation_vs_goldstandard.md
```

All 4 technologies should appear with TP/FP/TN/FN counts.

---

### Task 12: Run component stability analysis

**Files:**
- Output: `output/analysis/micro_stage1_stability.md`
- Output: `output/analysis/micro_stage1_stability.json`

- [ ] **Step 1: Run stability analysis**

```bash
uv run python scripts/analyze_stage1_component_stability_normalized.py \
  --normalized-dir output/normalized/ \
  --include-config v1v1v1 \
  --include-config d2v1v1 \
  --include-config d3v1v1 \
  --include-config d4v1v1 \
  --include-config d5v1v1 \
  --min-runs 2 \
  --out-md output/analysis/micro_stage1_stability.md \
  --out-json output/analysis/micro_stage1_stability.json
```

- [ ] **Step 2: Verify output**

```bash
cat output/analysis/micro_stage1_stability.md | head -60
```

Check that stability metrics appear for all 5 configs across 61 technologies.

---

### Task 13: Run convergence analysis

**Files:**
- Output: `output/analysis/micro_convergence.csv`

- [ ] **Step 1: Run convergence extraction from transcripts**

```bash
uv run python scripts/analyze_convergence_by_agent_count.py \
  --transcripts-dir output/transcripts/ \
  --out-csv output/analysis/micro_convergence.csv
```

- [ ] **Step 2: Verify output**

```bash
head -5 output/analysis/micro_convergence.csv
wc -l output/analysis/micro_convergence.csv
```

Check that configs v1v1v1 through d5v1v1 appear with convergence metrics.

---

### Task 14: Run sweet-spot tradeoff analysis

**Files:**
- Output: `output/analysis/micro_sweet_spot.md`
- Output: `output/analysis/micro_sweet_spot_by_tech.csv`
- Output: `output/analysis/micro_sweet_spot_by_n.csv`

This is the comprehensive analysis that combines stability, validity, convergence, and runtime with bootstrap confidence intervals. It depends on outputs from Tasks 10 and 13.

- [ ] **Step 1: Run sweet-spot analysis**

```bash
uv run python scripts/analyze_sweet_spot_tradeoffs.py \
  --transcripts-dir output/transcripts/ \
  --normalized-dir output/normalized/ \
  --canonical-vocab data/component_canonical_vocab_global_primary.json \
  --judge-jsonl output/analysis/micro_stage1_judge.jsonl \
  --log-dir output/logs/ \
  --out-md output/analysis/micro_sweet_spot.md \
  --out-techn-csv output/analysis/micro_sweet_spot_by_tech.csv \
  --out-by-n-csv output/analysis/micro_sweet_spot_by_n.csv
```

- [ ] **Step 2: Verify output**

```bash
head -5 output/analysis/micro_sweet_spot_by_n.csv
cat output/analysis/micro_sweet_spot.md | head -80
```

Check that by-N CSV has rows for N=1 through N=5 with stability, validity, convergence, and runtime columns.

---

### Task 15: Generate paper figures

**Files:**
- Output: `output/analysis/figures/validity_vs_n_dedup_invalid_and_k.png`
- Output: `output/analysis/figures/tradeoff_runtime_vs_stability.png`
- Output: `output/analysis/figures/convergence_rounds_vs_n.png`
- Output: `output/analysis/figures/invalid_rate_occ_vs_dedup.png`
- Output: `output/analysis/figures/paired_invalid_rate_dedup_n1_vs_n3.png`

- [ ] **Step 1: Generate figures**

```bash
mkdir -p output/analysis/figures

uv run python scripts/plot_sweet_spot_figures.py \
  --by-n-csv output/analysis/micro_sweet_spot_by_n.csv \
  --per-tech-csv output/analysis/micro_sweet_spot_by_tech.csv \
  --out-dir output/analysis/figures/
```

- [ ] **Step 2: Generate stability heatmap**

```bash
uv run python scripts/plot_stability_heatmap.py \
  --per-tech-csv output/analysis/micro_sweet_spot_by_tech.csv \
  --out output/analysis/figures/stability_heatmap_by_tech_and_n.png
```

- [ ] **Step 3: Verify all figures generated**

```bash
ls output/analysis/figures/*.png
```

Expected: 6 PNG files (5 from sweet-spot + 1 heatmap).

---

### Task 16: Review results and commit

- [ ] **Step 1: Review key metrics**

Open and review the sweet-spot markdown report:

```bash
cat output/analysis/micro_sweet_spot.md
```

Key things to check:
- Does debate still improve validity (lower invalid rates at N=3 vs N=1)?
- Does stability improve with debate (higher Jaccard at N=3 vs N=1)?
- What is the recommended sweet-spot N?
- How do the 61-tech results compare qualitatively to the 26-tech paper results?

- [ ] **Step 2: Commit configs**

```bash
git add config_micro_*.json config_goldstandard_supplement.json data/tech_list_goldstandard_supplement.csv
git commit -m "config: add microelectronics 61-tech rerun configs and gold standard supplement"
```

- [ ] **Step 3: Commit analysis outputs**

```bash
git add output/analysis/micro_*.md output/analysis/micro_*.csv output/analysis/micro_*.jsonl
git add output/analysis/figures/*.png
git commit -m "data: microelectronics 61-tech rerun analysis results"
```
