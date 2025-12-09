"""Transform domain models to UI state dictionaries and export formats."""

from typing import Dict, Any, List
from ..adm.run_models import Run, RunDecision, hash_run_params
from .ui import prep_decision_for_state
from .prompt_logic import (
    get_llm_backbones_from_config,
    get_max_alignment_attributes,
    compute_possible_attributes,
)
from ..adm.probe import Probe
from ..utils.utils import readable
import json
import copy
import yaml


def resolved_config_to_yaml(resolved_config: Dict[str, Any] | None) -> str:
    if not resolved_config:
        return ""
    return yaml.dump(resolved_config, default_flow_style=False, sort_keys=False)


def extract_base_scenarios(probes: Dict[str, Probe]) -> List[Dict]:
    """Extract unique base scenario IDs from all probes."""
    unique_bases = sorted(set(probe.scenario_id for probe in probes.values()))
    return [{"value": id, "title": id} for id in unique_bases]


def get_scenes_for_base_scenario(
    probes: Dict[str, Probe], scenario_id: str
) -> List[Dict]:
    scene_map = {
        probe.scene_id: (probe.display_state or "").split("\n")[0]
        for probe in probes.values()
        if probe.scenario_id == scenario_id
    }

    return [
        {
            "value": scene_id,
            "title": f"{scene_id} - {text[:50]}{'...' if len(text) > 50 else ''}",
        }
        for scene_id, text in scene_map.items()
    ]


def kdma_values_to_alignment_attributes(
    kdma_values: List, all_attrs: Dict, descriptions: Dict
) -> List[Dict[str, Any]]:
    """Transform kdma_values to UI-format alignment_attributes."""
    result = []
    for i, kv in enumerate(kdma_values):
        kdma = kv.kdma if hasattr(kv, "kdma") else kv.get("kdma")
        value = kv.value if hasattr(kv, "value") else kv.get("value")
        attr_info = all_attrs.get(kdma, {})
        result.append(
            {
                "index": i,
                "value": kdma,
                "score": value,
                "title": readable(kdma),
                "description": descriptions.get(kdma, {}).get(
                    "description", f"No description for {kdma}"
                ),
                "possible_scores": attr_info.get("possible_scores", "continuous"),
            }
        )
    return result


def _get_attribute_descriptions(
    run: Run, probe_registry, decider_registry
) -> Dict[str, Any]:
    """Extract attribute_definitions from decider config."""
    all_deciders = decider_registry.get_all_deciders()
    datasets = probe_registry.get_datasets()
    from ..adm.config import get_decider_config as get_config

    config = get_config(run.probe_id, all_deciders, datasets, run.decider_name)
    if not config:
        return {}

    from omegaconf import OmegaConf

    config.pop("instance", None)
    config.pop("step_definitions", None)
    resolved = OmegaConf.to_container(OmegaConf.create({"adm": config}), resolve=True)
    if isinstance(resolved, dict):
        return resolved.get("adm", {}).get("attribute_definitions", {})
    return {}


def _compute_possible_alignment_attributes(
    run: Run, all_attrs: Dict, descriptions: Dict
) -> List[Dict[str, Any]]:
    """Compute available alignment attributes not currently in use."""
    used_kdmas = {kv.kdma for kv in run.decider_params.alignment_target.kdma_values}
    possible = compute_possible_attributes(all_attrs, used_kdmas, descriptions)
    return [
        {
            "value": p["value"],
            "title": readable(p["value"]),
            "possible_scores": p.get("possible_scores", "continuous"),
            "description": p.get("description", ""),
        }
        for p in possible
    ]


def decision_to_state_dict(decision: RunDecision) -> Dict[str, Any]:
    choice_letter = chr(decision.choice_index + ord("A"))

    decision_dict = {
        "unstructured": f"{choice_letter}. {decision.adm_result.decision.unstructured}",
        "justification": decision.adm_result.decision.justification,
        "choice_info": decision.adm_result.choice_info.model_dump(exclude_none=True),
    }

    return prep_decision_for_state(decision_dict)


