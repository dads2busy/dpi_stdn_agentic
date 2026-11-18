#!/usr/bin/env python3
"""Concentration indices beyond HHI: governance- and development-weighted HHI (Reviewer 3; plan Task 1.3).

For every material with USGS-sourced country shares in the resolved outputs (output/resolved/*.csv), compute:

  HHI      sum of squared country shares, shares in percent (0-10,000); US DOJ/FTC "highly concentrated"
           threshold 2,500.
  HHI_WGI  sum of s_i^2 * WGI_i with shares as fractions and WGI_i = World Bank Worldwide Governance Indicators
           Political Stability and Absence of Violence (PV.EST, 2023) rescaled to 0 (best) ... 10 (worst):
           10 * (2.5 - PV) / 5, clipped. This is the EU CRM supply-risk convention; the range is 0-10.
  HHI_HDI  the same with HDI_i' = 10 * (1 - HDI_i), UNDP Human Development Index 2022 (higher = less developed).

The residual "OTHER" producer and countries without a score (e.g. Taiwan, absent from both sources) get the
share-weighted mean score of the named producers of that material. A sensitivity with OTHER dropped is reported.

Shares: one distribution per material. Provenance per row: "usgs" when the share came from the USGS Mineral
Commodity Summaries database (country_source == "usgs", or the pipeline's USGS template reasoning
"USGS Mineral Commodity Summaries ..."); otherwise "llm" (LLM fallback cache or debate estimate). A material uses
its modal USGS distribution when one exists, else its modal LLM distribution, and the table labels the source.
Some critical materials have no USGS distribution of their own; neodymium, for instance, is reported only within
the rare-earth aggregate.

Usage (code repo): uv run --with numpy --with scipy python scripts/concentration_indices.py \
    > output/analysis/concentration_indices.md
"""
import csv
import glob
import json
from collections import Counter, defaultdict

from scipy.stats import spearmanr

WGI_PATH = "data/external/wgi/wgi_pv_est_2023.json"
HDI_PATH = "data/external/hdi/hdr_composite_time_series.csv"
HDI_YEAR = "hdi_2022"
MAP_OUT = "data/country_name_map.csv"
NONCOUNTRY = "NONCOUNTRY"
OVERRIDES = {  # raw name (lower) -> iso3; USGS and LLM spellings that do not match the WB/UNDP names
    "burma": "MMR", "myanmar": "MMR", "congo": "COD", "congo (drc)": "COD", "democratic republic of congo": "COD",
    "iran": "IRN", "korea, north": "PRK", "korea, republic of": "KOR", "south korea": "KOR", "laos": "LAO",
    "russia": "RUS", "turkey": "TUR", "vietnam": "VNM", "taiwan": "TWN", "other": "OTHER",
    "developers": NONCOUNTRY, "europe (germany and france)": NONCOUNTRY, "europe (combined)": NONCOUNTRY,
    "european union": NONCOUNTRY,
}


def hhi(shares_pct):
    return sum(s * s for s in shares_pct.values())


def weighted_hhi(shares_pct, w):
    """EU convention: shares as fractions, weights on a 0-10 scale -> index on 0-10."""
    return sum((s / 100) ** 2 * w[c] for c, s in shares_pct.items())


def wgi_to_score(pv):
    return min(10.0, max(0.0, 10 * (2.5 - pv) / 5))


def hdi_to_score(h):
    return 10 * (1 - h)


def load_scores():
    wgi, names = {}, {}
    for x in json.load(open(WGI_PATH))[1]:
        iso = x["countryiso3code"]
        if iso and x["value"] is not None:
            wgi[iso] = wgi_to_score(float(x["value"]))
            names[x["country"]["value"].lower()] = iso
    hdi = {}
    with open(HDI_PATH, encoding="latin-1") as f:
        for r in csv.DictReader(f):
            names.setdefault(r["country"].lower(), r["iso3"])
            if r.get(HDI_YEAR):
                hdi[r["iso3"]] = hdi_to_score(float(r[HDI_YEAR]))
    return wgi, hdi, names


def build_name_map(raw_names, names):
    out = {}
    for n in raw_names:
        k = n.lower()
        out[n] = OVERRIDES.get(k) or names.get(k)
    missing = sorted(n for n, v in out.items() if not v)
    assert not missing, f"unmapped country names: {missing}"
    with open(MAP_OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["raw", "iso3"])
        w.writerows(sorted(out.items()))
    return out


def row_source(r):
    if r.get("country_source") == "usgs" or (r.get("country_reasoning") or "").startswith(
            "USGS Mineral Commodity Summaries"):
        return "usgs"
    return "llm"


def material_distributions(name_map):
    """material -> ({iso3: share%}, source, n distinct variants); USGS modal distribution preferred."""
    seen = {"usgs": defaultdict(Counter), "llm": defaultdict(Counter)}
    techs = defaultdict(set)
    for path in glob.glob("output/resolved/*.csv"):
        groups = defaultdict(dict)
        with open(path) as fh:
            for r in csv.DictReader(fh):
                mat = r.get("material_resolved") or r.get("material")
                c = name_map.get(r.get("country") or "")
                if not mat or not c or c == NONCOUNTRY:
                    continue
                try:
                    s = float(r["percentage"])
                except (TypeError, ValueError):
                    continue
                groups[(r["technology"], r["component"], mat, row_source(r))][c] = s
                techs[mat].add(r["technology"])
        for (t, comp, mat, src), d in groups.items():
            seen[src][mat][tuple(sorted((c, round(s, 2)) for c, s in d.items()))] += 1
    out = {}
    for m in set(seen["usgs"]) | set(seen["llm"]):
        src = "usgs" if m in seen["usgs"] else "llm"
        cnt = seen[src][m]
        out[m] = (dict(cnt.most_common(1)[0][0]), src, len(cnt))
    return out, techs


