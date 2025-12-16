"""Import experiments from ZIP files and directories."""

import io
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional

from align_utils.discovery import parse_experiments_directory
from align_utils.models import (
    ExperimentData,
    ExperimentItem,
    get_experiment_items,
    ADMResult,
    Decision,
    ChoiceInfo,
)

from ..adm.experiment_converters import (
    deciders_from_experiments,
    probes_from_experiment_items,
)
from ..adm.experiment_config_loader import load_experiment_adm_config
from ..adm.probe import Probe, get_probe_id
from ..adm.decider.types import DeciderParams
from ..adm.run_models import Run, RunDecision
from .runs_presentation import compute_experiment_item_cache_key


@dataclass
class StoredExperimentItem:
    """ExperimentItem with pre-loaded config for use after temp dir cleanup."""

    item: ExperimentItem
    resolved_config: Dict
    cache_key: str


@dataclass
class ExperimentImportResult:
    """Result of importing experiments."""

    probes: List[Probe]
    deciders: dict
    items: Dict[str, StoredExperimentItem]


def import_experiments(experiments_path: Path) -> ExperimentImportResult:
    """Import experiments from a directory path.

    Returns ExperimentImportResult with probes, deciders, and items keyed by cache_key.
    """
    print(f"Loading experiments from {experiments_path}...")
    experiments: List[ExperimentData] = parse_experiments_directory(experiments_path)
    all_items: List[ExperimentItem] = [
        item for exp in experiments for item in get_experiment_items(exp)
    ]

    probes = probes_from_experiment_items(all_items)
    deciders = deciders_from_experiments(experiments)

    items: Dict[str, StoredExperimentItem] = {}
    for item in all_items:
        resolved_config = load_experiment_adm_config(item.experiment_path) or {}
        cache_key = compute_experiment_item_cache_key(item, resolved_config)
        items[cache_key] = StoredExperimentItem(item, resolved_config, cache_key)

    print(f"Loaded {len(items)} experiment items from {len(experiments)} experiments")
    return ExperimentImportResult(probes, deciders, items)


def import_experiments_from_zip(zip_bytes: bytes) -> ExperimentImportResult:
    """Extract and parse experiments from a ZIP file.

    Returns ExperimentImportResult with probes, deciders, and items keyed by cache_key.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            zf.extractall(temp_path)

        return import_experiments(temp_path)


def run_from_stored_experiment_item(stored: StoredExperimentItem) -> Optional[Run]:
    """Convert StoredExperimentItem to Run with decision populated.

    Uses pre-loaded resolved_config instead of loading from (possibly deleted) path.
    """
    item = stored.item
    if not item.item.output:
        return None

    probe_id = get_probe_id(item.item)

    decider_params = DeciderParams(
        scenario_input=item.item.input,
        alignment_target=item.config.alignment_target,
        resolved_config=stored.resolved_config,
    )

    output = item.item.output
    decision = RunDecision(
        adm_result=ADMResult(
            decision=Decision(
                unstructured=output.action.unstructured,
                justification=output.action.justification or "",
            ),
            choice_info=item.item.choice_info or ChoiceInfo(),
        ),
        choice_index=output.choice,
    )

    decider_name = item.experiment_path.parent.name

    return Run(
        id=str(uuid.uuid4()),
        probe_id=probe_id,
        decider_name=decider_name,
        llm_backbone_name=item.config.adm.llm_backbone or "N/A",
        system_prompt="",
        decider_params=decider_params,
        decision=decision,
    )
