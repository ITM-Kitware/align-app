from pathlib import Path
import copy
from typing import TypedDict, List, Dict, Any, cast

import hydra
from omegaconf import OmegaConf
import align_system
import align_system.utils.hydrate_state
from align_system.utils.hydrate_state import (
    p2triage_hydrate_scenario_state,
)
from align_system.utils import logging, call_with_coerced_args
from align_system.utils.alignment_utils import attributes_in_alignment_target
from align_utils.models import AlignmentTarget, KDMAValue

# Import prompt classes at module level to avoid 6.7s delay on first use
from align_system.prompt_engineering.outlines_prompts import (
    ComparativeKDMASystemPrompt,
    ComparativeRegressionSystemPromptWithTemplate,
)

# from .action_filtering import filter_actions
from .probe import Probe
from .config import resolve_decider_config, get_base_decider_config


def get_icl_data_paths():
    """Get paths to ICL data files from align-system repository"""
    icl_base_path = Path(align_system.__file__).parent / "resources" / "icl" / "phase2"

    data_mapping = {
        "medical": "July2025-MU-train_20250804.json",
        "affiliation": "July2025-AF-train_20250804.json",
        "merit": "July2025-MF-train_20250804.json",
        "personal_safety": "July2025-PS-train_20250804.json",
        "search": "July2025-SS-train_20250804.json",
    }

    return {
        key: str(icl_base_path / filename) for key, filename in data_mapping.items()
    }


def add_default_state_fields(full_state: Dict[str, Any]) -> Dict[str, Any]:
    """Add default environment and supplies fields to full_state if missing.
    Returns a new dict with defaults applied.
    """
    return {
        **full_state,
        "environment": full_state.get("environment") or {},
        "supplies": full_state.get("supplies") or {},
    }


def p2triage_hydrate_scenario_state_with_defaults(record):
    """Add default fields if missing (needed for phase2 ICL data) then call original function"""
    record_copy = record.copy()
    record_copy["full_state"] = add_default_state_fields(record_copy["full_state"])
    return p2triage_hydrate_scenario_state(record_copy)


# Monkey-patch the hydration function
align_system.utils.hydrate_state.p2triage_hydrate_scenario_state = (
    p2triage_hydrate_scenario_state_with_defaults
)


root_logger = logging.getLogger()
root_logger.setLevel("WARNING")


class DeciderParams(TypedDict):
    llm_backbone: str
    decider: str


class Choice(TypedDict):
    unstructured: str


class Attribute(TypedDict):
    type: str
    score: float


class ProbeAndAlignment(TypedDict):
    probe: Probe
    alignment_target: AlignmentTarget


class Prompt(ProbeAndAlignment):
    decider_params: DeciderParams


class SerializedKDMAValue(TypedDict):
    kdma: str
    value: float
    kdes: Any | None


class SerializedAlignmentTarget(TypedDict):
    id: str
    kdma_values: List[SerializedKDMAValue]


class SerializedProbeAndAlignment(TypedDict):
    probe: dict
    alignment_target: SerializedAlignmentTarget


class SerializedPrompt(SerializedProbeAndAlignment):
    decider_params: DeciderParams
    system_prompt: str


class DeciderContext(Prompt):
    resolved_config: dict


align_system_path = Path(align_system.__file__).parent
base_align_system_config_dir = align_system_path / "configs"


def _generate_comparative_regression_pipeline_system_prompt(ctx, alignment):
    adm_config = ctx["config"]

    system_prompt_template_config = adm_config["step_definitions"][
        "comparative_regression"
    ]["system_prompt_template"]

    target_class = system_prompt_template_config.get("_target_")
    if (
        target_class
        == "align_system.prompt_engineering.outlines_prompts.ComparativeKDMASystemPrompt"
    ):
        system_prompt_template = ComparativeKDMASystemPrompt()
    elif (
        target_class
        == "align_system.prompt_engineering.outlines_prompts.ComparativeRegressionSystemPromptWithTemplate"
    ):
        system_prompt_template = ComparativeRegressionSystemPromptWithTemplate()
    else:
        # Fall back to Hydra for unknown classes.  Was slow.
        system_prompt_template = hydra.utils.instantiate(system_prompt_template_config)

    # To resolve references like `${adm.mu}`, we need to provide the 'adm' context to hydra.
    # We can wrap the config and then instantiate the 'attribute_definitions' part.
    config_for_instantiation = OmegaConf.create({"adm": adm_config})
    all_attributes = hydra.utils.instantiate(
        config_for_instantiation.adm.attribute_definitions
    )

    target_attribute_names = attributes_in_alignment_target(alignment)
    target_attributes = [all_attributes[n] for n in target_attribute_names]
    attribute_prompts = [
        call_with_coerced_args(system_prompt_template, {"target_attribute": attribute})
        for attribute in target_attributes
    ]
    return "\n\n".join(attribute_prompts)


