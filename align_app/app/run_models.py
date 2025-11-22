from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import hashlib
import json
from ..adm.decider.types import DeciderParams
from align_utils.models import ADMResult


def hash_run_params(
    probe_id: str,
    decider_name: str,
    llm_backbone_name: str,
    decider_params: DeciderParams,
) -> str:
    cache_key_data = {
        "probe_id": probe_id,
        "decider": decider_name,
        "llm_backbone": llm_backbone_name,
        "alignment_target": decider_params.alignment_target.model_dump(),
        "state": decider_params.scenario_input.state,
        "choices": decider_params.scenario_input.choices,
    }
    json_str = json.dumps(cache_key_data, sort_keys=True)
    return hashlib.md5(json_str.encode()).hexdigest()


class RunDecision(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    adm_result: ADMResult
    choice_index: int

    @classmethod
    def from_adm_result(
        cls, adm_result: ADMResult, probe_choices: List[Dict]
    ) -> "RunDecision":
        choice_idx = next(
            (
                i
                for i, choice in enumerate(probe_choices)
                if choice["unstructured"] == adm_result.decision.unstructured
            ),
            0,
        )

        return cls(
            adm_result=adm_result,
            choice_index=choice_idx,
        )

    def to_state_dict(self) -> Dict[str, Any]:
        from .ui import prep_decision_for_state

        choice_letter = chr(self.choice_index + ord("A"))

        decision_dict = {
            "unstructured": f"{choice_letter}. {self.adm_result.decision.unstructured}",
            "justification": self.adm_result.decision.justification,
            "choice_info": self.adm_result.choice_info.model_dump(exclude_none=True),
        }

        return prep_decision_for_state(decision_dict)


class Run(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    id: str
    decider_params: DeciderParams
    probe_id: str
    decider_name: str
    llm_backbone_name: str
    system_prompt: str
    decision: Optional[RunDecision] = None

    def compute_cache_key(self) -> str:
        return hash_run_params(
            probe_id=self.probe_id,
            decider_name=self.decider_name,
            llm_backbone_name=self.llm_backbone_name,
            decider_params=self.decider_params,
        )

    def to_state_dict(self) -> Dict[str, Any]:
        scenario_input = self.decider_params.scenario_input

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
            "probe_id": self.probe_id,
            "scene_id": scene_id,
            "scenario_id": scenario_input.scenario_id,
            "display_state": display_state,
            "state": scenario_input.state,
            "choices": scenario_input.choices,
            "full_state": scenario_input.full_state,
        }

        result = {
            "id": self.id,
            "prompt": {
                "probe": probe_dict,
                "alignment_target": self.decider_params.alignment_target.model_dump(),
                "decider_params": {
                    "llm_backbone": self.llm_backbone_name,
                    "decider": self.decider_name,
                },
                "system_prompt": self.system_prompt,
                "resolved_config": self.decider_params.resolved_config,
                "decider": {"name": self.decider_name},
                "llm_backbone": self.llm_backbone_name,
            },
        }

        if self.decision:
            result["decision"] = self.decision.to_state_dict()

        return result
