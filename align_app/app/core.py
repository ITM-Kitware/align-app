from pathlib import Path
from trame.app import get_server
from trame.decorators import TrameApp, controller
from . import ui
from .search import SearchController
from .runs_registry import RunsRegistry
from .runs_state_adapter import RunsStateAdapter
from ..adm.decider_registry import create_decider_registry
from ..adm.probe_registry import create_probe_registry
from .import_experiments import import_experiments


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

        self.server.cli.add_argument(
            "--experiments",
            help="Path to directory containing pre-computed experiment results",
        )

        args, _ = self.server.cli.parse_known_args()

        # Skip default probes if either --scenarios or --experiments is provided
        scenarios_paths = args.scenarios
        if args.experiments and scenarios_paths is None:
            scenarios_paths = []

        self._probe_registry = create_probe_registry(scenarios_paths)

        experiment_result = None
        if args.experiments:
            experiment_result = import_experiments(Path(args.experiments))
            self._probe_registry.add_probes(experiment_result.probes)

        self._cli_decider_paths = args.deciders or []
        self._system_adm_paths: list[str] = []
        self._experiment_deciders = experiment_result.deciders if experiment_result else {}

        self._decider_registry = create_decider_registry(
            self._cli_decider_paths,
            self._probe_registry,
            experiment_deciders=self._experiment_deciders,
        )
        self._runs_registry = RunsRegistry(
            self._probe_registry,
            self._decider_registry,
        )

        if experiment_result:
            self._runs_registry.add_experiment_items(experiment_result.items)

        self._runsController = RunsStateAdapter(
            self.server,
            self._probe_registry,
            self._decider_registry,
            self._runs_registry,
            self.add_system_adm,
        )
        self._search_controller = SearchController(
            self.server,
            self._probe_registry,
            on_search_select=self._handle_search_select,
        )

        if self.server.hot_reload:
            self.server.controller.on_server_reload.add(self._build_ui)

        self._build_ui()
        self.reset_state()

    def _handle_search_select(self, run_id: str, scenario_id: str, scene_id: str):
        new_run_id = self._runsController.update_run_scenario(run_id, scenario_id)
        self._runsController.update_run_scene(new_run_id, scene_id)

    @controller.set("reset_state")
    def reset_state(self):
        self._runsController.reset_state()

    def add_system_adm(self, config_path: str):
        """Add a system ADM and recreate the decider registry."""
        if config_path in self._system_adm_paths:
            return

        self._system_adm_paths.append(config_path)
        all_paths = self._cli_decider_paths + self._system_adm_paths
        self._decider_registry = create_decider_registry(
            all_paths,
            self._probe_registry,
            experiment_deciders=self._experiment_deciders,
        )
        self._runs_registry.update_decider_registry(self._decider_registry)
        self._runsController.update_decider_registry(self._decider_registry)

    def _build_ui(self, *args, **kwargs):
        extra_args = {}
        if self.server.hot_reload:
            ui.reload(ui)
            extra_args["reload"] = self._build_ui
        self.ui = ui.AlignLayout(self.server, **extra_args)
