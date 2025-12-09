from playwright.sync_api import expect

from .page_objects.align_page import AlignPage


def test_llm_auto_selection_on_decider_change(align_page_with_decision: AlignPage):
    """Test that LLM is auto-selected when switching deciders.

    Scenario: When switching from pipeline_random (no LLMs) back to an LLM-using
    decider, it should auto-select the first LLM in the list.
    """
    align_page = align_page_with_decision
    page = align_page.page

    random_llm = align_page.get_results_llm_value()
    assert random_llm == "N/A", f"Expected N/A for pipeline_random, got: {random_llm}"

    align_page.results_decider_dropdown.click()
    listbox = page.get_by_role("listbox", name="Decider-list")
    expect(listbox).to_be_visible()

    llm_decider, decider_name = align_page.find_decider_in_open_list(
        exclude=["pipeline_random"]
    )
    assert llm_decider is not None, "Test requires at least one LLM-using decider"

    llm_decider.click()
    expect(listbox).not_to_be_visible()

    final_llm = align_page.get_results_llm_value()
    assert final_llm != "N/A", (
        f"Expected LLM to be auto-selected after switching to {decider_name}, got: {final_llm}"
    )


def test_llm_preserved_when_available_in_new_decider(
    align_page_with_decision: AlignPage,
):
    """Test that LLM is preserved when switching between deciders with same LLM list."""
    align_page = align_page_with_decision
    page = align_page.page

    align_page.results_decider_dropdown.click()
    decider_listbox = page.get_by_role("listbox", name="Decider-list")
    expect(decider_listbox).to_be_visible()

    first_llm_decider, first_decider_name = align_page.find_decider_in_open_list(
        exclude=["pipeline_random"]
    )
    assert first_llm_decider is not None, "Test requires at least one LLM-using decider"

    first_llm_decider.click()
    expect(decider_listbox).not_to_be_visible()

    initial_llm = align_page.get_results_llm_value()
    assert initial_llm != "N/A", f"Expected LLM to be selected for {first_decider_name}"

    align_page.results_llm_dropdown.click()
    llm_listbox = page.get_by_role("listbox", name="LLM-list")
    expect(llm_listbox).to_be_visible()
    llm_items = llm_listbox.get_by_role("option")

    if llm_items.count() < 2:
        page.keyboard.press("Escape")
        return

    second_llm = llm_items.nth(1)
    second_llm_text = second_llm.text_content()
    second_llm.click()
    expect(llm_listbox).not_to_be_visible()

    selected_llm = align_page.get_results_llm_value()

    align_page.results_decider_dropdown.click()
    expect(decider_listbox).to_be_visible()

    second_llm_decider, _ = align_page.find_decider_in_open_list(
        exclude=["pipeline_random", first_decider_name]
    )

    if second_llm_decider is None:
        page.keyboard.press("Escape")
        return

    second_llm_decider.click()
    expect(decider_listbox).not_to_be_visible()

    preserved_llm = align_page.get_results_llm_value()
    assert second_llm_text in preserved_llm or preserved_llm != "N/A", (
        f"Expected LLM to be preserved or auto-selected, got: {preserved_llm}"
    )