def impute(shares, score):
    named = {c: s for c, s in shares.items() if c in score}
    tot = sum(named.values())
    fill = sum(score[c] * s for c, s in named.items()) / tot if tot else 5.0
    return {c: score.get(c, fill) for c in shares}, [c for c in shares if c not in score]


def main():
    wgi, hdi, names = load_scores()
    raw = {r["country"] for f in glob.glob("output/resolved/*.csv") for r in csv.DictReader(open(f)) if r["country"]}
    name_map = build_name_map(raw, names)
    dists, techs = material_distributions(name_map)

    rows, imputed_any = [], Counter()
    for m, (sh, src, nvar) in dists.items():
        if sum(sh.values()) < 50:  # fragmentary distributions (a single partial row) are not indexable
            continue
        ww, miss_w = impute(sh, wgi)
        wh, miss_h = impute(sh, hdi)
        imputed_any.update(miss_w + miss_h)
        no_other = {c: s for c, s in sh.items() if c != "OTHER"}
        rows.append(dict(material=m, src=src, n_tech=len(techs[m]), variants=nvar, hhi=hhi(sh),
                         wgi=weighted_hhi(sh, ww), hdi=weighted_hhi(sh, wh),
                         wgi_noother=weighted_hhi(no_other, ww), top=max(sh, key=sh.get), top_share=max(sh.values())))
    for key in ["hhi", "wgi", "hdi"]:
        for i, r in enumerate(sorted(rows, key=lambda r: -r[key]), 1):
            r[f"rank_{key}"] = i

    print("# Concentration indices: HHI vs governance- (WGI) and development- (HDI) weighted HHI\n")
    nu = sum(r["src"] == "usgs" for r in rows)
    print(f"{len(rows)} materials with country shares in `output/resolved` ({nu} USGS-sourced, {len(rows) - nu} "
          "LLM-estimated, labelled). WGI = Political Stability "
          "(PV.EST) 2023, rescaled 0 best–10 worst; HDI 2022, scored 10·(1−HDI). OTHER and unscored countries get the "
          "share-weighted mean score of named producers. Imputed: "
          + ", ".join(f"{c} ({n} uses)" for c, n in imputed_any.most_common()) + ".\n")
    for subset, lab0 in [(rows, "all"), ([r for r in rows if r["src"] == "usgs"], "USGS-sourced only")]:
        rh = [r["hhi"] for r in subset]
        for k, lab in [("wgi", "HHI_WGI"), ("hdi", "HHI_HDI"), ("wgi_noother", "HHI_WGI without OTHER")]:
            rho = spearmanr(rh, [r[k] for r in subset])
            print(f"- {lab0} (n={len(subset)}): Spearman HHI vs {lab}: ρ = {rho.statistic:.3f} (p = {rho.pvalue:.2g})")
    multi = [r["material"] for r in rows if r["variants"] > 1]  # within the chosen source
    print(f"- Materials whose share distribution (within its chosen source) varies across rows; modal one used: {len(multi)}\n")

    print("## All materials, ranked by HHI\n")
    print("| Material | Source | Techs | Top producer (share %) | HHI | ≥2,500 | HHI_WGI | HHI_HDI | Rank HHI | Rank WGI | Rank HDI |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: -r["hhi"]):
        print(f"| {r['material']} | {r['src']} | {r['n_tech']} | {r['top']} ({r['top_share']:.0f}) | {r['hhi']:,.0f} | "
              f"{'yes' if r['hhi'] >= 2500 else ''} | {r['wgi']:.2f} | {r['hdi']:.2f} | {r['rank_hhi']} | "
              f"{r['rank_wgi']} | {r['rank_hdi']} |")

    print("\n## Where the verdicts diverge\n")
    top = 10
    for k, lab in [("wgi", "HHI_WGI"), ("hdi", "HHI_HDI")]:
        a = {r["material"] for r in rows if r["rank_hhi"] <= top}
        b = {r["material"] for r in rows if r[f"rank_{k}"] <= top}
        print(f"- Top-{top} by {lab} but not by HHI: {', '.join(sorted(b - a)) or 'none'}")
        print(f"- Top-{top} by HHI but not by {lab}: {', '.join(sorted(a - b)) or 'none'}")
        movers = sorted(rows, key=lambda r: r["rank_hhi"] - r[f"rank_{k}"], reverse=True)[:8]
        print(f"- Largest rises under {lab} (rank HHI → {lab}): "
              + "; ".join(f"{r['material']} {r['rank_hhi']}→{r[f'rank_{k}']} (HHI {r['hhi']:,.0f})" for r in movers))
    nd = next((r for r in rows if r["material"].lower() == "neodymium"), None)
    if nd:
        print(f"\nNeodymium: HHI {nd['hhi']:,.0f} (rank {nd['rank_hhi']}), HHI_WGI {nd['wgi']:.2f} "
              f"(rank {nd['rank_wgi']}), HHI_HDI {nd['hdi']:.2f} (rank {nd['rank_hdi']}); {nd['n_tech']} technologies.")


if __name__ == "__main__":
    main()
