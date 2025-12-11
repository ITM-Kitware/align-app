"""Update runs with new scenes and scenarios."""

from typing import Optional, Dict, Any
from ..adm.run_models import Run
from ..adm.probe import Probe
import copy
from .runs_presentation import (
    get_scenes_for_base_scenario,
    get_llm_backbones_from_config,
    get_max_alignment_attributes,
)
from align_utils.models import AlignmentTarget, KDMAValue


def create_default_choice(index: int, text: str) -> Dict[str, Any]:
    return {
        "action_id": f"action-{index}",
        "unstructured": text,
        "action_type": "APPLY_TREATMENT",
        "intent_action": True,
        "parameters": {},
        "justification": None,
    }


def find_probe_by_scenario_and_scene(
    probes: Dict[str, Probe], scenario_id: str, scene_id: str
) -> str:
    matches = [
        probe_id
        for probe_id, probe in probes.items()
        if probe.scenario_id == scenario_id and probe.scene_id == scene_id
    ]
    return matches[0] if matches else ""


def get_first_scene_for_scenario(probes: Dict[str, Probe], scenario_id: str) -> str:
    scene_items = get_scenes_for_base_scenario(probes, scenario_id)
    return scene_items[0]["value"] if scene_items else ""


def build_run_with_new_scene(run: Run, probe: Probe) -> Run:
    """Build new Run with updated scene probe.

    Pure domain transformation - just updates scene/probe data.
    Doesn't touch decision field.
    """
    updated_params = run.decider_params.model_copy(
        update={"scenario_input": probe.item.input}
    )

    return run.model_copy(
        update={"probe_id": probe.probe_id, "decider_params": updated_params}
    )


def prepare_scene_update(
    run: Run, scene_id: str, *, probe_registry, decider_registry=None
) -> Optional[Run]:
    """Prepare run with new scene (orchestration + transformation).

    Performs lookups and builds updated run with new scene.
    Used by factory-generated registry methods.
    """
    current_probe = probe_registry.get_probe(run.probe_id)
    if not current_probe:
        return None

    base_scenario_id = current_probe.scenario_id

    probes = probe_registry.get_probes()
    new_probe_id = find_probe_by_scenario_and_scene(probes, base_scenario_id, scene_id)
    new_probe = probe_registry.get_probe(new_probe_id)

    if not new_probe:
        return None

    return build_run_with_new_scene(run, new_probe)


def prepare_scenario_update(
    run: Run, scenario_id: str, *, probe_registry, decider_registry=None
) -> Optional[Run]:
    """Prepare run with new scenario (orchestration + transformation).

    Performs lookups and builds updated run with new scenario.
    Auto-selects first scene_id in the new scenario.
    Used by factory-generated registry methods.
    """
    probes = probe_registry.get_probes()
    first_scene_id = get_first_scene_for_scenario(probes, scenario_id)

    if not first_scene_id:
        return None

    new_probe_id = find_probe_by_scenario_and_scene(probes, scenario_id, first_scene_id)
    new_probe = probe_registry.get_probe(new_probe_id)

    if not new_probe:
        return None

    return build_run_with_new_scene(run, new_probe)


def prepare_decider_update(
    run: Run, decider_name: str, *, probe_registry=None, decider_registry
) -> Optional[Run]:
    """Prepare run with new decider (orchestration + transformation).

    Gets new resolved_config for the decider and builds updated run.
    Auto-selects appropriate LLM if current one is not available in new decider.
    Used by factory-generated registry methods.
    """
    decider_options = decider_registry.get_decider_options(run.probe_id, decider_name)
    available_llms = get_llm_backbones_from_config(decider_options)

    llm_backbone = run.llm_backbone_name
    if llm_backbone not in available_llms:
        llm_backbone = available_llms[0] if available_llms else "N/A"

    resolved_config = decider_registry.get_decider_config(
        probe_id=run.probe_id,
        decider=decider_name,
        llm_backbone=llm_backbone,
    )

    if resolved_config is None:
        return None

    updated_params = run.decider_params.model_copy(
        update={"resolved_config": resolved_config}
    )

    return run.model_copy(
        update={
            "decider_name": decider_name,
            "llm_backbone_name": llm_backbone,
            "decider_params": updated_params,
        }
    )


