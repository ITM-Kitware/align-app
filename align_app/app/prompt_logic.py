"""Pure business logic and validation functions for prompt handling."""

from typing import Dict, List, Any, cast
import copy
from omegaconf import OmegaConf
from ..adm.types import Attribute, DeciderParams, Prompt
from ..adm.state_builder import attributes_to_alignment_target
from ..adm.probe import Probe
from ..adm.config import get_decider_config


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
    return decider_configs.get("max_alignment_attributes", 0)


def get_llm_backbones_from_config(decider_configs: Dict) -> List[str]:
    """Extract LLM backbones from decider config."""
    if decider_configs and "llm_backbones" in decider_configs:
        return decider_configs["llm_backbones"]
    return ["N/A"]


def find_probe_by_base_and_scene(
    probes: Dict[str, Probe], base_id: str, scene_id: str
) -> str:
    """Find the full probe_id given base and scene IDs."""
    matches = [
        probe_id
        for probe_id, probe in probes.items()
        if probe.scenario_id == base_id and probe.scene_id == scene_id
    ]
    return matches[0] if matches else ""


def create_prompt_base(
    probe: Probe, llm_backbone: str, decider: str, attributes: List[Attribute]
) -> dict:
    """Build base prompt structure from components.

    Returns a dict with probe as Probe model (internal representation).
    """
    return {
        "decider_params": DeciderParams(llm_backbone=llm_backbone, decider=decider),
        "alignment_target": attributes_to_alignment_target(attributes),
        "probe": probe,
    }


def build_prompt_context(
    probe_id: str,
    llm_backbone: str,
    decider: str,
    attributes: List[Dict],
    system_prompt: str,
    edited_text: str,
    edited_choices: List[str],
    decider_registry,
    probe_registry,
) -> Dict:
    mapped_attributes: List[Attribute] = [
        Attribute(type=a["value"], score=a["score"]) for a in attributes
    ]

    probe = probe_registry.get_probe(probe_id)

    prompt_data = create_prompt_base(probe, llm_backbone, decider, mapped_attributes)

    resolved_config = decider_registry.get_decider_config(
        probe.probe_id,
        decider=decider,
        llm_backbone=llm_backbone,
    )

    original_choices = cast(List[Dict], probe.choices or [])
    edited_choices_list = build_choices_from_edited(edited_choices, original_choices)

    updated_full_state = copy.deepcopy(probe.full_state) or {}
    updated_full_state["unstructured"] = edited_text

    updated_probe = probe.model_copy(
        update={
            "display_state": edited_text,
        }
    )

    updated_probe.item.input.full_state = updated_full_state
    updated_probe.item.input.choices = edited_choices_list

    return {
        **prompt_data,
        "system_prompt": system_prompt,
        "resolved_config": resolved_config,
        "probe": updated_probe,
        "all_deciders": decider_registry.get_all_deciders(),
        "datasets": probe_registry.get_datasets(),
    }


def get_alignment_descriptions_map(prompt: Prompt) -> dict:
    """Get attribute descriptions for alignment targets from ADM config."""
    probe: Probe = prompt["probe"]
    probe_id = probe.probe_id
    decider = prompt["decider_params"]["decider"]
    all_deciders = prompt["all_deciders"]
    datasets = prompt["datasets"]

    config = get_decider_config(probe_id, all_deciders, datasets, decider)
    if not config:
        return {}

    config.pop("instance", None)
    config.pop("step_definitions", None)

    attributes_resolved = OmegaConf.to_container(
        OmegaConf.create({"adm": config}),
        resolve=True,
    )

    if not isinstance(attributes_resolved, dict):
        return {}

    adm_section = attributes_resolved.get("adm", {})
    if not isinstance(adm_section, dict):
        return {}

    attribute_map = adm_section.get("attribute_definitions", {})

    return attribute_map
