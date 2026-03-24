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


def _parse_bool(value: str | bool | None, default: bool) -> bool:
    """Parse a boolean value from string, bool, or None."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.lower() == "true"


async def process_all_technologies(config: ConfigModel, cli_args: argparse.Namespace) -> dict:
    """Process all technologies using the enhanced orchestrator.

    Args:
        config: Configuration model with paths and settings
        cli_args: Parsed command-line arguments (can override env vars)

    Returns:
        Dict with processing statistics
    """
    # Get values from CLI args first, fall back to env vars, then defaults
    # CLI args are None if not specified, so we check for that

    # Debate toggles
    if cli_args.enable_component_debate is not None:
        enable_debate = cli_args.enable_component_debate
    else:
        enable_debate = os.getenv("ENABLE_COMPONENT_DEBATE", "false").lower() == "true"

    if cli_args.enable_material_debate is not None:
        enable_material_debate = cli_args.enable_material_debate
    else:
        enable_material_debate = os.getenv("ENABLE_MATERIAL_DEBATE", "false").lower() == "true"

    if cli_args.enable_country_debate is not None:
        enable_country_debate = cli_args.enable_country_debate
    else:
        enable_country_debate = os.getenv("ENABLE_COUNTRY_DEBATE", "true").lower() == "true"

    if cli_args.enable_process_consumables is not None:
        enable_process_consumables = cli_args.enable_process_consumables
    else:
        enable_process_consumables = getattr(config, 'enable_process_consumables', False)

    # Store resolved value back on config so orchestrator can read it
    config.enable_process_consumables = enable_process_consumables

    if cli_args.process_consumables_model is not None:
        config.process_consumables_model = cli_args.process_consumables_model

    # Number of agents
    if cli_args.num_agents_component is not None:
        num_agents_component = cli_args.num_agents_component
    else:
        num_agents_component = int(os.getenv("NUM_AGENTS_COMPONENT", 3))

    if cli_args.num_agents_material is not None:
        num_agents_material = cli_args.num_agents_material
    else:
        num_agents_material = int(os.getenv("NUM_AGENTS_MATERIAL", 3))

    if cli_args.num_agents_country is not None:
        num_agents_country = cli_args.num_agents_country
    else:
        num_agents_country = int(os.getenv("NUM_AGENTS_COUNTRY", 3))

    # Debate parameters
    if cli_args.max_debate_rounds is not None:
        max_debate_rounds = cli_args.max_debate_rounds
    else:
        max_debate_rounds = int(os.getenv("MAX_DEBATE_ROUNDS", 3))

    if cli_args.convergence_threshold is not None:
        convergence_threshold = cli_args.convergence_threshold
    else:
        convergence_threshold = float(os.getenv("CONVERGENCE_THRESHOLD", 0.8))

    if cli_args.save_transcripts is not None:
        save_transcripts = cli_args.save_transcripts
    else:
        save_transcripts = os.getenv("SAVE_TRANSCRIPTS", "true").lower() == "true"

    orchestrator = STDNOrchestrator(
        config,
        enable_debate=enable_debate,
        enable_material_debate=enable_material_debate,
        enable_country_debate=enable_country_debate,
        num_agents_component=num_agents_component,
        num_agents_material=num_agents_material,
        num_agents_country=num_agents_country,
        max_debate_rounds=max_debate_rounds,
        convergence_threshold=convergence_threshold,
        save_transcripts=save_transcripts,
        # enable_process_consumables is stored on config; will be wired in Task 5
    )

    tech_list_path = Path(config.tech_list_path)
    if not tech_list_path.exists():
        raise FileNotFoundError(f"Technology list not found: {tech_list_path}")

    # Load technologies with their specific roles and domains
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

    # Build mappings for per-technology roles and domains
    technologies = [t["tech"] for t in tech_data]
    tech_roles = {t["tech"]: t["role"] for t in tech_data}
    tech_domains = {t["tech"]: t["domain"] for t in tech_data}

    # Call run_pipeline ONCE with all technologies and their role/domain mappings
    result = await orchestrator.run_pipeline(
        technologies=technologies,
        role="supply chain analyst",  # Default fallback
        domain="technology",  # Default fallback
        tech_roles=tech_roles,  # ← Per-tech role mapping
        tech_domains=tech_domains,  # ← Per-tech domain mapping
    )

    return {
        "successful": result["successful"],
        "failed": result["failed"],
        "total": len(tech_data),
        "output_file": orchestrator.output_file,
    }


# ============================================================================
# Entry Point
# ============================================================================


def _str_to_bool(value: str) -> bool:
    """Convert string to boolean for argparse."""
    if value.lower() in ("true", "1", "yes", "on"):
        return True
    elif value.lower() in ("false", "0", "no", "off"):
        return False
    else:
        raise argparse.ArgumentTypeError(f"Boolean value expected, got '{value}'")


def main():
    # Log effective retries for pydantic_ai Agents (used by agent factory functions)
    # This is controlled via env var to avoid threading config through every agent constructor.
    effective_retries = os.environ.get("STDN_AGENT_RETRIES", "").strip() or "5"
    print(f"[stdn] STDN_AGENT_RETRIES={effective_retries}")

    # Log where model configuration will come from. Agents may use:
    # - per-agent models from config (component_model/materials_model/country_model), OR
    # - STDN_MODEL from environment (often set via .env), OR
    # - fallbacks (e.g., OLLAMA_MODEL) if neither is set.
    env_stdn_model = os.environ.get("STDN_MODEL", "").strip()
    env_ollama_model = os.environ.get("OLLAMA_MODEL", "").strip()
    print(
        "[stdn] model sources: "
        f"STDN_MODEL={'<set>' if env_stdn_model else '<unset>'}, "
        f"OLLAMA_MODEL={'<set>' if env_ollama_model else '<unset>'}"
    )
    if env_stdn_model:
        print(f"[stdn] STDN_MODEL={env_stdn_model}")

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

    # Debate toggle arguments
    parser.add_argument(
        "--enable-component-debate",
        type=_str_to_bool,
        default=None,
        metavar="BOOL",
        help="Enable multi-agent debate for component extraction (default: from .env or false)",
    )
    parser.add_argument(
        "--enable-material-debate",
        type=_str_to_bool,
        default=None,
        metavar="BOOL",
        help="Enable multi-agent debate for material extraction (default: from .env or false)",
    )
    parser.add_argument(
        "--enable-country-debate",
        type=_str_to_bool,
        default=None,
        metavar="BOOL",
        help="Enable multi-agent voting for country data (default: from .env or false)",
    )
    parser.add_argument(
        "--enable-process-consumables",
        type=_str_to_bool,
        default=None,
        metavar="BOOL",
        help="Enable Stage 2b: process consumables extraction (default: from config or false)",
    )
    parser.add_argument(
        "--process-consumables-model",
        type=str,
        default=None,
        metavar="MODEL",
        help="Model for process consumables agents (defaults to main model)",
    )

    # Number of agents arguments
    parser.add_argument(
        "--num-agents-component",
        type=int,
        default=None,
        metavar="N",
        help="Number of agents for component debate (default: from .env or 3)",
    )
    parser.add_argument(
        "--num-agents-material",
        type=int,
        default=None,
        metavar="N",
        help="Number of agents for material debate (default: from .env or 3)",
    )
    parser.add_argument(
        "--num-agents-country",
        type=int,
        default=None,
        metavar="N",
        help="Number of agents for country voting (default: from .env or 3)",
    )

    # Debate parameters
    parser.add_argument(
        "--max-debate-rounds",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of debate rounds (default: from .env or 3)",
    )
    parser.add_argument(
        "--convergence-threshold",
        type=float,
        default=None,
        metavar="FLOAT",
        help="Convergence threshold for debate (default: from .env or 0.8)",
    )
    parser.add_argument(
        "--save-transcripts",
        type=_str_to_bool,
        default=None,
        metavar="BOOL",
        help="Save debate transcripts (default: from .env or true)",
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

    # Log which model configuration is present in config vs environment.
    # This helps diagnose surprises where STDN_MODEL in .env overrides expectations.
    print(
        "[stdn] config models: "
        f"model={getattr(config, 'model', None)!r}, "
        f"component_model={getattr(config, 'component_model', None)!r}, "
        f"materials_model={getattr(config, 'materials_model', None)!r}, "
        f"country_model={getattr(config, 'country_model', None)!r}"
    )
    env_stdn_model = os.environ.get("STDN_MODEL", "").strip()
    if env_stdn_model:
        print(
            "[stdn] NOTE: STDN_MODEL is set in the environment; "
            "any agent factory that does not receive an explicit model may default to it."
        )

    # Process all technologies
    try:
        results = asyncio.run(process_all_technologies(config, args))

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
