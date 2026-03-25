# Process Consumables Extraction Stage (Stage 2b) — Design Spec

## Problem

The current STDN-GEN pipeline extracts materials that physically constitute components (Stage 2), but misses materials consumed during manufacturing processes — e.g., Helium as a carrier/purge gas in CVD and cooling medium in lithography. These process consumables represent real supply chain dependencies that the current prompt architecture systematically excludes.

## Decision Summary

| Decision | Choice | Rationale |
|---|---|---|
| Graph attachment | Technology-level (`T → M_process`) | Process consumables don't map to individual components; future-proofed for optional `C → M_process` edges later since the agent receives the component list |
| Pipeline position | Stage 2b, after Stage 1 (components) | Component context helps identify relevant manufacturing processes |
| Extraction protocol | Single extraction + judge (not debate) | Process consumables are less ambiguous than constituent materials; judge catches omissions and hallucinations at half the cost of debate |
| Judge powers | Filter + suggest | Addresses the core problem (missed materials like Helium) by allowing the judge to add items |
| Output format | Nested JSON (authoritative) with typed sections; flat CSV derived with `dependency_type` column | Clean separation of constituent vs. process consumable dependencies |

## Pipeline Integration

### Stage Ordering and Execution

```
Stage 1: Component Extraction
    ↓ (stabilized component list)
    ├── Stage 2: Constituent Materials Extraction  ─┐
    └── Stage 2b: Process Consumables Extraction  ──┤ (can run in parallel)
                                                    ↓
Stage 3: Country Assignment (receives merged material list)
Stage 4: Post-processing Normalization (handles both material types)
```

**Stages 2 and 2b can run in parallel** since neither depends on the other's output — both only require the stabilized component list from Stage 1. This is an optional performance optimization; sequential execution (2 then 2b, or vice versa) is also valid.

Stage 2b receives:
- The technology description (same input as Stage 1)
- The stabilized component list from Stage 1

Stage 2b produces:
- A set of process consumable materials with confidence scores, attached to the technology node (`T → M_process`)

**Stage 2b is single-pass** (one extraction call + one judge call). There is no debate loop and no convergence criterion — this is intentional, as process consumables are less ambiguous than constituent materials and the judge provides sufficient quality control.

### Integration with Stage 3 (Country Assignment)

Stage 3 receives a **single merged material list** combining Stage 2 constituent materials and Stage 2b process consumables. Each material carries its `dependency_type` tag. The country assignment logic (USGS-first, Borda fallback) operates identically regardless of type — the country profiling agents do not need to distinguish between constituent and process materials, since the question "who produces this material?" is the same either way. The `dependency_type` tag passes through Stage 3 unchanged and is preserved in the final output.

### Integration with Stage 4 (Normalization)

Stage 4 normalization operates on material names regardless of type. Process consumables use the same canonical vocabulary and the same rule-based → LLM semantic mapping pipeline. The normalization tuple for process consumables is `(technology, material)` rather than `(component, material)`, since there is no component association. The canonical vocabulary does not need a separate namespace — "Helium" is "Helium" whether constituent or process consumable. If a material appears as both (unlikely but possible), the two entries are distinct rows/objects distinguished by `dependency_type`.

### Error Handling

If the extraction agent returns zero process consumables, or if the judge removes all proposed items, the `process_consumables` section is emitted with an empty `materials` array. This is a valid output — some technologies may genuinely have no notable process consumables. The metadata block still logs the extraction and judge actions for auditability.

### Graph Schema Extension

Current edge set:
```
E ⊂ (T × C) ∪ (C × M) ∪ (M × P)
```

Extended edge set:
```
E ⊂ (T × C) ∪ (C × M) ∪ (T × M_proc) ∪ (M × P) ∪ (M_proc × P)
```

Where `M_proc` is a typed subset of materials with `dependency_type = "process_consumable"`.

