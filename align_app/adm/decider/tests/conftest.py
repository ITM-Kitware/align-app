import json
from pathlib import Path
import pytest
import multiprocessing as mp
from omegaconf import OmegaConf
from align_utils.models import InputData
import align_system


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def scenario_input():
    json_path = (
        Path(align_system.__file__).parent
        / "resources"
        / "icl"
        / "phase2"
        / "July2025-PS-train_20250804.json"
    )

    with open(json_path) as f:
        examples = json.load(f)

    input_data_dict = examples[0]["input"]
    return InputData.model_validate(input_data_dict)


@pytest.fixture(scope="module")
def resolved_random_config():
    return {
        "step_definitions": {
            "format_choices": {
                "_target_": "align_system.algorithms.misc_itm_adm_components.ITMFormatChoicesADMComponent"
            },
            "random_choice": {
                "_target_": "align_system.algorithms.random_adm_component.RandomChoiceADMComponent"
            },
            "random_action_parameter_completion": {
                "_target_": "align_system.algorithms.random_adm_component.RandomParameterCompletionADMComponent"
            },
            "ensure_chosen_action": {
                "_target_": "align_system.algorithms.misc_itm_adm_components.EnsureChosenActionADMComponent"
            },
            "populate_choice_info": {
                "_target_": "align_system.algorithms.misc_itm_adm_components.PopulateChoiceInfo"
            },
        },
        "name": "pipeline_random",
        "instance": {
            "_target_": "align_system.algorithms.pipeline_adm.PipelineADM",
            "steps": [
                "${ref:adm.step_definitions.format_choices}",
                "${ref:adm.step_definitions.random_choice}",
                "${ref:adm.step_definitions.random_action_parameter_completion}",
                "${ref:adm.step_definitions.ensure_chosen_action}",
                "${ref:adm.step_definitions.populate_choice_info}",
            ],
        },
    }


@pytest.fixture(scope="module")
def alignment_target_baseline():
    return OmegaConf.create(
        {
            "_target_": "swagger_client.models.AlignmentTarget",
            "id": "baseline",
            "kdma_values": [],
        }
    )


@pytest.fixture
def worker_queues():
    ctx = mp.get_context("spawn")
    manager = ctx.Manager()
    request_queue = manager.Queue()
    response_queue = manager.Queue()
    yield request_queue, response_queue
