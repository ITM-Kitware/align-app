from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html
from ..utils.utils import noop, readable, readable_sentence
from .unordered_object import (
    UnorderedObject,
    ValueWithProgressBar,
    PlainUnorderedObject,
    PlainNestedObjectRenderer,
    PlainObjectProperty,
)


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


RUN_COLUMN_MIN_WIDTH = "28rem"
LABEL_COLUMN_WIDTH = "12rem"
INDICATOR_SPACE = "3rem"
PENDING_SPINNER_CONDITION = "pending_cache_keys.includes(runs[id].cache_key)"
TITLE_TRUNCATE_STYLE = (
    "overflow: hidden; text-overflow: ellipsis; "
    f"white-space: nowrap; width: calc(100% - {INDICATOR_SPACE});"
)

CHOICE_INFO_DESCRIPTIONS = {
    "Predicted KDMA values": "Key Decision-Making Attributes associated with each choice",
    "ICL example responses": (
        "Training examples with annotated KDMA scores used to guide model alignment through similarity matching"
    ),
    "True KDMA values": "Ground-truth KDMA scores from annotations in the training dataset",
    "True relevance": "Ground-truth relevance labels indicating how much a KDMA applies to the scenario",
    "Alignment info": (
        "Intermediate calculations from alignment functions showing "
        "per-KDMA midpoints, relevance weights, and voting decisions"
    ),
    "Per step timing stats": "Seconds each pipeline ADM step in the took to execute",
}

DROP_HANDLER_JS = """
isDragging = false;
(async (e) => {
    const U8 = utils.get('Uint8Array');
    const P = utils.get('Promise');
    const FR = utils.get('FileReader');

    const readFile = (entry) => new P((resolve) => {
        entry.file((f) => {
            const reader = new FR();
            reader.onload = () => resolve({
                path: entry.fullPath.slice(1),
                content: Array.from(new U8(reader.result))
            });
            reader.readAsArrayBuffer(f);
        });
    });

    const readDir = async (dir) => {
        const files = [];
        const reader = dir.createReader();
        const readBatch = () => new P((resolve) => reader.readEntries(resolve));
        let batch;
        while ((batch = await readBatch()).length > 0) {
            for (const entry of batch) {
                if (entry.isFile) files.push(await readFile(entry));
                else if (entry.isDirectory) files.push(...await readDir(entry));
            }
        }
        return files;
    };

    for (const item of e.dataTransfer.items) {
        const entry = item.webkitGetAsEntry();
        if (!entry) continue;
        if (entry.isFile) {
            const file = item.getAsFile();
            if (file.name.endsWith('.zip')) {
                const buf = await file.arrayBuffer();
                trigger('import_zip_bytes', [Array.from(new U8(buf))]);
            }
        } else if (entry.isDirectory) {
            const files = await readDir(entry);
            trigger('import_directory_files', [files]);
        }
    }
})($event)
""".strip().replace("\n", " ")


class PerKDMARenderer(html.Ul):
    def __init__(self, per_kdma_expr, **kwargs):
        super().__init__(classes="ml-4", **kwargs)
        with self:
            with html.Li(v_for=(f"[kdma, data] in Object.entries({per_kdma_expr})",)):
                html.Span("{{kdma}}: ")
                with html.Template(
                    v_if=("typeof data === 'string' && data.trim()[0] === '{'")
                ):
                    with html.Template(
                        v_if=(
                            "(() => { try { JSON.parse(data); return true; } catch { return false; } })()"
                        )
                    ):
                        PlainNestedObjectRenderer("JSON.parse(data)")
                    with html.Template(v_else=True):
                        html.Span("{{data}}")
                with html.Template(
                    v_else_if=("typeof data === 'object' && data !== null",)
                ):
                    PlainNestedObjectRenderer("data")
                with html.Template(v_else=True):
                    html.Span("{{data}}")


