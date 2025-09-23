"""Pure business logic and validation functions for prompt handling."""

from typing import Dict, List, Any, cast
import copy
from ..adm.adm_core import get_prompt, Attribute


def create_default_choice(index: int, text: str) -> Dict[str, Any]:
    """Create a new choice with required fields for the alignment system."""
    return {
        "action_id": f"action-{index}",
        "unstructured": text,
        "action_type": "APPLY_TREATMENT",
        "intent_action": True,
        "parameters": {},
        "justification": None,
    }


def compute_possible_attributes(
    all_attrs: Dict, used_attrs: set, descriptions: Dict
) -> List[Dict]:
    """Compute available attributes not currently in use."""
    return [
        {
            "value": key,
            **details,
            "description": descriptions.get(key, {}).get(
                "description", f"No description available for {key}"
            ),
        }
        for key, details in all_attrs.items()
        if key not in used_attrs
    ]


def filter_valid_attributes(
    attributes: List[Dict], valid_attributes: Dict
) -> List[Dict]:
    """Filter attributes to only include valid ones for the dataset."""
    return [
        attr
        for attr in attributes
        if attr["value"] in valid_attributes
        and attr.get("possible_scores")
        == valid_attributes[attr["value"]].get("possible_scores")
    ]


def select_initial_decider(deciders: List[Dict], current: str = "") -> str:
    """Select the initial decider based on current selection and available options."""
    if not deciders:
        return ""

    valid_values = [dm["value"] for dm in deciders]
    if not current or current not in valid_values:
        return deciders[0]["value"]
    return current


def build_choices_from_edited(
    edited_choices: List[str], original_choices: List[Dict]
) -> List[Dict]:
    """Build new choices array with edited text."""
    new_choices = []
    for i, choice_text in enumerate(edited_choices):
        if i < len(original_choices):
            choice = copy.deepcopy(original_choices[i])
            choice["unstructured"] = choice_text
        else:
            choice = create_default_choice(i, choice_text)
        new_choices.append(choice)
    return new_choices


def get_max_alignment_attributes(decider_configs: Dict) -> int:
    """Extract max alignment attributes from decider configs."""
    if not decider_configs:
        return 0
    postures = decider_configs.get("postures", {})
    if "aligned" in postures:
        return postures["aligned"].get("max_alignment_attributes", 0)
    return 0


def get_llm_backbones_from_config(decider_configs: Dict) -> List[str]:
    """Extract LLM backbones from decider config."""
    if decider_configs and "llm_backbones" in decider_configs:
        return decider_configs["llm_backbones"]
    return ["N/A"]


def build_prompt_context(
    scenario_id: str,
    llm_backbone: str,
    decider: str,
    attributes: List[Dict],
    system_prompt: str,
    edited_text: str,
    edited_choices: List[str],
    decider_registry,
) -> Dict:
    mapped_attributes: List[Attribute] = [
        Attribute(type=a["value"], score=a["score"]) for a in attributes
    ]

    prompt_data = get_prompt(
        scenario_id,
        llm_backbone,
        decider,
        mapped_attributes,
    )

    scenario = prompt_data["scenario"]

    resolved_config = decider_registry.resolve_decider_config(
        scenario["scenario_id"],
        prompt_data["decider_params"]["decider"],
        prompt_data["alignment_target"],
    )

    original_choices = cast(List[Dict], scenario.get("choices", []))
    edited_choices_list = build_choices_from_edited(edited_choices, original_choices)

    updated_scenario = {
        **scenario,
        "display_state": edited_text,
        "full_state": {
            **cast(Dict, scenario.get("full_state", {})),
            "unstructured": edited_text,
        },
        "choices": edited_choices_list,
    }

    return {
        **prompt_data,
        "system_prompt": system_prompt,
        "resolved_config": resolved_config,
        "scenario": updated_scenario,
    }
