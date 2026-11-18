# Concentration indices: HHI vs governance- (WGI) and development- (HDI) weighted HHI

231 materials with country shares in `output/resolved` (37 USGS-sourced, 194 LLM-estimated, labelled). WGI = Political Stability (PV.EST) 2023, rescaled 0 best–10 worst; HDI 2022, scored 10·(1−HDI). OTHER and unscored countries get the share-weighted mean score of named producers. Imputed: OTHER (32 uses), TWN (20 uses), PRK (1 uses), NCL (1 uses).

- all (n=231): Spearman HHI vs HHI_WGI: ρ = 0.975 (p = 5.9e-151)
- all (n=231): Spearman HHI vs HHI_HDI: ρ = 0.868 (p = 1.3e-71)
- all (n=231): Spearman HHI vs HHI_WGI without OTHER: ρ = 0.975 (p = 2.5e-151)
- USGS-sourced only (n=37): Spearman HHI vs HHI_WGI: ρ = 0.966 (p = 4.1e-22)
- USGS-sourced only (n=37): Spearman HHI vs HHI_HDI: ρ = 0.865 (p = 5e-12)
- USGS-sourced only (n=37): Spearman HHI vs HHI_WGI without OTHER: ρ = 0.966 (p = 4.1e-22)
- Materials whose share distribution (within its chosen source) varies across rows; modal one used: 109

## All materials, ranked by HHI

