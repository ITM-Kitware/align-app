import re

from playwright.sync_api import Page, expect

from .page_objects.align_page import AlignPage


def test_pipeline_random_decision_flow(page: Page, align_app_server: str):
    align_page = AlignPage(page)

    align_page.goto(align_app_server)

    align_page.select_decider("Pipeline Random")

    align_page.click_send_button()

    align_page.wait_for_decision()

    expect(align_page.decision_text).to_have_text(re.compile(r"^[A-Z].+"))
