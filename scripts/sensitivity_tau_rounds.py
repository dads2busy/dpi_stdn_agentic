#!/usr/bin/env python3
"""Convergence-threshold (tau) and round-cap (R) sensitivity of component stability (Reviewer 1.5).

Metric: per-technology median pairwise Jaccard of canonical component sets across runs, the
same metric as cross_domain_stability_analysis.py. Component sets come from debate transcripts,
mapped through the canonical vocabulary, so every scenario is measured the same way.

Block A (submitted microelectronics d3v1v1, 60 techs x 5 runs, April 2026): each run's debate is
replayed with the pipeline's own consensus rule (MultiAgentDebater.build_adaptive_consensus_semantic)
on the proposals of the round where a lower tau or a lower round cap would have stopped it.
Tau above 0.7 cannot be replayed (those rounds were never run), so it comes from Block B.

Block B (24-tech subset reruns, October 2026): recorded final consensus of the tau=0.85, tau=0.95
and tau=0.95/R=5 reruns, against the same-session r5 run (tau=0.7, R=5) as control; r5 never went
past round 3, so it is effectively tau=0.7, R=3.

Usage: uv run python -m scripts.sensitivity_tau_rounds > output/analysis/sensitivity_tau_rounds.md
"""
import argparse
import asyncio
import csv
import glob
import json
import shutil
from collections import defaultdict
from itertools import combinations
from statistics import median

from scripts.normalize_outputs_global_granularity import _norm_key
from stdn_agentic.debate.component_debater import MultiAgentDebater

REVISION_VOCAB = "data/component_canonical_vocab_global_primary_revision.json"
# Revision vocab plus LLM mappings for replayed early-round names (built by --extend-vocab).
VOCAB = "data/component_canonical_vocab_sensitivity.json"
NON_PRIMARY = "__NON_PRIMARY__"
APRIL_RUNS = ("20260414_140920", "20260414_140932", "20260414_140945", "20260414_140958", "20260414_141010")
V1_PATTERN = "output/normalized/stdns_output_v1v1v1_2026041*.csv"
SUBSET = "data/tech_list_tau_subset.csv"
MICRO_LIST = "data/tech_list_microelectronic_products.csv"

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
    """Consensus the pipeline would have produced had the debate ended after round r (1-based)."""
    rd = t["component_stage"]["phase2_debate_rounds"][r - 1]
    props = [{**c, "agent_id": agent} for agent, comps in rd["proposals"].items() for c in comps]
    _, details = _DEBATER.build_adaptive_consensus_semantic(props, rd["convergence"])
    return [name for name, d in details.items() if d.get("confidence", 0.0) > 0.0]


def canonical_set(names, vocab):
    """Map names through the vocab; drop non-primary; keep unknown names verbatim and count them."""
    out, unmapped = set(), 0
    for n in names:
        v = vocab.get(_norm_key(n))
        if v is None:
            out.add(n)
            unmapped += 1
        elif v != NON_PRIMARY:
            out.add(v)
    return out, unmapped


def unmapped_names_by_tech(picked, vocab):
    """picked: [(technology, names)]. Names absent from vocab, one representative per vocab key."""
    out, seen = defaultdict(list), set()
    for tech, names in picked:
        for n in names:
            k = _norm_key(n)
            if k in vocab or (tech, k) in seen:
                continue
            seen.add((tech, k))
            out[tech].append(n.strip())
    return dict(out)


async def _llm_map(by_tech, vocab, model="openai:gpt-4.1", chunk_size=120):
    """Map unseen names the way the submitted normalization did (per technology, gpt-4.1, chunks of 120)."""
    from scripts.normalize_outputs_global_granularity import chunked, llm_normalize_chunk

    canon = sorted(set(vocab.values()) - {NON_PRIMARY})
    added = {}
    for tech, names in sorted(by_tech.items()):
        for chunk in chunked(names, chunk_size):
            m = await llm_normalize_chunk(names=chunk, model=model, non_primary_sentinel=NON_PRIMARY,
                                          existing_canonicals=canon, retries=3, technology=tech)
            for raw, canonical in m.items():
                added[_norm_key(raw)] = canonical
    return added


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a | b) else 1.0


def per_tech_median_jaccard(sets_by_tech):
    return {t: median(jaccard(a, b) for a, b in combinations(s, 2)) for t, s in sets_by_tech.items() if len(s) >= 2}