def prepare_llm_update(
    run: Run, llm_backbone: str, *, probe_registry=None, decider_registry
) -> Optional[Run]:
    """Prepare run with new LLM backbone (orchestration + transformation).

    Gets new resolved_config for the LLM backbone and builds updated run.
    Used by factory-generated registry methods.
    """
    resolved_config = decider_registry.get_decider_config(
        probe_id=run.probe_id,
        decider=run.decider_name,
        llm_backbone=llm_backbone,
    )

    if resolved_config is None:
        return None

    updated_params = run.decider_params.model_copy(
        update={"resolved_config": resolved_config}
    )

    return run.model_copy(
        update={"llm_backbone_name": llm_backbone, "decider_params": updated_params}
    )


def prepare_add_alignment_attribute(
    run: Run, _: Any, *, probe_registry, decider_registry
) -> Optional[Run]:
    """Add first available alignment attribute to the run."""
    decider_options = decider_registry.get_decider_options(
        run.probe_id, run.decider_name
    )
    max_attrs = get_max_alignment_attributes(decider_options)

    current_kdmas = run.decider_params.alignment_target.kdma_values
    if len(current_kdmas) >= max_attrs:
        return None

    all_attrs = probe_registry.get_attributes(run.probe_id)
    used_kdmas = {kv.kdma for kv in current_kdmas}
    available = [k for k in all_attrs.keys() if k not in used_kdmas]

    if not available:
        return None

    first_available = available[0]
    attr_info = all_attrs[first_available]
    possible_scores = attr_info.get("possible_scores", "continuous")
    initial_score = 0.0 if possible_scores == "continuous" else 0

    new_kdma = KDMAValue(kdma=first_available, value=initial_score, kdes=None)
    new_kdma_values = list(current_kdmas) + [new_kdma]

    new_alignment_target = AlignmentTarget(
        id=run.decider_params.alignment_target.id, kdma_values=new_kdma_values
    )
    updated_params = run.decider_params.model_copy(
        update={"alignment_target": new_alignment_target}
    )
    return run.model_copy(update={"decider_params": updated_params})


def prepare_update_alignment_attribute_value(
    run: Run, payload: Dict[str, Any], *, probe_registry, decider_registry
) -> Optional[Run]:
    """Update KDMA type for an alignment attribute."""
    attr_index = payload["attr_index"]
    new_kdma = payload["value"]

    current_kdmas = list(run.decider_params.alignment_target.kdma_values)
    if attr_index < 0 or attr_index >= len(current_kdmas):
        return None

    all_attrs = probe_registry.get_attributes(run.probe_id)
    attr_info = all_attrs.get(new_kdma, {})
    possible_scores = attr_info.get("possible_scores", "continuous")
    initial_score = 0.0 if possible_scores == "continuous" else 0

    current_kdmas[attr_index] = KDMAValue(kdma=new_kdma, value=initial_score, kdes=None)

    new_alignment_target = AlignmentTarget(
        id=run.decider_params.alignment_target.id, kdma_values=current_kdmas
    )
    updated_params = run.decider_params.model_copy(
        update={"alignment_target": new_alignment_target}
    )
    return run.model_copy(update={"decider_params": updated_params})


