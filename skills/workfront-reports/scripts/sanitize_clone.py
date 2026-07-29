#!/usr/bin/env python3
"""Sanitise a cloned Workfront report payload for cross-tenant transfer (v0.9.0).

Input shape: a dict with optional keys `report`, `uift`, `uigb`, `uivw`, each holding
the JSON object returned by the corresponding GET (with `definition` field as a JSON
object, NOT a text-mode string).

Output: 5-bucket walker report.
    {
      "strip":        [{ "key": "<dotted path>", "value": "<...>" }, ...],
      "prompt":       [{ "key": "...", "value": "...", "reason": "..." }, ...],
      "parity_check": [{ "field": "<DE name>", "uiObjCode": "<code>",
                         "source_form": "<form name if known>" }, ...],
      "host_rewrite": [{ "path": "<dotted path>",
                         "url": "<the hardcoded URL>",
                         "source_host": "<extracted hostname>" }, ...],
      "cleaned":      <payload with strip items removed; prompt/host_rewrite
                       items kept pending user decision>
    }
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

AUTO_STRIP_KEYS = frozenset({
    "customerID", "preferenceID", "securityRootID", "appGlobalID",
    "objID", "modDate", "lastUpdateDate", "globalUIKey", "extRefID"
})

PROMPT_TENANT_LOCAL_KEYS = frozenset({
    "ownerID", "categoryID", "homeGroupID", "userID", "groupID",
    "teamID", "roleID", "enteredByID", "lastUpdatedByID",
    "scheduledReportID", "reportFolderID", "runAsUserID",
    "publicRunAsUserID", "templateID"
})

GUID_RE = re.compile(r"\b[0-9a-f]{32}\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
DE_RE = re.compile(r"DE:([^\n=&]+?)(?=$|\n|&|_Mod$)")
DOLLAR_TOKEN_RE = re.compile(r"\$\$[A-Z_][A-Z_0-9.+\-]*[dy]?")
WF_HOST_URL_RE = re.compile(
    r"https?://([a-z][a-z0-9\-]+(?:\.sb\d+)?\.(?:preview\.|my\.)?workfront\.com)/[^\s\"'<>]*",
    re.IGNORECASE
)
STATIC_PATH_RE = re.compile(r"/static/[^\s\"'<>]+")

# OR:<n>: and EXISTS:<letter>: prefix patterns
PREFIX_RE = re.compile(r"^(?:OR:\d+:|EXISTS:[a-z]:)")

# Control keys inside EXISTS blocks — always valid, never prompted
EXISTS_CONTROL = frozenset({"$$EXISTSMOD", "$$OBJCODE", "$$ID"})


def _is_session_token(value: Any) -> bool:
    """Pass-through: $$USER.*, $$TODAY+/-Nd, $$NOW, $$EXISTSMOD, $$OBJCODE, etc."""
    return isinstance(value, str) and value.startswith("$$")


def _strip_filter_prefix(key: str) -> tuple[str, str]:
    """Strip OR:<n>: or EXISTS:<letter>: prefix. Returns (prefix, remainder)."""
    m = PREFIX_RE.match(key)
    if m:
        return m.group(0), key[m.end():]
    return "", key


def _strip_de_prefix(key: str) -> tuple[bool, str]:
    """Strip DE: prefix. Returns (had_prefix, remainder-without-DE-without-_Mod)."""
    s = key
    if s.endswith("_Mod"):
        s = s[:-4]
    if s.startswith("DE:"):
        return True, s[3:]
    return False, s


def _walk_record(record: dict, prefix: str,
                 strip: list, prompt: list) -> dict:
    cleaned = {}
    for key, value in record.items():
        path = f"{prefix}.{key}"
        if key == "definition":
            # definition is handled separately by _walk_definition
            cleaned[key] = value
            continue
        if key in AUTO_STRIP_KEYS:
            strip.append({"key": path, "value": value})
            continue
        if key in PROMPT_TENANT_LOCAL_KEYS:
            if value not in (None, "", 0, False):
                prompt.append({
                    "key": path, "value": value,
                    "reason": "tenant-local reference — may not exist on destination"
                })
            cleaned[key] = value
            continue
        if isinstance(key, str) and key.endswith("ID") and isinstance(value, str) and value:
            prompt.append({
                "key": path, "value": value,
                "reason": "unknown ID field — may not exist on destination"
            })
            cleaned[key] = value
            continue
        cleaned[key] = value
    return cleaned


def _walk_filter_definition(defn: dict, prefix: str, uiObjCode: str,
                            prompt: list, parity: list,
                            host_rewrites: list) -> None:
    """UIFT.definition is a flat {string: string} map (plus OR:/EXISTS: prefixed keys)."""
    if not isinstance(defn, dict):
        return
    for key, value in defn.items():
        if not isinstance(key, str) or key == "":
            continue
        # Strip OR:/EXISTS: prefix
        wrap_prefix, inner_key = _strip_filter_prefix(key)
        # EXISTS control keys are always valid
        if wrap_prefix.startswith("EXISTS:"):
            # Strip the EXISTS:<letter>: prefix to check if it's a control key
            if inner_key in EXISTS_CONTROL:
                continue
        # Skip _Mod sibling keys (they're handled with their base key)
        if inner_key.endswith("_Mod"):
            continue
        # DE: parity check
        has_de, base_field = _strip_de_prefix(inner_key)
        if has_de:
            _add_parity(parity, base_field, uiObjCode)
            # also check value for non-session non-empty patterns:
            _scan_filter_value(value, f"{prefix}.{key}", prompt, host_rewrites)
            continue
        # Check the value for hard-coded GUIDs, dates, host URLs, etc.
        _scan_filter_value(value, f"{prefix}.{key}", prompt, host_rewrites)


def _scan_filter_value(value: Any, path: str,
                       prompt: list, host_rewrites: list) -> None:
    if not isinstance(value, str):
        return
    if _is_session_token(value):
        return
    # Hard-coded GUID
    for guid in sorted(set(GUID_RE.findall(value))):
        prompt.append({"key": path, "value": guid,
                       "reason": "hardcoded GUID — likely source-environment ID"})
    # Hard-coded date (after masking $$ tokens)
    masked = DOLLAR_TOKEN_RE.sub("", value)
    for date in sorted(set(DATE_RE.findall(masked))):
        prompt.append({"key": path, "value": date,
                       "reason": "hardcoded date — carries source-environment timezone interpretation"})
    # Host URL
    for m in WF_HOST_URL_RE.finditer(value):
        host_rewrites.append({"path": path, "url": m.group(0),
                              "source_host": m.group(1)})


# Free-text DE: scanner — DE_RE is tuned for filter-map keys (stops at &/=/_Mod);
# inline prose needs to stop at sentence punctuation and conjunctions too.
_DE_TEXT_RE = re.compile(r"DE:([A-Za-z0-9_][A-Za-z0-9_ \-]*?)(?=[.,;:!?\n]|\s+(?:and|or|to|on|in|for|with|by|the|a|an)\b|\s*$)", re.IGNORECASE)


def _scan_text_for_de_refs(text: str, uiObjCode: str, parity: list) -> None:
    if not isinstance(text, str) or not text:
        return
    for raw in _DE_TEXT_RE.findall(text):
        # Trim trailing whitespace/punctuation that the regex doesn't catch
        name = raw.rstrip(" \t.,;:!?")
        _add_parity(parity, name, uiObjCode)


def _walk_view_definition(defn: dict, prefix: str, uiObjCode: str,
                          parity: list, host_rewrites: list) -> None:
    """UIVW.definition: {column[], row[], property}."""
    if not isinstance(defn, dict):
        return
    for col_idx, col in enumerate(defn.get("column", [])):
        col_path = f"{prefix}.definition.column[{col_idx}]"
        _walk_column(col, col_path, uiObjCode, parity, host_rewrites)
    for row_idx, row in enumerate(defn.get("row", [])):
        row_path = f"{prefix}.definition.row[{row_idx}]"
        _walk_row(row, row_path, uiObjCode, parity, host_rewrites)


def _walk_column(col: dict, path: str, uiObjCode: str,
                 parity: list, host_rewrites: list) -> None:
    if not isinstance(col, dict):
        return
    # valuefield: bare DE: name (asymmetry — UIVW column drops DE: prefix)
    vf = col.get("valuefield")
    if isinstance(vf, str) and vf and ":" not in vf and not vf.startswith("$$"):
        # Heuristic: if it has spaces or starts with a capital, treat as DE: ref
        if " " in vf or (vf[0].isupper() and vf not in _BUILTIN_NO_DE):
            _add_parity(parity, vf, uiObjCode)
    # querysort: DE: prefix KEPT
    qs = col.get("querysort")
    if isinstance(qs, str) and qs.startswith("DE:"):
        _add_parity(parity, qs[3:], uiObjCode)
    # aggregator.valuefield: DE: prefix KEPT
    agg = col.get("aggregator")
    if isinstance(agg, dict):
        agg_vf = agg.get("valuefield")
        if isinstance(agg_vf, str) and agg_vf.startswith("DE:"):
            _add_parity(parity, agg_vf[3:], uiObjCode)
    # valueexpression: scan for host URLs
    ve = col.get("valueexpression")
    if isinstance(ve, str):
        for m in WF_HOST_URL_RE.finditer(ve):
            host_rewrites.append({"path": f"{path}.valueexpression",
                                  "url": m.group(0),
                                  "source_host": m.group(1)})
    # image.case[].comparison.truetext: scan for static asset paths + URLs
    image = col.get("image")
    if isinstance(image, dict):
        for case_idx, case_entry in enumerate(image.get("case", [])):
            comp = case_entry.get("comparison", {}) if isinstance(case_entry, dict) else {}
            tt = comp.get("truetext")
            if isinstance(tt, str):
                if STATIC_PATH_RE.match(tt):
                    host_rewrites.append({
                        "path": f"{path}.image.case[{case_idx}].comparison.truetext",
                        "url": tt, "source_host": None
                    })
                for m in WF_HOST_URL_RE.finditer(tt):
                    host_rewrites.append({
                        "path": f"{path}.image.case[{case_idx}].comparison.truetext",
                        "url": m.group(0), "source_host": m.group(1)
                    })


def _walk_row(row: dict, path: str, uiObjCode: str,
              parity: list, host_rewrites: list) -> None:
    # Same scanning as a column — row[]-level styledefs may reference DE: fields
    if isinstance(row, dict):
        styledef = row.get("styledef")
        if isinstance(styledef, dict):
            for case_idx, case_entry in enumerate(styledef.get("case", [])):
                comp = case_entry.get("comparison", {}) if isinstance(case_entry, dict) else {}
                lm = comp.get("leftmethod")
                if isinstance(lm, str) and lm.startswith("DE:"):
                    _add_parity(parity, lm[3:], uiObjCode)


def _walk_group_definition(defn: dict, prefix: str, uiObjCode: str,
                           parity: list) -> None:
    """UIGB.definition: {group[], textmode}."""
    if not isinstance(defn, dict):
        return
    for grp_idx, grp in enumerate(defn.get("group", [])):
        if not isinstance(grp, dict):
            continue
        # group.valuefield: DE: DROPPED — bare name is a DE: ref
        vf = grp.get("valuefield")
        if isinstance(vf, str) and vf and ":" not in vf and not vf.startswith("$$"):
            if " " in vf or (vf[0].isupper() and vf not in _BUILTIN_NO_DE):
                _add_parity(parity, vf, uiObjCode)


_BUILTIN_NO_DE = frozenset({
    "ID", "name", "status", "priority", "condition", "owner", "portfolio", "program",
    "project", "task", "template", "parent", "milestone", "objCode", "objID",
    "hours", "actualCompletionDate", "plannedCompletionDate", "actualStartDate",
    "plannedStartDate", "percentComplete", "referenceNumber", "displayName"
})


def _add_parity(parity: list, field_name: str, uiObjCode: str) -> None:
    name = field_name.strip()
    if not name:
        return
    # dedupe by field name across all locations — one parity check per unique DE: name
    for existing in parity:
        if existing.get("field") == name:
            # promote uiObjCode if previously unknown
            if not existing.get("uiObjCode") and uiObjCode:
                existing["uiObjCode"] = uiObjCode
            return
    parity.append({"field": name, "uiObjCode": uiObjCode})


def sanitise(payload: dict) -> dict:
    strip: list = []
    prompt: list = []
    parity: list = []
    host_rewrites: list = []
    cleaned: dict = {}

    for obj_code in ("report", "uift", "uigb", "uivw"):
        if obj_code not in payload:
            continue
        record = payload[obj_code]
        if record is None or not isinstance(record, dict):
            continue
        # Walk top-level fields (strips / prompts)
        cleaned_record = _walk_record(record, obj_code, strip, prompt)
        # Walk the definition object (parity / host_rewrite / additional prompts)
        defn = record.get("definition") or {}
        uiObjCode = record.get("uiObjCode", "")
        if obj_code == "uift":
            _walk_filter_definition(defn, obj_code, uiObjCode, prompt, parity, host_rewrites)
        elif obj_code == "uigb":
            _walk_group_definition(defn, obj_code, uiObjCode, parity)
        elif obj_code == "uivw":
            _walk_view_definition(defn, obj_code, uiObjCode, parity, host_rewrites)
        cleaned[obj_code] = cleaned_record

    # E2: scan report.description for inline DE: references
    report_record = payload.get("report") or {}
    if isinstance(report_record, dict):
        _scan_text_for_de_refs(
            report_record.get("description") or "",
            report_record.get("uiObjCode", ""),
            parity,
        )

    return {
        "strip": strip,
        "prompt": prompt,
        "parity_check": parity,
        "host_rewrite": host_rewrites,
        "cleaned": cleaned,
    }


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-stdin", action="store_true", required=True,
                   help="read source payload JSON from stdin")
    p.parse_args()
    payload = json.loads(sys.stdin.read())
    result = sanitise(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
