"""Export normalized STDN output for stdn-explorer.

Reads all normalized CSVs from the pipeline output, filters to the
technologies listed in a tech list file, adds a subdomain column from
the tech list, and writes the result. Can produce both the intermediate
explorer format (without subdomain) and the final stdn-explorer format
(with subdomain).

Usage:
    # Export all domains defined in config
    python scripts/export_for_explorer.py

    # Export a single domain
    python scripts/export_for_explorer.py --tech-list data/tech_list_microelectronic_products.csv --output-name microelectronics

    # Export without subdomain column (intermediate format)
    python scripts/export_for_explorer.py --no-subdomain

    # Specify normalized CSV directory and debate config pattern
    python scripts/export_for_explorer.py --normalized-dir output/normalized --config-pattern d3d3v3

    # Export directly to stdn-explorer data directory
    python scripts/export_for_explorer.py --explorer-dir ../stdn-explorer/data
"""

import argparse
import csv
import glob
import shutil
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent

# Default domain configurations: (tech_list_file, output_name)
DEFAULT_DOMAINS = [
    ("data/tech_list_microelectronic_products.csv", "microelectronics"),
    ("data/tech_list_biotechnology_products.csv", "biotechnology"),
    ("data/tech_list_pharmaceutical_products.csv", "pharmaceuticals"),
]


def load_tech_list(tech_list_path: Path) -> dict[str, str]:
    """Load a tech list CSV and return {technology_name: subdomain}.

    The tech list CSV has columns: domain (actually subdomain), tech, role.
    """
    tech_to_subdomain = {}
    with open(tech_list_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            tech_name = row["tech"].strip()
            subdomain = row["domain"].strip()  # "domain" column is actually subdomain
            tech_to_subdomain[tech_name] = subdomain
    return tech_to_subdomain


def load_normalized_rows(
    normalized_dir: Path,
    config_pattern: str | None = None,
) -> list[dict]:
    """Load all rows from normalized STDN CSVs.

    If config_pattern is specified, only loads files matching that pattern
    (e.g., "d3d3v3" loads only stdns_output_d3d3v3_*.csv).

    When the same technology appears in multiple files (from separate
    pipeline runs), keeps only the rows from the most recent file
    (sorted by filename, which encodes a timestamp).
    """
    pattern = f"stdns_output_{config_pattern}_*.csv" if config_pattern else "stdns_output_*.csv"
    files = sorted(normalized_dir.glob(pattern))

    if not files:
        print(f"No normalized CSVs found matching {normalized_dir / pattern}", file=sys.stderr)
        return []

    # Load rows per file, track which file each technology came from.
    # Later files (sorted by timestamp in filename) take precedence.
    tech_to_file = {}  # technology -> filename that should supply its rows
    file_rows = {}     # filename -> list of rows

    for f in files:
        fname = f.name
        with open(f) as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            file_rows[fname] = rows
            techs_in_file = set(r["technology"] for r in rows)
            for t in techs_in_file:
                tech_to_file[t] = fname  # later files overwrite earlier ones

    # Collect rows, keeping only those from the winning file per technology
    all_rows = []
    for fname, rows in file_rows.items():
        for row in rows:
            if tech_to_file.get(row["technology"]) == fname:
                all_rows.append(row)

    total_files = len(files)
    used_files = len(set(tech_to_file.values()))
    print(f"Loaded {len(all_rows)} rows from {used_files} of {total_files} normalized CSVs (latest per technology)")
    return all_rows


def filter_and_export(
    all_rows: list[dict],
    tech_to_subdomain: dict[str, str],
    output_path: Path,
    include_subdomain: bool = True,
):
    """Filter rows to technologies in the tech list and write to CSV.

    If include_subdomain is True, inserts a 'subdomain' column after 'technology'.
    When a technology appears in multiple normalized files (from different runs),
    keeps the rows from the most recent file (latest timestamp in filename).
    """
    # Filter to matching technologies
    target_techs = set(tech_to_subdomain.keys())
    matched_rows = [r for r in all_rows if r["technology"] in target_techs]

    if not matched_rows:
        print(f"  WARNING: No rows matched any of the {len(target_techs)} technologies")
        return

    # Report coverage
    found_techs = set(r["technology"] for r in matched_rows)
    missing = target_techs - found_techs
    if missing:
        print(f"  WARNING: {len(missing)} technologies not found in normalized data:")
        for t in sorted(missing):
            print(f"    - {t}")

    # Determine column order from the union of all row keys
    all_keys = []
    seen = set()
    for row in matched_rows:
        for k in row.keys():
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
    fieldnames = all_keys

    if include_subdomain and "subdomain" not in fieldnames:
        tech_idx = fieldnames.index("technology")
        fieldnames.insert(tech_idx + 1, "subdomain")

    # Add subdomain values
    if include_subdomain:
        for row in matched_rows:
            row["subdomain"] = tech_to_subdomain.get(row["technology"], "")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matched_rows)

    print(f"  Wrote {len(matched_rows)} rows ({len(found_techs)} technologies) to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Export normalized STDN output for stdn-explorer"
    )
    parser.add_argument(
        "--tech-list",
        type=Path,
        help="Path to a single tech list CSV. If omitted, exports all default domains.",
    )
    parser.add_argument(
        "--output-name",
        help="Output filename stem (e.g., 'microelectronics'). Required with --tech-list.",
    )
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=PROJECT_DIR / "output" / "normalized",
        help="Directory containing normalized STDN CSVs (default: output/normalized)",
    )
    parser.add_argument(
        "--config-pattern",
        help="Only load normalized CSVs matching this debate config (e.g., 'd3d3v3')",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "data" / "explorer",
        help="Directory for intermediate explorer CSVs (default: data/explorer)",
    )
    parser.add_argument(
        "--explorer-dir",
        type=Path,
        help="If set, also exports with subdomain column to this directory (e.g., ../stdn-explorer/data)",
    )
    parser.add_argument(
        "--no-subdomain",
        action="store_true",
        help="Skip the subdomain column in all outputs",
    )
    args = parser.parse_args()

    # Load all normalized rows once
    all_rows = load_normalized_rows(args.normalized_dir, args.config_pattern)
    if not all_rows:
        sys.exit(1)

    # Determine which domains to export
    if args.tech_list:
        if not args.output_name:
            parser.error("--output-name is required when using --tech-list")
        domains = [(str(args.tech_list), args.output_name)]
    else:
        domains = DEFAULT_DOMAINS

    for tech_list_rel, output_name in domains:
        tech_list_path = PROJECT_DIR / tech_list_rel
        if not tech_list_path.exists():
            print(f"Tech list not found: {tech_list_path}", file=sys.stderr)
            continue

        print(f"\nExporting {output_name}:")
        tech_to_subdomain = load_tech_list(tech_list_path)
        print(f"  Tech list: {len(tech_to_subdomain)} technologies")

        # Export with subdomain to data/explorer/
        explorer_path = args.output_dir / f"{output_name}_60techs.csv"
        filter_and_export(
            all_rows, tech_to_subdomain, explorer_path,
            include_subdomain=not args.no_subdomain,
        )

        # Copy to stdn-explorer data dir if specified
        if args.explorer_dir:
            final_path = args.explorer_dir / f"{output_name}.csv"
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(explorer_path, final_path)
            print(f"  Copied to {final_path}")


if __name__ == "__main__":
    main()
