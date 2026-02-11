#!/usr/bin/env python3
"""
Post-processing script to normalize component names across STDN output CSVs.

This script:
1. Loads component names from specified CSV files
2. Checks existing canonical vocabulary for known mappings
3. Sends unknown names to LLM for normalization
4. Updates the canonical vocabulary with new mappings
5. Writes normalized CSVs to output/normalized/ directory
6. Writes a normalization manifest JSON capturing batch metadata for traceability

Manifest:
- By default, writes a JSON manifest into the output directory (default: output/normalized/)
  that records:
  - timestamp
  - glob pattern used
  - input CSV list
  - output CSV list
  - vocab path and vocab size before/after
  - counts of unique components, cached vs unknown
  - number of new mappings added
  - model used for LLM normalization

Usage:
    # Normalize all raw output files
    python scripts/normalize_outputs.py --pattern "output/raw/stdns_output_*.csv"

    # Normalize specific config group
    python scripts/normalize_outputs.py --pattern "output/raw/stdns_output_d3d3v3_*.csv"

    # Dry run (preview changes)
    python scripts/normalize_outputs.py --pattern "output/raw/*.csv" --dry-run

    # Custom vocabulary path
    python scripts/normalize_outputs.py --pattern "output/raw/*.csv" --vocab data/my_vocab.json
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
from pydantic import BaseModel, Field
from pydantic_ai import Agent

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from stdn_agentic.normalization.canonical_vocab import CanonicalVocab

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# LLM normalization prompt with material-relevant specificity
NORMALIZATION_SYSTEM_PROMPT = """You are a component name normalizer for supply chain analysis.

Your task is to map raw component names to canonical forms while preserving material-relevant specificity.

RULES:
1. Consolidate naming variations to a single canonical form
   - "Li-ion Battery", "Lithium Ion Battery", "Battery Pack (Li-ion)" → "Lithium-ion Battery"
   - "LCD Panel", "LCD Display", "Liquid Crystal Display" → "LCD Display"
   - "CPU", "Central Processing Unit", "Processor" → "CPU"

2. PRESERVE material-relevant distinctions - these affect supply chain materials:
   - Battery chemistry: Lithium-ion, Lead-acid, NiMH, LFP, Solid-state
   - Display technology: OLED, LCD, LED, Mini-LED, Micro-LED
   - Semiconductor type: Silicon, GaN, SiC when specified
   - Memory type: DRAM, NAND Flash, NOR Flash, SRAM

3. AVOID overly generic names:
   - Do NOT use just "Battery" - specify chemistry if known
   - Do NOT use just "Display" - specify technology if known
   - Do NOT use just "Chip" - specify function (Memory Chip, Power IC, etc.)

4. Use Title Case for canonical names (e.g., "Lithium-ion Battery", "OLED Display")

5. Output must be in English only. Translate non-English names.

