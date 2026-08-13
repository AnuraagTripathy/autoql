import { isValidAgentqlName } from "./translator";
import type {
  GeneratedAction,
  GeneratedScript,
  Interaction,
  TranslatedLocator,
} from "./types";

export const DEFAULT_URL = "https://example.com";
export const DEFAULT_FUNCTION_NAME = "run_migrated_flow";

const INTERACTION_METHODS: Partial<Record<Interaction, string>> = {
  click: "click",
  fill: "fill",
  type: "type",
  check: "check",
  select_option: "select_option",
  hover: "hover",
  wait_for: "wait_for",
};

const VALUE_INTERACTIONS = new Set<Interaction>(["fill", "type", "select_option"]);

export function pythonRepr(value: string): string {
  const escaped = value
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/\r/g, "\\r")
    .replace(/\t/g, "\\t");
  if (escaped.includes("'") && !escaped.includes('"')) {
    return `"${escaped.replace(/"/g, '\\"')}"`;
  }
  return `'${escaped.replace(/'/g, "\\'")}'`;
}

export function buildAgentqlQuery(translations: TranslatedLocator[]): string {
  const seen = new Set<string>();
  const fields: string[] = [];
  for (const item of translations) {
    const name = item.name.trim();
    if (!name || seen.has(name) || !isValidAgentqlName(name)) continue;
    seen.add(name);
    fields.push(name);
  }
  if (!fields.length) return "{\n}";
  return "{\n" + fields.map((name) => `    ${name}`).join("\n") + "\n}";
}

export function actionStatement(
  action: GeneratedAction,
  responseVar = "elements",
): string {
  const method = INTERACTION_METHODS[action.interaction];
  const target = `${responseVar}.${action.name}`;
  if (!method) {
    return `# skip ${action.name}: unsupported interaction ${pythonRepr(action.interaction)}`;
  }
  if (VALUE_INTERACTIONS.has(action.interaction)) {
    return `${target}.${method}(${pythonRepr(action.fill_value || "")})`;
  }
  return `${target}.${method}()`;
}

export function fieldNames(translations: TranslatedLocator[]): string[] {
  return buildAgentqlQuery(translations)
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && line !== "{" && line !== "}");
}

export function translationsToActions(
  translations: TranslatedLocator[],
): GeneratedAction[] {
  return translations
    .filter((item) => isValidAgentqlName(item.name))
    .map((item) => ({
      name: item.name,
      interaction: item.locator.interaction,
      fill_value: item.locator.fill_value,
      source_lineno: item.locator.lineno,
    }));
}

function renderPythonModule(opts: {
  query: string;
  actions: GeneratedAction[];
  url: string;
  functionName: string;
  headless: boolean;
  sourcePath: string | null;
}): string {
  const origin = opts.sourcePath || "legacy script";
  const queryLiteral = `"""\n${opts.query}\n"""`;
  const actionLines = opts.actions.map((action) => `        ${actionStatement(action)}`);
  const actionsBlock = actionLines.length
    ? actionLines.join("\n")
    : "        pass  # no interactions discovered";

  return `"""
Auto-generated AgentQL migration of ${origin}.

Regenerate with \`\`python generator.py\`\` — do not hand-edit locators here.
Requires AGENTQL_API_KEY (see .env.example).
"""

import agentql
from playwright.sync_api import sync_playwright

QUERY = ${queryLiteral}


def ${opts.functionName}() -> None:
    """Run the migrated flow with semantic AgentQL selectors."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=${opts.headless ? "True" : "False"})
        page = agentql.wrap(browser.new_page())
        page.goto(${pythonRepr(opts.url)})

        elements = page.query_elements(QUERY)
${actionsBlock}

        browser.close()


if __name__ == "__main__":
    ${opts.functionName}()
`;
}

export function generateScript(
  translations: TranslatedLocator[],
  opts: {
    url?: string;
    functionName?: string;
    headless?: boolean;
    sourcePath?: string | null;
  } = {},
): GeneratedScript {
  const url = opts.url ?? DEFAULT_URL;
  const query = buildAgentqlQuery(translations);
  const names = fieldNames(translations);
  const actions = translationsToActions(translations);
  const python_source = renderPythonModule({
    query,
    actions,
    url,
    functionName: opts.functionName ?? DEFAULT_FUNCTION_NAME,
    headless: opts.headless ?? true,
    sourcePath: opts.sourcePath ?? null,
  });
  return {
    query,
    python_source,
    url,
    field_names: names,
    actions,
    source_path: opts.sourcePath ?? null,
  };
}
