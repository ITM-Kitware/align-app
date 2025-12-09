from typing import Any, Tuple
import gc
from functools import partial
from align_system.utils.hydra_utils import initialize_with_custom_references
from align_system.utils.hydrate_state import p2triage_hydrate_scenario_state
from align_utils.models import InputData, ADMResult, Decision, ChoiceInfo
from .types import DeciderParams


def hydrate_scenario_input(scenario_input: InputData) -> Tuple[Any, Any]:
    """Hydrate scenario input into state and actions for ADM.

    Args:
        scenario_input: InputData from align_utils containing scenario information

    Returns:
        Tuple of (state, actions) ready for ADM execution
    """
    full_state = scenario_input.full_state or {}
    full_state_with_defaults = {
        **full_state,
        "environment": full_state.get("environment") or {},
        "supplies": full_state.get("supplies") or {},
    }

    record = {
        "scenario_id": scenario_input.scenario_id,
        "full_state": full_state_with_defaults,
        "state": scenario_input.state,
        "choices": scenario_input.choices,
    }

    return p2triage_hydrate_scenario_state(record)


def choose_action(model: Any, params: DeciderParams) -> ADMResult:
    """Choose an action using the ADM model.

    Handles hydration and execution.

    Args:
        model: Instantiated ADM model
        params: DeciderParams with scenario_input, alignment_target, resolved_config

    Returns:
        ADMResult with decision and choice_info
    """

    state, actions = hydrate_scenario_input(params.scenario_input)

    func = (
        model.instance.top_level_choose_action
        if hasattr(model.instance, "top_level_choose_action")
        else model.instance.choose_action
    )

    result = func(
        scenario_state=state,
        available_actions=actions,
        alignment_target=params.alignment_target.model_dump(),
        **model.get("inference_kwargs", {}),
        reasoning_max_length=-1,
        max_generator_tokens=-1,
        generator_seed=2,
    )

    raw_decision = result[0]
    choice_info_dict = result[1]["choice_info"]

    return ADMResult(
        decision=Decision(
            unstructured=raw_decision.unstructured,
            justification=raw_decision.justification,
        ),
        choice_info=ChoiceInfo(**choice_info_dict)
        if isinstance(choice_info_dict, dict)
        else choice_info_dict,
    )


def instantiate_adm(decider_config):
    """Instantiate an ADM from a resolved config.

    The config should already have llm_backbone merged into it by the app layer.

    Args:
        decider_config: Fully resolved configuration dict

    Returns: (choose_action_func, cleanup_func)
        Tuple of curried functions - choose_action with model baked in, and cleanup
    """
    if decider_config is None:
        raise ValueError("decider_config is required")

    adm = initialize_with_custom_references({"adm": decider_config})["adm"]

    def cleanup(_):
        import torch

        gc.collect()
        torch.cuda.empty_cache()

    return partial(choose_action, adm), partial(cleanup, adm)
