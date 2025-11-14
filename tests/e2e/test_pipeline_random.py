from playwright.sync_api import Page

from .page_objects.align_page import AlignPage


def test_pipeline_random_decision_flow(page: Page, align_app_server: str):
    align_page = AlignPage(page)

    align_page.goto(align_app_server)

    align_page.select_decider("Pipeline Random")

    align_page.click_send_button()

    align_page.wait_for_decision(timeout=60000)

    decision_text = align_page.get_decision_text()
    assert decision_text is not None
    assert len(decision_text) > 0
    assert decision_text[0].isupper()
