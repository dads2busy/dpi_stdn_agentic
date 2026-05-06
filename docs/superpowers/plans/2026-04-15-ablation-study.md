# Ablation study implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quantify the contribution of each pipeline layer (normalization, structured extraction, debate) to output quality across 61 microelectronics technologies.

**Architecture:** Extend the naive baseline script to accept an arbitrary tech list, run it on 61 techs, run the judge on raw v1v1v1 files, then build a comparison script that assembles all 5 layers into a single table.

**Tech Stack:** Python, pydantic-ai, openai:gpt-4.1-mini (extraction), openai:gpt-4.1 (judge/normalization)

---

### Task 1: Add --tech-list argument to naive_component_baseline.py

**Files:**
- Modify: `scripts/naive_component_baseline.py`

When `--tech-list` is provided, the script reads technologies from that CSV (column `tech`) instead of the gold standard. Gold standard comparison (precision/recall/F1) is skipped, and the report only contains extraction summary (component counts, stability) and judge plausibility rates.

- [ ] **Step 1: Add the CLI argument**

In `parse_args()`, add after the `--goldstandard` argument:

```python
    p.add_argument(
        "--tech-list", default=None,
        help="Path to tech list CSV (domain,tech,role columns). "
             "When provided, runs on these techs instead of gold standard. "
             "Gold standard comparison is skipped.",
    )
```

- [ ] **Step 2: Add tech list loading at the top of async_main**

Replace the block at lines 386-398 (gold standard loading) with:

```python
    # 1. Determine technologies and optional gold standard
    if args.tech_list:
        # Tech-list mode: run on arbitrary technologies, no gold standard comparison
        import csv as csv_mod
        tech_list_path = Path(args.tech_list)
        if not tech_list_path.exists():
            print(f"ERROR: tech list not found: {tech_list_path}", file=sys.stderr)
            return 2
        with open(tech_list_path) as f:
            reader = csv_mod.DictReader(f)
            technologies = sorted(set(row["tech"] for row in reader))
        print(f"Tech list: {len(technologies)} technologies")
        gold_standard = None
    else:
        # Gold standard mode: original behavior
        gs_path = Path(args.goldstandard)
        if not gs_path.exists():
            print(f"ERROR: gold standard not found: {gs_path}", file=sys.stderr)
            return 2
        raw_gold = load_goldstandard(gs_path)
        technologies = sorted(raw_gold.keys())
        print(f"Gold standard: {len(technologies)} technologies")

        vocab = load_canonical_vocab(Path(args.global_vocab))
        gold_standard = await normalize_goldstandard_components(
            raw_gold, vocab, args.normalization_model, args.retries
        )
        print(f"Normalized gold standard: {sum(len(v) for v in gold_standard.values())} components")
```

- [ ] **Step 3: Guard gold standard usage throughout the script**

In step 4 (judging raw components, ~line 444), change:

```python
        for comp in raw_unions[tech] | gold_standard.get(tech, set()):
```

to:

```python
        gs_comps = gold_standard.get(tech, set()) if gold_standard else set()
        for comp in raw_unions[tech] | gs_comps:
```

Apply the same pattern at ~line 545 (judging normalized components):

```python
        gs_comps = gold_standard.get(tech, set()) if gold_standard else set()
        for comp in norm_unions[tech] | gs_comps:
```

- [ ] **Step 4: Guard metrics computation**

In step 5 (raw metrics, ~line 477-490), wrap the gold standard metrics:

```python
    raw_metrics: List[ValidationMetrics] = []
    for tech in technologies:
        gs_comps = gold_standard.get(tech, set()) if gold_standard else set()
        naive_comps = raw_unions[tech]
        if gold_standard:
            m = compute_metrics(tech, gs_comps, naive_comps, cache)
            raw_metrics.append(m)

        run_sizes = [len(s) for s in raw_run_sets[tech]]
        raw_tech_results[tech] = {
            "union_size": len(naive_comps),
            "mean_per_run": mean(run_sizes) if run_sizes else 0,
            "min_per_run": min(run_sizes) if run_sizes else 0,
            "max_per_run": max(run_sizes) if run_sizes else 0,
            "jaccard": pairwise_jaccard(raw_run_sets[tech]),
        }
```

Apply the same to step 9 (normalized metrics, ~line 576-590).

- [ ] **Step 5: Guard report writing**

In `write_report`, the gold standard table should only be written when `metrics_list` is non-empty. Add a condition around the "Judge Validation Against Gold Standard" section:

```python
    if metrics_list:
        parts.append("\n## Judge Validation Against Gold Standard\n\n")
        # ... existing table code ...
```

