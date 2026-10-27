# Material resolution report

Counts are material nodes: distinct (technology, component, material) per run, summed over runs. *Before* classifies the material as extracted; *after* classifies each constituent it resolves to via `data/material_resolution_map.csv`. Generic entries that remain generic after resolution are petrochemical resins, biologicals, and USGS mineral commodities reported as such.

## Microelectronics d5v1v1 (submitted, 5 runs)

| level | before | after |
|---|---|---|
| element | 4905 (62.8%) | 6592 (57.3%) |
| compound | 702 (9.0%) | 4136 (36.0%) |
| generic | 2197 (28.1%) | 771 (6.7%) |
| not_material | 10 (0.1%) | 4 (0.0%) |
| unmapped | 0 (0.0%) | 0 (0.0%) |
| **element + compound** | 71.8% | 93.3% |

Most frequent generic materials before resolution: Epoxy resins (765), Glass (522), Ceramic (338), Steel Ingots (329), Stainless steel (96), Fiberglass (68), Acrylic (43), Solder paste (13)

## Biotechnology d5v1v1 (revision, 5 runs)

| level | before | after |
|---|---|---|
| element | 3145 (44.2%) | 6897 (56.8%) |
| compound | 1442 (20.3%) | 4750 (39.2%) |
| generic | 2450 (34.5%) | 485 (4.0%) |
| not_material | 73 (1.0%) | 0 (0.0%) |
| unmapped | 0 (0.0%) | 0 (0.0%) |
| **element + compound** | 64.5% | 96.0% |

Most frequent generic materials before resolution: Glass (572), Epoxy resins (396), Stainless steel (270), Stainless steel (SS 304/316) (268), Steel Ingots (235), Stainless steel (SS 316) (202), Ceramic (152), Acrylic (82)

## Pharmaceuticals d5v1v1 (revision, 5 runs)

| level | before | after |
|---|---|---|
| element | 2538 (42.0%) | 7957 (68.3%) |
| compound | 1191 (19.7%) | 3479 (29.8%) |
| generic | 2298 (38.0%) | 220 (1.9%) |
| not_material | 14 (0.2%) | 1 (0.0%) |
| unmapped | 0 (0.0%) | 0 (0.0%) |
| **element + compound** | 61.7% | 98.1% |

Most frequent generic materials before resolution: Stainless steel (SS 304/316) (420), Glass (406), Stainless steel (SS 316) (326), Steel Ingots (317), Stainless steel (283), Epoxy resins (208), Ceramic (160), HEPA filter media (32)