For each input name, output the canonical form it should map to."""


class ComponentMapping(BaseModel):
    """LLM output model for component name mappings."""

    mappings: Dict[str, str] = Field(
        description="Dict mapping each input component name to its canonical form"
    )


async def normalize_with_llm(
    unknown_names: List[str],
    model: str = "anthropic:claude-sonnet-4-20250514",
    batch_size: int = 100,
) -> Dict[str, str]:
    """
    Use LLM to normalize unknown component names in batches.

    Args:
        unknown_names: List of component names not in vocab
        model: Model identifier to use
        batch_size: Number of names to process per LLM call

    Returns:
        Dict mapping raw names to canonical names
    """
    if not unknown_names:
        return {}

    logger.info(
        f"Sending {len(unknown_names)} unknown names to LLM for normalization (batch size: {batch_size})"
    )

    all_mappings: Dict[str, str] = {}

    # Process in batches
    for i in range(0, len(unknown_names), batch_size):
        batch = unknown_names[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(unknown_names) + batch_size - 1) // batch_size

        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} names)")

        names_list = "\n".join(f"- {name}" for name in batch)
        prompt = f"Normalize these component names to canonical forms:\n\n{names_list}"

        agent = Agent(
            model=model,
            output_type=ComponentMapping,
            system_prompt=NORMALIZATION_SYSTEM_PROMPT,
        )

        try:
            result = await agent.run(prompt)
            if result and result.output:
                mappings = result.output.mappings
                logger.info(f"  Batch {batch_num}: LLM returned {len(mappings)} mappings")
                all_mappings.update(mappings)
            else:
                # Fallback for this batch
                logger.warning(f"  Batch {batch_num}: No output, using basic normalization")
                for name in batch:
                    all_mappings[name] = name.strip().title()
        except Exception as e:
            logger.error(f"  Batch {batch_num} failed: {e}")
            # Fallback for this batch
            for name in batch:
                all_mappings[name] = name.strip().title()

    logger.info(f"Total mappings from LLM: {len(all_mappings)}")

    # Consolidation pass: merge remaining semantic duplicates across batches
    unique_canonicals = list(set(all_mappings.values()))
    if len(unique_canonicals) > 1:
        logger.info(
            f"Running consolidation pass on {len(unique_canonicals)} unique canonical names..."
        )
        consolidated = await consolidate_canonical_names(unique_canonicals, model)

        # Update mappings to use consolidated names
        if consolidated:
            updates = 0
            for raw_name, canonical in all_mappings.items():
                if canonical in consolidated and consolidated[canonical] != canonical:
                    all_mappings[raw_name] = consolidated[canonical]
                    updates += 1
            logger.info(f"Consolidation updated {updates} mappings")

    return all_mappings


async def consolidate_canonical_names(
    canonical_names: List[str],
    model: str = "anthropic:claude-sonnet-4-20250514",
    batch_size: int = 150,
    max_iterations: int = 3,
) -> Dict[str, str]:
    """
    Consolidate canonical names by merging remaining semantic duplicates.

    Runs multiple iterations until no more consolidations are found or max iterations reached.

    Args:
        canonical_names: List of canonical names to consolidate
        model: Model identifier to use
        batch_size: Number of names to process per LLM call
        max_iterations: Maximum consolidation iterations

    Returns:
        Dict mapping old canonical names to consolidated canonical names
    """
    if len(canonical_names) <= 1:
        return {}

    consolidation_prompt = """You are consolidating component names that were normalized in separate batches.

Some semantically equivalent components may have been given different canonical names because they were processed separately.

TASK: Review these canonical component names and identify any that refer to the SAME component type. Map duplicates to a single canonical form.

RULES:
1. Merge obvious duplicates:
   - "Application Processor" and "Application Processor (SoC)" and "System-on-Chip" → pick ONE canonical form
   - "Camera" and "Camera Module" and "Camera Sensor Module" → pick ONE canonical form
   - "Display Module" and "Display Panel" and "OLED Display" → pick ONE canonical form

2. PRESERVE material-relevant distinctions:
   - Keep "Lithium-ion Battery" separate from generic "Battery" if both exist (prefer specific)
   - Keep "OLED Display" vs "LCD Display" if both exist (different materials)

3. When merging, prefer:
   - More specific names over generic (e.g., "Lithium-ion Battery" over "Battery")
   - Standard industry terminology
   - Names that indicate the material composition

4. If a name is already optimal, map it to itself.

