import { migrateSource } from "./migrate";
import { classifySelector, parseSource } from "./parser";
import { SAMPLE_LOGIN } from "./samples";
import { heuristicName, toSnakeCase } from "./translator";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

const sample = migrateSource(SAMPLE_LOGIN, { sourcePath: "sample_legacy.py" });

assert(sample.locator_count === 4, `expected 4 locators, got ${sample.locator_count}`);
assert(sample.translations[0].name === "user_input", sample.translations[0].name);
assert(sample.translations[1].name === "icon_eye_button", sample.translations[1].name);
assert(sample.translations[2].name === "pwd_input", sample.translations[2].name);
assert(sample.translations[3].name === "btn_primary_button", sample.translations[3].name);
assert(sample.script.url === "https://example.com/login", sample.script.url);
assert(
  sample.script.query ===
    "{\n    user_input\n    icon_eye_button\n    pwd_input\n    btn_primary_button\n}",
  sample.script.query,
);
assert(sample.script.python_source.includes("elements.user_input.fill('demo_user')"), "fill user");
assert(sample.script.python_source.includes("elements.icon_eye_button.click()"), "click eye");
assert(sample.script.python_source.includes("elements.pwd_input.fill('s3cret!')"), "fill pwd");
assert(sample.script.python_source.includes("elements.btn_primary_button.click()"), "click submit");
assert(sample.translations[3].locator.kind === "xpath", "xpath submit");

const locators = parseSource(SAMPLE_LOGIN);
assert(locators[0].fill_value === "demo_user", "demo_user fill");
assert(locators[2].fill_value === "s3cret!", "secret fill");

assert(classifySelector("//button") === "xpath", "xpath classify");
assert(classifySelector("div.login > input") === "css", "css classify");
assert(toSnakeCase("ShowPassword") === "show_password", toSnakeCase("ShowPassword"));
assert(toSnakeCase("123go") === "el_123go", toSnakeCase("123go"));

const selenium = parseSource(`
from selenium.webdriver.common.by import By
driver.find_element(By.CSS_SELECTOR, "a.nav")
driver.find_element(By.XPATH, "//footer")
`);
assert(selenium.length === 2, `selenium ${selenium.length}`);
assert(selenium[0].kind === "css", selenium[0].kind);
assert(selenium[1].kind === "xpath", selenium[1].kind);

const direct = parseSource(`
page.fill("#user", "demo")
page.click("button.submit")
`);
assert(direct.length === 2, `direct ${direct.length}`);
assert(direct[0].selector === "#user", direct[0].selector);
assert(direct[0].fill_value === "demo", String(direct[0].fill_value));

const ignored = parseSource(`
sel = "div.x"
page.locator(sel).click()
page.click(get_selector())
`);
assert(ignored.length === 0, `ignored ${ignored.length}`);

assert(
  heuristicName({
    selector: "input[name='email']",
    kind: "css",
    interaction: "fill",
    lineno: 1,
    col_offset: 0,
    fill_value: null,
    raw_call: "fill",
  }) === "email_input",
  "email_input",
);

console.log("pipeline verify: all checks passed");
