"""Parse user-supplied dropdown option lists into normalised records.

Supports four input modes:
  - 'lines'           one option per line; label == value
  - 'csv'             header row required; columns: label, [value], [displayOrder], [isHidden]
  - 'tsv'             same as csv, tab-separated
  - 'comma'           single-line comma-separated labels
  - 'label_eq_value'  one per line, 'label = value' format

Format autodetected unless an explicit `format_hint` is supplied.

The output of `parse_option_list()` feeds directly into the bulk POST body
described in `knowledge/custom-forms/03-create-form-recipe.md`:

    updates=[{"parameterID": "...", "label": "...", "value": "...",
              "displayOrder": N}, ...]
"""

from __future__ import annotations

import csv
import io
import re
from typing import Literal

FormatHint = Literal["lines", "csv", "tsv", "comma", "label_eq_value"]


def parse_option_list(
    input_text: str,
    *,
    format_hint: FormatHint | None = None,
) -> list[dict]:
    """Parse `input_text` into a list of option dicts.

    Each dict has keys: `label`, `value`, `displayOrder`, and optionally
    `isHidden`. Default `value` is the label; default `displayOrder` is the
    1-based row index.

    Raises ValueError on empty / malformed input.
    """
    text = (input_text or "").strip()
    if not text:
        raise ValueError("input is empty")

    fmt = format_hint or _detect_format(text)

    if fmt == "csv":
        return _parse_delimited(text, delimiter=",")
    if fmt == "tsv":
        return _parse_delimited(text, delimiter="\t")
    if fmt == "label_eq_value":
        return _parse_label_eq_value(text)
    if fmt == "comma":
        return _parse_comma(text)
    if fmt == "lines":
        return _parse_lines(text)

    raise ValueError(f"unknown format: {fmt}")


def _detect_format(text: str) -> FormatHint:
    first_line = text.split("\n", 1)[0]
    if "," in first_line and "label" in first_line.lower():
        return "csv"
    if "\t" in first_line and "label" in first_line.lower():
        return "tsv"
    if any(" = " in line for line in text.split("\n")):
        return "label_eq_value"
    if "\n" not in text and "," in text:
        return "comma"
    return "lines"


def _parse_lines(text: str) -> list[dict]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        raise ValueError("no non-empty lines")
    return [
        {"label": line, "value": line, "displayOrder": i + 1}
        for i, line in enumerate(lines)
    ]


def _parse_comma(text: str) -> list[dict]:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        raise ValueError("no non-empty comma-separated values")
    return [
        {"label": p, "value": p, "displayOrder": i + 1}
        for i, p in enumerate(parts)
    ]


def _parse_label_eq_value(text: str) -> list[dict]:
    options = []
    for i, raw in enumerate(text.split("\n")):
        line = raw.strip()
        if not line:
            continue
        if " = " not in line:
            raise ValueError(
                f"line {i + 1} missing ' = ' separator: {line!r}"
            )
        label, value = line.split(" = ", 1)
        options.append({
            "label": label.strip(),
            "value": value.strip(),
            "displayOrder": len(options) + 1,
        })
    if not options:
        raise ValueError("no label = value lines found")
    return options


def _parse_delimited(text: str, *, delimiter: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fieldnames = reader.fieldnames or []
    lowered = [f.lower() for f in fieldnames]
    if "label" not in lowered:
        raise ValueError(
            f"header row must include 'label' column; got {fieldnames!r}"
        )

    field_map = {f.lower(): f for f in fieldnames}
    label_field = field_map["label"]
    value_field = field_map.get("value")
    display_order_field = field_map.get("displayorder")
    is_hidden_field = field_map.get("ishidden")

    options: list[dict] = []
    for i, row in enumerate(reader):
        label = (row.get(label_field) or "").strip()
        if not label:
            raise ValueError(f"row {i + 1} has empty label")
        value = (
            (row.get(value_field) or "").strip()
            if value_field
            else label
        ) or label
        display_order = i + 1
        if display_order_field:
            raw_order = (row.get(display_order_field) or "").strip()
            if raw_order:
                if not re.fullmatch(r"-?\d+", raw_order):
                    raise ValueError(
                        f"row {i + 1} has non-integer displayOrder: "
                        f"{raw_order!r}"
                    )
                display_order = int(raw_order)
        opt = {
            "label": label,
            "value": value,
            "displayOrder": display_order,
        }
        if is_hidden_field:
            raw_hidden = (row.get(is_hidden_field) or "").strip().lower()
            if raw_hidden in ("true", "1", "yes"):
                opt["isHidden"] = True
        options.append(opt)

    if not options:
        raise ValueError("no data rows found")
    return options
