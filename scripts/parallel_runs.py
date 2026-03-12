#!/usr/bin/env python3
"""
Parallel Pipeline Runs Script

Launches multiple parallel pipeline runs with validation:
1. Dynamically creates database copies and config files for each run
2. Starts each run sequentially with a delay between launches
3. Validates that output file is created before launching next run
4. Monitors that all files are growing during execution
5. Cleans up temporary database and config files after completion

Collision-proof shared-normalization mode:
- Each run config sets `output_csv_filename` to `stdns_output_{config_type}_run{N}` to avoid
  timestamp collisions when multiple runs create output files close together.
- Output directory remains shared across runs so that consolidated outputs can be normalized together.
- After ALL runs complete:
  1) raw outputs are renamed back to the standard naming by removing `_run{N}` from filenames
  2) a single shared normalization pass is run across the consolidated raw files
     (writing to output/normalized/), matching the intended “group normalization” behavior
  3) JSON files are generated from the normalized CSVs (JSON contains normalized components)

Usage:
    # Run 5 v1v1v1 runs using base config
    python scripts/parallel_runs.py --config-type v1v1v1 --num-runs 5 --base-config config.json

    # Run 5 d3d3v3 runs
    python scripts/parallel_runs.py --config-type d3d3v3 --num-runs 5 --base-config config.json

    # Custom delay between launches
    python scripts/parallel_runs.py --config-type v1v1v1 --num-runs 5 --base-config config.json --delay 15

    # Skip cleanup (keep temp files for debugging)
    python scripts/parallel_runs.py --config-type v1v1v1 --num-runs 5 --base-config config.json --no-cleanup
"""

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def get_today_date_prefix() -> str:
    """Get today's date in the format used by output files (YYYYMMDD)."""
    return datetime.now().strftime("%Y%m%d")


def find_new_output_file(
    output_dir: Path,
    filename_config_marker: str,
    date_prefix: str,
    known_files: set[str],
    run_num: int | None = None,
) -> str | None:
    """Find a newly created output file that wasn't in known_files.

    In collision-proof mode each run uses a unique output_csv_filename prefix:
      stdns_output_{config_type}_run{N}

    The orchestrator then appends:
      _{timestamp}.csv

    So for detection we must match:
      stdns_output_{filename_config_marker}_run{N}_{date_prefix}*.csv
    """
    if run_num is None:
        pattern = f"stdns_output_{filename_config_marker}_{date_prefix}*.csv"
    else:
        pattern = f"stdns_output_{filename_config_marker}_run{run_num}_{date_prefix}*.csv"

    for f in output_dir.glob(pattern):
        if f.name not in known_files:
            return f.name
    return None


def wait_for_new_file(
    output_dir: Path,
    filename_config_marker: str,
    date_prefix: str,
    known_files: set[str],
    run_num: int | None = None,
    timeout: int = 30,
    poll_interval: float = 1.0,
) -> str | None:
    """Wait for a new output file to appear, return filename or None on timeout."""
    elapsed = 0
    while elapsed < timeout:
        new_file = find_new_output_file(
            output_dir,
            filename_config_marker,
            date_prefix,
            known_files,
            run_num=run_num,
        )
        if new_file:
            return new_file
        time.sleep(poll_interval)
        elapsed += poll_interval
    return None


def check_files_growing(
    output_dir: Path, files: list[str], interval: float = 5.0
) -> dict[str, bool]:
    """
    Check if files are growing by comparing sizes before and after interval.

    Supports:
    - relative filenames (resolved against output_dir)
    - absolute/relative full paths passed in `files`
    """
    sizes_before: dict[str, int] = {}
    for f in files:
        p = Path(f)
        path = p if p.is_absolute() or p.parent != Path(".") else (output_dir / f)
        if path.exists():
            sizes_before[f] = path.stat().st_size

    time.sleep(interval)

    results: dict[str, bool] = {}
    for f in files:
        p = Path(f)
        path = p if p.is_absolute() or p.parent != Path(".") else (output_dir / f)
        if path.exists():
            size_after = path.stat().st_size
            size_before = sizes_before.get(f, 0)
            # Consider growing if size increased, or if still at header-only size (192 bytes)
            # Files at 192 bytes are waiting for first technology to complete
            results[f] = size_after > size_before or size_after == 192
        else:
            results[f] = False

    return results


