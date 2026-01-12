from typing import Dict, Optional, Callable
from trame.app import asynchronous
from trame.app.file_upload import ClientFile
from trame.decorators import TrameApp, controller, change, trigger
from ..adm.run_models import Run
from .runs_registry import RunsRegistry
from .runs_table_filter import RunsTableFilter
from ..adm.decider.types import DeciderParams
from ..adm.system_adm_discovery import discover_system_adms
from ..utils.utils import get_id
from .runs_presentation import extract_base_scenarios
from . import runs_presentation
from .export_experiments import export_runs_to_zip
from .import_experiments import import_experiments_from_zip
from align_utils.models import AlignmentTarget


@TrameApp()
class RunsStateAdapter:
    def __init__(
        self,
        server,
        probe_registry,
        decider_registry,
        runs_registry: RunsRegistry,
        add_system_adm_callback: Callable[[str], None],
    ):
        self.server = server
        self.runs_registry = runs_registry
        self.probe_registry = probe_registry
        self.decider_registry = decider_registry
        self._add_system_adm_callback = add_system_adm_callback
        self.server.state.pending_cache_keys = []
        self.server.state.runs_table_modal_open = False
        self.server.state.runs_table_selected = []
        self.server.state.runs_table_search = ""
        self.server.state.runs_table_headers = [
            {"title": "", "key": "in_comparison", "sortable": False, "width": "24px"},
            {"title": "Scenario", "key": "scenario_id"},
            {"title": "Scene", "key": "scene_id"},
            {"title": "Situation", "key": "probe_text", "sortable": False},
            {"title": "Decider", "key": "decider_name"},
            {"title": "LLM", "key": "llm_backbone_name"},
            {"title": "Alignment", "key": "alignment_summary"},
            {"title": "Decision", "key": "decision_text"},
        ]
        self.server.state.import_experiment_file = None
        self.server.state.adm_browser_open = False
        self.server.state.adm_browser_run_id = None
        self.server.state.system_adms = {}
        self.server.state.selected_system_adms = []
        self.server.state.probe_dirty = {}
        self.server.state.config_dirty = {}
        self.table_filter = RunsTableFilter(server)
        self._sync_from_runs_data(runs_registry.get_all_runs())

    @property
    def state(self):
        return self.server.state

    def _sync_from_runs_data(self, runs_dict: Dict[str, Run]):
        new_runs = {}
        for run_id, run in runs_dict.items():
            new_run = runs_presentation.run_to_state_dict(
                run, self.probe_registry, self.decider_registry
            )
            new_runs[run_id] = new_run
        self.state.runs = new_runs

        run_table_rows_by_id = {
            row["id"]: row
            for row in (
                runs_presentation.run_to_table_row(run_dict)
                for run_dict in new_runs.values()
            )
        }
        run_table_rows = list(run_table_rows_by_id.values())

        active_cache_keys = {run.compute_cache_key() for run in runs_dict.values()}
        stored_items = self.runs_registry.get_all_experiment_items()
        experiment_table_rows = [
            runs_presentation.experiment_item_to_table_row(
                stored.item, stored.cache_key
            )
            for cache_key, stored in stored_items.items()
            if cache_key not in active_cache_keys
        ]

        self.table_filter.set_all_rows(run_table_rows + experiment_table_rows)

        probes = self.probe_registry.get_probes()
        self.state.base_scenarios = extract_base_scenarios(probes)

        self.state.probe_dirty = {}
        self.state.config_dirty = {}

        if not self.state.runs:
            self.state.runs_to_compare = []
            self.state.runs_json = "[]"
            self.state.run_edit_configs = {}

    @controller.set("reset_runs_state")
    def reset_state(self):
        self.runs_registry.clear_runs()
        self._sync_from_runs_data({})
        self.create_default_run()

    @controller.set("clear_all_runs")
    def clear_all_runs(self):
        self.runs_registry.clear_all()
        self._sync_from_runs_data({})
        self.state.runs_to_compare = []
        self.state.runs_table_selected = []
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
        llm_backbones = (
            decider_options.get("llm_backbones", []) if decider_options else []
        )
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

    @controller.set("delete_run_from_compare")
    def delete_run_from_compare(self, column_index):
        runs_to_compare = list(self.state.runs_to_compare)
        if len(runs_to_compare) > 1:
            runs_to_compare.pop(column_index)
            self.state.runs_to_compare = runs_to_compare

    @controller.set("copy_run")
    def copy_run(self, run_id, column_index):
        source_run = self.runs_registry.get_run(run_id)
        if not source_run:
            return

        new_run = source_run.model_copy(update={"id": get_id()})

        self.runs_registry.add_run(new_run)
        self._sync_run_to_state(new_run, insert_at_index=column_index + 1)

    def _sync_run_to_state(self, run: Run, insert_at_index=None):
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
                runs_to_compare = list(self.state.runs_to_compare)
                if insert_at_index is None:
                    runs_to_compare.append(run.id)
                else:
                    runs_to_compare.insert(insert_at_index, run.id)
                self.state.runs_to_compare = runs_to_compare

    def _handle_run_update(self, old_run_id: str, new_run: Optional[Run]):
        if new_run:
            # Always replace old run ID with new ID in the comparison view
            # This keeps the run in the same UI position
            # Note: Registry layer handles whether to keep or remove the old run
            # based on decision state (see _create_update_method)
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
            choices = self.state.runs[run_id]["prompt"]["probe"]["choices"]
            self.state.probe_dirty[run_id] = self._is_probe_edited(
                run_id, text, choices
            )
            self.state.dirty("probe_dirty")

    @controller.set("update_run_choice_text")
    def update_run_choice_text(self, run_id: str, index: int, text: str):
        if run_id in self.state.runs:
            choices = self.state.runs[run_id]["prompt"]["probe"]["choices"]
            if 0 <= index < len(choices):
                choices[index]["unstructured"] = text
                self.state.dirty("runs")
                probe_text = self.state.runs[run_id]["prompt"]["probe"]["display_state"]
                self.state.probe_dirty[run_id] = self._is_probe_edited(
                    run_id, probe_text, choices
                )
                self.state.dirty("probe_dirty")

    @controller.set("update_run_config_yaml")
    def update_run_config_yaml(self, run_id: str, yaml_text: str):
        if run_id in self.state.runs:
            self.state.runs[run_id]["prompt"]["resolved_config_yaml"] = yaml_text
            self.state.dirty("runs")
            is_edited = self._is_config_edited(run_id, yaml_text)
            self.state.config_dirty[run_id] = is_edited
            self.state.dirty("config_dirty")

    @controller.set("add_run_choice")
    def add_run_choice(self, run_id: str):
        new_run = self.runs_registry.add_run_choice(run_id, None)
        self._handle_run_update(run_id, new_run)

    @controller.set("delete_run_choice")
    def delete_run_choice(self, run_id: str, index: int):
        new_run = self.runs_registry.delete_run_choice(run_id, index)
        self._handle_run_update(run_id, new_run)

    @controller.set("save_probe_edits")
    def save_probe_edits(
        self,
        run_id: str,
        current_text: str = "",
        current_choices: Optional[list] = None,
    ):
        if current_choices is None:
            current_choices = []

        if not self._is_probe_edited(run_id, current_text, current_choices):
            self.state.probe_dirty[run_id] = False
            self.state.dirty("probe_dirty")
            return

        new_probe_id = self._create_edited_probe_for_run(
            run_id, current_text, current_choices
        )
        if not new_probe_id:
            return

        run = self.runs_registry.get_run(run_id)
        if not run:
            return

        if new_probe_id == run.probe_id:
            self.state.probe_dirty[run_id] = False
            self.state.dirty("probe_dirty")
            return

        new_probe = self.probe_registry.get_probe(new_probe_id)
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

        # Cleanup: If original run had no decision (was a draft), remove it
        if run.decision is None:
            self.runs_registry.remove_run(run_id)

        self.state.runs_to_compare = [
            new_run_id if rid == run_id else rid for rid in self.state.runs_to_compare
        ]
        self._sync_from_runs_data(self.runs_registry.get_all_runs())

    @controller.set("save_config_edits")
    def save_config_edits(self, run_id: str, current_yaml: str = ""):
        is_edited = self._is_config_edited(run_id, current_yaml)
        if not is_edited:
            self.state.config_dirty[run_id] = False
            self.state.dirty("config_dirty")
            return

        self._create_run_with_edited_config(run_id, current_yaml)

    def _is_probe_edited(
        self, run_id: str, current_text: str, current_choices: list
    ) -> bool:
        """Check if UI state differs from original probe."""
        run = self.runs_registry.get_run(run_id)
        if not run:
            return False

        try:
            original_probe = self.probe_registry.get_probe(run.probe_id)
        except ValueError:
            return False

        original_text = original_probe.display_state or ""

        if current_text != original_text:
            return True

        original_choices = original_probe.choices or []

        if len(current_choices) != len(original_choices):
            return True

        for curr, orig in zip(current_choices, original_choices):
            if curr.get("unstructured") != orig.get("unstructured"):
                return True

        return False

    def _create_edited_probe_for_run(
        self, run_id: str, edited_text: str, edited_choices: list
    ) -> Optional[str]:
        """Create new probe from UI state edited content. Returns new probe_id."""
        run = self.runs_registry.get_run(run_id)
        if not run:
            return None

        new_probe = self.probe_registry.add_edited_probe(
            run.probe_id, edited_text, list(edited_choices)
        )
        return new_probe.probe_id

    def _is_config_edited(self, run_id: str, current_yaml: str) -> bool:
        """Check if UI config YAML differs from original resolved_config."""
        run = self.runs_registry.get_run(run_id)
        if not run:
            return False

        original_yaml = runs_presentation.resolved_config_to_yaml(
            run.decider_params.resolved_config
        )
        return current_yaml != original_yaml

    def _create_run_with_edited_config(
        self, run_id: str, current_yaml: str
    ) -> Optional[str]:
        """Create new run with edited config. Returns new run_id, or None if no change."""
        import yaml
        from align_app.adm.decider_registry import _get_root_decider_name

        run = self.runs_registry.get_run(run_id)
        if not run:
            return None
        new_config = yaml.safe_load(current_yaml)

        decider_options = self.decider_registry.get_decider_options(
            run.probe_id, run.decider_name
        )
        llm_backbones = (
            decider_options.get("llm_backbones", []) if decider_options else []
        )

        root_decider_name = _get_root_decider_name(run.decider_name)
        root_config = self.decider_registry.get_decider_config(
            probe_id=run.probe_id,
            decider=root_decider_name,
            llm_backbone=run.llm_backbone_name,
        )

        if root_config == new_config:
            new_decider_name = root_decider_name
        else:
            new_decider_name = self.decider_registry.add_edited_decider(
                run.decider_name, new_config, llm_backbones
            )

        if new_decider_name == run.decider_name:
            return None

        updated_params = run.decider_params.model_copy(
            update={"resolved_config": new_config}
        )
        new_run_id = get_id()
        new_run = run.model_copy(
            update={
                "id": new_run_id,
                "decider_name": new_decider_name,
                "decider_params": updated_params,
                "decision": None,
            }
        )
        self.runs_registry.add_run(new_run)

        # Cleanup: If original run had no decision (was a draft), remove it
        if run.decision is None:
            self.runs_registry.remove_run(run_id)

        self.state.runs_to_compare = [
            new_run_id if rid == run_id else rid for rid in self.state.runs_to_compare
        ]
        self._sync_from_runs_data(self.runs_registry.get_all_runs())
        return new_run_id

    def _add_pending_cache_key(self, cache_key: str):
        if cache_key and cache_key not in self.state.pending_cache_keys:
            self.state.pending_cache_keys = [*self.state.pending_cache_keys, cache_key]

    def _remove_pending_cache_key(self, cache_key: str):
        if cache_key:
            self.state.pending_cache_keys = [
                k for k in self.state.pending_cache_keys if k != cache_key
            ]

    async def _execute_run_decision(self, run_id: str):
        ui_run = self.state.runs.get(run_id, {})
        current_text = (
            ui_run.get("prompt", {}).get("probe", {}).get("display_state", "")
        )
        current_choices = ui_run.get("prompt", {}).get("probe", {}).get("choices", [])

        if self._is_probe_edited(run_id, current_text, current_choices):
            new_probe_id = self._create_edited_probe_for_run(
                run_id, current_text, current_choices
            )
            if not new_probe_id:
                return
            run = self.runs_registry.get_run(run_id)
            if not run:
                return
            updated_run = run.model_copy(update={"probe_id": new_probe_id})
            self.runs_registry.add_run(updated_run)
            self._sync_run_to_state(updated_run)
            self.state.runs_to_compare = [
                updated_run.id if rid == run_id else rid
                for rid in self.state.runs_to_compare
            ]
            run_id = updated_run.id

        cache_key = self.state.runs.get(run_id, {}).get("cache_key")

        with self.state:
            self._add_pending_cache_key(cache_key)

        await self.server.network_completion

        await self.runs_registry.execute_run_decision(run_id)

        with self.state:
            all_runs = self.runs_registry.get_all_runs()
            self._sync_from_runs_data(all_runs)
            self._remove_pending_cache_key(cache_key)

    @controller.set("execute_run_decision")
    def execute_run_decision(self, run_id: str):
        asynchronous.create_task(self._execute_run_decision(run_id))

    def export_runs_to_json(self) -> str:
        return runs_presentation.export_runs_to_json(self.state.runs)

    @trigger("export_runs_zip")
    def trigger_export_runs_zip(self) -> bytes:
        return export_runs_to_zip(self.state.runs)

    @trigger("export_table_runs_zip")
    def trigger_export_table_runs_zip(self) -> bytes:
        selected = self.state.runs_table_selected
        if not selected:
            return export_runs_to_zip(self.state.runs)

        selected_runs = {}
        for item in selected:
            cache_key = item["id"] if isinstance(item, dict) else item
            run = self.runs_registry.get_run_by_cache_key(cache_key)
            if not run:
                run = self.runs_registry.materialize_experiment_item(cache_key)
            if run:
                run_dict = runs_presentation.run_to_state_dict(
                    run, self.probe_registry, self.decider_registry
                )
                selected_runs[run.id] = run_dict

        return export_runs_to_zip(selected_runs)

    @controller.set("update_runs_table_selected")
    def update_runs_table_selected(self, selected):
        self.state.runs_table_selected = selected if selected else []

    @controller.set("open_runs_table_modal")
    def open_runs_table_modal(self):
        self.state.runs_table_modal_open = True

    @controller.set("close_runs_table_modal")
    def close_runs_table_modal(self):
        self.state.runs_table_modal_open = False
        self.state.runs_table_selected = []

    @controller.set("add_selected_runs_to_compare")
    def add_selected_runs_to_compare(self):
        selected = self.state.runs_table_selected
        if not selected:
            return

        existing = list(self.state.runs_to_compare)

        for item in selected:
            cache_key = item["id"] if isinstance(item, dict) else item

            run = self.runs_registry.get_run_by_cache_key(cache_key)

            if not run:
                run = self.runs_registry.materialize_experiment_item(cache_key)

            if run and run.id not in existing:
                existing.append(run.id)

        self.state.runs_to_compare = existing
        self.state.runs_table_modal_open = False
        self.state.runs_table_selected = []
        self._sync_from_runs_data(self.runs_registry.get_all_runs())

    @controller.set("on_table_row_click")
    def on_table_row_click(self, _event, item):
        cache_key = item.get("id") if isinstance(item, dict) else item
        if not cache_key:
            return

        run = self.runs_registry.get_run_by_cache_key(cache_key)

        if not run:
            run = self.runs_registry.materialize_experiment_item(cache_key)

        if run and run.id not in self.state.runs_to_compare:
            self.state.runs_to_compare = [*self.state.runs_to_compare, run.id]
            self._sync_from_runs_data(self.runs_registry.get_all_runs())

    @change("runs")
    def update_runs_json(self, **_):
        json_data = self.export_runs_to_json()
        self.state.runs_json = json_data
        self.state.flush()

    @change("import_experiment_file")
    def on_import_experiment_file(self, import_experiment_file, **_):
        if import_experiment_file is None:
            return

        file = ClientFile(import_experiment_file)
        if not file.content:
            return

        result = import_experiments_from_zip(file.content)

        self.probe_registry.add_probes(result.probes)
        self.decider_registry.add_deciders(result.deciders)
        self.runs_registry.add_experiment_items(result.items)

        self._sync_from_runs_data(self.runs_registry.get_all_runs())

        self.state.import_experiment_file = None

    @trigger("import_directory_files")
    def trigger_import_directory_files(self, files_data):
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_info in files_data:
                zf.writestr(file_info["path"], bytes(file_info["content"]))
        zip_buffer.seek(0)

        result = import_experiments_from_zip(zip_buffer.read())
        self.probe_registry.add_probes(result.probes)
        self.decider_registry.add_deciders(result.deciders)
        self.runs_registry.add_experiment_items(result.items)
        self._sync_from_runs_data(self.runs_registry.get_all_runs())

    @trigger("import_zip_bytes")
    def trigger_import_zip_bytes(self, zip_content):
        result = import_experiments_from_zip(bytes(zip_content))
        self.probe_registry.add_probes(result.probes)
        self.decider_registry.add_deciders(result.deciders)
        self.runs_registry.add_experiment_items(result.items)
        self._sync_from_runs_data(self.runs_registry.get_all_runs())

    def update_decider_registry(self, new_registry):
        self.decider_registry = new_registry
        self._sync_from_runs_data(self.runs_registry.get_all_runs())

    @controller.set("open_adm_browser")
    def open_adm_browser(self, run_id: str | None = None):
        self.state.system_adms = discover_system_adms()
        self.state.adm_browser_run_id = run_id
        self.state.adm_browser_open = True

    @controller.set("close_adm_browser")
    def close_adm_browser(self):
        self.state.adm_browser_open = False
        self.state.adm_browser_run_id = None

    @controller.set("select_system_adm")
    def select_system_adm(self, adm_name: str, config_path: str):
        if adm_name not in self.state.selected_system_adms:
            self.state.selected_system_adms = [
                *self.state.selected_system_adms,
                adm_name,
            ]
        self._add_system_adm_callback(config_path)

        if self.state.adm_browser_run_id:
            self.update_run_decider(self.state.adm_browser_run_id, adm_name)

        self.state.adm_browser_open = False
        self.state.adm_browser_run_id = None
