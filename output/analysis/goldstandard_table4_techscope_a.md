# Table 4 (revision): judge validation against the gold standard, techscope pass a

Judge recall: annotator items judged as written. Precision: pipeline canonicals (v1v1v1 + d3v1v1) the judge accepts that match a gold item (gold mapped with the same per-technology vocab), lower bound.

| Technology | Gold items | Judge recall | Pipeline components (accepted) | Matched gold | Lower-bound precision | Gold canonicals |
|---|---|---|---|---|---|---|
| Pharmaceutical Lyophilizer | 15 | 0.933 | 15 (15) | 8 | 0.533 | 8 |
| Rotary tablet press | 21 | 1.000 | 12 (12) | 9 | 0.750 | 9 |
| Single-use bioreactor | 16 | 0.750 | 9 (9) | 8 | 0.889 | 8 |
| Smartphone | 37 | 0.865 | 7 (7) | 7 | 1.000 | 7 |
| **Pooled** | 89 | 0.888 | 43 (43) | 32 | 0.744 | 32 |
| **Mean of technologies** | | 0.887 | | | 0.793 | |

Gold items the judge rejected: Pharmaceutical Lyophilizer: Heat transfer fluid, Single-use bioreactor: Optional systems for pH, temperature, sterilzation, modulation, Single-use bioreactor: Tubing, Single-use bioreactor: Vent heater jack, Single-use bioreactor: Stainless Steel tote, Smartphone: Board-to-board connectors, Smartphone: Buttons, Smartphone: GPS, Smartphone: metal–oxide–semiconductor, Smartphone: barometers

Accepted pipeline components with no gold match (counted as false positives):
- Pharmaceutical Lyophilizer: Chassis and Structural Frame, Condensate Drain and Collection System, Control System and Human-Machine Interface, Control System and Instrumentation, Control System and Panels, Door and Sealing System, Product Loading and Unloading System
- Rotary tablet press: Compression Rollers, Lubrication System, Punches, Die Table, and Dies
- Single-use bioreactor: Sampling and Addition Ports
- Smartphone: none
