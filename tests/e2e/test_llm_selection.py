from playwright.sync_api import Page

from .page_objects.align_page import AlignPage


def test_llm_auto_selection_on_decider_change(page: Page, align_app_server: str):
    """Test that LLM is auto-selected when switching deciders.

    Scenario: When switching from pipeline_random (no LLMs) back to an LLM-using
    decider, it should auto-select the first LLM in the list.
    """
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    align_page.select_decider("Pipeline Baseline")
    align_page.click_send_button()
    align_page.wait_for_decision()

    page.get_by_role("button").filter(has_text="Scenario").click()

    initial_llm = align_page.get_results_llm_value()
    assert "mistralai" in initial_llm or "llama" in initial_llm, (
        f"Expected initial LLM to be from LLM_BACKBONES, got: {initial_llm}"
    )

    align_page.select_results_llm("mistralai/Mistral-7B-Instruct-v0.2")
    page.wait_for_timeout(500)

    current_llm = align_page.get_results_llm_value()
    assert "Mistral-7B-Instruct-v0.2" in current_llm, (
        f"Expected LLM to be Mistral-7B-Instruct-v0.2, got: {current_llm}"
    )

    align_page.results_decider_dropdown.click()
    page.wait_for_selector(".v-list-item", state="visible")
    pipeline_random = page.locator(".v-list-item").filter(has_text="pipeline_random")
    pipeline_random.click()
    page.wait_for_timeout(500)

    random_llm = align_page.get_results_llm_value()
    assert random_llm == "N/A", f"Expected N/A for pipeline_random, got: {random_llm}"

    align_page.results_decider_dropdown.click()
    page.wait_for_selector(".v-list-item", state="visible")
    baseline = page.locator(".v-list-item").filter(has_text="pipeline_baseline")
    baseline.click()
    page.wait_for_timeout(500)

    final_llm = align_page.get_results_llm_value()
    assert "mistralai/Mistral-7B-Instruct-v0.3" in final_llm, (
        f"Expected first LLM (Mistral-7B-Instruct-v0.3) after switching from N/A, got: {final_llm}"
    )


def test_llm_preserved_when_available_in_new_decider(
    page: Page, align_app_server: str
):
    """Test that LLM is preserved when switching between deciders with same LLM list."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    align_page.select_decider("Pipeline Baseline")
    align_page.click_send_button()
    align_page.wait_for_decision()

    page.get_by_role("button").filter(has_text="Scenario").click()

    align_page.select_results_llm("meta-llama/Llama-3.3-70B-Instruct")
    page.wait_for_timeout(500)

    selected_llm = align_page.get_results_llm_value()
    assert "Llama-3.3-70B-Instruct" in selected_llm, (
        f"Expected Llama-3.3-70B-Instruct, got: {selected_llm}"
    )

    align_page.results_decider_dropdown.click()
    page.wait_for_selector(".v-list-item", state="visible")

    decider_items = page.locator(".v-list-item")
    non_baseline_llm_decider = None
    for i in range(decider_items.count()):
        item_text = decider_items.nth(i).text_content()
        if (
            item_text
            and "pipeline_baseline" not in item_text
            and "pipeline_random" not in item_text
        ):
            non_baseline_llm_decider = decider_items.nth(i)
            break

    assert non_baseline_llm_decider is not None, (
        "Test requires at least one non-baseline, non-random decider"
    )

    non_baseline_llm_decider.click()
    page.wait_for_timeout(500)

    preserved_llm = align_page.get_results_llm_value()
    assert "Llama-3.3-70B-Instruct" in preserved_llm, (
        f"Expected LLM to be preserved as Llama-3.3-70B-Instruct, got: {preserved_llm}"
    )