class AlignmentInfoRenderer(html.Ul):
    def __init__(self, alignment_info_expr, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Li(
                v_for=(f"[key, value] in Object.entries({alignment_info_expr})",),
                key=("key",),
            ):
                html.Span("{{key}}: ")
                with html.Template(v_if=("key.toLowerCase() === 'per kdma'",)):
                    PerKDMARenderer("value")
                with html.Template(v_else=True):
                    PlainObjectProperty("value")


def make_keys_readable(obj, max_depth=2, current_depth=0):
    if current_depth >= max_depth or not isinstance(obj, dict):
        return obj

    result = {}
    for key, value in obj.items():
        readable_key = readable_sentence(key)
        if isinstance(value, dict):
            result[readable_key] = make_keys_readable(
                value, max_depth, current_depth + 1
            )
        elif isinstance(value, list):
            result[readable_key] = [
                make_keys_readable(item, max_depth, current_depth + 1)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[readable_key] = value
    return result


def prep_decision_for_state(decision_data):
    choice_info_keys = list(decision_data["choice_info"].keys())
    return {
        **decision_data,
        "choice_info_readable_keys": [readable(key) for key in choice_info_keys],
        "choice_info_readable": make_keys_readable(decision_data["choice_info"]),
    }


class TooltipIcon(vuetify3.VTooltip):
    """Question mark icon with tooltip for showing descriptions."""

    def __init__(self, description_expression, **kwargs):
        super().__init__(location="top", max_width="400px", **kwargs)
        with self:
            with vuetify3.Template(v_slot_activator=("{ props }",)):
                vuetify3.VIcon(
                    "mdi-help-circle-outline",
                    size="small",
                    v_bind="props",
                    classes="ml-2 text-grey",
                )
            html.Div(
                "{{ " + description_expression + " }}",
                style="white-space: normal; word-wrap: break-word;",
            )


class IclExampleListRenderer(html.Ul):
    def __init__(self, icl_data, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Li(
                v_for=(f"[kdma, examples] in Object.entries({icl_data})",),
                key=("kdma",),
            ):
                html.Span("{{kdma}}: ")
                with html.Ul(classes="ml-4"):
                    with html.Li(
                        v_for=("(example, index) in examples",),
                        key=("index",),
                    ):
                        html.Span("Example {{index + 1}}: ")
                        with html.Ul(classes="ml-4"):
                            with html.Li(
                                v_if=(
                                    "example.similarity_score !== null && example.similarity_score !== undefined",
                                )
                            ):
                                html.Span("Similarity: ")
                                ValueWithProgressBar("example.similarity_score")
                            with html.Li(
                                v_else_if=("example.similarity_score === null",)
                            ):
                                html.Span("Random")
                            with html.Li():
                                html.Span("Prompt: {{example.prompt}}")
                            html.Li(
                                "Reasoning: {{example.response.reasoning}}",
                                v_if=("example.response.reasoning",),
                            )
                            with html.Li(
                                v_for=(
                                    "([choice, responseData]) in Object.entries(example.response)"
                                    ".filter(([key]) => key !== 'reasoning')"
                                ),
                                key=("choice",),
                            ):
                                html.Span("{{choice}}: Score ")
                                ValueWithProgressBar(
                                    "responseData.score", decimals=0, max_value=100
                                )


class PanelSection(vuetify3.VExpansionPanel):
    def __init__(self, child, **kwargs):
        super().__init__(**kwargs)

        has_text = hasattr(child, "Text")
        with self:
            # set icons to blank to keep column alignment.  hide-actions changes width of available space.
            icon_kwargs = (
                {"expand_icon": "", "collapse_icon": ""} if not has_text else {}
            )
            with vuetify3.VExpansionPanelTitle(static=not has_text, **icon_kwargs):
                child.Title()
            if has_text:
                with vuetify3.VExpansionPanelText():
                    child.Text()


class RowWithLabel:
    def __init__(self, run_content=noop, label="", no_runs=None, compare_expr=None):
        title = bool(label)
        base_style = (
            f"min-width: {RUN_COLUMN_MIN_WIDTH}; "
            f"flex-basis: {RUN_COLUMN_MIN_WIDTH}; flex-grow: 1;"
        )
        if compare_expr:
            prev_expr = compare_expr.replace(
                "runs[id]", "runs[runs_to_compare[column - 1]]"
            )
            next_expr = compare_expr.replace(
                "runs[id]", "runs[runs_to_compare[column + 1]]"
            )
            diff_from_prev = (
                f"column > 0 && JSON.stringify({compare_expr}) "
                f"!== JSON.stringify({prev_expr})"
            )
            diff_from_next = (
                f"column < runs_to_compare.length - 1 && JSON.stringify({compare_expr}) "
                f"!== JSON.stringify({next_expr})"
            )
            left_shadow = (
                "inset 1px 0 0 0 rgba(0,0,0,0.12), "
                "inset 2px 0 0 0 rgba(0,0,0,0.08), "
                "inset 3px 0 0 0 rgba(0,0,0,0.04)"
            )
            right_shadow = (
                "inset -1px 0 0 0 rgba(0,0,0,0.12), "
                "inset -2px 0 0 0 rgba(0,0,0,0.08), "
                "inset -3px 0 0 0 rgba(0,0,0,0.04)"
            )
            both_shadows = f"{left_shadow}, {right_shadow}"
            shadow_expr = (
                f"({diff_from_prev} && {diff_from_next}) ? '{both_shadows}' : "
                f"({diff_from_prev} ? '{left_shadow}' : "
                f"({diff_from_next} ? '{right_shadow}' : 'none'))"
            )
            border_color = f"({diff_from_prev}) ? 'rgba(0,0,0,0.25)' : 'transparent'"
            col_style = (
                f"`{base_style} border-left: 2px solid ${{({border_color})}}; "
                f"box-shadow: ${{({shadow_expr})}}`",
            )
        else:
            col_style = f"{base_style}; border-left: 2px solid transparent;"

        with vuetify3.VRow(
            no_gutters=False,
            classes="flex-nowrap",
            style=(
                f"`display: inline-flex; min-width: 100%; "
                f"width: calc({LABEL_COLUMN_WIDTH} + ${{runs_to_compare.length}} * "
                f"{RUN_COLUMN_MIN_WIDTH} - {INDICATOR_SPACE});`",
            ),
        ):
            with vuetify3.VCol(
                classes="align-self-center flex-shrink-0 flex-grow-0",
                style=f"width: {LABEL_COLUMN_WIDTH}; min-width: {LABEL_COLUMN_WIDTH}; max-width: {LABEL_COLUMN_WIDTH};",
            ):
                html.Span(label, classes="text-h6")
            with vuetify3.VCol(
                v_for=("(id, column) in runs_to_compare",),
                key=("id",),
                v_if=("runs_to_compare.length > 0",),
                style=col_style,
                classes=(
                    "text-subtitle-1 text-no-wrap text-truncate d-flex align-center flex-shrink-0 ps-4 pe-4"
                    if title
                    else "align-self-stretch text-break flex-shrink-0 ps-4 pe-4"
                ),
            ):
                run_content()
            with vuetify3.VCol(
                v_else=True,
                classes=(
                    "text-subtitle-1 text-no-wrap text-truncate align-self-center"
                    if title
                    else ""
                ),
            ):
                if no_runs:
                    no_runs()


class LlmBackbone:
    class Title(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                vuetify3.VSelect(
                    label="LLM",
                    items=("runs[id].llm_backbone_items",),
                    model_value=("runs[id].prompt.decider_params.llm_backbone",),
                    update_modelValue=(
                        self.server.controller.update_run_llm_backbone,
                        r"[id, $event]",
                    ),
                    hide_details="auto",
                )

            RowWithLabel(
                run_content=run_content,
                label="LLM",
                compare_expr="runs[id].prompt.decider_params.llm_backbone",
            )


class Decider:
    class Title(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                with html.Div(
                    style=f"display: flex; gap: 8px; align-items: center; width: calc(100% - {INDICATOR_SPACE});",
                    raw_attrs=["@click.stop", "@mousedown.stop"],
                ):
                    vuetify3.VSelect(
                        label="Decider",
                        items=("runs[id].decider_items",),
                        model_value=("runs[id].prompt.decider_params.decider",),
                        update_modelValue=(
                            self.server.controller.update_run_decider,
                            r"[id, $event]",
                        ),
                        hide_details="auto",
                        style="flex: 1 1 auto; min-width: 0;",
                    )
                    with vuetify3.VBtn(
                        icon=True,
                        size="small",
                        variant="tonal",
                        click=(self.server.controller.open_adm_browser, "[id]"),
                        style="flex: 0 0 auto;",
                    ):
                        vuetify3.VIcon("mdi-folder-search")

            RowWithLabel(
                run_content=run_content,
                label="Decider",
                compare_expr="runs[id].prompt.decider_params.decider",
            )

    class Text(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                ctrl = self.server.controller
                with html.Div(style="align-self: flex-start; width: 100%;"):
                    vuetify3.VTextarea(
                        model_value=("runs[id].prompt.resolved_config_yaml",),
                        update_modelValue=(
                            ctrl.update_run_config_yaml,
                            r"[id, $event]",
                        ),
                        auto_grow=True,
                        rows=1,
                        variant="outlined",
                        density="compact",
                        hide_details="auto",
                        classes="config-textarea",
                        style="font-family: monospace; font-size: 0.85em;",
                    )
                    with html.Div(classes="d-flex mt-2", v_if="config_dirty[id]"):
                        vuetify3.VBtn(
                            "Save",
                            click=(
                                ctrl.save_config_edits,
                                "[id, runs[id].prompt.resolved_config_yaml]",
                            ),
                            color="primary",
                            size="small",
                        )

            RowWithLabel(
                run_content=run_content,
                label="Config",
                compare_expr="runs[id].prompt.resolved_config_yaml",
            )


class Alignment:
    COMPARE_EXPR = (
        "runs[id].alignment_attributes.map(a => ({value: a.value, score: a.score}))"
    )

    class Title:
        def __init__(self):
            def run_content():
                html.Div(
                    "{{ runs[id].alignment_attributes.length ? "
                    "runs[id].alignment_attributes.map(att => `${att.title} ${att.score}`).join(' - ') : "
                    "'No Alignment' }}",
                    style=TITLE_TRUNCATE_STYLE,
                )

            RowWithLabel(
                run_content=run_content,
                label="Alignment",
                compare_expr=Alignment.COMPARE_EXPR,
            )

    class Text(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                with html.Template(
                    v_for=("attr in runs[id].alignment_attributes",),
                    key=("attr.index",),
                ):
                    with vuetify3.VRow(no_gutters=True):
                        with vuetify3.VSelect(
                            label="Alignment",
                            items=("runs[id].possible_alignment_attributes",),
                            model_value=("attr",),
                            update_modelValue=(
                                self.server.controller.update_run_alignment_attribute_value,
                                r"[id, attr.index, $event]",
                            ),
                            no_data_text="No available alignments",
                            hide_details="auto",
                        ):
                            with vuetify3.Template(v_slot_append_inner=""):
                                TooltipIcon("attr.description")
                        with vuetify3.VBtn(
                            classes="ml-2 mt-1",
                            icon=True,
                            click=(
                                self.server.controller.delete_run_alignment_attribute,
                                "[id, attr.index]",
                            ),
                        ):
                            vuetify3.VIcon("mdi-delete")

                    with vuetify3.VRow(
                        v_if=("attr.possible_scores !== 'continuous' || true",),
                        align="center",
                        justify="center",
                        classes="mb-2",
                    ):
                        with html.Template(
                            v_if=("attr.possible_scores === 'continuous'",)
                        ):
                            vuetify3.VSlider(
                                style="max-width: 300px",
                                model_value=("attr.score",),
                                end=(
                                    self.server.controller.update_run_alignment_attribute_score,
                                    r"[id, attr.index, $event]",
                                ),
                                min=(0,),
                                max=(1,),
                                step=(0.1,),
                                thumb_label=True,
                                hide_details="auto",
                            )
                        vuetify3.VSlider(
                            v_else=True,
                            style="max-width: 300px",
                            model_value=("attr.score",),
                            end=(
                                self.server.controller.update_run_alignment_attribute_score,
                                r"[id, attr.index, $event]",
                            ),
                            max=("attr.possible_scores.length - 1",),
                            ticks=(
                                r"Object.fromEntries(attr.possible_scores.map((s, i) => [i, s]))",
                            ),
                            show_ticks="always",
                            step="1",
                            tick_size="4",
                            hide_details="auto",
                        )

                vuetify3.VBtn(
                    "Add Alignment",
                    click=(
                        self.server.controller.add_run_alignment_attribute,
                        "[id]",
                    ),
                    v_if=(
                        "runs[id].alignment_attributes.length < runs[id].max_alignment_attributes"
                        " && runs[id].possible_alignment_attributes.length > 0"
                    ),
                    classes="my-2",
                )

            RowWithLabel(run_content=run_content, compare_expr=Alignment.COMPARE_EXPR)


class SystemPrompt:
    COMPARE_EXPR = "runs[id].prompt.system_prompt"

    class Title:
        def __init__(self):
            def run_content():
                html.Div(
                    "{{runs[id].prompt.system_prompt}}",
                    style=TITLE_TRUNCATE_STYLE,
                )

            RowWithLabel(
                run_content=run_content,
                label="System Prompt",
                compare_expr=SystemPrompt.COMPARE_EXPR,
            )

    class Text:
        def __init__(self):
            def run_content():
                html.P("{{runs[id].prompt.system_prompt}}")

            RowWithLabel(
                run_content=run_content, compare_expr=SystemPrompt.COMPARE_EXPR
            )


class EditableProbeLayoutForRun:
    def __init__(self, server):
        ctrl = server.controller
        html.Div("Situation", classes="text-h6 pt-4")
        vuetify3.VTextarea(
            model_value=("runs[id].prompt.probe.display_state",),
            update_modelValue=(ctrl.update_run_probe_text, "[id, $event]"),
            auto_grow=True,
            rows=3,
            hide_details="auto",
        )
        html.Div("Choices", classes="text-h6 pt-4")
        with html.Div(classes="ml-4"):
            with html.Ul(classes="pa-0", style="list-style: none"):
                with html.Li(
                    v_for="(choice, index) in runs[id].prompt.probe.choices",
                    key=("index",),
                    classes="d-flex align-center mb-2",
                ):
                    html.Span(
                        "{{String.fromCharCode(65 + index)}}.",
                        classes="mr-2",
                    )
                    vuetify3.VTextarea(
                        model_value=("choice.unstructured",),
                        update_modelValue=(
                            ctrl.update_run_choice_text,
                            "[id, index, $event]",
                        ),
                        auto_grow=True,
                        rows=1,
                        hide_details="auto",
                        density="compact",
                        classes="flex-grow-1",
                    )
                    with vuetify3.VBtn(
                        icon=True,
                        size="small",
                        classes="ml-2",
                        disabled=("runs[id].prompt.probe.choices.length <= 2",),
                        click=(ctrl.delete_run_choice, "[id, index]"),
                        v_if="runs[id].max_choices > 2",
                    ):
                        vuetify3.VIcon("mdi-close", size="small")
            vuetify3.VBtn(
                "Add Choice",
                click=(ctrl.add_run_choice, "[id]"),
                variant="outlined",
                size="small",
                classes="mt-2",
                v_if=(
                    "runs[id].prompt.probe.choices.length < "
                    "runs[id].max_choices && runs[id].max_choices > 2"
                ),
            )
            vuetify3.VBtn(
                "Save",
                click=(
                    ctrl.save_probe_edits,
                    "[id, runs[id].prompt.probe.display_state, runs[id].prompt.probe.choices]",
                ),
                color="primary",
                size="small",
                classes="mt-2 ml-2",
                v_if="probe_dirty[id]",
            )


class Probe:
    COMPARE_EXPR = (
        "runs[id].prompt.probe.scenario_id + '/' + runs[id].prompt.probe.scene_id"
    )

    class Title(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                with html.Div(
                    classes="d-flex ga-2 align-center",
                    style=f"width: calc(100% - {INDICATOR_SPACE});",
                    raw_attrs=["@click.stop", "@mousedown.stop"],
                ):
                    RunSearchField(
                        v_bind=(
                            "{ style: run_search_expanded_id === id ? 'flex: 1;' : 'width: 48px;' }",
                        ),
                    )
                    vuetify3.VSelect(
                        v_if=("run_search_expanded_id !== id",),
                        label="Scenario",
                        items=("base_scenarios",),
                        model_value=("runs[id].prompt.probe.scenario_id",),
                        update_modelValue=(
                            self.server.controller.update_run_scenario,
                            r"[id, $event]",
                        ),
                        hide_details="auto",
                        style="flex: 1;",
                    )
                    vuetify3.VSelect(
                        v_if=("run_search_expanded_id !== id",),
                        label="Scene",
                        items=("runs[id].scene_items",),
                        model_value=("runs[id].prompt.probe.scene_id",),
                        update_modelValue=(
                            self.server.controller.update_run_scene,
                            r"[id, $event]",
                        ),
                        hide_details="auto",
                        style="flex: 1;",
                    )

            RowWithLabel(
                run_content=run_content,
                label="Scenario",
                compare_expr=Probe.COMPARE_EXPR,
            )

    class Text(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                EditableProbeLayoutForRun(self.server)

            RowWithLabel(run_content=run_content, compare_expr=Probe.COMPARE_EXPR)


class Decision:
    COMPARE_EXPR = "runs[id].decision?.unstructured"

    class Title(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def render_run_decision():
                html.Div(
                    "{{runs[id].decision.unstructured}}",
                    v_if=("runs[id].decision",),
                    style=TITLE_TRUNCATE_STYLE,
                )
                with html.Template(v_else=True):
                    vuetify3.VProgressCircular(
                        v_if=(PENDING_SPINNER_CONDITION,),
                        indeterminate=True,
                        size=20,
                    )
                    with vuetify3.VBtn(
                        v_else=True,
                        click=(self.server.controller.execute_run_decision, "[id]"),
                        append_icon="mdi-send",
                        raw_attrs=["@click.stop"],
                    ):
                        html.Span("Choose")

            RowWithLabel(
                run_content=render_run_decision,
                label="Decision",
                compare_expr=Decision.COMPARE_EXPR,
            )

    class Text:
        def __init__(self):
            def render_run_decision_text():
                with html.Template(v_if=("runs[id].decision",)):
                    html.Div("Justification", classes="text-h6")
                    html.P("{{runs[id].decision.justification}}")

            RowWithLabel(
                run_content=render_run_decision_text, compare_expr=Decision.COMPARE_EXPR
            )


class ChoiceInfo:
    COMPARE_EXPR = "runs[id].decision?.choice_info_readable"

    class Title:
        def __init__(self):
            def render_choice_info():
                html.Div(
                    "{{runs[id].decision.choice_info_readable_keys.join(', ')}}",
                    v_if=(
                        "runs[id].decision && runs[id].decision.choice_info_readable_keys",
                    ),
                    style=TITLE_TRUNCATE_STYLE,
                )
                with html.Template(v_else=True):
                    vuetify3.VProgressCircular(
                        v_if=(PENDING_SPINNER_CONDITION,),
                        indeterminate=True,
                        size=20,
                    )

            RowWithLabel(
                run_content=render_choice_info,
                label="Choice Info",
                compare_expr=ChoiceInfo.COMPARE_EXPR,
            )

    class Text:
        def __init__(self):
            def render_choice_info_text():
                with html.Template(
                    v_if=(
                        "runs[id].decision && runs[id].decision.choice_info_readable",
                    )
                ):
                    with html.Div(
                        v_for=(
                            "[key, value] in Object.entries(runs[id].decision.choice_info_readable)",
                        ),
                        key=("key",),
                        classes="mb-4",
                    ):
                        with html.Div(classes="text-h6 d-flex align-center"):
                            html.Span("{{key}}")
                            TooltipIcon(
                                "choiceInfoDescriptions[key] || 'No description available'",
                                v_if=("choiceInfoDescriptions[key]",),
                            )
                        with html.Div(classes="ml-4"):
                            with html.Template(
                                v_if=("key === 'ICL example responses'",)
                            ):
                                IclExampleListRenderer("value")
                            with html.Template(v_else_if=("key === 'Alignment info'",)):
                                AlignmentInfoRenderer("value")
                            with html.Template(
                                v_else_if=("key === 'Per step timing stats'",)
                            ):
                                PlainUnorderedObject("value")
                            with html.Template(v_else=True):
                                UnorderedObject("value")

            RowWithLabel(
                run_content=render_choice_info_text,
                compare_expr=ChoiceInfo.COMPARE_EXPR,
            )


class RunNumber:
    class Title(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                with vuetify3.VRow(no_gutters=True, classes="align-center"):
                    with vuetify3.VCol(classes="flex-grow-1"):
                        vuetify3.VSelect(
                            items=(
                                "Object.values(runs).map((r, i) => ({"
                                "title: (i+1) + ' - ' + (r.comparison_label || ''), value: i + 1}))",
                            ),
                            model_value=("Object.keys(runs).indexOf(id) + 1",),
                            update_modelValue=(
                                self.server.controller.update_run_to_compare,
                                r"[$event, column]",
                            ),
                            hide_details="auto",
                        )
                    with vuetify3.VCol(classes="flex-grow-0 d-flex ga-2 ml-2"):
                        with vuetify3.VBtn(
                            icon=True,
                            size="small",
                            variant="tonal",
                            click=(self.server.controller.copy_run, "[id, column]"),
                        ):
                            vuetify3.VIcon("mdi-plus")
                        with vuetify3.VBtn(
                            icon=True,
                            size="small",
                            variant="tonal",
                            disabled=("runs_to_compare.length <= 1",),
                            click=(
                                self.server.controller.delete_run_from_compare,
                                "[column]",
                            ),
                        ):
                            vuetify3.VIcon("mdi-close")

            def no_runs():
                html.Div("No Runs")

            RowWithLabel(run_content=run_content, label="Run", no_runs=no_runs)


def sortable_filter_header(key: str, title: str, filter_var: str, options_var: str):
    """Create a sortable column header with filter dropdown."""
    with vuetify3.Template(
        raw_attrs=[
            f'v-slot:header.{key}="{{ column, isSorted, getSortIcon, toggleSort }}"'
        ],
    ):
        with html.Div(
            classes="d-flex align-center cursor-pointer",
            raw_attrs=["@click='toggleSort(column)'"],
        ):
            html.Span(title, classes="text-subtitle-2")
            vuetify3.VIcon(
                raw_attrs=[
                    "v-if='isSorted(column)'",
                    ":icon='getSortIcon(column)'",
                ],
                size="small",
                classes="ml-1",
            )
        vuetify3.VSelect(
            v_model=(filter_var,),
            items=(options_var,),
            clearable=True,
            multiple=True,
            density="compact",
            hide_details=True,
            raw_attrs=["@click.stop", "@mousedown.stop"],
        )


def cell_with_tooltip(key: str):
    """Create cell template with native title tooltip."""
    with html.Template(raw_attrs=[f'v-slot:item.{key}="{{ item }}"']):
        html.Span(f"{{{{ item.{key} }}}}", v_bind_title=f"item.{key}")


def situation_cell_with_info_icon():
    """Create situation cell with truncated text and info icon tooltip."""
    with html.Template(raw_attrs=['v-slot:item.probe_text="{ item }"']):
        with html.Div(classes="d-flex align-center", style="gap: 4px;"):
            html.Span(
                "{{ item.probe_text }}",
                style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;",
            )
            with vuetify3.VTooltip(location="top", max_width="400px"):
                with vuetify3.Template(v_slot_activator="{ props }"):
                    vuetify3.VIcon(
                        "mdi-information-outline",
                        size="x-small",
                        v_bind="props",
                        classes="text-grey flex-shrink-0",
                        style="cursor: help;",
                    )
                html.Div(
                    "{{ item.probe_text }}",
                    style="white-space: normal; word-wrap: break-word;",
                )


def filterable_column(key: str, title: str, filter_var: str, options_var: str):
    """Create sortable column header with filter and cell tooltip."""
    sortable_filter_header(key, title, filter_var, options_var)
    cell_with_tooltip(key)


class RunsTablePanel(html.Div):
    def __init__(self, **kwargs):
        super().__init__(
            classes="runs-table-panel d-flex flex-column",
            style=(
                "table_collapsed ? "
                "'flex: 0; width: 0; min-width: 0; height: 100%; overflow: hidden; "
                "transition: flex 0.3s ease, width 0.3s ease, min-width 0.3s ease;' : "
                "'flex: 1; min-width: 25vw; height: 100%; overflow: hidden; "
                "transition: flex 0.3s ease, width 0.3s ease, min-width 0.3s ease;'",
            ),
            **kwargs,
        )
        ctrl = self.server.controller
        with self:
            with html.Div(
                classes="d-flex align-center flex-wrap pa-1 flex-shrink-0 ga-1",
                style=(
                    "table_collapsed ? "
                    "'min-height: 2.5rem; visibility: hidden;' : "
                    "'min-height: 2.5rem;'",
                ),
            ):
                with vuetify3.VBtn(
                    variant="text",
                    click=(ctrl.toggle_table_collapsed,),
                    classes="text-none",
                    size="small",
                ):
                    vuetify3.VIcon("mdi-chevron-left", size="small", classes="mr-1")
                    html.Span("Runs", classes="text-caption")
                    vuetify3.VIcon("mdi-table", size="small", classes="ml-1")
                vuetify3.VTextField(
                    v_model=("runs_table_search",),
                    placeholder="Search...",
                    prepend_inner_icon="mdi-magnify",
                    clearable=True,
                    hide_details=True,
                    density="compact",
                    variant="underlined",
                    style="min-width: 100px; max-width: 200px; flex: 1 1 100px;",
                )
                with vuetify3.VBtn(
                    size="x-small",
                    variant="text",
                    click=(ctrl.clear_all_table_filters,),
                    prepend_icon="mdi-filter-off",
                ):
                    html.Span("Clear")

            with html.Div(style="flex: 1; overflow: auto;"):
                with vuetify3.VCard(elevation=2, classes="ma-1"):
                    with vuetify3.VDataTable(
                        items=("runs_table_items",),
                        headers=("runs_table_headers",),
                        item_value="id",
                        hover=True,
                        density="compact",
                        search=("runs_table_search",),
                        items_per_page=(50,),
                        click_row=(ctrl.on_table_row_click, "[$event, item]"),
                    ):
                        with html.Template(
                            raw_attrs=['v-slot:item.in_comparison="{ item }"']
                        ):
                            with html.Div(style="text-overflow: clip;"):
                                vuetify3.VIcon(
                                    raw_attrs=[
                                        "@click.stop",
                                        ':icon="runs_to_compare.some('
                                        "rid => runs[rid]?.cache_key === item.id) "
                                        "? 'mdi-eye' : 'mdi-eye-off'\"",
                                    ],
                                    size="small",
                                    style="cursor: pointer;",
                                    click=(ctrl.toggle_run_in_comparison, "[item.id]"),
                                )
                        filterable_column(
                            "scenario_id",
                            "Scenario",
                            "runs_table_filter_scenario",
                            "runs_table_scenario_options",
                        )
                        filterable_column(
                            "scene_id",
                            "Scene",
                            "runs_table_filter_scene",
                            "runs_table_scene_options",
                        )
                        situation_cell_with_info_icon()
                        filterable_column(
                            "decider_name",
                            "Decider",
                            "runs_table_filter_decider",
                            "runs_table_decider_options",
                        )
                        filterable_column(
                            "llm_backbone_name",
                            "LLM",
                            "runs_table_filter_llm",
                            "runs_table_llm_options",
                        )
                        filterable_column(
                            "alignment_summary",
                            "Alignment",
                            "runs_table_filter_alignment",
                            "runs_table_alignment_options",
                        )
                        filterable_column(
                            "decision_text",
                            "Decision",
                            "runs_table_filter_decision",
                            "runs_table_decision_options",
                        )
                        with html.Template(raw_attrs=["v-slot:no-data"]):
                            with html.Div(
                                classes="d-flex flex-column align-center pa-4"
                            ):
                                html.Div("No runs found", classes="text-body-2")


class ComparisonPanel(html.Div):
    def __init__(self, **kwargs):
        super().__init__(
            classes="comparison-panel d-flex flex-column flex-grow-1",
            style="min-width: 0; height: 100%; overflow: hidden;",
            **kwargs,
        )
        ctrl = self.server.controller
        with self:
            with html.Div(
                classes="d-flex justify-end align-center pa-1 flex-shrink-0",
                style=(
                    "comparison_collapsed ? "
                    "'height: 2.5rem; visibility: hidden;' : "
                    "'height: 2.5rem;'",
                ),
            ):
                with vuetify3.VBtn(
                    variant="text",
                    click=(ctrl.toggle_comparison_collapsed,),
                    classes="text-none",
                    size="small",
                ):
                    vuetify3.VIcon("mdi-compare", size="small", classes="mr-1")
                    html.Span("Compare", classes="text-caption")
                    vuetify3.VIcon("mdi-chevron-right", size="small", classes="ml-1")

            with html.Div(style="flex: 1; overflow: auto;"):
                ResultsComparison()


class RunsTableModal(html.Div):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VDialog(
                v_model=("runs_table_modal_open",),
                fullscreen=True,
            ):
                with vuetify3.VCard():
                    with vuetify3.VToolbar(density="compact"):
                        vuetify3.VToolbarTitle("Runs")
                        vuetify3.VSpacer()
                        vuetify3.VTextField(
                            v_model=("runs_table_search",),
                            placeholder="Search",
                            prepend_inner_icon="mdi-magnify",
                            clearable=True,
                            hide_details=True,
                            density="compact",
                            style="max-width: 300px;",
                            classes="mr-4",
                        )
                        with vuetify3.VBtn(
                            click=(self.server.controller.clear_all_table_filters,),
                            prepend_icon="mdi-filter-off",
                            classes="mr-4",
                        ):
                            html.Span("Clear Filters")
                        with vuetify3.VBtn(
                            click=(
                                self.server.controller.add_selected_runs_to_compare,
                            ),
                            disabled=("runs_table_selected.length === 0",),
                            prepend_icon="mdi-compare",
                            classes="mr-4",
                        ):
                            html.Span("Compare Selected")
                        vuetify3.VFileInput(
                            v_model=("import_experiment_file", None),
                            accept=".zip",
                            ref="tableImportFileInput",
                            style="display: none;",
                        )
                        html.Input(
                            type="file",
                            ref="tableDirInput",
                            style="display: none;",
                            raw_attrs=[
                                "webkitdirectory",
                                "directory",
                                (
                                    '@change="if($event && $event.target && $event.target.files) {'
                                    "(async (files) => {"
                                    "const data = [];"
                                    "const U8 = utils.get('Uint8Array');"
                                    "for (let i = 0; i < files.length; i++) {"
                                    "const f = files[i];"
                                    "const buf = await f.arrayBuffer();"
                                    "data.push({path: f.webkitRelativePath, content: Array.from(new U8(buf))});"
                                    "}"
                                    "trigger('import_directory_files', [data]);"
                                    "})($event.target.files);"
                                    '}"'
                                ),
                            ],
                        )
                        with vuetify3.VMenu():
                            with vuetify3.Template(v_slot_activator="{ props }"):
                                with vuetify3.VBtn(
                                    v_bind="props",
                                    prepend_icon="mdi-upload",
                                    classes="mr-4",
                                ):
                                    html.Span("Load Experiments")
                            with vuetify3.VList(density="compact"):
                                vuetify3.VListItem(
                                    title="From Zip File",
                                    prepend_icon="mdi-zip-box",
                                    click=(
                                        "trame.refs.tableImportFileInput.$el"
                                        ".querySelector('input').click()"
                                    ),
                                )
                                vuetify3.VListItem(
                                    title="From Directory",
                                    prepend_icon="mdi-folder-open",
                                    click="trame.refs.tableDirInput.click()",
                                )
                        with vuetify3.VBtn(
                            click=(
                                "utils.download('align-app-experiments.zip', "
                                "trigger('export_table_runs_zip'), 'application/zip')"
                            ),
                            prepend_icon="mdi-download",
                            classes="mr-4",
                        ):
                            html.Span("Download")
                            vuetify3.VBadge(
                                content=("runs_table_selected.length || '   '",),
                                inline=True,
                                color="grey",
                                style=(
                                    "'opacity: ' + (runs_table_selected.length > 0 ? '1' : '0')",
                                ),
                            )
                        with vuetify3.VMenu():
                            with vuetify3.Template(v_slot_activator="{ props }"):
                                with vuetify3.VBtn(
                                    v_bind="props",
                                    prepend_icon="mdi-delete-sweep",
                                    classes="mr-4",
                                ):
                                    html.Span("Delete All")
                            with vuetify3.VCard(min_width="200"):
                                vuetify3.VCardTitle(
                                    "Delete all runs?", classes="text-subtitle-1"
                                )
                                with vuetify3.VCardActions():
                                    vuetify3.VSpacer()
                                    vuetify3.VBtn("Cancel", variant="text")
                                    vuetify3.VBtn(
                                        "Delete",
                                        color="error",
                                        variant="text",
                                        click=self.server.controller.clear_all_runs,
                                    )
                        with vuetify3.VBtn(
                            icon=True,
                            click=(self.server.controller.close_runs_table_modal,),
                        ):
                            vuetify3.VIcon("mdi-close")
                    with vuetify3.VCardText(
                        classes="pa-0",
                        style="height: calc(100vh - 64px); overflow: auto;",
                    ):
                        with vuetify3.VDataTable(
                            items=("runs_table_items",),
                            headers=("runs_table_headers",),
                            model_value=("runs_table_selected",),
                            update_modelValue=(
                                self.server.controller.update_runs_table_selected,
                                "[$event]",
                            ),
                            item_value="id",
                            show_select=True,
                            hover=True,
                            search=("runs_table_search",),
                            items_per_page=(100,),
                            click_row=(
                                self.server.controller.on_table_row_click,
                                "[$event, item]",
                            ),
                        ):
                            with html.Template(
                                raw_attrs=['v-slot:item.in_comparison="{ item }"']
                            ):
                                with html.Div(style="text-overflow: clip;"):
                                    vuetify3.VIcon(
                                        raw_attrs=[
                                            "@click.stop",
                                            ':icon="runs_to_compare.some('
                                            "rid => runs[rid]?.cache_key === item.id) "
                                            "? 'mdi-eye' : 'mdi-eye-off'\"",
                                        ],
                                        size="small",
                                        style="cursor: pointer;",
                                        click=(
                                            self.server.controller.toggle_run_in_comparison,
                                            "[item.id]",
                                        ),
                                    )
                            filterable_column(
                                "scenario_id",
                                "Scenario",
                                "runs_table_filter_scenario",
                                "runs_table_scenario_options",
                            )
                            filterable_column(
                                "scene_id",
                                "Scene",
                                "runs_table_filter_scene",
                                "runs_table_scene_options",
                            )
                            situation_cell_with_info_icon()
                            filterable_column(
                                "decider_name",
                                "Decider",
                                "runs_table_filter_decider",
                                "runs_table_decider_options",
                            )
                            filterable_column(
                                "llm_backbone_name",
                                "LLM",
                                "runs_table_filter_llm",
                                "runs_table_llm_options",
                            )
                            filterable_column(
                                "alignment_summary",
                                "Alignment",
                                "runs_table_filter_alignment",
                                "runs_table_alignment_options",
                            )
                            filterable_column(
                                "decision_text",
                                "Decision",
                                "runs_table_filter_decision",
                                "runs_table_decision_options",
                            )
                            with html.Template(raw_attrs=["v-slot:no-data"]):
                                with html.Div(
                                    classes="d-flex flex-column align-center pa-8"
                                ):
                                    html.Div(
                                        "No matching runs found",
                                        classes="text-h6 mb-4",
                                    )
                                    with vuetify3.VBtn(
                                        click=(
                                            self.server.controller.clear_all_table_filters,
                                        ),
                                        prepend_icon="mdi-filter-off",
                                        v_if=(
                                            "runs_table_filter_scenario.length > 0 || "
                                            "runs_table_filter_scene.length > 0 || "
                                            "runs_table_filter_decider.length > 0 || "
                                            "runs_table_filter_llm.length > 0 || "
                                            "runs_table_filter_alignment.length > 0 || "
                                            "runs_table_filter_decision.length > 0 || "
                                            "runs_table_search"
                                        ),
                                    ):
                                        html.Span("Clear Filters")


class AdmBrowserModal(html.Div):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VDialog(
                v_model=("adm_browser_open",),
                max_width="600px",
            ):
                with vuetify3.VCard():
                    with vuetify3.VToolbar(density="compact"):
                        vuetify3.VToolbarTitle("System ADMs")
                        vuetify3.VSpacer()
                        with vuetify3.VBtn(
                            icon=True,
                            click=self.server.controller.close_adm_browser,
                        ):
                            vuetify3.VIcon("mdi-close")
                    with vuetify3.VCardText(
                        style="max-height: 70vh; overflow-y: auto;",
                    ):
                        with html.Div(
                            v_for="(adms, category) in system_adms",
                            key="category",
                            classes="mb-4",
                        ):
                            html.Div(
                                "{{ category }}",
                                classes="text-subtitle-1 font-weight-bold mb-2",
                            )
                            with vuetify3.VList(density="compact"):
                                with vuetify3.VListItem(
                                    v_for="adm in adms",
                                    key="adm.name",
                                    click=(
                                        self.server.controller.select_system_adm,
                                        "[adm.name, adm.config_path]",
                                    ),
                                ):
                                    with vuetify3.VListItemTitle():
                                        html.Span("{{ adm.title }}")
                                    with vuetify3.Template(v_slot_append=""):
                                        vuetify3.VIcon(
                                            "mdi-check",
                                            v_if=(
                                                "selected_system_adms.includes(adm.name)",
                                            ),
                                            color="success",
                                        )


class ResultsComparison(html.Div):
    def __init__(self, **kwargs):
        super().__init__(classes="d-inline-flex flex-wrap ga-4", **kwargs)
        with self:
            with vuetify3.VExpansionPanels(
                multiple=True, variant="accordion", classes="ma-1"
            ):
                PanelSection(child=RunNumber)
                PanelSection(child=Probe)
                PanelSection(child=Decider)
                PanelSection(child=Alignment)
                PanelSection(child=SystemPrompt)
                PanelSection(child=LlmBackbone)
                PanelSection(child=Decision)
                PanelSection(child=ChoiceInfo)


class RunSearchField(html.Div):
    """Search field for runs with dropdown results menu."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Div(
                raw_attrs=[
                    'v-click-outside="() => { '
                    'if (run_search_expanded_id === id) run_search_expanded_id = null }"'
                ],
            ):
                with vuetify3.VMenu(
                    v_model=("search_menu_open",),
                    close_on_content_click=False,
                    location="bottom",
                    offset=(8,),
                ):
                    with vuetify3.Template(v_slot_activator=("{ props }",)):
                        vuetify3.VTextField(
                            v_model=("search_query",),
                            placeholder="Search",
                            prepend_inner_icon="mdi-magnify",
                            clearable=("run_search_expanded_id === id",),
                            hide_details="auto",
                            v_bind="props",
                            focus="run_search_expanded_id = id",
                            click_clear="run_search_expanded_id = null; search_query = ''",
                        )
                    with vuetify3.VCard(
                        v_if=("run_search_expanded_id === id",),
                    ):
                        with vuetify3.VList(density="compact"):
                            with vuetify3.VListItem(
                                v_for="(result, index) in search_results",
                                key="result.id",
                                click=(
                                    self.server.controller.select_run_search_result,
                                    "[id, index]",
                                ),
                                disabled=("result.id === null",),
                            ):
                                with vuetify3.VListItemTitle():
                                    html.Span(
                                        "{{ result.scenario_id }} - {{ result.scene_id }}",
                                        classes="font-weight-medium",
                                        v_if=("result.id !== null",),
                                    )
                                with vuetify3.VListItemSubtitle():
                                    html.Span(
                                        "{{ result.display_text }}",
                                        classes="text-caption",
                                    )


class AlignLayout(SinglePageLayout):
    def __init__(
        self,
        server,
        reload=None,
        **kwargs,
    ):
        super().__init__(server, **kwargs)

        self.state.trame__title = "align-app"
        self.state.choiceInfoDescriptions = CHOICE_INFO_DESCRIPTIONS
        self.state.isDragging = False
        self.title.set_text("Align App")
        self.icon.hide()
        self.footer.hide()

        with self as layout:
            with layout.toolbar:
                vuetify3.VSpacer()
                if reload:
                    with vuetify3.VBtn(icon=True, click=reload):
                        vuetify3.VIcon("mdi-refresh")
                vuetify3.VFileInput(
                    v_model=("import_experiment_file", None),
                    accept=".zip",
                    ref="importFileInput",
                    style="display: none;",
                )
                html.Input(
                    type="file",
                    ref="dirInput",
                    style="display: none;",
                    raw_attrs=[
                        "webkitdirectory",
                        "directory",
                        (
                            '@change="if($event && $event.target && $event.target.files) {'
                            "(async (files) => {"
                            "const data = [];"
                            "const U8 = utils.get('Uint8Array');"
                            "for (let i = 0; i < files.length; i++) {"
                            "const f = files[i];"
                            "const buf = await f.arrayBuffer();"
                            "data.push({path: f.webkitRelativePath, content: Array.from(new U8(buf))});"
                            "}"
                            "trigger('import_directory_files', [data]);"
                            "})($event.target.files);"
                            '}"'
                        ),
                    ],
                )
                with vuetify3.VMenu():
                    with vuetify3.Template(v_slot_activator="{ props }"):
                        with vuetify3.VBtn(v_bind="props", prepend_icon="mdi-upload"):
                            html.Span("Load Experiments")
                    with vuetify3.VList(density="compact"):
                        vuetify3.VListItem(
                            title="From Zip File",
                            prepend_icon="mdi-zip-box",
                            click="trame.refs.importFileInput.$el.querySelector('input').click()",
                        )
                        vuetify3.VListItem(
                            title="From Directory",
                            prepend_icon="mdi-folder-open",
                            click="trame.refs.dirInput.click()",
                        )
                with vuetify3.VBtn(
                    click="utils.download('align-app-experiments.zip', trigger('export_runs_zip'), 'application/zip')",
                    disabled=("Object.keys(runs).length === 0",),
                    prepend_icon="mdi-download",
                ):
                    html.Span("Download Experiments")
                with vuetify3.VMenu():
                    with vuetify3.Template(v_slot_activator="{ props }"):
                        with vuetify3.VBtn(
                            v_bind="props",
                            prepend_icon="mdi-close-circle-outline",
                        ):
                            html.Span("Close Runs")
                    with vuetify3.VCard(min_width="200"):
                        vuetify3.VCardTitle(
                            "Close all runs?", classes="text-subtitle-1"
                        )
                        with vuetify3.VCardActions():
                            vuetify3.VSpacer()
                            vuetify3.VBtn("Cancel", variant="text")
                            vuetify3.VBtn(
                                "Close",
                                color="error",
                                variant="text",
                                click=self.server.controller.reset_state,
                            )

            with layout.content:
                html.Div(
                    v_html=(
                        "'<style>"
                        "html { overflow: hidden !important; }"
                        ".v-textarea .v-field__input { overflow-y: hidden !important; }"
                        ".v-expansion-panel { max-width: none !important; }"
                        ".config-textarea textarea { white-space: pre; overflow-x: auto; }"
                        ".runs-table-panel .v-data-table table { table-layout: fixed; width: 100%; }"
                        ".runs-table-panel .v-data-table td { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }"
                        ".runs-table-panel .v-data-table th { vertical-align: top; }"
                        ".runs-table-panel .v-data-table th:first-child { padding-top: 8px; }"
                        ".drop-zone-active { outline: 3px dashed #1976d2 !important; outline-offset: -3px; }"
                        "</style>'"
                    )
                )
                with html.Div(
                    classes="d-flex",
                    style="height: calc(100vh - 64px); position: relative;",
                ):
                    with html.Div(
                        v_if=("table_collapsed",),
                        classes="d-flex align-center pa-1",
                        style="position: absolute; top: 0; left: 0; z-index: 1; height: 2.5rem;",
                    ):
                        with vuetify3.VBtn(
                            variant="text",
                            click=(server.controller.toggle_table_collapsed,),
                            classes="text-none",
                            size="small",
                        ):
                            vuetify3.VIcon(
                                "mdi-chevron-right", size="small", classes="mr-1"
                            )
                            html.Span("Runs", classes="text-caption")
                            vuetify3.VIcon("mdi-table", size="small", classes="ml-1")
                    with html.Div(
                        v_if=("comparison_collapsed",),
                        classes="d-flex align-center pa-1",
                        style="position: absolute; top: 0; right: 0; z-index: 1; height: 2.5rem;",
                    ):
                        with vuetify3.VBtn(
                            variant="text",
                            click=(server.controller.toggle_comparison_collapsed,),
                            classes="text-none",
                            size="small",
                        ):
                            vuetify3.VIcon("mdi-compare", size="small", classes="mr-1")
                            html.Span("Compare", classes="text-caption")
                            vuetify3.VIcon(
                                "mdi-chevron-left", size="small", classes="ml-1"
                            )
                    RunsTablePanel()
                    with html.Div(
                        classes=("isDragging ? 'drop-zone-active' : ''",),
                        style=(
                            "comparison_collapsed ? "
                            "'flex: 0; width: 0; min-width: 0; margin-left: auto; overflow: hidden; "
                            "transition: flex 0.3s ease, width 0.3s ease, min-width 0.3s ease;' : "
                            "'flex: 1; min-width: 200px; margin-left: auto; overflow: hidden; "
                            "transition: flex 0.3s ease, width 0.3s ease, min-width 0.3s ease;'",
                        ),
                        raw_attrs=[
                            '@dragover.prevent="isDragging = true"',
                            '@dragleave.prevent="isDragging = false"',
                            f'@drop.prevent="{DROP_HANDLER_JS}"',
                        ],
                    ):
                        ComparisonPanel()
                RunsTableModal()
                AdmBrowserModal()
