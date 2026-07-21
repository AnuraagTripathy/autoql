"""
OpenAI-backed translator for Legacy-to-AgentQL migration.

Maps brittle CSS/XPath locators (from ``parser.ParsedLocator``) into
semantic snake_case AgentQL query field names. Prefers gpt-4o-mini when
an API key is available; otherwise (or on failure) uses deterministic
heuristic fallbacks so offline / CI runs still produce usable names.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from parser import Interaction, ParsedLocator

DEFAULT_MODEL = "gpt-4o-mini"

# Source weights: semantic attributes beat structural classes/tags.
_SOURCE_WEIGHTS: dict[str, int] = {
    "testid": 8,
    "name": 7,
    "aria": 6,
    "placeholder": 5,
    "type": 5,
    "id": 4,
    "class": 2,
    "tag": 0,
}

_SYSTEM_PROMPT = """\
You name DOM elements for AgentQL queries.
Given a brittle CSS or XPath selector and the interaction applied to it,
reply with JSON only: {"name": "<snake_case>", "rationale": "<short reason>"}.
Rules:
- name must be snake_case, start with a letter, and describe the element's role
- prefer roles like username_input, password_input, submit_button, show_password_button
- do not include CSS/XPath syntax in the name
- keep names short (2-4 words / tokens)
"""

_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")

# Prefer semantic HTML / test-id hints over structural noise.
_ATTR_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("testid", re.compile(r"""data-testid\s*=\s*['"]([^'"]+)['"]""", re.I)),
    ("testid", re.compile(r"""@data-testid\s*=\s*['"]([^'"]+)['"]""", re.I)),
    ("name", re.compile(r"""\[name\s*=\s*['"]([^'"]+)['"]""", re.I)),
    ("name", re.compile(r"""@name\s*=\s*['"]([^'"]+)['"]""", re.I)),
    ("id", re.compile(r"""#([A-Za-z][\w-]*)""")),
    ("id", re.compile(r"""\[id\s*=\s*['"]([^'"]+)['"]""", re.I)),
    ("id", re.compile(r"""@id\s*=\s*['"]([^'"]+)['"]""", re.I)),
    ("aria", re.compile(r"""aria-label\s*=\s*['"]([^'"]+)['"]""", re.I)),
    ("placeholder", re.compile(r"""placeholder\s*=\s*['"]([^'"]+)['"]""", re.I)),
    ("type", re.compile(r"""\[type\s*=\s*['"]([^'"]+)['"]""", re.I)),
    ("type", re.compile(r"""@type\s*=\s*['"]([^'"]+)['"]""", re.I)),
)

_CLASS_PATTERN = re.compile(r"""\.([A-Za-z][\w-]*)""")
_XPATH_CLASS = re.compile(
    r"""contains\(\s*@class\s*,\s*['"]([^'"]+)['"]\s*\)""",
    re.I,
)
_TAG_PATTERN = re.compile(r"(?:^|[/\s>+~,])([a-z][a-z0-9]*)", re.I)

_NOISE_TOKENS = frozenset(
    {
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
        "button",  # re-added via interaction suffix when useful
        "input",
        "icon",
        "toolbar",
        "footer",
        "header",
        "nav",
    }
)

_INTERACTION_SUFFIX: dict[Interaction, str] = {
    Interaction.CLICK: "button",
    Interaction.FILL: "input",
    Interaction.TYPE: "input",
    Interaction.CHECK: "checkbox",
    Interaction.SELECT: "select",
    Interaction.HOVER: "element",
    Interaction.WAIT: "element",
    Interaction.OTHER: "element",
    Interaction.NONE: "element",
}


class TranslationSource(str, Enum):
    """Where the AgentQL field name came from."""

    OPENAI = "openai"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class TranslatedLocator:
    """A parsed locator paired with a semantic AgentQL name.

    Attributes:
        locator: Original AST-extracted locator.
        name: snake_case AgentQL query field (unique within a batch).
        source: Whether the name came from OpenAI or a local heuristic.
        rationale: Optional short explanation of the naming choice.
    """

    locator: ParsedLocator
    name: str
    source: TranslationSource
    rationale: str | None = None


def to_snake_case(raw: str) -> str:
    """Normalize *raw* into a conservative snake_case identifier."""
    if not raw or not raw.strip():
        return "element"

    text = _CAMEL_BOUNDARY.sub(r"\1_\2", raw.strip())
    text = text.replace("-", "_").replace(" ", "_")
    text = _NON_ALNUM.sub("_", text.lower())
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        return "element"
    if text[0].isdigit():
        text = f"el_{text}"
    return text


def is_valid_agentql_name(name: str) -> bool:
    """Return True when *name* is a usable AgentQL field identifier."""
    return bool(name) and _SNAKE_RE.match(name) is not None


def ensure_unique(name: str, used: set[str]) -> str:
    """Return *name*, appending ``_2``, ``_3``, … until unused."""
    candidate = name if is_valid_agentql_name(name) else to_snake_case(name)
    if candidate not in used:
        used.add(candidate)
        return candidate

    suffix = 2
    while f"{candidate}_{suffix}" in used:
        suffix += 1
    unique = f"{candidate}_{suffix}"
    used.add(unique)
    return unique


def _tokens_from_selector(selector: str) -> list[tuple[str, str]]:
    """Pull ``(source, token)`` pairs from a selector, attrs first."""
    tokens: list[tuple[str, str]] = []

    for label, pattern in _ATTR_PATTERNS:
        for match in pattern.finditer(selector):
            tokens.append((label, match.group(1)))

    for match in _CLASS_PATTERN.finditer(selector):
        tokens.append(("class", match.group(1)))
    for match in _XPATH_CLASS.finditer(selector):
        tokens.append(("class", match.group(1)))

    # Structural tags are last-resort hints when nothing semantic appears.
    for match in _TAG_PATTERN.finditer(selector):
        tokens.append(("tag", match.group(1)))

    return tokens


