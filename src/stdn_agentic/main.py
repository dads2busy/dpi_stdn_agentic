#!/usr/bin/env python3
"""
Main execution script for STDN generation using Pydantic AI agents
"""

import asyncio
import argparse
import pandas as pd
from datetime import datetime
from pydantic_ai import RunUsage

from .models import ConfigModel
from .orchestrator import STDNOrchestrator
from .utils import read_json_to_dict, validate_config


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


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Create STDNs based on a list of technologies using Pydantic AI agents"
    )
    parser.add_argument(
        '-i', '--inputfile',
        type=str,
        required=True,
        help="JSON configuration file with technology list, model, and output settings"
    )
    
    args = parser.parse_args()
    
    # Load and validate config
    config_data = read_json_to_dict(args.inputfile)
    config_data = validate_config(config_data)
    config = ConfigModel(**config_data)
    
    # Run async pipeline
    results = asyncio.run(process_all_technologies(config))
    
    return results


if __name__ == "__main__":
    main()
