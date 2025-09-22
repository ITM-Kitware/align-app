from hydra.core.global_hydra import GlobalHydra

from align_app.adm.hydra_config_loader import load_adm_config


def test_load_regular_config():
    result = load_adm_config("adm/pipeline_baseline.yaml")
    assert "adm" in result
    assert "instance" in result["adm"]
    assert (
        result["adm"]["instance"]["_target_"]
        == "align_system.algorithms.pipeline_adm.PipelineADM"
    )


def test_load_experiment_config():
    result = load_adm_config(
        "experiment/phase2_july_collab/pipeline_fewshot_comparative_regression_20icl_live_eval_test.yaml"
    )
    assert "adm" in result
    adm = result["adm"]
    assert "step_definitions" in adm
    if "regression_icl" in adm["step_definitions"]:
        icl_settings = adm["step_definitions"]["regression_icl"]
        if "icl_generator_partial" in icl_settings:
            incontext = icl_settings["icl_generator_partial"].get(
                "incontext_settings", {}
            )
            assert incontext.get("number") == 20


def test_auto_detect_config_type():
    regular_result = load_adm_config("adm/pipeline_baseline.yaml")
    assert "adm" in regular_result

    experiment_result = load_adm_config(
        "experiment/phase2_july_collab/pipeline_fewshot_comparative_regression_20icl_live_eval_test.yaml"
    )
    assert "adm" in experiment_result


def test_caching_behavior():
    result1 = load_adm_config("adm/pipeline_baseline.yaml")
    result2 = load_adm_config("adm/pipeline_baseline.yaml")
    assert result1 == result2
    assert result1 is result2


def test_fresh_context_isolation():
    if GlobalHydra.instance().is_initialized():
        GlobalHydra.instance().clear()

    result1 = load_adm_config("adm/pipeline_baseline.yaml")
    assert not GlobalHydra.instance().is_initialized()

    result2 = load_adm_config("adm/pipeline_random.yaml")
    assert "adm" in result1
    assert "adm" in result2


def test_regular_vs_experiment_loading():
    regular_cfg = load_adm_config("adm/pipeline_baseline.yaml")
    assert "adm" in regular_cfg

    exp_cfg = load_adm_config(
        "experiment/phase2_july_collab/pipeline_fewshot_comparative_regression_20icl_live_eval_test.yaml"
    )
    assert "adm" in exp_cfg
    assert len(exp_cfg.keys()) > len(regular_cfg.keys())


def test_adm_core_integration_scenario():
    config_path = "adm/pipeline_baseline.yaml"
    full_cfg = load_adm_config(config_path)
    adm_cfg = full_cfg.get("adm", {})
    assert "instance" in adm_cfg
    assert "step_definitions" in adm_cfg

    full_cfg = load_adm_config(
        "experiment/phase2_july_collab/pipeline_fewshot_comparative_regression_20icl_live_eval_test.yaml"
    )
    adm_cfg = full_cfg.get("adm", {})
    assert "instance" in adm_cfg
    assert "step_definitions" in adm_cfg


def test_experiment_path_formats():
    exp_file = "pipeline_fewshot_comparative_regression_20icl_live_eval_test.yaml"

    test_cases = [
        f"experiment/phase2_july_collab/{exp_file}",
        f"phase2_july_collab/{exp_file}",
    ]

    results = []
    for config_path in test_cases:
        result = load_adm_config(config_path)
        results.append(result)
        assert "adm" in result

    if len(results) > 1:
        for i in range(1, len(results)):
            assert results[0]["adm"].keys() == results[i]["adm"].keys()
