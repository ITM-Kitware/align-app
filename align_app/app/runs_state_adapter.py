from typing import Dict, Optional
from trame.app import asynchronous
from trame.decorators import TrameApp, controller, change
from .run_models import Run
from .runs_registry import RunsRegistry
from ..adm.decider.types import DeciderParams
from ..utils.utils import get_id
from .prompt import extract_base_scenarios
from . import runs_presentation
from align_utils.models import AlignmentTarget


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
        self.create_default_run()

    def create_default_run(self):
        probes = self.probe_registry.get_probes()
        if not probes:
            return

        first_probe_id = next(iter(probes))
        first_probe = probes[first_probe_id]

        all_deciders = self.decider_registry.get_all_deciders()
        if not all_deciders:
            return

        decider_name = next(iter(all_deciders))
        decider_options = self.decider_registry.get_decider_options(
            first_probe_id, decider_name
        )
        llm_backbones = decider_options.get("llm_backbones", []) if decider_options else []
        llm_backbone = llm_backbones[0] if llm_backbones else ""

        resolved_config = self.decider_registry.get_decider_config(
            probe_id=first_probe_id,
            decider=decider_name,
            llm_backbone=llm_backbone,
        )

        if resolved_config is None:
            return

        alignment_target = AlignmentTarget(id="ad_hoc", kdma_values=[])

        decider_params = DeciderParams(
            scenario_input=first_probe.item.input,
            alignment_target=alignment_target,
            resolved_config=resolved_config,
        )

        run = Run(
            id=get_id(),
            decider_params=decider_params,
            probe_id=first_probe_id,
            decider_name=decider_name,
            llm_backbone_name=llm_backbone,
            system_prompt="",
        )

        self.runs_registry.add_run(run)
        self._sync_run_to_state(run)

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

    def _handle_run_update(self, old_run_id: str, new_run: Optional[Run]):
        if new_run:
            self.state.runs_to_compare = [
                new_run.id if rid == old_run_id else rid
                for rid in self.state.runs_to_compare
            ]
            self._sync_from_runs_data(self.runs_registry.get_all_runs())

    @controller.set("update_run_scene")
    def update_run_scene(self, run_id: str, scene_id: str):
        """Handle scene change for a run.

        Minimal - just coordinates registry call and UI sync.
        All complexity delegated to registry → core layers.
        """
        new_run = self.runs_registry.update_run_scene(run_id, scene_id)
        self._handle_run_update(run_id, new_run)

    @controller.set("update_run_scenario")
    def update_run_scenario(self, run_id: str, scenario_id: str):
        """Handle scenario change for a run.

        Minimal - just coordinates registry call and UI sync.
        All complexity delegated to registry → core layers.
        Returns the new run ID (may differ from input if run was recreated).
        """
        new_run = self.runs_registry.update_run_scenario(run_id, scenario_id)
        self._handle_run_update(run_id, new_run)
        return new_run.id if new_run else run_id

    @controller.set("update_run_decider")
    def update_run_decider(self, run_id: str, decider_name: str):
        """Handle decider change for a run.

        Minimal - just coordinates registry call and UI sync.
        All complexity delegated to registry → core layers.
        """
        new_run = self.runs_registry.update_run_decider(run_id, decider_name)
        self._handle_run_update(run_id, new_run)

    @controller.set("update_run_llm_backbone")
    def update_run_llm_backbone(self, run_id: str, llm_backbone: str):
        """Handle LLM backbone change for a run.

        Minimal - just coordinates registry call and UI sync.
        All complexity delegated to registry → core layers.
        """
        new_run = self.runs_registry.update_run_llm_backbone(run_id, llm_backbone)
        self._handle_run_update(run_id, new_run)

    @controller.set("add_run_alignment_attribute")
    def add_run_alignment_attribute(self, run_id: str):
        new_run = self.runs_registry.add_run_alignment_attribute(run_id, None)
        self._handle_run_update(run_id, new_run)

    @controller.set("update_run_alignment_attribute_value")
    def update_run_alignment_attribute_value(
        self, run_id: str, attr_index: int, value: str
    ):
        new_run = self.runs_registry.update_run_alignment_attribute_value(
            run_id, {"attr_index": attr_index, "value": value}
        )
        self._handle_run_update(run_id, new_run)

    @controller.set("update_run_alignment_attribute_score")
    def update_run_alignment_attribute_score(
        self, run_id: str, attr_index: int, score: float
    ):
        new_run = self.runs_registry.update_run_alignment_attribute_score(
            run_id, {"attr_index": attr_index, "score": score}
        )
        self._handle_run_update(run_id, new_run)

    @controller.set("delete_run_alignment_attribute")
    def delete_run_alignment_attribute(self, run_id: str, attr_index: int):
        new_run = self.runs_registry.delete_run_alignment_attribute(run_id, attr_index)
        self._handle_run_update(run_id, new_run)

    @controller.set("update_run_probe_text")
    def update_run_probe_text(self, run_id: str, text: str):
        if run_id in self.state.runs:
            self.state.runs[run_id]["prompt"]["probe"]["display_state"] = text
            self.state.dirty("runs")

    @controller.set("update_run_choice_text")
    def update_run_choice_text(self, run_id: str, index: int, text: str):
        if run_id in self.state.runs:
            choices = self.state.runs[run_id]["prompt"]["probe"]["choices"]
            if 0 <= index < len(choices):
                choices[index]["unstructured"] = text
                self.state.dirty("runs")

    @controller.set("add_run_choice")
    def add_run_choice(self, run_id: str):
        new_run = self.runs_registry.add_run_choice(run_id, None)
        self._handle_run_update(run_id, new_run)

    @controller.set("delete_run_choice")
    def delete_run_choice(self, run_id: str, index: int):
        new_run = self.runs_registry.delete_run_choice(run_id, index)
        self._handle_run_update(run_id, new_run)

    @controller.set("check_probe_edited")
    def check_probe_edited(self, run_id: str):
        if not self._is_probe_edited(run_id):
            return

        new_probe_id = self._create_edited_probe_for_run(run_id)
        new_probe = self.probe_registry.get_probe(new_probe_id)
        run = self.runs_registry.get_run(run_id)

        updated_params = run.decider_params.model_copy(
            update={"scenario_input": new_probe.item.input}
        )
        new_run_id = get_id()
        new_run = run.model_copy(
            update={
                "id": new_run_id,
                "probe_id": new_probe_id,
                "decider_params": updated_params,
                "decision": None,
            }
        )
        self.runs_registry.add_run(new_run)

        self.state.runs_to_compare = [
            new_run_id if rid == run_id else rid for rid in self.state.runs_to_compare
        ]
        self._sync_from_runs_data(self.runs_registry.get_all_runs())

    def _is_probe_edited(self, run_id: str) -> bool:
        """Check if UI state differs from original probe."""
        run = self.runs_registry.get_run(run_id)
        if not run:
            return False

        if run_id not in self.state.runs:
            return False

        try:
            original_probe = self.probe_registry.get_probe(run.probe_id)
        except ValueError:
            return False

        ui_run = self.state.runs[run_id]
        current_text = ui_run["prompt"]["probe"].get("display_state", "")
        original_text = original_probe.display_state or ""

        if current_text != original_text:
            return True

        current_choices = ui_run["prompt"]["probe"].get("choices", [])
        original_choices = original_probe.choices or []

        if len(current_choices) != len(original_choices):
            return True

        for curr, orig in zip(current_choices, original_choices):
            if curr.get("unstructured") != orig.get("unstructured"):
                return True

        return False

    def _create_edited_probe_for_run(self, run_id: str) -> str:
        """Create new probe from UI state edited content. Returns new probe_id."""
        run = self.runs_registry.get_run(run_id)
        ui_run = self.state.runs[run_id]
        edited_text = ui_run["prompt"]["probe"].get("display_state", "")
        edited_choices = list(ui_run["prompt"]["probe"].get("choices", []))

        new_probe = self.probe_registry.add_edited_probe(
            run.probe_id, edited_text, edited_choices
        )
        return new_probe.probe_id

    async def _execute_run_decision(self, run_id: str):
        with self.state:
            self.state.runs_computing = list(set(self.state.runs_computing + [run_id]))

        if self._is_probe_edited(run_id):
            new_probe_id = self._create_edited_probe_for_run(run_id)
            run = self.runs_registry.get_run(run_id)
            updated_run = run.model_copy(update={"probe_id": new_probe_id})
            self.runs_registry.add_run(updated_run)
            self.state.runs_to_compare = [
                updated_run.id if rid == run_id else rid
                for rid in self.state.runs_to_compare
            ]
            run_id = updated_run.id

        await self.server.network_completion  # show spinner

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
