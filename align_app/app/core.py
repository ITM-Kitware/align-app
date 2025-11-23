from trame.app import get_server
from trame.decorators import TrameApp, controller
from . import ui
from .prompt import PromptController
from .runs_registry import create_runs_registry
from .runs_state_adapter import RunsStateAdapter


@TrameApp()
class AlignApp:
    def __init__(self, server=None):
        self.server = get_server(server, client_type="vue3")

        self.server.cli.add_argument(
            "--deciders",
            nargs="*",
            help=(
                "Paths to ADM or experiment config YAML files "
                "like phase2_july_collab/pipeline_baseline.yaml"
            ),
        )

        self.server.cli.add_argument(
            "--scenarios",
            nargs="*",
            help="Paths to scenarios JSON files or directories of JSON files (space-separated)",
        )

        args, _ = self.server.cli.parse_known_args()

        self._promptController = PromptController(
            self.server, args.deciders, args.scenarios
        )
        self._runs_registry = create_runs_registry()
        self._runsController = RunsStateAdapter(
            self.server, self._promptController, self._runs_registry
        )

        if self.server.hot_reload:
            self.server.controller.on_server_reload.add(self._build_ui)

        self._build_ui()
        self.reset_state()
        self._populate_available_probes()

    @property
    def state(self):
        return self.server.state

    @property
    def ctrl(self):
        return self.server.controller

    @controller.set("reset_state")
    def reset_state(self):
        self._runsController.reset_state()
        self.state.available_probes = []

    def _populate_available_probes(self):
        probes = self._promptController.probe_registry.get_probes()
        self.state.available_probes = [
            {
                "text": f"{probe.scenario_id} - {probe.scene_id} - {probe_id}",
                "value": probe_id,
            }
            for probe_id, probe in probes.items()
        ]

    def _initialize_run_edit_config(self, run_id: str):
        if run_id not in self.state.runs:
            return

        run = self.state.runs[run_id]
        prompt = run["prompt"]

        self.state.run_edit_configs[run_id] = {
            "probe_id": prompt["probe"]["id"],
            "decider": prompt["decider"]["name"],
            "llm_backbone": prompt["llm_backbone"],
            "alignment_attributes": prompt.get("alignment_target", {})
            .get("kdma_values", [])
            .copy(),
            "edited_probe_text": prompt["probe"]["state"],
            "edited_choices": [
                choice["unstructured"] for choice in prompt["probe"]["choices"]
            ],
            "system_prompt": prompt.get("system_prompt", ""),
        }

        self.state.run_needs_execution[run_id] = False
        self.state.run_cache_available[run_id] = False
        self.state.run_validation_errors[run_id] = []

    def _get_cache_key_for_run(self, run_id: str) -> str:
        raise NotImplementedError(
            "TODO: Update for Phase 2 - need to build DeciderParams from edit config"
        )

    def _has_run_config_changed(self, run_id: str) -> bool:
        if run_id not in self.state.runs or run_id not in self.state.run_edit_configs:
            return False

        original_run = self.state.runs[run_id]
        edit_config = self.state.run_edit_configs[run_id]
        prompt = original_run["prompt"]

        return (
            edit_config["probe_id"] != prompt["probe"]["id"]
            or edit_config["decider"] != prompt["decider"]["name"]
            or edit_config["llm_backbone"] != prompt["llm_backbone"]
            or edit_config["alignment_attributes"]
            != prompt.get("alignment_target", {}).get("kdma_values", [])
            or edit_config["edited_probe_text"] != prompt["probe"]["state"]
            or [choice for choice in edit_config["edited_choices"]]
            != [choice["unstructured"] for choice in prompt["probe"]["choices"]]
        )

    def _build_ui(self, *args, **kwargs):
        extra_args = {}
        if self.server.hot_reload:
            ui.reload(ui)
            extra_args["reload"] = self._build_ui
        self.ui = ui.AlignLayout(self.server, **extra_args)
