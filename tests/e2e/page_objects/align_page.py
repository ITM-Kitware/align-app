from playwright.sync_api import Page, expect


class AlignPage:
    def __init__(self, page: Page):
        self.page = page

    def goto(self, url: str):
        self.page.goto(url)
        self.page.wait_for_load_state("domcontentloaded")

    def select_decider(self, decider_name: str):
        decider_dropdown = self.page.locator("label:has-text('Decider')").locator("..")
        decider_dropdown.click()
        self.page.locator(f".v-list-item:has-text('{decider_name}')").click()

    def click_send_button(self):
        send_button = self.page.locator("button:has(i.mdi-send)")
        send_button.click()

    def wait_for_decision(self, timeout: int = 30000):
        self.page.wait_for_selector(
            "text=/^[A-Z]\\./", timeout=timeout, state="visible"
        )

    def get_decision_text(self) -> str:
        decision_element = self.page.locator("text=/^[A-Z]\\./").first
        return decision_element.text_content()

    def is_send_button_enabled(self) -> bool:
        send_button = self.page.locator("button:has(i.mdi-send)")
        return send_button.is_enabled()

    def wait_for_spinner_to_appear(self):
        spinner = self.page.locator(".v-progress-circular")
        expect(spinner).to_be_visible(timeout=5000)

    def wait_for_spinner_to_disappear(self, timeout: int = 30000):
        spinner = self.page.locator(".v-progress-circular")
        expect(spinner).not_to_be_visible(timeout=timeout)
