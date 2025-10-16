#!/usr/bin/env python3
"""
Main execution script for STDN generation using Pydantic AI agents
"""

import os
import asyncio
import argparse
import pandas as pd
from datetime import datetime
from pathlib import Path
from pydantic_ai import RunUsage
from dotenv import load_dotenv

from stdn_agentic.models import ConfigModel
from stdn_agentic.orchestrator import STDNOrchestrator
from stdn_agentic.country_agent import get_country_data_generator
from stdn_agentic.utils import read_json_to_dict, validate_config

# Load environment variables
load_dotenv()


def find_config_file(specified_path: str = None) -> str:
    """
    Search for config file in multiple locations.
    Priority order:
    1. Specified path (command line argument)
    2. Environment variable STDN_CONFIG
    3. Current directory
    4. User home directory
    5. System config directory
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
    
    # Priority 3: Current directory
    locations = [
        "./config.json",
        "./config/config.json",
    ]
    
    # Priority 4: User home directory
    home = Path.home()
    locations.extend([
        home / ".stdn_pydantic_ai" / "config.json",
        home / "stdn_pydantic_ai" / "config.json",
    ])
    
    # Priority 5: System config directory
    if os.name != 'nt':  # Unix-like
        locations.append("/etc/stdn_pydantic_ai/config.json")
    else:  # Windows
        locations.append("C:\\ProgramData\\stdn_pydantic_ai\\config.json")
    
    # Search all locations
    for loc in locations:
        if os.path.exists(loc):
            print(f"Found config file: {loc}")
            return str(loc)
    
    raise FileNotFoundError(
        "No config file found. Searched locations:\n" +
        "\n".join(f"  - {loc}" for loc in locations) +
        "\n\nPlease specify config file with -i flag or set STDN_CONFIG environment variable."
    )


async def process_all_technologies(config: ConfigModel):
    """Main function to process all technologies"""
    print(f"Start: {datetime.now()}")
    
    # Initialize orchestrator
    orchestrator = STDNOrchestrator(config)
    
    # Load technology list
    tech_list_df = pd.read_csv(config.import_tech_list)
    
    # Track usage across all runs
    usage = RunUsage()
    
    # Process each technology
    results = []
    for idx, row in tech_list_df.iterrows():
        result = await orchestrator.process_technology(
            tech=row['tech'],
            role=row['role'],
            domain=row['domain'],
            usage=usage
        )
        if result:
            results.append(result)
    
    # Write outputs
    orchestrator.write_csv_output(results, start_new_file=True)
    orchestrator.write_timing_csv(results)
    
    print(f"\nTotal Usage: {usage}")
    print(f"End: {datetime.now()}")
    
    return results


async def generate_country_data(config: ConfigModel):
    """Generate country data repository"""
    mode = config.country_data_mode
    
    print(f"Generating country data repository in {mode.upper()} mode...")
    
    generator = get_country_data_generator(config)
    await generator.generate_country_data(
        output_file=config.materials_top_countries_repository,
        mode=mode,
        specific_materials=config.materials_to_update
    )
    
    print(f"Country data generation complete!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Create STDNs based on a list of technologies using Pydantic AI agents"
    )
    parser.add_argument(
        '-i', '--inputfile',
        type=str,
        required=False,
        help="JSON configuration file with technology list, model, and output settings"
    )
    parser.add_argument(
        '--generate-countries',
        action='store_true',
        help="Generate country data repository before processing technologies"
    )
    parser.add_argument(
        '--country-mode',
        type=str,
        choices=['full', 'incremental', 'update'],
        help="Country generation mode: full (rebuild), incremental (add new), update (specific materials)"
    )
    parser.add_argument(
        '--update-materials',
        type=str,
        nargs='+',
        help="Specific materials to update (for --country-mode update)"
    )
    
    args = parser.parse_args()
    
    # Find config file
    config_file = find_config_file(args.inputfile)
    print(f"Loading configuration from: {config_file}")
    
    # Load and validate config
    config_data = read_json_to_dict(config_file)
    config_data = validate_config(config_data)
    
    # Override config with CLI arguments
    if args.generate_countries:
        config_data['generate_country_data'] = True
    
    if args.country_mode:
        config_data['country_data_mode'] = args.country_mode
    
    if args.update_materials:
        config_data['materials_to_update'] = args.update_materials
    
    config = ConfigModel(**config_data)
    
    # Generate country data if requested
    if config.generate_country_data:
        asyncio.run(generate_country_data(config))
        
        # If only generating countries, exit after completion
        if not tech_list_exists(config.import_tech_list):
            print("No technology list found. Country data generation complete.")
            return None
    
    # Run async pipeline
    results = asyncio.run(process_all_technologies(config))
    
    return results


def tech_list_exists(tech_list_path: str) -> bool:
    """Check if technology list file exists and is not empty"""
    if not os.path.exists(tech_list_path):
        return False
    
    try:
        df = pd.read_csv(tech_list_path)
        return len(df) > 0
    except:
        return False


if __name__ == "__main__":
    main()