Also add a plausibility summary section that always runs (tech-list mode doesn't have gold standard but still has judge verdicts). After the extraction summary, add:

```python
    # Judge plausibility summary (always available)
    parts.append("\n## Judge Plausibility Summary\n\n")
    parts.append("| Technology | Components | Plausible | Not Plausible | Invalid Rate |\n")
    parts.append("| --- | --- | --- | --- | --- |\n")
    for tech in sorted(tech_results.keys()):
        total = tech_results[tech]["union_size"]
        # Count plausible from cache (caller should pass cache or compute inline)
        parts.append(f"| {tech} | {total} | — | — | — |\n")
```

Actually, this is getting complex. Simpler approach: pass `metrics_list=[]` when no gold standard, and the existing report function already handles an empty list (writes an empty table). The extraction summary and stability are always written. This is sufficient for the ablation — the judge plausibility data comes from the separate `micro_stage1_judge.md` report.

- [ ] **Step 6: Guard the summary comparison at the end**

In the summary print block (~lines 609-628), wrap the gold standard metrics:

```python
    if gold_standard:
        for label, mlist in [("Raw", raw_metrics), ("Normalized", norm_metrics)]:
            tp = sum(m.true_positive for m in mlist)
            # ... rest of aggregation ...
```

- [ ] **Step 7: Test the change**

```bash
# Test with gold standard (original behavior)
uv run python scripts/naive_component_baseline.py --runs 1 --goldstandard data/goldstndrd.csv --analysis-dir /tmp/test_naive 2>&1 | tail -10

# Test with tech list (new behavior) — use a small list
echo "domain,tech,role" > /tmp/test_techs.csv
echo "Test,Smartphone,an expert" >> /tmp/test_techs.csv
echo "Test,Laptop PC,an expert" >> /tmp/test_techs.csv
uv run python scripts/naive_component_baseline.py --tech-list /tmp/test_techs.csv --runs 1 --analysis-dir /tmp/test_naive_techlist 2>&1 | tail -10
```

Both should complete without errors.

- [ ] **Step 8: Commit**

```bash
git add scripts/naive_component_baseline.py
git commit -m "feat: add --tech-list to naive baseline for arbitrary tech sets"
```

---

### Task 2: Run naive baseline on 61 microelectronics techs

**Files:**
- Output: `output/naive_micro/naive_components_*.json` (61 x 5 = 305 files)
- Output: `output/analysis/naive_baseline_micro_raw.md`
- Output: `output/analysis/naive_baseline_micro_normalized.md`

- [ ] **Step 1: Run naive baseline**

```bash
uv run python scripts/naive_component_baseline.py \
  --tech-list data/tech_list_microelectronic_products.csv \
  --extraction-model openai:gpt-4.1-mini \
  --runs 5 \
  --naive-vocab data/component_canonical_vocab_global_primary.json \
  --output-dir output/naive_micro \
  --analysis-dir output/analysis \
  --cache-jsonl output/analysis/stage1_component_judge_cache.jsonl
```

This takes a while (305 extractions + judging + normalization). Run with:

```bash
nohup uv run python scripts/naive_component_baseline.py \
  --tech-list data/tech_list_microelectronic_products.csv \
  --extraction-model openai:gpt-4.1-mini \
  --runs 5 \
  --naive-vocab data/component_canonical_vocab_global_primary.json \
  --output-dir output/naive_micro \
  --analysis-dir output/analysis \
  --cache-jsonl output/analysis/stage1_component_judge_cache.jsonl \
  > logs/naive_micro.log 2>&1 &
```

- [ ] **Step 2: Verify outputs**

```bash
ls output/naive_micro/*.json | wc -l   # expect 305
cat output/analysis/naive_baseline_micro_raw.md | head -30
cat output/analysis/naive_baseline_micro_normalized.md | head -30
```

---

### Task 3: Run judge on raw v1v1v1 files

**Files:**
- Output: `output/analysis/ablation_raw_v1v1v1_judge.md`
- Output: `output/analysis/ablation_raw_v1v1v1_judge.jsonl`

- [ ] **Step 1: Run judge on raw files**

The judge script reads CSVs with `technology` and `component` columns. Raw pipeline CSVs have the same schema as normalized ones.

```bash
uv run python scripts/judge_stage1_components_from_normalized_outputs.py \
  --normalized-dir output/raw/ \
  --configs v1v1v1 \
  --judge-model openai:gpt-4.1 \
  --cache output/analysis/stage1_component_judge_cache.jsonl \
  --out-md output/analysis/ablation_raw_v1v1v1_judge.md \
  --out-jsonl output/analysis/ablation_raw_v1v1v1_judge.jsonl
```

Many components will already be in the judge cache from earlier runs.

- [ ] **Step 2: Run stability on raw v1v1v1 files**

```bash
uv run python scripts/analyze_stage1_component_stability_normalized.py \
  --normalized-dir output/raw/ \
  --include-config v1v1v1 \
  --min-runs 2 \
  --out-md output/analysis/ablation_raw_v1v1v1_stability.md \
  --out-json output/analysis/ablation_raw_v1v1v1_stability.json
```

- [ ] **Step 3: Verify outputs**

```bash
head -25 output/analysis/ablation_raw_v1v1v1_judge.md
head -25 output/analysis/ablation_raw_v1v1v1_stability.md
```

---

### Task 4: Build ablation comparison script

**Files:**
- Create: `scripts/ablation_comparison.py`

A script that reads the results from all 5 layers and produces a single comparison table.

- [ ] **Step 1: Create the script**

```python
#!/usr/bin/env python3
"""
Ablation comparison: contribution of each pipeline layer.

Reads stability and judge results from the analysis outputs and
produces a single comparison table.

Usage:
    uv run python scripts/ablation_comparison.py
    uv run python scripts/ablation_comparison.py --out-md output/analysis/ablation_comparison.md
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean, median


def load_stability_json(path: Path) -> dict:
    """Load stability JSON and return {config: {tech: median_jaccard}}."""
    with open(path) as f:
        data = json.load(f)
    return data


def extract_macro_median_stability(stability_json: dict) -> float:
    """Extract macro-median Jaccard from stability JSON."""
    # The JSON has per_config -> [{tech, median_jaccard, ...}]
    tech_medians = []
    for config_data in stability_json.get("per_config", {}).values():
        for entry in config_data:
            tech_medians.append(entry.get("median_jaccard", 0.0))
    return median(tech_medians) if tech_medians else 0.0


def extract_judge_invalid_rate(judge_md_path: Path) -> tuple:
    """Parse the judge markdown report to extract median invalid rates.

    Returns (occ_median, dedup_median) from the per-configuration summary table.
    """
    if not judge_md_path.exists():
        return (None, None)

    text = judge_md_path.read_text()
    # Look for the per-configuration variability summary table
    # Format: | config | runs_entries | invalid_rate_median | ...
    occ_median = None
    for line in text.splitlines():
        if line.startswith("| v1v1v1") or line.startswith("| d3v1v1"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                try:
                    occ_median = float(parts[3])
                except (ValueError, IndexError):
                    pass
    return (occ_median, None)


def extract_naive_stability(naive_md_path: Path) -> float:
    """Parse naive baseline markdown to extract aggregate stability."""
    if not naive_md_path.exists():
        return 0.0

    text = naive_md_path.read_text()
    jaccards = []
    in_table = False
    for line in text.splitlines():
        if "Stability (Jaccard)" in line:
            in_table = True
            continue
        if in_table and line.startswith("| ---"):
            continue
        if in_table and line.startswith("|"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 7:
                try:
                    jaccards.append(float(parts[6]))
                except (ValueError, IndexError):
                    pass
        elif in_table and not line.startswith("|"):
            in_table = False

    return median(jaccards) if jaccards else 0.0


def extract_component_count(naive_md_path: Path) -> float:
    """Parse naive baseline markdown to extract median component count."""
    if not naive_md_path.exists():
        return 0.0

    text = naive_md_path.read_text()
    counts = []
    in_table = False
    for line in text.splitlines():
        if "| Technology | Union |" in line:
            in_table = True
            continue
        if in_table and line.startswith("| ---"):
            continue
        if in_table and line.startswith("|"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                try:
                    counts.append(float(parts[2]))
                except (ValueError, IndexError):
                    pass
        elif in_table and not line.startswith("|"):
            in_table = False

    return median(counts) if counts else 0.0


def main():
    p = argparse.ArgumentParser(description="Ablation comparison table.")
    p.add_argument("--out-md", default="output/analysis/ablation_comparison.md")
    p.add_argument("--sweet-spot-csv", default="output/analysis/micro_sweet_spot_by_n.csv",
                   help="Sweet-spot by-N CSV for structured layers.")
    p.add_argument("--naive-raw-md", default="output/analysis/naive_baseline_micro_raw.md")
    p.add_argument("--naive-norm-md", default="output/analysis/naive_baseline_micro_normalized.md")
    p.add_argument("--raw-stability-json", default="output/analysis/ablation_raw_v1v1v1_stability.json")
    p.add_argument("--raw-judge-md", default="output/analysis/ablation_raw_v1v1v1_judge.md")
    p.add_argument("--norm-judge-md", default="output/analysis/micro_stage1_judge.md")
    args = p.parse_args()

    # Layer 1: Naive raw
    naive_raw_stability = extract_naive_stability(Path(args.naive_raw_md))
    naive_raw_components = extract_component_count(Path(args.naive_raw_md))

    # Layer 2: Naive normalized
    naive_norm_stability = extract_naive_stability(Path(args.naive_norm_md))
    naive_norm_components = extract_component_count(Path(args.naive_norm_md))

    # Layer 3: Structured raw (v1v1v1 un-normalized)
    raw_stability_path = Path(args.raw_stability_json)
    if raw_stability_path.exists():
        raw_stab_data = load_stability_json(raw_stability_path)
        structured_raw_stability = extract_macro_median_stability(raw_stab_data)
    else:
        structured_raw_stability = 0.0

    # Layers 4-5: from sweet-spot CSV
    sweet_spot_path = Path(args.sweet_spot_csv)
    structured_norm_stability = 0.0
    structured_norm_invalid = 0.0
    debate_stability = 0.0
    debate_invalid = 0.0
    structured_norm_components = 0.0
    debate_components = 0.0

    if sweet_spot_path.exists():
        with open(sweet_spot_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                n = int(row.get("N", 0))
                if n == 1:
                    structured_norm_stability = float(row.get("stability_median", 0))
                    structured_norm_invalid = float(row.get("not_plausible_occ_median", 0))
                    structured_norm_components = float(row.get("components_median", 0))
                elif n == 3:
                    debate_stability = float(row.get("stability_median", 0))
                    debate_invalid = float(row.get("not_plausible_occ_median", 0))
                    debate_components = float(row.get("components_median", 0))

    # Raw v1v1v1 judge
    raw_judge_invalid = extract_judge_invalid_rate(Path(args.raw_judge_md))[0]

    # Build table
    out_path = Path(args.out_md)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Ablation: contribution of each pipeline layer\n\n",
        f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        f"- **Technologies**: 61 (microelectronics)\n",
        f"- **Runs per layer**: 5\n\n",
        "## Comparison\n\n",
        "| Layer | Stability (median Jaccard) | Invalid rate occ (median) | Components (median) |\n",
        "| --- | --- | --- | --- |\n",
        f"| 1. Naive raw | {naive_raw_stability:.3f} | — | {naive_raw_components:.1f} |\n",
        f"| 2. Naive + normalization | {naive_norm_stability:.3f} | — | {naive_norm_components:.1f} |\n",
        f"| 3. Structured raw (v1v1v1) | {structured_raw_stability:.3f} | {raw_judge_invalid:.3f} | — |\n",
        f"| 4. Structured + normalization (v1v1v1) | {structured_norm_stability:.3f} | {structured_norm_invalid:.3f} | {structured_norm_components:.1f} |\n",
        f"| 5. Structured + norm + debate (d3v1v1) | {debate_stability:.3f} | {debate_invalid:.3f} | {debate_components:.1f} |\n",
        "\n## Interpretation\n\n",
        "Each row adds one layer on top of the previous:\n",
        "- Row 1 → 2: effect of **normalization alone** on naive output\n",
        "- Row 2 → 4: effect of **structured extraction** (role conditioning, ontology, exclusion rules)\n",
        "- Row 1 → 3: effect of **structured extraction without normalization**\n",
        "- Row 3 → 4: effect of **normalization on structured output**\n",
        "- Row 4 → 5: effect of **multi-agent debate**\n",
    ]

    out_path.write_text("".join(lines))
    print(f"Wrote: {out_path}")
    print("\n" + "".join(lines))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/ablation_comparison.py
git commit -m "feat: add ablation comparison script for pipeline layer analysis"
```

---

### Task 5: Run the full ablation and produce results

This task depends on Tasks 2 and 3 completing (the long-running extraction and judge runs).

- [ ] **Step 1: Run the ablation comparison**

```bash
uv run python scripts/ablation_comparison.py \
  --out-md output/analysis/ablation_comparison.md
```

- [ ] **Step 2: Review the comparison table**

```bash
cat output/analysis/ablation_comparison.md
```

- [ ] **Step 3: Commit all ablation results**

```bash
git add -f output/analysis/ablation_*.md output/analysis/ablation_*.json output/analysis/ablation_*.jsonl
git add -f output/analysis/naive_baseline_micro_*.md
git add scripts/ablation_comparison.py
git commit -m "data: ablation study results - contribution of each pipeline layer"
```
