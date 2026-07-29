"""The 6-input permission combiner — rewritten 2026-05-18 against
Phase A empirical findings; layer 4 (system-wide override) removed
2026-05-19 after Finding 7 (HAR capture #6) disproved that layer's
existence in modern v17.0 Workfront.

Given a user, target object, and access level (with its ALVPER
permission collection populated), return a structured verdict
explaining whether the user can perform `attempted_action` on the
target object — and **why**.

Pure function. Makes no API calls. The caller is responsible for
pre-fetching everything via the Workfront REST API (using the wrappers
in skills/workfront-api/scripts/ and the audit recipes in
knowledge/permissions/05-audit-recipes.md).

Empirical model (Phase A 2026-05-18):

- `coreAction` enum is: `ADD`, `DELETE`, `EDIT`, `LIMITED_EDIT`, `VIEW`.
  Neither `CONTRIBUTE` nor `MANAGE` exist on real Workfront tenants.
- `ADD` is a separate axis from VIEW→LIMITED_EDIT→EDIT→DELETE — it
  represents "can create new objects of this type" rather than a
  rank on the read/write ladder.
- `AccessLevel.accessLevelPermissions` is a **collection** of `ALVPER`
  rows, one per `(objObjCode, coreAction)` granted combination.
  Not a flat dict. Standard access level has ~92 ALVPER rows.
- `AccessLevel.isAdmin=true` short-circuits all per-object capability
  checks — System Admin's ALVPER collection is empty by design.
- `AccessRule.accessorID` + `accessorObjCode` (not `accessorObjID`).
- `AccessRule.isInherited` + `ancestorID` + `ancestorObjCode` surface
  inheritance INLINE — explicit parent-walking is optional fallback.
- `forbiddenActions` are **feature-flag denials** at a different
  granularity than `coreAction`. They name specific UI features that
  can be denied (e.g. `EDIT_FINANCE`, `SHARE_SYSTEMWIDE`) even when
  `coreAction` grants the broader action.
- **No tenant-wide visibility override layer.** The "users can see all
  projects" / "users see only their own data" toggles modelled in
  v0.14.x do not appear to exist as discoverable settings in modern
  v17.0. See knowledge/permissions/07-system-wide-overrides.md.

Precedence (most permissive layer wins, except for short-circuits):

  1. user.isActive            — short-circuit DENY if False
  2. accessLevel.isAdmin       — short-circuit ALLOW if True
  3. ownership                 — short-circuit ALLOW if user owns the object
  4. access-level capability   — DENY if no ALVPER row for (objObjCode, action)
  5. direct AccessRule         — ALLOW if a USER-accessor rule grants the action
  6. group AccessRule          — ALLOW via any group membership
  7. team AccessRule           — same for teams
  8. role AccessRule           — same for roles
  9. inline-inherited rules    — same matcher; uses isInherited+ancestorID
  10. default                  — DENY with a summary of all layers checked

This module is fixture-tested via tests/test_permission_resolver.py.
"""

from __future__ import annotations

from typing import Any, Literal

# Empirical Phase A enum (live-tenant survey 2026-05-18, 393 ALVPER rows).
CoreAction = Literal["ADD", "DELETE", "EDIT", "LIMITED_EDIT", "VIEW"]

# fieldAccessPrivileges decoder. The 18 codes come from the Phase A survey
# (capture #6, 2026-05-18 — see
# knowledge/permissions/07-system-wide-overrides.md). Decoded with
# varying confidence; codes lacking a label
# fall through as "<CODE> (interpretation pending)" so the surface stays
# honest. The resolver surfaces these as informational metadata on the
# verdict — they're an orthogonal axis to the ALVPER capability matrix.
PRIVILEGE_CODE_LABELS: dict[str, str] = {
    # Financial-field grants (high confidence — VFN/EFN map to the
    # "view/edit financial fields" toggles surfaced in the Workfront
    # admin UI for any access level).
    "VFN": "view financial fields",
    "EFN": "edit financial fields",
    # Custom-data (DE) field grants (high confidence — D = DE namespace,
    # V/E/S = view/edit/share; presence on every level matches the
    # "DE fields" admin-UI toggle group).
    "VDE": "view custom-data (DE) fields",
    "EDE": "edit custom-data (DE) fields",
    "SDE": "share custom-data (DE) fields",
    # Per-object-class advanced access privileges (moderate confidence —
    # P/T/I prefix on PAP/TAP/IAP matches Project/Task/Issue and the
    # codes appear in the higher-tier access levels only).
    "PAP": "project access privileges (advanced)",
    "TAP": "task access privileges (advanced)",
    "IAP": "issue access privileges (advanced)",
    # Time-management (moderate confidence — present on every level
    # including External User; matches the "logged time" UI toggles).
    "VTMAWMG": "view time/work-mgmt data",
    "VALLTM": "view all time-management entries",
    # Codes below appear in higher-tier levels only (Standard, Standard
    # with Limits, System Admin). Not yet decoded against Adobe docs —
    # leave as raw codes so the user sees them and we don't lie.
    # TAD, HAD, PRE, PDO, PCA, VPR, MGU, CPJ
}

