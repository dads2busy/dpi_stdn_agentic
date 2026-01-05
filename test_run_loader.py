#!/usr/bin/env python3
"""
Test script for Run Loader implementation.

This script demonstrates loading STDN run files from the output directory
and extracting component/material data for normalization.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from stdn_agentic.normalization.run_loader import RunLoader


def print_separator(title: str = ""):
    """Print a section separator."""
    print("\n" + "=" * 80)
    if title:
        print(f" {title}")
        print("=" * 80)


def main():
    """Run the loader tests."""
    print_separator("STDN Run Loader Test")
    
    # Initialize loader
    print("\n[1] Initializing RunLoader...")
    try:
        loader = RunLoader(output_dir="./output")
        print("✓ RunLoader initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize RunLoader: {e}")
        return 1
    
    # Load all runs
    print("\n[2] Loading all run files...")
    try:
        runs = loader.load_all_runs(pattern="stdns_output_*.csv")
        print(f"✓ Loaded {len(runs)} run files")
    except Exception as e:
        print(f"✗ Failed to load runs: {e}")
        return 1
    
    if not runs:
        print("✗ No run files found")
        return 1
    
    # Display run summary
    print("\n[3] Run Summary:")
    summary = loader.get_run_summary(runs)
    print(f"  - Total runs: {summary['total_runs']}")
    print(f"  - Total components: {summary['total_components']}")
    print(f"  - Avg components/run: {summary['avg_components_per_run']:.1f}")
    print(f"  - Date range: {summary['date_range']['earliest']} to {summary['date_range']['latest']}")
    
    # Display unique technologies
    print("\n[4] Unique Technologies:")
    technologies = loader.get_unique_technologies(runs)
    for i, tech in enumerate(technologies, 1):
        print(f"  {i}. {tech}")
    
    # Display unique components
    print("\n[5] Unique Components:")
    components = loader.get_unique_components(runs)
    print(f"  Total unique component names: {len(components)}")
    if len(components) <= 20:
        for i, comp in enumerate(components, 1):
            print(f"  {i}. {comp}")
    else:
        print(f"  First 10:")
        for i, comp in enumerate(components[:10], 1):
            print(f"  {i}. {comp}")
        print(f"  ... and {len(components) - 10} more")
    
    # Display detailed info for first run
    print_separator("Sample Run Details")
    first_run = runs[0]
    print(f"\nRun ID: {first_run.run_id}")
    print(f"Timestamp: {first_run.timestamp}")
    print(f"File: {first_run.file_path.name}")
    print(f"Components: {len(first_run.components)}")
    
    # Show first component in detail
    if first_run.components:
        comp = first_run.components[0]
        print(f"\n  First Component:")
        print(f"    Technology: {comp.technology}")
        print(f"    Component: {comp.component}")
        print(f"    Confidence: {comp.component_confidence}")
        print(f"    Reasoning: {comp.component_reasoning[:100]}...")
        print(f"    Materials: {len(comp.materials)}")
        
        if comp.materials:
            mat = comp.materials[0]
            print(f"\n    First Material:")
            print(f"      Material: {mat['material']}")
            print(f"      Confidence: {mat['material_confidence']}")
            print(f"      HS Code: {mat['hs_code']}")
            print(f"      Country: {mat['country']}")
            print(f"      Amount: {mat['amount']} {mat['meas_unit']}")
    
    # Display component distribution across runs
    print_separator("Component Distribution")
    print("\nComponents per run:")
    for run in runs:
        print(f"  {run.run_id}: {len(run.components)} components")
    
    # Test JSON export
    print("\n[6] Testing JSON export...")
    try:
        run_dict = first_run.to_dict()
        print(f"✓ Successfully converted run to dictionary")
        print(f"  Keys: {list(run_dict.keys())}")
    except Exception as e:
        print(f"✗ Failed to convert to dictionary: {e}")
        return 1
    
    # Summary
    print_separator("Test Summary")
    print("\n✓ All loader tests passed!")
    print(f"\nLoader is ready to feed data into normalization pipeline.")
    print(f"Total data loaded:")
    print(f"  - {len(runs)} runs")
    print(f"  - {summary['total_components']} components")
    print(f"  - {len(technologies)} unique technologies")
    print(f"  - {len(components)} unique component names")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