def run_to_state_dict(
    run: Run, probe_registry=None, decider_registry=None
) -> Dict[str, Any]:
    scenario_input = run.decider_params.scenario_input

    display_state = None
    if scenario_input.full_state and "unstructured" in scenario_input.full_state:
        display_state = scenario_input.full_state["unstructured"]

    scene_id = None
    if (
        scenario_input.full_state
        and "meta_info" in scenario_input.full_state
        and "scene_id" in scenario_input.full_state["meta_info"]
    ):
        scene_id = scenario_input.full_state["meta_info"]["scene_id"]

    probe_dict = {
        "probe_id": run.probe_id,
        "scene_id": scene_id,
        "scenario_id": scenario_input.scenario_id,
        "display_state": display_state,
        "state": scenario_input.state,
        "choices": copy.deepcopy(scenario_input.choices),
        "full_state": scenario_input.full_state,
    }

    scene_items = []
    if probe_registry:
        probes = probe_registry.get_probes()
        scene_items = get_scenes_for_base_scenario(probes, scenario_input.scenario_id)

    decider_items = []
    llm_backbone_items = ["N/A"]
    alignment_attributes = []
    possible_alignment_attributes = []
    max_alignment_attributes = 0
    system_prompt = run.system_prompt
    if decider_registry:
        all_deciders = decider_registry.get_all_deciders()
        decider_items = list(all_deciders.keys())
        decider_options = decider_registry.get_decider_options(
            run.probe_id, run.decider_name
        )
        llm_backbone_items = get_llm_backbones_from_config(decider_options)
        max_alignment_attributes = get_max_alignment_attributes(decider_options)

        if not system_prompt or system_prompt == "Unknown":
            system_prompt = decider_registry.get_system_prompt(
                decider=run.decider_name,
                alignment_target=run.decider_params.alignment_target,
                probe_id=run.probe_id,
            )

    if probe_registry and decider_registry:
        all_attrs = probe_registry.get_attributes(run.probe_id)
        descriptions = _get_attribute_descriptions(
            run, probe_registry, decider_registry
        )

        alignment_attributes = kdma_values_to_alignment_attributes(
            run.decider_params.alignment_target.kdma_values, all_attrs, descriptions
        )
        possible_alignment_attributes = _compute_possible_alignment_attributes(
            run, all_attrs, descriptions
        )

    cache_key = hash_run_params(
        probe_id=run.probe_id,
        decider_name=run.decider_name,
        llm_backbone_name=run.llm_backbone_name,
        decider_params=run.decider_params,
    )

    result = {
        "id": run.id,
        "cache_key": cache_key,
        "config_dirty": False,
        "scene_items": scene_items,
        "decider_items": decider_items,
        "llm_backbone_items": llm_backbone_items,
        "alignment_attributes": alignment_attributes,
        "possible_alignment_attributes": possible_alignment_attributes,
        "max_alignment_attributes": max_alignment_attributes,
        "max_choices": 2,
        "prompt": {
            "probe": probe_dict,
            "alignment_target": run.decider_params.alignment_target.model_dump(),
            "decider_params": {
                "llm_backbone": run.llm_backbone_name,
                "decider": run.decider_name,
            },
            "system_prompt": system_prompt,
            "resolved_config": run.decider_params.resolved_config,
            "resolved_config_yaml": resolved_config_to_yaml(
                run.decider_params.resolved_config
            ),
            "decider": {"name": run.decider_name},
            "llm_backbone": run.llm_backbone_name,
        },
        "decision": decision_to_state_dict(run.decision) if run.decision else None,
    }

    return result


def export_runs_to_json(runs_dict: Dict[str, Dict[str, Any]]) -> str:
    exported_runs = []

    for run_dict in runs_dict.values():
        decision = run_dict.get("decision")
        if not decision:
            continue

        prompt = run_dict["prompt"]

        choice_idx = 0
        if "unstructured" in decision:
            decision_text = decision["unstructured"]
            if decision_text and len(decision_text) > 0:
                first_char = decision_text[0]
                if first_char.isalpha() and first_char.upper() >= "A":
                    choice_idx = ord(first_char.upper()) - ord("A")

        input_data = {
            "scenario_id": prompt["probe"]["scenario_id"],
            "full_state": prompt["probe"]["full_state"],
            "state": prompt["probe"]["full_state"]["unstructured"],
            "choices": prompt["probe"]["choices"],
        }

        output_data: Dict[str, Any] = {"choice": choice_idx}

        if choice_idx < len(prompt["probe"]["choices"]):
            selected_choice = prompt["probe"]["choices"][choice_idx]
            output_data["action"] = {
                "unstructured": selected_choice["unstructured"],
                "justification": decision.get("justification", ""),
            }

        exported_run = {"input": input_data, "output": output_data}
        exported_runs.append(exported_run)

    return json.dumps(exported_runs, indent=2)
