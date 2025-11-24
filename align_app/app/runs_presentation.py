"""Transform domain models to UI state dictionaries and export formats."""

from typing import Dict, Any
from .run_models import Run, RunDecision
from .ui import prep_decision_for_state
from .prompt import get_scenes_for_base_scenario
from .prompt_logic import get_llm_backbones_from_config
import json


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
        "choices": scenario_input.choices,
        "full_state": scenario_input.full_state,
    }

    scene_items = []
    if probe_registry:
        probes = probe_registry.get_probes()
        scene_items = get_scenes_for_base_scenario(probes, scenario_input.scenario_id)

    decider_items = []
    llm_backbone_items = ["N/A"]
    system_prompt = run.system_prompt
    if decider_registry:
        all_deciders = decider_registry.get_all_deciders()
        decider_items = list(all_deciders.keys())
        decider_options = decider_registry.get_decider_options(
            run.probe_id, run.decider_name
        )
        llm_backbone_items = get_llm_backbones_from_config(decider_options)

        if not system_prompt or system_prompt == "Unknown":
            system_prompt = decider_registry.get_system_prompt(
                decider=run.decider_name,
                attributes=run.decider_params.alignment_target.kdma_values,
                probe_id=run.probe_id,
            )

    result = {
        "id": run.id,
        "scene_items": scene_items,
        "decider_items": decider_items,
        "llm_backbone_items": llm_backbone_items,
        "prompt": {
            "probe": probe_dict,
            "alignment_target": run.decider_params.alignment_target.model_dump(),
            "decider_params": {
                "llm_backbone": run.llm_backbone_name,
                "decider": run.decider_name,
            },
            "system_prompt": system_prompt,
            "resolved_config": run.decider_params.resolved_config,
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

        output_data = {"choice": choice_idx}

        if choice_idx < len(prompt["probe"]["choices"]):
            selected_choice = prompt["probe"]["choices"][choice_idx]
            output_data["action"] = {
                "unstructured": selected_choice["unstructured"],
                "justification": decision.get("justification", ""),
            }

        exported_run = {"input": input_data, "output": output_data}
        exported_runs.append(exported_run)

    return json.dumps(exported_runs, indent=2)
