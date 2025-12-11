from typing import Dict, Optional, List
from pydantic import BaseModel
import hashlib
import json
from .decider.types import DeciderParams
from align_utils.models import ADMResult


def hash_run_params(
    probe_id: str,
    decider_name: str,
    llm_backbone_name: str,
    decider_params: DeciderParams,
) -> str:
    alignment_target = decider_params.alignment_target
    kdma_values = [kv.model_dump() for kv in alignment_target.kdma_values]

    # Exclude alignment_target from resolved_config since it's already in kdma_values
    resolved_config = decider_params.resolved_config or {}
    config_for_hash = {k: v for k, v in resolved_config.items() if k != "alignment_target"}

    cache_key_data = {
        "probe_id": probe_id,
        "decider": decider_name,
        "llm_backbone": llm_backbone_name,
        "kdma_values": kdma_values,
        "state": decider_params.scenario_input.state,
        "choices": decider_params.scenario_input.choices,
        "resolved_config": config_for_hash,
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
