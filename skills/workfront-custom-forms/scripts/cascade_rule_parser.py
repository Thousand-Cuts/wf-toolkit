"""Natural-language → structured cascade-rule intent parser.

Used by workfront-custom-forms Flow 1 (NL-create) and Flow 2 (modify) to
turn the user's brief into a list of cascade-rule dicts. Output is
name-based; ID resolution happens later, after parameter creation, in the
flow's payload-composition step.

Output shape per rule — see tests/test_cascade_rule_parser.py docstring.

Schema verified empirically against CTCSRL/CTCSRM (2026-05-22).
"""

from __future__ import annotations

import re
from typing import Optional


class ParseError(ValueError):
    """Raised when a brief contains a recognizable rule phrase but is malformed."""


# A quoted name: "foo bar" or 'foo bar'  →  captured without quotes
_QUOTED = r"(?:'([^']+)'|\"([^\"]+)\")"

# An unquoted name token: greedy non-keyword run.
# Stops at: when/if/is/equals/unless/and/otherwise/,/. and other rule keywords.
# This is a simple heuristic — for ambiguous cases users should quote.
_STOP_WORDS = (
    r"when|if|is|equals|unless|and|otherwise|,"
)
_UNQUOTED = rf"((?:(?!\b(?:{_STOP_WORDS})\b)\S)+(?:\s+(?!\b(?:{_STOP_WORDS})\b)\S+)*)"

# A "name" can be either quoted or unquoted (quoted wins).
_NAME = rf"(?:{_QUOTED}|{_UNQUOTED})"


def _extract_name(match_groups: tuple, start_index: int) -> Optional[str]:
    """Given a regex match's groups tuple and the index of a name capture
    triple (quoted-single, quoted-double, unquoted), return whichever is set.
    """
    sq, dq, uq = (
        match_groups[start_index],
        match_groups[start_index + 1],
        match_groups[start_index + 2],
    )
    name = sq or dq or uq
    return name.strip() if name else None


def _split_into_sentences(brief: str) -> list[str]:
    """Split a multi-rule brief on newline or period boundaries.

    Periods inside quoted strings are NOT split on.
    """
    sentences: list[str] = []
    buf = ""
    in_quote: Optional[str] = None
    for ch in brief:
        if in_quote:
            buf += ch
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ("'", '"'):
            in_quote = ch
            buf += ch
            continue
        if ch == "\n" or ch == ".":
            if buf.strip():
                sentences.append(buf.strip())
            buf = ""
            continue
        buf += ch
    if buf.strip():
        sentences.append(buf.strip())
    return sentences


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Verb at the start of a rule. Captures the verb so we know DISPLAY vs SKIP.
# Note: SHOW + the-rest-of-the-form is its own pattern below.
_VERB = r"(?P<verb>show|hide|skip)"

# Connector between target and trigger: "when" or "if".
_WHEN_IF = r"(?:when|if)"

# Equals / is — both meanings identical.
_IS_EQ = r"(?:is|equals)"

# "is not" / "unless" → NOTEXIST.
# The "unless" form: "show X unless Y is Z" — handled by replacing 'unless' with
# 'when ... is not' before pattern matching.

