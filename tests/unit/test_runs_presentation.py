from unittest.mock import MagicMock, patch
from align_app.app.runs_presentation import run_to_state_dict
from align_app.adm.run_models import Run


@patch("align_app.app.runs_presentation.get_decider_config")
@patch("align_app.app.runs_presentation.hash_run_params")
def test_run_to_state_dict_creates_comparison_label(mock_hash, mock_get_config):
    mock_hash.return_value = "mock_hash"
    mock_get_config.return_value = {}

    # Setup mocks
    mock_run = MagicMock(spec=Run)
    mock_run.id = "run-123"
    mock_run.probe_id = "test-probe"
    mock_run.decider_name = "test-decider"
    mock_run.llm_backbone_name = "gpt-4"
    mock_run.decision = None

    # Mock decider_params
    mock_params = MagicMock()
    mock_params.scenario_input.scenario_id = "test-scenario"
    mock_params.scenario_input.full_state = {"meta_info": {"scene_id": "test-scene"}}
    mock_params.resolved_config = {}  # Set explicit empty dict
    mock_params.alignment_target.kdma_values = [
        MagicMock(kdma="completeness", value=0.8),
        MagicMock(kdma="speed", value=0.2),
    ]
    mock_run.decider_params = mock_params

    # Mock registries
    mock_probe_registry = MagicMock()
    mock_decider_registry = MagicMock()

    # Mock system prompt and configuration
    mock_run.system_prompt = "Test System Prompt"
    mock_decider_registry.get_all_deciders.return_value = {"test-decider": {}}
    mock_decider_registry.get_system_prompt.return_value = "Test System Prompt"
    mock_decider_registry.get_decider_options.return_value = {
        "llm_backbones": ["gpt-4"],
        "max_alignment_attributes": 3,
    }
    mock_probe_registry.get_probes.return_value = {}  # Return empty dict of probes

    # Mock attribute descriptions
    mock_probe_registry.get_attributes.return_value = {
        "completeness": {"possible_scores": "continuous"},
        "speed": {"possible_scores": "continuous"},
    }

    # Execute
    result = run_to_state_dict(mock_run, mock_probe_registry, mock_decider_registry)

    # Verify
    expected_label = "test-scenario - test-scene - Completeness 0.8, Speed 0.2 - test-decider - gpt-4"
    assert result["comparison_label"] == expected_label


@patch("align_app.app.runs_presentation.get_decider_config")
@patch("align_app.app.runs_presentation.hash_run_params")
def test_run_to_state_dict_creates_comparison_label_no_alignment(
    mock_hash, mock_get_config
):
    mock_hash.return_value = "mock_hash"
    mock_get_config.return_value = {}

    # Setup mocks
    mock_run = MagicMock(spec=Run)
    mock_run.id = "run-123"
    mock_run.probe_id = "test-probe"
    mock_run.decider_name = "test-decider"
    mock_run.llm_backbone_name = "gpt-4"
    mock_run.decision = None

    mock_params = MagicMock()
    mock_params.scenario_input.scenario_id = "test-scenario"
    mock_params.scenario_input.full_state = {"meta_info": {"scene_id": "test-scene"}}
    mock_params.resolved_config = {}
    mock_params.alignment_target.kdma_values = []
    mock_run.decider_params = mock_params

    mock_probe_registry = MagicMock()
    mock_decider_registry = MagicMock()

    mock_decider_registry.get_all_deciders.return_value = {"test-decider": {}}
    mock_decider_registry.get_decider_options.return_value = {}
    mock_decider_registry.get_system_prompt.return_value = "Test System Prompt"
    mock_probe_registry.get_attributes.return_value = {}
    mock_probe_registry.get_probes.return_value = {}  # Return empty dict of probes

    mock_run.system_prompt = "Test System Prompt"

    # Execute
    result = run_to_state_dict(mock_run, mock_probe_registry, mock_decider_registry)

    # Verify
    expected_label = "test-scenario - test-scene - No Alignment - test-decider - gpt-4"
    assert result["comparison_label"] == expected_label
