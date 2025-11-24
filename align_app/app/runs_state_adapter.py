from typing import Dict
from trame.app import asynchronous
from trame.decorators import TrameApp, controller, change
from .run_models import Run
from .runs_registry import RunsRegistry
from ..adm.decider.types import DeciderParams
from ..utils.utils import get_id
from .prompt import extract_base_scenarios
from . import runs_presentation


@TrameApp()
class RunsStateAdapter:
    def __init__(self, server, prompt_controller, runs_registry: RunsRegistry):
        self.server = server
        self.prompt_controller = prompt_controller
        self.runs_registry = runs_registry
        self.probe_registry = prompt_controller.probe_registry
        self.decider_registry = prompt_controller.decider_api
        self.server.state.runs_computing = []
        self._sync_from_runs_data(runs_registry.get_all_runs())

    @property
    def state(self):
        return self.server.state

    def _sync_from_runs_data(self, runs_dict: Dict[str, Run]):
        self.state.runs = {
            run_id: runs_presentation.run_to_state_dict(
                run, self.probe_registry, self.decider_registry
            )
            for run_id, run in runs_dict.items()
        }

        probes = self.probe_registry.get_probes()
        self.state.base_scenarios = extract_base_scenarios(probes)

        if not self.state.runs:
            self.state.runs_to_compare = []
            self.state.runs_json = "[]"
            self.state.run_edit_configs = {}

    @controller.set("reset_runs_state")
    def reset_state(self):
        self.runs_registry.clear_runs()
        self._sync_from_runs_data({})

    @controller.set("update_run_to_compare")
    def update_run_to_compare(self, run_index, run_column_index):
        runs = list(self.state.runs.keys())
        self.state.runs_to_compare[run_column_index] = runs[run_index - 1]
        self.state.dirty("runs_to_compare")

    def _sync_run_to_state(self, run: Run):
        run_dict = runs_presentation.run_to_state_dict(
            run, self.probe_registry, self.decider_registry
        )

        with self.state:
            self.state.runs = {
                run_id: (run_dict if run_id == run.id else item)
                for run_id, item in self.state.runs.items()
            }
            if run.id not in self.state.runs:
                self.state.runs = {**self.state.runs, run.id: run_dict}
                self.state.runs_to_compare = self.state.runs_to_compare + [run.id]

    async def create_and_execute_run(self):
        prompt_context = self.prompt_controller.get_prompt()
        run_id = get_id()

        decider_params = DeciderParams(
            scenario_input=prompt_context["probe"].item.input,
            alignment_target=prompt_context["alignment_target"],
            resolved_config=prompt_context["resolved_config"],
        )

        run = Run(
            id=run_id,
            decider_params=decider_params,
            probe_id=prompt_context["probe"].probe_id,
            decider_name=prompt_context.get("decider_params", {}).get("decider", ""),
            llm_backbone_name=prompt_context.get("decider_params", {}).get(
                "llm_backbone", ""
            ),
            system_prompt=prompt_context.get("system_prompt", ""),
        )

        self.runs_registry.add_run(run)
        self._sync_run_to_state(run)

        await self.server.network_completion  # show spinner

        probe_choices = prompt_context["probe"].choices or []
        updated_run = await self.runs_registry.execute_decision(run, probe_choices)

        self._sync_run_to_state(updated_run)

    @controller.set("submit_prompt")
    def submit_prompt(self):
        asynchronous.create_task(self.create_and_execute_run())

    @controller.set("update_run_scene")
    def update_run_scene(self, run_id: str, scene_id: str):
        """Handle scene change for a run.

        Minimal - just coordinates registry call and UI sync.
        All complexity delegated to registry → core layers.
        """
        updated_run = self.runs_registry.update_run_scene(run_id, scene_id)

        if updated_run:
            self._sync_run_to_state(updated_run)

    @controller.set("update_run_scenario")
    def update_run_scenario(self, run_id: str, scenario_id: str):
        """Handle scenario change for a run.

        Minimal - just coordinates registry call and UI sync.
        All complexity delegated to registry → core layers.
        """
        updated_run = self.runs_registry.update_run_scenario(run_id, scenario_id)

        if updated_run:
            self._sync_run_to_state(updated_run)

    @controller.set("update_run_decider")
    def update_run_decider(self, run_id: str, decider_name: str):
        """Handle decider change for a run.

        Minimal - just coordinates registry call and UI sync.
        All complexity delegated to registry → core layers.
        """
        updated_run = self.runs_registry.update_run_decider(run_id, decider_name)

        if updated_run:
            self._sync_run_to_state(updated_run)

    async def _execute_run_decision(self, run_id: str):
        self.state.runs_computing = list(set(self.state.runs_computing + [run_id]))

        updated_run = await self.runs_registry.execute_run_decision(run_id)

        if updated_run:
            self._sync_run_to_state(updated_run)

        self.state.runs_computing = [
            rid for rid in self.state.runs_computing if rid != run_id
        ]

    @controller.set("execute_run_decision")
    def execute_run_decision(self, run_id: str):
        asynchronous.create_task(self._execute_run_decision(run_id))

    def export_runs_to_json(self) -> str:
        return runs_presentation.export_runs_to_json(self.state.runs)

    @change("runs")
    def update_runs_json(self, **_):
        json_data = self.export_runs_to_json()
        self.state.runs_json = json_data
        self.state.flush()
