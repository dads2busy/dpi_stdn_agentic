#!/usr/bin/env python3
"""Expand generic material labels to elemental/compound constituents (post-pass).

Reads normalized STDN CSVs, maps each `material` through data/material_resolution_map.csv,
and writes output/resolved/<same filename>.csv with added columns:
  material_resolved, material_level, material_elements, resolution_provenance.
Rows whose material maps to itself keep their country shares (provenance `identity`);
expanded or renamed rows (provenance `map`) get country shares refetched from USGS, then the
LLM fallback cache; materials neither covers keep blank country fields.

Usage: uv run python scripts/resolve_materials.py --pattern "output/normalized/stdns_output_*.csv" --out output/resolved
"""
import argparse
import csv
import glob
import os

NEW_FIELDS = ["material_resolved", "material_level", "material_elements", "resolution_provenance", "country_source"]
COUNTRY_FIELDS = ["country", "percentage", "country_confidence", "country_reasoning", "meas_unit", "amount"]


def load_map(path):
    """source -> [(resolved_name, resolved_level, elements)]; [] for a non-material with no constituent."""
    m = {}
    for r in csv.DictReader(open(path)):
        if not r["resolved"]:
            m[r["source"]] = []
            continue
        res = r["resolved"].split("|")
        lv = r["resolved_level"].split("|")
        if len(lv) == 1:
            lv = lv * len(res)
        el = r["elements"].split(";") if r["elements"] else [""] * len(res)
        m[r["source"]] = list(zip(res, lv, el))
    return m


def _key(s):
    return s.strip().lower()


def _blank_country(row):
    return {**row, **{f: "" for f in COUNTRY_FIELDS if f in row or f in ("country", "percentage")}}


def load_hs_codes(path="data/hs_codes_and_usgs_names.csv"):
    return {r["Elements_Compounds"]: r["HS_Code"] for r in csv.DictReader(open(path))}


def resolve_rows(rows, mapping, hs_codes=None):
    """hs_codes: ontology name -> HS code; mapped rows take their constituent's code ("" if not in the ontology)."""
    lower = {_key(k): v for k, v in mapping.items()}
    hs_codes = hs_codes or {}
    out = []
    for r in rows:
        tgt = lower.get(_key(r["material"]))
        if tgt is None:
            out.append({**r, "material_resolved": r["material"], "material_level": "unmapped",
                        "material_elements": "", "resolution_provenance": "identity"})
        elif tgt == []:
            out.append({**_blank_country(r), "material_resolved": "", "material_level": "not_material",
                        "material_elements": "", "resolution_provenance": "map"})
        elif len(tgt) == 1 and _key(tgt[0][0]) == _key(r["material"]):
            name, lvl, el = tgt[0]
            out.append({**r, "material_resolved": r["material"], "material_level": lvl,
                        "material_elements": el, "resolution_provenance": "identity"})
        else:
            for name, lvl, el in tgt:
                row = {**_blank_country(r), "material_resolved": name, "material_level": lvl,
                       "material_elements": el, "resolution_provenance": "map"}
                if "hs_code" in r:
                    row["hs_code"] = hs_codes.get(name, "")
                out.append(row)
    # Normalized CSVs carry one row per country, so a blanked expansion repeats once per
    # original country row; keep the first of each identical row.
    seen, deduped = set(), []
    for r in out:
        if r["resolution_provenance"] == "map":
            k = tuple(sorted(r.items()))
            if k in seen:
                continue
            seen.add(k)
        deduped.append(r)
    return deduped


def fill_countries(rows, lookup):
    """Give each mapped row one row per producing country from lookup(material) -> [country dicts].
    Identity rows, non-materials, and materials lookup returns nothing for stay as they are.
    Sets country_source: `original` (identity rows keep the pipeline's shares), `usgs` or `llm_cache`
    (refetched), or "" (no data)."""
    out = []
    for r in rows:
        if r["resolution_provenance"] != "map":
            out.append({**r, "country_source": "original"})
            continue
        data = lookup(r["material_resolved"]) if r["material_resolved"] else []
        if not data:
            out.append({**r, "country_source": ""})
            continue
        for c in data:
            row = {**r, "country": c.get("country", ""), "percentage": c.get("percentage", ""),
                   "country_source": c.get("source", "")}
            for field, key in [("country_confidence", "confidence"), ("country_reasoning", "reasoning"),
                               ("meas_unit", "meas_unit"), ("amount", "amount")]:
                if field in r:
                    row[field] = c.get(key, "")
            out.append(row)
    return out


def usgs_lookup(src_year=2024, meas_year=2023):
    """USGS first, then the LLM fallback cache; never a live LLM call. Same years as the pipeline enricher."""
    from stdn_agentic.data.llm_fallback_cache import LLMFallbackCache
    from stdn_agentic.data.repository import CountryDataRepository

    repo = CountryDataRepository(database_path="./data/world_mineral_commodity_reports_2022-2025_v8.db",
                                 deps=None, use_llm_fallback=False)
    # TTL is ignored here: entries are read as recorded, whatever their age.
    cache = LLMFallbackCache(ttl_hours=10**6)
    memo = {}

    def lookup(material):
        if material not in memo:
            data = [{"confidence": 0.95, **c, "source": "usgs",
                     "reasoning": f"USGS Mineral Commodity Summaries {src_year}/{meas_year} (resolution refetch)"}
                    for c in repo.query_usgs(material, src_year, meas_year)]
            if not data:
                hs = repo.lookup_hs_code(material)
                cached = cache.get_countries(hs_code=hs, usgs_name=material, src_year=src_year, meas_year=meas_year) if hs else None
                data = [{**c, "source": "llm_cache",
                         "reasoning": f"LLM fallback cache (previously computed) - no USGS data available for {material}"}
                        for c in cached or []]
            memo[material] = data
        return memo[material]

    lookup.memo = memo
    return lookup


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", required=True)
    ap.add_argument("--out", default="output/resolved")
    ap.add_argument("--map", default="data/material_resolution_map.csv")
    ap.add_argument("--no-refetch", action="store_true", help="leave mapped rows with blank country fields")
    a = ap.parse_args()
    mapping = load_map(a.map)
    hs_codes = load_hs_codes()
    lookup = None if a.no_refetch else usgs_lookup()
    os.makedirs(a.out, exist_ok=True)
    for f in sorted(glob.glob(a.pattern)):
        rows = list(csv.DictReader(open(f)))
        if not rows:
            print(f, "empty, skipped")
            continue
        out = resolve_rows(rows, mapping, hs_codes)
        if lookup:
            out = fill_countries(out, lookup)
        fields = list(rows[0].keys()) + NEW_FIELDS
        with open(os.path.join(a.out, os.path.basename(f)), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(out)
        print(f, len(rows), "->", len(out))


if __name__ == "__main__":
    main()
