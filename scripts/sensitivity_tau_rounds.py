#!/usr/bin/env python3
"""Convergence-threshold (tau) and round-cap (R) sensitivity of component stability (Reviewer 1.5).

Metric: per-technology median pairwise Jaccard of canonical component sets across runs, the same
metric as cross_domain_stability_analysis.py. Component sets come from debate transcripts (recorded
final consensus), mapped through the revision vocabulary.

A. Method check on the submitted microelectronics d3v1v1 runs (60 techs x 5, April 2026): the recorded
   final consensus through the vocabulary reproduces the submitted median, and replaying the pipeline's
   consensus rule (MultiAgentDebater.build_adaptive_consensus_semantic) on the last round reproduces
   every recorded consensus. Early stops are not replayed: names in rounds the pipeline did not finish
   never went through its final LLM normalization, so their stability depends on how they are
   normalized after the fact (0.29-0.48 for stop-after-round-1 across choices tried).

B. Reruns on the 24-technology subset with the round-1 agent_id fix (f948c3e), all in one session:
   tau=0.7/R=3 control, tau=0.85, tau=0.95, R=1, R=2.

Usage: uv run --with scipy python -m scripts.sensitivity_tau_rounds > output/analysis/sensitivity_tau_rounds.md
"""
import csv
import glob
import json
from collections import defaultdict
from itertools import combinations
from statistics import median

from scripts.normalize_outputs_global_granularity import _norm_key, _norm_tech
from stdn_agentic.debate.component_debater import MultiAgentDebater

VOCAB = "data/component_canonical_vocab_global_primary_revision.json"
NON_PRIMARY = "__NON_PRIMARY__"
APRIL_RUNS = ("20260414_140920", "20260414_140932", "20260414_140945", "20260414_140958", "20260414_141010")
V1_APRIL = "output/normalized/stdns_output_v1v1v1_2026041*.csv"
V1_FIX = "output/normalized/stdns_output_fxmicro_v1v1v1_*.csv"
SUBSET = "data/tech_list_tau_subset.csv"
MICRO_LIST = "data/tech_list_microelectronic_products.csv"
RERUNS = {
    "fxctl": "Control: tau=0.7, R=3",
    "fxtau085": "tau=0.85, R=3",
    "fxtau095": "tau=0.95, R=3",
    "fxr2": "tau=0.7, R=2",
    "fxr1": "tau=0.7, R=1",
}

# Constructed as the pipeline does (orchestrator/pipeline.py, MultiAgentDebater(...)).
_DEBATER = MultiAgentDebater(max_rounds=3, convergence_threshold=0.7, confidence_weight=0.3, peer_support_boost=0.15)


def stop_round_for_tau(rounds, tau):
    for i, r in enumerate(rounds, 1):
        if r["convergence"] >= tau:
            return i
    return len(rounds)


def stop_round(rounds, tau, cap):
    return min(stop_round_for_tau(rounds, tau), cap, len(rounds))


def consensus_at_round(t, r):
    """Consensus the pipeline produces from round r's proposals (1-based)."""
    rd = t["component_stage"]["phase2_debate_rounds"][r - 1]
    # Before f948c3e, round-1 proposals carried no agent_id, so a debate that stopped after round 1 pooled
    # them under one agent (min support 1). Later rounds carry agent ids.
    props = [({**c, "agent_id": agent} if r > 1 else dict(c)) for agent, comps in rd["proposals"].items() for c in comps]
    _, details = _DEBATER.build_adaptive_consensus_semantic(props, rd["convergence"])
    return [name for name, d in details.items() if d.get("confidence", 0.0) > 0.0]


def _lookup(vocab, name, tech=None):
    k = _norm_key(name)
    if tech is not None:
        v = vocab.get(f"{_norm_tech(tech)}|||{k}")
        if v is not None:
            return v
    return vocab.get(k)