# Pattern: show/hide/skip <target> when/if <trigger> is/equals <value>
# Optional: ", otherwise show <otherwise>"
# Optional: " and <trigger2> is <value2>" (multi-match AND)
# The trailing "and" / "otherwise" groups are parsed in a second pass.
_MAIN_PATTERN = re.compile(
    rf"""
    ^\s*
    {_VERB}\s+
    {_NAME}\s+                            # target (groups 1,2,3)
    {_WHEN_IF}\s+
    {_NAME}\s+                            # trigger (groups 4,5,6)
    {_IS_EQ}\s+
    (?P<negate>not\s+)?                   # optional 'not' between is/equals and value
    {_NAME}                               # value (groups 7,8,9)
    (?P<tail>.*)$
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

# "show the rest of the form when Y is Z"
_REST_PATTERN = re.compile(
    rf"""
    ^\s*
    show\s+the\s+rest\s+of\s+the\s+form\s+
    {_WHEN_IF}\s+
    {_NAME}\s+                            # trigger (groups 1,2,3)
    {_IS_EQ}\s+
    (?P<negate>not\s+)?
    {_NAME}                               # value (groups 4,5,6)
    (?P<tail>.*)$
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

# Sub-patterns parsed off the "tail" after main match.
_OTHERWISE_PATTERN = re.compile(
    rf"""
    ^\s*,?\s*otherwise\s+show\s+
    {_NAME}                               # otherwise target
    (?P<rest>.*)$
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

_AND_MATCH_PATTERN = re.compile(
    rf"""
    ^\s*and\s+
    {_NAME}\s+                            # additional trigger
    {_IS_EQ}\s+
    (?P<negate>not\s+)?
    {_NAME}                               # additional value
    (?P<rest>.*)$
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_cascade_rules(brief: str) -> list[dict]:
    """Parse a multi-rule natural-language brief.

    Returns a list of rule dicts. Empty input or input with no rule phrases
    returns an empty list (no error). Malformed rule phrases raise ParseError.
    """
    if not brief or not brief.strip():
        return []

    rules: list[dict] = []
    for sentence in _split_into_sentences(brief):
        rule = _parse_single_sentence(sentence)
        if rule is not None:
            rules.append(rule)
    return rules


def _looks_like_rule(sentence: str) -> bool:
    """Heuristic: does this sentence contain a recognizable verb?"""
    return bool(re.search(r"\b(show|hide|skip)\b", sentence, re.IGNORECASE))


def _parse_single_sentence(sentence: str) -> Optional[dict]:
    """Parse one sentence. Returns None if it's not a rule, raises if malformed."""
    if not _looks_like_rule(sentence):
        return None

    # Normalize "unless" → "when ... is not": "show X unless Y is Z" → "show X when Y is not Z"
    # The transformation is purely lexical.
    normalized = re.sub(
        r"\bunless\b", "when", sentence, flags=re.IGNORECASE
    )
    # If we replaced 'unless', also flip the eventual 'is' to 'is not'.
    # We do this only if the original contained 'unless' AND the result doesn't
    # already have 'is not'.
    if re.search(r"\bunless\b", sentence, re.IGNORECASE):
        normalized = re.sub(
            r"\b(is|equals)\s+(?!not\b)",
            lambda m: f"{m.group(1)} not ",
            normalized,
            count=1,
            flags=re.IGNORECASE,
        )

    # Try the rest-of-form pattern first.
    m = _REST_PATTERN.match(normalized)
    if m:
        groups = m.groups()
        # Group layout: [0..2]=trigger sq/dq/uq, [3]=negate, [4..6]=value sq/dq/uq, [7]=tail
        trigger = _extract_name(groups, 0)
        value = _extract_name(groups, 4)
        if not trigger or not value:
            raise ParseError(f"Could not parse trigger/value from rest-of-form rule: {sentence!r}")
        rule = _new_rule(
            sentence,
            ruleType="DISPLAY",
            trigger=trigger,
            value=value,
            target=None,
            negate=bool(m.group("negate")),
            to_end_of_form=True,
        )
        return _parse_tail(rule, m.group("tail"))

    m = _MAIN_PATTERN.match(normalized)
    if m:
        groups = m.groups()
        # Group layout: [0]=verb, [1..3]=target, [4..6]=trigger, [7]=negate, [8..10]=value, [11]=tail
        verb = m.group("verb").lower()
        target = _extract_name(groups, 1)
        trigger = _extract_name(groups, 4)
        value = _extract_name(groups, 8)
        if not target or not trigger or not value:
            raise ParseError(f"Missing target/trigger/value in: {sentence!r}")
        rule_type = "DISPLAY" if verb == "show" else "SKIP"
        rule = _new_rule(
            sentence,
            ruleType=rule_type,
            trigger=trigger,
            value=value,
            target=target,
            negate=bool(m.group("negate")),
            to_end_of_form=False,
        )
        return _parse_tail(rule, m.group("tail"))

    # Sentence contains a verb but didn't match any pattern.
    raise ParseError(f"Could not parse rule phrase: {sentence!r}")


def _new_rule(
    raw: str,
    *,
    ruleType: str,
    trigger: str,
    value: str,
    target: Optional[str],
    negate: bool,
    to_end_of_form: bool,
) -> dict:
    return {
        "ruleType": ruleType,
        "trigger_param_name": trigger,
        "matchType": "NOTEXIST" if negate else "EXIST",
        "value": value,
        "target_param_name": target,
        "target_group_name": None,  # populated by callers that recognize group refs
        "otherwise_param_name": None,
        "to_end_of_form": to_end_of_form,
        "multi_match": [],
        "raw": raw,
    }


def _parse_tail(rule: dict, tail: str) -> dict:
    """Process any trailing ', otherwise show W' and ' and Y is V' clauses."""
    tail = tail.strip()
    while tail:
        # Try AND first — otherwise can only appear once at the very end, but
        # AND clauses can chain.
        m = _AND_MATCH_PATTERN.match(tail)
        if m:
            groups = m.groups()
            # Layout: [0..2]=trigger, [3]=negate, [4..6]=value, [7]=rest
            trigger = _extract_name(groups, 0)
            value = _extract_name(groups, 4)
            if not trigger or not value:
                raise ParseError(
                    f"Malformed AND clause in rule: {rule['raw']!r}"
                )
            rule["multi_match"].append(
                {
                    "matchType": "NOTEXIST" if m.group("negate") else "EXIST",
                    "trigger_param_name": trigger,
                    "value": value,
                }
            )
            tail = m.group("rest").strip()
            continue

        m = _OTHERWISE_PATTERN.match(tail)
        if m:
            groups = m.groups()
            otherwise = _extract_name(groups, 0)
            if not otherwise:
                raise ParseError(
                    f"Malformed 'otherwise' clause in rule: {rule['raw']!r}"
                )
            rule["otherwise_param_name"] = otherwise
            tail = m.group("rest").strip()
            continue

        # Unrecognized trailing content — error.
        raise ParseError(f"Trailing content unparseable in rule: {rule['raw']!r} (leftover: {tail!r})")

    return rule


# ---------------------------------------------------------------------------
# Apply-gate render helper
# ---------------------------------------------------------------------------


def render_rule_for_apply_gate(rule: dict, index: int = 1) -> str:
    """Format one parsed rule for the user-facing apply-gate prompt.

    Example: "Rule 1: Show 'Other notes' when 'Vendor type' = 'Other'"
    """
    verb = "Show" if rule["ruleType"] == "DISPLAY" else "Hide"
    cmp = "≠" if rule["matchType"] == "NOTEXIST" else "="

    if rule["to_end_of_form"]:
        target_desc = "the rest of the form"
    elif rule["target_param_name"]:
        target_desc = f"'{rule['target_param_name']}'"
    elif rule["target_group_name"]:
        target_desc = f"group '{rule['target_group_name']}'"
    else:
        target_desc = "<no target>"

    primary = (
        f"Rule {index}: {verb} {target_desc} when "
        f"'{rule['trigger_param_name']}' {cmp} '{rule['value']}'"
    )

    extras = []
    for mm in rule["multi_match"]:
        mm_cmp = "≠" if mm["matchType"] == "NOTEXIST" else "="
        extras.append(
            f"AND '{mm['trigger_param_name']}' {mm_cmp} '{mm['value']}'"
        )

    if rule["otherwise_param_name"]:
        extras.append(f"otherwise show '{rule['otherwise_param_name']}'")

    if extras:
        return primary + " " + " ".join(extras)
    return primary