Output a mapping where EVERY input name appears as a key, mapped to its consolidated canonical form."""

    all_mappings: Dict[str, str] = {name: name for name in canonical_names}
    current_names = canonical_names.copy()

    for iteration in range(max_iterations):
        if len(current_names) <= 1:
            break

        logger.info(f"  Consolidation iteration {iteration + 1}: {len(current_names)} unique names")

        iteration_mappings: Dict[str, str] = {}

        # Process in batches
        for i in range(0, len(current_names), batch_size):
            batch = current_names[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(current_names) + batch_size - 1) // batch_size

            names_list = "\n".join(f"- {name}" for name in batch)
            prompt = f"Consolidate these canonical component names:\n\n{names_list}"

            agent = Agent(
                model=model,
                output_type=ComponentMapping,
                system_prompt=consolidation_prompt,
            )

            try:
                result = await agent.run(prompt)
                if result and result.output:
                    for k, v in result.output.mappings.items():
                        iteration_mappings[k] = v
                else:
                    # Keep names as-is if no output
                    for name in batch:
                        iteration_mappings[name] = name
            except Exception as e:
                logger.error(f"    Consolidation batch {batch_num}/{total_batches} failed: {e}")
                for name in batch:
                    iteration_mappings[name] = name

        # Count consolidations in this iteration
        consolidations = sum(1 for k, v in iteration_mappings.items() if k != v)
        logger.info(f"    Iteration {iteration + 1}: {consolidations} names consolidated")

        if consolidations == 0:
            logger.info("    No more consolidations found, stopping")
            break

        # Update all_mappings: follow the chain
        for original, current in all_mappings.items():
            if current in iteration_mappings:
                all_mappings[original] = iteration_mappings[current]

        # Get new unique names for next iteration
        current_names = list(set(all_mappings.values()))

    # Count total consolidations
    total_consolidated = sum(1 for k, v in all_mappings.items() if k != v)
    logger.info(f"  Total consolidations: {total_consolidated}")

    return all_mappings


def extract_components_from_csvs(csv_files: List[Path]) -> Set[str]:
    """
    Extract unique component names from CSV files.

    Args:
        csv_files: List of CSV file paths

    Returns:
        Set of unique component names
    """
    all_components: Set[str] = set()

    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path)
            if "component" in df.columns:
                components = df["component"].dropna().unique()
                all_components.update(components)
        except Exception as e:
            logger.warning(f"Error reading {csv_path}: {e}")

    return all_components


def normalize_csv_file(
    csv_path: Path,
    mappings: Dict[str, str],
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Apply normalization mappings to a single CSV file.

    Args:
        csv_path: Path to input CSV
        mappings: Dict mapping raw names to canonical names
        output_dir: Directory for normalized output (default: output/normalized)

    Returns:
        Path to output file
    """
    df = pd.read_csv(csv_path)

    if "component" not in df.columns:
        logger.warning(f"No 'component' column in {csv_path}, skipping")
        return csv_path

    # Create lowercase lookup for case-insensitive matching
    lower_mappings = {k.lower(): v for k, v in mappings.items()}

    # Apply normalization
    original_components = df["component"].copy()
    df["component"] = df["component"].apply(
        lambda x: lower_mappings.get(str(x).lower(), x) if pd.notna(x) else x
    )

    # Count changes
    changes = (original_components != df["component"]).sum()

    # Determine output path
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / csv_path.name
    else:
        # Default: output/normalized/
        default_output_dir = Path("output/normalized")
        default_output_dir.mkdir(parents=True, exist_ok=True)
        output_path = default_output_dir / csv_path.name

    df.to_csv(output_path, index=False)
    logger.info(f"Wrote {output_path} ({changes} components normalized)")

    return output_path


