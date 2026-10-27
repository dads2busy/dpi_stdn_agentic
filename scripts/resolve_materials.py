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

NEW_FIELDS = ["material_resolved", "material_level", "material_elements", "resolution_provenance"]
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


def resolve_rows(rows, mapping):
    lower = {_key(k): v for k, v in mapping.items()}
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
                out.append({**_blank_country(r), "material_resolved": name, "material_level": lvl,
                            "material_elements": el, "resolution_provenance": "map"})
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
    Identity rows, non-materials, and materials lookup returns nothing for stay as they are."""
    out = []
    for r in rows:
        data = lookup(r["material_resolved"]) if r["resolution_provenance"] == "map" and r["material_resolved"] else []
        if not data:
            out.append(r)
            continue
        for c in data:
            row = {**r, "country": c.get("country", ""), "percentage": c.get("percentage", "")}
            for field, key in [("country_confidence", "confidence"), ("country_reasoning", "reasoning"),
                               ("meas_unit", "meas_unit"), ("amount", "amount"), ("hs_code", "hs_code")]:
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
            data = repo.query_usgs(material, src_year, meas_year)
            if data:
                for c in data:
                    c.setdefault("confidence", 0.95)
                    c.setdefault("reasoning", f"USGS Mineral Commodity Summaries {src_year}/{meas_year} (resolution refetch)")
            else:
                hs = repo.lookup_hs_code(material)
                data = (cache.get_countries(hs_code=hs, usgs_name=material, src_year=src_year, meas_year=meas_year) or []) if hs else []
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
    lookup = None if a.no_refetch else usgs_lookup()
    os.makedirs(a.out, exist_ok=True)
    for f in sorted(glob.glob(a.pattern)):
        rows = list(csv.DictReader(open(f)))
        if not rows:
            print(f, "empty, skipped")
            continue
        out = resolve_rows(rows, mapping)
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