def _tech_names(path):
    rows = list(csv.DictReader(open(path)))
    key = [c for c in rows[0] if "tech" in c.lower()][0]
    return [r[key] for r in rows]


def _v1_medians():
    runs = []
    for f in sorted(glob.glob(V1_PATTERN)):
        run = defaultdict(set)
        for row in csv.DictReader(open(f)):
            if row.get("technology") and row.get("component"):
                run[row["technology"]].add(row["component"])
        runs.append(run)
    techs = {t for r in runs for t in r}
    return per_tech_median_jaccard({t: [r[t] for r in runs if t in r] for t in techs})


def _load(pattern, keep=None):
    out = []
    for f in sorted(glob.glob(pattern)):
        if keep and not any(k in f for k in keep):
            continue
        out.append(json.load(open(f)))
    return out


def _scenario_sets(transcripts, vocab, pick):
    """pick(transcript) -> component names, or None to skip. Returns tech -> [set per run], unmapped, n."""
    sets, unmapped, n, rounds_used = defaultdict(list), 0, 0, []
    for t in transcripts:
        picked = pick(t)
        if picked is None:
            continue
        names, r_used = picked
        s, u = canonical_set(names, vocab)
        sets[t["component_stage"]["phase3_final_consensus"]["technology"]].append(s)
        unmapped += u
        n += 1
        rounds_used.append(r_used)
    return sets, unmapped, n, rounds_used


def _recorded(t):
    rds = t["component_stage"]["phase2_debate_rounds"]
    return t["component_stage"]["phase3_final_consensus"]["components"], len(rds)


def _replay(tau, cap):
    def pick(t):
        rds = t["component_stage"]["phase2_debate_rounds"]
        if not rds:
            return None
        r = stop_round(rds, tau, cap)
        return consensus_at_round(t, r), r
    return pick


def _scenarios_a():
    return [
        ("Recorded final (tau=0.7, R=3, as submitted)", _recorded),
        ("Replay at actual stop (tau=0.7, R=3)", _replay(0.7, 3)),
        ("Replay R=1 (stop after round 1)", _replay(0.7, 1)),
        ("Replay R=2", _replay(0.7, 2)),
        ("Replay tau=0.6", _replay(0.6, 3)),
        ("Replay tau=0.5", _replay(0.5, 3)),
    ]


