#!/usr/bin/env python3
"""
Main execution script for STDN generation using Pydantic AI agents

This module handles:
- Configuration file discovery and loading
- CLI argument parsing
- Technology processing orchestration
- Output file writing

The enhanced version uses STDNOrchestrator's internal run_pipeline method
which handles CSV writing automatically.
"""

import argparse
import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from stdn_agentic.models import ConfigModel
from stdn_agentic.orchestrator import STDNOrchestrator
from stdn_agentic.utils import read_json_to_dict, validate_config

# Load environment variables
load_dotenv()


# ============================================================================
# Configuration File Discovery
# ============================================================================


def find_config_file(specified_path: str | None = None) -> str:
    """
    Search for config file in multiple locations.

    Priority order:
    1. Specified path (command line argument)
    2. Environment variable STDN_CONFIG
    3. Current directory
    4. User home directory

    Args:
        specified_path: Optional explicit path from command line

    Returns:
        Path to found config file

    Raises:
        FileNotFoundError: If no config file found in any location
    """
    # Priority 1: Explicit path provided
    if specified_path:
        if os.path.exists(specified_path):
            return specified_path
        else:
            raise FileNotFoundError(f"Config file not found: {specified_path}")

    # Priority 2: Environment variable
    env_config = os.environ.get("STDN_CONFIG")
    if env_config and os.path.exists(env_config):
        print(f"Using config from STDN_CONFIG: {env_config}")
        return env_config

    # Priority 3: Search standard locations
    locations = [
        "config.json",
        ".config.json",
        ".config/config.json",
    ]

    # Add home directory locations (convert Path to str)
    home = Path.home()
    locations.extend(
        [
            str(home / ".stdn" / "config.json"),
            str(home / "stdn" / "config.json"),
        ]
    )

    for loc in locations:
        if os.path.exists(loc):
            print(f"Found config file: {loc}")
            return str(loc)

    # No config found
    raise FileNotFoundError(
        f"No config file found. Searched locations:\n"
        f"{chr(10).join(f'  - {loc}' for loc in locations)}\n\n"
        f"Specify config file with -i flag or set STDN_CONFIG environment variable."
    )


# ============================================================================
# Main Processing Function
# ============================================================================


async def process_all_technologies(config: ConfigModel) -> dict:
    """
    Process all technologies using the enhanced orchestrator.

    Args:
        config: Configuration model with paths and settings

    Returns:
        Dict with processing statistics
    """
    # Read debate settings from environment or config
    enable_debate = os.getenv("ENABLE_DEBATE", "false").lower() == "true"
    enable_material_debate = os.getenv("ENABLE_MATERIAL_DEBATE", "false").lower() == "true"
    enable_country_debate = os.getenv("ENABLE_COUNTRY_DEBATE", "false").lower() == "true"
    max_debate_rounds = int(os.getenv("MAX_DEBATE_ROUNDS", "3"))
    convergence_threshold = float(os.getenv("CONVERGENCE_THRESHOLD", "0.8"))
    save_transcripts = os.getenv("SAVE_TRANSCRIPTS", "true").lower() == "true"
    debate_top_p = float(os.getenv("DEBATE_TOP_P", "0.0001"))

    # Initialize enhanced orchestrator
    orchestrator = STDNOrchestrator(
        config,
        enable_debate=enable_debate,
        enable_material_debate=enable_material_debate,
        enable_country_debate=enable_country_debate,
        max_debate_rounds=max_debate_rounds,
        convergence_threshold=convergence_threshold,
        save_transcripts=save_transcripts,
        debate_top_p=debate_top_p,
    )

    # Load technologies from config
    tech_list_path = Path(config.tech_list_path)
    if not tech_list_path.exists():
        raise FileNotFoundError(f"Technology list not found: {tech_list_path}")

    # Read full CSV data including role
    import csv

    tech_data = []
    with open(tech_list_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "tech" in row and row["tech"]:
                tech_data.append(
                    {
                        "tech": row["tech"].strip(),
                        "role": row.get("role", "supply chain analyst").strip(),
                        "domain": row.get("domain", "technology").strip(),
                    }
                )

    print(f"{'=' * 80}")
    print(f"STDN Generation Started: {datetime.now()}")
    print(f"{'=' * 80}")

    if enable_debate:
        print("🔄 Multi-agent debate ENABLED")
        print(f"📊 Max rounds: {max_debate_rounds}")
        print(f"🎯 Convergence threshold: {convergence_threshold}")
        print(f"💾 Save transcripts: {save_transcripts}")

    print(f"\n📋 {len(tech_data)} technologies from {config.tech_list_path}\n")

    # ✅ Call run_pipeline with tech list that will be processed with roles
    # We need to modify this to process individually OR modify run_pipeline
    # Let's use the simpler approach: call run_pipeline for each tech

    successful = 0
    failed = 0

    # Initialize the CSV file with headers
    import csv as csv_module

    with open(orchestrator.output_file, "w", newline="") as f:
        writer = csv_module.DictWriter(
            f,
            fieldnames=[
                "technology",
                "component",
                "component_confidence",
                "component_reasoning",
                "material",
                "material_confidence",
                "material_reasoning",
                "hs_code",
                "country",
                "meas_unit",
                "amount",
                "percentage",
                "country_confidence",
                "country_reasoning",
            ],
        )
        writer.writeheader()

    # Process each technology with its specific role
    for tech_info in tech_data:
        tech = tech_info["tech"]
        role = tech_info["role"]
        domain = tech_info["domain"]

        # ✅ Use run_pipeline with single technology and specific role
        result = await orchestrator.run_pipeline(
            technologies=[tech],
            role=role,  # ✅ Use role from CSV
            domain=domain,  # ✅ Use domain from CSV
        )

        if result["successful"] > 0:
            successful += 1
        else:
            failed += 1

    print(f"\n{'=' * 80}")
    print(f"STDN Generation Completed: {datetime.now()}")
    print(f"{'=' * 80}")
    print(f"Successfully processed: {successful}/{len(tech_data)} technologies")
    print(f"Output saved to: {orchestrator.output_file}")

    if enable_debate and orchestrator.reporter:
        print(f"Debate transcripts saved to: {orchestrator.reporter.output_dir}")

    return {
        "successful": successful,
        "failed": failed,
        "total": len(tech_data),
        "output_file": orchestrator.output_file,
    }


# ============================================================================
# Entry Point
# ============================================================================


def main():
    """
    Main entry point for the CLI application.

    Handles:
    - Configuration file discovery
    - Command-line argument parsing
    - Technology processing orchestration
    """
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description="Create STDNs based on a list of technologies using Pydantic AI agents"
    )

    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        required=False,
        help="JSON configuration file with technology list, model, and output settings",
    )

    args = parser.parse_args()

    # Find and load configuration
    try:
        config_file = find_config_file(args.input_file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    print(f"Loading configuration from: {config_file}\n")

    try:
        config_data = read_json_to_dict(config_file)
        config_data = validate_config(config_data)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # Create config model
    try:
        config = ConfigModel(**config_data)
    except Exception as e:
        print(f"Error validating configuration: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # Process all technologies
    try:
        results = asyncio.run(process_all_technologies(config))

        if results["successful"] == 0:
            print("\nWarning: No technologies were successfully processed.")
            return 1

        print(f"\n✓ Successfully processed {results['successful']}/{results['total']} technologies")
        return 0

    except Exception as e:
        print(f"\nError during technology processing: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