| Material | Source | Techs | Top producer (share %) | HHI | ≥2,500 | HHI_WGI | HHI_HDI | Rank HHI | Rank WGI | Rank HDI |
|---|---|---|---|---|---|---|---|---|---|---|
| Gallium | usgs | 21 | CHN (98) | 9,676 | yes | 5.20 | 2.05 | 1 | 1 | 2 |
| Niobium | usgs | 2 | BRA (90) | 8,237 | yes | 4.94 | 1.96 | 2 | 3 | 3 |
| Bismuth telluride | llm | 56 | CHN (90) | 8,136 | yes | 4.38 | 1.73 | 3 | 4 | 4 |
| Cesium | llm | 18 | CAN (85) | 7,338 | yes | 2.77 | 0.52 | 4 | 23 | 83 |
| Dysprosium | llm | 2 | CHN (85) | 7,300 | yes | 3.93 | 1.54 | 5 | 5 | 6 |
| Tungsten carbide | llm | 6 | CHN (85) | 7,284 | yes | 3.92 | 1.54 | 6 | 6 | 5 |
| Magnesium | llm | 13 | CHN (84) | 7,126 | yes | 3.84 | 1.51 | 7 | 7 | 7 |
| Mercury | usgs | 2 | CHN (83) | 7,023 | yes | 3.78 | 1.50 | 8 | 8 | 8 |
| Tungsten | usgs | 41 | CHN (81) | 6,559 | yes | 3.53 | 1.39 | 9 | 9 | 12 |
| Bismuth | usgs | 4 | CHN (80) | 6,525 | yes | 3.49 | 1.40 | 10 | 10 | 11 |
| Tungsten hexafluoride | llm | 1 | CHN (79) | 6,341 | yes | 3.40 | 1.34 | 11 | 11 | 13 |
| Graphite | usgs | 38 | CHN (77) | 6,009 | yes | 3.25 | 1.30 | 12 | 14 | 14 |
| Gallium arsenide | llm | 81 | CHN (75) | 5,808 | yes | 3.09 | 1.20 | 13 | 18 | 18 |
| Guanidine hydrochloride | llm | 1 | CHN (75) | 5,808 | yes | 3.13 | 1.23 | 14 | 15 | 15 |
| Octadecylsilane | llm | 4 | CHN (75) | 5,808 | yes | 3.11 | 1.21 | 15 | 17 | 17 |
| Neodymium | llm | 14 | CHN (75) | 5,808 | yes | 3.12 | 1.21 | 16 | 16 | 16 |
| Cobalt | usgs | 10 | COD (74) | 5,544 | yes | 4.94 | 2.86 | 17 | 2 | 1 |
| Iridium | llm | 1 | ZAF (70) | 5,218 | yes | 3.27 | 1.46 | 18 | 12 | 9 |
| Aluminum gallium arsenide | llm | 44 | CHN (70) | 5,218 | yes | 2.78 | 1.06 | 19 | 22 | 23 |
| Platinum | llm | 33 | ZAF (70) | 5,208 | yes | 3.27 | 1.45 | 20 | 13 | 10 |
| SYBR Green I dye | llm | 1 | CHN (70) | 5,208 | yes | 2.79 | 1.06 | 21 | 21 | 22 |
| Barium | llm | 2 | CHN (70) | 5,154 | yes | 2.80 | 1.12 | 22 | 20 | 20 |
| Vanadium | usgs | 15 | CHN (68) | 5,148 | yes | 2.83 | 1.09 | 23 | 19 | 21 |
| Barium titanate | llm | 163 | CHN (70) | 5,136 | yes | 2.73 | 1.06 | 24 | 24 | 25 |
| Silicon carbide | llm | 32 | CHN (70) | 5,077 | yes | 2.73 | 1.06 | 25 | 25 | 24 |
| Iodine | usgs | 1 | CHL (63) | 4,924 | yes | 2.14 | 0.64 | 26 | 47 | 67 |
| Magnesium oxide | llm | 4 | CHN (65) | 4,860 | yes | 2.62 | 0.97 | 27 | 26 | 27 |
| Indium | usgs | 60 | CHN (66) | 4,778 | yes | 2.46 | 0.95 | 28 | 31 | 30 |
| Antibodies | llm | 15 | USA (65) | 4,708 | yes | 2.48 | 0.40 | 29 | 30 | 122 |
| Titanium carbide | llm | 7 | CHN (65) | 4,608 | yes | 2.49 | 0.95 | 30 | 28 | 29 |
| Germanium | llm | 17 | CHN (65) | 4,600 | yes | 2.50 | 0.95 | 31 | 27 | 31 |
| Magnesium chloride | llm | 3 | CHN (65) | 4,588 | yes | 2.49 | 0.93 | 32 | 29 | 33 |
| Yttrium | llm | 2 | CHN (65) | 4,584 | yes | 2.46 | 0.95 | 33 | 33 | 28 |
| Cerium oxide | llm | 1 | CHN (65) | 4,560 | yes | 2.44 | 0.93 | 34 | 34 | 35 |
| L-glutamine | llm | 1 | CHN (65) | 4,539 | yes | 2.46 | 0.98 | 35 | 32 | 26 |
| Amino acids | llm | 12 | CHN (65) | 4,507 | yes | 2.39 | 0.92 | 36 | 36 | 36 |
| Lead zirconate titanate | llm | 1 | CHN (65) | 4,466 | yes | 2.38 | 0.91 | 37 | 37 | 37 |
| Aluminum sulfate | llm | 2 | CHN (65) | 4,463 | yes | 2.42 | 0.95 | 38 | 35 | 32 |
| Gallium nitride | llm | 32 | CHN (60) | 4,158 | yes | 2.19 | 0.80 | 39 | 41 | 44 |
| Boron nitride | llm | 5 | CHN (60) | 4,138 | yes | 2.28 | 0.93 | 40 | 38 | 34 |
| N,N'-Methylenebisacrylamide | llm | 1 | CHN (60) | 4,058 | yes | 2.19 | 0.86 | 41 | 40 | 39 |
| EDTA | llm | 2 | CHN (60) | 4,038 | yes | 2.17 | 0.86 | 42 | 42 | 40 |
| Polyvinylidene fluoride | llm | 7 | CHN (60) | 4,038 | yes | 2.13 | 0.79 | 43 | 49 | 50 |
| Hafnium oxide | llm | 1 | CHN (60) | 4,038 | yes | 2.16 | 0.80 | 44 | 44 | 47 |
| Agarose | llm | 8 | CHN (60) | 4,038 | yes | 2.12 | 0.79 | 45 | 50 | 49 |
| Beryllium | usgs | 2 | USA (58) | 4,018 | yes | 2.15 | 0.41 | 46 | 45 | 118 |
| Polyacrylamide | llm | 5 | CHN (60) | 3,999 | yes | 2.15 | 0.82 | 47 | 46 | 42 |
| Ethanol | llm | 9 | USA (56) | 3,972 | yes | 2.16 | 0.43 | 48 | 43 | 108 |
| Nucleotides | llm | 2 | CHN (60) | 3,963 | yes | 2.11 | 0.80 | 49 | 53 | 48 |
| Hydrofluoric acid | llm | 2 | CHN (60) | 3,935 | yes | 2.12 | 0.80 | 50 | 51 | 45 |
| Fluorine | llm | 2 | CHN (60) | 3,935 | yes | 2.13 | 0.84 | 51 | 48 | 41 |
| Arsenic | usgs | 1 | PER (45) | 3,806 | yes | 2.28 | 0.87 | 52 | 39 | 38 |
| Indium gallium arsenide | llm | 25 | CHN (55) | 3,708 | yes | 1.83 | 0.70 | 53 | 63 | 60 |
| Tris buffer | llm | 2 | CHN (55) | 3,658 | yes | 1.97 | 0.73 | 54 | 57 | 55 |
| DAPI | llm | 2 | CHN (55) | 3,658 | yes | 2.02 | 0.81 | 55 | 55 | 43 |
| Polytetrafluoroethylene | llm | 127 | CHN (55) | 3,638 | yes | 1.90 | 0.69 | 56 | 61 | 62 |
| Sodium phosphate | llm | 22 | CHN (50) | 3,630 | yes | 1.97 | 0.68 | 57 | 56 | 64 |
| Aluminum | usgs | 181 | CHN (59) | 3,613 | yes | 1.95 | 0.77 | 58 | 59 | 53 |
| Lithium carbonate | llm | 3 | AUS (50) | 3,568 | yes | 1.32 | 0.29 | 59 | 123 | 177 |
| Primers | llm | 2 | USA (50) | 3,501 | yes | 1.86 | 0.39 | 60 | 62 | 126 |
| Aluminum oxide | llm | 172 | CHN (54) | 3,392 | yes | 1.80 | 0.71 | 61 | 65 | 57 |
| Boron trioxide | llm | 1 | TUR (47) | 3,354 | yes | 2.11 | 0.42 | 62 | 52 | 114 |
| Steel Ingots | llm | 160 | CHN (57) | 3,352 | yes | 1.80 | 0.71 | 63 | 64 | 58 |
| Biotin-streptavidin | llm | 2 | USA (50) | 3,338 | yes | 1.74 | 0.33 | 64 | 68 | 153 |
| Phosphorus | llm | 23 | CHN (53) | 3,281 | yes | 1.80 | 0.73 | 65 | 66 | 54 |
| Lithium | usgs | 24 | AUS (48) | 3,252 | yes | 1.22 | 0.28 | 66 | 132 | 180 |
| Boron carbide | llm | 11 | TUR (50) | 3,250 | yes | 2.10 | 0.46 | 67 | 54 | 102 |
| RNA polymerase | llm | 1 | USA (50) | 3,250 | yes | 1.64 | 0.26 | 68 | 79 | 191 |
| Polyimide | llm | 92 | CHN (50) | 3,250 | yes | 1.65 | 0.59 | 69 | 76 | 72 |
| Chloroform | llm | 1 | CHN (50) | 3,250 | yes | 1.75 | 0.65 | 70 | 67 | 66 |
| Sulfur hexafluoride | llm | 1 | CHN (50) | 3,208 | yes | 1.66 | 0.58 | 71 | 75 | 73 |
| Iron | llm | 175 | CHN (50) | 3,177 | yes | 1.64 | 0.62 | 72 | 77 | 69 |
| Cement | usgs | 1 | CHN (51) | 3,165 | yes | 1.72 | 0.69 | 73 | 69 | 61 |
| dNTPs | llm | 5 | CHN (45) | 3,138 | yes | 1.66 | 0.53 | 74 | 74 | 81 |
| Antibiotics | llm | 5 | CHN (50) | 3,089 | yes | 1.69 | 0.68 | 75 | 72 | 63 |
| Antimony | usgs | 15 | CHN (48) | 3,072 | yes | 1.69 | 0.72 | 76 | 73 | 56 |
| PEEK | llm | 2 | CHN (45) | 3,000 | yes | 1.54 | 0.50 | 77 | 85 | 90 |
| Titanium nitride | llm | 11 | CHN (45) | 3,000 | yes | 1.52 | 0.50 | 78 | 88 | 87 |
| Aluminum nitride | llm | 11 | CHN (45) | 2,988 | yes | 1.40 | 0.50 | 79 | 106 | 86 |
| Boron | llm | 179 | TUR (47) | 2,970 | yes | 1.92 | 0.40 | 80 | 60 | 125 |
| Polysulfone | llm | 9 | CHN (45) | 2,958 | yes | 1.52 | 0.49 | 81 | 87 | 91 |
| Acetonitrile | llm | 3 | CHN (45) | 2,914 | yes | 1.50 | 0.49 | 82 | 90 | 92 |
| Recombinant proteins | llm | 1 | USA (45) | 2,863 | yes | 1.51 | 0.31 | 83 | 89 | 165 |
| Polyethersulfone | llm | 17 | CHN (45) | 2,858 | yes | 1.45 | 0.49 | 84 | 96 | 94 |
| Oxygen | llm | 9 | CHN (45) | 2,858 | yes | 1.57 | 0.57 | 85 | 83 | 74 |
| Deuterium | llm | 1 | USA (40) | 2,850 | yes | 1.61 | 0.47 | 86 | 80 | 97 |
| Fetal bovine serum | llm | 1 | USA (45) | 2,850 | yes | 1.44 | 0.23 | 87 | 98 | 202 |
| DNA polymerase | llm | 5 | USA (40) | 2,850 | yes | 1.45 | 0.33 | 88 | 95 | 154 |
| Horseradish peroxidase (HRP) | llm | 1 | USA (40) | 2,850 | yes | 1.46 | 0.34 | 89 | 93 | 146 |
| Protease inhibitors | llm | 1 | IND (40) | 2,850 | yes | 1.72 | 0.79 | 90 | 71 | 51 |
| Carbon | llm | 60 | CHN (45) | 2,850 | yes | 1.60 | 0.63 | 91 | 81 | 68 |
| Collagenase | llm | 1 | USA (40) | 2,850 | yes | 1.45 | 0.33 | 92 | 97 | 155 |
| Indium phosphide | llm | 15 | CHN (48) | 2,816 | yes | 1.43 | 0.53 | 93 | 99 | 78 |
| Helium | usgs | 9 | QAT (39) | 2,815 | yes | 1.15 | 0.29 | 94 | 143 | 176 |
| Nickel | usgs | 177 | IDN (50) | 2,807 | yes | 1.72 | 0.80 | 95 | 70 | 46 |
| Streptavidin | llm | 1 | USA (40) | 2,800 | yes | 1.46 | 0.36 | 96 | 92 | 135 |
| Avidin | llm | 1 | USA (40) | 2,800 | yes | 1.43 | 0.33 | 97 | 100 | 156 |
| Titanium | llm | 93 | CHN (45) | 2,799 | yes | 1.49 | 0.60 | 98 | 91 | 71 |
| Ferrous sulfate | llm | 2 | CHN (45) | 2,799 | yes | 1.54 | 0.56 | 99 | 86 | 76 |
| Zirconium dioxide | llm | 163 | AUS (43) | 2,782 | yes | 1.20 | 0.40 | 100 | 136 | 121 |
| Alexa Fluor dyes | llm | 5 | USA (40) | 2,750 | yes | 1.34 | 0.24 | 101 | 117 | 196 |
| DNA primers | llm | 8 | USA (40) | 2,713 | yes | 1.40 | 0.32 | 102 | 105 | 160 |
| Silane | llm | 1 | CHN (47) | 2,707 | yes | 1.42 | 0.50 | 103 | 101 | 88 |
| Ammonium persulfate | llm | 1 | CHN (45) | 2,689 | yes | 1.38 | 0.48 | 104 | 108 | 96 |
| Acrylonitrile butadiene styrene | llm | 57 | CHN (40) | 2,658 | yes | 1.32 | 0.42 | 105 | 122 | 116 |
| Insulin | llm | 1 | USA (40) | 2,658 | yes | 1.45 | 0.40 | 106 | 94 | 120 |
| Gelatin | llm | 2 | CHN (40) | 2,650 | yes | 1.42 | 0.45 | 107 | 103 | 104 |
| Polyethylene glycol (PEG) | llm | 8 | CHN (40) | 2,650 | yes | 1.37 | 0.44 | 108 | 110 | 106 |
| Dextran | llm | 1 | CHN (40) | 2,650 | yes | 1.38 | 0.44 | 109 | 109 | 107 |
| Acrylamide | llm | 7 | CHN (40) | 2,650 | yes | 1.32 | 0.41 | 110 | 125 | 117 |
| Photoresist | llm | 14 | KOR (35) | 2,650 | yes | 0.80 | 0.20 | 111 | 197 | 209 |
| Chromium | usgs | 175 | ZAF (44) | 2,621 | yes | 1.64 | 0.70 | 112 | 78 | 59 |
| Hydrogen peroxide | llm | 4 | CHN (40) | 2,614 | yes | 1.35 | 0.43 | 113 | 116 | 112 |
| Ammonium hydroxide | llm | 2 | CHN (40) | 2,599 | yes | 1.41 | 0.48 | 114 | 104 | 95 |
| CMP slurries | llm | 2 | CHN (44) | 2,593 | yes | 1.34 | 0.46 | 115 | 118 | 100 |
| Sulfuric acid | llm | 1 | CHN (45) | 2,568 | yes | 1.40 | 0.53 | 116 | 107 | 80 |
| Thermal interface materials | llm | 2 | CHN (45) | 2,566 | yes | 1.33 | 0.47 | 117 | 120 | 99 |
| Titanium dioxide | llm | 32 | CHN (45) | 2,558 | yes | 1.42 | 0.57 | 118 | 102 | 75 |
| Cycloolefin | llm | 4 | JPN (35) | 2,558 | yes | 0.94 | 0.32 | 119 | 172 | 164 |
| Growth factors | llm | 1 | USA (35) | 2,558 | yes | 1.33 | 0.35 | 120 | 119 | 137 |
| Polyvinyl chloride | llm | 51 | CHN (46) | 2,554 | yes | 1.36 | 0.51 | 121 | 113 | 85 |
| Chromium oxide | llm | 2 | ZAF (40) | 2,550 | yes | 1.56 | 0.65 | 122 | 84 | 65 |
| Epoxy resins | llm | 171 | CHN (40) | 2,550 | yes | 1.24 | 0.41 | 123 | 131 | 119 |
| Phosphine | llm | 1 | CHN (45) | 2,516 | yes | 1.36 | 0.52 | 124 | 112 | 82 |
| Bovine serum albumin (BSA) | llm | 1 | USA (35) | 2,514 | yes | 1.32 | 0.33 | 125 | 124 | 148 |
| Molybdenum | usgs | 149 | CHN (42) | 2,510 | yes | 1.35 | 0.49 | 126 | 115 | 93 |
| Tantalum | usgs | 24 | COD (41) | 2,500 |  | 1.96 | 1.19 | 127 | 58 | 19 |
| Calcium phosphate | llm | 2 | CHN (40) | 2,473 |  | 1.36 | 0.50 | 128 | 111 | 89 |
| Epoxy molding compounds | llm | 1 | CHN (45) | 2,437 |  | 1.27 | 0.46 | 129 | 129 | 103 |
| Nylon | llm | 4 | CHN (40) | 2,433 |  | 1.30 | 0.46 | 130 | 128 | 101 |
| Polymethyl methacrylate | llm | 113 | CHN (40) | 2,433 |  | 1.20 | 0.40 | 131 | 134 | 123 |
| Diamond (industrial) | usgs | 7 | RUS (40) | 2,415 |  | 1.59 | 0.61 | 132 | 82 | 70 |
| Selenium | usgs | 2 | CHN (42) | 2,406 |  | 1.16 | 0.43 | 133 | 141 | 109 |
| Cadmium telluride | llm | 2 | CHN (35) | 2,400 |  | 1.15 | 0.34 | 134 | 142 | 140 |
| Flux | llm | 1 | CHN (46) | 2,393 |  | 1.32 | 0.52 | 135 | 126 | 84 |
| Phosphoric acid | llm | 3 | CHN (40) | 2,389 |  | 1.31 | 0.47 | 136 | 127 | 98 |
| Ammonium sulfate | llm | 3 | CHN (40) | 2,389 |  | 1.35 | 0.53 | 137 | 114 | 79 |
| Polycarbonate | llm | 171 | CHN (35) | 2,319 |  | 1.14 | 0.34 | 138 | 145 | 145 |
| Argon | llm | 24 | USA (35) | 2,283 |  | 1.21 | 0.27 | 139 | 133 | 184 |
| Separator wetting agents | llm | 1 | CHN (41) | 2,275 |  | 1.16 | 0.40 | 140 | 140 | 124 |
| Electrolyte solvents | llm | 1 | CHN (42) | 2,274 |  | 1.17 | 0.42 | 141 | 139 | 115 |
| Xenon | llm | 2 | RUS (30) | 2,250 |  | 1.32 | 0.36 | 142 | 121 | 134 |
| Powder coating chemicals | llm | 1 | CHN (42) | 2,232 |  | 1.18 | 0.43 | 143 | 138 | 111 |
| Calcium chloride | llm | 3 | USA (30) | 2,153 |  | 1.12 | 0.30 | 144 | 148 | 170 |
| Silicon nitride | llm | 23 | CHN (35) | 2,150 |  | 0.95 | 0.33 | 145 | 170 | 150 |
| Lead | usgs | 24 | CHN (42) | 2,134 |  | 1.13 | 0.43 | 146 | 147 | 113 |
| Solder flux | llm | 16 | CHN (40) | 2,113 |  | 1.09 | 0.38 | 147 | 152 | 129 |
| Etchants | llm | 2 | CHN (39) | 2,094 |  | 1.07 | 0.36 | 148 | 153 | 132 |
| Manganese | usgs | 30 | ZAF (36) | 2,081 |  | 1.20 | 0.55 | 149 | 137 | 77 |
| Phosphate rock | usgs | 1 | CHN (41) | 2,080 |  | 1.14 | 0.45 | 150 | 144 | 105 |
| Copper etchants | llm | 1 | CHN (38) | 2,074 |  | 1.06 | 0.36 | 151 | 154 | 133 |
| Ethylene glycol | llm | 1 | CHN (35) | 2,063 |  | 1.09 | 0.34 | 152 | 151 | 144 |
| Solder paste and flux | llm | 1 | CHN (40) | 2,061 |  | 1.03 | 0.37 | 153 | 156 | 131 |
| Photoresist and Developers | llm | 1 | CHN (36) | 2,035 |  | 0.96 | 0.33 | 154 | 169 | 149 |
| Boron trifluoride | llm | 1 | TUR (28) | 2,032 |  | 1.20 | 0.27 | 155 | 135 | 187 |
| Zinc oxide | llm | 1 | CHN (35) | 2,018 |  | 1.12 | 0.43 | 156 | 149 | 110 |
| Tantalum oxide | llm | 5 | RWA (27) | 2,012 |  | 1.26 | 0.78 | 157 | 130 | 52 |
| Potassium phosphate | llm | 23 | CHN (28) | 1,981 |  | 1.13 | 0.37 | 158 | 146 | 130 |
| Optical Coating Materials | llm | 1 | CHN (36) | 1,962 |  | 0.99 | 0.32 | 159 | 158 | 158 |
| Photoresists and developers | llm | 3 | JPN (28) | 1,954 |  | 0.71 | 0.23 | 160 | 207 | 203 |
| Photoresists | llm | 1 | CHN (28) | 1,933 |  | 0.77 | 0.26 | 161 | 200 | 189 |
| Hydrochloric acid | llm | 1 | CHN (35) | 1,933 |  | 1.04 | 0.34 | 162 | 155 | 141 |
| Wet Etch Chemicals | llm | 1 | CHN (34) | 1,915 |  | 0.95 | 0.31 | 163 | 171 | 168 |
| Acetic acid | llm | 9 | CHN (30) | 1,914 |  | 0.98 | 0.29 | 164 | 164 | 178 |
| Polypropylene | llm | 122 | CHN (30) | 1,914 |  | 1.01 | 0.29 | 165 | 157 | 175 |
| Photolithography Chemicals | llm | 1 | CHN (34) | 1,877 |  | 0.89 | 0.30 | 166 | 183 | 169 |
| Surface Preparation Chemicals | llm | 2 | CHN (37) | 1,867 |  | 0.99 | 0.35 | 167 | 160 | 136 |
| Anti-corrosion agents | llm | 1 | CHN (36) | 1,863 |  | 0.99 | 0.35 | 168 | 159 | 139 |
| Passivation Chemicals | llm | 1 | CHN (36) | 1,855 |  | 0.97 | 0.33 | 169 | 167 | 152 |
| Silver chloride | llm | 4 | MEX (26) | 1,853 |  | 1.11 | 0.38 | 170 | 150 | 128 |
| Glycerol | llm | 1 | USA (27) | 1,848 |  | 0.98 | 0.28 | 171 | 162 | 182 |
| Vacuum pump oil | llm | 1 | CHN (35) | 1,835 |  | 0.96 | 0.32 | 172 | 168 | 159 |
| Protein A | llm | 1 | USA (28) | 1,829 |  | 0.97 | 0.26 | 173 | 166 | 190 |
| Isopropyl Alcohol | llm | 3 | CHN (34) | 1,829 |  | 0.98 | 0.32 | 174 | 163 | 161 |
| Acetone | llm | 4 | USA (28) | 1,821 |  | 0.91 | 0.23 | 175 | 178 | 199 |
| Methanol | llm | 2 | CHN (35) | 1,814 |  | 0.98 | 0.33 | 176 | 161 | 151 |
| Potassium hydroxide | llm | 1 | USA (28) | 1,798 |  | 0.91 | 0.21 | 177 | 177 | 207 |
| Sodium hydroxide | llm | 7 | CHN (30) | 1,789 |  | 0.94 | 0.28 | 178 | 175 | 181 |
| Surface Treatment Chemicals | llm | 1 | CHN (37) | 1,789 |  | 0.94 | 0.34 | 179 | 173 | 147 |
| III-V Semiconductor Precursors | llm | 1 | CHN (32) | 1,777 |  | 0.88 | 0.27 | 180 | 186 | 186 |
| Polyethylene terephthalate | llm | 152 | CHN (30) | 1,769 |  | 0.91 | 0.32 | 181 | 176 | 162 |
| Glucose | llm | 4 | USA (30) | 1,769 |  | 0.97 | 0.27 | 182 | 165 | 185 |
| Paints and surface coatings | llm | 1 | CHN (37) | 1,763 |  | 0.94 | 0.34 | 183 | 174 | 142 |
| Adhesives | llm | 1 | CHN (36) | 1,709 |  | 0.90 | 0.31 | 184 | 181 | 166 |
| Etch Chemistries | llm | 1 | CHN (30) | 1,705 |  | 0.83 | 0.25 | 185 | 195 | 195 |
| Cutting fluids | llm | 2 | CHN (34) | 1,693 |  | 0.88 | 0.30 | 186 | 185 | 173 |
| Polystyrene | llm | 34 | CHN (30) | 1,689 |  | 0.85 | 0.26 | 187 | 192 | 188 |
| Sealing compounds and adhesives | llm | 1 | CHN (35) | 1,684 |  | 0.86 | 0.29 | 188 | 190 | 174 |
| Cleanroom solvents | llm | 1 | CHN (32) | 1,674 |  | 0.85 | 0.26 | 189 | 193 | 192 |
| Polyethylene | llm | 133 | CHN (28) | 1,668 |  | 0.88 | 0.26 | 190 | 184 | 193 |
| Anti-corrosion chemical treatments | llm | 1 | CHN (33) | 1,664 |  | 0.87 | 0.30 | 191 | 188 | 171 |
| Acids and Etch Chemicals | llm | 1 | CHN (35) | 1,662 |  | 0.90 | 0.33 | 192 | 179 | 157 |
| Sand and gravel (industrial) | usgs | 4 | USA (32) | 1,661 |  | 0.88 | 0.19 | 193 | 187 | 213 |
| Silicon | usgs | 179 | CHN (40) | 1,651 |  | 0.89 | 0.35 | 194 | 182 | 138 |
| Copper oxide | llm | 10 | CHL (30) | 1,625 |  | 0.84 | 0.29 | 195 | 194 | 179 |
| Zinc | usgs | 5 | CHN (33) | 1,608 |  | 0.87 | 0.34 | 196 | 189 | 143 |
| Silicon dioxide | llm | 179 | CHN (30) | 1,573 |  | 0.85 | 0.28 | 197 | 191 | 183 |
| Ultrapure Water | llm | 1 | CHN (29) | 1,521 |  | 0.75 | 0.23 | 198 | 203 | 201 |
| Diatomite | usgs | 1 | USA (32) | 1,521 |  | 0.75 | 0.12 | 199 | 202 | 229 |
| Mica (Natural) | usgs | 1 | CHN (26) | 1,496 |  | 0.77 | 0.32 | 200 | 201 | 163 |
| Adhesives and Surface Treatment Chemicals | llm | 1 | CHN (29) | 1,445 |  | 0.73 | 0.22 | 201 | 204 | 205 |
| Ammonia | llm | 6 | CHN (30) | 1,429 |  | 0.82 | 0.31 | 202 | 196 | 167 |
| Potassium chloride | llm | 4 | CAN (35) | 1,425 |  | 0.57 | 0.12 | 203 | 222 | 230 |
| Calcium carbonate | llm | 179 | USA (24) | 1,423 |  | 0.78 | 0.24 | 204 | 198 | 197 |
| Refrigerants | llm | 2 | CHN (30) | 1,386 |  | 0.70 | 0.22 | 205 | 209 | 206 |
| Nitrogen | llm | 12 | CHN (30) | 1,377 |  | 0.78 | 0.30 | 206 | 199 | 172 |
| Lubricants and grease | llm | 1 | CHN (29) | 1,375 |  | 0.73 | 0.25 | 207 | 205 | 194 |
| Nitrogen and argon | llm | 1 | USA (24) | 1,351 |  | 0.73 | 0.20 | 208 | 206 | 211 |
| Grinding oils | llm | 1 | CHN (26) | 1,340 |  | 0.70 | 0.23 | 209 | 208 | 204 |
| Tin | usgs | 83 | CHN (23) | 1,324 |  | 0.90 | 0.38 | 210 | 180 | 127 |
| Ultra high purity gases | llm | 1 | CHN (24) | 1,317 |  | 0.65 | 0.18 | 211 | 213 | 214 |
| Purge gases | llm | 1 | CHN (27) | 1,311 |  | 0.66 | 0.20 | 212 | 211 | 212 |
| Solvents | llm | 1 | CHN (25) | 1,294 |  | 0.68 | 0.20 | 213 | 210 | 210 |
| Ultrapure Deionized Water | llm | 1 | CHN (23) | 1,266 |  | 0.61 | 0.17 | 214 | 216 | 218 |
| Dopant gases | llm | 1 | USA (21) | 1,224 |  | 0.57 | 0.15 | 215 | 221 | 223 |
| Carbon dioxide | llm | 2 | CHN (30) | 1,198 |  | 0.65 | 0.23 | 216 | 214 | 200 |
| Inert Gases | llm | 1 | CHN (22) | 1,173 |  | 0.59 | 0.15 | 217 | 219 | 222 |
| Lubricants | llm | 4 | CHN (25) | 1,167 |  | 0.63 | 0.21 | 218 | 215 | 208 |
| Cleaning solvents | llm | 5 | CHN (22) | 1,163 |  | 0.60 | 0.17 | 219 | 217 | 215 |
| Compressed nitrogen | llm | 1 | CHN (24) | 1,146 |  | 0.59 | 0.17 | 220 | 220 | 219 |
| Sputtering or Evaporation Process Gases | llm | 1 | USA (21) | 1,138 |  | 0.55 | 0.14 | 221 | 223 | 227 |
| Hydrogen | llm | 1 | CHN (20) | 1,098 |  | 0.59 | 0.17 | 222 | 218 | 216 |
| Silver | usgs | 121 | MEX (25) | 1,081 |  | 0.66 | 0.24 | 223 | 212 | 198 |
| Zeolites (natural) | usgs | 2 | SVK (20) | 1,035 |  | 0.45 | 0.17 | 224 | 228 | 217 |
| Gold | usgs | 150 | OTHER (23) | 954 |  | 0.47 | 0.13 | 225 | 227 | 228 |
| Lubricants and process oils | llm | 1 | USA (19) | 910 |  | 0.49 | 0.15 | 226 | 224 | 224 |
| Salt | usgs | 1 | CHN (20) | 882 |  | 0.48 | 0.16 | 227 | 225 | 220 |
| Sulfur | usgs | 1 | CHN (23) | 862 |  | 0.47 | 0.15 | 228 | 226 | 221 |
| Sodium chloride | llm | 25 | CHN (18) | 838 |  | 0.44 | 0.14 | 229 | 229 | 225 |
| Water | llm | 24 | CHN (17) | 718 |  | 0.41 | 0.14 | 230 | 230 | 226 |
| Gold and copper etchants | llm | 1 | CHN (14) | 558 |  | 0.27 | 0.07 | 231 | 231 | 231 |