def _generate_baseline_pipeline_system_prompt(ctx, alignment):
    """Generate system prompt for pipeline_baseline ADM.

    The baseline ADM always uses the same prompt regardless of alignment,
    as it represents an unaligned baseline approach.
    """
    return (
        "You are an assistant specialized in answering multiple-choice "
        "questions related to medical triage. When a question is posed, "
        "carefully analyze the symptoms or conditions "
        "described. Respond by providing a detailed reasoning using a "
        "step-by-step process or process of elimination. Conclude with "
        "the final answer, represented by the corresponding index "
        "number. Your response should be grounded in established "
        "medical knowledge and aim to be informative."
    )


LLM_BACKBONES = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mistral-7B-Instruct-v0.2",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
]


def create_decider_entry(config_path, overrides={}):
    """Base factory for creating decider entries with overrides."""
    return {
        "config_path": config_path,
        "llm_backbones": LLM_BACKBONES,
        "model_path_keys": ["structured_inference_engine", "model_name"],
        "postures": {"baseline": {}},
        **overrides,
    }


_BASE_DECIDERS = {
    "phase2_pipeline_zeroshot_comparative_regression": create_decider_entry(
        "adm/phase2_pipeline_zeroshot_comparative_regression.yaml",
        {
            "config_overrides": {
                "comparative_regression_choice_schema": {"reasoning_max_length": -1}
            },
            "postures": {"aligned": {}},
            "system_prompt_generator": _generate_comparative_regression_pipeline_system_prompt,
        },
    ),
    "phase2_pipeline_fewshot_comparative_regression": create_decider_entry(
        "adm/phase2_pipeline_fewshot_comparative_regression.yaml",
        {
            "config_overrides": {
                "comparative_regression_choice_schema": {"reasoning_max_length": -1},
                "step_definitions": {
                    "regression_icl": {
                        "icl_generator_partial": {
                            "incontext_settings": {"datasets": get_icl_data_paths()}
                        }
                    }
                },
            },
            "postures": {"aligned": {}},
            "system_prompt_generator": _generate_comparative_regression_pipeline_system_prompt,
        },
    ),
    "pipeline_baseline": create_decider_entry(
        "adm/pipeline_baseline.yaml",
        {
            "config_overrides": {
                "step_definitions": {
                    "outlines_baseline": {
                        "scenario_description_template": {
                            "_target_": "align_system.prompt_engineering.outlines_prompts.Phase2ScenarioDescription"
                        },
                        "prompt_template": {
                            "_target_": "align_system.prompt_engineering.outlines_prompts.Phase2BaselinePrompt"
                        },
                        "enable_caching": True,
                    }
                }
            },
            "postures": {"baseline": {}},
            "system_prompt_generator": _generate_baseline_pipeline_system_prompt,
        },
    ),
    "pipeline_random": create_decider_entry(
        "adm/pipeline_random.yaml",
        {"postures": {"baseline": {}}},
    ),
}


def create_runtime_decider_entry(config_path):
    """Create a decider entry for a runtime config."""
    return create_decider_entry(
        config_path,
        {
            "postures": {
                "aligned": {
                    "max_alignment_attributes": 10,
                },
                "baseline": {},
            },
            "runtime_config": True,
        },
    )


def get_all_deciders(config_paths=[]):
    """Get all deciders, merging runtime configs from paths with base deciders."""
    runtime_deciders = {
        Path(config_path).stem: create_runtime_decider_entry(config_path)
        for config_path in config_paths
    }
    return {**runtime_deciders, **_BASE_DECIDERS}


decider_names = list(_BASE_DECIDERS.keys())


