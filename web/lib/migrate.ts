import { generateScript } from "./generator";
import { extractGotoUrl, parseSource } from "./parser";
import { translateLocators } from "./translator";
import type { MigrationResult } from "./types";

export function migrateSource(
  source: string,
  opts: { sourcePath?: string; url?: string } = {},
): MigrationResult {
  const locators = parseSource(source);
  const translations = translateLocators(locators);
  const resolvedUrl = opts.url || extractGotoUrl(source) || "https://example.com";
  const sourcePath = opts.sourcePath ?? "legacy script";
  const script = generateScript(translations, {
    url: resolvedUrl,
    sourcePath,
  });

  return {
    source_path: sourcePath,
    locator_count: locators.length,
    translation_count: translations.length,
    translations,
    script,
    parseError: null,
  };
}
