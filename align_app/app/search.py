from typing import Optional, Tuple
from trame.decorators import TrameApp, controller
from rapidfuzz import fuzz, process, utils
from ..adm.probe import Probe
from ..utils.utils import debounce


@TrameApp()
class SearchController:
    """Controller for search functionality with dropdown menu."""

    def __init__(self, server, probe_registry, on_search_select=None):
        self.server = server
        self.probe_registry = probe_registry
        self._on_search_select = on_search_select
        self.server.state.search_query = ""
        self.server.state.search_results = []
        self.server.state.search_menu_open = False
        self.server.state.run_search_expanded_id = None
        self.server.state.change("search_query")(
            debounce(0.2, self.server.state)(self.update_search_results)
        )

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

    def _get_search_selection(self, index: int) -> Optional[Tuple[str, str]]:
        """Extract scenario_id and scene_id from search result at index."""
        if not (0 <= index < len(self.server.state.search_results)):
            return None
        result = self.server.state.search_results[index]
        if result.get("id") is None:
            return None
        return (result.get("scenario_id"), result.get("scene_id"))

    @controller.add("select_run_search_result")
    def select_run_search_result(self, run_id, index):
        selection = self._get_search_selection(index)
        if selection and self._on_search_select:
            scenario_id, scene_id = selection
            self._on_search_select(run_id, scenario_id, scene_id)
            self.server.state.run_search_expanded_id = None
