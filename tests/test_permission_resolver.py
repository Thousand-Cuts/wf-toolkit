"""Tests for skills/workfront-permissions/scripts/permission_resolver.py.

Rewritten 2026-05-18 against the Phase A empirical model:
  - coreAction enum: ADD / DELETE / EDIT / LIMITED_EDIT / VIEW (5 values)
  - AccessLevel.accessLevelPermissions is a collection of ALVPER rows
    (per-objObjCode + per-coreAction granularity)
  - AccessLevel.isAdmin=true is the System Admin gate
  - AccessRule fields: accessorID + accessorObjCode (not accessorObjID)
  - Inheritance surfaces inline via isInherited + ancestorID + ancestorObjCode
  - forbiddenActions are feature-flag denials, not coreAction subtractions
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "workfront-permissions" / "scripts"


@pytest.fixture(autouse=True)
def _on_path():
    str_scripts = str(SCRIPTS_DIR)
    if str_scripts not in sys.path:
        sys.path.insert(0, str_scripts)
    yield


@pytest.fixture
def resolver():
    sys.modules.pop("permission_resolver", None)
    return importlib.import_module("permission_resolver")


# ---------------------------------------------------------------------------
# Fixture helpers — build the Phase-A-shaped payloads

def make_user(*, active=True, user_id="u1", groups=None, teams=None, roles=None):
    return {
        "ID": user_id,
        "isActive": active,
        "accessLevelID": "al1",
        "groups": groups or [],
        "teams": teams or [],
        "roles": roles or [],
    }


def make_access_level(*, name="Standard", is_admin=False, grants=None, privileges=None, license_type=None):
    """`grants` is a list of (objObjCode, coreAction) tuples to materialise
    as ALVPER rows. `privileges` (optional) is a list of fieldAccessPrivileges
    codes — when None, the field is omitted entirely (matches the wire
    behaviour for tenants that don't populate it)."""
    alps = [
        {
            "objCode": "ALVPER",
            "objObjCode": obj,
            "coreAction": act,
            "forbiddenActions": [],
            "secondaryActions": [],
            "isAdmin": False,
        }
        for obj, act in (grants or [])
    ]
    out: dict = {
        "ID": "al1",
        "name": name,
        "isAdmin": is_admin,
        "accessLevelPermissions": alps,
    }
    if privileges is not None:
        out["fieldAccessPrivileges"] = privileges
    if license_type is not None:
        out["licenseType"] = license_type
    return out


def make_target(
    *,
    objcode="PROJ",
    object_id="p1",
    owner_id=None,
    rules=None,
):
    return {
        "ID": object_id,
        "objCode": objcode,
        "ownerID": owner_id,
        "accessRules": rules or [],
    }


def make_rule(
    *,
    accessor_id,
    accessor_objcode="USER",
    core_action="EDIT",
    forbidden=None,
    is_inherited=False,
    ancestor_id=None,
    ancestor_objcode=None,
    security_objcode="PROJ",
    security_obj_id="p1",
):
    return {
        "ID": f"rule-{accessor_id}",
        "objCode": "ACSRUL",
        "accessorID": accessor_id,
        "accessorObjCode": accessor_objcode,
        "coreAction": core_action,
        "forbiddenActions": forbidden or [],
        "isInherited": is_inherited,
        "ancestorID": ancestor_id,
        "ancestorObjCode": ancestor_objcode,
        "securityObjCode": security_objcode,
        "securityObjID": security_obj_id,
    }


# ---------------------------------------------------------------------------
# Layer 1 — User active

def test_inactive_user_short_circuits_to_deny(resolver):
    out = resolver.resolve(
        user=make_user(active=False),
        access_level=make_access_level(is_admin=True),
        target_object=make_target(),
        attempted_action="VIEW",
    )
    assert out["verdict"] == "DENY"
    assert out["reason"] == resolver.REASON_USER_INACTIVE


# ---------------------------------------------------------------------------
# Layer 2 — isAdmin bypass (new in Phase A model)

def test_is_admin_bypass_short_circuits_to_allow(resolver):
    out = resolver.resolve(
        user=make_user(),
        # isAdmin=true wins regardless of empty ALVPER collection
        access_level=make_access_level(is_admin=True, grants=[]),
        target_object=make_target(owner_id="other-user"),
        attempted_action="DELETE",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_IS_ADMIN


def test_is_admin_short_circuits_even_when_no_explicit_rule(resolver):
    # System Admin's ALVPER collection is empty; should still allow.
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(is_admin=True),
        target_object=make_target(),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "ALLOW"


# ---------------------------------------------------------------------------
# Layer 3 — Ownership

def test_owner_allowed_even_when_other_layers_deny(resolver):
    out = resolver.resolve(
        user=make_user(),
        # Access level lacks DELETE on PROJ
        access_level=make_access_level(grants=[("PROJ", "VIEW")]),
        target_object=make_target(owner_id="u1"),
        attempted_action="DELETE",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_OWNER


# ---------------------------------------------------------------------------
# Layer 5 — Access level capability (ALVPER collection traversal)

def test_deny_when_alvper_collection_lacks_objcode_action_combo(resolver):
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "VIEW")]),  # no EDIT
        target_object=make_target(
            owner_id="other",
            rules=[make_rule(accessor_id="u1", core_action="EDIT")],
        ),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "DENY"
    assert out["reason"] == resolver.REASON_ACCESS_LEVEL_LACKS_CAPABILITY


