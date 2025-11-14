import pytest
from omegaconf import OmegaConf
from align_app.adm.probe_registry import create_probe_registry
from align_app.adm.adm_core import get_all_deciders
from align_app.adm.config import get_decider_config


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
def alignment_target_with_kdma():
    return OmegaConf.create(
        {
            "_target_": "swagger_client.models.AlignmentTarget",
            "id": "test-alignment",
            "kdma_values": [{"kdma": "medical", "value": 0.5}],
        }
    )


@pytest.fixture
def alignment_target_baseline():
    return OmegaConf.create(
        {
            "_target_": "swagger_client.models.AlignmentTarget",
            "id": "baseline",
            "kdma_values": [],
        }
    )


class TestGetDeciderConfig:
    def test_returns_merged_config_for_valid_decider(
        self, sample_probe, all_deciders, datasets
    ):
        result = get_decider_config(
            sample_probe.probe_id, "pipeline_baseline", all_deciders, datasets
        )

        assert result is not None
        assert isinstance(result, dict)

    def test_returns_none_for_invalid_decider(
        self, sample_probe, all_deciders, datasets
    ):
        result = get_decider_config(
            sample_probe.probe_id, "nonexistent_decider", all_deciders, datasets
        )

        assert result is None

    def test_merges_config_overrides(self, sample_probe, all_deciders, datasets):
        result = get_decider_config(
            sample_probe.probe_id,
            "phase2_pipeline_zeroshot_comparative_regression",
            all_deciders,
            datasets,
        )

        assert result is not None
        assert isinstance(result, dict)


class TestInstantiateAdm:
    def test_instantiate_returns_model_and_cleanup(
        self, sample_probe, all_deciders, datasets
    ):
        from align_app.adm.decider.executor import instantiate_adm

        config = get_decider_config(
            sample_probe.probe_id,
            "pipeline_baseline",
            all_deciders,
            datasets,
        )

        model, cleanup = instantiate_adm(config)

        assert model is not None
        assert cleanup is not None
        assert callable(cleanup)

        cleanup()

    def test_instantiate_with_llm_backbone(self, sample_probe, all_deciders, datasets):
        from align_app.adm.decider.executor import instantiate_adm

        config = get_decider_config(
            sample_probe.probe_id,
            "pipeline_baseline",
            all_deciders,
            datasets,
        )

        model, cleanup = instantiate_adm(config)

        assert model is not None

        cleanup()

    def test_instantiate_raises_for_none_config(self):
        from align_app.adm.decider.executor import instantiate_adm

        with pytest.raises(ValueError, match="decider_config is required"):
            instantiate_adm(None)
