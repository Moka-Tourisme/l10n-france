"""Point of sale pair: sell a margin VAT product and ask for an invoice.

Usage: python3 parcours_pdv.py <output.png>
"""
import sys

from playwright.sync_api import sync_playwright

from parcours import DB, base_url

PRODUCT = "Séjour découverte Alsace"
CUSTOMER = "Office de Tourisme de Colmar"


def click_when_visible(page, selector, timeout=30000):
    loc = page.locator(selector)
    for _ in range(timeout // 500):
        if loc.count() and loc.first.is_visible():
            loc.first.click()
            return
        page.wait_for_timeout(500)
    raise AssertionError(f"{selector} never became visible")


def main(out):
    url = base_url()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{url}/web/login?db={DB}")
        page.fill('input[name="login"]', "admin")
        page.fill('input[name="password"]', "admin")
        page.click('.oe_login_form button[type="submit"]')
        page.wait_for_selector(".o_main_navbar", timeout=60000)
        page.goto(f"{url}/pos/ui?config_id=1")
        page.wait_for_selector(".pos", timeout=90000)
        page.wait_for_timeout(5000)
        # Opening cash control, shown on a fresh session.
        opening = page.locator('.opening-cash-control .button:has-text("Ouvrir")')
        if opening.count() and opening.first.is_visible():
            opening.first.click()
            page.wait_for_timeout(2000)
        click_when_visible(page, f'.product:has(.product-name:text-is("{PRODUCT}"))')
        page.wait_for_timeout(500)
        assert page.locator(f'.orderline:has-text("{PRODUCT}")').count(), "line not added"
        click_when_visible(page, ".set-partner")
        click_when_visible(page, f'.partner-line:has-text("{CUSTOMER}")')
        page.wait_for_timeout(500)
        confirm = page.locator('.partnerlist-screen .button.next.highlight')
        if confirm.count() and confirm.first.is_visible():
            confirm.first.click()
        page.wait_for_timeout(1000)
        click_when_visible(page, ".pay")
        click_when_visible(page, '.paymentmethod:has-text("Espèces")')
        click_when_visible(page, ".js_invoice")
        page.wait_for_timeout(500)
        click_when_visible(page, ".button.next.validation")
        # Either an error popup or the receipt screen must show up.
        page.wait_for_selector(".popup, .receipt-screen", timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=out, full_page=True)
        print(page.evaluate(
            "() => document.querySelector('.popup')?.innerText"
            " || (document.querySelector('.receipt-screen') ? 'RECEIPT SCREEN' : 'NOTHING')"
        )[:600])
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1])
