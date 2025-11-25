from playwright.sync_api import Page, expect

from .page_objects.align_page import AlignPage

ALIGNMENT_DECIDER = "phase2_pipeline_zeroshot_comparative_regression"


def _setup_with_alignment_decider(align_page: AlignPage, page: Page):
    """Start with pipeline_random then switch to alignment decider."""
    align_page.select_decider("Pipeline Random")
    align_page.click_send_button()
    align_page.wait_for_decision()

    page.get_by_role("button").filter(has_text="Scenario").first.click()
    align_page.select_results_decider(ALIGNMENT_DECIDER)


def test_add_alignment_attribute(page: Page, align_app_server: str):
    """Test adding an alignment attribute in results comparison."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    _setup_with_alignment_decider(align_page, page)

    align_page.expand_alignment_panel()

    initial_count = align_page.get_alignment_count()
    assert initial_count == 0, f"Expected 0 alignments initially, got {initial_count}"

    expect(align_page.add_alignment_button).to_be_visible()
    align_page.click_add_alignment()

    align_page.expand_alignment_panel()
    first_dropdown = align_page.get_alignment_dropdown(0)
    expect(first_dropdown).to_be_visible()

    first_value = align_page.get_alignment_value(0)
    assert first_value, "First alignment should have a value"


def test_delete_alignment_attribute(page: Page, align_app_server: str):
    """Test deleting an alignment attribute in results comparison."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    _setup_with_alignment_decider(align_page, page)

    align_page.expand_alignment_panel()
    align_page.click_add_alignment()

    align_page.expand_alignment_panel()
    first_dropdown = align_page.get_alignment_dropdown(0)
    expect(first_dropdown).to_be_visible()

    delete_btn = align_page.get_alignment_delete_button(0)
    expect(delete_btn).to_be_visible()
    delete_btn.click()

    align_page.expand_alignment_panel()
    expect(align_page.add_alignment_button).to_be_visible()


def test_add_multiple_alignment_attributes(page: Page, align_app_server: str):
    """Test adding multiple alignment attributes."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    _setup_with_alignment_decider(align_page, page)

    align_page.expand_alignment_panel()
    align_page.click_add_alignment()

    align_page.expand_alignment_panel()
    expect(align_page.get_alignment_dropdown(0)).to_be_visible()
    align_page.click_add_alignment()

    align_page.expand_alignment_panel()
    expect(align_page.get_alignment_dropdown(1)).to_be_visible()

    count = align_page.get_alignment_count()
    assert count == 2, f"Expected 2 alignments, got {count}"

    first_value = align_page.get_alignment_value(0)
    second_value = align_page.get_alignment_value(1)
    assert first_value != second_value, (
        f"Different alignments should have different values: {first_value} vs {second_value}"
    )


def test_change_alignment_attribute_value(page: Page, align_app_server: str):
    """Test changing alignment attribute KDMA type."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    _setup_with_alignment_decider(align_page, page)

    align_page.expand_alignment_panel()
    align_page.click_add_alignment()

    align_page.expand_alignment_panel()
    initial_value = align_page.get_alignment_value(0)

    dropdown = align_page.get_alignment_dropdown(0)
    dropdown.click()

    listbox = page.get_by_role("listbox", name="Alignment-list")
    expect(listbox).to_be_visible()

    options = listbox.get_by_role("option")
    option_count = options.count()
    assert option_count > 0, "Alignment dropdown should have options"

    first_option = options.first
    first_option_text = first_option.text_content()
    assert first_option_text, "First option should have text"
    first_option.click()

    page.wait_for_timeout(500)

    align_page.expand_alignment_panel()
    expect(align_page.get_alignment_dropdown(0)).to_be_visible()
    updated_value = align_page.get_alignment_value(0)
    assert updated_value != initial_value, (
        f"Expected value to change from {initial_value} to {first_option_text}, got {updated_value}"
    )
