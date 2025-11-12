#!/usr/bin/env python3
"""
Main execution script for STDN generation using Pydantic AI agents

This module handles:
- Configuration file discovery and loading
- CLI argument parsing
- Country data generation (optional)
- Multi-technology orchestration
- Output file writing and reporting

For government/policy work, this ensures:
- Reproducible runs with saved configuration
- Trackable technology processing with timing
- Detailed debate transcripts for policy review
- Clear audit trail of all decisions
"""

import argparse
import asyncio
import csv
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pydantic_ai import RunUsage

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
    5. System config directory

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

    # Priority 3-5: Search standard locations
    locations = [
        ".config.json",
        ".config/config.json",
    ]

    # Add home directory locations
    home = Path.home()
    locations.extend(
        [
            home / ".stdn_pydantic_ai" / "config.json",
            home / "stdn_pydantic_ai" / "config.json",
        ]
    )

    # Add system locations (Unix-like systems)
    if os.name != "nt":  # Not Windows
        locations.append("/etc/stdn_pydantic_ai/config.json")
    else:  # Windows
        locations.append("C:\\ProgramData\\pydantic_ai\\config.json")

    for loc in locations:
        if os.path.exists(loc):
            print(f"Found config file: {loc}")
            return str(loc)

    # No config found
    raise FileNotFoundError(
        f"No config file found. Searched locations:\n"
        f"  {chr(10).join(f'  - {loc}' for loc in locations)}\n\n"
        f"Specify config file with -i flag or set STDN_CONFIG environment variable."
    )


# ============================================================================
# Processing Functions
# ============================================================================


