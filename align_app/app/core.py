from pathlib import Path
from trame.app import get_server
from trame.decorators import TrameApp, controller
from . import ui
from .search import SearchController
from .runs_registry import create_runs_registry
from .runs_state_adapter import RunsStateAdapter
from ..adm.decider_registry import create_decider_registry
from ..adm.probe_registry import create_probe_registry
from ..adm.experiment_results_registry import create_experiment_results_registry
from ..adm.experiment_converters import (
    probes_from_experiment_items,
    deciders_from_experiments,
)


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

        self._experiment_results_registry = (
            create_experiment_results_registry(Path(args.experiments))
            if args.experiments
            else None
        )

        experiment_deciders = {}
        if self._experiment_results_registry:
            experiment_probes = probes_from_experiment_items(
                self._experiment_results_registry.get_all_items()
            )
            self._probe_registry.add_probes(experiment_probes)

            experiment_deciders = deciders_from_experiments(
                self._experiment_results_registry.get_experiments()
            )

        self._decider_registry = create_decider_registry(
            args.deciders or [],
            self._probe_registry,
            experiment_deciders=experiment_deciders,
        )
        self._runs_registry = create_runs_registry(
            self._probe_registry,
            self._decider_registry,
        )
        self._search_controller = SearchController(self.server, self._probe_registry)
        self._runsController = RunsStateAdapter(
            self.server,
            self._probe_registry,
            self._decider_registry,
            self._runs_registry,
        )
        self._search_controller.set_runs_state_adapter(self._runsController)

        if self.server.hot_reload:
            self.server.controller.on_server_reload.add(self._build_ui)

        self._build_ui()
        self.reset_state()

    @controller.set("reset_state")
    def reset_state(self):
        self._runsController.reset_state()

    def _build_ui(self, *args, **kwargs):
        extra_args = {}
        if self.server.hot_reload:
            ui.reload(ui)
            extra_args["reload"] = self._build_ui
        self.ui = ui.AlignLayout(self.server, **extra_args)
