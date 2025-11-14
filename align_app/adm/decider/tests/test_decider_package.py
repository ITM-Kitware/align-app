import pytest
from align_app.adm.decider import MultiprocessDecider, DeciderParams


@pytest.fixture
def decider_params(scenario_input, alignment_target_baseline, resolved_random_config):
    return DeciderParams(
        scenario_input=scenario_input,
        alignment_target=alignment_target_baseline,
        resolved_config=resolved_random_config,
    )


class TestMultiprocessDecider:
    @pytest.mark.anyio
    async def test_can_import_from_package(self):
        from align_app.adm.decider import MultiprocessDecider, DeciderParams

        assert MultiprocessDecider is not None
        assert DeciderParams is not None

    @pytest.mark.anyio
    async def test_executes_decision_successfully(self, decider_params):
        decider = MultiprocessDecider()

        try:
            result = await decider.get_decision(decider_params)

            assert result is not None
            assert hasattr(result, "decision")
            assert hasattr(result.decision, "unstructured")
            assert hasattr(result.decision, "justification")
            assert result.decision.unstructured is not None
        finally:
            decider.shutdown()

    @pytest.mark.anyio
    async def test_multiple_decisions_succeed(self, decider_params):
        decider = MultiprocessDecider()

        try:
            for _ in range(3):
                result = await decider.get_decision(decider_params)
                assert result is not None
                assert hasattr(result, "decision")
        finally:
            decider.shutdown()

    def test_shutdown_is_idempotent(self, decider_params):
        import asyncio

        decider = MultiprocessDecider()

        asyncio.run(decider.get_decision(decider_params))

        decider.shutdown()
        decider.shutdown()