def test_alvper_exact_match_on_objobjcode_action(resolver):
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(
            grants=[("PROJ", "VIEW"), ("PROJ", "EDIT")]
        ),
        target_object=make_target(
            owner_id="other",
            rules=[make_rule(accessor_id="u1", core_action="EDIT")],
        ),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "ALLOW"


def test_add_is_a_separate_axis_from_view_edit_delete(resolver):
    # ADD must be explicitly granted; not implied by EDIT or DELETE.
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "EDIT"), ("PROJ", "DELETE")]),
        target_object=make_target(owner_id="other"),
        attempted_action="ADD",
    )
    assert out["verdict"] == "DENY"
    assert out["reason"] == resolver.REASON_ACCESS_LEVEL_LACKS_CAPABILITY


# ---------------------------------------------------------------------------
# Layers 6-9 — direct / group / team / role shares

def test_direct_user_share_grants_action(resolver):
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "EDIT")]),
        target_object=make_target(
            owner_id="other",
            rules=[make_rule(accessor_id="u1", core_action="EDIT")],
        ),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_DIRECT_SHARE


def test_group_share_grants_via_membership(resolver):
    out = resolver.resolve(
        user=make_user(groups=[{"ID": "g1"}]),
        access_level=make_access_level(grants=[("PROJ", "VIEW")]),
        target_object=make_target(
            owner_id="other",
            rules=[make_rule(
                accessor_id="g1", accessor_objcode="GROUP",
                core_action="VIEW",
            )],
        ),
        attempted_action="VIEW",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_GROUP_SHARE


def test_team_share_grants_via_membership(resolver):
    out = resolver.resolve(
        user=make_user(teams=[{"ID": "t1"}]),
        access_level=make_access_level(grants=[("TASK", "EDIT")]),
        target_object=make_target(
            objcode="TASK",
            owner_id="other",
            rules=[make_rule(
                accessor_id="t1", accessor_objcode="TEAMOB",
                core_action="EDIT", security_objcode="TASK",
            )],
        ),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_TEAM_SHARE


def test_role_share_grants_via_membership(resolver):
    out = resolver.resolve(
        user=make_user(roles=[{"ID": "r1"}]),
        access_level=make_access_level(grants=[("PROJ", "EDIT")]),
        target_object=make_target(
            owner_id="other",
            rules=[make_rule(
                accessor_id="r1", accessor_objcode="ROLE",
                core_action="EDIT",
            )],
        ),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_ROLE_SHARE


def test_rule_coreaction_must_match_exactly(resolver):
    # The matcher requires exact coreAction equality — VIEW rule does
    # NOT satisfy an EDIT request (Phase A: not strictly ordinal).
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "EDIT")]),
        target_object=make_target(
            owner_id="other",
            rules=[make_rule(accessor_id="u1", core_action="VIEW")],
        ),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "DENY"
    assert out["reason"] == resolver.REASON_NO_GRANT


# ---------------------------------------------------------------------------
# Layer 10 — Inline inheritance via isInherited

def test_inherited_rule_surfaces_inline(resolver):
    out = resolver.resolve(
        user=make_user(groups=[{"ID": "g1"}]),
        access_level=make_access_level(grants=[("PROJ", "DELETE")]),
        target_object=make_target(
            owner_id="other",
            rules=[
                make_rule(
                    accessor_id="g1", accessor_objcode="GROUP",
                    core_action="DELETE",
                    is_inherited=True,
                    ancestor_id="port-1", ancestor_objcode="PORT",
                ),
            ],
        ),
        attempted_action="DELETE",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_INHERITED
    assert out["inherited_from"] == {"objCode": "PORT", "id": "port-1"}


# ---------------------------------------------------------------------------
# forbiddenActions as feature-flag denials

def test_feature_flag_denial_when_attempted_feature_in_forbidden(resolver):
    # The rule grants EDIT, but a check for the EDIT_FINANCE feature
    # should DENY because forbiddenActions includes it.
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "EDIT")]),
        target_object=make_target(
            owner_id="other",
            rules=[make_rule(
                accessor_id="u1", core_action="EDIT",
                forbidden=["EDIT_FINANCE"],
            )],
        ),
        attempted_action="EDIT",
        attempted_feature="EDIT_FINANCE",
    )
    assert out["verdict"] == "DENY"
    assert out["reason"] == resolver.REASON_FORBIDDEN_FEATURE_FLAG


