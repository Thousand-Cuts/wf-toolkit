"""Tests for skills/workfront-custom-forms/scripts/option_list_parser.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the script importable without packaging.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(
    0,
    str(REPO_ROOT / "skills" / "workfront-custom-forms" / "scripts"),
)

import option_list_parser as olp  # noqa: E402


# ---------------------------------------------------------------------------
# lines mode

def test_lines_basic():
    options = olp.parse_option_list("a\nb\nc")
    assert options == [
        {"label": "a", "value": "a", "displayOrder": 1},
        {"label": "b", "value": "b", "displayOrder": 2},
        {"label": "c", "value": "c", "displayOrder": 3},
    ]


def test_lines_trims_whitespace_and_blank_rows():
    options = olp.parse_option_list("  a\n\n  b  \n\n")
    assert [o["label"] for o in options] == ["a", "b"]
    assert [o["displayOrder"] for o in options] == [1, 2]


def test_lines_200_option_input():
    text = "\n".join(f"opt{i}" for i in range(1, 201))
    options = olp.parse_option_list(text)
    assert len(options) == 200
    assert options[-1] == {"label": "opt200", "value": "opt200", "displayOrder": 200}


# ---------------------------------------------------------------------------
# csv mode

def test_csv_with_header_and_value():
    text = "label,value\nFoo,foo\nBar,bar"
    options = olp.parse_option_list(text)
    assert options == [
        {"label": "Foo", "value": "foo", "displayOrder": 1},
        {"label": "Bar", "value": "bar", "displayOrder": 2},
    ]


def test_csv_with_explicit_display_order():
    text = "label,value,displayOrder\nFoo,foo,10\nBar,bar,5\nBaz,baz,7"
    options = olp.parse_option_list(text)
    assert [o["displayOrder"] for o in options] == [10, 5, 7]


def test_csv_with_isHidden():
    text = "label,value,isHidden\nFoo,foo,true\nBar,bar,false"
    options = olp.parse_option_list(text)
    assert options[0].get("isHidden") is True
    assert "isHidden" not in options[1]


def test_csv_quoted_commas_in_values():
    text = 'label,value\n"Hello, world",hello_world\nNo comma,plain'
    options = olp.parse_option_list(text)
    assert options[0] == {
        "label": "Hello, world",
        "value": "hello_world",
        "displayOrder": 1,
    }


def test_csv_missing_label_column_raises_when_csv_hint_forced():
    # Without 'label' in the header, autodetection (correctly) doesn't pick
    # CSV mode — it falls back to line-mode. The error only fires when
    # the operator explicitly forces CSV parsing on a malformed header.
    text = "name,value\nFoo,foo"
    with pytest.raises(ValueError, match="must include 'label'"):
        olp.parse_option_list(text, format_hint="csv")


def test_csv_non_integer_display_order_raises():
    text = "label,displayOrder\nFoo,abc"
    with pytest.raises(ValueError, match="non-integer displayOrder"):
        olp.parse_option_list(text)


def test_csv_value_defaults_to_label_when_value_blank():
    text = "label,value\nFoo,\nBar,bar"
    options = olp.parse_option_list(text)
    assert options[0]["value"] == "Foo"
    assert options[1]["value"] == "bar"


# ---------------------------------------------------------------------------
# tsv mode

def test_tsv_detection_via_hint():
    text = "label\tvalue\nFoo\tfoo\nBar\tbar"
    options = olp.parse_option_list(text, format_hint="tsv")
    assert len(options) == 2
    assert options[0]["value"] == "foo"


# ---------------------------------------------------------------------------
# label_eq_value mode

def test_label_eq_value_basic():
    text = "Foo = foo\nBar = bar"
    options = olp.parse_option_list(text)
    assert options == [
        {"label": "Foo", "value": "foo", "displayOrder": 1},
        {"label": "Bar", "value": "bar", "displayOrder": 2},
    ]


def test_label_eq_value_with_complex_values():
    text = "Production = prod-east-1\nStaging = stg-east-1"
    options = olp.parse_option_list(text)
    assert options[0]["value"] == "prod-east-1"


def test_label_eq_value_missing_separator_raises():
    text = "Foo = foo\nbarNoSeparator"
    with pytest.raises(ValueError, match="missing ' = ' separator"):
        olp.parse_option_list(text)


# ---------------------------------------------------------------------------
# comma mode (single line)

def test_comma_single_line():
    options = olp.parse_option_list("Foo, Bar, Baz")
    assert [o["label"] for o in options] == ["Foo", "Bar", "Baz"]
    assert [o["displayOrder"] for o in options] == [1, 2, 3]


def test_comma_ignores_empty_segments():
    options = olp.parse_option_list("Foo,, Bar ,")
    assert [o["label"] for o in options] == ["Foo", "Bar"]


# ---------------------------------------------------------------------------
# error cases

def test_empty_input_raises():
    with pytest.raises(ValueError, match="empty"):
        olp.parse_option_list("")


def test_whitespace_only_raises():
    with pytest.raises(ValueError, match="empty"):
        olp.parse_option_list("   \n\n  ")


def test_unknown_format_hint_raises():
    with pytest.raises(ValueError, match="unknown format"):
        olp.parse_option_list("a\nb", format_hint="bogus")  # type: ignore[arg-type]