def _row(label, med, ref, base=None, rounds=None, unmapped=0, n=0):
    techs = sorted(set(med) & set(ref))
    m = median(med[t] for t in techs)
    d_ref = m - median(ref[t] for t in techs)
    worse = sum(med[t] < ref[t] for t in techs)
    better = sum(med[t] > ref[t] for t in techs)
    cells = [label, str(len(techs)), f"{m:.3f}", f"{d_ref:+.3f}", f"{better}/{worse}/{len(techs) - better - worse}"]
    if base is not None:
        bt = sorted(set(med) & set(base))
        cells.append(f"{median(med[t] - base[t] for t in bt):+.3f}")
    cells += [f"{sum(rounds) / len(rounds):.2f}" if rounds else "", f"{unmapped}/{n}"]
    return "| " + " | ".join(cells) + " |"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extend-vocab", action="store_true",
                    help=f"map unmapped replay names with the LLM and write {VOCAB} (revision vocab + additions)")
    a = ap.parse_args()

    april = _load("output/transcripts/*_d3v1v1_20260414_14*.json", keep=APRIL_RUNS)
    if a.extend_vocab:
        base = json.load(open(REVISION_VOCAB))
        picked = []
        for _, pick in _scenarios_a()[2:]:
            for t in april:
                got = pick(t)
                if got is not None:
                    picked.append((t["component_stage"]["phase3_final_consensus"]["technology"], got[0]))
        by_tech = unmapped_names_by_tech(picked, base["mappings"])
        added = asyncio.run(_llm_map(by_tech, base["mappings"]))
        shutil.copyfile(REVISION_VOCAB, VOCAB)
        out = json.load(open(VOCAB))
        out["mappings"] = {**out["mappings"], **{k: v for k, v in added.items() if k not in out["mappings"]}}
        json.dump(out, open(VOCAB, "w"), indent=2, sort_keys=True)
        print(f"added {len(added)} mappings for {sum(map(len, by_tech.values()))} names over {len(by_tech)} techs -> {VOCAB}")
        return

    vocab = json.load(open(VOCAB))["mappings"]
    v1 = _v1_medians()
    scen_a = _scenarios_a()
    res_a = {}
    for label, pick in scen_a:
        sets, u, n, rounds = _scenario_sets(april, vocab, pick)
        res_a[label] = (per_tech_median_jaccard(sets), u, n, rounds)
    base_a = res_a["Replay at actual stop (tau=0.7, R=3)"][0]

    print("# Convergence threshold (tau) and round cap (R) sensitivity\n")
    print("Metric: per-technology median pairwise Jaccard of canonical component sets across runs "
          "(the submitted stability metric), median over technologies. Component sets are taken from debate "
          f"transcripts and mapped through `{VOCAB}`. *Better/worse/tied* counts technologies against the "
          "single-agent v1v1v1 baseline. *Rounds* is the mean number of debate rounds used. *Unmapped* counts "
          "component names not in the vocabulary (kept verbatim).\n\n"
          f"`{VOCAB}` is the revision vocabulary plus LLM mappings for names that appear only in replayed early "
          "rounds (built with `--extend-vocab`, using the submitted normalization's model, prompt and technology "
          "context). Without it those names stay unnormalized and early-stop stability is understated: the "
          "stop-after-round-1 median falls from 0.288 to 0.144 with 1,797 unmapped names.\n")
    print("## A. Submitted microelectronics runs (d3v1v1, 60 technologies, 5 runs), replayed\n")
    print("Replays apply the pipeline's consensus rule to the proposals of the round where the debate would "
          "have stopped. The replay at the actual stop reproduces the recorded final consensus exactly for most "
          "runs; the rest differ by the post-debate LLM normalization pass, so replayed scenarios are compared "
          "against the replay at the actual stop (Δ vs replay).\n")
    print("| scenario | techs | median Jaccard | Δ vs v1 | better/worse/tied vs v1 | Δ vs replay (median of per-tech diffs) | rounds | unmapped |")
    print("|---|---|---|---|---|---|---|---|")
    for label, _ in scen_a:
        med, u, n, rounds = res_a[label]
        print(_row(label, med, v1, base_a, rounds, u, n))
    print(f"\nv1v1v1 baseline median over the same technologies: {median(v1[t] for t in base_a if t in v1):.3f}\n")

    subset = _tech_names(SUBSET)
    micro = set(_tech_names(MICRO_LIST))
    sub_micro = [t for t in subset if t in micro]
    res_b = {}
    for tag in ["r5", "tau085", "tau095", "tau095r5"]:
        sets, u, n, rounds = _scenario_sets(_load(f"output/transcripts/*_{tag}_d3v1v1_*.json"), vocab, _recorded)
        res_b[tag] = (per_tech_median_jaccard(sets), u, n, rounds)
    ctrl = res_b["r5"][0]
    april_sub = {t: v for t, v in res_a["Recorded final (tau=0.7, R=3, as submitted)"][0].items() if t in sub_micro}

    print(f"## B. Reruns on the {len(subset)}-technology subset (October 2026)\n")
    print("Control is the same-session r5 run (tau=0.7, R=5); no r5 debate went past round 3, so it is "
          "effectively tau=0.7, R=3 and isolates tau from drift since the April runs. "
          "*Better/worse/tied* and Δ are against the control.\n")
    print("| scenario | techs | median Jaccard | Δ vs control | better/worse/tied vs control | rounds | unmapped |")
    print("|---|---|---|---|---|---|---|")
    labels = {"r5": "Control: tau=0.7, R=5 (r5)", "tau085": "tau=0.85, R=3", "tau095": "tau=0.95, R=3",
              "tau095r5": "tau=0.95, R=5"}
    for tag, label in labels.items():
        med, u, n, rounds = res_b[tag]
        print(_row(label, med, ctrl, None, rounds, u, n))

    print(f"\n### Microelectronics techs in the subset ({len(sub_micro)}), against v1 and the April runs\n")
    print("| scenario | techs | median Jaccard | Δ vs v1 | better/worse/tied vs v1 | rounds | unmapped |")
    print("|---|---|---|---|---|---|---|")
    print(_row("April submitted (tau=0.7, R=3)", april_sub, v1))
    for tag, label in labels.items():
        med = {t: v for t, v in res_b[tag][0].items() if t in sub_micro}
        print(_row(label, med, v1))


if __name__ == "__main__":
    main()
