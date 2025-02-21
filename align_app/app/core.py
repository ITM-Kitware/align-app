from trame.app import get_server
from trame.decorators import TrameApp, controller
from . import ui
from ..adm.decider import get_prompt, get_decision, readable_scenario


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

    def update_prompt(self):
        self._prompt = get_prompt()
        self.state.prompt = readable_scenario(self._prompt["scenario"])

    @controller.set("reset_state")
    def reset_state(self):
        self.update_prompt()
        self.state.output = []

    @controller.set("submit_prompt")
    def submit_prompt(self):
        decision = get_decision(self._prompt)
        readable_decision = repr(decision)
        self.state.output = [
            *self.state.output,
            readable_decision,
        ]
        self.update_prompt()

    def _build_ui(self, *args, **kwargs):
        extra_args = {}
        if self.server.hot_reload:
            ui.reload(ui)
            extra_args["reload"] = self._build_ui
        self.ui = ui.AlignLayout(self.server, **extra_args)
