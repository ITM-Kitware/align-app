from dataclasses import dataclass, replace
from typing import Dict, Optional, List, Tuple
from .run_models import Run, RunDecision
from ..adm.decider import get_decision


@dataclass(frozen=True)
class Runs:
    runs: Dict[str, Run]
    decision_cache_index: Dict[str, str]

    @staticmethod
    def empty():
        return Runs(runs={}, decision_cache_index={})


def add_run(data: Runs, run: Run) -> Runs:
    return replace(data, runs={**data.runs, run.id: run})


def get_run(data: Runs, run_id: str) -> Optional[Run]:
    return data.runs.get(run_id)


def get_all_runs(data: Runs) -> Dict[str, Run]:
    return data.runs


def filter_runs_by_probe(data: Runs, probe_id: str) -> List[Run]:
    return [r for r in data.runs.values() if r.probe_id == probe_id]


def get_cached_decision(data: Runs, cache_key: str) -> Optional[RunDecision]:
    run_id = data.decision_cache_index.get(cache_key)
    if run_id is None:
        return None
    run = data.runs.get(run_id)
    return run.decision if run else None


def add_cached_decision(data: Runs, cache_key: str, run_id: str) -> Runs:
    return replace(
        data, decision_cache_index={**data.decision_cache_index, cache_key: run_id}
    )


async def compute_decision(
    data: Runs, run: Run, probe_choices: List[Dict]
) -> Tuple[Runs, Run]:
    cache_key = run.compute_cache_key()

    if cached := get_cached_decision(data, cache_key):
        return data, run.model_copy(update={"decision": cached})

    adm_result = await get_decision(run.decider_params)
    decision = RunDecision.from_adm_result(adm_result, probe_choices)

    updated_run = run.model_copy(update={"decision": decision})
    new_data = add_run(data, updated_run)
    new_data = add_cached_decision(new_data, cache_key, updated_run.id)

    return new_data, updated_run


def update_run(data: Runs, run_id: str, updated_run: Run) -> Runs:
    """Generic run updater with cache check.

    Updates run and checks cache with new parameters.
    If cache hit, populates decision from cached run.

    Pure domain operation - receives already-transformed run.
    """
    cache_key = updated_run.compute_cache_key()
    cached_decision = get_cached_decision(data, cache_key)

    if cached_decision:
        updated_run = updated_run.model_copy(update={"decision": cached_decision})

    return replace(data, runs={**data.runs, run_id: updated_run})


def init_runs() -> Runs:
    return Runs.empty()


def clear_runs(_: Runs) -> Runs:
    return Runs.empty()