**Note on the layering invariant:** The current STDN definition constrains edges to adjacent layers. The `T → M_proc` edge skips the component layer, which relaxes this invariant. In the paper, we handle this by defining process consumables as belonging to a distinct material sublayer that is adjacent to T (i.e., the graph has two types of material nodes at different depths). Alternatively, the paper can simply note that the strict adjacency constraint applies to constituent dependencies, while process consumable dependencies follow a shorter `T → M_proc → P` path. Either framing preserves interpretability.

## Extraction Protocol

### Step 1 — Extraction Agent

A single agent with a process-engineering role prompt proposes process consumables.

**System prompt — core framing:**

> You are a semiconductor process engineer and manufacturing chemist. Given a technology description and its component list, identify materials that are *consumed during the manufacturing process* but do *not* become part of the final product. These include process gases, etchants, solvents, photoresists, slurries, cleaning agents, cooling media, and similar consumables.
>
> Do NOT include materials that physically constitute a component — those are handled separately.

**Agent receives:**
- Technology description
- Stabilized component list from Stage 1 (as context for inferring manufacturing processes — the agent does NOT produce component-level edges)
- Materials ontology (HS-aligned) as a reference, not a hard constraint — many process consumables (photoresists, slurries, specialty gases) are not in the HS-aligned ontology; the agent should prefer ontology-aligned names when available but may propose names outside the ontology for process-specific chemicals
- Standard 7-level confidence scale

**Agent produces:**
- Set of process consumable materials, each with: name, confidence, optional grounding (text span or domain knowledge reference)
- Materials are associated with the technology only — no component-level association in the current version (future extension)

### Step 2 — Judge Agent

A separate LLM call reviews the extraction agent's proposal.

**System prompt — core framing:**

> You are a materials scientist reviewing a proposed list of manufacturing process consumables for a given technology. Your tasks:
> 1. Remove any item that is a constituent material (physically part of the product), is hallucinated, or is too generic to be actionable.
> 2. Adjust confidence scores based on how universal the consumable is for this technology class.
> 3. Add any critical process consumables that were missed. Additions must include a rationale and are capped at 0.7 confidence unless strongly justified.
>
> For each action (keep/remove/adjust/add), provide a brief justification.

**Judge receives:**
- Technology description
- Stabilized component list
- Extraction agent's full proposal
- Materials ontology

**Judge produces:**
- Revised list with per-item action labels (`keep`, `remove`, `adjust`, `add`) and justifications

**Auditability:** Both the original proposal and all judge modifications are logged in run metadata.

### Confidence Formula

The existing pipeline computes final confidence using a peer-support formula: `s_final = s_agent × (0.7 + 0.3 × n_support / N)`. Stage 2b has no multi-agent support count. Instead, the final confidence for each process consumable is simply the judge's output confidence:

- **Kept items:** the judge may accept the extractor's confidence or adjust it.
- **Added items:** capped at 0.7 unless the judge provides strong justification for a higher score.
- **No peer-support multiplier** — the extract + judge protocol is a different trust model from debate, and the confidence values reflect a single expert assessment validated by a single reviewer.

### Cost Estimate

Stage 2b requires 2 LLM calls per technology (1 extraction + 1 judge), compared to 6–9 calls for a full debate stage (3 agents × up to 3 rounds). For a batch of 26 technologies, this adds ~52 LLM calls to the pipeline.

## Output Schema

### JSON (authoritative format)

```json
{
  "technology": "Smartphone Application Processor (SoC)",
  "constituent_dependencies": {
    "components": [
      {
        "name": "Die",
        "confidence": 0.95,
        "materials": [
          {
            "name": "Silicon",
            "confidence": 0.95,
            "countries": [
              { "name": "China", "confidence": 0.92, "source": "authoritative" }
            ]
          }
        ]
      }
    ]
  },
  "process_consumables": {
    "materials": [
      {
        "name": "Helium",
        "confidence": 0.85,
        "extraction_provenance": "judge_addition",
        "rationale": "Carrier/purge gas in CVD and lithography cooling",
        "countries": [
          { "name": "United States", "confidence": 0.95, "source": "authoritative" }
        ]
      }
    ]
  },
  "metadata": {
    "run_id": "...",
    "timestamp": "...",
    "stage_2b": {
      "extractor_items": 8,
      "judge_removed": 1,
      "judge_added": 2,
      "final_items": 9
    }
  }
}
```

