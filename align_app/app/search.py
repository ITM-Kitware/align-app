from trame.decorators import TrameApp, controller
from rapidfuzz import fuzz, process, utils
from ..adm.probe import Probe
from ..utils.utils import debounce


@TrameApp()
class SearchController:
    """Controller for search functionality with dropdown menu."""

    def __init__(self, server, probe_registry):
        self.server = server
        self.probe_registry = probe_registry
        self.runs_state_adapter = None
        self.server.state.search_query = ""
        self.server.state.search_results = []
        self.server.state.search_menu_open = False
        self.server.state.run_search_expanded_id = None
        self.server.state.change("search_query")(
            debounce(0.2, self.server.state)(self.update_search_results)
        )

    def set_runs_state_adapter(self, runs_state_adapter):
        self.runs_state_adapter = runs_state_adapter

    def _create_search_result(self, probe_id, probe: Probe):
        display_state = probe.display_state or ""
        display_text = display_state.split("\n")[0] if display_state else ""
        display_text = f"{display_text[:60]}{'...' if len(display_text) > 60 else ''}"
        return {
            "id": probe_id,
            "scenario_id": probe.scenario_id,
            "scene_id": probe.scene_id,
            "display_text": display_text,
        }

    def update_search_results(self, search_query, **_):
        if not search_query:
            self.server.state.search_results = []
            self.server.state.search_menu_open = False
            return

        probes = self.probe_registry.get_probes()

        searchable_items = {
            probe_id: (
                f"{probe.scenario_id} "
                f"{probe.scene_id} "
                f"{probe.display_state or ''} "
                f"{' '.join(choice.get('unstructured', '') for choice in (probe.choices or []))}"
            )
            for probe_id, probe in probes.items()
        }

        matches = process.extract(
            search_query,
            searchable_items,
            scorer=fuzz.token_set_ratio,
            processor=utils.default_process,
            limit=200,
            score_cutoff=80,
        )

        results = [
            self._create_search_result(probe_id, probes[probe_id])
            for _, _, probe_id in matches
        ]

        self.server.state.search_results = results or [
            {
                "id": None,
                "scenario_id": "",
                "scene_id": "",
                "display_text": "No results found",
            }
        ]
        self.server.state.search_menu_open = True

    @controller.add("select_run_search_result")
    def select_run_search_result(self, run_id, index):
        if 0 <= index < len(self.server.state.search_results):
            result = self.server.state.search_results[index]
            if result.get("id") is not None and self.runs_state_adapter:
                new_run_id = self.runs_state_adapter.update_run_scenario(
                    run_id, result.get("scenario_id")
                )
                self.runs_state_adapter.update_run_scene(
                    new_run_id, result.get("scene_id")
                )
                self.server.state.run_search_expanded_id = None
