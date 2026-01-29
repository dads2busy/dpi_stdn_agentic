#!/usr/bin/env python3
"""
Convert existing debate transcripts to the new enhanced format.

This script upgrades v1 transcripts to v2 format by:
1. Adding version metadata
2. Computing support analysis for each round
3. Adding structured critique data
4. Computing round-over-round changes

Usage:
    python scripts/convert_transcripts.py [--input-dir DIR] [--output-dir DIR] [--dry-run]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def normalize_component_name(name: str) -> str:
    """Normalize component name for comparison."""
    if not name:
        return ""
    normalized = name.lower().strip()
    normalized = normalized.replace("-", " ").replace("_", " ")
    return " ".join(normalized.split())


def compute_support_analysis(
    proposals: Dict[str, List[Dict[str, Any]]], num_agents: int = 3
) -> Dict[str, Any]:
    """Compute support level analysis for proposals."""
    comp_support: Dict[str, Dict[str, Any]] = {}

    for agent_id, agent_props in proposals.items():
        for prop in agent_props:
            if isinstance(prop, dict):
                name = prop.get("component", prop.get("name", ""))
                confidence = prop.get("confidence", 0.8)
            else:
                continue

            if not name:
                continue

            norm = normalize_component_name(name)
            if norm not in comp_support:
                comp_support[norm] = {
                    "display_name": name,
                    "agents": set(),
                    "confidences": [],
                }
            comp_support[norm]["agents"].add(agent_id)
            comp_support[norm]["confidences"].append(confidence)

    consensus_items = []
    majority_items = []
    isolated_items = []

    for norm_name, data in comp_support.items():
        support_count = len(data["agents"])
        if support_count == num_agents:
            consensus_items.append(norm_name)
        elif support_count > num_agents / 2:
            majority_items.append(norm_name)
        else:
            isolated_items.append(norm_name)

    return {
        "consensus": consensus_items,
        "majority": majority_items,
        "isolated": isolated_items,
    }


def compute_round_changes(
    current: Dict[str, List[Dict]], previous: Optional[Dict[str, List[Dict]]]
) -> Optional[Dict[str, Any]]:
    """Compute changes between rounds."""
    if not previous:
        return None

    def get_components(proposals: Dict[str, List[Dict]]) -> set:
        comps = set()
        for agent_props in proposals.values():
            for prop in agent_props:
                if isinstance(prop, dict):
                    name = prop.get("component", prop.get("name", ""))
                    if name:
                        comps.add(normalize_component_name(name))
        return comps

    current_comps = get_components(current)
    previous_comps = get_components(previous)

    return {
        "items_added": list(current_comps - previous_comps),
        "items_removed": list(previous_comps - current_comps),
        "confidence_changes": {},
    }


def generate_structured_critiques(
    proposals: Dict[str, List[Dict]], round_num: int, num_agents: int = 3
) -> List[Dict[str, Any]]:
    """Generate structured critique data."""
    support = compute_support_analysis(proposals, num_agents)
    critiques = []

    # Create critique entries for isolated items
    for item in support.get("isolated", []):
        critiques.append(
            {
                "item_name": item,
                "support_level": "isolated",
                "supporting_agents": [],
                "opposing_agents": [],
                "avg_confidence": 0.0,
                "critique_text": f"Isolated proposal '{item}' needs peer support.",
            }
        )

    # Create entries for consensus items
    for item in support.get("consensus", []):
        critiques.append(
            {
                "item_name": item,
                "support_level": "consensus",
                "supporting_agents": [],
                "opposing_agents": [],
                "avg_confidence": 0.0,
                "critique_text": f"Strong consensus on '{item}'.",
            }
        )

    return critiques


def convert_transcript(transcript: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a v1 transcript to v2 format."""
    # Check if already v2
    if transcript.get("version") == "2.0":
        print("  Already v2 format, skipping conversion")
        return transcript

    # Extract existing data
    technology = transcript.get("technology", "Unknown")
    tech_spec = transcript.get("technology_specification", technology)
    tech_reasoning = transcript.get("technology_reasoning", "")
    timestamp = transcript.get("timestamp", datetime.now().isoformat())

    # Get phase data
    phase1 = transcript.get("phase1_initial_proposals", [])
    phase2 = transcript.get("phase2_debate_rounds", [])
    phase3 = transcript.get("phase3_final_consensus", {})

    # Determine number of agents
    num_agents = len(phase1) if phase1 else 3

    # Convert debate rounds to enhanced format
    enhanced_rounds = []
    previous_proposals = None

    for round_data in phase2:
        round_num = round_data.get("round_num", 0)
        convergence = round_data.get("convergence", 0.0)
        proposals = round_data.get("proposals", {})
        threshold = 0.75

        # Compute support analysis
        support_analysis = compute_support_analysis(proposals, num_agents)

        # Compute changes from previous round
        changes = compute_round_changes(proposals, previous_proposals)

        # Generate structured critiques
        structured_critiques = generate_structured_critiques(proposals, round_num, num_agents)

        enhanced_round = {
            "round_num": round_num,
            "convergence": convergence,
            "threshold": threshold,
            "threshold_reached": convergence >= threshold,
            "proposals": proposals,
            "rounds_completed": round_data.get("rounds_completed", round_num),
            "support_analysis": support_analysis,
            "critiques": structured_critiques,
            "changes_from_previous": changes,
        }
        enhanced_rounds.append(enhanced_round)
        previous_proposals = proposals

    # Build v2 transcript
    v2_transcript = {
        "version": "2.0",
        "metadata": {
            "technology": technology,
            "technology_specification": tech_spec,
            "technology_reasoning": tech_reasoning,
            "timestamp": timestamp,
            "format_version": "2.0",
            "converted_from": "1.0",
            "conversion_date": datetime.now().isoformat(),
        },
        "config": {
            "num_agents": num_agents,
            "max_rounds": len(phase2) if phase2 else 3,
            "convergence_threshold": 0.75,
        },
        "component_stage": {
            "phase1_initial_proposals": phase1,
            "phase2_debate_rounds": enhanced_rounds,
            "phase3_final_consensus": phase3,
        },
        # Preserve materials debate if present
        "materials_debate": transcript.get("materials_debate"),
    }

    return v2_transcript


