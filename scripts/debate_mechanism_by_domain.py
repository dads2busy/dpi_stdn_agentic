#!/usr/bin/env python3
"""Why does debate's effect on stability differ by domain? (Reviewer 1.4)

For every paired technology, relates the debate effect Δ = d3 - v1 median pairwise Jaccard (from the
paper's cross_domain_stability_analysis.py) to transcript-derived properties of its d3v1v1 debates:

  r1_agreement   round-1 inter-agent agreement (phase2_debate_rounds[0].convergence)
  rounds         rounds to termination
  r1_candidates  distinct candidates pooled across agents in round 1 (the consensus rule's own grouping)
  consolidation  1 - |final consensus| / r1_candidates (how far debate narrows the pool). Set-based
                 "fraction pruned" is not measurable: only ~20% of final names appear verbatim in round 1.
  stopped_r1     share of runs that stopped after round 1 (before the f948c3e fix these skipped the
                 multi-agent support rule)

Per technology each metric is the median over its runs (stopped_r1: the share). Reports per-domain medians,
Spearman rho with Δ (pooled and within domain, bootstrap 95% CI), and Δ by technology type
(data/tech_type_labels.csv) with Kruskal-Wallis tests.

Two datasets: the submitted runs (April/May 2026, before the fix) and the post-fix reruns (fx* tags).

Usage: uv run --with scipy --with numpy python -m scripts.debate_mechanism_by_domain > output/analysis/debate_mechanism_by_domain.md
"""
import csv
import glob
import importlib.util
import json
import os
import re
from collections import defaultdict
from statistics import mean, median

from stdn_agentic.debate.component_debater import MultiAgentDebater

PAPER_SCRIPT = os.path.expanduser("~/git/D-PI-2026-05-STDN-COMMS-SUSTAIN/scripts/cross_domain_stability_analysis.py")
TYPES = ["instrument", "consumer_product", "infrastructure", "component", "production_equipment"]
METRICS = ["r1_agreement", "rounds", "r1_candidates", "consolidation", "stopped_r1"]
DOMAIN_ORDER = ["microelectronics", "biotech", "pharma"]
LISTS = {
    "microelectronics": "data/tech_list_microelectronic_products.csv",
    "biotech": "data/tech_list_biotechnology_products.csv",
    "pharma": "data/tech_list_pharmaceutical_products.csv",
}
# Normalized-CSV patterns (v1, d3) per dataset; d3 transcripts are matched by the d3 run timestamps.
DATASETS = {
    "submitted (before fix)": {
        "microelectronics": ("output/normalized/stdns_output_v1v1v1_2026041*.csv", "output/normalized/stdns_output_d3v1v1_2026041*.csv", ""),
        "biotech": ("output/normalized/stdns_output_biotech_v1v1v1_*.csv", "output/normalized/stdns_output_biotech_d3v1v1_*.csv", ""),
        "pharma": ("output/normalized/stdns_output_pharma_v1v1v1_*.csv", "output/normalized/stdns_output_pharma_d3v1v1_*.csv", ""),
    },
    "post-fix reruns": {
        "microelectronics": ("output/normalized/stdns_output_fxmicro_v1v1v1_*.csv", "output/normalized/stdns_output_fxmicro_d3v1v1_*.csv", "fxmicro_"),
        "biotech": ("output/normalized/stdns_output_fxbiotech_v1v1v1_*.csv", "output/normalized/stdns_output_fxbiotech_d3v1v1_*.csv", "fxbiotech_"),
        "pharma": ("output/normalized/stdns_output_fxpharma_v1v1v1_*.csv", "output/normalized/stdns_output_fxpharma_d3v1v1_*.csv", "fxpharma_"),
    },
}

_DEBATER = MultiAgentDebater(max_rounds=3, convergence_threshold=0.7, confidence_weight=0.3, peer_support_boost=0.15)


def metrics_for_transcript(t):
    cs = t["component_stage"]
    rds = cs["phase2_debate_rounds"]
    r1 = rds[0]
    props = [{**c, "agent_id": a} for a, comps in r1["proposals"].items() for c in comps]
    norm_to_conf, _, _ = _DEBATER._aggregate_proposals_by_norm(props)
    n_cand = len(norm_to_conf)
    n_final = len(cs["phase3_final_consensus"]["components"])
    return {
        "r1_agreement": float(r1["convergence"]),
        "rounds": len(rds),
        "r1_candidates": n_cand,
        "consolidation": min(1.0, max(0.0, 1.0 - n_final / n_cand)) if n_cand else 0.0,
        "stopped_r1": len(rds) == 1,
    }


