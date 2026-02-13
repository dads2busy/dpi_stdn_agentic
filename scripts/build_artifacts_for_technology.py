#!/usr/bin/env python3
"""
Build per-technology artifacts from normalized outputs.

For a single *base* technology name (e.g., "Bioreactor"), this script:
1) Extracts only matching rows from every `output/normalized/*.csv` into:
     output/artifacts/<TechSlug>/<same_filename>.csv

   Matching rule (base technology across configs):
   - A row matches if its `technology` column equals:
       - <base>
       - <base> + " " + <config_tag>
     where <config_tag> matches the compact 3-stage marker used in this project:
       - 3 tokens, each token is:
           'v' or 'd' followed by 1-2 digits
       - Examples (all valid):
           v1v1v1
           d3v1v1
           v1d12d19
           d5v1d9

2) Combines extracted files per config marker into:
     output/artifacts/<TechSlug>_combined/<TechSlug>_<config>_combined.csv

   Adds two columns:
     - agent: 1..N (file index within that config group, sorted by filename; capped to max-files-per-config)
     - config: config marker (e.g., v1v1v1, d3v1v1, v1d12d19, ...)

3) Combines per-config combined files into:
     output/artifacts/<TechSlug>_combined/<TechSlug>_ALL_configs_combined.csv

Optionally deletes the intermediate extracted directory and any empty dirs.

Usage:
  uv run python scripts/build_artifacts_for_technology.py --technology "Bioreactor"

Notes:
- Requires that normalized CSVs have a `technology` column.
- Config marker is parsed from filename: stdns_output_<cfg>_YYYYMMDD_HHMMSS.csv
- This script operates on CSVs only (not JSON).
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

_RX_CFG_FROM_FILENAME = re.compile(r"^stdns_output_([a-z0-9]+)_\d{8}_\d{6}\.csv$", re.IGNORECASE)

# Config tag token: 'v' or 'd' + 1-2 digits, repeated 3 times (stage order).
# Examples: v1v1v1, d3v1v1, v1d12d19, d5v1d9
_RX_CFG_TOKEN = re.compile(
    r"(?:^|\s)((?:[vd]\d{1,2}){3})(?:$|\s)",
    re.IGNORECASE,
)


def slugify(s: str) -> str:
    s = (s or "").strip()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return slug or "TECH"


def _strip_cfg_suffix(label: str) -> tuple[str, str]:
    """
    Split a technology label into (base, cfg).
    If no cfg token is found, cfg="unknown" and base=label.
    """
    label = (label or "").strip()
    m = _RX_CFG_TOKEN.search(label)
    if not m:
        return label, "unknown"
    cfg = m.group(1)
    base = (label[: m.start(1)] + label[m.end(1) :]).strip()
    base = re.sub(r"\s+", " ", base)
    return base, cfg


def _matches_base_technology(base_tech: str, row_tech: str) -> bool:
    """
    True if row_tech corresponds to base_tech, either exactly or with a config tag.

    Examples:
      base_tech="Bioreactor"
        row_tech="Bioreactor" -> True
        row_tech="Bioreactor v1v1v1" -> True
        row_tech="Bioreactor d3v1v1" -> True
        row_tech="Bioreactor somethingelse" -> False (unless it parses as cfg token)
    """
    base_tech = (base_tech or "").strip()
    row_tech = (row_tech or "").strip()
    if not base_tech or not row_tech:
        return False

    if row_tech == base_tech:
        return True

    base, cfg = _strip_cfg_suffix(row_tech)
    if cfg == "unknown":
        return False
    return base == base_tech


@dataclass(frozen=True)
class Paths:
    normalized_dir: Path
    artifacts_root: Path
    extracted_dir: Path
    combined_dir: Path


def iter_normalized_csvs(normalized_dir: Path) -> Iterable[Path]:
    yield from sorted(normalized_dir.glob("*.csv"))


def extract_rows_for_base_technology(base_technology: str, paths: Paths) -> int:
    """
    Step 1: For each normalized CSV, write a filtered CSV into extracted_dir
    containing only rows whose `technology` matches `base_technology` (across configs).

    Returns number of extracted files written.
    """
    paths.extracted_dir.mkdir(parents=True, exist_ok=True)

    written_files = 0
    for src in iter_normalized_csvs(paths.normalized_dir):
        dst = paths.extracted_dir / src.name

        with src.open("r", encoding="utf-8", newline="") as fin:
            r = csv.DictReader(fin)
            if not r.fieldnames or "technology" not in r.fieldnames:
                continue

            out_f = None
            w: Optional[csv.DictWriter] = None
            wrote_any = False

            for row in r:
                row_tech = (row.get("technology") or "").strip()
                if not _matches_base_technology(base_technology, row_tech):
                    continue

                if out_f is None:
                    out_f = dst.open("w", encoding="utf-8", newline="")
                    w = csv.DictWriter(out_f, fieldnames=r.fieldnames)
                    w.writeheader()

                assert w is not None
                w.writerow(row)
                wrote_any = True

            if out_f is not None:
                out_f.close()

        if wrote_any:
            written_files += 1
        else:
            if dst.exists():
                dst.unlink()

    return written_files


def group_extracted_by_config(extracted_dir: Path) -> dict[str, list[Path]]:
    """
    Group extracted CSV files by config marker inferred from the filename:
      stdns_output_<cfg>_YYYYMMDD_HHMMSS.csv
    """
    bycfg: dict[str, list[Path]] = {}
    for fp in sorted(extracted_dir.glob("*.csv")):
        m = _RX_CFG_FROM_FILENAME.match(fp.name)
        if not m:
            continue
        cfg = m.group(1)
        bycfg.setdefault(cfg, []).append(fp)
    return bycfg


def combine_per_config(
    tech_slug: str,
    bycfg: dict[str, list[Path]],
    combined_dir: Path,
    max_files_per_config: int,
) -> list[Path]:
    """
    Step 2: Combine extracted CSVs per config.
    Returns list of per-config combined file paths.
    """
    combined_dir.mkdir(parents=True, exist_ok=True)

    out_paths: list[Path] = []
    for cfg, files in sorted(bycfg.items()):
        files = files[:max_files_per_config]
        if not files:
            continue

        out_path = combined_dir / f"{tech_slug}_{cfg}_combined.csv"

        with files[0].open("r", encoding="utf-8", newline="") as f0:
            r0 = csv.DictReader(f0)
            # csv.DictReader.fieldnames is Optional[Sequence[str]]; cast to list for safe concatenation
            fieldnames = list(r0.fieldnames or [])
            if not fieldnames:
                continue

        out_fields = ["agent", "config"] + fieldnames

        total_rows = 0
        with out_path.open("w", encoding="utf-8", newline="") as fout:
            w = csv.DictWriter(fout, fieldnames=out_fields)
            w.writeheader()

            for idx, fp in enumerate(files, start=1):
                with fp.open("r", encoding="utf-8", newline="") as fin:
                    r = csv.DictReader(fin)
                    if (r.fieldnames or []) != fieldnames:
                        raise RuntimeError(
                            f"Header mismatch for {fp}: expected {fieldnames} got {r.fieldnames}"
                        )
                    for row in r:
                        row_out = {"agent": idx, "config": cfg}
                        row_out.update(row)
                        w.writerow(row_out)
                        total_rows += 1

        if total_rows == 0:
            out_path.unlink(missing_ok=True)
            continue

        out_paths.append(out_path)

    return out_paths


def combine_all_configs(tech_slug: str, combined_dir: Path) -> Path:
    """
    Step 3: Combine all per-config combined files into one file.
    Returns output path.
    """
    out_path = combined_dir / f"{tech_slug}_ALL_configs_combined.csv"
    inputs = sorted(combined_dir.glob(f"{tech_slug}_*_combined.csv"))
    inputs = [p for p in inputs if p.resolve() != out_path.resolve()]

    if not inputs:
        raise RuntimeError(f"No per-config combined files found in {combined_dir}")

    with inputs[0].open("r", encoding="utf-8", newline="") as f0:
        r0 = csv.DictReader(f0)
        fieldnames = r0.fieldnames
        if not fieldnames:
            raise RuntimeError(f"Empty header in {inputs[0]}")

    rows = 0
    with out_path.open("w", encoding="utf-8", newline="") as fout:
        w = csv.DictWriter(fout, fieldnames=fieldnames)
        w.writeheader()

        for fp in inputs:
            with fp.open("r", encoding="utf-8", newline="") as fin:
                r = csv.DictReader(fin)
                if r.fieldnames != fieldnames:
                    raise RuntimeError(f"Header mismatch combining: {fp}")
                for row in r:
                    w.writerow(row)
                    rows += 1

    if rows == 0:
        raise RuntimeError("All-config combined file would be empty; refusing to write.")

    return out_path


def delete_empty_dirs(root: Path) -> None:
    """
    Depth-first delete empty dirs under root (excluding root itself).
    """
    dirs = [p for p in root.rglob("*") if p.is_dir()]
    for d in sorted(dirs, reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--technology",
        required=True,
        help=(
            "Base technology name to extract. Matches rows whose `technology` column "
            "is either exactly this string or this string followed by a config tag "
            "(e.g. 'Bioreactor d3v1v1')."
        ),
    )
    ap.add_argument(
        "--normalized-dir",
        default="output/normalized",
        help="Directory containing normalized CSVs.",
    )
    ap.add_argument(
        "--artifacts-dir",
        default="output/artifacts",
        help="Root directory to write artifacts under.",
    )
    ap.add_argument(
        "--max-files-per-config",
        type=int,
        default=10,
        help="Max extracted files to combine per config.",
    )
    ap.add_argument(
        "--delete-extracted",
        action="store_true",
        help="Delete the intermediate extracted directory after combined outputs are written.",
    )
    args = ap.parse_args()

    base_technology: str = args.technology
    tech_slug = slugify(base_technology)

    paths = Paths(
        normalized_dir=Path(args.normalized_dir),
        artifacts_root=Path(args.artifacts_dir),
        extracted_dir=Path(args.artifacts_dir) / tech_slug,
        combined_dir=Path(args.artifacts_dir) / f"{tech_slug}_combined",
    )

    if not paths.normalized_dir.exists():
        raise SystemExit(f"Normalized dir not found: {paths.normalized_dir}")

    paths.artifacts_root.mkdir(parents=True, exist_ok=True)

    n_extracted = extract_rows_for_base_technology(base_technology, paths)
    if n_extracted == 0:
        raise SystemExit(
            f"No rows found for base technology '{base_technology}' in {paths.normalized_dir}"
        )

    bycfg = group_extracted_by_config(paths.extracted_dir)
    per_cfg = combine_per_config(
        tech_slug=tech_slug,
        bycfg=bycfg,
        combined_dir=paths.combined_dir,
        max_files_per_config=int(args.max_files_per_config),
    )
    if not per_cfg:
        raise SystemExit(
            f"Extracted rows exist, but no per-config groups were found in {paths.extracted_dir}. "
            "Expected filenames like stdns_output_<cfg>_YYYYMMDD_HHMMSS.csv"
        )

    all_path = combine_all_configs(tech_slug=tech_slug, combined_dir=paths.combined_dir)

    if args.delete_extracted:
        shutil.rmtree(paths.extracted_dir, ignore_errors=True)
        delete_empty_dirs(paths.artifacts_root)

    print(f"Base technology: {base_technology}")
    print(f"Extracted files written: {n_extracted} -> {paths.extracted_dir}")
    print(f"Per-config combined files: {len(per_cfg)} -> {paths.combined_dir}")
    print(f"All-config combined file: {all_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