async def process_all_technologies(
    config: ConfigModel,
) -> list:
    """
    Main function to process all technologies in the tech list.

    Args:
        config: Configuration model with paths and settings

    Returns:
        List of successfully processed technology results
    """
    print(f"\n{'=' * 80}")
    print(f"STDN Generation Started: {datetime.now()}")
    print(f"{'=' * 80}\n")

    # Read debate settings from environment
    enable_debate = os.getenv("ENABLE_DEBATE", "false").lower() == "true"
    max_debate_rounds = int(os.getenv("MAX_DEBATE_ROUNDS", "3"))
    convergence_threshold = float(os.getenv("CONVERGENCE_THRESHOLD", "0.8"))
    save_transcripts = os.getenv("SAVE_TRANSCRIPTS", "true").lower() == "true"

    # Initialize orchestrator WITH debate settings
    orchestrator = STDNOrchestrator(
        config,
        enable_debate=enable_debate,
        max_debate_rounds=max_debate_rounds,
        convergence_threshold=convergence_threshold,
        save_transcripts=save_transcripts,
    )

    if enable_debate:
        print(f"\n🎤 Multi-agent debate ENABLED:")
        print(f"   Max rounds: {max_debate_rounds}")
        print(f"   Convergence threshold: {convergence_threshold}")
        print(f"   Save transcripts: {save_transcripts}\n")

    # Load technologies from CSV
    tech_list_path = Path(config.import_tech_list)
    if not tech_list_path.exists():
        print(f"Error: Technology list not found: {tech_list_path}")
        return []

    technologies = []
    with open(tech_list_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        technologies = list(reader)

    print(f"Loaded {len(technologies)} technologies from {tech_list_path}\n")

    # Process each technology
    results = []
    usage = RunUsage()

    for i, tech_row in enumerate(technologies, 1):
        tech = tech_row.get("tech", "")
        role = tech_row.get("role", "analyst")
        domain = tech_row.get("domain", "technology")

        if not tech:
            print(f"⚠️  Skipping row {i}: missing 'tech' column")
            continue

        try:
            # Process technology through orchestrator
            result = await orchestrator.process_technology(
                tech=tech,
                role=role,
                domain=domain,
                usage=usage,
            )

            if result:
                results.append(result)

                # Write result immediately to CSV (incremental output)
                orchestrator.write_csv_output([result], start_new_file=(i == 1))

                print(f"✓ Successfully processed: {tech}")
            else:
                print(f"✗ Failed to process: {tech}")

        except Exception as e:
            print(f"❌ Error processing {tech}: {e}")
            import traceback

            traceback.print_exc()
            continue

    # Print summary
    print(f"\n{'=' * 80}")
    print(f"STDN Generation Completed: {datetime.now()}")
    print(f"{'=' * 80}\n")

    print(f"Successfully processed: {len(results)}/{len(technologies)} technologies")

    if results:
        print(f"\n✓ Output saved to: {orchestrator.output_file}")
        if enable_debate and save_transcripts:
            print(f"✓ Debate transcripts saved to: ./src/stdn_agentic/debate_transcripts/results/")
    else:
        print("\nWarning: No technologies were successfully processed.")

    print(f"\nUsage: {usage}")

    return results


# ============================================================================
# Country Data Generation
# ============================================================================


async def generate_country_data(
    config: ConfigModel,
) -> None:
    """
    Generate or update country data repository.

    Args:
        config: Configuration model with country generation settings
    """
    print(f"\nGenerating country data repository in {config.country_data_mode.upper()} mode...")

    # Import here to avoid circular dependency
    from stdn_agentic.data import CountryDataRepository

    repository = CountryDataRepository(config)
    await repository.generate_country_data(
        output_file=config.materials_top_countries_repository,
        mode=config.country_data_mode,
        specific_materials=config.materials_to_update,
    )

    print("Country data generation complete!")


# ============================================================================
# Entry Point
# ============================================================================


def main():
    """
    Main entry point for the CLI application.

    Handles:
    - Configuration file discovery
    - Command-line argument parsing
    - Optional country data generation
    - Technology processing orchestration
    """
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description=("Create STDNs based on a list of technologies using Pydantic AI agents")
    )

    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        required=False,
        help="JSON configuration file with technology list, model, and output settings",
    )

    parser.add_argument(
        "--generate-countries",
        action="store_true",
        help="Generate country data repository before processing technologies",
    )

    parser.add_argument(
        "--country-mode",
        type=str,
        choices=["full", "incremental", "update"],
        help="Country generation mode: full (rebuild), incremental (add new), update (specific materials)",
    )

    parser.add_argument(
        "--update-materials",
        type=str,
        nargs="+",
        help="Specific materials to update for --country-mode update",
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
        return 1

    # Override config with CLI arguments
    if args.country_mode:
        config_data["country_data_mode"] = args.country_mode

    if args.update_materials:
        config_data["materials_to_update"] = args.update_materials

    if args.generate_countries:
        config_data["generate_country_data"] = True

    # Create config model
    try:
        config = ConfigModel(**config_data)
    except Exception as e:
        print(f"Error validating configuration: {e}")
        return 1

    # Generate country data if requested
    if config.generate_country_data:
        try:
            asyncio.run(generate_country_data(config))
        except Exception as e:
            print(f"Error during country data generation: {e}")
            return 1

        # If only generating countries, exit
        if not find_config_file(config.import_tech_list).exists():
            print("No technology list found. Country data generation complete.")
            return 0

    # Process all technologies
    try:
        results = asyncio.run(process_all_technologies(config))
        if not results:
            print("Warning: No technologies were successfully processed.")
            return 1
    except Exception as e:
        print(f"Error during technology processing: {e}")
        return 1

    print(f"✓ Successfully processed {len(results)} technologies")
    return 0


# ============================================================================
# Utility Functions
# ============================================================================


def tech_list_exists(tech_list_path: str) -> bool:
    """
    Check if technology list file exists and is not empty.

    Args:
        tech_list_path: Path to technology list CSV

    Returns:
        True if file exists and has content, False otherwise
    """
    if not os.path.exists(tech_list_path):
        return False

    try:
        df = pd.read_csv(tech_list_path)
        return len(df) > 0
    except Exception:
        return False


if __name__ == "__main__":
    exit(main())
