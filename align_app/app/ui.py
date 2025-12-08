from typing import Any, Dict, cast
import copy
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html
from ..adm.types import Prompt, SerializedPrompt, SerializedAlignmentTarget
from ..adm.probe import Probe as ProbeModel
from ..utils.utils import noop, readable, readable_sentence, sentence_lines
from .prompt_logic import get_alignment_descriptions_map
from .unordered_object import (
    UnorderedObject,
    ValueWithProgressBar,
    PlainUnorderedObject,
    PlainNestedObjectRenderer,
    PlainObjectProperty,
)


def serialize_prompt(prompt: Prompt) -> SerializedPrompt:
    """Serialize a prompt for JSON/state storage, removing non-serializable fields.

    This is THE serialization boundary - converts Probe to dict for UI state.
    Input: prompt["probe"] is Probe model
    Output: prompt["probe"] is dict
    """
    probe: ProbeModel = prompt["probe"]
    alignment_target = cast(
        SerializedAlignmentTarget, prompt["alignment_target"].model_dump()
    )

    system_prompt: str = prompt.get("system_prompt", "")  # type: ignore[assignment]
    result: SerializedPrompt = {
        "probe": probe.to_dict(),
        "alignment_target": alignment_target,
        "decider_params": prompt["decider_params"],
        "system_prompt": system_prompt,
    }

    return copy.deepcopy(result)


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


SENTENCE_KEYS = ["intent", "unstructured"]  # Keys to apply sentence function to

RUN_COLUMN_MIN_WIDTH = "28rem"

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


def readable_probe(probe):
    full_state = probe.full_state or {}
    characters = full_state.get("characters", [])
    readable_characters = [
        {**c, **{key: sentence_lines(c[key]) for key in SENTENCE_KEYS if key in c}}
        for c in characters
    ]

    return {
        "probe_id": probe.probe_id,
        "scene_id": probe.scene_id,
        "scenario_id": probe.scenario_id,
        "display_state": probe.display_state,
        "full_state": {**full_state, "characters": readable_characters},
        "choices": probe.choices,
        "state": probe.state,
    }


def readable_attribute(kdma_value, descriptions):
    return {
        **kdma_value,
        "description": descriptions.get(kdma_value.get("kdma"), {}).get(
            "description",
            f"No description for {kdma_value.get('kdma')}",
        ),
        "kdma": readable(kdma_value.get("kdma")),
        "value": round(kdma_value.get("value"), 2),
    }


