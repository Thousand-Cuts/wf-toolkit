"""Tests for skills/workfront-custom-forms/scripts/cascade_rule_parser.py.

The parser converts natural-language briefs into structured cascade-rule
intents (name-based, not ID-based — ID resolution happens later, after
the admin's parameters have been created and we know their server-
assigned IDs).

Output shape per parsed rule:
    {
        "ruleType":            "DISPLAY" | "SKIP",
        "trigger_param_name":  str,                          # primary trigger
        "matchType":           "EXIST" | "NOTEXIST",
        "value":               str,
        "target_param_name":   str | None,
        "target_group_name":   str | None,
        "otherwise_param_name": str | None,
        "to_end_of_form":      bool,
        "multi_match": [                                      # AND conditions
            {"matchType": ..., "trigger_param_name": ..., "value": ...},
            ...
        ],
        "raw":                 str,                           # original brief sentence
    }

Empirically verified shape (2026-05-22).
ruleType enum verified in 2026-05-22-custom-forms-phase-b4-* (DISPLAY/SKIP only).
matchType enum verified in Phase B-3 (EXIST/NOTEXIST only — note: no underscore).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills/workfront-custom-forms/scripts"),
)

from cascade_rule_parser import parse_cascade_rules, ParseError  # noqa: E402


# ----------------------------------------------------------------------------
# Single-rule patterns
# ----------------------------------------------------------------------------


def test_simple_show_when_is():
    """show X when Y is Z → DISPLAY, EXIST."""
    rules = parse_cascade_rules("show 'Other notes' when 'Vendor type' is 'Other'")
    assert len(rules) == 1
    r = rules[0]
    assert r["ruleType"] == "DISPLAY"
    assert r["matchType"] == "EXIST"
    assert r["trigger_param_name"] == "Vendor type"
    assert r["value"] == "Other"
    assert r["target_param_name"] == "Other notes"
    assert r["to_end_of_form"] is False
    assert r["multi_match"] == []
    assert r["otherwise_param_name"] is None


def test_show_if_equals_synonym():
    """show X if Y equals Z → same as 'when ... is ...'."""
    rules = parse_cascade_rules("show 'Notes' if 'Status' equals 'Active'")
    assert len(rules) == 1
    r = rules[0]
    assert r["ruleType"] == "DISPLAY"
    assert r["matchType"] == "EXIST"
    assert r["trigger_param_name"] == "Status"
    assert r["value"] == "Active"
    assert r["target_param_name"] == "Notes"


def test_hide_when_is():
    """hide X when Y is Z → SKIP, EXIST."""
    rules = parse_cascade_rules("hide 'Approval Notes' when 'Status' is 'Draft'")
    assert len(rules) == 1
    r = rules[0]
    assert r["ruleType"] == "SKIP"
    assert r["matchType"] == "EXIST"
    assert r["target_param_name"] == "Approval Notes"


def test_skip_if_synonym():
    """skip X if Y equals Z → same as hide ... when ... is ..."""
    rules = parse_cascade_rules("skip 'Field' if 'Trigger' equals 'X'")
    assert len(rules) == 1
    assert rules[0]["ruleType"] == "SKIP"
    assert rules[0]["matchType"] == "EXIST"


def test_show_when_not():
    """show X when Y is NOT Z → DISPLAY, NOTEXIST."""
    rules = parse_cascade_rules(
        "show 'Internal notes' when 'Status' is not 'Closed'"
    )
    assert len(rules) == 1
    r = rules[0]
    assert r["matchType"] == "NOTEXIST"
    assert r["trigger_param_name"] == "Status"
    assert r["value"] == "Closed"
    assert r["target_param_name"] == "Internal notes"


def test_show_unless_synonym():
    """show X unless Y is Z → NOTEXIST."""
    rules = parse_cascade_rules("show 'X' unless 'Y' is 'Z'")
    assert len(rules) == 1
    assert rules[0]["matchType"] == "NOTEXIST"


def test_show_rest_of_form():
    """show the rest of the form when Y is Z → toEndOfForm=True."""
    rules = parse_cascade_rules(
        "show the rest of the form when 'Vendor type' is 'Other'"
    )
    assert len(rules) == 1
    r = rules[0]
    assert r["ruleType"] == "DISPLAY"
    assert r["to_end_of_form"] is True
    assert r["target_param_name"] is None
    assert r["target_group_name"] is None
    assert r["trigger_param_name"] == "Vendor type"
    assert r["value"] == "Other"


def test_otherwise_clause():
    """show X when Y is Z, otherwise show W → otherwise_param_name=W."""
    rules = parse_cascade_rules(
        "show 'Premium notes' when 'Tier' is 'Premium', otherwise show 'Basic notes'"
    )
    assert len(rules) == 1
    r = rules[0]
    assert r["target_param_name"] == "Premium notes"
    assert r["otherwise_param_name"] == "Basic notes"


def test_multi_match_and():
    """show X when Y is Z and W is V → multi_match has one extra entry."""
    rules = parse_cascade_rules(
        "show 'Detail' when 'Type' is 'Custom' and 'Region' is 'North'"
    )
    assert len(rules) == 1
    r = rules[0]
    assert r["trigger_param_name"] == "Type"
    assert r["value"] == "Custom"
    assert len(r["multi_match"]) == 1
    assert r["multi_match"][0]["trigger_param_name"] == "Region"
    assert r["multi_match"][0]["value"] == "North"
    assert r["multi_match"][0]["matchType"] == "EXIST"


# ----------------------------------------------------------------------------
# Multiple rules in one brief
# ----------------------------------------------------------------------------


def test_multiple_rules_newline_separated():
    """Two rules separated by newline → two output entries."""
    brief = (
        "show 'Notes' when 'Type' is 'Other'\n"
        "hide 'Approval' when 'Status' is 'Draft'"
    )
    rules = parse_cascade_rules(brief)
    assert len(rules) == 2
    assert rules[0]["ruleType"] == "DISPLAY"
    assert rules[1]["ruleType"] == "SKIP"


def test_multiple_rules_period_separated():
    """Two rules separated by '.' → two output entries."""
    brief = (
        "show 'Notes' when 'Type' is 'Other'. "
        "show 'Detail' when 'Type' is 'Custom'."
    )
    rules = parse_cascade_rules(brief)
    assert len(rules) == 2
    assert all(r["ruleType"] == "DISPLAY" for r in rules)


# ----------------------------------------------------------------------------
# Quoting / name extraction
# ----------------------------------------------------------------------------


def test_double_quotes():
    """Double quotes accepted as alternative to single."""
    rules = parse_cascade_rules('show "Other notes" when "Vendor type" is "Other"')
    assert len(rules) == 1
    assert rules[0]["target_param_name"] == "Other notes"
    assert rules[0]["trigger_param_name"] == "Vendor type"
    assert rules[0]["value"] == "Other"


def test_unquoted_single_word_names():
    """Unquoted single-word names work (the admin may not quote)."""
    rules = parse_cascade_rules("show Notes when Type is Other")
    assert len(rules) == 1
    r = rules[0]
    assert r["target_param_name"] == "Notes"
    assert r["trigger_param_name"] == "Type"
    assert r["value"] == "Other"


def test_raw_field_preserved():
    """The 'raw' field returns the original brief snippet for apply-gate render."""
    brief = "show 'X' when 'Y' is 'Z'"
    rules = parse_cascade_rules(brief)
    assert rules[0]["raw"] == brief


# ----------------------------------------------------------------------------
# Rejection / error cases
# ----------------------------------------------------------------------------


def test_empty_brief_returns_empty_list():
    """Empty input → empty list, not an error (the admin supplied no rules)."""
    assert parse_cascade_rules("") == []
    assert parse_cascade_rules("   \n  ") == []


def test_brief_with_no_rule_phrases_returns_empty():
    """Brief that contains no show/hide/skip phrases → empty list."""
    assert parse_cascade_rules("Create a form for projects with Vendor type") == []


def test_malformed_show_without_when_raises():
    """show X by itself with no condition → ParseError."""
    with pytest.raises(ParseError):
        parse_cascade_rules("show 'Notes' something")


def test_show_when_missing_value_raises():
    """show X when Y is → missing value → ParseError."""
    with pytest.raises(ParseError):
        parse_cascade_rules("show 'Notes' when 'Type' is")


# ----------------------------------------------------------------------------
# Case insensitivity for keywords (but not for names/values)
# ----------------------------------------------------------------------------


def test_keywords_case_insensitive():
    """SHOW, Show, show — all parse the same. Field names + values stay verbatim."""
    rules = parse_cascade_rules("SHOW 'Notes' WHEN 'Type' IS 'Other'")
    assert len(rules) == 1
    assert rules[0]["target_param_name"] == "Notes"
    assert rules[0]["trigger_param_name"] == "Type"
    assert rules[0]["value"] == "Other"  # value preserved verbatim
