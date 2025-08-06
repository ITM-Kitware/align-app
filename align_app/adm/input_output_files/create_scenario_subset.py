#!/usr/bin/env python3
"""
Generic script to create a subset of scenarios from JSON files.

This script reads JSON files from an input directory, randomly samples N scenarios
from each file, and saves the subsets to an output directory with the same filenames.

Last run command:
    python create_scenario_subset.py \
        --input-dir /data/shared/samba/phase2_icl \
        --output-dir ./phase2_july \
        --count 10 \
        --pattern "July2025-*-train_*.json" \
        --seed 42
"""

import argparse
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys


def load_json_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load and validate JSON file structure."""
    try:
        with open(file_path, "r") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"Expected list at root level, got {type(data)}")

        return data
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return []


def sample_scenarios(
    scenarios: List[Dict[str, Any]], count: int, seed: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Randomly sample scenarios from the list."""
    if seed is not None:
        random.seed(seed)

    if len(scenarios) <= count:
        print(
            f"Warning: File has {len(scenarios)} scenarios, requested {count}. Using all scenarios."
        )
        return scenarios

    return random.sample(scenarios, count)


def save_json_file(data: List[Dict[str, Any]], file_path: Path) -> bool:
    """Save data to JSON file."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {file_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Extract N scenarios from each JSON file in a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract 10 scenarios from July files
  python create_scenario_subset.py \
    --input-dir /data/shared/samba/phase2_icl \
    --output-dir . \
    --count 10 \
    --pattern "July2025-*-train_*.json"
  # Extract 5 scenarios from all JSON files with specific seed
  python create_scenario_subset.py \
    --input-dir /path/to/input \
    --output-dir /path/to/output \
    --count 5 \
    --seed 42
        """,
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing input JSON files",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to save subset JSON files",
    )

    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of scenarios to extract per file (default: 10)",
    )

    parser.add_argument(
        "--pattern",
        type=str,
        default="*.json",
        help="File pattern to match (default: *.json)",
    )

    parser.add_argument("--seed", type=int, help="Random seed for reproducible results")

    args = parser.parse_args()

    # Validate input directory
    if not args.input_dir.exists() or not args.input_dir.is_dir():
        print(
            f"Error: Input directory {args.input_dir} does not exist or is not a directory"
        )
        sys.exit(1)

    # Find matching JSON files
    input_files = list(args.input_dir.glob(args.pattern))
    if not input_files:
        print(f"No files matching pattern '{args.pattern}' found in {args.input_dir}")
        sys.exit(1)

    print(f"Found {len(input_files)} files matching pattern '{args.pattern}':")
    for f in sorted(input_files):
        print(f"  {f.name}")
    print()

    # Process each file
    total_scenarios_processed = 0
    total_scenarios_output = 0
    successful_files = 0

    for input_file in sorted(input_files):
        print(f"Processing {input_file.name}...")

        # Load scenarios
        scenarios = load_json_file(input_file)
        if not scenarios:
            print("  Skipped (no valid scenarios)\n")
            continue

        total_scenarios_processed += len(scenarios)

        # Sample scenarios
        subset = sample_scenarios(scenarios, args.count, args.seed)
        total_scenarios_output += len(subset)

        # Save subset
        output_file = args.output_dir / input_file.name
        if save_json_file(subset, output_file):
            print(f"  Saved {len(subset)} scenarios to {output_file}")
            successful_files += 1
        else:
            print(f"  Failed to save {output_file}")

        print()

    # Summary
    print("=" * 50)
    print("SUMMARY:")
    print(f"Files processed: {len(input_files)}")
    print(f"Files successfully saved: {successful_files}")
    print(f"Total scenarios in input: {total_scenarios_processed}")
    print(f"Total scenarios in output: {total_scenarios_output}")
    print(f"Output directory: {args.output_dir.absolute()}")

    if args.seed is not None:
        print(f"Random seed used: {args.seed}")


if __name__ == "__main__":
    main()
