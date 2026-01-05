"""Decider configuration definitions and system prompt generation."""

from pathlib import Path
from typing import Dict, Any
import hydra
from omegaconf import OmegaConf
import align_system
from align_system.prompt_engineering.outlines_prompts import (
    ComparativeKDMASystemPrompt,
    ComparativeRegressionSystemPromptWithTemplate,
)
from align_system.utils import call_with_coerced_args
from align_system.utils.alignment_utils import attributes_in_alignment_target
from align_utils.models import AlignmentTarget
from .config import get_decider_config


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


LLM_BACKBONES = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mistral-7B-Instruct-v0.2",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
]


def _generate_comparative_regression_pipeline_system_prompt(config, alignment):
    system_prompt_template_config = config["step_definitions"][
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
    config_for_instantiation = OmegaConf.create({"adm": config})
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


def _generate_random_pipeline_system_prompt(_config, _alignment):
    return "N/A"


def _generate_baseline_pipeline_system_prompt(_config, _alignment):
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


def create_decider_entry(config_path, overrides={}):
    """Base factory for creating decider entries with overrides."""
    return {
        "config_path": config_path,
        "llm_backbones": LLM_BACKBONES,
        "dataset_overrides": {},
        **overrides,
    }


_BASE_DECIDERS = {
    "phase2_pipeline_zeroshot_comparative_regression": create_decider_entry(
        "adm/phase2_pipeline_zeroshot_comparative_regression.yaml",
        {
            "max_alignment_attributes": 10,
            "config_overrides": {
                "comparative_regression_choice_schema": {"reasoning_max_length": -1},
            },
            "system_prompt_generator": _generate_comparative_regression_pipeline_system_prompt,
        },
    ),
    "phase2_pipeline_fewshot_comparative_regression": create_decider_entry(
        "adm/phase2_pipeline_fewshot_comparative_regression.yaml",
        {
            "max_alignment_attributes": 10,
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
            "system_prompt_generator": _generate_baseline_pipeline_system_prompt,
        },
    ),
    "pipeline_random": create_decider_entry(
        "adm/pipeline_random.yaml",
        {
            "llm_backbones": [],
            "system_prompt_generator": _generate_random_pipeline_system_prompt,
        },
    ),
}


DECISION_FLOW_SYSTEM_PROMPT_OVERRIDES = {
    "step_definitions": {
        "variables": {
            "system_prompt_template": {
                "_target_": "align_system.prompt_engineering.outlines_prompts.DefaultITMBaselineSystemPrompt"
            }
        },
        "extraction": {
            "system_prompt_template": {
                "_target_": "align_system.prompt_engineering.outlines_prompts.DefaultITMBaselineSystemPrompt"
            }
        },
        "attribute": {
            "system_prompt_template": {
                "_target_": "align_system.prompt_engineering.outlines_prompts.DefaultITMBaselineSystemPrompt"
            }
        },
        "filter": {
            "system_prompt_template": {
                "_target_": "align_system.prompt_engineering.outlines_prompts.DefaultITMBaselineSystemPrompt"
            }
        },
        "objective": {
            "system_prompt_template": {
                "_target_": "align_system.prompt_engineering.outlines_prompts.DefaultITMBaselineSystemPrompt"
            }
        },
        "express_unstructured": {
            "system_prompt_template": {
                "_target_": "align_system.prompt_engineering.outlines_prompts.DefaultITMBaselineSystemPrompt"
            }
        },
        "math_reason": {
            "system_prompt_template": {
                "_target_": "align_system.prompt_engineering.outlines_prompts.DefaultITMBaselineSystemPrompt"
            }
        },
    }
}


def create_runtime_decider_entry(config_path):
    """Create a decider entry for a runtime config."""
    overrides = {
        "max_alignment_attributes": 10,
        "runtime_config": True,
    }

    if "decision_flow" in config_path:
        overrides["config_overrides"] = DECISION_FLOW_SYSTEM_PROMPT_OVERRIDES

    return create_decider_entry(config_path, overrides)


def get_runtime_deciders(config_paths):
    """Get runtime deciders from CLI config paths."""
    return {
        Path(config_path).stem: create_runtime_decider_entry(config_path)
        for config_path in config_paths
    }


def get_system_prompt(
    decider: str,
    alignment_target: AlignmentTarget,
    probe_id: str,
    all_deciders: Dict[str, Any],
    datasets: Dict[str, Any],
) -> str:
    """Generate system prompt for a decider with given alignment target."""
    decider_main_config = all_deciders.get(decider)
    if not decider_main_config:
        raise ValueError(f"Decider '{decider}' not found in all_deciders configuration")

    generate_sys_prompt = decider_main_config.get("system_prompt_generator")
    if not generate_sys_prompt:
        return "Unknown"

    probe = None
    for dataset_info in datasets.values():
        if probe_id in dataset_info["probes"]:
            probe = dataset_info["probes"][probe_id]
            break
    if probe is None:
        raise ValueError(f"Probe '{probe_id}' not found in datasets configuration")

    config = get_decider_config(probe.probe_id, all_deciders, datasets, decider)

    if config is None:
        return ""

    return generate_sys_prompt(config, alignment_target.model_dump())
