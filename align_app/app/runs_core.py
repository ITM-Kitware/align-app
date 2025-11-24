from dataclasses import dataclass, replace
from typing import Dict, Optional, List, Tuple
from .run_models import Run, RunDecision
from ..adm.decider import get_decision


@dataclass(frozen=True)
class Runs:
    runs: Dict[str, Run]
    decision_cache: Dict[str, RunDecision]

    @staticmethod
    def empty():
        return Runs(runs={}, decision_cache={})


def add_run(data: Runs, run: Run) -> Runs:
    new_data = replace(data, runs={**data.runs, run.id: run})
    if run.decision:
        cache_key = run.compute_cache_key()
        new_data = add_cached_decision(new_data, cache_key, run.decision)
    return new_data


def remove_run(data: Runs, run_id: str) -> Runs:
    runs = {rid: run for rid, run in data.runs.items() if rid != run_id}
    return replace(data, runs=runs)


def get_run(data: Runs, run_id: str) -> Optional[Run]:
    return data.runs.get(run_id)


def get_all_runs(data: Runs) -> Dict[str, Run]:
    return data.runs


def filter_runs_by_probe(data: Runs, probe_id: str) -> List[Run]:
    return [r for r in data.runs.values() if r.probe_id == probe_id]


def get_cached_decision(data: Runs, cache_key: str) -> Optional[RunDecision]:
    return data.decision_cache.get(cache_key)


def apply_cached_decision(data: Runs, run: Run) -> Run:
    cache_key = run.compute_cache_key()
    cached_decision = get_cached_decision(data, cache_key)
    return run.model_copy(update={"decision": cached_decision})


def add_cached_decision(data: Runs, cache_key: str, decision: RunDecision) -> Runs:
    return replace(data, decision_cache={**data.decision_cache, cache_key: decision})


async def compute_decision(
    data: Runs, run: Run, probe_choices: List[Dict]
) -> Tuple[Runs, Run]:
    cache_key = run.compute_cache_key()

    if cached := get_cached_decision(data, cache_key):
        updated_run = run.model_copy(update={"decision": cached})
        new_data = add_run(data, updated_run)
        return new_data, updated_run

    adm_result = await get_decision(run.decider_params)
    decision = RunDecision.from_adm_result(adm_result, probe_choices)

    updated_run = run.model_copy(update={"decision": decision})
    new_data = add_run(data, updated_run)
    new_data = add_cached_decision(new_data, cache_key, decision)

    return new_data, updated_run


def update_run(data: Runs, run_id: str, updated_run: Run) -> Runs:
    """Generic run updater with cache check.

    Updates run and sets decision from cache (None if no cache hit).

    Pure domain operation - receives already-transformed run.
    """
    updated_run = apply_cached_decision(data, updated_run)
    return replace(data, runs={**data.runs, run_id: updated_run})


def init_runs() -> Runs:
    return Runs.empty()


def clear_runs(_: Runs) -> Runs:
    return Runs.empty()
