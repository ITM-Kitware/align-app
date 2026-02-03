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
    """Test loading experiments from a zip file adds runs to the table panel."""
    align_page = AlignPage(page)
    align_page.goto(align_app_server)

    table_panel = page.locator(".runs-table-panel")
    expect(table_panel).to_be_visible()

    def get_table_items_count():
        return page.evaluate("window.trame.state.state.runs_table_items?.length || 0")

    initial_count = get_table_items_count()

    load_button = page.get_by_role("button", name="Load Experiments", exact=True)
    load_button.click()

    from_zip_item = page.locator(".v-list-item").filter(has_text="From Zip File")
    expect(from_zip_item).to_be_visible()

    with page.expect_file_chooser() as fc_info:
        from_zip_item.click()

    file_chooser = fc_info.value
    file_chooser.set_files(str(EXPERIMENTS_ZIP))

    page.evaluate(
        """
        (async () => {
            const input = trame.refs.importFileInput.$el.querySelector('input[type="file"]');
            if (input && input.files && input.files.length > 0) {
                const file = input.files[0];
                const arrayBuffer = await file.arrayBuffer();
                const uint8Array = new Uint8Array(arrayBuffer);
                await trame.trigger('import_zip_bytes', [Array.from(uint8Array)]);
            }
        })();
        """
    )

    def wait_for_import():
        for _ in range(30):
            count = get_table_items_count()
            if count > initial_count:
                return True
            page.wait_for_timeout(500)
        return False

    wait_for_import()

    final_count = get_table_items_count()

    assert final_count > initial_count, (
        f"Expected more runs in table panel after import. Initial: {initial_count}, "
        f"Final: {final_count}"
    )
