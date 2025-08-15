from trame.widgets import html, vuetify3


class ValueWithProgressBar(html.Span):
    def __init__(self, value_expression, decimals=2, max_value=1, **kwargs):
        super().__init__(**kwargs)
        with self:
            vuetify3.VProgressLinear(
                model_value=(f"({value_expression} / {max_value}) * 100",),
                height="10",
                readonly=True,
                style=("display: inline-block; width: 80px;"),
            )
            html.Span(
                f"{{{{{value_expression}.toFixed({decimals})}}}}",
                style="display: inline-block; margin-left: 8px;",
            )


class NumericValue(html.Span):
    def __init__(self, value_expr, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Template(
                v_if=(
                    f"typeof {value_expr} === 'number' && {value_expr} >= 0 && {value_expr} <= 1",
                )
            ):
                ValueWithProgressBar(value_expr)
            with html.Template(v_else=True):
                html.Span(f"{{{{{value_expr}}}}}")


class ArrayValue(html.Span):
    def __init__(self, array_expr, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Template(
                v_if=(
                    f"{array_expr}.every(v => typeof v === 'number' && v >= 0 && v <= 1)",
                )
            ):
                with html.Span(
                    v_for=(f"(item, index) in {array_expr}",), key=("index",)
                ):
                    ValueWithProgressBar("item")
                    html.Span(", ", v_if=(f"index < {array_expr}.length - 1",))
            with html.Template(v_else=True):
                html.Span(f"{{{{{array_expr}.join(', ')}}}}")


class SimpleValue(html.Span):
    def __init__(self, value_expr, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Template(v_if=(f"Array.isArray({value_expr})",)):
                ArrayValue(value_expr)
            with html.Template(v_else=True):
                NumericValue(value_expr)


class NestedObjectRenderer(html.Ul):
    def __init__(self, obj_expr, **kwargs):
        super().__init__(classes="ml-4", **kwargs)
        with self:
            with html.Li(v_for=(f"[k, v] in Object.entries({obj_expr})",)):
                html.Span("{{k.charAt(0).toUpperCase() + k.slice(1)}}: ")
                SimpleValue("v")


class ObjectProperty(html.Span):
    def __init__(self, value_expr, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Template(
                v_if=(
                    f"typeof {value_expr} === 'object' && {value_expr} !== null && !Array.isArray({value_expr})",
                )
            ):
                html.Br()
                NestedObjectRenderer(value_expr)
            with html.Template(v_else_if=(f"Array.isArray({value_expr})",)):
                ArrayValue(value_expr)
            with html.Template(v_else=True):
                NumericValue(value_expr)


class UnorderedObject(html.Ul):
    def __init__(self, obj, **kwargs):
        super().__init__(**kwargs)
        with self:
            with html.Li(
                v_if=f"{obj}", v_for=(f"[key, value] in Object.entries({obj})",)
            ):
                html.Span("{{key}}: ")
                ObjectProperty("value")
            html.Div("No Object", v_else=True)