def probe_to_dict(probe: Probe) -> Dict[str, Any]:
    """
    Convert Probe to dictionary representation for serialization.

    Returns a dict with all probe fields suitable for JSON serialization
    or passing to hydration functions.
    """
    return {
        "probe_id": probe.probe_id,
        "scene_id": probe.scene_id,
        "scenario_id": probe.scenario_id,
        "display_state": probe.display_state,
        "full_state": probe.full_state,
        "state": probe.state,
        "choices": probe.choices,
    }


def create_probe_state(probe: Probe):
    """Create a probe state from a probe"""
    probe_dict = probe_to_dict(probe)
    probe_dict["full_state"] = add_default_state_fields(probe.full_state or {})

    state, actions = p2triage_hydrate_scenario_state(probe_dict)
    return state, actions


def attributes_to_alignment_target(
    attributes: List[Attribute],
) -> AlignmentTarget:
    """Create AlignmentTarget Pydantic model from attributes."""
    return AlignmentTarget(
        id="ad_hoc",
        kdma_values=[
            KDMAValue(
                kdma=a["type"],
                value=a["score"],
                kdes=None,
            )
            for a in attributes
        ],
    )


def build_prompt_data(
    probe: Probe, llm_backbone: str, decider: str, attributes: List[Attribute]
) -> dict:
    """Build a prompt data structure from components.

    Returns a dict with probe as Probe model (internal representation).
    """
    return {
        "decider_params": DeciderParams(llm_backbone=llm_backbone, decider=decider),
        "alignment_target": attributes_to_alignment_target(attributes),
        "probe": probe,
    }


def serialize_prompt(prompt: Prompt) -> SerializedPrompt:
    """Serialize a prompt for JSON/state storage, removing non-serializable fields.

    This is THE serialization boundary - converts Probe to dict for UI state.
    Input: prompt["probe"] is Probe model
    Output: prompt["probe"] is dict
    """
    probe: Probe = prompt["probe"]
    alignment_target = cast(
        SerializedAlignmentTarget, prompt["alignment_target"].model_dump()
    )

    system_prompt: str = prompt.get("system_prompt", "")  # type: ignore[assignment]
    result: SerializedPrompt = {
        "probe": probe_to_dict(probe),
        "alignment_target": alignment_target,
        "decider_params": prompt["decider_params"],
        "system_prompt": system_prompt,
    }

    return copy.deepcopy(result)


def get_probe_from_datasets(probe_id: str, datasets: Dict[str, Any]) -> Probe:
    for dataset_info in datasets.values():
        if probe_id in dataset_info["probes"]:
            return dataset_info["probes"][probe_id]
    raise ValueError(f"Probe '{probe_id}' not found in datasets configuration")


def prepare_context(
    probe: Probe,
    decider: str,
    alignment_target: AlignmentTarget,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
) -> Dict[str, Any]:
    state, actions = create_probe_state(probe)
    config = resolve_decider_config(
        probe.probe_id, decider, alignment_target, all_deciders, datasets
    )
    return {
        "state": state,
        "actions": actions,
        "scenario_id": probe.probe_id,
        "config": config,
    }


def get_system_prompt(
    decider: str,
    attributes: List[Attribute],
    probe_id: str,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
) -> str:
    decider_main_config = all_deciders.get(decider)
    if not decider_main_config:
        raise ValueError(f"Decider '{decider}' not found in all_deciders configuration")

    generate_sys_prompt = decider_main_config.get("system_prompt_generator")
    if not generate_sys_prompt:
        return "Unknown"

    probe = get_probe_from_datasets(probe_id, datasets)
    alignment_target = attributes_to_alignment_target(attributes)
    ctx = prepare_context(probe, decider, alignment_target, all_deciders, datasets)

    if ctx.get("config") is None:
        # This implies that for the given decider and baseline/aligned posture,
        # a valid configuration was not found (e.g., kaleido needs an alignment and has no baseline posture).
        return ""

    alignment = attributes_to_alignment_target(attributes)
    return generate_sys_prompt(ctx, alignment.model_dump())


def get_alignment_descriptions_map(prompt: Prompt) -> dict:
    probe: Probe = prompt["probe"]
    probe_id = probe.probe_id
    decider = prompt["decider_params"]["decider"]
    all_deciders = prompt.get("all_deciders")
    datasets = prompt.get("datasets")

    config = get_base_decider_config(
        probe_id,
        decider,
        baseline=False,
        all_deciders=all_deciders,
        datasets=datasets,
    )
    if not config:
        return {}

    # remove custom refs which cause errors when Omega is trying to resolve them
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
