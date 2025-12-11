"""Export runs as Pydantic Experiment structures in ZIP format."""

import io
import json
import zipfile
from typing import Any, Dict, List, Tuple

import yaml
from align_utils.models import (
    Action,
    ChoiceInfo,
    InputData,
    InputOutputItem,
    Output,
)


def _extract_choice_index(decision: Dict) -> int:
    """Extract choice index from decision unstructured text (A. -> 0, B. -> 1)."""
    if "unstructured" in decision:
        text = decision["unstructured"]
        if text and len(text) > 0:
            first_char = text[0].upper()
            if first_char.isalpha() and first_char >= "A":
                return ord(first_char) - ord("A")
    return 0


def run_dict_to_input_output_item(
    run_dict: Dict[str, Any], alignment_target_id: str
) -> InputOutputItem:
    """Convert a run state dict to InputOutputItem Pydantic model."""
    prompt = run_dict["prompt"]
    decision = run_dict.get("decision")

    input_data = InputData(
        scenario_id=prompt["probe"]["scenario_id"],
        alignment_target_id=alignment_target_id,
        full_state=prompt["probe"]["full_state"],
        state=prompt["probe"].get("state")
        or prompt["probe"]["full_state"].get("unstructured"),
        choices=prompt["probe"]["choices"],
    )

    output = None
    choice_info = None
    if decision:
        choice_idx = _extract_choice_index(decision)
        choices = prompt["probe"]["choices"]

        action_dict = choices[choice_idx] if choice_idx < len(choices) else choices[0]
        action = Action(
            action_id=action_dict.get("action_id", f"choice_{choice_idx}"),
            action_type=action_dict.get("action_type", "CHOICE"),
            unstructured=action_dict.get("unstructured", ""),
            justification=decision.get("justification", ""),
            character_id=action_dict.get("character_id"),
            intent_action=action_dict.get("intent_action"),
            kdma_association=action_dict.get("kdma_association"),
        )
        output = Output(choice=choice_idx, action=action)

        if "choice_info" in decision and decision["choice_info"]:
            choice_info = ChoiceInfo(**decision["choice_info"])

    return InputOutputItem(
        input=input_data,
        output=output,
        choice_info=choice_info,
        label=None,
    )


def _alignment_target_id_from_kdma_values(alignment_target: Dict[str, Any]) -> str:
    """Generate alignment target ID from KDMA values (e.g., 'affiliation-0.5_merit-0.3')."""
    kdma_values = alignment_target.get("kdma_values", [])
    if not kdma_values:
        return "unknown"
    parts = [f"{kv.get('kdma')}-{kv.get('value', 0.0)}" for kv in kdma_values]
    return "_".join(sorted(parts))


def _get_alignment_target_id(run_dict: Dict[str, Any]) -> str:
    """Get alignment target ID, generating one from KDMA values if 'ad_hoc' or missing."""
    alignment_target = run_dict["prompt"].get("alignment_target") or {}
    target_id = alignment_target.get("id", "")
    if not target_id or target_id == "ad_hoc":
        return _alignment_target_id_from_kdma_values(alignment_target)
    return target_id


def _group_runs_by_experiment(
    runs_dict: Dict[str, Dict[str, Any]],
) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """Group runs by (decider_name, alignment_target_id)."""
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    for run_dict in runs_dict.values():
        if not run_dict.get("decision"):
            continue

        decider_name = run_dict["prompt"]["decider"]["name"]
        alignment_target_id = _get_alignment_target_id(run_dict)
        key = (decider_name, alignment_target_id)

        if key not in groups:
            groups[key] = []
        groups[key].append(run_dict)

    return groups


def _build_experiment_config(
    run_dict: Dict[str, Any],
    decider_name: str,
    alignment_target_id: str,
) -> Dict[str, Any]:
    """Build experiment config matching align_utils ExperimentConfig format."""
    resolved_config = run_dict["prompt"].get("resolved_config") or {}
    alignment_target = run_dict["prompt"]["alignment_target"]

    kdma_values = [
        {"kdma": kv.get("kdma"), "value": kv.get("value", 0.0), "kdes": kv.get("kdes")}
        for kv in alignment_target.get("kdma_values", [])
    ]

    return {
        "adm": resolved_config,
        "alignment_target": {"id": alignment_target_id, "kdma_values": kdma_values},
    }


def export_runs_to_zip(runs_dict: Dict[str, Dict[str, Any]]) -> bytes:
    """Export runs to ZIP file as bytes for browser download."""
    groups = _group_runs_by_experiment(runs_dict)

    if not groups:
        return b""

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for (decider_name, alignment_target_id), run_dicts in groups.items():
            items = [
                run_dict_to_input_output_item(rd, alignment_target_id)
                for rd in run_dicts
            ]

            items_json = json.dumps(
                [item.model_dump(exclude_none=True) for item in items],
                indent=2,
            )

            config = _build_experiment_config(
                run_dicts[0], decider_name, alignment_target_id
            )
            config_yaml = yaml.dump(config, default_flow_style=False, sort_keys=False)

            base_path = f"{decider_name}/{alignment_target_id}"

            zf.writestr(f"{base_path}/input_output.json", items_json)
            zf.writestr(f"{base_path}/.hydra/config.yaml", config_yaml)

    zip_buffer.seek(0)
    return zip_buffer.read()
