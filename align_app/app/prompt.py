from trame.decorators import TrameApp, change
from ..adm import adm_core


@TrameApp()
class PromptController:
    def __init__(self, server):
        self.server = server
        self.reset()

    def update_scenarios(self):
        scenarios = adm_core.get_scenarios()
        items = [
            {"value": id, "title": f"{id} - {s['state']}"}
            for id, s in scenarios.items()
        ]
        self.server.state.scenarios = items
        self.server.state.prompt_scenario_id = self.server.state.scenarios[0]["value"]

    def reset(self):
        self.update_scenarios()

    @change("prompt_scenario_id")
    def on_scenario_change(self, prompt_scenario_id, **kwargs):
        s = adm_core.get_scenarios()[prompt_scenario_id]
        self.server.state.prompt_scenario = s

    def get_prompt(self):
        return adm_core.get_prompt(self.server.state.prompt_scenario_id)