def prep_for_state(prompt: Prompt):
    descriptions = get_alignment_descriptions_map(prompt)
    p = serialize_prompt(prompt)
    result: Dict[str, Any] = {
        **p,
        "alignment_target": {
            **p["alignment_target"],
            "kdma_values": [
                readable_attribute(a, descriptions)
                for a in p["alignment_target"]["kdma_values"]
            ],
        },
        "decider_params": {
            **p["decider_params"],
            "decider": readable(p["decider_params"]["decider"]),
        },
        "probe": readable_probe(prompt["probe"]),
    }
    return result


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

        indicator_space = "3rem"
        with vuetify3.VRow(
            no_gutters=False,
            classes="flex-nowrap",
            style=(
                f"`display: inline-flex; min-width: 100%; "
                f"width: calc(12rem + ${{runs_to_compare.length}} * {RUN_COLUMN_MIN_WIDTH} - {indicator_space});`",
            ),
        ):
            with vuetify3.VCol(
                classes="align-self-center flex-shrink-0 flex-grow-0",
                style="width: 12rem; min-width: 12rem; max-width: 12rem;",
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
                vuetify3.VSelect(
                    label="Decider",
                    items=("runs[id].decider_items",),
                    model_value=("runs[id].prompt.decider_params.decider",),
                    update_modelValue=(
                        self.server.controller.update_run_decider,
                        r"[id, $event]",
                    ),
                    hide_details="auto",
                )

            RowWithLabel(
                run_content=run_content,
                label="Decider",
                compare_expr="runs[id].prompt.decider_params.decider",
            )


class Alignment:
    COMPARE_EXPR = "runs[id].alignment_attributes"

    class Title:
        def __init__(self):
            def run_content():
                html.Span(
                    "{{ runs[id].alignment_attributes.length ? "
                    "runs[id].alignment_attributes.map(att => `${att.title} ${att.score}`).join(' - ') : "
                    "'No Alignment' }}"
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
                    style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; width: calc(100% - 2rem);",
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

            RowWithLabel(run_content=run_content, compare_expr=SystemPrompt.COMPARE_EXPR)


class ProbeLayout:
    def __init__(self, probe):
        html.Div("Situation", classes="text-h6")
        html.P(f"{{{{{probe}.display_state}}}}", style="white-space: pre-wrap;")
        html.Div("Choices", classes="text-h6 pt-4")
        with html.Ol(classes="ml-8", type="A"):
            html.Li("{{choice.unstructured}}", v_for=(f"choice in {probe}.choices"))


class EditableProbeLayoutForRun:
    def __init__(self, server):
        ctrl = server.controller
        html.Div("Situation", classes="text-h6 pt-4")
        vuetify3.VTextarea(
            model_value=("runs[id].prompt.probe.display_state",),
            update_modelValue=(ctrl.update_run_probe_text, "[id, $event]"),
            blur=(ctrl.check_probe_edited, "[id]"),
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
                        blur=(ctrl.check_probe_edited, "[id]"),
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


class Probe:
    COMPARE_EXPR = "runs[id].prompt.probe.scenario_id + '/' + runs[id].prompt.probe.scene_id"

    class Title(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                with html.Div(
                    classes="d-flex ga-2 align-center",
                    style="width: 100%;",
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
                html.Span(
                    "{{runs[id].decision.unstructured}}", v_if=("runs[id].decision",)
                )
                with html.Template(v_else=True):
                    vuetify3.VProgressCircular(
                        v_if=("pending_cache_keys.includes(runs[id].cache_key)",),
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

            RowWithLabel(run_content=render_run_decision_text, compare_expr=Decision.COMPARE_EXPR)


class ChoiceInfo:
    COMPARE_EXPR = "runs[id].decision?.choice_info_readable"

    class Title:
        def __init__(self):
            def render_choice_info():
                html.Span(
                    "{{runs[id].decision.choice_info_readable_keys.join(', ')}}",
                    v_if=(
                        "runs[id].decision && runs[id].decision.choice_info_readable_keys",
                    ),
                )
                with html.Template(v_else=True):
                    vuetify3.VProgressCircular(
                        v_if=("pending_cache_keys.includes(runs[id].cache_key)",),
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

            RowWithLabel(run_content=render_choice_info_text, compare_expr=ChoiceInfo.COMPARE_EXPR)


class RunNumber:
    class Title(html.Template):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            def run_content():
                with vuetify3.VRow(no_gutters=True, classes="align-center"):
                    with vuetify3.VCol(classes="flex-grow-1"):
                        vuetify3.VSelect(
                            items=("Object.keys(runs).map((_, i) => i + 1)",),
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

            RowWithLabel(run_content=run_content, label="Run Number", no_runs=no_runs)


class ResultsComparison(html.Div):
    def __init__(self, **kwargs):
        super().__init__(classes="d-inline-flex flex-wrap ga-4 pa-1", **kwargs)
        with self:
            with vuetify3.VExpansionPanels(multiple=True, variant="accordion"):
                PanelSection(child=RunNumber)
                PanelSection(child=Probe)
                PanelSection(child=Decider)
                PanelSection(child=Alignment)
                PanelSection(child=SystemPrompt)
                PanelSection(child=LlmBackbone)
                PanelSection(child=Decision)
                PanelSection(child=ChoiceInfo)


class ProbePanel(vuetify3.VExpansionPanel):
    def __init__(self, probe, **kwargs):
        super().__init__(**kwargs)
        with self:
            with vuetify3.VExpansionPanelTitle():
                with html.Div(classes="text-subtitle-1 text-no-wrap text-truncate"):
                    html.Span(
                        f"{{{{{probe}.probe_id}}}} - "
                        f"{{{{{probe}.full_state.unstructured}}}}",
                    )
            with vuetify3.VExpansionPanelText():
                ProbeLayout(probe)


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
        self.title.set_text("Align App")
        self.icon.hide()
        self.footer.hide()

        with self as layout:
            with layout.toolbar:
                vuetify3.VSpacer()
                if reload:
                    with vuetify3.VBtn(icon=True, click=reload):
                        vuetify3.VIcon("mdi-refresh")
                with vuetify3.VBtn(
                    click="utils.download('align-app-runs.json', runs_json || '[]', 'application/json')",
                    disabled=("Object.keys(runs).length === 0",),
                    prepend_icon="mdi-file-download",
                ):
                    html.Span("Export Runs")
                with vuetify3.VBtn(
                    click=self.server.controller.reset_state,
                    prepend_icon="mdi-delete-sweep",
                ):
                    html.Span("Clear Runs")

            with layout.content:
                html.Div(
                    v_html=(
                        "'<style>"
                        "html { overflow: hidden !important; }"
                        ".v-textarea .v-field__input { overflow-y: hidden !important; }"
                        ".v-expansion-panel { max-width: none !important; }"
                        "</style>'"
                    )
                )
                with vuetify3.VContainer(
                    fluid=True,
                    classes="overflow-auto pa-0",
                    style="height: calc(100vh - 64px);",
                ):
                    with html.Div(
                        style="min-width: 100%; width: fit-content; padding: 16px;",
                    ):
                        ResultsComparison()
