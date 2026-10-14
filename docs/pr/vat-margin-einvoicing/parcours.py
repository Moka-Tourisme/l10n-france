"""Backoffice pair: post a customer invoice carrying a margin VAT line.

Usage: python3 parcours.py <invoice_id> <output.png>
"""
import subprocess
import sys

from playwright.sync_api import sync_playwright

DB = "zz-vatmargin-einv"
COMPOSE = ["docker", "compose", "-p", "moka16-einv"]


def base_url():
    out = subprocess.run(
        COMPOSE + ["port", "odoo16", "8069"], capture_output=True, text=True
    ).stdout.strip()
    if not out:
        raise SystemExit("odoo16 is not running in moka16-einv")
    return "http://localhost:%s" % out.rsplit(":", 1)[-1]


def main(invoice_id, out):
    url = base_url()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{url}/web/login?db={DB}")
        page.fill('input[name="login"]', "admin")
        page.fill('input[name="password"]', "admin")
        page.click('.oe_login_form button[type="submit"]')
        page.wait_for_selector(".o_main_navbar", timeout=60000)
        page.goto(f"{url}/web#id={invoice_id}&model=account.move&view_type=form")
        page.wait_for_selector(".o_form_view .o_statusbar_buttons", timeout=60000)
        page.locator('.o_statusbar_buttons button[name="action_post"]').first.click()
        # Either the error dialog or the posted state must show up.
        page.wait_for_selector(
            '.modal.d-block, .o_statusbar_status button.o_arrow_button_current[data-value="posted"]',
            timeout=30000,
        )
        page.wait_for_timeout(1000)
        page.screenshot(path=out, full_page=True)
        state = page.evaluate(
            "() => document.querySelector('.modal.d-block .modal-body')?.innerText || 'NO DIALOG'"
        )
        print(state[:600])
        browser.close()


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
