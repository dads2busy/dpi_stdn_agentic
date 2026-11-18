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
| Pharmaceutical Lyophilizer | 8 | 15 | 8 | 7 | 0 | 0 | 0.533 | 1.000 | 0.696 | 1.000 |
| Rotary tablet press | 9 | 12 | 9 | 3 | 0 | 0 | 0.750 | 1.000 | 0.857 | 1.000 |
| Single-use bioreactor | 8 | 9 | 8 | 1 | 0 | 0 | 0.889 | 1.000 | 0.941 | 1.000 |
| Smartphone | 7 | 7 | 7 | 0 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **AGGREGATE** | 32 | 43 | 32 | 11 | 0 | 0 | 0.744 | 1.000 | 0.853 | — |

## False Negatives (Gold Standard Components Judge Rejected)

These are components in the gold standard that the judge labeled implausible.

## False Positives (Pipeline-Only Components Judge Accepted)

These are components NOT in the gold standard that the judge labeled plausible. Some may actually be valid components missing from the gold standard.

### Pharmaceutical Lyophilizer

- **Chassis and Structural Frame**: The chassis and structural frame of a pharmaceutical lyophilizer are critical primary components, as they form the core structural architecture housing all functional subsystems and provide mechanical support, stability, and mounting points for other major assemblies. These are typically manufactured or procured as complete subassemblies by lyophilizer OEMs.
- **Condensate Drain and Collection System**: The Condensate Drain and Collection System is a plausible primary manufacturing component for a pharmaceutical lyophilizer. It is a critical subassembly responsible for collecting and disposing of condensate generated during the freeze-drying process, typically supplied as an integrated functional module. This system has distinct supplier and maintenance considerations and is essential for the operational integrity of the lyophilizer.
- **Control System and Human-Machine Interface**: The control system and human-machine interface (HMI) are plausible primary manufacturing components for a pharmaceutical lyophilizer. These assemblies are procured or engineered as integrated modules that manage core operational functions, user interaction, and coordination of the lyophilization process, forming a key functional subassembly.
- **Control System and Instrumentation**: The control system and instrumentation are primary components in a pharmaceutical lyophilizer as they manage, monitor, and regulate the lyophilization process. These elements are procured as major, function-specific modules with distinct supply chains and are essential for the core operation of the lyophilizer.
- **Control System and Panels**: The control system and panels are integral subassemblies for a pharmaceutical lyophilizer, managing process automation, monitoring, and safety. They are procured or manufactured as complete units, often from specialized suppliers, and represent a key functional and dependency boundary in the equipment's architecture.
- **Door and Sealing System**: The Door and Sealing System is a primary manufacturing component of a pharmaceutical lyophilizer, as it is a distinct subassembly responsible for sealing the vacuum chamber and enabling safe, sterile operation. It is typically procured or manufactured separately due to its engineering and regulatory complexity.
- **Product Loading and Unloading System**: The product loading and unloading system is a key functional subassembly in a pharmaceutical lyophilizer. It is often procured as a distinct module and is critical for automated handling of product trays before and after the freeze-drying process, typically manufactured or supplied separately from other systems.

### Rotary tablet press

- **Compression Rollers**: Compression rollers are a critical subassembly in a rotary tablet press, responsible for compressing the powder into tablets. They are procured or manufactured as distinct components, have their own supply chains, and form a core functional part of the press's operation.
- **Lubrication System**: The lubrication system is a major functional module in a rotary tablet press, ensuring smooth operation and longevity of moving parts. It is typically procured as a distinct unit with its own supply chain and maintenance requirements.
- **Punches, Die Table, and Dies**: Punches, die table, and dies are primary manufacturing components of a rotary tablet press. These components form the essential mechanism for compressing powder into tablets, have distinct supply chains, and are often procured as major subassemblies or units. They represent core functional elements of the rotary tablet press architecture.

### Single-use bioreactor

- **Sampling and Addition Ports**: Sampling and addition ports are distinct, functional subassemblies that enable critical connections for media addition and fluid sampling in single-use bioreactors. They are typically procured as specific assemblies that interface directly with bioprocessing systems, forming a core part of the bioreactor's functional design and supply chain.