def _score_token(token: str, source: str) -> int:
    """Higher scores prefer semantic attributes over layout chrome."""
    snake = to_snake_case(token)
    if not snake or snake in _NOISE_TOKENS:
        return -1
    score = 1 + _SOURCE_WEIGHTS.get(source, 0)
    if any(hint in snake for hint in ("user", "pass", "email", "login", "submit", "search", "pwd")):
        score += 3
    if snake.endswith(("btn", "button", "input", "field", "link")):
        score += 1
    if len(snake) <= 2:
        score -= 1
    return score


def _pick_stem(locator: ParsedLocator) -> str:
    """Choose a base identifier stem from selector hints."""
    ranked: list[tuple[int, str]] = []
    for source, token in _tokens_from_selector(locator.selector):
        score = _score_token(token, source)
        if score < 0:
            continue
        ranked.append((score, to_snake_case(token)))

    if ranked:
        # Prefer higher score, then shorter stems (user over login_form).
        ranked.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
        return ranked[0][1]

    # Interaction-only fallback when the selector is pure structure.
    return _INTERACTION_SUFFIX.get(locator.interaction, "element")


def heuristic_name(locator: ParsedLocator) -> str:
    """Derive a snake_case AgentQL name from selector tokens and interaction.

    Prefers ``name`` / ``data-testid`` / id / type attributes, then useful
    class fragments, and finally tags. Appends an interaction-appropriate
    suffix when it is not already implied by the stem.
    """
    stem = _pick_stem(locator)
    suffix = _INTERACTION_SUFFIX.get(locator.interaction, "element")

    # Avoid ``password_input_input`` / ``submit_button_button`` duplication.
    if stem == suffix or stem.endswith(f"_{suffix}"):
        return stem
    if suffix == "button" and stem.endswith(("_btn", "btn", "_button", "button")):
        return stem if stem.endswith("button") else to_snake_case(stem.replace("btn", "button"))
    if suffix == "input" and any(stem.endswith(s) for s in ("_input", "_field", "input", "field")):
        return stem

    # Type=password + fill → password_input; name=user + fill → user_input.
    return f"{stem}_{suffix}"


def resolve_api_key(api_key: str | None = None) -> str | None:
    """Return an explicit key, else ``OPENAI_API_KEY`` from the environment."""
    if api_key:
        return api_key
    return os.environ.get("OPENAI_API_KEY") or None


def _fallback_translation(
    locator: ParsedLocator,
    used: set[str],
    *,
    rationale: str,
) -> TranslatedLocator:
    """Build a :class:`TranslatedLocator` from the local heuristic."""
    name = ensure_unique(heuristic_name(locator), used)
    return TranslatedLocator(
        locator=locator,
        name=name,
        source=TranslationSource.FALLBACK,
        rationale=rationale,
    )


def _openai_name_for(
    locator: ParsedLocator,
    *,
    api_key: str,
    model: str,
) -> tuple[str, str] | None:
    """Ask OpenAI for a name; return ``(name, rationale)`` or ``None``."""
    try:
        from openai import OpenAI
    except ImportError:
        return None

    user_prompt = {
        "selector": locator.selector,
        "kind": locator.kind.value,
        "interaction": locator.interaction.value,
        "fill_value": locator.fill_value,
        "raw_call": locator.raw_call,
    }

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_prompt)},
            ],
        )
    except Exception:
        return None

    try:
        content = response.choices[0].message.content or ""
        payload = json.loads(content)
    except (IndexError, TypeError, json.JSONDecodeError, AttributeError):
        return None

    name = payload.get("name") if isinstance(payload, dict) else None
    rationale = payload.get("rationale") if isinstance(payload, dict) else None
    if not isinstance(name, str) or not is_valid_agentql_name(to_snake_case(name)):
        return None
    reason = rationale if isinstance(rationale, str) else "openai suggestion"
    return to_snake_case(name), reason


def translate_locator(
    locator: ParsedLocator,
    *,
    used_names: set[str] | None = None,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    force_fallback: bool = False,
) -> TranslatedLocator:
    """Translate one locator into a unique AgentQL field name.

    Tries gpt-4o-mini when an API key is available and *force_fallback* is
    false. Any missing key, import/network/parse failure, or invalid name
    falls back to :func:`heuristic_name`.
    """
    used = used_names if used_names is not None else set()
    key = resolve_api_key(api_key)

    if not force_fallback and key:
        suggestion = _openai_name_for(locator, api_key=key, model=model)
        if suggestion is not None:
            name, rationale = suggestion
            return TranslatedLocator(
                locator=locator,
                name=ensure_unique(name, used),
                source=TranslationSource.OPENAI,
                rationale=rationale,
            )
        return _fallback_translation(
            locator,
            used,
            rationale="openai unavailable or invalid; used heuristic",
        )

    reason = "force_fallback" if force_fallback else "no OPENAI_API_KEY; used heuristic"
    return _fallback_translation(locator, used, rationale=reason)


def translate_locators(
    locators: Sequence[ParsedLocator],
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    force_fallback: bool = False,
) -> list[TranslatedLocator]:
    """Translate locators in order, keeping names unique across the batch."""
    used: set[str] = set()
    results: list[TranslatedLocator] = []
    for locator in locators:
        results.append(
            translate_locator(
                locator,
                used_names=used,
                api_key=api_key,
                model=model,
                force_fallback=force_fallback,
            )
        )
    return results
