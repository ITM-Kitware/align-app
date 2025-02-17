from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


class AlignLayout(SinglePageLayout):
    def __init__(
        self,
        server,
        reload=None,
        **kwargs,
    ):
        super().__init__(server, **kwargs)

        self.state.trame__title = "align-app"

        with SinglePageLayout(self.server) as layout:
            # Toolbar
            layout.title.set_text("Align App")
            with layout.toolbar:
                vuetify3.VSpacer()
                if reload:
                    with vuetify3.VBtn(icon=True, click=reload):
                        vuetify3.VIcon("mdi-refresh")
                with vuetify3.VBtn(icon=True, click=self.controller.reset_state):
                    vuetify3.VIcon("mdi-undo")

            # Main content
            with layout.content:
                with vuetify3.VContainer(fluid=True, classes="fill-height"):
                    with vuetify3.VCol(
                        cols=12, classes="d-flex flex-column fill-height"
                    ):
                        with html.Div(classes="flex-grow-1"):
                            with html.Div(
                                classes="flex-grow-1",
                                v_for=("chat in output",),
                                key="output",
                            ):
                                html.Div("{{chat}}")
                        with html.Div(classes="mt-auto"):
                            with vuetify3.VCard():
                                with vuetify3.VCardText():
                                    vuetify3.VTextarea(
                                        v_model=("prompt",),
                                        placeholder="Enter prompt",
                                        variant="underlined",
                                        auto_grow=True,
                                        max_rows=10,
                                        hide_details="auto",
                                    )
                                with vuetify3.VCardActions():
                                    with vuetify3.VBtn(
                                        click=self.controller.submit_prompt
                                    ):
                                        vuetify3.VIcon("mdi-send")
