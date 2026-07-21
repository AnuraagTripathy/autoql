"""
Dummy legacy Playwright script with brittle CSS/XPath locators.

Used as the end-to-end fixture for the Legacy-to-AgentQL Migrator.
The AST parser (`parser.py`) should discover four locator call sites below.
"""

from playwright.sync_api import sync_playwright


def run_legacy_login_flow() -> None:
    """Simulate a fragile selector-heavy login workflow."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://example.com/login")

        # Brittle nested CSS path for the username field
        page.locator("div#app > div.container > form.login-form > input[name='user']").fill(
            "demo_user"
        )

        # Deeply nested list-item button for password visibility toggle
        page.locator("div > ul.toolbar > li:nth-child(2) > button.icon-eye").click()

        # Complex attribute selector for the password input
        page.locator("form[action='/auth/login'] input[type='password'][data-testid='pwd']").fill(
            "s3cret!"
        )

        # XPath-style fragile submit control
        page.locator("//div[@id='footer']//button[contains(@class, 'btn-primary')]").click()

        browser.close()


if __name__ == "__main__":
    run_legacy_login_flow()
