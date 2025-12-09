"""Tests for experiment cache population and retrieval."""

from pathlib import Path
import pytest

from align_app.adm.run_models import Run
from align_app.adm.decider.types import DeciderParams
from align_app.app.runs_registry import create_runs_registry
from align_app.app.runs_core import Runs, populate_cache_bulk
from align_app.adm.experiment_converters import runs_from_experiment_items
from align_utils.models import AlignmentTarget, KDMAValue, get_experiment_items
from align_utils.discovery import parse_experiments_directory


@pytest.fixture
def single_experiment_path(experiments_fixtures_path: Path) -> Path:
    """Return path to a single experiment for faster tests."""
    return experiments_fixtures_path / "pipeline_baseline_greedy_w_cache" / "affiliation-0.0"


def test_cache_populated_from_experiment(single_experiment_path: Path):
    """Verify cache is populated from experiment items."""
    experiments = parse_experiments_directory(single_experiment_path.parent.parent)

    target_experiments = [
        exp for exp in experiments
        if "pipeline_baseline_greedy_w_cache" in str(exp.experiment_path)
        and "affiliation-0.0" in str(exp.experiment_path)
    ]
    assert len(target_experiments) == 1

    items = get_experiment_items(target_experiments[0])
    assert len(items) > 0

    runs = runs_from_experiment_items(items)
    assert len(runs) > 0
    assert all(run.decision is not None for run in runs)

    data = Runs.empty()
    data = populate_cache_bulk(data, runs)

    assert len(data.decision_cache) == len(runs)


def test_cache_hit_with_matching_params(single_experiment_path: Path):
    """Verify cache returns decision when params match."""
    experiments = parse_experiments_directory(single_experiment_path.parent.parent)

    target_experiments = [
        exp for exp in experiments
        if "pipeline_baseline_greedy_w_cache" in str(exp.experiment_path)
        and "affiliation-0.0" in str(exp.experiment_path)
    ]

    items = get_experiment_items(target_experiments[0])
    cached_runs = runs_from_experiment_items(items[:1])
    cached_run = cached_runs[0]

    class MockProbeRegistry:
        def get_probe(self, probe_id):
            return None
        def get_probes(self):
            return {}

    class MockDeciderRegistry:
        def get_system_prompt(self, **kwargs):
            return ""

    runs_registry = create_runs_registry(MockProbeRegistry(), MockDeciderRegistry())
    runs_registry.populate_cache_bulk(cached_runs)

    ui_alignment_target = AlignmentTarget(
        id="ad_hoc",
        kdma_values=[KDMAValue(kdma="affiliation", value=0.0)]
    )

    ui_run = Run(
        id="ui-test-run",
        probe_id=cached_run.probe_id,
        decider_name=cached_run.decider_name,
        llm_backbone_name=cached_run.llm_backbone_name,
        system_prompt="",
        decider_params=DeciderParams(
            scenario_input=cached_run.decider_params.scenario_input,
            alignment_target=ui_alignment_target,
            resolved_config=cached_run.decider_params.resolved_config,
        ),
    )

    runs_registry.add_run(ui_run)
    fetched = runs_registry.get_run("ui-test-run")

    assert fetched is not None
    assert fetched.decision is not None
    assert fetched.decision.adm_result.decision.unstructured == cached_run.decision.adm_result.decision.unstructured


def test_cache_miss_with_different_params(single_experiment_path: Path):
    """Verify cache returns None when params don't match."""
    experiments = parse_experiments_directory(single_experiment_path.parent.parent)

    target_experiments = [
        exp for exp in experiments
        if "pipeline_baseline_greedy_w_cache" in str(exp.experiment_path)
        and "affiliation-0.0" in str(exp.experiment_path)
    ]

    items = get_experiment_items(target_experiments[0])
    cached_runs = runs_from_experiment_items(items[:1])
    cached_run = cached_runs[0]

    class MockProbeRegistry:
        def get_probe(self, probe_id):
            return None
        def get_probes(self):
            return {}

    class MockDeciderRegistry:
        def get_system_prompt(self, **kwargs):
            return ""

    runs_registry = create_runs_registry(MockProbeRegistry(), MockDeciderRegistry())
    runs_registry.populate_cache_bulk(cached_runs)

    different_alignment_target = AlignmentTarget(
        id="ad_hoc",
        kdma_values=[KDMAValue(kdma="affiliation", value=0.5)]
    )

    ui_run = Run(
        id="ui-test-run-miss",
        probe_id=cached_run.probe_id,
        decider_name=cached_run.decider_name,
        llm_backbone_name=cached_run.llm_backbone_name,
        system_prompt="",
        decider_params=DeciderParams(
            scenario_input=cached_run.decider_params.scenario_input,
            alignment_target=different_alignment_target,
            resolved_config=cached_run.decider_params.resolved_config,
        ),
    )

    runs_registry.add_run(ui_run)
    fetched = runs_registry.get_run("ui-test-run-miss")

    assert fetched is not None
    assert fetched.decision is None


def test_cache_preserved_after_clear_runs(single_experiment_path: Path):
    """Verify cache is preserved when runs are cleared."""
    experiments = parse_experiments_directory(single_experiment_path.parent.parent)

    target_experiments = [
        exp for exp in experiments
        if "pipeline_baseline_greedy_w_cache" in str(exp.experiment_path)
        and "affiliation-0.0" in str(exp.experiment_path)
    ]

    items = get_experiment_items(target_experiments[0])
    cached_runs = runs_from_experiment_items(items[:1])
    cached_run = cached_runs[0]

    class MockProbeRegistry:
        def get_probe(self, probe_id):
            return None
        def get_probes(self):
            return {}

    class MockDeciderRegistry:
        def get_system_prompt(self, **kwargs):
            return ""

    runs_registry = create_runs_registry(MockProbeRegistry(), MockDeciderRegistry())
    runs_registry.populate_cache_bulk(cached_runs)

    runs_registry.clear_runs()

    ui_alignment_target = AlignmentTarget(
        id="ad_hoc",
        kdma_values=[KDMAValue(kdma="affiliation", value=0.0)]
    )

    ui_run = Run(
        id="ui-after-clear",
        probe_id=cached_run.probe_id,
        decider_name=cached_run.decider_name,
        llm_backbone_name=cached_run.llm_backbone_name,
        system_prompt="",
        decider_params=DeciderParams(
            scenario_input=cached_run.decider_params.scenario_input,
            alignment_target=ui_alignment_target,
            resolved_config=cached_run.decider_params.resolved_config,
        ),
    )

    runs_registry.add_run(ui_run)
    fetched = runs_registry.get_run("ui-after-clear")

    assert fetched is not None
    assert fetched.decision is not None
