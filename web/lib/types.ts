export type LocatorKind = "css" | "xpath" | "unknown";

export type Interaction =
  | "click"
  | "fill"
  | "type"
  | "check"
  | "select_option"
  | "hover"
  | "wait_for"
  | "other"
  | "none";

export type TranslationSource = "openai" | "fallback";

export type ParsedLocator = {
  selector: string;
  kind: LocatorKind;
  interaction: Interaction;
  lineno: number;
  col_offset: number;
  fill_value: string | null;
  raw_call: string | null;
};

export type TranslatedLocator = {
  locator: ParsedLocator;
  name: string;
  source: TranslationSource;
  rationale: string | null;
};

export type GeneratedAction = {
  name: string;
  interaction: Interaction;
  fill_value: string | null;
  source_lineno: number | null;
};

export type GeneratedScript = {
  query: string;
  python_source: string;
  url: string;
  field_names: string[];
  actions: GeneratedAction[];
  source_path: string | null;
};

export type MigrationResult = {
  source_path: string;
  locator_count: number;
  translation_count: number;
  translations: TranslatedLocator[];
  script: GeneratedScript;
  parseError: string | null;
};
