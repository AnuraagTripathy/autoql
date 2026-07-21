"""
OpenAI-backed translator for Legacy-to-AgentQL migration.

Maps brittle CSS/XPath locators (from ``parser.ParsedLocator``) into
semantic snake_case AgentQL query field names. Prefers gpt-4o-mini when
an API key is available; otherwise (or on failure) uses deterministic
heuristic fallbacks so offline / CI runs still produce usable names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from parser import Interaction, ParsedLocator

DEFAULT_MODEL = "gpt-4o-mini"

_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


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


def heuristic_name(locator: ParsedLocator) -> str:
    """Derive a snake_case AgentQL name from selector tokens (stub)."""
    raise NotImplementedError("heuristic fallback not yet implemented")


def translate_locator(
    locator: ParsedLocator,
    *,
    used_names: set[str] | None = None,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    force_fallback: bool = False,
) -> TranslatedLocator:
    """Translate one locator into an AgentQL field name (stub)."""
    raise NotImplementedError("OpenAI translator not yet implemented")


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
