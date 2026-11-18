#!/usr/bin/env python3
"""Table 4 (judge validation against the gold standard), revision version.

The earlier procedure (validate_judge_against_goldstandard.py) mapped gold-standard items onto the pipeline's
canonical components before judging. Under per-technology normalization that collapses the 89 distinct
annotator items to ~32 (Smartphone 37 -> 7), so the gold standard is reshaped to resemble the pipeline output.
This version separates the two jobs:

  Judge recall      the judge labels each distinct annotator item AS WRITTEN (case-insensitive dedupe);
                    recall = share labelled plausible. Independent of normalization.
  Lower-bound       among pipeline canonical components (v1v1v1 + d3v1v1 runs) that the judge labels plausible,
  precision         the share that match a gold item. Gold items are mapped to canonicals with the same
                    per-technology vocab as the pipeline (lookup, then the gold-normalization LLM call with the
                    technology's canonicals) for matching only. Unmatched accepted components count as false
                    positives, so this is a lower bound (the gold standard is incomplete).

Usage (code repo):
  uv run python scripts/goldstandard_table4.py --pass a > output/analysis/goldstandard_table4_techscope_a.md
"""
import argparse
import asyncio
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).parent))
from validate_judge_against_goldstandard import (  # noqa: E402
    JudgedRecord,
    _cache_key,
    _llm_normalize_for_goldstandard,
    _norm_key,
    append_cache_jsonl,
    build_judge_prompt,
    load_cache_jsonl,
    load_canonical_vocab,
    load_pipeline_components,
    make_judge_agent,
)

SENTINEL = "__NON_PRIMARY__"
JUDGE_MODEL = "openai:gpt-4.1"


def load_gold_items(path):
    """tech -> list of distinct annotator items (first spelling kept; case-insensitive dedupe)."""
    out = defaultdict(dict)
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            t, c = r["Technology"].strip(), (r["Component"] or "").strip()
            if c:
                out[t].setdefault(c.lower(), c)
    return {t: list(d.values()) for t, d in out.items()}


async def judge_all(pairs, cache, cache_path):
    missing = [(t, c) for t, c in pairs if _cache_key(t, c) not in cache]
    if missing:
        agent = make_judge_agent(JUDGE_MODEL, retries=5)
        for t, c in missing:
            res = await agent.run(build_judge_prompt(t, c))
            rec = JudgedRecord(technology=t, component=c, plausible=bool(res.output.plausible),
                               rationale=str(res.output.rationale),
                               judged_at_utc=datetime.now(timezone.utc).isoformat(), judge_model=JUDGE_MODEL)
            append_cache_jsonl(cache_path, _cache_key(t, c), rec)
            cache[_cache_key(t, c)] = rec
    return cache


async def gold_to_canonical(gold, vocab):
    """tech -> {gold item: canonical or SENTINEL}, via the technology's vocab and canonicals."""
    out = {}
    for tech, items in gold.items():
        prefix = f"{_norm_key(tech)}|||"
        canon = sorted({v for k, v in vocab.items() if k.startswith(prefix) and v != SENTINEL})
        m, unknown = {}, []
        for it in items:
            v = vocab.get(prefix + _norm_key(it))
            (m.__setitem__(it, v) if v else unknown.append(it))
        if unknown:
            m.update(await _llm_normalize_for_goldstandard(unknown, tech, canon, "openai:gpt-4.1", 5, SENTINEL))
        out[tech] = m
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="rep", choices=["a", "b"], required=True)
    args = ap.parse_args()
    gold = load_gold_items("data/goldstndrd.csv")
    vocab = load_canonical_vocab(Path(f"data/component_canonical_vocab_techscope_{args.rep}.json"))
    pipeline = load_pipeline_components(Path(f"output/normalized_techscope_{args.rep}"), {"v1v1v1", "d3v1v1"},
                                        set(gold))

    raw_cache_path = Path("output/analysis/judge_cache_goldval_raw.jsonl")
    pipe_cache_path = Path(f"output/analysis/judge_cache_goldval_techscope_{args.rep}.jsonl")
    raw_cache = await judge_all([(t, c) for t, items in gold.items() for c in items],
                                load_cache_jsonl(raw_cache_path), raw_cache_path)
    pipe_cache = await judge_all([(t, c) for t, comps in pipeline.items() for c in comps],
                                 load_cache_jsonl(pipe_cache_path), pipe_cache_path)
    g2c = await gold_to_canonical(gold, vocab)

    print(f"# Table 4 (revision): judge validation against the gold standard, techscope pass {args.rep}\n")
    print("Judge recall: annotator items judged as written. Precision: pipeline canonicals (v1v1v1 + d3v1v1) the "
          "judge accepts that match a gold item (gold mapped with the same per-technology vocab), lower bound.\n")
    print("| Technology | Gold items | Judge recall | Pipeline components (accepted) | Matched gold | "
          "Lower-bound precision | Gold canonicals |")
    print("|---|---|---|---|---|---|---|")
    tot = defaultdict(int)
    recalls, precs = [], []
    rejected = []
    for tech in sorted(gold):
        items = gold[tech]
        acc = [c for c in items if raw_cache[_cache_key(tech, c)].plausible]
        rejected += [(tech, c) for c in items if not raw_cache[_cache_key(tech, c)].plausible]
        gold_canon = {v for v in g2c[tech].values() if v and v != SENTINEL}
        comps = pipeline.get(tech, set())
        accepted = [c for c in comps if pipe_cache[_cache_key(tech, c)].plausible]
        matched = [c for c in accepted if c in gold_canon]
        r, p = len(acc) / len(items), (len(matched) / len(accepted) if accepted else float("nan"))
        recalls.append(r)
        precs.append(p)
        for k, v in [("items", len(items)), ("acc", len(acc)), ("comps", len(comps)), ("accepted", len(accepted)),
                     ("matched", len(matched)), ("canon", len(gold_canon))]:
            tot[k] += v
        print(f"| {tech} | {len(items)} | {r:.3f} | {len(comps)} ({len(accepted)}) | {len(matched)} | {p:.3f} | "
              f"{len(gold_canon)} |")
    print(f"| **Pooled** | {tot['items']} | {tot['acc'] / tot['items']:.3f} | {tot['comps']} ({tot['accepted']}) | "
          f"{tot['matched']} | {tot['matched'] / tot['accepted']:.3f} | {tot['canon']} |")
    print(f"| **Mean of technologies** | | {mean(recalls):.3f} | | | {mean(precs):.3f} | |")
    print("\nGold items the judge rejected:", ", ".join(f"{t}: {c}" for t, c in rejected) or "none")
    unmatched = {t: sorted(c for c in pipeline.get(t, set()) if pipe_cache[_cache_key(t, c)].plausible
                           and c not in {v for v in g2c[t].values()}) for t in gold}
    print("\nAccepted pipeline components with no gold match (counted as false positives):")
    for t, cs in sorted(unmatched.items()):
        print(f"- {t}: {', '.join(cs) or 'none'}")


if __name__ == "__main__":
    asyncio.run(main())