def _paper_module():
    spec = importlib.util.spec_from_file_location("cross_domain_stability_analysis", PAPER_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tech_names(path):
    return {r["tech"] for r in csv.DictReader(open(path))}


def per_tech_metrics(domain, d3_pattern, tag):
    """(domain, tech) -> metric medians over that technology's d3v1v1 runs."""
    runs = [re.search(r"(\d{8}_\d{6})\.csv$", f).group(1) for f in sorted(glob.glob(d3_pattern))]
    techs = _tech_names(LISTS[domain])
    by_tech = defaultdict(list)
    for ts in runs:
        for f in glob.glob(f"output/transcripts/*_{tag}d3v1v1_{ts}.json"):
            t = json.load(open(f))
            tech = t["component_stage"]["phase3_final_consensus"]["technology"]
            if tech in techs and t["component_stage"]["phase2_debate_rounds"]:
                by_tech[tech].append(metrics_for_transcript(t))
    out = {}
    for tech, ms in by_tech.items():
        row = {k: median(m[k] for m in ms) for k in METRICS if k != "stopped_r1"}
        row["stopped_r1"] = mean(m["stopped_r1"] for m in ms)
        out[(domain, tech)] = row
    return out


def _spearman_ci(x, y, rng, n_boot=10000):
    import numpy as np
    from scipy import stats

    x, y = np.asarray(x, float), np.asarray(y, float)
    rho = stats.spearmanr(x, y).statistic
    p = stats.spearmanr(x, y).pvalue
    boots = []
    for _ in range(n_boot):
        i = rng.integers(0, len(x), len(x))
        r = stats.spearmanr(x[i], y[i]).statistic
        if not np.isnan(r):
            boots.append(r)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return rho, p, lo, hi


def analyse(name, domains, paper, labels):
    import numpy as np
    from scipy import stats

    rng = np.random.default_rng(42)
    deltas = paper.paired_deltas({d: (v1, d3, LISTS[d]) for d, (v1, d3, _) in domains.items()}) if domains \
        else paper.paired_deltas()
    if not deltas:
        print(f"## {name}\n\nNo paired technologies found (runs not normalized yet).\n")
        return
    metrics = {}
    for d, (_, d3p, tag) in (domains or DATASETS["submitted (before fix)"]).items():
        metrics.update(per_tech_metrics(d, d3p, tag))
    keys = [k for k in deltas if k in metrics]

    print(f"## {name}\n")
    print(f"{len(keys)} paired technologies with transcripts "
          + ", ".join(f"{d} {sum(k[0] == d for k in keys)}" for d in DOMAIN_ORDER) + ".\n")
    print("### Per-domain medians\n")
    print("| domain | median per-tech Δ | " + " | ".join(METRICS) + " |")
    print("|---|---|" + "---|" * len(METRICS))
    for d in DOMAIN_ORDER:
        ks = [k for k in keys if k[0] == d]
        if not ks:
            continue
        cells = [f"{median(deltas[k] for k in ks):+.3f}"]
        for m in METRICS:
            v = [metrics[k][m] for k in ks]
            cells.append(f"{mean(v):.1%}" if m == "stopped_r1" else f"{median(v):.3f}")
        print(f"| {d} | " + " | ".join(cells) + " |")
    print("\n*Median per-tech Δ* is the median of per-technology differences, not the difference of domain "
          "medians reported in the paper's Table 2. *stopped_r1* is the mean share of runs per technology that "
          "stopped after round 1.\n")

    print("### Spearman correlation with Δ (rho, bootstrap 95% CI, p)\n")
    print("| metric | pooled | " + " | ".join(DOMAIN_ORDER) + " |")
    print("|---|---|" + "---|" * len(DOMAIN_ORDER))
    for m in METRICS:
        cells = []
        for ks in [keys] + [[k for k in keys if k[0] == d] for d in DOMAIN_ORDER]:
            x = [metrics[k][m] for k in ks]
            y = [deltas[k] for k in ks]
            if len(set(x)) < 2:
                cells.append("constant")
                continue
            rho, p, lo, hi = _spearman_ci(x, y, rng)
            cells.append(f"{rho:+.2f} ({lo:+.2f}, {hi:+.2f}), p={p:.3g}")
        print(f"| {m} | " + " | ".join(cells) + " |")

    print("\n### Δ by technology type (Kruskal-Wallis)\n")
    print("| type | " + " | ".join(["pooled"] + DOMAIN_ORDER) + " |")
    print("|---|" + "---|" * (1 + len(DOMAIN_ORDER)))
    for ty in TYPES:
        cells = []
        for d in [None] + DOMAIN_ORDER:
            v = [deltas[k] for k in keys if labels.get(k) == ty and (d is None or k[0] == d)]
            cells.append(f"{median(v):+.3f} (n={len(v)})" if v else "-")
        print(f"| {ty} | " + " | ".join(cells) + " |")
    cells = []
    for d in [None] + DOMAIN_ORDER:
        groups = [[deltas[k] for k in keys if labels.get(k) == ty and (d is None or k[0] == d)] for ty in TYPES]
        groups = [g for g in groups if len(g) >= 3]
        if len(groups) < 2:
            cells.append("n/a (<2 types with n>=3)")
            continue
        h = stats.kruskal(*groups)
        cells.append(f"H={h.statistic:.2f}, p={h.pvalue:.3g}, k={len(groups)}")
    print("| **Kruskal-Wallis** | " + " | ".join(cells) + " |\n")


def main():
    paper = _paper_module()
    labels = {(r["domain"], r["tech"]): r["type"] for r in csv.DictReader(open("data/tech_type_labels.csv"))}
    print("# Mechanism of the domain-dependent debate effect\n")
    print("Δ is the per-technology debate effect, d3v1v1 minus v1v1v1 median pairwise Jaccard of canonical "
          "components (`cross_domain_stability_analysis.paired_deltas`). Metrics come from the d3v1v1 debate "
          "transcripts; see the script docstring for definitions. Bootstrap: 10,000 resamples, "
          "`numpy.random.default_rng(42)`. Technology types: `data/tech_type_labels.csv`.\n")
    for name, domains in DATASETS.items():
        analyse(name, None if name.startswith("submitted") else domains, paper, labels)


if __name__ == "__main__":
    main()
