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


def find_config_file(specified_path: str = None) -> str:
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

    # Add home directory locations
    home = Path.home()
    locations.extend(
        [
            home / ".stdn" / "config.json",
            home / "stdn" / "config.json",
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

    The new orchestrator handles CSV writing internally via run_pipeline(),
    so we don't need separate write_csv_output calls.

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

    # Read tech list
    import csv

    technologies = []
    with open(tech_list_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "tech" in row and row["tech"]:
                technologies.append(row["tech"].strip())

    # Run the pipeline (handles everything internally)
    results = await orchestrator.run_pipeline(
        technologies=technologies,
        role="supply chain analyst",
        domain="technology",
    )

    return results


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
