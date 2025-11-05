import pytest
from omegaconf import OmegaConf
from align_app.adm.probe_registry import create_probe_registry
from align_app.adm.adm_core import get_all_deciders
from align_app.adm.config import resolve_decider_config
from align_app.adm.decider import MultiprocessDecider, DeciderParams


@pytest.fixture
def probe_registry():
    return create_probe_registry()


@pytest.fixture
def sample_probe(probe_registry):
    probes = probe_registry.get_probes()
    return list(probes.values())[0]


@pytest.fixture
def datasets(probe_registry):
    return probe_registry.get_datasets()


@pytest.fixture
def all_deciders():
    return get_all_deciders()


@pytest.fixture
def alignment_target_baseline():
    return OmegaConf.create(
        {
            "_target_": "swagger_client.models.AlignmentTarget",
            "id": "baseline",
            "kdma_values": [],
        }
    )


@pytest.fixture
def decider_params(sample_probe, alignment_target_baseline, all_deciders, datasets):
    resolved_config = resolve_decider_config(
        sample_probe.probe_id,
        "pipeline_random",
        alignment_target_baseline,
        all_deciders,
        datasets,
    )

    return DeciderParams(
        scenario_input=sample_probe.item.input,
        alignment_target=alignment_target_baseline,
        resolved_config=resolved_config,
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
    async def test_multiple_decisions_reuse_worker(self, decider_params):
        decider = MultiprocessDecider()

        try:
            result1 = await decider.get_decision(decider_params)
            process1_pid = decider.process.pid

            result2 = await decider.get_decision(decider_params)
            process2_pid = decider.process.pid

            assert result1 is not None
            assert result2 is not None
            assert process1_pid == process2_pid
        finally:
            decider.shutdown()

    def test_shutdown_stops_worker_process(self, decider_params):
        import asyncio

        decider = MultiprocessDecider()

        asyncio.run(decider.get_decision(decider_params))

        process = decider.process
        assert process.is_alive()

        decider.shutdown()

        process.join(timeout=2)
        assert not process.is_alive()
