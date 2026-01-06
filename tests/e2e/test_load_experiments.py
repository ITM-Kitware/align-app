from pathlib import Path

from playwright.sync_api import expect

from .page_objects.align_page import AlignPage


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
EXPERIMENTS_ZIP = FIXTURES_DIR / ".cache" / "experiments.zip"


def test_load_experiments_menu_opens(page, align_app_server):
    """Test that the Load Experiments menu opens and shows options."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    load_button = page.get_by_role("button", name="Load Experiments", exact=True)
    expect(load_button).to_be_visible()
    load_button.click()

    from_zip_item = page.locator(".v-list-item").filter(has_text="From Zip File")
    expect(from_zip_item).to_be_visible()

    from_dir_item = page.locator(".v-list-item").filter(has_text="From Directory")
    expect(from_dir_item).to_be_visible()


def test_load_experiments_from_zip(page, align_app_server, experiments_fixtures_path):
    """Test loading experiments from a zip file adds runs to the table."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    browse_runs_button = page.get_by_role("button", name="Browse Runs")
    browse_runs_button.click()

    modal = page.locator(".v-dialog")
    expect(modal).to_be_visible()

    initial_rows = modal.locator("table tbody tr")
    expect(initial_rows.first).to_be_visible()
    initial_count = initial_rows.count()

    page.keyboard.press("Escape")
    expect(modal).not_to_be_visible()

    load_button = page.get_by_role("button", name="Load Experiments", exact=True)
    load_button.click()

    from_zip_item = page.locator(".v-list-item").filter(has_text="From Zip File")
    expect(from_zip_item).to_be_visible()

    with page.expect_file_chooser() as fc_info:
        from_zip_item.click()

    file_chooser = fc_info.value
    file_chooser.set_files(str(EXPERIMENTS_ZIP))

    page.wait_for_timeout(3000)

    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    page.get_by_role("button", name="Browse Runs").click()
    page.wait_for_selector(".v-dialog", state="visible", timeout=10000)

    final_rows = modal.locator("table tbody tr")
    expect(final_rows.first).to_be_visible()
    final_count = final_rows.count()

    assert final_count > initial_count, (
        f"Expected more rows after import. Initial: {initial_count}, Final: {final_count}"
    )
