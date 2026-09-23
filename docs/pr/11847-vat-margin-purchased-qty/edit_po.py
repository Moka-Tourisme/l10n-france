"""Sets one purchase line's quantity through the purchase order form.

Usage: python3 edit_po.py <purchase order id> <row index> <quantity>
"""
import sys

from playwright.sync_api import sync_playwright

URL = "http://localhost:8070"
po_id, row, qty = sys.argv[1], int(sys.argv[2]), sys.argv[3]

with sync_playwright() as p:
    page = p.chromium.launch().new_page(viewport={"width": 1400, "height": 900})
    page.goto(f"{URL}/web/login?db=test-app")
    page.fill("input[name=login]", "admin")
    page.fill("input[name=password]", "admin")
    page.click("button[type=submit]")
    page.wait_for_selector(".o_main_navbar")
    page.goto(f"{URL}/web#id={po_id}&model=purchase.order&view_type=form")
    page.wait_for_selector(".o_form_view .o_data_row")
    cell = page.locator(".o_data_row").nth(row).locator("td[name=product_qty]")
    # The cell reports itself covered by the row's sticky header: click the
    # row first to put it in edition, then the quantity input appears.
    page.locator(".o_data_row").nth(row).locator("td[name=name]").click(force=True)
    field = page.locator(".o_data_row.o_selected_row td[name=product_qty] input")
    field.wait_for()
    field.fill(qty)
    field.press("Tab")
    page.locator(".o_form_button_save:visible").click()
    page.locator(".o_form_button_save:visible").wait_for(state="hidden", timeout=15000)
    page.wait_for_timeout(1000)
    assert page.locator(".o_notification.bg-danger, .o_dialog .modal-title:has-text('Erreur')").count() == 0
    print("ROW:", page.locator(".o_data_row").nth(row).inner_text().replace("\n", " | "))
