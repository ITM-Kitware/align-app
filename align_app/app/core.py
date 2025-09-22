from trame.app import get_server, asynchronous
from trame.decorators import TrameApp, controller, change
from . import ui
from ..adm.decider import get_decision
from .prompt import PromptController
from ..utils.utils import get_id
from ..adm.adm_core import register_experiment_deciders
import json


@TrameApp()
class AlignApp:
    def __init__(self, server=None):
        self.server = get_server(server, client_type="vue3")

        self.server.cli.add_argument(
            "--decider",
            nargs="*",
            help=(
                "Paths to ADM or experiment config YAML files "
                "like phase2_july_collab/pipeline_baseline.yaml"
            ),
        )

        args, _ = self.server.cli.parse_known_args()
        if args.decider:
            register_experiment_deciders(args.decider)

        self._promptController = PromptController(self.server)

        # Update deciders list if experiment configs were registered
        if args.decider:
            self._promptController.update_deciders()
        if self.server.hot_reload:
            self.server.controller.on_server_reload.add(self._build_ui)

        self._build_ui()
        self.reset_state()
        self.state.runs_json = "[]"

    @property
    def state(self):
        return self.server.state

    @property
    def ctrl(self):
        return self.server.controller

    @controller.set("reset_state")
    def reset_state(self):
        self._promptController.reset()
        self.state.runs = {}
        self.state.runs_to_compare = []

    @controller.set("update_run_to_compare")
    def update_run_to_compare(self, run_index, run_column_index):
        runs = list(self.state.runs.keys())
        self.state.runs_to_compare[run_column_index] = runs[run_index - 1]
        self.state.dirty("runs_to_compare")

    async def make_decision(self):
        prompt = self._promptController.get_prompt()
        run_id = get_id()
        run = {"id": run_id, "prompt": ui.prep_for_state(prompt)}
        with self.state:
            self.state.runs = {
                **self.state.runs,
                run_id: run,
            }
            if len(self.state.runs_to_compare) >= 2:
                self.state.runs_to_compare = self.state.runs_to_compare[1:] + [run_id]
            else:
                self.state.runs_to_compare = self.state.runs_to_compare + [run_id]

        await self.server.network_completion  # let spinner be shown

        adm_result = await get_decision(prompt)

        choice_idx = next(
            (
                i
                for i, choice in enumerate(prompt["scenario"]["choices"])
                if choice["unstructured"] == adm_result.decision["unstructured"]
            ),
            0,
        )
        choice_letter = chr(choice_idx + ord("A"))

        # Create decision with choice letter prefix
        decision_data = adm_result.decision.copy()
        decision_data["unstructured"] = (
            f"{choice_letter}. " + decision_data["unstructured"]
        )
        decision_data["choice_info"] = adm_result.choice_info

        # Format for UI display
        formatted_decision = ui.prep_decision_for_state(decision_data)

        with self.state:
            self.state.runs = {
                id: {**item, "decision": formatted_decision} if id == run_id else item
                for id, item in self.state.runs.items()
            }

    @controller.set("submit_prompt")
    def submit_prompt(self):
        asynchronous.create_task(self.make_decision())

    def export_runs_to_json(self):
        exported_runs = []

        for run_id, run_data in self.state.runs.items():
            if "decision" not in run_data:
                continue

            prompt = run_data["prompt"]
            decision = run_data["decision"]

            # Find choice index from decision unstructured text
            choice_idx = 0
            if "unstructured" in decision:
                decision_text = decision["unstructured"]
                if decision_text and len(decision_text) > 0:
                    first_char = decision_text[0]
                    if first_char.isalpha() and first_char.upper() >= "A":
                        choice_idx = ord(first_char.upper()) - ord("A")

            # Build input section
            input_data = {
                "scenario_id": prompt["scenario"]["scenario_id"],
                "full_state": prompt["scenario"]["full_state"],
                "state": prompt["scenario"]["full_state"]["unstructured"],
                "choices": prompt["scenario"]["choices"],
            }

            # Build output section
            output_data = {"choice": choice_idx}

            # Add action data if available
            if choice_idx < len(prompt["scenario"]["choices"]):
                selected_choice = prompt["scenario"]["choices"][choice_idx]
                output_data["action"] = {
                    "unstructured": selected_choice["unstructured"],
                    "justification": decision.get("justification", ""),
                }

            exported_run = {"input": input_data, "output": output_data}
            exported_runs.append(exported_run)

        return json.dumps(exported_runs, indent=2)

    @change("runs")
    def update_runs_json(self, **_):
        """Update the runs_json state variable whenever runs change"""
        json_data = self.export_runs_to_json()
        self.state.runs_json = json_data
        self.state.flush()

    def _build_ui(self, *args, **kwargs):
        extra_args = {}
        if self.server.hot_reload:
            ui.reload(ui)
            extra_args["reload"] = self._build_ui
        self.ui = ui.AlignLayout(self.server, **extra_args)