# AccessLevel.licenseType decoder. The empirical surface from Phase A is
# narrow — only "F" (full) confirmed on the surveyed tenant (System Admin
# + Standard both carried licenseType="F"). Other letter codes likely
# exist on tenants with Light Worker / External User license tiers, but
# were not present in the survey. Documented intentionally thin so the user
# sees unknown codes raw rather than getting wrong labels.
LICENSE_TYPE_LABELS: dict[str, str] = {
    "F": "Full license",
    # Likely-existing but not confirmed in Phase A: Light worker, External
    # User, etc. Multi-tenant survey would tighten this.
}

# Verdict reason codes (stable string constants for test assertions).
REASON_USER_INACTIVE = "user_inactive"
REASON_IS_ADMIN = "is_admin"
REASON_OWNER = "owner"
REASON_ACCESS_LEVEL_LACKS_CAPABILITY = "access_level_lacks_capability"
REASON_DIRECT_SHARE = "direct_share"
REASON_GROUP_SHARE = "group_share"
REASON_TEAM_SHARE = "team_share"
REASON_ROLE_SHARE = "role_share"
REASON_INHERITED = "inherited"
REASON_NO_GRANT = "no_grant"
REASON_FORBIDDEN_FEATURE_FLAG = "forbidden_feature_flag"