def get_active_process_count(config_type: str) -> int:
    """Count active stdn processes for the given config type."""
    try:
        result = subprocess.run(
            f"ps aux | grep 'stdn -i config_{config_type}' | grep -v grep | grep -v 'uv run' | wc -l",
            shell=True,
            capture_output=True,
            text=True,
        )
        return int(result.stdout.strip())
    except (ValueError, subprocess.SubprocessError):
        return 0


def kill_all_processes(config_type: str) -> None:
    """Kill all running stdn processes for the given config type."""
    subprocess.run(f"pkill -f 'stdn -i config_{config_type}'", shell=True)
    print(f"Killed all {config_type} processes")


def create_database_copies(
    base_db_path: Path,
    num_copies: int,
    project_dir: Path,
    *,
    config_type: str,
) -> list[Path]:
    """
    Create copies of the database for parallel runs.

    IMPORTANT: Copies are config-type-specific to avoid DuckDB file lock conflicts when
    multiple configuration groups run concurrently (e.g., d3v1v1 and d5v1v1 in parallel).

    Returns list of paths to the created database copies.
    """
    db_copies = []
    base_name = base_db_path.stem  # e.g., "world_mineral_commodity_reports_2022-2025_v8"
    db_dir = base_db_path.parent

    print(f"\nCreating {num_copies} database copies from {base_db_path}...")

    for run_num in range(1, num_copies + 1):
        copy_name = f"{base_name}_{config_type}_run{run_num}.db"
        copy_path = db_dir / copy_name

        if copy_path.exists():
            print(f"  Database copy already exists: {copy_path}")
        else:
            print(f"  Creating: {copy_path}")
            shutil.copy2(base_db_path, copy_path)

        db_copies.append(copy_path)

    print(f"  Created {len(db_copies)} database copies\n")
    return db_copies


def create_config_files(
    base_config_path: Path,
    config_type: str,
    db_copies: list[Path],
    project_dir: Path,
    *,
    base_output_dir: Path,
    filename_config_marker: str | None = None,
) -> list[Path]:
    """
    Create config files for each parallel run.

    Returns list of paths to the created config files.
    """
    with open(base_config_path) as f:
        base_config = json.load(f)

    config_files = []
    print(f"Creating {len(db_copies)} config files from {base_config_path}...")

    for run_num, db_path in enumerate(db_copies, start=1):
        config_name = f"config_{config_type}_run{run_num}.json"
        config_path = project_dir / config_name

        # Create config with updated database path
        run_config = base_config.copy()

        # Store relative path for portability
        run_config["usgs_database"] = f"./{db_path.relative_to(project_dir)}"

        # Collision-proof output naming while keeping output_dir shared:
        # - Keep output_dir identical across runs so consolidated outputs can be normalized together.
        # - Make the base output name unique per run to prevent timestamp collisions.
        run_config["output_csv_filename"] = f"stdns_output_{config_type}_run{run_num}"

        # Force a shared output directory across runs (raw/ + normalized/ live under this).
        run_config["output_dir"] = f"./{base_output_dir.relative_to(project_dir)}"

        # IMPORTANT: For parallel runs, skip in-process normalization/JSON.
        # We will run one shared normalization pass after all runs finish, and generate JSON from
        # normalized CSVs then. This avoids duplicated work and races.
        run_config["skip_postprocess_normalization"] = True
        run_config["skip_json_output"] = True

        print(f"  Creating: {config_path}")
        with open(config_path, "w") as f:
            json.dump(run_config, f, indent=2)

        config_files.append(config_path)

    print(f"  Created {len(config_files)} config files\n")
    return config_files


def cleanup_temp_files(
    db_copies: list[Path],
    config_files: list[Path],
) -> None:
    """Remove temporary database copies and config files."""
    print("\nCleaning up temporary files...")

    for db_path in db_copies:
        if db_path.exists():
            print(f"  Removing: {db_path}")
            db_path.unlink()

    for config_path in config_files:
        if config_path.exists():
            print(f"  Removing: {config_path}")
            config_path.unlink()

    print("  Cleanup complete\n")


