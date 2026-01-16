"""Tests for experiment decider loading and instantiation."""

from pathlib import Path


def test_experiment_fixtures_download(experiments_fixtures_path: Path):
    """Verify experiment fixtures are downloaded and extracted."""
    assert experiments_fixtures_path.exists()
    assert experiments_fixtures_path.is_dir()

    experiment_dirs = list(experiments_fixtures_path.iterdir())
    assert len(experiment_dirs) >= 3, "Expected at least 3 experiment types"


def test_experiment_registry_loads_items(experiments_fixtures_path: Path):
    """Verify experiment results registry loads all experiment items."""
    from align_app.adm.experiment_results_registry import (
        create_experiment_results_registry,
    )

    registry = create_experiment_results_registry(experiments_fixtures_path)

    all_items = registry.get_all_items()
    assert len(all_items) > 0, "Expected experiment items to be loaded"


def test_unique_deciders_extracted(experiments_fixtures_path: Path):
    """Verify deciders are extracted from experiments, one per decider batch."""
    from align_app.adm.experiment_converters import deciders_from_experiments
    from align_app.adm.experiment_results_registry import (
        create_experiment_results_registry,
    )

    registry = create_experiment_results_registry(experiments_fixtures_path)

    experiment_deciders = deciders_from_experiments(
        registry.get_experiments(), experiments_fixtures_path
    )
    assert len(experiment_deciders) == 5, (
        f"Expected 5 deciders (one per decider batch), got {len(experiment_deciders)}"
    )

    expected_deciders = {
        "pipeline_fewshot_comparative_regression_loo_20icl",
        "pipeline_fewshot_comparative_regression_loo_20icl_rerun",
        "pipeline_baseline",
        "pipeline_baseline_greedy_w_cache",
        "pipeline_baseline_multi",
    }
    assert set(experiment_deciders.keys()) == expected_deciders


def test_experiment_decider_config_loading(experiments_fixtures_path: Path):
    """Verify experiment decider configs can be loaded."""
    from align_app.adm.experiment_config_loader import load_experiment_adm_config
    from align_app.adm.experiment_converters import deciders_from_experiments
    from align_app.adm.experiment_results_registry import (
        create_experiment_results_registry,
    )

    registry = create_experiment_results_registry(experiments_fixtures_path)
    experiment_deciders = deciders_from_experiments(
        registry.get_experiments(), experiments_fixtures_path
    )

    for name, entry in experiment_deciders.items():
        config = load_experiment_adm_config(Path(entry["experiment_path"]))

        assert config is not None, f"Config for {name} could not be loaded"
        assert "instance" in config, f"Config for {name} missing 'instance'"
        assert config["instance"].get("_target_"), (
            f"Config for {name} missing instance._target_"
        )


def test_decider_registry_includes_experiment_deciders(experiments_fixtures_path: Path):
    """Verify decider registry includes experiment deciders."""
    from align_app.adm.decider_registry import create_decider_registry
    from align_app.adm.experiment_converters import (
        deciders_from_experiments,
        probes_from_experiment_items,
    )
    from align_app.adm.experiment_results_registry import (
        create_experiment_results_registry,
    )
    from align_app.adm.probe_registry import create_probe_registry

    exp_registry = create_experiment_results_registry(experiments_fixtures_path)

    probe_registry = create_probe_registry(scenarios_paths=[])
    experiment_probes = probes_from_experiment_items(exp_registry.get_all_items())
    probe_registry.add_probes(experiment_probes)

    experiment_deciders = deciders_from_experiments(
        exp_registry.get_experiments(), experiments_fixtures_path
    )

    decider_registry = create_decider_registry(
        config_paths=[],
        scenario_registry=probe_registry,
        experiment_deciders=experiment_deciders,
    )

    all_deciders = decider_registry.get_all_deciders()

    for exp_name in experiment_deciders:
        assert exp_name in all_deciders, (
            f"Experiment decider {exp_name} not in registry"
        )
        assert all_deciders[exp_name].get("experiment_config") is True


def test_get_decider_config_for_experiment(experiments_fixtures_path: Path):
    """Verify get_decider_config works for experiment deciders."""
    from align_app.adm.decider_registry import create_decider_registry
    from align_app.adm.experiment_converters import (
        deciders_from_experiments,
        probes_from_experiment_items,
    )
    from align_app.adm.experiment_results_registry import (
        create_experiment_results_registry,
    )
    from align_app.adm.probe_registry import create_probe_registry

    exp_registry = create_experiment_results_registry(experiments_fixtures_path)

    probe_registry = create_probe_registry(scenarios_paths=[])
    experiment_probes = probes_from_experiment_items(exp_registry.get_all_items())
    probe_registry.add_probes(experiment_probes)

    experiment_deciders = deciders_from_experiments(
        exp_registry.get_experiments(), experiments_fixtures_path
    )

    decider_registry = create_decider_registry(
        config_paths=[],
        scenario_registry=probe_registry,
        experiment_deciders=experiment_deciders,
    )

    probes = probe_registry.get_probes()
    probe_id = next(iter(probes.keys()))
    exp_decider_name = "pipeline_fewshot_comparative_regression_loo_20icl"

    config = decider_registry.get_decider_config(
        probe_id=probe_id,
        decider=exp_decider_name,
    )

    assert config is not None
    assert "instance" in config
    assert (
        config["instance"]["_target_"]
        == "align_system.algorithms.pipeline_adm.PipelineADM"
    )