def resolve(
    *,
    user: dict,
    access_level: dict,
    target_object: dict,
    attempted_action: CoreAction,
    attempted_feature: str | None = None,
) -> dict:
    """Combine the 6 inputs and return a verdict.

    Required shapes (post-Phase-A):

    user = {
      "ID": "<user-guid>",
      "isActive": bool,
      "accessLevelID": "<access-level-guid>",
      "groups": [{"ID": "..."}],
      "teams":  [{"ID": "..."}],
      "roles":  [{"ID": "..."}],
    }

    access_level = {
      "ID": "<guid>",
      "name": "Standard",
      "isAdmin": bool,                    # Empirical: top-level field
      "licenseType": "F" | ...,           # Optional
      "accessLevelPermissions": [
          {
              "objCode": "ALVPER",
              "objObjCode": "PROJ",       # The objCode this rule grants on
              "coreAction": "EDIT",
              "forbiddenActions": [...],  # string[] of feature-flag names
              "secondaryActions": [...],
              "isAdmin": False,
          },
          ...
      ],
    }

    target_object = {
      "ID": "<object-guid>",
      "objCode": "PROJ",
      "ownerID": "<user-guid>" | None,
      "accessRules": [                    # Inline-includes inherited rules
          {
              "ID": "<rule-guid>",
              "accessorID": "<user/group/team/role guid>",
              "accessorObjCode": "USER" | "GROUP" | "TEAMOB" | "ROLE",
              "coreAction": "EDIT",
              "forbiddenActions": [...],
              "isInherited": False,
              "ancestorID": None,         # populated when isInherited=True
              "ancestorObjCode": None,    # e.g. "PORT"
              "securityObjCode": "PROJ",
              "securityObjID": "<same as target_object.ID>",
          },
          ...
      ],
    }

    attempted_feature: optional feature-flag name (e.g. "EDIT_FINANCE")
      to check against forbiddenActions. If supplied, even an ALLOW
      verdict gets downgraded to DENY when the matched rule's
      forbiddenActions includes this feature.

    Returns a Verdict dict with:
      verdict, reason, matched_rule, matched_accessor, inherited_from,
      all_inputs_checked, suggestions, field_privileges, license_tier
    """
    layers_checked: list[dict] = []
    privileges = _summarize_field_privileges(access_level)
    license_tier = _summarize_license_tier(access_level)

    def _v(**kw: Any) -> dict:
        # Local closure so every return path carries the access-level
        # metadata (privileges + license tier) without 9 repeated kwargs
        # at each callsite.
        return _verdict(
            field_privileges=privileges,
            license_tier=license_tier,
            **kw,
        )

    # 1. Active user.
    if not user.get("isActive", True):
        layers_checked.append({"layer": "user_active", "result": False})
        return _v(
            decision="DENY",
            reason=REASON_USER_INACTIVE,
            layers=layers_checked,
            suggestions=["Reactivate the user."],
        )
    layers_checked.append({"layer": "user_active", "result": True})

    # 2. System Admin bypass.
    if access_level.get("isAdmin"):
        layers_checked.append({"layer": "is_admin", "result": True})
        return _v(
            decision="ALLOW",
            reason=REASON_IS_ADMIN,
            layers=layers_checked,
        )
    layers_checked.append({"layer": "is_admin", "result": False})

    # 3. Ownership.
    owner_id = target_object.get("ownerID")
    if owner_id and owner_id == user.get("ID"):
        layers_checked.append({"layer": "owner", "result": True})
        return _v(
            decision="ALLOW",
            reason=REASON_OWNER,
            layers=layers_checked,
            matched_accessor={"objCode": "USER", "id": user["ID"]},
        )
    layers_checked.append({"layer": "owner", "result": False})

    # 4. Access-level capability — traverse the ALVPER collection.
    if not _access_level_grants(access_level, target_object.get("objCode", ""), attempted_action):
        layers_checked.append({"layer": "access_level_capability", "result": False})
        return _v(
            decision="DENY",
            reason=REASON_ACCESS_LEVEL_LACKS_CAPABILITY,
            layers=layers_checked,
            suggestions=[
                f"Grant the access level '{access_level.get('name', '')}' the "
                f"capability to {attempted_action} on "
                f"{target_object.get('objCode')} (add an ALVPER row). "
                "Affects every user holding this access level."
            ],
        )
    layers_checked.append({"layer": "access_level_capability", "result": True})

    # 5-8. Direct / group / team / role rules on the target object.
    #     The target's accessRules collection includes inherited rules
    #     inline; we handle both via the same matcher and distinguish
    #     after the fact via the rule's isInherited flag.
    matched = _first_matching_rule(
        rules=target_object.get("accessRules") or [],
        user=user,
        action=attempted_action,
    )
    if matched is not None:
        layer_name, accessor, rule = matched
        # Check forbidden feature flag if caller asked.
        if attempted_feature and attempted_feature in (rule.get("forbiddenActions") or []):
            layers_checked.append({"layer": layer_name + "_share", "result": True})
            layers_checked.append({"layer": "forbidden_feature_flag", "result": True})
            return _v(
                decision="DENY",
                reason=REASON_FORBIDDEN_FEATURE_FLAG,
                layers=layers_checked,
                matched_rule=rule,
                matched_accessor=accessor,
                suggestions=[
                    f"The matching AccessRule grants {attempted_action} but "
                    f"forbids the feature '{attempted_feature}'. Remove it "
                    "from forbiddenActions on this rule, or grant via a "
                    "different rule without this denial."
                ],
            )

        if rule.get("isInherited"):
            inherited_from = {
                "objCode": rule.get("ancestorObjCode"),
                "id": rule.get("ancestorID"),
            }
            layers_checked.append({"layer": "inherited", "result": True})
            return _v(
                decision="ALLOW",
                reason=REASON_INHERITED,
                layers=layers_checked,
                matched_rule=rule,
                matched_accessor=accessor,
                inherited_from=inherited_from,
            )

        reason_map = {
            "direct": REASON_DIRECT_SHARE,
            "group": REASON_GROUP_SHARE,
            "team": REASON_TEAM_SHARE,
            "role": REASON_ROLE_SHARE,
        }
        layers_checked.append({"layer": layer_name + "_share", "result": True})
        return _v(
            decision="ALLOW",
            reason=reason_map[layer_name],
            layers=layers_checked,
            matched_rule=rule,
            matched_accessor=accessor,
        )

    layers_checked.append({"layer": "direct_or_accessor_share", "result": False})

    # 9. Default DENY.
    return _v(
        decision="DENY",
        reason=REASON_NO_GRANT,
        layers=layers_checked,
        suggestions=[
            f"Add a direct AccessRule for this user with coreAction={attempted_action}.",
            "Or share the object with a group / team / role the user belongs to.",
            "Or share the object's parent (the inherited rule will surface inline on the child).",
        ],
    )


# ---------------------------------------------------------------------------
# Internals

def _verdict(
    *,
    decision: str,
    reason: str,
    layers: list[dict],
    matched_rule: dict | None = None,
    matched_accessor: dict | None = None,
    inherited_from: dict | None = None,
    suggestions: list[str] | None = None,
    field_privileges: dict | None = None,
    license_tier: dict | None = None,
) -> dict:
    return {
        "verdict": decision,
        "reason": reason,
        "matched_rule": matched_rule,
        "matched_accessor": matched_accessor,
        "inherited_from": inherited_from,
        "all_inputs_checked": layers,
        "suggestions": suggestions or [],
        "field_privileges": field_privileges,
        "license_tier": license_tier,
    }


