# Canonical Vocab v1.0 → v1.1 Refinements

**Date:** 2026-05-12
**Scope:** Targeted re-mappings to preserve dependency-relevant sub-types for Communications Sustainability paper vignette technologies (EV Traction Inverter, 5G Base Station Macro Cell). Does NOT broaden vocab; only retargets specific variants from generic canonicals to more-specific canonicals.
**Rationale:** Phase 2 vignette construction surfaced unexpected critical materials: silicon carbide and barium titanate for EV Traction Inverter; gallium arsenide for 5G Base Station. Investigation revealed a specific vocab over-collapse for 5G: "remote radio unit" collapsed to generic "Radio Unit", while the more specific "Remote Radio Unit (RRU)" canonical was already present and does preserve the GaN dependency story when the materials stage processes it. A separate but related over-collapse exists for permanent-magnet motor components (see below). Both are fixed here.

**Source of truth CSV:** `output/normalized/stdns_output_d5v1v1_20260414_165728.csv` (d5v1v1 run, 300 EV rows, 100 5G rows; most data-rich single-file snapshot of v1.0 outputs for these two technologies).

---

## Diagnosis Summary

### EV Traction Inverter

**Canonical components in existing runs (all d5v1v1):**
- AC Output Filter and Protection Module
- Cabinet Enclosure
- Cable Harness
- Control Electronics Module
- Cooling Solution / Cooling System
- DC Link Capacitors
- Driver Electronics Module
- Power Amplifier Module
- Power Semiconductor Module (IGBT or SiC MOSFET)
- Power Semiconductor Module (IGBT or SiC)
- Power Semiconductor Module (IGBT)
- Power Semiconductor Modules (IGBT or SiC MOSFET)
- Printed Circuit Board (PCB) Assembly
- Sensors and Instrumentation
- Structural Enclosure and Chassis

**Materials surfaced:** Silicon carbide (from Power Semiconductor Module), Barium titanate (from DC Link Capacitors), Aluminum, Copper, Silicon, Polypropylene, Epoxy resins.

**Key finding:** No "Rotor Assembly" or permanent-magnet component was extracted for EV Traction Inverter in ANY run across ALL config types (v1v1v1, d2–d5). This is technically correct: an EV traction inverter is the power electronics unit that drives the motor — it does NOT contain permanent magnets or rotors. Those are in the motor itself. The SiC and barium titanate story accurately describes an inverter's real critical-material dependencies (wide-bandgap semiconductors and high-capacitance MLCCs). The "expected" rare-earth story would apply to an EV traction MOTOR, not an inverter.

**Conclusion:** The plan's "smoking gun" (permanent magnet rotor assembly → Rotor Assembly) is a genuine vocab over-collapse, but it does NOT affect the EV Traction Inverter vignette. No amount of vocab refinement will cause the EV Traction Inverter pipeline to extract rotor/NdFeB components, because the component extraction stage never proposes them (correctly). The EV Traction Inverter vignette's critical-material story (SiC for switching, barium titanate for DC link MLCCs) is factually accurate and does NOT need remediation.

The permanent magnet variants ARE fixed here anyway, because they represent genuine over-collapses for other technologies (electric motors, wind turbine generators) and it is correct maintenance — just not the vignette fix the plan anticipated.

### 5G Base Station Macro Cell

**Canonical components in existing runs (all d5v1v1):**
- Antenna System
- Backhaul/Transport Interface Module
- Baseband Unit (BBU)
- Cabinet Enclosure
- Clock and Timing Module
- Control Electronics Module
- Cooling Solution
- Power Supply Module
- Radio Unit
- Remote Radio Unit (RRU)
- Structural Enclosure and Chassis

**Materials surfaced:** Gallium arsenide (from Radio Unit, Remote Radio Unit), Silicon, Aluminum, Copper, Gold, Ceramic, Quartz.

**Key finding:** "Remote Radio Unit (RRU)" appears as a canonical in the vocab (from variant `'remote radio unit (rru'`), and when materials extraction processes it, GaN (gallium nitride) does appear in some runs (d3v1v1). However, the bare variant `'remote radio unit'` maps to the generic `'Radio Unit'` canonical — this IS a vocab over-collapse. When material extraction sees "Radio Unit" instead of "Remote Radio Unit (RRU)", it assigns gallium arsenide (GaAs) rather than gallium nitride (GaN). This distinction matters: the 5G PA story the paper wants to tell involves GaN (the dominant modern PA technology for macro-cell base stations), not GaAs (which is older legacy).

