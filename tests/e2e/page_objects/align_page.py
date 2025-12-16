from playwright.sync_api import Page, expect, Locator


class AlignPage:
    def __init__(self, page: Page):
        self.page = page

    @property
    def decider_dropdown(self) -> Locator:
        return self.page.get_by_role("button", name="Decider")

    @property
    def send_button(self) -> Locator:
        return self.page.get_by_role("button", name="Choose", exact=True)

    @property
    def spinner(self) -> Locator:
        return self.page.locator(".v-progress-circular")

    @property
    def decision_button(self) -> Locator:
        return self.page.get_by_role("button").filter(has_text="Decision")

    @property
    def decision_text(self) -> Locator:
        # Decision button structure: button > wrapper div > [Decision label, decision text]
        # Get the second child div which contains the decision result
        return self.decision_button.locator("div").first.locator("div").nth(1)

    @property
    def scenario_dropdown(self) -> Locator:
        return self.page.get_by_role("button", name="Scenario")

    @property
    def scenario_combobox(self) -> Locator:
        # Scenario combobox is inside Scenario panel, filter by "Scenario" label (not "Scene")
        return self.scenario_dropdown.get_by_role("combobox").filter(
            has_text="Scenario"
        )

    @property
    def scene_dropdown(self) -> Locator:
        # Scene combobox is inside Scenario panel, filter by "Scene" label
        return self.scenario_dropdown.get_by_role("combobox").filter(has_text="Scene")

    def get_scenario_dropdown_value(self) -> str:
        value = self.scenario_combobox.locator("input").input_value()
        if value is None:
            raise RuntimeError("Scenario dropdown value is None")
        return value

    @property
    def results_decider_dropdown(self) -> Locator:
        return self.page.get_by_role("button", name="Decider")

    @property
    def llm_button(self) -> Locator:
        return self.page.get_by_role("button", name="LLM")

    @property
    def results_llm_dropdown(self) -> Locator:
        return self.llm_button

    @property
    def decision_send_button(self) -> Locator:
        return self.page.get_by_role("button", name="Choose", exact=True)

    def goto(self, url: str) -> None:
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")
        expect(self.page.locator(".v-expansion-panels")).to_be_visible()

    def select_decider(self, decider_name: str) -> None:
        expect(self.decider_dropdown).to_be_visible()
        self.decider_dropdown.click()
        listbox = self.page.get_by_role("listbox", name="Decider-list")
        expect(listbox).to_be_visible()
        option = self.page.get_by_role("option", name=decider_name)
        expect(option).to_be_visible()
        option.click()
        expect(listbox).not_to_be_visible()

    def click_send_button(self) -> None:
        expect(self.send_button).to_be_visible()
        self.send_button.click()

    def click_and_wait_for_decision(self) -> None:
        """Click the send button and wait for the decision to appear."""
        expect(self.send_button).to_be_visible()
        self.send_button.click()
        expect(self.send_button).not_to_be_visible()

    def wait_for_decision(self) -> None:
        expect(self.send_button).not_to_be_visible()

    def get_decision_text(self) -> str:
        text = self.decision_text.text_content()
        if text is None:
            raise RuntimeError("Decision text is None")
        return text

    def is_send_button_enabled(self) -> bool:
        return self.send_button.is_enabled()

    def wait_for_spinner_to_appear(self) -> None:
        expect(self.spinner).to_be_visible()

    def wait_for_spinner_to_disappear(self) -> None:
        expect(self.spinner).not_to_be_visible()

    def select_scenario(self, scenario_id: str) -> None:
        self.scenario_dropdown.click()
        listbox = self.page.get_by_role("listbox", name="Scenario-list")
        expect(listbox).to_be_visible()
        option = self.page.get_by_role("option", name=scenario_id)
        option.click()
        expect(listbox).not_to_be_visible()

    def select_scene(self, scene_id: str) -> None:
        self.scene_dropdown.click()
        listbox = self.page.get_by_role("listbox", name="Scene-list")
        expect(listbox).to_be_visible()
        option = listbox.get_by_role("option").filter(has_text=scene_id)
        option.click()
        expect(listbox).not_to_be_visible()

    def get_scene_dropdown_value(self) -> str:
        value = self.scene_dropdown.locator("input").input_value()
        if value is None:
            raise RuntimeError("Scene dropdown value is None")
        return value

    def click_decision_send_button(self) -> None:
        self.decision_send_button.click()

    def wait_for_decision_send_button(self) -> None:
        expect(self.decision_send_button).to_be_visible()

    def select_results_decider(self, decider_name: str) -> None:
        expect(self.results_decider_dropdown).to_be_visible()
        self.results_decider_dropdown.click()
        listbox = self.page.get_by_role("listbox", name="Decider-list")
        expect(listbox).to_be_visible()
        option = self.page.get_by_role("option", name=decider_name)
        option.click()
        expect(listbox).not_to_be_visible()

    def get_results_llm_value(self) -> str:
        value = self.results_llm_dropdown.locator("input").input_value()
        if value is None:
            raise RuntimeError("LLM dropdown value is None")
        return value

    def select_results_llm(self, llm_name: str) -> None:
        expect(self.results_llm_dropdown).to_be_visible()
        self.results_llm_dropdown.click()
        listbox = self.page.get_by_role("listbox", name="LLM-list")
        expect(listbox).to_be_visible()
        option = self.page.get_by_role("option", name=llm_name)
        option.click()
        expect(listbox).not_to_be_visible()

    @property
    def scenario_panel(self) -> Locator:
        return (
            self.page.locator(".v-expansion-panel")
            .filter(has=self.page.get_by_role("button").filter(has_text="Scenario"))
            .first
        )

    @property
    def scenario_panel_title(self) -> Locator:
        return (
            self.page.get_by_role("button")
            .filter(has_text="Scenario")
            .filter(has=self.page.locator(".v-expansion-panel-title__overlay"))
        )

    @property
    def scenario_panel_content(self) -> Locator:
        return self.scenario_panel.locator(".v-expansion-panel-text")

    @property
    def situation_textarea(self) -> Locator:
        return self.scenario_panel_content.locator(
            ".v-textarea textarea:not(.v-textarea__sizer)"
        ).first

    def expand_scenario_panel(self) -> None:
        expect(self.scenario_panel_title).to_be_visible()
        is_expanded = self.scenario_panel_title.get_attribute("aria-expanded") == "true"
        if not is_expanded:
            expand_icon = self.scenario_panel_title.locator(".mdi-chevron-down")
            expand_icon.click()
        expect(self.scenario_panel_title).to_have_attribute("aria-expanded", "true")
        expect(self.scenario_panel_content).to_be_visible()

    def get_situation_text(self) -> str:
        expect(self.situation_textarea).to_be_visible()
        value = self.situation_textarea.input_value()
        return value if value else ""

    def set_situation_text(self, text: str) -> None:
        expect(self.situation_textarea).to_be_visible()
        self.situation_textarea.fill(text)

    def blur_situation_textarea(self) -> None:
        self.situation_textarea.blur()

    def get_scene_dropdown_value_from_panel(self) -> str:
        dropdown = self.scenario_panel.get_by_role("combobox").filter(has_text="Scene")
        value = dropdown.locator("input").input_value()
        return value if value else ""

    @property
    def alignment_panel_title(self) -> Locator:
        return (
            self.page.get_by_role("button")
            .filter(has_text="Alignment")
            .filter(has=self.page.locator(".v-expansion-panel-title__overlay"))
        )

    @property
    def alignment_panel_content(self) -> Locator:
        return (
            self.page.locator(".v-expansion-panel")
            .filter(has=self.page.get_by_role("button").filter(has_text="Alignment"))
            .locator(".v-expansion-panel-text")
        )

    def expand_alignment_panel(self) -> None:
        expect(self.alignment_panel_title).to_be_visible()
        is_expanded = (
            self.alignment_panel_title.get_attribute("aria-expanded") == "true"
        )
        if not is_expanded:
            self.alignment_panel_title.click()
        expect(self.alignment_panel_title).to_have_attribute("aria-expanded", "true")
        expect(self.alignment_panel_content).to_be_visible()

    @property
    def add_alignment_button(self) -> Locator:
        return self.alignment_panel_content.get_by_role("button", name="Add Alignment")

    def get_alignment_count(self) -> int:
        return self.alignment_panel_content.locator(".v-select").count()

    def get_alignment_dropdown(self, index: int = 0) -> Locator:
        return self.alignment_panel_content.locator(".v-select").nth(index)

    def get_alignment_delete_button(self, index: int = 0) -> Locator:
        return self.alignment_panel_content.locator("button:has(.mdi-delete)").nth(
            index
        )

    def click_add_alignment(self) -> None:
        expect(self.add_alignment_button).to_be_visible()
        self.add_alignment_button.click()

    def delete_alignment(self, index: int = 0) -> None:
        delete_btn = self.get_alignment_delete_button(index)
        expect(delete_btn).to_be_visible()
        delete_btn.click()

    def get_alignment_value(self, index: int = 0) -> str:
        dropdown = self.get_alignment_dropdown(index)
        value = dropdown.locator("input").input_value()
        if value is None:
            return ""
        return value

    def select_alignment(self, index: int, alignment_name: str) -> None:
        dropdown = self.get_alignment_dropdown(index)
        expect(dropdown).to_be_visible()
        dropdown.click()
        menu_item = self.page.locator(f".v-list-item:has-text('{alignment_name}')")
        expect(menu_item).to_be_visible()
        menu_item.click()

    def find_decider_in_open_list(
        self, exclude: list[str] | None = None
    ) -> tuple[Locator | None, str | None]:
        """Find a decider from the open dropdown list, excluding specified names.

        Must be called when a decider dropdown is already open.
        Returns (locator, name) tuple or (None, None) if not found.
        """
        exclude = exclude or []
        decider_items = self.page.locator(".v-list-item")
        for i in range(decider_items.count()):
            item_text = decider_items.nth(i).text_content()
            if item_text and not any(excl in item_text for excl in exclude):
                return decider_items.nth(i), item_text
        return None, None

    @property
    def decider_panel(self) -> Locator:
        return (
            self.page.locator(".v-expansion-panel")
            .filter(has=self.page.get_by_role("button").filter(has_text="Decider"))
            .first
        )

    @property
    def decider_panel_title(self) -> Locator:
        return (
            self.page.get_by_role("button")
            .filter(has_text="Decider")
            .filter(has=self.page.locator(".v-expansion-panel-title__overlay"))
        )

    @property
    def decider_panel_content(self) -> Locator:
        return self.decider_panel.locator(".v-expansion-panel-text")

    @property
    def config_textarea(self) -> Locator:
        return self.decider_panel_content.locator(
            ".config-textarea textarea:not(.v-textarea__sizer)"
        )

    def expand_decider_panel(self) -> None:
        expect(self.decider_panel_title).to_be_visible()
        is_expanded = self.decider_panel_title.get_attribute("aria-expanded") == "true"
        if not is_expanded:
            expand_icon = self.decider_panel_title.locator(".mdi-chevron-down")
            expand_icon.click()
        expect(self.decider_panel_title).to_have_attribute("aria-expanded", "true")
        expect(self.decider_panel_content).to_be_visible()

    def get_config_yaml(self) -> str:
        expect(self.config_textarea).to_be_visible()
        value = self.config_textarea.input_value()
        return value if value else ""

    def set_config_yaml(self, yaml_text: str) -> None:
        expect(self.config_textarea).to_be_visible()
        self.config_textarea.fill(yaml_text)

    def blur_config_textarea(self) -> None:
        self.config_textarea.blur()

    def get_decider_dropdown_value(self) -> str:
        dropdown = self.decider_panel.get_by_role("combobox").filter(has_text="Decider")
        value = dropdown.locator("input").input_value()
        return value if value else ""
