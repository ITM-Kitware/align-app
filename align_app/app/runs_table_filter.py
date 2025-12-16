import re
from typing import List, Dict, Any, Tuple
from trame.decorators import TrameApp, change


def natural_sort_key(s: str) -> list:
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]


FILTER_COLUMNS = [
    ("runs_table_filter_scenario", "scenario_id"),
    ("runs_table_filter_scene", "scene_id"),
    ("runs_table_filter_decider", "decider_name"),
    ("runs_table_filter_llm", "llm_backbone_name"),
    ("runs_table_filter_alignment", "alignment_summary"),
    ("runs_table_filter_decision", "decision_text"),
]


def compute_filter_options(
    rows: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    return {
        "runs_table_scenario_options": sorted(
            set(r["scenario_id"] for r in rows if r.get("scenario_id")),
            key=natural_sort_key,
        ),
        "runs_table_scene_options": sorted(
            set(r["scene_id"] for r in rows if r.get("scene_id")),
            key=natural_sort_key,
        ),
        "runs_table_decider_options": sorted(
            set(r["decider_name"] for r in rows if r.get("decider_name")),
            key=natural_sort_key,
        ),
        "runs_table_llm_options": sorted(
            set(r["llm_backbone_name"] for r in rows if r.get("llm_backbone_name")),
            key=natural_sort_key,
        ),
        "runs_table_alignment_options": sorted(
            set(r["alignment_summary"] for r in rows if r.get("alignment_summary")),
            key=natural_sort_key,
        ),
        "runs_table_decision_options": sorted(
            set(r["decision_text"] for r in rows if r.get("decision_text")),
            key=natural_sort_key,
        ),
    }


def filter_rows(
    rows: List[Dict[str, Any]],
    filters: List[Tuple[List[str], str]],
) -> List[Dict[str, Any]]:
    def row_matches(row: Dict[str, Any]) -> bool:
        for filter_values, key in filters:
            if filter_values and row.get(key) not in filter_values:
                return False
        return True

    return [r for r in rows if row_matches(r)]


@TrameApp()
class RunsTableFilter:
    def __init__(self, server):
        self.server = server
        self._all_rows: List[Dict[str, Any]] = []

        self.state.runs_table_filter_scenario = []
        self.state.runs_table_filter_scene = []
        self.state.runs_table_filter_decider = []
        self.state.runs_table_filter_llm = []
        self.state.runs_table_filter_alignment = []
        self.state.runs_table_filter_decision = []

        self.state.runs_table_scenario_options = []
        self.state.runs_table_scene_options = []
        self.state.runs_table_decider_options = []
        self.state.runs_table_llm_options = []
        self.state.runs_table_alignment_options = []
        self.state.runs_table_decision_options = []

    @property
    def state(self):
        return self.server.state

    def set_all_rows(self, rows: List[Dict[str, Any]]):
        self._all_rows = rows
        self._update_filter_options()
        self._apply_filters()

    def _update_filter_options(self):
        options = compute_filter_options(self._all_rows)
        for key, value in options.items():
            setattr(self.state, key, value)

    @change(
        "runs_table_filter_scenario",
        "runs_table_filter_scene",
        "runs_table_filter_decider",
        "runs_table_filter_llm",
        "runs_table_filter_alignment",
        "runs_table_filter_decision",
    )
    def _on_filter_change(self, **kwargs):
        self._apply_filters()

    def _apply_filters(self):
        filters = [
            (getattr(self.state, state_key) or [], col_key)
            for state_key, col_key in FILTER_COLUMNS
        ]
        self.state.runs_table_items = filter_rows(self._all_rows, filters)
