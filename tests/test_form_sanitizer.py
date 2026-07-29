"""Tests for skills/workfront-custom-forms/scripts/form_sanitizer.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(
    0,
    str(REPO_ROOT / "skills" / "workfront-custom-forms" / "scripts"),
)

import form_sanitizer as fs  # noqa: E402


# ---------------------------------------------------------------------------
# DROP_DEFAULT behavior

def test_strips_owner_id_at_top_level():
    payload = {
        "ID": "src-cat-1",
        "name": "Vendor Tracking",
        "ownerID": "src-user-guid",
    }
    sanitised, findings = fs.sanitise_form_payload(payload)
    assert sanitised["ownerID"] is None
    assert any(
        f["field"] == "ownerID" and f["action"] == fs.ACTION_DROP
        for f in findings
    )


def test_strips_customer_id():
    payload = {"customerID": "src-cust-guid"}
    sanitised, findings = fs.sanitise_form_payload(payload)
    assert sanitised["customerID"] is None
    assert findings[0]["field"] == "customerID"
    assert findings[0]["action"] == fs.ACTION_DROP


# ---------------------------------------------------------------------------
# REMAP_REQUIRED behavior

def test_marks_parameter_id_for_remap_in_displayLogic():
    payload = {
        "parameters": [
            {
                "ID": "src-param-1",
                "displayLogic": {
                    "operator": "AND",
                    "conditions": [
                        {"parameterID": "src-other-param", "operator": "eq", "value": "Yes"},
                    ],
                },
            }
        ]
    }
    sanitised, findings = fs.sanitise_form_payload(payload)
    assert (
        sanitised["parameters"][0]["displayLogic"]["conditions"][0]["parameterID"]
        == "<remap:src-other-param>"
    )
    paths = [f["path"] for f in findings]
    assert any("displayLogic" in p and "parameterID" in p for p in paths)
    remap_findings = [f for f in findings if f["action"] == fs.ACTION_REMAP]
    assert len(remap_findings) == 1


def test_category_id_in_nested_object_marked_for_remap():
    payload = {
        "parameters": [
            {"categoryParameter": {"categoryID": "src-cat-2"}},
        ]
    }
    sanitised, findings = fs.sanitise_form_payload(payload)
    assert (
        sanitised["parameters"][0]["categoryParameter"]["categoryID"]
        == "<remap:src-cat-2>"
    )
    assert findings[0]["action"] == fs.ACTION_REMAP


# ---------------------------------------------------------------------------
# MANUAL_REVIEW behavior

def test_home_group_id_flagged_for_review_not_modified():
    payload = {"homeGroupID": "src-grp-1"}
    sanitised, findings = fs.sanitise_form_payload(payload)
    assert sanitised["homeGroupID"] == "src-grp-1"  # unchanged
    assert findings[0]["action"] == fs.ACTION_REVIEW


def test_role_id_flagged_for_review():
    payload = {"roleID": "src-role-1"}
    _, findings = fs.sanitise_form_payload(payload)
    assert any(
        f["field"] == "roleID" and f["action"] == fs.ACTION_REVIEW
        for f in findings
    )


# ---------------------------------------------------------------------------
# DE: parity checks

def test_de_field_in_calculation_flagged_for_parity():
    payload = {
        "parameters": [
            {
                "parameterType": "COMP",
                "calculation": "{DE:Project Tier} > 5",
            }
        ]
    }
    _, findings = fs.sanitise_form_payload(payload)
    parity = [f for f in findings if f["action"] == fs.ACTION_PARITY]
    assert len(parity) == 1
    assert parity[0]["original_value"] == "DE:Project Tier"


def test_multiple_de_tokens_in_one_calculation():
    payload = {
        "parameters": [
            {
                "calculation": (
                    "IF({DE:Vendor Name}='Acme', {DE:Spend Approved} * 1.1, "
                    "{DE:Spend Approved})"
                )
            }
        ]
    }
    _, findings = fs.sanitise_form_payload(payload)
    parity = [f for f in findings if f["action"] == fs.ACTION_PARITY]
    tokens = sorted(f["original_value"] for f in parity)
    assert tokens == ["DE:Spend Approved", "DE:Vendor Name"]


def test_passthrough_tokens_dollar_dollar_not_flagged():
    payload = {
        "parameters": [{"calculation": "$$USER.ID"}],
    }
    _, findings = fs.sanitise_form_payload(payload)
    assert findings == []


# ---------------------------------------------------------------------------
# keep_ids carve-out

def test_keep_ids_short_circuits_drop_default():
    payload = {"ownerID": "keep-me"}
    sanitised, findings = fs.sanitise_form_payload(
        payload, keep_ids={"keep-me"}
    )
    assert sanitised["ownerID"] == "keep-me"
    assert findings == []


def test_keep_ids_short_circuits_remap():
    payload = {"parameters": [{"parameterID": "preserved-id"}]}
    sanitised, findings = fs.sanitise_form_payload(
        payload, keep_ids={"preserved-id"}
    )
    assert sanitised["parameters"][0]["parameterID"] == "preserved-id"
    assert findings == []


# ---------------------------------------------------------------------------
# Multi-finding scenario

def test_full_form_with_multiple_finding_types():
    payload = {
        "ID": "src-cat",
        "name": "Project Vendor Tracking",
        "objCode": "PROJ",
        "ownerID": "src-user-1",
        "customerID": "src-cust",
        "parameters": [
            {
                "ID": "src-param-1",
                "name": "Vendor",
                "parameterType": "TXT",
            },
            {
                "ID": "src-param-2",
                "name": "Spend Bucket",
                "parameterType": "COMP",
                "calculation": "{DE:Spend Approved} > 50000",
                "displayLogic": {
                    "conditions": [
                        {"parameterID": "src-param-1", "operator": "isnotblank"}
                    ]
                },
            },
        ],
    }
    sanitised, findings = fs.sanitise_form_payload(payload)

    actions = sorted({f["action"] for f in findings})
    assert fs.ACTION_DROP in actions  # ownerID + customerID
    assert fs.ACTION_REMAP in actions  # parameterID inside displayLogic
    assert fs.ACTION_PARITY in actions  # DE:Spend Approved in calculation

    drop_paths = [f["path"] for f in findings if f["action"] == fs.ACTION_DROP]
    assert "ownerID" in drop_paths
    assert "customerID" in drop_paths


# ---------------------------------------------------------------------------
# CategoryParameter composite-key handling (Phase A 2026-05-18)

def test_categoryParameter_composite_id_flagged_as_composite_remap():
    payload = {
        "categoryParameters": [
            {
                "objCode": "CTGYPA",
                "ID": "src-cat-guid_src-param-guid",
                "parameterID": "src-param-guid",
                "displayOrder": 1,
            }
        ]
    }
    sanitised, findings = fs.sanitise_form_payload(payload)
    composite_findings = [f for f in findings if f["action"] == fs.ACTION_COMPOSITE_REMAP]
    assert len(composite_findings) == 1
    assert composite_findings[0]["original_value"] == "src-cat-guid_src-param-guid"
    assert (
        sanitised["categoryParameters"][0]["ID"]
        == "<composite-remap:src-cat-guid_src-param-guid>"
    )


def test_categoryParameter_composite_decomposition_in_recommendation():
    payload = {
        "categoryParameters": [
            {"objCode": "CTGYPA", "ID": "cat-A_param-B"}
        ]
    }
    _, findings = fs.sanitise_form_payload(payload)
    rec = findings[0]["recommendation"]
    assert "categoryID='cat-A'" in rec
    assert "parameterID='param-B'" in rec


def test_non_composite_ID_on_other_objcodes_not_flagged_as_composite():
    # A plain Parameter.ID happens to contain an underscore (unlikely but
    # defensive). Should not be treated as composite-remap.
    payload = {
        "parameters": [
            {"objCode": "PARAM", "ID": "param_with_underscore"}
        ]
    }
    _, findings = fs.sanitise_form_payload(payload)
    composite_findings = [f for f in findings if f["action"] == fs.ACTION_COMPOSITE_REMAP]
    assert composite_findings == []


def test_customExpression_DE_token_flagged_for_parity():
    payload = {
        "categoryParameters": [
            {
                "objCode": "CTGYPA",
                "parameterID": "p1",
                "customExpression": "{DE:Spend Approved} > {DE:Budget Cap}"
            }
        ]
    }
    _, findings = fs.sanitise_form_payload(payload)
    parity_tokens = sorted(
        f["original_value"]
        for f in findings if f["action"] == fs.ACTION_PARITY
    )
    assert parity_tokens == ["DE:Budget Cap", "DE:Spend Approved"]


# ---------------------------------------------------------------------------
# Original tests

def test_no_findings_on_clean_payload():
    payload = {
        "ID": "src-cat",
        "name": "Clean Form",
        "objCode": "PROJ",
        "parameters": [
            {"name": "Field A", "parameterType": "TXT"},
            {"name": "Field B", "parameterType": "DATE"},
        ],
    }
    sanitised, findings = fs.sanitise_form_payload(payload)
    assert findings == []
    assert sanitised == payload  # unchanged


# ---------------------------------------------------------------------------
# partition_cascade_rules — Flow 5 clone cascade-rule remap + orphan detection

def _sample_payload_with_cascade_rules():
    """Synthetic source-environment payload mirroring a real GET /category/<id>?fields=*,categoryParameters:*,categoryCascadeRules:*,categoryCascadeRules:categoryCascadeRuleMatches:* response."""
    return {
        "ID": "src-cat",
        "name": "Vendor Tracking",
        "categoryParameters": [
            {"parameterID": "p-vendor-type", "displayOrder": 0},
            {"parameterID": "p-other-notes", "displayOrder": 1},
            {"parameterID": "p-region", "displayOrder": 2},
            {"parameterID": "p-detail", "displayOrder": 3},
        ],
        "categoryCascadeRules": [
            {
                "ID": "ctcsrl-1",
                "ruleType": "DISPLAY",
                "nextParameterID": "p-other-notes",
                "nextParameterGroupID": None,
                "otherwiseParameterID": None,
                "toEndOfForm": False,
                "categoryCascadeRuleMatches": [
                    {"ID": "ctcsrm-1a", "matchType": "EXIST", "parameterID": "p-vendor-type", "value": "Other"}
                ],
            },
            {
                "ID": "ctcsrl-2",
                "ruleType": "DISPLAY",
                "nextParameterID": "p-detail",
                "nextParameterGroupID": None,
                "otherwiseParameterID": None,
                "toEndOfForm": False,
                "categoryCascadeRuleMatches": [
                    {"ID": "ctcsrm-2a", "matchType": "EXIST", "parameterID": "p-vendor-type", "value": "Custom"},
                    {"ID": "ctcsrm-2b", "matchType": "EXIST", "parameterID": "p-region", "value": "North"},
                ],
            },
            {
                "ID": "ctcsrl-3",
                "ruleType": "DISPLAY",
                "nextParameterID": None,
                "nextParameterGroupID": None,
                "otherwiseParameterID": None,
                "toEndOfForm": True,
                "categoryCascadeRuleMatches": [
                    {"ID": "ctcsrm-3a", "matchType": "NOTEXIST", "parameterID": "p-vendor-type", "value": "Closed"}
                ],
            },
        ],
    }


def test_partition_all_rules_remap_when_all_params_kept():
    payload = _sample_payload_with_cascade_rules()
    kept_params = {"p-vendor-type", "p-other-notes", "p-region", "p-detail"}
    to_remap, orphaned = fs.partition_cascade_rules(
        payload, kept_param_source_ids=kept_params, kept_group_source_ids=set()
    )
    assert orphaned == []
    # Expect remap descriptors covering: rule 0 (1 next + 1 match), rule 1 (1 next + 2 matches), rule 2 (0 next, toEndOfForm, + 1 match)
    # That's 2 + 3 + 1 = 6 descriptors total.
    assert len(to_remap) == 6
    # All point to known source IDs.
    assert {d["source_id"] for d in to_remap} == {"p-vendor-type", "p-other-notes", "p-region", "p-detail"}


def test_partition_rule_orphaned_when_target_dropped():
    payload = _sample_payload_with_cascade_rules()
    # The admin drops p-other-notes — rule 0's nextParameterID becomes orphaned.
    kept_params = {"p-vendor-type", "p-region", "p-detail"}
    to_remap, orphaned = fs.partition_cascade_rules(
        payload, kept_param_source_ids=kept_params, kept_group_source_ids=set()
    )
    assert len(orphaned) == 1
    o = orphaned[0]
    assert o["rule_index"] == 0
    assert o["dropped_source_id"] == "p-other-notes"
    assert o["dropped_field"] == "nextParameterID"
    # Rule 0 should NOT appear in to_remap (whole rule excluded).
    assert all(d["rule_index"] != 0 for d in to_remap)


def test_partition_rule_orphaned_when_match_trigger_dropped():
    payload = _sample_payload_with_cascade_rules()
    # Drop p-region — rule 1's second match becomes orphaned, whole rule excluded.
    kept_params = {"p-vendor-type", "p-other-notes", "p-detail"}
    to_remap, orphaned = fs.partition_cascade_rules(
        payload, kept_param_source_ids=kept_params, kept_group_source_ids=set()
    )
    assert len(orphaned) == 1
    o = orphaned[0]
    assert o["rule_index"] == 1
    assert o["dropped_source_id"] == "p-region"
    assert "matches[1].parameterID" in o["dropped_field"]
    assert all(d["rule_index"] != 1 for d in to_remap)


def test_partition_multiple_orphans():
    payload = _sample_payload_with_cascade_rules()
    # Drop everything except vendor-type — every rule except rule 2 (which has only vendor-type ref) is orphaned.
    # Rule 0 needs p-other-notes (orphan). Rule 1 needs p-detail + p-region (orphan).
    # Rule 2 only references p-vendor-type (toEndOfForm, no next/otherwise) — kept.
    kept_params = {"p-vendor-type"}
    to_remap, orphaned = fs.partition_cascade_rules(
        payload, kept_param_source_ids=kept_params, kept_group_source_ids=set()
    )
    orphan_indices = sorted(o["rule_index"] for o in orphaned)
    assert orphan_indices == [0, 1]
    assert all(d["rule_index"] == 2 for d in to_remap)


def test_partition_otherwise_param_orphan():
    payload = {
        "categoryParameters": [{"parameterID": "p-trigger"}, {"parameterID": "p-target"}],
        "categoryCascadeRules": [
            {
                "ID": "r1",
                "ruleType": "DISPLAY",
                "nextParameterID": "p-target",
                "otherwiseParameterID": "p-dropped-otherwise",
                "toEndOfForm": False,
                "categoryCascadeRuleMatches": [
                    {"matchType": "EXIST", "parameterID": "p-trigger", "value": "X"}
                ],
            }
        ],
    }
    to_remap, orphaned = fs.partition_cascade_rules(
        payload, kept_param_source_ids={"p-trigger", "p-target"}, kept_group_source_ids=set()
    )
    assert len(orphaned) == 1
    assert orphaned[0]["dropped_field"] == "otherwiseParameterID"
    assert orphaned[0]["dropped_source_id"] == "p-dropped-otherwise"


def test_partition_group_ref_kept():
    payload = {
        "categoryParameters": [{"parameterID": "p-trigger"}],
        "categoryCascadeRules": [
            {
                "ID": "r1",
                "ruleType": "DISPLAY",
                "nextParameterID": None,
                "nextParameterGroupID": "g-section-2",
                "toEndOfForm": False,
                "categoryCascadeRuleMatches": [
                    {"matchType": "EXIST", "parameterID": "p-trigger", "value": "X"}
                ],
            }
        ],
    }
    to_remap, orphaned = fs.partition_cascade_rules(
        payload,
        kept_param_source_ids={"p-trigger"},
        kept_group_source_ids={"g-section-2"},
    )
    assert orphaned == []
    fields_remapped = {d["field"] for d in to_remap}
    assert "nextParameterGroupID" in fields_remapped


def test_partition_no_cascade_rules_returns_empty():
    payload = {"ID": "src", "categoryParameters": [], "categoryCascadeRules": []}
    to_remap, orphaned = fs.partition_cascade_rules(
        payload, kept_param_source_ids=set(), kept_group_source_ids=set()
    )
    assert to_remap == []
    assert orphaned == []


def test_partition_missing_collection_returns_empty():
    # No categoryCascadeRules key at all — common when GET didn't request it.
    payload = {"ID": "src", "categoryParameters": []}
    to_remap, orphaned = fs.partition_cascade_rules(
        payload, kept_param_source_ids=set(), kept_group_source_ids=set()
    )
    assert to_remap == []
    assert orphaned == []
