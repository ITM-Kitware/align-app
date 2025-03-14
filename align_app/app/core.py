from trame.app import get_server, asynchronous
from trame.decorators import TrameApp, controller
from . import ui
from ..adm.adm_core import serialize_prompt, Prompt
from ..adm.decider import get_decision
from .prompt import PromptController
from ..utils.utils import get_id, readable


def prep_for_state(prompt: Prompt):
    p = serialize_prompt(prompt)
    p["alignment_targets"] = [
        {
            **a,
            "id": readable(a["id"]),
        }
        for a in p["alignment_targets"]
    ]
    p["decider_params"]["decider"] = readable(p["decider_params"]["decider"])
    return p


@TrameApp()
class AlignApp:
    def __init__(self, server=None):
        self.server = get_server(server, client_type="vue3")
        self._promptController = PromptController(self.server)
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
        self._promptController.reset()
        self.state.output = []

    async def make_decision(self):
        prompt = self._promptController.get_prompt()
        run_id = get_id()
        run = {"id": run_id, "prompt": prep_for_state(prompt)}
        with self.state:
            self.state.output = [
                *self.state.output,
                run,
            ]
        await self.server.network_completion  # let spinner be shown

        decision = await get_decision(prompt)

        with self.state:
            self.state.output = [
                {**item, "decision": decision} if item.get("id") == run_id else item
                for item in self.state.output
            ]

    @controller.set("submit_prompt")
    def submit_prompt(self):
        asynchronous.create_task(self.make_decision())

    def _build_ui(self, *args, **kwargs):
        extra_args = {}
        if self.server.hot_reload:
            ui.reload(ui)
            extra_args["reload"] = self._build_ui
        self.ui = ui.AlignLayout(self.server, **extra_args)
