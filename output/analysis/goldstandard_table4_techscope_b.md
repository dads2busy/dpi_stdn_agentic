# Table 4 (revision): judge validation against the gold standard, techscope pass b

Judge recall: annotator items judged as written. Precision: pipeline canonicals (v1v1v1 + d3v1v1) the judge accepts that match a gold item (gold mapped with the same per-technology vocab), lower bound.

| Technology | Gold items | Judge recall | Pipeline components (accepted) | Matched gold | Lower-bound precision | Gold canonicals |
|---|---|---|---|---|---|---|
| Pharmaceutical Lyophilizer | 15 | 0.933 | 11 (11) | 7 | 0.636 | 8 |
| Rotary tablet press | 21 | 1.000 | 11 (11) | 8 | 0.727 | 9 |
| Single-use bioreactor | 16 | 0.750 | 9 (9) | 8 | 0.889 | 8 |
| Smartphone | 37 | 0.865 | 7 (7) | 7 | 1.000 | 7 |
| **Pooled** | 89 | 0.888 | 38 (38) | 30 | 0.789 | 32 |
| **Mean of technologies** | | 0.887 | | | 0.813 | |

Gold items the judge rejected: Pharmaceutical Lyophilizer: Heat transfer fluid, Single-use bioreactor: Optional systems for pH, temperature, sterilzation, modulation, Single-use bioreactor: Tubing, Single-use bioreactor: Vent heater jack, Single-use bioreactor: Stainless Steel tote, Smartphone: Board-to-board connectors, Smartphone: Buttons, Smartphone: GPS, Smartphone: metal–oxide–semiconductor, Smartphone: barometers

Accepted pipeline components with no gold match (counted as false positives):
- Pharmaceutical Lyophilizer: Chassis And Structural Frame, Condensate Drain And Collection System, Door And Sealing System, Product Loading And Unloading System
- Rotary tablet press: Compression Rollers, Lubrication System, Tablet Discharge and Ejection System
- Single-use bioreactor: Sampling and Addition Ports
- Smartphone: none