def test_feature_flag_not_in_forbidden_still_grants(resolver):
    # Same as above but feature flag isn't in forbiddenActions.
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "EDIT")]),
        target_object=make_target(
            owner_id="other",
            rules=[make_rule(
                accessor_id="u1", core_action="EDIT",
                forbidden=["EDIT_FINANCE"],
            )],
        ),
        attempted_action="EDIT",
        attempted_feature="VIEW_CONTACTINFO",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_DIRECT_SHARE


def test_no_attempted_feature_means_no_denial(resolver):
    # forbiddenActions populated, but caller didn't ask about a feature.
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "EDIT")]),
        target_object=make_target(
            owner_id="other",
            rules=[make_rule(
                accessor_id="u1", core_action="EDIT",
                forbidden=["EDIT_FINANCE"],
            )],
        ),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "ALLOW"


# ---------------------------------------------------------------------------
# Default deny + layer summary

def test_default_deny_includes_suggestions(resolver):
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "VIEW")]),
        target_object=make_target(owner_id="other"),
        attempted_action="VIEW",
    )
    assert out["verdict"] == "DENY"
    assert out["reason"] == resolver.REASON_NO_GRANT
    assert len(out["suggestions"]) >= 1


def test_layers_checked_includes_each_layer(resolver):
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "VIEW")]),
        target_object=make_target(owner_id="other"),
        attempted_action="VIEW",
    )
    layers = {l["layer"] for l in out["all_inputs_checked"]}
    assert "user_active" in layers
    assert "is_admin" in layers
    assert "owner" in layers
    assert "access_level_capability" in layers


# ---------------------------------------------------------------------------
# Cross-check: empirical enum values

def test_all_five_core_actions_supported(resolver):
    """Confirm the resolver accepts each of the 5 Phase A enum values
    without falling over."""
    for action in ["ADD", "DELETE", "EDIT", "LIMITED_EDIT", "VIEW"]:
        out = resolver.resolve(
            user=make_user(),
            access_level=make_access_level(grants=[("PROJ", action)]),
            target_object=make_target(
                owner_id="other",
                rules=[make_rule(accessor_id="u1", core_action=action)],
            ),
            attempted_action=action,
        )
        assert out["verdict"] == "ALLOW", f"action={action} failed: {out}"


# ---------------------------------------------------------------------------
# fieldAccessPrivileges decoder (v0.16.0 — surfaces the orthogonal privilege
# axis Phase A confirmed exists on AccessLevel. The empirical 18-code enum
# lives in knowledge/permissions/02-access-level-reference.md.)

def test_field_privileges_is_none_when_access_level_lacks_field(resolver):
    """Backward-compat: fixtures that don't populate fieldAccessPrivileges
    should see field_privileges=None on the verdict, not a stub dict."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "VIEW")]),  # no privileges
        target_object=make_target(owner_id="other"),
        attempted_action="VIEW",
    )
    assert out["field_privileges"] is None


def test_field_privileges_decodes_known_codes(resolver):
    """Confidently-decoded codes (financial / DE / advanced-access) show up
    with human labels."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(
            grants=[("PROJ", "VIEW")],
            privileges=["VFN", "EFN", "VDE", "EDE", "PAP"],
        ),
        target_object=make_target(owner_id="other"),
        attempted_action="VIEW",
    )
    fp = out["field_privileges"]
    assert fp is not None
    assert fp["raw"] == ["VFN", "EFN", "VDE", "EDE", "PAP"]
    decoded_codes = {d["code"] for d in fp["decoded"]}
    assert decoded_codes == {"VFN", "EFN", "VDE", "EDE", "PAP"}
    labels = {d["code"]: d["label"] for d in fp["decoded"]}
    assert "financial" in labels["VFN"]
    assert "edit" in labels["EFN"].lower()
    assert "custom-data" in labels["VDE"] or "DE" in labels["VDE"]
    assert fp["undecoded"] == []


