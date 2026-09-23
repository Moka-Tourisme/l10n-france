"""Replays task 11847: the purchase order quantity and the quotation.

Usage: python3 parcours.py <avant|apres> <sale order id> <purchase order id>
Captures the quotation lines (quantity, margin, taxes) and the purchase order.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8070"
phase, so_id, po_id = sys.argv[1], sys.argv[2], sys.argv[3]
out = Path(__file__).parent

with sync_playwright() as p:
    page = p.chromium.launch().new_page(viewport={"width": 1400, "height": 900})
    page.goto(f"{URL}/web/login?db=test-app")
    page.fill("input[name=login]", "admin")
    page.fill("input[name=password]", "admin")
    page.click("button[type=submit]")
    page.wait_for_selector(".o_main_navbar")
    page.goto(f"{URL}/web#id={po_id}&model=purchase.order&view_type=form")
    page.wait_for_selector(".o_form_view .o_data_row")
    page.wait_for_timeout(800)
    page.screenshot(path=str(out / f"achat-{phase}.png"))
    # A draft purchase order is shared by every sale to the same supplier:
    # print each line with its origin.
    for row in page.locator(".o_data_row").all():
        print("ACHAT:", row.inner_text().replace("\n", " | "))
    page.goto(f"{URL}/web#id={so_id}&model=sale.order&view_type=form")
    page.wait_for_selector(".o_form_view .o_data_row")
    page.wait_for_timeout(800)
    page.screenshot(path=str(out / f"devis-{phase}.png"), full_page=True)
    print("DEVIS:", page.locator(".o_data_row").first.inner_text().replace("\n", " | "))
    print("TOTAUX:", page.locator(".oe_subtotal_footer, .o_tax_totals").first.inner_text().replace("\n", " | "))