def prepare_update_alignment_attribute_score(
    run: Run, payload: Dict[str, Any], *, probe_registry=None, decider_registry=None
) -> Optional[Run]:
    """Update score for an alignment attribute."""
    attr_index = payload["attr_index"]
    new_score = payload["score"]

    current_kdmas = list(run.decider_params.alignment_target.kdma_values)
    if attr_index < 0 or attr_index >= len(current_kdmas):
        return None

    old_kdma = current_kdmas[attr_index]
    current_kdmas[attr_index] = KDMAValue(
        kdma=old_kdma.kdma, value=new_score, kdes=old_kdma.kdes
    )

    new_alignment_target = AlignmentTarget(
        id=run.decider_params.alignment_target.id, kdma_values=current_kdmas
    )
    updated_params = run.decider_params.model_copy(
        update={"alignment_target": new_alignment_target}
    )
    return run.model_copy(update={"decider_params": updated_params})


def prepare_delete_alignment_attribute(
    run: Run, attr_index: int, *, probe_registry=None, decider_registry=None
) -> Optional[Run]:
    """Remove an alignment attribute from the run."""
    current_kdmas = list(run.decider_params.alignment_target.kdma_values)
    if attr_index < 0 or attr_index >= len(current_kdmas):
        return None

    new_kdma_values = [kv for i, kv in enumerate(current_kdmas) if i != attr_index]

    new_alignment_target = AlignmentTarget(
        id=run.decider_params.alignment_target.id, kdma_values=new_kdma_values
    )
    updated_params = run.decider_params.model_copy(
        update={"alignment_target": new_alignment_target}
    )
    return run.model_copy(update={"decider_params": updated_params})


def prepare_update_probe_text(
    run: Run, text: str, *, probe_registry=None, decider_registry=None
) -> Optional[Run]:
    """Update run's scenario_input.full_state.unstructured."""
    scenario_input = run.decider_params.scenario_input
    updated_full_state = copy.deepcopy(scenario_input.full_state) or {}
    updated_full_state["unstructured"] = text

    new_scenario_input = scenario_input.model_copy(
        update={"full_state": updated_full_state}
    )
    updated_params = run.decider_params.model_copy(
        update={"scenario_input": new_scenario_input}
    )
    return run.model_copy(update={"decider_params": updated_params})


def prepare_update_choice_text(
    run: Run, payload: Dict[str, Any], *, probe_registry=None, decider_registry=None
) -> Optional[Run]:
    """Update choice text at index. payload = {"index": int, "text": str}"""
    index, text = payload["index"], payload["text"]
    scenario_input = run.decider_params.scenario_input
    choices = list(scenario_input.choices or [])

    if index < 0 or index >= len(choices):
        return None

    choices[index] = {**choices[index], "unstructured": text}
    new_scenario_input = scenario_input.model_copy(update={"choices": choices})
    updated_params = run.decider_params.model_copy(
        update={"scenario_input": new_scenario_input}
    )
    return run.model_copy(update={"decider_params": updated_params})


def prepare_add_run_choice(
    run: Run, _, *, probe_registry=None, decider_registry=None
) -> Optional[Run]:
    """Add new empty choice."""
    scenario_input = run.decider_params.scenario_input
    choices = list(scenario_input.choices or [])
    new_choice = create_default_choice(len(choices), "")
    choices.append(new_choice)

    new_scenario_input = scenario_input.model_copy(update={"choices": choices})
    updated_params = run.decider_params.model_copy(
        update={"scenario_input": new_scenario_input}
    )
    return run.model_copy(update={"decider_params": updated_params})


def prepare_delete_run_choice(
    run: Run, index: int, *, probe_registry=None, decider_registry=None
) -> Optional[Run]:
    """Remove choice at index (min 2 choices)."""
    scenario_input = run.decider_params.scenario_input
    choices = list(scenario_input.choices or [])

    if len(choices) <= 2 or index < 0 or index >= len(choices):
        return None

    choices = [c for i, c in enumerate(choices) if i != index]
    new_scenario_input = scenario_input.model_copy(update={"choices": choices})
    updated_params = run.decider_params.model_copy(
        update={"scenario_input": new_scenario_input}
    )
    return run.model_copy(update={"decider_params": updated_params})