def parse_config_type(config_type: str) -> dict:
    """
    Parse a config type string into debate settings.

    Format: {component}{material}{country} where each is:
    - 'd{n}' for debate with n agents
    - 'v{n}' for voting/single-agent with n agents

    Examples:
    - 'd3d3v3' = debate(3) for components, debate(3) for materials, voting(3) for country
    - 'v1v1v1' = single agent throughout
    - 'd4v1v1' = debate(4) for components, single for materials, single for country

    Returns dict with keys:
    - enable_component_debate, num_agents_component
    - enable_material_debate, num_agents_material
    - enable_country_debate, num_agents_country
    """
    import re

    # Pattern: (d|v)(\d+) repeated 3 times
    pattern = r"^([dv])(\d+)([dv])(\d+)([dv])(\d+)$"
    match = re.match(pattern, config_type)

    if not match:
        raise ValueError(
            f"Invalid config type '{config_type}'. "
            "Expected format like 'd3d3v3', 'v1v1v1', 'd4v1v1', etc."
        )

    comp_type, comp_agents, mat_type, mat_agents, country_type, country_agents = match.groups()

    return {
        "enable_component_debate": comp_type == "d",
        "num_agents_component": int(comp_agents),
        "enable_material_debate": mat_type == "d",
        "num_agents_material": int(mat_agents),
        "enable_country_debate": country_type == "d",
        "num_agents_country": int(country_agents),
    }


