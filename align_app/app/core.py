from trame.app import get_server
from trame.decorators import TrameApp, controller
from . import ui
from ..adm.decider import get_decision


@TrameApp()
class AlignApp:
    def __init__(self, server=None):
        self.server = get_server(server, client_type="vue3")
        if self.server.hot_reload:
            self.server.controller.on_server_reload.add(self._build_ui)
        self._build_ui()

        self.reset_state()

    @property
    def state(self):
        return self.server.state

    @property
    def ctrl(self):
        return self.server.controller

    @controller.set("reset_state")
    def reset_state(self):
        self.state.prompt = ""
        self.state.output = []

    @controller.set("submit_prompt")
    def submit_prompt(self):
        decision = get_decision(self.state.prompt)
        self.state.output = self.state.output = [
            *self.state.output,
            decision,
        ]
        self.state.prompt = ""

    def _build_ui(self, *args, **kwargs):
        extra_args = {}
        if self.server.hot_reload:
            ui.reload(ui)
            extra_args["reload"] = self._build_ui
        self.ui = ui.AlignLayout(self.server, **extra_args)