def regenerate_txt_transcript(transcript: Dict[str, Any], txt_path: Path) -> bool:
    """Regenerate the TXT transcript file from converted JSON."""
    try:
        TRANSCRIPT_WIDTH = 80

        with open(txt_path, "w") as f:
            metadata = transcript.get("metadata", {})
            technology = metadata.get("technology", "Unknown")
            tech_spec = metadata.get("technology_specification", technology)
            tech_reasoning = metadata.get("technology_reasoning", "")
            timestamp = metadata.get("timestamp", "")

            config = transcript.get("config", {})
            num_agents = config.get("num_agents", 3)

            component_stage = transcript.get("component_stage", {})
            agent_responses = component_stage.get("phase1_initial_proposals", [])
            debate_history = component_stage.get("phase2_debate_rounds", [])
            final_consensus = component_stage.get("phase3_final_consensus", {})

            # ===== HEADER =====
            f.write("=" * TRANSCRIPT_WIDTH + "\n")
            f.write(f"STDN ANALYSIS: {technology}\n")
            f.write(f"Generated: {timestamp}\n")
            f.write("Format: v2.0 (converted)\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n")

            # ===== LEGEND =====
            f.write("\nLEGEND\n")
            f.write("-" * TRANSCRIPT_WIDTH + "\n")
            f.write("Support Levels:\n")
            f.write("  [C] CONSENSUS  - All agents agree (3/3)\n")
            f.write("  [M] MAJORITY   - Majority agrees (2/3)\n")
            f.write("  [I] ISOLATED   - Single agent only (1/3)\n")
            f.write("\nConfidence Scale: 0.0-1.0 (higher = more certain)\n")

            # ===== TECHNOLOGY SPECIFICATION =====
            f.write("\n" + "=" * TRANSCRIPT_WIDTH + "\n")
            f.write("TECHNOLOGY SPECIFICATION\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n\n")
            f.write(f"Query: {technology}\n")
            f.write(f"Specification: {tech_spec}\n")
            if tech_reasoning:
                f.write(f"\nReasoning: {tech_reasoning}\n")

            # ===== STAGE 1: COMPONENT EXTRACTION =====
            f.write("\n" + "=" * TRANSCRIPT_WIDTH + "\n")
            f.write("STAGE 1: COMPONENT EXTRACTION\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n")

            # Round 1: Initial Proposals
            f.write("\nROUND 1: Independent Proposals\n")
            f.write("-" * TRANSCRIPT_WIDTH + "\n")

            for idx, response in enumerate(agent_responses):
                agent_id = response.get("agent_id", f"Agent_{idx + 1}")
                components = response.get("components", [])

                f.write(f"\n{agent_id}:\n")
                for comp in components[:8]:  # Limit display
                    if isinstance(comp, dict):
                        name = comp.get("name", comp.get("component", str(comp)))
                        confidence = comp.get("confidence", 0.0)
                        f.write(f"  - {name} ({confidence:.2f})\n")
                    else:
                        f.write(f"  - {comp}\n")
                if len(components) > 8:
                    f.write(f"  ... and {len(components) - 8} more\n")

            # Subsequent rounds with enhanced data
            for round_data in debate_history:
                round_num = round_data.get("round_num", 0)
                if round_num <= 1:
                    continue

                convergence = round_data.get("convergence", 0.0)
                threshold = round_data.get("threshold", 0.75)
                threshold_reached = round_data.get("threshold_reached", False)

                f.write(
                    f"\nROUND {round_num}: {'Consensus Reached' if threshold_reached else 'Refinement'}\n"
                )
                f.write("-" * TRANSCRIPT_WIDTH + "\n")
                f.write(f"Convergence: {convergence:.1%}")
                if threshold_reached:
                    f.write(" (threshold reached)\n")
                else:
                    f.write(f" (threshold: {threshold:.0%})\n")

                # Show changes from previous round
                changes = round_data.get("changes_from_previous")
                if changes:
                    added = changes.get("items_added", [])
                    removed = changes.get("items_removed", [])
                    if added or removed:
                        f.write("\nChanges from Previous Round:\n")
                        if added:
                            f.write(f"  + Added: {', '.join(added[:5])}")
                            if len(added) > 5:
                                f.write(f" (+{len(added) - 5} more)")
                            f.write("\n")
                        if removed:
                            f.write(f"  - Removed: {', '.join(removed[:5])}")
                            if len(removed) > 5:
                                f.write(f" (+{len(removed) - 5} more)")
                            f.write("\n")

                # Show support analysis
                support = round_data.get("support_analysis", {})
                if support:
                    f.write("\nSupport Analysis:\n")
                    consensus = support.get("consensus", [])
                    majority = support.get("majority", [])
                    isolated = support.get("isolated", [])

                    if consensus:
                        f.write(f"  [C] Consensus ({len(consensus)} items)\n")
                    if majority:
                        f.write(f"  [M] Majority ({len(majority)} items)\n")
                    if isolated:
                        f.write(f"  [I] Isolated ({len(isolated)} items) - need peer support\n")

            # ===== FINAL CONSENSUS =====
            f.write("\n" + "=" * TRANSCRIPT_WIDTH + "\n")
            f.write("FINAL CONSENSUS: Components\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n\n")

            if isinstance(final_consensus, dict):
                consensus_comps = final_consensus.get("components", [])
                num_rounds = final_consensus.get("rounds", len(debate_history))
                overall_confidence = final_consensus.get("confidence", 0.0)
            else:
                consensus_comps = final_consensus if isinstance(final_consensus, list) else []
                num_rounds = len(debate_history)
                overall_confidence = 0.0

            f.write(f"Rounds Completed: {num_rounds}\n")
            f.write(f"Final Convergence: {overall_confidence:.1%}\n")
            f.write(f"Components Selected: {len(consensus_comps)}\n\n")

            for i, comp in enumerate(consensus_comps, 1):
                if isinstance(comp, dict):
                    name = comp.get("name", comp.get("component", str(comp)))
                    confidence = comp.get("confidence", 0.0)
                    f.write(f"  {i}. {name} ({confidence:.2f})\n")
                else:
                    f.write(f"  {i}. {comp}\n")

            # ===== FOOTER =====
            f.write("\n" + "=" * TRANSCRIPT_WIDTH + "\n")
            f.write("END OF TRANSCRIPT (v2.0 format)\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n")

        return True

    except Exception as e:
        print(f"  WARNING: Could not regenerate TXT: {e}")
        return False