### CSV (derived flat format)

Adds a `dependency_type` column. The `component` column is nullable for process consumables. The CSV contains **two confidence columns** to avoid ambiguity: `material_confidence` (the material-level score from extraction/debate) and `country_confidence` (the country-level score from Stage 3):

| technology | component | material | material_confidence | country | country_confidence | source | dependency_type |
|---|---|---|---|---|---|---|---|
| Smartphone SoC | Die | Silicon | 0.95 | China | 0.92 | authoritative | constituent |
| Smartphone SoC | | Helium | 0.85 | United States | 0.95 | authoritative | process_consumable |

### Schema Notes

- **JSON schema asymmetry:** Process consumable entries include `extraction_provenance` and `rationale` fields that constituent material entries do not. This reflects the different extraction protocols (debate vs. extract+judge). JSON consumers should be aware of this type-dependent schema. A future harmonization could add `extraction_provenance: "debate_final"` to constituent materials for uniformity. Note: `extraction_provenance` (which pipeline step produced the item) is distinct from the country-level `source` field (data provenance: `authoritative` vs. Borda fallback).
- **Output authority migration:** The current pipeline treats CSV as the primary output and JSON as a secondary encoding. This spec inverts that: JSON becomes the authoritative structured output, and CSV is a derived flat view. The CSV continues to be generated for spreadsheet-oriented consumers. Existing downstream tools that consume the CSV will need to handle the new `dependency_type` column and nullable `component` field.

## Paper Changes

The following sections of the SIGIR manuscript require updates:

1. **Problem formulation** (methodology.tex, Section 2.1): Extend the STDN edge set definition to include `T × M_proc` and `M_proc × P`.
2. **Pipeline description** (methodology.tex, Section 2.2): Add Stage 2b description with extract + judge protocol.
3. **Architecture figure** (methodology.tex): Add "Process Consumables Agent" box in Layer 1 and "Judge" box in Layer 2.
4. **Agent specialization table** (methodology.tex): Add row for process consumables extractor and judge.
5. **Supplementary S.1**: Add subsections specifying extraction and judge prompt requirements.
6. **Supplementary S.6**: Document the new JSON output structure with typed sections.
7. **Supplementary graph formalism**: If the supplementary contains a parallel formal definition of the edge set, update it to match the extended formulation in the main text.
8. **Limitations** (conclusions.tex): Soften the "may omit intermediate processing steps" limitation.
9. **Case study** (case_study.tex): Re-run smartphone example showing process consumables (e.g., Helium) now surfaced.

## Known Improvements

### Material Name Quality (Stage 2b Extraction Prompts)

The extraction and judge agents produce material names with two quality issues that require post-processing normalization:

1. **Parenthetical qualifiers**: Agents append usage context to material names (e.g., "Helium (for leak testing)", "Nitrogen (inert atmosphere during soldering)"). These create hundreds of false-duplicate materials. Currently stripped in post-processing via regex.

2. **Compound material names**: Agents sometimes combine materials into a single entry (e.g., "Helium and Nitrogen gases", "Acetone and IPA", "Flux and solder paste"). These are either split into separate rows (gas combos) or merged into canonical base materials (e.g., "Adhesives and sealants" → "Adhesives") in post-processing.

**Recommended fix**: Update the Stage 2b extraction and judge system prompts to:
- Instruct agents to output **only the base material name** without parenthetical usage context
- Instruct agents to list each material as a **separate entry**, never combine multiple materials with "and"
- Provide examples of good vs. bad material names in the prompt

This would eliminate the need for ~100 lines of post-processing normalization mappings in `pipeline.py` and produce cleaner data at the source.
