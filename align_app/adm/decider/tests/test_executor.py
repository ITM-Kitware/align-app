import pytest
from align_app.adm.decider.executor import instantiate_adm
from align_app.adm.decider.types import DeciderParams


@pytest.fixture
def instantiated_baseline_model(resolved_random_config):
    choose_action_func, cleanup_func = instantiate_adm(resolved_random_config)
    yield choose_action_func
    cleanup_func()


class TestExecuteAdmDecision:
    def test_execute_baseline_returns_adm_result(
        self,
        instantiated_baseline_model,
        scenario_input,
        alignment_target_baseline,
        resolved_random_config,
    ):
        params = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=resolved_random_config,
        )

        result = instantiated_baseline_model(params)

        assert result is not None
        assert hasattr(result, "decision")
        assert hasattr(result, "choice_info")
        assert result.decision.unstructured
        assert result.decision.justification

    def test_execute_returns_choice_info(
        self,
        instantiated_baseline_model,
        scenario_input,
        alignment_target_baseline,
        resolved_random_config,
    ):
        params = DeciderParams(
            scenario_input=scenario_input,
            alignment_target=alignment_target_baseline,
            resolved_config=resolved_random_config,
        )

        result = instantiated_baseline_model(params)

        assert result.choice_info is not None
