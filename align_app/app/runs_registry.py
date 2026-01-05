"""Service layer managing run state and coordinating domain operations."""

from typing import Optional, Dict, List, Any, Callable
from ..adm.run_models import Run
from . import runs_core
from . import runs_edit_logic
from ..utils.utils import get_id
from .import_experiments import StoredExperimentItem, run_from_stored_experiment_item


class RunsRegistry:
    def __init__(self, probe_registry, decider_registry):
        self._probe_registry = probe_registry
        self._decider_registry = decider_registry
        self._runs = runs_core.init_runs()
        self._experiment_items: Dict[str, StoredExperimentItem] = {}

    def _create_update_method(
        self,
        prepare_fn: Callable[..., Optional[Run]],
    ) -> Callable[[str, Any], Optional[Run]]:
        def update_method(run_id: str, value: Any) -> Optional[Run]:
            run = runs_core.get_run(self._runs, run_id)
            if not run:
                return None

            updated_run = prepare_fn(
                run,
                value,
                probe_registry=self._probe_registry,
                decider_registry=self._decider_registry,
            )
            if not updated_run:
                return None

            system_prompt = self._decider_registry.get_system_prompt(
                decider=updated_run.decider_name,
                alignment_target=updated_run.decider_params.alignment_target,
                probe_id=updated_run.probe_id,
            )

            new_run_id = get_id()
            new_run = updated_run.model_copy(
                update={
                    "id": new_run_id,
                    "decision": None,
                    "system_prompt": system_prompt,
                }
            )
            new_run = runs_core.apply_cached_decision(self._runs, new_run)

            if run.decision is None:
                self._runs = runs_core.remove_run(self._runs, run_id)
            self._runs = runs_core.add_run(self._runs, new_run)

            return new_run

        return update_method

    def add_run(self, run: Run) -> Run:
        self._runs = runs_core.add_run(self._runs, run)
        return run

    def add_runs_bulk(self, runs: List[Run]) -> None:
        self._runs = runs_core.add_runs_bulk(self._runs, runs)

    def populate_cache_bulk(self, runs: List[Run]) -> None:
        self._runs = runs_core.populate_cache_bulk(self._runs, runs)

    async def _execute_with_cache(self, run: Run, probe_choices: List[Dict]) -> Run:
        cache_key = run.compute_cache_key()

        cached = runs_core.get_cached_decision(self._runs, cache_key)
        if cached:
            updated_run = run.model_copy(update={"decision": cached})
            self._runs = runs_core.add_run(self._runs, updated_run)
            return updated_run

        decision = await runs_core.fetch_decision(run, probe_choices)
        updated_run = run.model_copy(update={"decision": decision})
        self._runs = runs_core.add_run(self._runs, updated_run)
        self._runs = runs_core.add_cached_decision(self._runs, cache_key, decision)
        return updated_run

    async def execute_decision(self, run: Run, probe_choices: List[Dict]) -> Run:
        return await self._execute_with_cache(run, probe_choices)

    async def execute_run_decision(self, run_id: str) -> Optional[Run]:
        run = runs_core.get_run(self._runs, run_id)
        if not run:
            return None

        probe = self._probe_registry.get_probe(run.probe_id)
        if not probe:
            return None

        return await self._execute_with_cache(run, probe.choices or [])

    def get_run(self, run_id: str) -> Optional[Run]:
        run = runs_core.get_run(self._runs, run_id)
        if run:
            run = runs_core.apply_cached_decision(self._runs, run)
        return run

    def get_all_runs(self) -> Dict[str, Run]:
        return dict(runs_core.get_all_runs_with_cached_decisions(self._runs))

    def clear_runs(self):
        self._runs = runs_core.clear_runs(self._runs)
        return self._runs

    def clear_all(self):
        self._runs = runs_core.init_runs()
        self._experiment_items = {}

    def update_run_scene(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(runs_edit_logic.prepare_scene_update)(
            run_id, value
        )

    def update_run_scenario(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(runs_edit_logic.prepare_scenario_update)(
            run_id, value
        )

    def update_run_decider(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(runs_edit_logic.prepare_decider_update)(
            run_id, value
        )

    def update_run_llm_backbone(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(runs_edit_logic.prepare_llm_update)(
            run_id, value
        )

    def add_run_alignment_attribute(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(
            runs_edit_logic.prepare_add_alignment_attribute
        )(run_id, value)

    def update_run_alignment_attribute_value(
        self, run_id: str, value: Any
    ) -> Optional[Run]:
        return self._create_update_method(
            runs_edit_logic.prepare_update_alignment_attribute_value
        )(run_id, value)

    def update_run_alignment_attribute_score(
        self, run_id: str, value: Any
    ) -> Optional[Run]:
        return self._create_update_method(
            runs_edit_logic.prepare_update_alignment_attribute_score
        )(run_id, value)

    def delete_run_alignment_attribute(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(
            runs_edit_logic.prepare_delete_alignment_attribute
        )(run_id, value)

    def update_run_probe_text(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(runs_edit_logic.prepare_update_probe_text)(
            run_id, value
        )

    def update_run_choice_text(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(runs_edit_logic.prepare_update_choice_text)(
            run_id, value
        )

    def add_run_choice(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(runs_edit_logic.prepare_add_run_choice)(
            run_id, value
        )

    def delete_run_choice(self, run_id: str, value: Any) -> Optional[Run]:
        return self._create_update_method(runs_edit_logic.prepare_delete_run_choice)(
            run_id, value
        )

    def add_experiment_items(self, items: Dict[str, StoredExperimentItem]):
        """Add experiment items (keyed by cache_key)."""
        self._experiment_items = {**self._experiment_items, **items}

    def get_experiment_item(self, cache_key: str) -> Optional[StoredExperimentItem]:
        return self._experiment_items.get(cache_key)

    def get_all_experiment_items(self) -> Dict[str, StoredExperimentItem]:
        return self._experiment_items

    def materialize_experiment_item(self, cache_key: str) -> Optional[Run]:
        """Convert experiment item to Run on demand. Populates decision cache."""
        stored = self._experiment_items.get(cache_key)
        if not stored:
            return None
        run = run_from_stored_experiment_item(stored)
        if run:
            self._runs = runs_core.add_run(self._runs, run)
        return run

    def get_run_by_cache_key(self, cache_key: str) -> Optional[Run]:
        """Find run by cache_key."""
        for run in self._runs.runs.values():
            if run.compute_cache_key() == cache_key:
                return runs_core.apply_cached_decision(self._runs, run)
        return None

    def update_decider_registry(self, new_registry):
        """Update the decider registry reference."""
        self._decider_registry = new_registry