async def main():
    parser = argparse.ArgumentParser(
        description="Normalize component names across STDN output CSVs"
    )
    parser.add_argument(
        "--pattern",
        type=str,
        required=True,
        help="Glob pattern for CSV files (e.g., 'output/stdns_output_*.csv')",
    )
    parser.add_argument(
        "--vocab",
        type=str,
        default="data/component_canonical_vocab.json",
        help="Path to canonical vocabulary JSON file",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="openai:gpt-4.1-mini",
        help="Model to use for LLM normalization",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/normalized",
        help="Directory for normalized output files (default: output/normalized)",
    )
    parser.add_argument(
        "--manifest-path",
        type=str,
        default="",
        help=(
            "Optional path for normalization manifest JSON. "
            "If not provided, writes to <output-dir>/normalization_manifest_<timestamp>.json"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be normalized without writing files",
    )
    parser.add_argument(
        "--show-mappings",
        action="store_true",
        help="Print all mappings after normalization",
    )

    args = parser.parse_args()

    # Find CSV files
    csv_files = [Path(p) for p in sorted(glob(args.pattern))]
    if not csv_files:
        logger.error(f"No files found matching pattern: {args.pattern}")
        sys.exit(1)

    logger.info(f"Found {len(csv_files)} CSV files matching pattern")

    # Establish output dir early (used for default manifest path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load canonical vocabulary
    vocab = CanonicalVocab(args.vocab)
    vocab_size_before = len(vocab.mappings)
    logger.info(f"Loaded vocab with {vocab_size_before} existing mappings")

    # Extract all unique component names
    all_components = extract_components_from_csvs(csv_files)
    logger.info(f"Found {len(all_components)} unique component names across all files")

    # Check which names are already in vocab
    cached, unknown = vocab.lookup_batch(list(all_components))
    logger.info(f"  - {len(cached)} already in vocab")
    logger.info(f"  - {len(unknown)} need LLM normalization")

    if args.dry_run:
        print("\n=== DRY RUN ===")
        print(f"\nFiles to process: {len(csv_files)}")
        for f in csv_files:
            print(f"  - {f}")
        print(f"\nUnique components: {len(all_components)}")
        print(f"Already in vocab: {len(cached)}")
        print(f"Need LLM normalization: {len(unknown)}")
        if unknown:
            print("\nComponents needing normalization:")
            for name in sorted(unknown):
                print(f"  - {name}")
        return

    # Normalize unknown names with LLM
    new_mappings: Dict[str, str] = {}
    if unknown:
        new_mappings = await normalize_with_llm(unknown, model=args.model)
        vocab.add_mappings(new_mappings)
        vocab.save()
        logger.info(f"Added {len(new_mappings)} new mappings to vocab")

    # Build complete mapping (cached + new)
    all_mappings = {**{name: cached[name] for name in cached}, **new_mappings}

    # Also add identity mappings for canonical names (in case they appear as-is)
    for canonical in set(all_mappings.values()):
        if canonical.lower() not in all_mappings:
            all_mappings[canonical] = canonical

    # Apply normalization to each CSV
    logger.info(f"\nNormalizing CSV files to {output_dir}...")
    written_csvs: List[Path] = []
    for csv_path in csv_files:
        out_path = normalize_csv_file(
            csv_path,
            all_mappings,
            output_dir=output_dir,
        )
        written_csvs.append(out_path)

    # Write manifest (only for non-dry-run runs)
    manifest = {
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pattern": args.pattern,
        "model": args.model,
        "vocab_path": args.vocab,
        "vocab_size_before": vocab_size_before,
        "vocab_size_after": len(vocab.mappings),
        "unique_components_total": len(all_components),
        "cached_components_count": len(cached),
        "unknown_components_count": len(unknown),
        "new_mappings_added": len(new_mappings),
        "input_csvs": [str(p) for p in csv_files],
        "output_csvs": [str(p) for p in written_csvs],
    }

    if args.manifest_path.strip():
        manifest_path = Path(args.manifest_path)
    else:
        manifest_path = (
            output_dir
            / f"normalization_manifest_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        )

    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Wrote normalization manifest: {manifest_path}")
    except Exception as e:
        logger.error(f"Failed to write normalization manifest to {manifest_path}: {e}")

    # Print summary
    print("\n=== NORMALIZATION COMPLETE ===")
    print(f"Files processed: {len(csv_files)}")
    print(f"Total vocab size: {len(vocab.mappings)}")
    print(f"New mappings added: {len(new_mappings)}")

    if args.show_mappings:
        print("\n=== ALL MAPPINGS ===")
        for raw, canonical in sorted(vocab.mappings.items()):
            print(f"  {raw} → {canonical}")


if __name__ == "__main__":
    asyncio.run(main())
