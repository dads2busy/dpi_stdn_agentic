# Material resolution report

Counts are material nodes: distinct (technology, component, material) per run, summed over runs. *Before* classifies the material as extracted; *after* classifies each constituent it resolves to via `data/material_resolution_map.csv`. Generic entries that remain generic after resolution are petrochemical resins, biologicals, and USGS commodities reported as such (including steel).

The headline is the share of material nodes that are element/compound-level: before = the material as extracted, after = every constituent it resolves to is element/compound-level (mean over runs). The level table below counts constituents after resolution, so its totals differ.

## Microelectronics d5v1v1 (submitted, 5 runs)

**Element/compound-level material nodes: 71.8% before, 85.9% after.**

| level | before (material nodes, n=7814) | after (constituents, n=10516) |
|---|---|---|
| element | 4905 (62.8%) | 5871 (55.8%) |
| compound | 702 (9.0%) | 3541 (33.7%) |
| generic | 2197 (28.1%) | 1100 (10.5%) |
| not_material | 10 (0.1%) | 4 (0.0%) |
| unmapped | 0 (0.0%) | 0 (0.0%) |

Country shares for resolved constituents (rows): llm_cache 16330 (79.5%), usgs 4210 (20.5%)


Most frequent generic materials before resolution: Epoxy resins (765), Glass (522), Ceramic (338), Steel Ingots (329), Stainless steel (96), Fiberglass (68), Acrylic (43), Solder paste (13)

## Biotechnology d5v1v1 (revision, 5 runs)

**Element/compound-level material nodes: 64.5% before, 89.9% after.**

| level | before (material nodes, n=7110) | after (constituents, n=11427) |
|---|---|---|
| element | 3145 (44.2%) | 6579 (57.6%) |
| compound | 1442 (20.3%) | 4128 (36.1%) |
| generic | 2450 (34.5%) | 720 (6.3%) |
| not_material | 73 (1.0%) | 0 (0.0%) |
| unmapped | 0 (0.0%) | 0 (0.0%) |

Country shares for resolved constituents (rows): llm_cache 19780 (58.9%), usgs 13780 (41.0%), none 36 (0.1%)


Most frequent generic materials before resolution: Glass (572), Epoxy resins (396), Stainless steel (270), Stainless steel (SS 304/316) (268), Steel Ingots (235), Stainless steel (SS 316) (202), Ceramic (152), Acrylic (82)

## Pharmaceuticals d5v1v1 (revision, 5 runs)

**Element/compound-level material nodes: 61.7% before, 91.1% after.**

| level | before (material nodes, n=6041) | after (constituents, n=10706) |
|---|---|---|
| element | 2538 (42.0%) | 7158 (66.9%) |
| compound | 1191 (19.7%) | 3010 (28.1%) |
| generic | 2298 (38.0%) | 537 (5.0%) |
| not_material | 14 (0.2%) | 1 (0.0%) |
| unmapped | 0 (0.0%) | 0 (0.0%) |

Country shares for resolved constituents (rows): llm_cache 18665 (50.2%), usgs 18515 (49.8%), none 1 (0.0%)


Most frequent generic materials before resolution: Stainless steel (SS 304/316) (420), Glass (406), Stainless steel (SS 316) (326), Steel Ingots (317), Stainless steel (283), Epoxy resins (208), Ceramic (160), HEPA filter media (32)