**Over-collapse identified:**
- `'remote radio unit'` → `'Radio Unit'` — should map to `'Remote Radio Unit (RRU)'`
- `'remote radio head'` → `'Radio Unit'` — should map to `'Remote Radio Head (RRH)'` (the RRH already has its own canonical with 7 variants; `'remote radio head'` mistakenly went to the generic instead)

---

## Refinements Applied

### EV Traction Inverter — Permanent Magnet Motor Variants

These fix a real over-collapse in the vocab, though it does not affect the EV Traction Inverter vignette. It WILL benefit any future technology runs involving electric motors, wind turbine generators, or other permanent-magnet machines.

| Variant | v1.0 canonical | v1.1 canonical | Rationale |
|---|---|---|---|
| `permanent magnet rotor assembly` | `Rotor Assembly` | `Permanent Magnet Rotor Assembly` | Preserves NdFeB/rare-earth dependency signal; motors with permanent magnets have fundamentally different material supply chains than induction motor rotors |
| `rotor assembly (permanent magnet rotor` | `Rotor Assembly` | `Permanent Magnet Rotor Assembly` | Same; truncated variant from LLM normalization |
| `rotor assembly (with permanent magnets` | `Rotor Assembly` | `Permanent Magnet Rotor Assembly` | Same |
| `rotor with permanent magnets` | `Rotor Assembly` | `Permanent Magnet Rotor Assembly` | Same |

`Permanent Magnet Rotor Assembly` is a NEW canonical introduced by v1.1 (did not exist in v1.0's 652 canonicals).

### 5G Base Station Macro Cell — Radio Unit Variants

| Variant | v1.0 canonical | v1.1 canonical | Rationale |
|---|---|---|---|
| `remote radio unit` | `Radio Unit` | `Remote Radio Unit (RRU)` | The RRU is a distinct sub-system (integrated PA+antenna+transceiver) with a different material profile than a generic "Radio Unit"; preserves GaN dependency signal |
| `remote radio head` | `Radio Unit` | `Remote Radio Head (RRH)` | The RRH is another distinct sub-system (similar role to RRU but different vendor terminology); already has its own canonical (`Remote Radio Head (RRH)`) with 7 other variants mapped to it; this was an erroneous mapping to the generic |

These two are RETARGETINGS to existing canonicals, not new canonicals. Total canonical count is expected to increase by exactly 1 (the new `Permanent Magnet Rotor Assembly`).

---

## Refinements NOT Made

| Expected refinement | Finding | Reason not applied |
|---|---|---|
| `gallium nitride power amplifier` → `GaN Power Amplifier Module` | No such variant exists in v1.0 vocab | The vocab has no GaN-specific PA variant to retarget; would require adding new variant+canonical, which is beyond targeted retargeting scope |
| `tantalum capacitor` → `Tantalum Capacitor` | No such variant exists in v1.0 vocab | No tantalum-qualified capacitor variant in v1.0; additionally, tantalum does NOT appear in any existing 5G Base Station run's materials, so this is a materials-extraction-stage gap, not a vocab over-collapse |
| EV Traction Inverter rare-earth/NdFeB | No rotor or permanent magnet component extracted for EV Inverter in any run | An EV traction inverter does not contain permanent magnets; the pipeline correctly models inverter (power electronics) components, not motor components; vocab fix cannot change this |

---

## Impact Assessment

After v1.1 is applied:
- Vocab mapping count: 6,677 (unchanged — only retargetings, no additions/deletions)
- Canonical count: 653 (was 652; +1 for new `Permanent Magnet Rotor Assembly`)
- EV Traction Inverter vignette: will produce same SiC/barium titanate story; permanent magnet fix does not affect it because those components are never extracted for this technology
- 5G Base Station vignette (after re-run with v1.1): `remote radio unit` raw components will normalize to `Remote Radio Unit (RRU)` canonical, which has a better chance of eliciting GaN from the materials extraction stage (consistent with what d3v1v1 already produces when the pipeline does extract that canonical)
- Future motor/generator technologies: will correctly preserve NdFeB/rare-earth signal via `Permanent Magnet Rotor Assembly`

**Important note for Task 3 (pipeline re-run):** The EV Traction Inverter vignette story needs to be re-framed in the paper. The SiC and barium titanate findings are factually correct for an inverter. If the paper's intended narrative requires rare-earth magnets, the technology should be "EV Traction Motor" not "EV Traction Inverter." The vocab refinement alone will not change the EV Inverter vignette's critical-material story.