def _summarize_field_privileges(access_level: dict) -> dict | None:
    """Decode access_level.fieldAccessPrivileges into a structured summary.

    Returns None when the access level has no fieldAccessPrivileges field
    (e.g. fixtures that don't populate it). Otherwise returns:

      {
        "raw": [<code>, ...],
        "decoded": [{"code": <code>, "label": <human-label>}, ...],
        "undecoded": [<code>, ...],
      }

    The decoded labels come from PRIVILEGE_CODE_LABELS. Undecoded codes
    are surfaced separately so the user sees them as opaque rather
    than silently dropped — preserves honesty about Phase A's
    interpretation gaps (see knowledge/permissions/02-access-level-reference.md).
    """
    raw = access_level.get("fieldAccessPrivileges")
    if raw is None:
        return None
    decoded: list[dict] = []
    undecoded: list[str] = []
    for code in raw:
        label = PRIVILEGE_CODE_LABELS.get(code)
        if label is None:
            undecoded.append(code)
        else:
            decoded.append({"code": code, "label": label})
    return {"raw": list(raw), "decoded": decoded, "undecoded": undecoded}


def _summarize_license_tier(access_level: dict) -> dict | None:
    """Decode access_level.licenseType into a structured summary.

    Returns None when the access level has no licenseType field.
    Otherwise returns:

      {"code": <code>, "label": <human-label or None>, "is_decoded": bool}

    Modelled as informational metadata (same as field_privileges) rather
    than a verdict constraint — the empirical surface from Phase A is
    too narrow to confidently auto-DENY based on tier. License-tier
    interaction with ALVPER grants is documented in
    knowledge/permissions/09-gotchas.md #17 for user judgement.
    """
    code = access_level.get("licenseType")
    if code is None:
        return None
    label = LICENSE_TYPE_LABELS.get(code)
    return {
        "code": code,
        "label": label,
        "is_decoded": label is not None,
    }


def _access_level_grants(access_level: dict, objcode: str, action: str) -> bool:
    """Walk the access_level's ALVPER collection looking for a row that
    grants `action` on `objcode`.

    Returns True iff any row matches `(objObjCode=objcode, coreAction=action)`.

    Note: this is exact-match, not ordinal-implies. Phase A confirmed
    coreAction is not strictly ordinal (ADD is a separate axis from
    VIEW→LIMITED_EDIT→EDIT→DELETE), so a separate ALVPER row per
    distinct (objObjCode, action) is the rule.

    To check "does this access level grant ANY of [VIEW, EDIT, DELETE]
    on PROJ?" the caller should invoke this once per action.
    """
    if access_level.get("isAdmin"):
        # System Admin shortcut: empty ALVPER collection by design.
        return True
    alps = access_level.get("accessLevelPermissions") or []
    for row in alps:
        if (
            row.get("objObjCode") == objcode
            and row.get("coreAction") == action
        ):
            return True
    return False


def _first_matching_rule(
    *,
    rules: list[dict],
    user: dict,
    action: str,
) -> tuple[str, dict, dict] | None:
    """Walk the inline rules in accessor-precedence order and return the
    first match.

    Precedence: USER → GROUP → TEAMOB → ROLE. Within each tier, the
    first rule that grants the required action wins.

    The rule's `isInherited` flag is preserved on the matched rule for
    the caller to inspect — the matcher itself doesn't differentiate
    inherited vs direct (inheritance now surfaces inline on the
    target's accessRules collection — see Phase A finding §Q7).
    """
    user_id = user.get("ID")
    group_ids = {g["ID"] for g in user.get("groups", []) if g.get("ID")}
    team_ids = {t["ID"] for t in user.get("teams", []) if t.get("ID")}
    role_ids = {r["ID"] for r in user.get("roles", []) if r.get("ID")}

    tiers = [
        ("direct", "USER", {user_id} if user_id else set()),
        ("group", "GROUP", group_ids),
        ("team", "TEAMOB", team_ids),
        ("role", "ROLE", role_ids),
    ]

    for layer_name, accessor_obj_code, accessor_ids in tiers:
        for rule in rules:
            if rule.get("accessorObjCode") != accessor_obj_code:
                continue
            if rule.get("accessorID") not in accessor_ids:
                continue
            if rule.get("coreAction") != action:
                continue
            return (
                layer_name,
                {"objCode": accessor_obj_code, "id": rule.get("accessorID")},
                rule,
            )
    return None