def launch_run(
    run_num: int,
    config_type: str,
    project_dir: Path,
    debate_settings: dict,
) -> subprocess.Popen:
    """Launch a single pipeline run."""
    config_file = f"config_{config_type}_run{run_num}.json"

    # Write logs under output/logs/ (ensure directory exists)
    log_dir = project_dir / "output" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{config_type}_run{run_num}.log"

    debate_flags = [
        "--enable-component-debate",
        str(debate_settings["enable_component_debate"]).lower(),
        "--enable-material-debate",
        str(debate_settings["enable_material_debate"]).lower(),
        "--enable-country-debate",
        str(debate_settings["enable_country_debate"]).lower(),
        "--num-agents-component",
        str(debate_settings["num_agents_component"]),
        "--num-agents-material",
        str(debate_settings["num_agents_material"]),
        "--num-agents-country",
        str(debate_settings["num_agents_country"]),
    ]

    cmd = [
        "uv",
        "run",
        "stdn",
        "-i",
        config_file,
        *debate_flags,
    ]

    with open(log_file, "w") as log:
        process = subprocess.Popen(
            cmd,
            cwd=project_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    return process


def wait_for_all_processes_to_complete(
    config_type: str,
    check_interval: int = 60,
) -> None:
    """Wait for all processes of the given config type to complete."""
    print(f"\nWaiting for all {config_type} processes to complete...")
    print(f"Checking every {check_interval} seconds. Press Ctrl+C to stop waiting.\n")

    try:
        while True:
            active_count = get_active_process_count(config_type)
            if active_count == 0:
                print(f"\nAll {config_type} processes have completed.")
                break

            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {active_count} process(es) still running...")
            time.sleep(check_interval)
    except KeyboardInterrupt:
        print("\n\nStopped waiting. Processes are still running in the background.")
        raise


def rename_raw_outputs_to_standard(
    output_dir: Path,
    config_type: str,
    num_runs: int,
    date_prefix: str,
) -> list[Path]:
    """
    Rename collision-proof raw outputs back to standard naming.

    From:
      output/raw/stdns_output_{config_type}_run{N}_{date_prefix}*.csv
    To:
      output/raw/stdns_output_{config_type}_{date_prefix}*.csv

    Returns list of renamed standard raw CSV paths.
    """
    renamed: list[Path] = []
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for run_num in range(1, num_runs + 1):
        run_prefix = f"stdns_output_{config_type}_run{run_num}_{date_prefix}"
        standard_prefix = f"stdns_output_{config_type}_{date_prefix}"
        renamed_for_run = False

        for f in raw_dir.glob(f"{run_prefix}*.csv"):
            new_name = f.name.replace(run_prefix, standard_prefix, 1)
            target = f.with_name(new_name)

            if target.exists():
                print(f"WARNING: Cannot rename (target exists): {f.name} -> {target.name}")
                continue

            print(f"Renaming raw: {f.name} -> {target.name}")
            f.rename(target)
            renamed.append(target)
            renamed_for_run = True

        if not renamed_for_run:
            run_prefix_any = f"stdns_output_{config_type}_run{run_num}_"
            standard_prefix_any = f"stdns_output_{config_type}_"

            for f in raw_dir.glob(f"{run_prefix_any}*.csv"):
                ts_part = f.name[len(run_prefix_any) :]
                new_name = f"{standard_prefix_any}{ts_part}"
                target = f.with_name(new_name)

                if target.exists():
                    print(f"WARNING: Cannot rename (target exists): {f.name} -> {target.name}")
                    continue

                print(f"Renaming raw (fallback): {f.name} -> {target.name}")
                f.rename(target)
                renamed.append(target)

    return renamed


def generate_json_from_normalized_group(
    output_dir: Path,
    config_type: str,
    date_prefix: str,
) -> list[Path]:
    """
    Generate JSON files from normalized CSVs for a configuration.

    IMPORTANT: This intentionally ignores timestamp/date so that JSON generation applies to
    ALL normalized outputs for the same config_type.

    Reads:
      output/normalized/stdns_output_{config_type}_*.csv

    Writes:
      output/normalized/stdns_output_{config_type}_*.json

    JSON is a row-wise serialization of the normalized CSV (so components are normalized).
    Returns list of written JSON paths.
    """
    written: list[Path] = []

    normalized_dir = output_dir / "normalized"
    if not normalized_dir.exists():
        print(f"WARNING: Normalized directory does not exist: {normalized_dir}")
        return written

    pattern = f"stdns_output_{config_type}_*.csv"
    normalized_csvs = sorted(normalized_dir.glob(pattern))

    if not normalized_csvs:
        print(f"WARNING: No normalized CSVs found matching: {normalized_dir / pattern}")
        return written

    for csv_path in normalized_csvs:
        json_name = csv_path.with_suffix(".json").name
        # Write JSON alongside normalized CSVs
        json_path = output_dir / "normalized" / json_name

        if json_path.exists():
            print(f"WARNING: JSON already exists, skipping: {json_path}")
            continue

        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            data = list(reader)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Wrote JSON: {json_path}")
        written.append(json_path)

    return written


def rename_json_outputs_to_standard(
    output_dir: Path,
    config_type: str,
    num_runs: int,
) -> list[Path]:
    """
    Rename per-run JSON outputs to a collision-proof standard form.

    The pipeline writes JSON as:
      {output_csv_filename}_{timestamp}.json

    In parallel runs we set:
      output_csv_filename = stdns_output_{config_type}_run{N}

    So JSON files look like:
      output/stdns_output_{config_type}_run{N}_YYYYMMDD_HHMMSS.json

    If we renamed them to `stdns_output_YYYYMMDD_HHMMSS.json`, parallel runs can collide
    whenever timestamps match. Instead we rename to:

      output/stdns_output_{config_type}_YYYYMMDD_HHMMSS_run{N}.json

    Returns list of renamed JSON paths.
    """
    renamed: list[Path] = []

    for run_num in range(1, num_runs + 1):
        run_prefix = f"stdns_output_{config_type}_run{run_num}_"
        renamed_for_run = False

        for f in output_dir.glob(f"{run_prefix}*.json"):
            # Extract the timestamp suffix after the run-specific prefix
            ts_part = f.name[len(run_prefix) : -len(".json")]  # YYYYMMDD_HHMMSS
            new_name = f"stdns_output_{config_type}_{ts_part}_run{run_num}.json"
            target = f.with_name(new_name)

            if target.exists():
                print(f"WARNING: Cannot rename JSON (target exists): {f.name} -> {target.name}")
                continue

            print(f"Renaming json: {f.name} -> {target.name}")
            f.rename(target)
            renamed.append(target)
            renamed_for_run = True

        if not renamed_for_run:
            run_prefix_any = f"stdns_output_{config_type}_run{run_num}"

            for f in output_dir.glob(f"{run_prefix_any}*.json"):
                suffix = f.name[len(run_prefix_any) : -len(".json")]
                if suffix.startswith("_"):
                    suffix = suffix[1:]
                ts_part = suffix
                new_name = f"stdns_output_{config_type}_{ts_part}_run{run_num}.json"
                target = f.with_name(new_name)

                if target.exists():
                    print(f"WARNING: Cannot rename JSON (target exists): {f.name} -> {target.name}")
                    continue

                print(f"Renaming json (fallback): {f.name} -> {target.name}")
                f.rename(target)
                renamed.append(target)

    return renamed


def run_shared_normalization_pass(
    output_dir: Path,
    config_type: str,
    date_prefix: str,
) -> None:
    """
    Run one shared, LLM-backed component-name normalization pass across ALL raw CSVs for
    a configuration (ignoring timestamp/date).

    This delegates to `scripts/normalize_outputs_global_granularity.py`, which enforces
    primary-component granularity and uses the material-aware prompt while writing
    normalized CSVs to output/normalized/.

    We intentionally do this ONCE (after raw files have been renamed back to the standard
    pattern), so normalization applies to all outputs of the same config_type.
    """
    pattern = f"output/raw/stdns_output_{config_type}_*.csv"

    print("\nRunning shared normalization via scripts/normalize_outputs_global_granularity.py ...")
    print(f"  Pattern: {pattern}")

    cmd = [
        "uv",
        "run",
        "python",
        "scripts/normalize_outputs_global_granularity.py",
        "--pattern",
        pattern,
        "--group-by",
        "technology",
        "--output-dir",
        "output/normalized",
        "--global-vocab",
        "data/component_canonical_vocab_global_primary.json",
        "--model",
        "ollama:qwen2.5:32b",
        "--chunk-size",
        "120",
    ]

    result = subprocess.run(cmd, cwd=output_dir.parent)
    if result.returncode != 0:
        raise RuntimeError(
            f"Shared normalization failed (exit {result.returncode}). Command: {' '.join(cmd)}"
        )


def run_parallel_pipeline(
    config_type: str,
    num_runs: int,
    delay_between_launches: int,
    project_dir: Path,
    output_dir: Path,
    base_config_path: Path,
    cleanup_after: bool = True,
    defer_shared_postprocess: bool = False,
) -> bool:
    """
    Run multiple pipeline instances in parallel.

    Returns True if all runs launched successfully, False otherwise.
    """
    # Parse config type to get debate settings
    debate_settings = parse_config_type(config_type)

    # Compute the ACTUAL debate config marker used in filenames by the orchestrator.
    #
    # Orchestrator logic (pipeline._build_debate_config_string) encodes:
    #   components: d{N} if debate enabled, else v1
    #   materials:  d{N} if debate enabled, else v1
    #   countries:  v{N} where N = num_agents_country if country_debate enabled, else 1
    #              (country always uses 'v' prefix — voting, never iterative debate)
    #
    # IMPORTANT: The user-facing config_type (e.g. "d3d3v3") is parsed by parse_config_type
    # which sets enable_country_debate = (country_type == "d").  Since country is always "v"
    # in the config_type string, enable_country_debate is always False, and the pipeline
    # collapses num_agents_country to 1 in the debate string.
    #
    # We use config_type directly for output_csv_filename (to keep filenames readable),
    # but filename_config_marker must match what the pipeline actually produces.
    filename_config_marker = (
        f"{'d' if debate_settings['enable_component_debate'] else 'v'}"
        f"{debate_settings['num_agents_component'] if debate_settings['enable_component_debate'] else 1}"
        f"{'d' if debate_settings['enable_material_debate'] else 'v'}"
        f"{debate_settings['num_agents_material'] if debate_settings['enable_material_debate'] else 1}"
        f"v{debate_settings['num_agents_country']}"
    )

    date_prefix = get_today_date_prefix()
    known_files: set[str] = set()
    launched_files: list[str] = []
    processes: list[subprocess.Popen] = []

    # Load base config to get database path
    with open(base_config_path) as f:
        base_config = json.load(f)

    base_db_path = project_dir / base_config["usgs_database"].lstrip("./")

    if not base_db_path.exists():
        print(f"ERROR: Base database not found: {base_db_path}")
        return False

    # Create database copies and config files
    db_copies = create_database_copies(
        base_db_path,
        num_runs,
        project_dir,
        config_type=config_type,
    )
    config_files = create_config_files(
        base_config_path,
        config_type,
        db_copies,
        project_dir,
        base_output_dir=output_dir,
        filename_config_marker=filename_config_marker,
    )

    # Get existing files to exclude (standard location only)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Existing standard files to exclude (based on ACTUAL filename marker)
    pattern_standard = f"stdns_output_{filename_config_marker}_{date_prefix}*.csv"
    for f in raw_dir.glob(pattern_standard):
        known_files.add(f.name)

    # Also exclude any collision-proof per-run raw files already present (if rerunning the script)
    pattern_runs = f"stdns_output_{filename_config_marker}_run*_{date_prefix}*.csv"
    for f in raw_dir.glob(pattern_runs):
        known_files.add(f.name)

    print(f"\n{'=' * 60}")
    print(f"Starting {num_runs} parallel {config_type} runs")
    print("Debate settings:")
    print(
        f"  Component: {'debate' if debate_settings['enable_component_debate'] else 'single'} ({debate_settings['num_agents_component']} agents)"
    )
    print(
        f"  Material:  {'debate' if debate_settings['enable_material_debate'] else 'single'} ({debate_settings['num_agents_material']} agents)"
    )
    print(
        f"  Country:   {'debate' if debate_settings['enable_country_debate'] else 'single'} ({debate_settings['num_agents_country']} agents)"
    )
    print(f"Delay between launches: {delay_between_launches}s")
    print(f"Output directory: {output_dir}")
    print(f"Cleanup after completion: {cleanup_after}")
    print(f"{'=' * 60}\n")

    try:
        for run_num in range(1, num_runs + 1):
            print(f"[Run {run_num}/{num_runs}] Launching...")

            # Check config file exists
            config_file = project_dir / f"config_{config_type}_run{run_num}.json"
            if not config_file.exists():
                print(f"  ERROR: Config file not found: {config_file}")
                print("  Stopping all processes and aborting.")
                kill_all_processes(config_type)
                return False

            # Launch the run
            process = launch_run(run_num, config_type, project_dir, debate_settings)
            processes.append(process)

            # Wait for output file to be created
            print("  Waiting for output file...")
            # Each run writes to the shared output/raw directory, but uses a unique
            # output_csv_filename, so we wait for the run-specific filename pattern.
            new_file = wait_for_new_file(
                raw_dir,
                filename_config_marker,
                date_prefix,
                known_files,
                run_num=run_num,
                timeout=30,
            )

            if new_file:
                print(f"  SUCCESS: Created {new_file}")
                known_files.add(new_file)
                # Track the actual raw file path (shared output/raw directory)
                launched_files.append(str((raw_dir / new_file)))
            else:
                print("  ERROR: Output file not created within timeout")
                print("  Stopping all processes and aborting.")
                kill_all_processes(config_type)
                return False

            # Delay before next launch (except for last run)
            if run_num < num_runs:
                print(f"  Waiting {delay_between_launches}s before next launch...")
                time.sleep(delay_between_launches)

        # All runs launched - verify all processes are running
        print(f"\n{'=' * 60}")
        print("All runs launched. Verifying...")
        print(f"{'=' * 60}\n")

        active_count = get_active_process_count(config_type)
        print(f"Active processes: {active_count}/{num_runs}")

        if active_count < num_runs:
            print(f"WARNING: Expected {num_runs} processes but only {active_count} are running")
            print("Check log files for errors.")

        # Check files are growing
        print("\nChecking if files are growing (5s interval)...")
        # launched_files may contain full paths; check_files_growing supports both
        growth_status = check_files_growing(output_dir, launched_files)

        all_ok = True
        for filename, is_growing in growth_status.items():
            file_path = Path(filename)
            if not file_path.is_absolute() and file_path.parent == Path("."):
                file_path = output_dir / filename
            size = file_path.stat().st_size if file_path.exists() else 0
            status = "OK" if is_growing else "NOT GROWING"
            if not is_growing:
                all_ok = False
            print(f"  {filename}: {size:,} bytes - {status}")

        if all_ok:
            print(f"\nSUCCESS: All {num_runs} {config_type} runs are active and files are valid")
        else:
            print("\nWARNING: Some files may not be growing. Check processes and logs.")

        # Print summary
        print(f"\n{'=' * 60}")
        print("Summary")
        print(f"{'=' * 60}")
        print(f"Config type: {config_type}")
        print(f"Runs launched: {num_runs}")
        print("Output files:")
        for f in launched_files:
            print(f"  - {f}")
        print("\nLog files:")
        for run_num in range(1, num_runs + 1):
            print(f"  - output/logs/{config_type}_run{run_num}.log")
        print("\nTo monitor progress:")
        print(f"  tail -f output/logs/{config_type}_run*.log")
        print("\nTo check file sizes (during parallel run):")
        print(f"  ls -la output/raw/stdns_output_{config_type}_run*_{date_prefix}*.csv")
        print("\nAfter completion, raw files will be renamed back to:")
        print(f"  output/raw/stdns_output_{config_type}_run*_{date_prefix}*.csv")
        print("\nTo stop all runs:")
        print(f"  pkill -f 'stdn -i config_{config_type}'")

        # Wait for completion if cleanup is enabled
        if cleanup_after:
            try:
                wait_for_all_processes_to_complete(config_type, check_interval=60)

                # Step 1: Rename collision-proof raw outputs back to standard naming
                print("\nRenaming raw outputs back to standard naming...")
                rename_raw_outputs_to_standard(
                    output_dir=output_dir,
                    config_type=filename_config_marker,
                    num_runs=num_runs,
                    date_prefix=date_prefix,
                )

                # Step 1b: Rename per-run JSON outputs back to standard naming
                print("\nRenaming JSON outputs back to standard naming...")
                rename_json_outputs_to_standard(
                    output_dir=output_dir,
                    config_type=filename_config_marker,
                    num_runs=num_runs,
                )

                if defer_shared_postprocess:
                    print(
                        "\nDeferring shared normalization and JSON generation (defer_shared_postprocess=True)."
                    )
                else:
                    # Step 2: Run one shared normalization pass across the consolidated raw outputs
                    run_shared_normalization_pass(
                        output_dir=output_dir,
                        config_type=filename_config_marker,
                        date_prefix=date_prefix,
                    )

                    # Step 3: Generate JSON from normalized outputs (JSON should contain normalized components)
                    print("\nGenerating JSON from normalized outputs...")
                    generate_json_from_normalized_group(
                        output_dir=output_dir,
                        config_type=filename_config_marker,
                        date_prefix=date_prefix,
                    )

                cleanup_temp_files(db_copies, config_files)
            except KeyboardInterrupt:
                print("\nSkipping cleanup due to interrupt.")
                print("NOTE: Outputs may still have per-run naming (contain '_runN_').")
                print("To manually cleanup later, run:")
                print(f"  rm -f data/*_run*.db config_{config_type}_run*.json")

        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        kill_all_processes(config_type)
        if cleanup_after:
            cleanup_temp_files(db_copies, config_files)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Launch parallel pipeline runs with validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config-type",
        type=str,
        required=True,
        help="Configuration type in format like 'd3d3v3', 'v1v1v1', 'd4v1v1'. "
        "Each segment is [d|v][N] for debate/voting with N agents. "
        "Order: component, material, country.",
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=5,
        help="Number of parallel runs to launch (default: 5)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=10,
        help="Delay in seconds between launching each run (default: 10)",
    )
    parser.add_argument(
        "--base-config",
        type=Path,
        required=True,
        help="Path to base config file (e.g., config.json)",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: current directory)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip cleanup of temp database and config files after completion",
    )
    parser.add_argument(
        "--defer-shared-postprocess",
        action="store_true",
        help="Defer shared normalization and JSON generation to run once after all configs finish",
    )

    args = parser.parse_args()

    # Validate config type format early
    try:
        parse_config_type(args.config_type)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    project_dir = args.project_dir.resolve()
    output_dir = project_dir / "output"
    base_config_path = (
        args.base_config.resolve()
        if args.base_config.is_absolute()
        else (project_dir / args.base_config).resolve()
    )

    # Validate directories and files exist
    if not project_dir.exists():
        print(f"ERROR: Project directory does not exist: {project_dir}")
        sys.exit(1)

    if not base_config_path.exists():
        print(f"ERROR: Base config file does not exist: {base_config_path}")
        sys.exit(1)

    if not output_dir.exists():
        print(f"Creating output directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing processes
    existing_count = get_active_process_count(args.config_type)
    if existing_count > 0:
        print(f"WARNING: {existing_count} existing {args.config_type} processes found.")
        response = input("Kill them and continue? [y/N]: ").strip().lower()
        if response == "y":
            kill_all_processes(args.config_type)
            time.sleep(2)
        else:
            print("Aborting.")
            sys.exit(1)

    # Run the parallel pipeline
    success = run_parallel_pipeline(
        config_type=args.config_type,
        num_runs=args.num_runs,
        delay_between_launches=args.delay,
        project_dir=project_dir,
        output_dir=output_dir,
        base_config_path=base_config_path,
        cleanup_after=not args.no_cleanup,
        defer_shared_postprocess=args.defer_shared_postprocess,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
