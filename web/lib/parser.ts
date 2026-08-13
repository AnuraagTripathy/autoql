import type { Interaction, LocatorKind, ParsedLocator } from "./types";

const INTERACTION_MAP: Record<string, Interaction> = {
  click: "click",
  fill: "fill",
  type: "type",
  check: "check",
  select_option: "select_option",
  hover: "hover",
  wait_for: "wait_for",
};

const LOCATOR_BUILDERS = new Set(["locator", "query_selector", "query_selector_all"]);
const FIND_ELEMENT_METHODS = new Set(["find_element", "find_elements"]);
const XPATH_PREFIX = /^\s*(\/\/|\(\s*\.?\/|\.\/)/;

type Token =
  | { kind: "ident"; value: string; index: number }
  | { kind: "string"; value: string; index: number }
  | { kind: "lparen"; index: number }
  | { kind: "rparen"; index: number }
  | { kind: "comma"; index: number }
  | { kind: "dot"; index: number };

export function classifySelector(selector: string): LocatorKind {
  if (!selector || !selector.trim()) return "unknown";
  const stripped = selector.trimStart();
  if (stripped.startsWith("xpath=") || XPATH_PREFIX.test(selector)) return "xpath";
  if (stripped.startsWith("/") && !stripped.startsWith("//")) return "xpath";
  return "css";
}

function posAt(source: string, index: number): { lineno: number; col_offset: number } {
  let lineno = 1;
  let lineStart = 0;
  for (let i = 0; i < index; i++) {
    if (source[i] === "\n") {
      lineno += 1;
      lineStart = i + 1;
    }
  }
  return { lineno, col_offset: index - lineStart };
}

function callStartIndex(source: string, identIndex: number): number {
  let i = identIndex;
  while (i > 0) {
    const prev = i - 1;
    if (source[prev] === ".") {
      i = prev;
      while (i > 0 && /[A-Za-z0-9_]/.test(source[i - 1])) i -= 1;
      continue;
    }
    break;
  }
  return i;
}

function tokenize(source: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;

  const push = (token: Token) => tokens.push(token);

  while (i < source.length) {
    const ch = source[i];

    if (ch === "#") {
      while (i < source.length && source[i] !== "\n") i += 1;
      continue;
    }

    if (ch === " " || ch === "\t" || ch === "\n" || ch === "\r") {
      i += 1;
      continue;
    }

    if (ch === "(") {
      push({ kind: "lparen", index: i });
      i += 1;
      continue;
    }
    if (ch === ")") {
      push({ kind: "rparen", index: i });
      i += 1;
      continue;
    }
    if (ch === ",") {
      push({ kind: "comma", index: i });
      i += 1;
      continue;
    }
    if (ch === ".") {
      push({ kind: "dot", index: i });
      i += 1;
      continue;
    }

    if (ch === "'" || ch === '"') {
      const extracted = readPythonString(source, i);
      if (extracted) {
        push({ kind: "string", value: extracted.value, index: i });
        i = extracted.end;
        continue;
      }
    }

    if (/[A-Za-z_]/.test(ch)) {
      const start = i;
      i += 1;
      while (i < source.length && /[A-Za-z0-9_]/.test(source[i])) i += 1;
      push({ kind: "ident", value: source.slice(start, i), index: start });
      continue;
    }

    i += 1;
  }

  return tokens;
}

function readPythonString(
  source: string,
  start: number,
): { value: string; end: number } | null {
  const quote = source[start];
  if (quote !== "'" && quote !== '"') return null;
  const triple = source.slice(start, start + 3) === quote.repeat(3);
  const delim = triple ? quote.repeat(3) : quote;
  let i = start + delim.length;
  let value = "";

  while (i < source.length) {
    if (source.slice(i, i + delim.length) === delim) {
      return { value, end: i + delim.length };
    }
    if (source[i] === "\\") {
      const next = source[i + 1];
      const escapes: Record<string, string> = {
        n: "\n",
        t: "\t",
        r: "\r",
        "\\": "\\",
        "'": "'",
        '"': '"',
      };
      value += next in escapes ? escapes[next] : (next ?? "");
      i += 2;
      continue;
    }
    value += source[i];
    i += 1;
  }
  return null;
}

function consumeCallArgs(
  tokens: Token[],
  openIndex: number,
): { args: Token[]; end: number } | null {
  if (tokens[openIndex]?.kind !== "lparen") return null;
  const args: Token[] = [];
  let depth = 1;
  let i = openIndex + 1;
  let current: Token | null = null;

  while (i < tokens.length && depth > 0) {
    const tok = tokens[i];
    if (tok.kind === "lparen") {
      depth += 1;
    } else if (tok.kind === "rparen") {
      depth -= 1;
      if (depth === 0) {
        if (current && depth === 0) args.push(current);
        return { args, end: i };
      }
    } else if (tok.kind === "comma" && depth === 1) {
      if (current) args.push(current);
      current = null;
    } else if (depth === 1 && current === null) {
      current = tok;
    }
    i += 1;
  }
  return null;
}

function dottedIdent(tokens: Token[], index: number): string {
  const parts: string[] = [];
  let i = index;
  while (i < tokens.length) {
    const tok = tokens[i];
    if (tok.kind === "ident") {
      parts.push(tok.value);
      const next = tokens[i + 1];
      const after = tokens[i + 2];
      if (next?.kind === "dot" && after?.kind === "ident") {
        i += 2;
        continue;
      }
      break;
    }
    break;
  }
  return parts.join(".");
}

function kindFromByStrategy(strategy: string, selector: string): LocatorKind {
  const name = strategy.toUpperCase();
  if (name.includes("XPATH")) return "xpath";
  if (["CSS", "ID", "NAME", "CLASS", "TAG"].some((token) => name.includes(token))) {
    return "css";
  }
  return classifySelector(selector);
}

export function parseSource(source: string): ParsedLocator[] {
  const tokens = tokenize(source);
  const locators: ParsedLocator[] = [];
  const handledActionAt = new Set<number>();

  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i];
    if (tok.kind !== "ident") continue;

    if (LOCATOR_BUILDERS.has(tok.value) && tokens[i + 1]?.kind === "lparen") {
      const call = consumeCallArgs(tokens, i + 1);
      if (!call) continue;
      const selectorTok = call.args[0];
      if (!selectorTok || selectorTok.kind !== "string") continue;

      let j = call.end + 1;
      if (tokens[j]?.kind === "dot") j += 1;
      const actionTok = tokens[j];
      if (!actionTok || actionTok.kind !== "ident") continue;
      const interaction = INTERACTION_MAP[actionTok.value];
      if (!interaction) continue;
      if (tokens[j + 1]?.kind !== "lparen") continue;

      const actionCall = consumeCallArgs(tokens, j + 1);
      let fillValue: string | null = null;
      if (
        actionCall &&
        (interaction === "fill" || interaction === "type") &&
        actionCall.args[0]?.kind === "string"
      ) {
        fillValue = actionCall.args[0].value;
      }

      const start = callStartIndex(source, tok.index);
      const pos = posAt(source, start);
      locators.push({
        selector: selectorTok.value,
        kind: classifySelector(selectorTok.value),
        interaction,
        lineno: pos.lineno,
        col_offset: pos.col_offset,
        fill_value: fillValue,
        raw_call: actionTok.value,
      });
      handledActionAt.add(actionTok.index);
      continue;
    }

    if (FIND_ELEMENT_METHODS.has(tok.value) && tokens[i + 1]?.kind === "lparen") {
      const call = consumeCallArgs(tokens, i + 1);
      if (!call || call.args.length < 2) continue;
      const selectorTok = call.args[1];
      if (selectorTok.kind !== "string") continue;
      const strategyIndex = tokens.findIndex(
        (candidate, idx) => idx > i && candidate === call.args[0],
      );
      const strategy = dottedIdent(tokens, strategyIndex === -1 ? i : strategyIndex);
      const start = callStartIndex(source, tok.index);
      const pos = posAt(source, start);
      locators.push({
        selector: selectorTok.value,
        kind: kindFromByStrategy(strategy, selectorTok.value),
        interaction: "none",
        lineno: pos.lineno,
        col_offset: pos.col_offset,
        fill_value: null,
        raw_call: tok.value,
      });
      continue;
    }

    const interaction = INTERACTION_MAP[tok.value];
    if (!interaction) continue;
    if (handledActionAt.has(tok.index)) continue;
    if (tokens[i + 1]?.kind !== "lparen") continue;
    // Chained locator().action() already handled; page.direct needs an ident receiver.
    const prev = tokens[i - 1];
    if (prev?.kind === "rparen") continue;

    const call = consumeCallArgs(tokens, i + 1);
    if (!call || call.args.length === 0 || call.args[0].kind !== "string") continue;

    let fillValue: string | null = null;
    if (
      (interaction === "fill" || interaction === "type") &&
      call.args[1]?.kind === "string"
    ) {
      fillValue = call.args[1].value;
    }

    const start = callStartIndex(source, tok.index);
    const pos = posAt(source, start);
    locators.push({
      selector: call.args[0].value,
      kind: classifySelector(call.args[0].value),
      interaction,
      lineno: pos.lineno,
      col_offset: pos.col_offset,
      fill_value: fillValue,
      raw_call: tok.value,
    });
  }

  locators.sort((a, b) => a.lineno - b.lineno || a.col_offset - b.col_offset);
  return locators;
}

export function extractGotoUrl(source: string): string | null {
  const tokens = tokenize(source);
  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i];
    if (tok.kind !== "ident" || tok.value !== "goto") continue;
    if (tokens[i + 1]?.kind !== "lparen") continue;
    const call = consumeCallArgs(tokens, i + 1);
    if (call?.args[0]?.kind === "string") return call.args[0].value;
  }
  return null;
}