def canonical_set(names, vocab, tech=None):
    """Map names through the vocab (technology-scoped entry first); drop non-primary; keep unknown names
    verbatim and count them."""
    out, unmapped = set(), 0
    for n in names:
        v = _lookup(vocab, n, tech)
        if v is None:
            out.add(n)
            unmapped += 1
        elif v != NON_PRIMARY:
            out.add(v)
    return out, unmapped


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a | b) else 1.0


def per_tech_median_jaccard(sets_by_tech):
    return {t: median(jaccard(a, b) for a, b in combinations(s, 2)) for t, s in sets_by_tech.items() if len(s) >= 2}


def _tech_names(path):
    rows = list(csv.DictReader(open(path)))
    key = [c for c in rows[0] if "tech" in c.lower()][0]
    return [r[key] for r in rows]


def _v1_medians(pattern):
    runs = []
    for f in sorted(glob.glob(pattern)):
        run = defaultdict(set)
        for row in csv.DictReader(open(f)):
            if row.get("technology") and row.get("component"):
                run[row["technology"]].add(row["component"])
        runs.append(run)
    techs = {t for r in runs for t in r}
    return per_tech_median_jaccard({t: [r[t] for r in runs if t in r] for t in techs})


def _load(pattern, keep=None):
    return [json.load(open(f)) for f in sorted(glob.glob(pattern)) if not keep or any(k in f for k in keep)]


def _sets(transcripts, vocab, pick):
    """pick(transcript) -> component names. Returns per-tech medians, unmapped count, runs, rounds used."""
    sets, unmapped, rounds = defaultdict(list), 0, []
    for t in transcripts:
        tech = t["component_stage"]["phase3_final_consensus"]["technology"]
        s, u = canonical_set(pick(t), vocab, tech)
        sets[tech].append(s)
        unmapped += u
        rounds.append(len(t["component_stage"]["phase2_debate_rounds"]))
    return per_tech_median_jaccard(sets), unmapped, len(transcripts), rounds


def _recorded(t):
    return t["component_stage"]["phase3_final_consensus"]["components"]


def _replay_last(t):
    rds = t["component_stage"]["phase2_debate_rounds"]
    return consensus_at_round(t, len(rds)) if rds else []


def paired_p(med, ref):
    """Two-sided paired Wilcoxon p over shared technologies (zero differences dropped); None if all tie."""
    from scipy import stats

    diffs = [med[t] - ref[t] for t in sorted(set(med) & set(ref))]
    if not any(abs(d) > 1e-12 for d in diffs):
        return None
    return float(stats.wilcoxon(diffs, zero_method="wilcox", alternative="two-sided").pvalue)


def _row(label, med, ref, rounds=None, unmapped=0, n=0):
    techs = sorted(set(med) & set(ref))
    m = median(med[t] for t in techs)
    d_ref = m - median(ref[t] for t in techs)
    d_pair = median(med[t] - ref[t] for t in techs)
    worse = sum(med[t] < ref[t] for t in techs)
    better = sum(med[t] > ref[t] for t in techs)
    cells = [label, str(len(techs)), f"{m:.3f}", f"{d_ref:+.3f}", f"{d_pair:+.3f}",
             f"{better}/{worse}/{len(techs) - better - worse}",
             "" if (p := paired_p(med, ref)) is None else f"{p:.3g}",
             f"{sum(rounds) / len(rounds):.2f}" if rounds else "", f"{unmapped}/{n}" if n else ""]
    return "| " + " | ".join(cells) + " |"


HEADER = ("| scenario | techs | median Jaccard | Δ median | median per-tech Δ | better/worse/tied | Wilcoxon p | rounds | unmapped |\n"
          "|---|---|---|---|---|---|---|---|---|")