## Where the verdicts diverge

- Top-10 by HHI_WGI but not by HHI: Cobalt
- Top-10 by HHI but not by HHI_WGI: Cesium
- Largest rises under HHI_WGI (rank HHI → HHI_WGI): Tantalum 127→58 (HHI 2,500); Diamond (industrial) 132→82 (HHI 2,415); Chromium oxide 122→84 (HHI 2,550); Chromium 112→78 (HHI 2,621); Tin 210→180 (HHI 1,324); Tantalum oxide 157→130 (HHI 2,012); Nickel 95→70 (HHI 2,807); Ammonium sulfate 137→114 (HHI 2,389)
- Top-10 by HHI_HDI but not by HHI: Cobalt, Iridium, Platinum
- Top-10 by HHI but not by HHI_HDI: Bismuth, Cesium, Tungsten
- Largest rises under HHI_HDI (rank HHI → HHI_HDI): Tantalum 127→19 (HHI 2,500); Tantalum oxide 157→52 (HHI 2,012); Tin 210→127 (HHI 1,324); Manganese 149→77 (HHI 2,081); Diamond (industrial) 132→70 (HHI 2,415); Ammonium sulfate 137→79 (HHI 2,389); Chromium oxide 122→65 (HHI 2,550); Silicon 194→138 (HHI 1,651)

Neodymium: HHI 5,808 (rank 16), HHI_WGI 3.12 (rank 16), HHI_HDI 1.21 (rank 16); 14 technologies.
