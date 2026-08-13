export const SAMPLE_LOGIN = `"""
Dummy legacy Playwright script with brittle CSS/XPath locators.

Used as the end-to-end fixture for the Legacy-to-AgentQL Migrator.
The AST parser (\`parser.py\`) should discover four locator call sites below.
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
`;

export const SAMPLE_CHECKOUT = `from playwright.sync_api import sync_playwright


def run_legacy_checkout() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://shop.example/checkout")

        page.locator("#email-field").fill("ada@example.com")
        page.locator("button[data-testid='apply-coupon']").click()
        page.fill("input[name='cardNumber']", "4242424242424242")
        page.locator("//button[contains(@class, 'btn-pay')]").click()

        browser.close()
`;

export const SAMPLE_SELENIUM = `from selenium.webdriver.common.by import By


def search_legacy(driver) -> None:
    driver.get("https://example.com/search")
    driver.find_element(By.CSS_SELECTOR, "input[name='q']")
    driver.find_element(By.XPATH, "//button[@type='submit']")
    page = driver  # mixed-style suites still happen
    page.click("a.nav-login")
`;

export const SAMPLES = [
  {
    id: "login",
    label: "Login fixture",
    filename: "sample_legacy.py",
    source: SAMPLE_LOGIN,
  },
  {
    id: "checkout",
    label: "Checkout flow",
    filename: "checkout_legacy.py",
    source: SAMPLE_CHECKOUT,
  },
  {
    id: "selenium",
    label: "Selenium mix",
    filename: "selenium_legacy.py",
    source: SAMPLE_SELENIUM,
  },
] as const;
