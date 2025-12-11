from collections import namedtuple
from pathlib import Path
from typing import List
from align_utils.discovery import parse_experiments_directory
from align_utils.models import ExperimentItem, ExperimentData, get_experiment_items


ExperimentResultsRegistry = namedtuple(
    "ExperimentResultsRegistry",
    [
        "get_all_items",
        "get_experiments",
    ],
)


def create_experiment_results_registry(
    experiments_path: Path,
) -> ExperimentResultsRegistry:
    """
    Creates an ExperimentResultsRegistry with pre-computed experiment results.
    Loads experiment directories containing input_output.json + hydra configs.
    """
    experiments: List[ExperimentData] = parse_experiments_directory(experiments_path)
    all_items: List[ExperimentItem] = [
        item for exp in experiments for item in get_experiment_items(exp)
    ]

    return ExperimentResultsRegistry(
        get_all_items=lambda: all_items,
        get_experiments=lambda: experiments,
    )