def process_file(input_path: Path, output_path: Path, dry_run: bool = False) -> bool:
    """Process a single transcript file."""
    print(f"Processing: {input_path.name}")

    try:
        with open(input_path) as f:
            transcript = json.load(f)

        converted = convert_transcript(transcript)

        if dry_run:
            print(f"  Would write to: {output_path}")
            return True

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(converted, f, indent=2, default=str)

        print(f"  Converted JSON: {output_path}")

        # Also regenerate the TXT file with the new format
        txt_path = output_path.with_suffix(".txt")
        if regenerate_txt_transcript(converted, txt_path):
            print(f"  Regenerated TXT: {txt_path}")

        return True

    except json.JSONDecodeError as e:
        print(f"  ERROR: Invalid JSON - {e}")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Convert debate transcripts to enhanced v2 format")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("src/stdn_agentic/debate_transcripts/results"),
        help="Directory containing transcripts to convert",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: overwrite in place)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Convert a single file instead of directory",
    )

    args = parser.parse_args()

    if args.file:
        # Single file mode
        input_path = args.file
        output_path = args.output_dir / args.file.name if args.output_dir else input_path
        success = process_file(input_path, output_path, args.dry_run)
        sys.exit(0 if success else 1)

    # Directory mode
    input_dir = args.input_dir
    output_dir = args.output_dir or input_dir

    if not input_dir.exists():
        print(f"ERROR: Input directory does not exist: {input_dir}")
        sys.exit(1)

    json_files = list(input_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {input_dir}")
        sys.exit(0)

    print(f"Found {len(json_files)} JSON files to process")
    if args.dry_run:
        print("DRY RUN - no changes will be made\n")

    success_count = 0
    error_count = 0

    for json_file in sorted(json_files):
        output_path = output_dir / json_file.name
        if process_file(json_file, output_path, args.dry_run):
            success_count += 1
        else:
            error_count += 1

    print(f"\nSummary: {success_count} converted, {error_count} errors")
    sys.exit(0 if error_count == 0 else 1)


if __name__ == "__main__":
    main()