def main():
    vocab = json.load(open(VOCAB))["mappings"]

    print("# Convergence threshold (tau) and round cap (R) sensitivity\n")
    print("Metric: per-technology median pairwise Jaccard of canonical component sets across runs (the "
          "submitted stability metric), median over technologies. Component sets are each run's recorded final "
          f"consensus from the debate transcripts, mapped through `{VOCAB}`. *Δ median* is the difference of "
          "medians; *median per-tech Δ* is the median of per-technology differences; *better/worse/tied* counts "
          "technologies against the reference named in each table, and *Wilcoxon p* is the two-sided paired "
          "Wilcoxon test against it. *Rounds* is the mean number of debate rounds "
          "used; *unmapped* counts component names not in the vocabulary (kept verbatim).\n")

    april = _load("output/transcripts/*_d3v1v1_20260414_14*.json", keep=APRIL_RUNS)
    v1_april = _v1_medians(V1_APRIL)
    rec = _sets(april, vocab, _recorded)
    rep = _sets(april, vocab, _replay_last)
    exact = sum(set(_recorded(t)) == set(_replay_last(t)) for t in april)
    one_round = sum(len(t["component_stage"]["phase2_debate_rounds"]) == 1 for t in april)
    print("## A. Method check: submitted microelectronics runs (d3v1v1, 60 technologies, 5 runs)\n")
    print(f"Replaying the pipeline's consensus rule on each debate's last round reproduces the recorded final "
          f"consensus for {exact} of {len(april)} runs. {one_round} of these debates stopped after round 1; "
          "before the f948c3e fix their consensus needed support from one agent instead of two of three. "
          "Reference: single-agent v1v1v1 runs of the same week.\n")
    print(HEADER)
    print(_row("Recorded final (tau=0.7, R=3, as submitted)", rec[0], v1_april, rec[3], rec[1], rec[2]))
    print(_row("Replay of last round", rep[0], v1_april, rep[3], rep[1], rep[2]))
    print(f"\nv1v1v1 median: {median(v1_april.values()):.3f}. Early stops are not replayed: rounds the pipeline did "
          "not finish never went through its final LLM normalization, and the stop-after-round-1 median ranged "
          "from 0.29 to 0.48 across the after-the-fact normalizations tried. Lower round caps are measured by "
          "rerunning instead (B).\n")

    subset = _tech_names(SUBSET)
    micro = set(_tech_names(MICRO_LIST))
    sub_micro = [t for t in subset if t in micro]
    res = {tag: _sets(_load(f"output/transcripts/*_{tag}_d3v1v1_*.json"), vocab, _recorded) for tag in RERUNS}
    res = {tag: r for tag, r in res.items() if r[2]}
    if "fxctl" not in res:
        print("## B. Reruns\n\nPost-fix reruns not available yet.\n")
        return
    ctrl = res["fxctl"][0]
    print(f"## B. Reruns on the {len(subset)}-technology subset, after the fix (one session)\n")
    print("All runs use the f948c3e fix and were run back to back with the same models. Reference: the "
          "tau=0.7, R=3 control.\n")
    print(HEADER)
    for tag, label in RERUNS.items():
        if tag in res:
            med, u, n, rounds = res[tag]
            print(_row(label, med, ctrl, rounds, u, n))
    caps = {tag: max(res[tag][3]) for tag in res}
    unused = [RERUNS[t] for t in ("fxtau085", "fxtau095") if t in caps and caps[t] < 3]
    if unused:
        print(f"\nNo debate reached the R=3 cap in: {', '.join(unused)}.\n")

    v1_fix = _v1_medians(V1_FIX)
    if v1_fix:
        print(f"\n### Microelectronics techs in the subset ({len(sub_micro)}), against same-session v1v1v1\n")
        print(HEADER)
        for tag, label in RERUNS.items():
            if tag in res:
                med = {t: v for t, v in res[tag][0].items() if t in sub_micro}
                print(_row(label, med, v1_fix))
        print(f"\nv1v1v1 median over these technologies: {median(v1_fix[t] for t in sub_micro if t in v1_fix):.3f}\n")


if __name__ == "__main__":
    main()
