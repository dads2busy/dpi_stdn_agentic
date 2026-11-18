# LLM Judge Validation Against Gold Standard

- **Date**: 2026-11-18 13:59
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Pipeline configs**: d3v1v1, v1v1v1
- **Technologies**: Pharmaceutical Lyophilizer, Rotary tablet press, Single-use bioreactor, Smartphone

## Methodology

The gold standard lists known-valid primary manufacturing components per technology. Both gold standard and pipeline component names are normalized through the same canonical vocabulary. The LLM judge is run on the union of gold standard and pipeline components. Precision/recall/F1 measure how well the judge's plausibility verdicts align with gold standard membership.

**Caveat**: The gold standard may not be exhaustive. Components NOT in the gold standard that the judge labels plausible may actually be valid — the false positive count is an upper bound, and precision is a lower bound.

## Per-Technology Results

| Technology | Gold Std | Pipeline | TP | FP | TN | FN | Precision | Recall | F1 | Pipeline Recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 8 | 11 | 8 | 4 | 0 | 0 | 0.667 | 1.000 | 0.800 | 0.875 |
| Rotary tablet press | 9 | 11 | 9 | 3 | 0 | 0 | 0.750 | 1.000 | 0.857 | 0.889 |
| Single-use bioreactor | 8 | 9 | 8 | 1 | 0 | 0 | 0.889 | 1.000 | 0.941 | 1.000 |
| Smartphone | 7 | 7 | 7 | 0 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **AGGREGATE** | 32 | 38 | 32 | 8 | 0 | 0 | 0.800 | 1.000 | 0.889 | — |

## False Negatives (Gold Standard Components Judge Rejected)

These are components in the gold standard that the judge labeled implausible.

## False Positives (Pipeline-Only Components Judge Accepted)

These are components NOT in the gold standard that the judge labeled plausible. Some may actually be valid components missing from the gold standard.

### Pharmaceutical Lyophilizer

- **Chassis And Structural Frame**: The chassis and structural frame are integral to a pharmaceutical lyophilizer as they provide the main support structure for all major modules and subsystems. They are manufactured or sourced as distinct assemblies, form the core of the equipment’s architecture, and have dedicated supply chains.
- **Condensate Drain And Collection System**: The condensate drain and collection system is a primary subassembly in pharmaceutical lyophilizers, as it manages removal and storage of water vapor condensed during the freeze-drying process. It is typically procured and maintained as a distinct module with functional and regulatory importance.
- **Door And Sealing System**: The Door and Sealing System is a primary manufacturing component for a pharmaceutical lyophilizer, as it forms a major structural and functional subassembly. It maintains the vacuum seal necessary for the lyophilization process and is procured or manufactured as a distinct unit, often from specialized suppliers.
- **Product Loading And Unloading System**: The Product Loading and Unloading System is a major functional module of a pharmaceutical lyophilizer. It is a separately manufactured subassembly responsible for the automatic and sterile transfer of products into and out of the lyophilizer chamber. This system has a distinct supply chain and is critical to the operational efficiency and integrity of the lyophilization process.

### Rotary tablet press

- **Compression Rollers**: Compression rollers are a core functional component of rotary tablet presses, directly involved in forming tablets by compressing powder within dies. They are typically procured or manufactured as distinct subassemblies with their own supply chains, making them a plausible primary manufacturing component.
- **Lubrication System**: A lubrication system in a rotary tablet press is a major functional subassembly responsible for ensuring smooth operation and preventing mechanical wear. It is typically procured or manufactured as a distinct module with its own supply chain, making it a plausible primary manufacturing component.
- **Tablet Discharge and Ejection System**: The tablet discharge and ejection system is a major functional subassembly in a rotary tablet press, responsible for the controlled removal of formed tablets from the die table. It is typically manufactured and supplied as a distinct module and is essential for the operation of the press.

### Single-use bioreactor

- **Sampling and Addition Ports**: Sampling and addition ports are major functional modules in single-use bioreactors, enabling critical process operations such as aseptic sampling, reagent addition, and process monitoring. These ports are typically manufactured as integral, standardized subassemblies and sourced from specialized suppliers, forming a distinct supply chain category.

