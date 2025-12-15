"""Import experiments from ZIP files."""

import io
import tempfile
import zipfile
from pathlib import Path
from typing import List, Tuple

from align_utils.discovery import parse_experiments_directory
from align_utils.models import ExperimentData, ExperimentItem, get_experiment_items

from ..adm.experiment_converters import (
    deciders_from_experiments,
    probes_from_experiment_items,
    runs_from_experiment_items,
)
from ..adm.probe import Probe
from ..adm.run_models import Run


def import_experiments_from_zip(
    zip_bytes: bytes,
) -> Tuple[List[Probe], dict, List[Run]]:
    """Extract and parse experiments from a ZIP file.

    Returns:
        Tuple of (probes, experiment_deciders, runs)
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            zf.extractall(temp_path)

        experiments: List[ExperimentData] = parse_experiments_directory(temp_path)
        all_items: List[ExperimentItem] = [
            item for exp in experiments for item in get_experiment_items(exp)
        ]

        probes = probes_from_experiment_items(all_items)
        experiment_deciders = deciders_from_experiments(experiments)
        runs = runs_from_experiment_items(all_items)

        return probes, experiment_deciders, runs
