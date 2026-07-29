"""Cross-environment form payload sanitiser.

Walks a source-environment Category payload (with nested Parameters,
ParameterGroups, ParameterOptions, displayLogic) and produces:

  - a sanitised copy with tenant-specific identifiers stripped or marked
    for remap
  - a list of findings describing each identifier flagged, what action
    was taken, and what the operator should do next

Pure function. Makes no API calls. Knowledge of which destination-tenant
IDs are appropriate replacements is the caller's responsibility — the
sanitiser only surfaces what's tenant-specific in the source.

Used by Flow 5 (clone-and-adapt) in `knowledge/custom-forms/06-clone-and-adapt-recipe.md`.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

# ---------------------------------------------------------------------------
# Field-name classification.
#
# DROP_DEFAULT: fields representing tenant-specific identity that almost
#               never have a meaningful destination-tenant equivalent. Set
#               to None on the sanitised payload.
# REMAP_REQUIRED: fields representing IDs that the destination tenant
#                 typically does have an equivalent of but only the
#                 operator can supply (categoryID, parameterID for
#                 displayLogic references, etc.). Replaced with a
#                 `<remap:...>` placeholder so the failure mode is loud.
# MANUAL_REVIEW: fields that might be legitimate to carry over (a roleID
#                that exists on both tenants) or might not. Left as-is in
#                the payload but flagged so the operator decides.

DROP_DEFAULT_FIELDS = frozenset({
    "customerID",
    "enteredByID",
    "ownerID",
    "createdByID",
    "lastUpdatedByID",
})

REMAP_REQUIRED_FIELDS = frozenset({
    "categoryID",
    "parameterID",
    "parameterGroupID",
})

MANUAL_REVIEW_FIELDS = frozenset({
    "homeGroupID",
    "roleID",
    "groupID",
    "teamID",
})

# Field names whose string values may contain `DE:FieldName` references
# that need destination-tenant parity checks. Phase A 2026-05-18:
# `calculation` was a v0 guess — the real field is `customExpression` on
# CategoryParameter rows. Both names are kept for back-compat; the real
# one is `customExpression`.
DE_BEARING_FIELDS = frozenset({
    "calculation",
    "calculationDisplay",
    "customExpression",
    "rawCustomExpression",
    "displayLogic",
    "value",
    "valueExpression",
})

# Composite-key fields — CategoryParameter.ID is `<categoryID>_<parameterID>`.
# Phase A 2026-05-18 finding: CTGYPA composite IDs don't transfer cross-tenant.
# Treat them like REMAP_REQUIRED but flag distinctly so the operator knows
# both halves of the composite need fresh destination IDs.
COMPOSITE_KEY_FIELDS = frozenset({
    "ID",  # ONLY when the parent dict's objCode is CTGYPA
})

ACTION_COMPOSITE_REMAP = "composite_remap_required"

ACTION_DROP = "drop_default"
ACTION_REMAP = "remap_required"
ACTION_REVIEW = "manual_review"
ACTION_PARITY = "parity_check_required"
# ACTION_COMPOSITE_REMAP defined above near COMPOSITE_KEY_FIELDS.

# Tokens that are intentionally tenant-neutral and pass through untouched.
PASSTHROUGH_TOKENS = ("$$USER", "$$TODAY", "$$NOW", "$$HOST")

_DE_TOKEN_RE = re.compile(r"DE:[A-Za-z0-9 _\-]+?(?=$|[^A-Za-z0-9 _\-])")


def sanitise_form_payload(
    source_payload: dict,
    *,
    destination_schema: dict | None = None,
    keep_ids: set[str] | None = None,
) -> tuple[dict, list[dict]]:
    """Return `(sanitised_payload, findings)`.

    `sanitised_payload` is a deep-copy of `source_payload` with:
      - DROP_DEFAULT fields set to None
      - REMAP_REQUIRED fields replaced with `<remap:<original-value>>`
      - everything else left structurally intact

    `findings` is a list of dicts:
      {
        "path": "parameters[2].displayLogic.conditions[0].parameterID",
        "field": "parameterID",
        "original_value": "<guid>",
        "action": ACTION_REMAP,
        "recommendation": "<operator-facing hint>",
      }

    `destination_schema` is currently unused but reserved: future versions
    may use it to drop fields that don't exist on the destination tenant's
    metadata, rather than asking the operator. Out of scope for v1.
    """
    keep_ids = set(keep_ids or ())
    payload = deepcopy(source_payload)
    findings: list[dict] = []

    _walk(payload, path="", findings=findings, keep_ids=keep_ids)
    return payload, findings


def _walk(
    node: Any,
    *,
    path: str,
    findings: list[dict],
    keep_ids: set[str],
) -> None:
    if isinstance(node, dict):
        for key, value in list(node.items()):
            sub_path = f"{path}.{key}" if path else key
            if isinstance(value, str):
                _check_string_field(
                    node=node, key=key, value=value, path=sub_path,
                    findings=findings, keep_ids=keep_ids,
                )
            elif isinstance(value, (dict, list)):
                _walk(value, path=sub_path, findings=findings, keep_ids=keep_ids)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk(
                item,
                path=f"{path}[{i}]",
                findings=findings,
                keep_ids=keep_ids,
            )


def _check_string_field(
    *,
    node: dict,
    key: str,
    value: str,
    path: str,
    findings: list[dict],
    keep_ids: set[str],
) -> None:
    if value in keep_ids:
        return

    # CategoryParameter composite-ID detection. CTGYPA.ID has the shape
    # `<categoryID>_<parameterID>` — neither half transfers cross-tenant,
    # and the composite key cannot be supplied directly on write (the link
    # is created via the PUT-on-Category nested categoryParameters
    # collection, not via direct POST). Surface the composite explicitly.
    if key == "ID" and node.get("objCode") == "CTGYPA" and "_" in value:
        try:
            src_cat, src_param = value.split("_", 1)
        except ValueError:
            src_cat, src_param = "", ""
        findings.append({
            "path": path,
            "field": key,
            "original_value": value,
            "action": ACTION_COMPOSITE_REMAP,
            "recommendation": (
                "CategoryParameter composite ID. Source decomposes into "
                f"categoryID={src_cat!r} + parameterID={src_param!r}. "
                "Neither half exists on destination. On write, this row "
                "is created by PUTting categoryParameters:[...] on the "
                "destination Category — the composite ID is auto-assigned."
            ),
        })
        node[key] = f"<composite-remap:{value}>"
        return

    if key in DROP_DEFAULT_FIELDS:
        findings.append({
            "path": path,
            "field": key,
            "original_value": value,
            "action": ACTION_DROP,
            "recommendation": (
                "Dropping by default — this field is tenant-specific user "
                "or customer identity and cannot be carried across."
            ),
        })
        node[key] = None
        return

    if key in REMAP_REQUIRED_FIELDS:
        findings.append({
            "path": path,
            "field": key,
            "original_value": value,
            "action": ACTION_REMAP,
            "recommendation": (
                "Cross-tenant ID — supply destination equivalent before "
                "write or this reference will break."
            ),
        })
        node[key] = f"<remap:{value}>"
        return

    if key in MANUAL_REVIEW_FIELDS:
        findings.append({
            "path": path,
            "field": key,
            "original_value": value,
            "action": ACTION_REVIEW,
            "recommendation": (
                "Tenant-specific reference — confirm a destination "
                "equivalent exists or drop the reference."
            ),
        })
        return

    if key in DE_BEARING_FIELDS:
        # Skip tenant-neutral pass-through tokens entirely.
        if any(token in value for token in PASSTHROUGH_TOKENS) and not _DE_TOKEN_RE.search(value):
            return
        for token in _extract_de_tokens(value):
            findings.append({
                "path": path,
                "field": key,
                "original_value": token,
                "action": ACTION_PARITY,
                "recommendation": (
                    f"Confirm '{token}' exists on destination tenant "
                    "before write."
                ),
            })


# ---------------------------------------------------------------------------
# Cascade-rule partition (Flow 5 clone).
#
# v0.26.0 addition. The clone flow needs to know, for each CTCSRL in the
# source payload's `categoryCascadeRules` collection:
#
#   (a) which source-environment IDs appear in fields that the writer will need
#       to substitute after the destination Category + Parameters exist
#       (`nextParameterID`, `nextParameterGroupID`, `otherwiseParameterID`,
#       plus every `categoryCascadeRuleMatches[].parameterID`)
#
#   (b) which rules can no longer be cloned because a Parameter or
#       ParameterGroup they reference is being dropped during sanitization
#       or operator-side modification
#
# `partition_cascade_rules()` is told which source param/group IDs are
# being kept and returns the two buckets the spec calls `to_remap` and
# `orphaned`. Pure function; no API calls. Whole-rule policy: if ANY
# field on a rule references a dropped ID, the entire rule is orphaned
# (not partially cloned with broken matches).


def partition_cascade_rules(
    source_payload: dict,
    *,
    kept_param_source_ids: set[str],
    kept_group_source_ids: set[str],
) -> tuple[list[dict], list[dict]]:
    """Split source-payload cascade rules into (to_remap, orphaned).

    `to_remap` entries describe one field-substitution each:
        {
            "rule_index":  int,             # index in categoryCascadeRules
            "field":       str,             # "nextParameterID" | "nextParameterGroupID"
                                            #  | "otherwiseParameterID"
                                            #  | "matches[N].parameterID"
            "source_id":   str,
            "match_index": int | None,      # set only for match-level fields
        }

    `orphaned` entries describe one dropped rule. If multiple references
    inside a rule are dropped, only the FIRST one encountered is reported
    (good enough for the operator-facing warning; the underlying source
    rule is preserved in the clone-report artifact regardless).
        {
            "rule_index":         int,
            "dropped_field":      str,      # same vocabulary as `field`
            "dropped_source_id":  str,
            "reason":             str,      # human-readable
        }
    """
    rules = source_payload.get("categoryCascadeRules") or []
    to_remap: list[dict] = []
    orphaned: list[dict] = []

    for rule_index, rule in enumerate(rules):
        # Collect all ID references in this rule first, then decide whole-rule
        # status. Order of fields scanned: nextParameterID, nextParameterGroupID,
        # otherwiseParameterID, matches[N].parameterID.
        rule_refs: list[dict] = []  # one entry per ID reference

        next_param = rule.get("nextParameterID")
        if next_param:
            rule_refs.append({
                "field": "nextParameterID",
                "source_id": next_param,
                "match_index": None,
                "kept": next_param in kept_param_source_ids,
            })

        next_group = rule.get("nextParameterGroupID")
        if next_group:
            rule_refs.append({
                "field": "nextParameterGroupID",
                "source_id": next_group,
                "match_index": None,
                "kept": next_group in kept_group_source_ids,
            })

        otherwise = rule.get("otherwiseParameterID")
        if otherwise:
            rule_refs.append({
                "field": "otherwiseParameterID",
                "source_id": otherwise,
                "match_index": None,
                "kept": otherwise in kept_param_source_ids,
            })

        matches = rule.get("categoryCascadeRuleMatches") or []
        for match_index, match in enumerate(matches):
            match_param = match.get("parameterID")
            if match_param:
                rule_refs.append({
                    "field": f"matches[{match_index}].parameterID",
                    "source_id": match_param,
                    "match_index": match_index,
                    "kept": match_param in kept_param_source_ids,
                })

        # Whole-rule orphan check.
        first_drop = next((r for r in rule_refs if not r["kept"]), None)
        if first_drop is not None:
            orphaned.append({
                "rule_index": rule_index,
                "dropped_field": first_drop["field"],
                "dropped_source_id": first_drop["source_id"],
                "reason": (
                    f"Rule {rule_index} references source ID "
                    f"{first_drop['source_id']!r} in {first_drop['field']}; "
                    "that Parameter or ParameterGroup is not in the destination plan."
                ),
            })
            continue

        # All refs kept — emit remap descriptors.
        for ref in rule_refs:
            to_remap.append({
                "rule_index": rule_index,
                "field": ref["field"],
                "source_id": ref["source_id"],
                "match_index": ref["match_index"],
            })

    return to_remap, orphaned


def _extract_de_tokens(text: str) -> list[str]:
    """Find DE:FieldName tokens. Returns each unique match in source order."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _DE_TOKEN_RE.finditer(text):
        token = match.group(0).rstrip()
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out