def test_field_privileges_surfaces_undecoded_codes_separately(resolver):
    """Codes we haven't decoded yet (e.g. TAD/HAD/PRE/PDO/PCA/VPR/MGU/CPJ)
    must be visible in the verdict, not silently dropped — preserves
    honesty about Phase A's interpretation gaps."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(
            grants=[("PROJ", "VIEW")],
            privileges=["VFN", "TAD", "MGU", "ZZZ_unknown_future"],
        ),
        target_object=make_target(owner_id="other"),
        attempted_action="VIEW",
    )
    fp = out["field_privileges"]
    assert fp["raw"] == ["VFN", "TAD", "MGU", "ZZZ_unknown_future"]
    assert {d["code"] for d in fp["decoded"]} == {"VFN"}
    assert set(fp["undecoded"]) == {"TAD", "MGU", "ZZZ_unknown_future"}


def test_field_privileges_present_even_on_deny_verdicts(resolver):
    """Privileges are access-level metadata — they ride on every verdict,
    including DENYs (the auditor needs to see them when explaining why
    a user can't perform an action)."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(
            grants=[],  # no ALVPER capabilities — DENY at layer 4
            privileges=["VFN", "EFN"],
        ),
        target_object=make_target(owner_id="other"),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "DENY"
    assert out["field_privileges"] is not None
    assert out["field_privileges"]["raw"] == ["VFN", "EFN"]


def test_field_privileges_present_on_isadmin_short_circuit(resolver):
    """isAdmin levels still have a fieldAccessPrivileges field in the
    wire (Phase A: System Admin has all 18). The short-circuit at layer 2
    must not drop the privileges metadata."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(
            is_admin=True,
            privileges=["VFN", "EFN", "VDE", "EDE", "SDE", "PAP", "TAP", "IAP"],
        ),
        target_object=make_target(owner_id="other"),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_IS_ADMIN
    fp = out["field_privileges"]
    assert fp is not None
    assert len(fp["raw"]) == 8


# ---------------------------------------------------------------------------
# license_tier surfacing (v0.17.0 — surfaces AccessLevel.licenseType as
# informational metadata on every verdict, alongside field_privileges.
# Modelled as a separate axis, not a verdict constraint — empirical
# surface from Phase A is too thin to auto-DENY based on tier.)

def test_license_tier_is_none_when_access_level_lacks_field(resolver):
    """Backward-compat: fixtures that don't populate licenseType should
    see license_tier=None on the verdict."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(grants=[("PROJ", "VIEW")]),  # no license
        target_object=make_target(owner_id="other"),
        attempted_action="VIEW",
    )
    assert out["license_tier"] is None


def test_license_tier_decodes_F_with_label(resolver):
    """F is the only license code Phase A confirmed (both System Admin
    and Standard carried it on the surveyed tenant)."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(
            grants=[("PROJ", "VIEW")],
            license_type="F",
        ),
        target_object=make_target(owner_id="other"),
        attempted_action="VIEW",
    )
    lt = out["license_tier"]
    assert lt is not None
    assert lt["code"] == "F"
    assert lt["is_decoded"] is True
    assert "full" in lt["label"].lower()


def test_license_tier_surfaces_unknown_code_undecoded(resolver):
    """Unknown license codes (e.g. Light Worker / External User tiers
    not surveyed in Phase A) must surface raw with is_decoded=False —
    same honesty principle as field_privileges' undecoded[] list."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(
            grants=[("PROJ", "VIEW")],
            license_type="X_unknown_tier",
        ),
        target_object=make_target(owner_id="other"),
        attempted_action="VIEW",
    )
    lt = out["license_tier"]
    assert lt is not None
    assert lt["code"] == "X_unknown_tier"
    assert lt["is_decoded"] is False
    assert lt["label"] is None


def test_license_tier_present_on_isadmin_short_circuit(resolver):
    """isAdmin levels still have a licenseType — the layer 2 short-circuit
    must not drop the metadata."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(
            is_admin=True,
            license_type="F",
        ),
        target_object=make_target(owner_id="other"),
        attempted_action="EDIT",
    )
    assert out["verdict"] == "ALLOW"
    assert out["reason"] == resolver.REASON_IS_ADMIN
    assert out["license_tier"] is not None
    assert out["license_tier"]["code"] == "F"


def test_license_tier_does_not_constrain_verdict(resolver):
    """Surface-only — does NOT cause a DENY even if the tier is unknown.
    The empirical surface is too thin to auto-constrain; admin
    judgement applies (per knowledge/permissions/09-gotchas.md #6)."""
    out = resolver.resolve(
        user=make_user(),
        access_level=make_access_level(
            grants=[("PROJ", "VIEW")],
            license_type="X_unknown_tier",
        ),
        target_object=make_target(owner_id="other",
                                  rules=[make_rule(accessor_id="u1",
                                                   core_action="VIEW")]),
        attempted_action="VIEW",
    )
    assert out["verdict"] == "ALLOW"
    assert out["license_tier"]["is_decoded"] is False
