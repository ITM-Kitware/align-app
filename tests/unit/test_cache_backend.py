from align_utils.models import InputData, AlignmentTarget, KDMAValue


def test_hash_run_params_generates_consistent_key():
    from align_app.app.run_models import hash_run_params
    from align_app.adm.decider.types import DeciderParams

    scenario_input = InputData(
        scenario_id="test_scenario",
        state="scenario text",
        choices=[{"unstructured": "A"}, {"unstructured": "B"}],
    )

    alignment_target = AlignmentTarget(
        id="test_target",
        kdma_values=[KDMAValue(kdma="Medical", value=0.5)],
    )

    decider_params = DeciderParams(
        scenario_input=scenario_input,
        alignment_target=alignment_target,
        resolved_config={},
    )

    hash1 = hash_run_params(
        probe_id="test.scene.probe",
        decider_name="adept-icl-template",
        llm_backbone_name="gpt-4o",
        decider_params=decider_params,
    )

    hash2 = hash_run_params(
        probe_id="test.scene.probe",
        decider_name="adept-icl-template",
        llm_backbone_name="gpt-4o",
        decider_params=decider_params,
    )

    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) == 32


def test_hash_run_params_different_for_changed_params():
    from align_app.app.run_models import hash_run_params
    from align_app.adm.decider.types import DeciderParams

    scenario_input = InputData(
        scenario_id="test_scenario",
        state="scenario text",
        choices=[{"unstructured": "A"}, {"unstructured": "B"}],
    )

    alignment_target = AlignmentTarget(
        id="test_target",
        kdma_values=[KDMAValue(kdma="Medical", value=0.5)],
    )

    decider_params = DeciderParams(
        scenario_input=scenario_input,
        alignment_target=alignment_target,
        resolved_config={},
    )

    hash1 = hash_run_params(
        probe_id="test.scene.probe",
        decider_name="adept-icl-template",
        llm_backbone_name="gpt-4o",
        decider_params=decider_params,
    )

    hash2 = hash_run_params(
        probe_id="test.scene.probe",
        decider_name="different-decider",
        llm_backbone_name="gpt-4o",
        decider_params=decider_params,
    )

    assert hash1 != hash2
