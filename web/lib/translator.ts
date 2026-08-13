import type { Interaction, ParsedLocator, TranslatedLocator } from "./types";

const SOURCE_WEIGHTS: Record<string, number> = {
  testid: 8,
  name: 7,
  aria: 6,
  placeholder: 5,
  type: 5,
  id: 4,
  class: 2,
  tag: 0,
};

const SNAKE_RE = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/;
const NON_ALNUM = /[^a-z0-9]+/g;
const CAMEL_BOUNDARY = /([a-z0-9])([A-Z])/g;

const ATTR_PATTERNS: [string, RegExp][] = [
  ["testid", /data-testid\s*=\s*['"]([^'"]+)['"]/gi],
  ["testid", /@data-testid\s*=\s*['"]([^'"]+)['"]/gi],
  ["name", /\[name\s*=\s*['"]([^'"]+)['"]/gi],
  ["name", /@name\s*=\s*['"]([^'"]+)['"]/gi],
  ["id", /#([A-Za-z][\w-]*)/g],
  ["id", /\[id\s*=\s*['"]([^'"]+)['"]/gi],
  ["id", /@id\s*=\s*['"]([^'"]+)['"]/gi],
  ["aria", /aria-label\s*=\s*['"]([^'"]+)['"]/gi],
  ["placeholder", /placeholder\s*=\s*['"]([^'"]+)['"]/gi],
  ["type", /\[type\s*=\s*['"]([^'"]+)['"]/gi],
  ["type", /@type\s*=\s*['"]([^'"]+)['"]/gi],
];

const CLASS_PATTERN = /\.([A-Za-z][\w-]*)/g;
const XPATH_CLASS = /contains\(\s*@class\s*,\s*['"]([^'"]+)['"]\s*\)/gi;
const TAG_PATTERN = /(?:^|[/\s>+~,])([a-z][a-z0-9]*)/gi;

const NOISE_TOKENS = new Set([
  "div",
  "span",
  "ul",
  "li",
  "form",
  "body",
  "html",
  "app",
  "container",
  "wrapper",
  "main",
  "section",
  "nth",
  "child",
  "contains",
  "class",
  "btn",
  "button",
  "input",
  "icon",
  "toolbar",
  "footer",
  "header",
  "nav",
]);

const INTERACTION_SUFFIX: Record<Interaction, string> = {
  click: "button",
  fill: "input",
  type: "input",
  check: "checkbox",
  select_option: "select",
  hover: "element",
  wait_for: "element",
  other: "element",
  none: "element",
};

export function toSnakeCase(raw: string): string {
  if (!raw || !raw.trim()) return "element";
  let text = raw.trim().replace(CAMEL_BOUNDARY, "$1_$2");
  text = text.replace(/-/g, "_").replace(/ /g, "_");
  text = text.toLowerCase().replace(NON_ALNUM, "_");
  text = text.replace(/_+/g, "_").replace(/^_|_$/g, "");
  if (!text) return "element";
  if (/^\d/.test(text)) text = `el_${text}`;
  return text;
}

export function isValidAgentqlName(name: string): boolean {
  return Boolean(name) && SNAKE_RE.test(name);
}

export function ensureUnique(name: string, used: Set<string>): string {
  let candidate = isValidAgentqlName(name) ? name : toSnakeCase(name);
  if (!used.has(candidate)) {
    used.add(candidate);
    return candidate;
  }
  let suffix = 2;
  while (used.has(`${candidate}_${suffix}`)) suffix += 1;
  const unique = `${candidate}_${suffix}`;
  used.add(unique);
  return unique;
}

function tokensFromSelector(selector: string): [string, string][] {
  const tokens: [string, string][] = [];
  for (const [label, pattern] of ATTR_PATTERNS) {
    pattern.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(selector))) {
      tokens.push([label, match[1]]);
    }
  }
  CLASS_PATTERN.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = CLASS_PATTERN.exec(selector))) {
    tokens.push(["class", match[1]]);
  }
  XPATH_CLASS.lastIndex = 0;
  while ((match = XPATH_CLASS.exec(selector))) {
    tokens.push(["class", match[1]]);
  }
  TAG_PATTERN.lastIndex = 0;
  while ((match = TAG_PATTERN.exec(selector))) {
    tokens.push(["tag", match[1]]);
  }
  return tokens;
}

function scoreToken(token: string, source: string): number {
  const snake = toSnakeCase(token);
  if (!snake || NOISE_TOKENS.has(snake)) return -1;
  let score = 1 + (SOURCE_WEIGHTS[source] ?? 0);
  if (["user", "pass", "email", "login", "submit", "search", "pwd"].some((hint) => snake.includes(hint))) {
    score += 3;
  }
  if (["btn", "button", "input", "field", "link"].some((suffix) => snake.endsWith(suffix))) {
    score += 1;
  }
  if (snake.length <= 2) score -= 1;
  return score;
}

function pickStem(locator: ParsedLocator): string {
  const ranked: [number, string][] = [];
  for (const [source, token] of tokensFromSelector(locator.selector)) {
    const score = scoreToken(token, source);
    if (score < 0) continue;
    ranked.push([score, toSnakeCase(token)]);
  }
  if (ranked.length) {
    ranked.sort((a, b) => b[0] - a[0] || a[1].length - b[1].length || a[1].localeCompare(b[1]));
    return ranked[0][1];
  }
  return INTERACTION_SUFFIX[locator.interaction] ?? "element";
}

export function heuristicName(locator: ParsedLocator): string {
  const stem = pickStem(locator);
  const suffix = INTERACTION_SUFFIX[locator.interaction] ?? "element";

  if (stem === suffix || stem.endsWith(`_${suffix}`)) return stem;
  if (suffix === "button" && (stem.endsWith("_btn") || stem.endsWith("btn") || stem.endsWith("_button") || stem.endsWith("button"))) {
    return stem.endsWith("button") ? stem : toSnakeCase(stem.replace("btn", "button"));
  }
  if (suffix === "input" && ["_input", "_field", "input", "field"].some((s) => stem.endsWith(s))) {
    return stem;
  }
  return `${stem}_${suffix}`;
}

export function translateLocators(locators: ParsedLocator[]): TranslatedLocator[] {
  const used = new Set<string>();
  return locators.map((locator) => ({
    locator,
    name: ensureUnique(heuristicName(locator), used),
    source: "fallback" as const,
    rationale: "force_fallback",
  }));
}
