# 01 — The Permission Model

The Workfront permission model is a **graph**, not a stack. Six orthogonal inputs combine additively to produce "can user X do Y on object Z?". The most permissive layer wins.

Updated 2026-05-18 with Phase A empirical findings; layer 4 (system-wide override) removed 2026-05-19 after HAR capture #6 disproved its existence in modern v17.0 — see `07-system-wide-overrides` for the historical context.

## The 6 inputs (verified)

```
                        Can <user> <action> <object>?
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   user.isActive            access_level.isAdmin         target_object.ownerID
   (short-circuit DENY      (short-circuit ALLOW —       (short-circuit ALLOW
    if False)                System Admin gate)           if matches user)
                                    │
                  access_level.accessLevelPermissions
                  (collection of ALVPER rows — DENY if no
                   row for (objObjCode, attempted_action))
                                    │
                ┌─────────────┬─────┴─────┬─────────────┐
                │             │           │             │
          direct share   group share  team share   role share
          (USER         (GROUP       (TEAMOB      (ROLE
           accessor)     accessor)    accessor)    accessor)
                │             │           │             │
                └─────────────┴─────┬─────┴─────────────┘
                                    │
                          inline-inherited rules
                          (target's accessRules collection
                           includes inherited rows with
                           isInherited=true + ancestorID +
                           ancestorObjCode)
```

Default: DENY.

## `coreAction` enum (5 values, empirical)

```
ADD, DELETE, EDIT, LIMITED_EDIT, VIEW
```

**Critical:** earlier spec drafts mentioned `CONTRIBUTE` and `MANAGE` — these **do not exist** on real Workfront tenants. The actual enum surveyed across 393 production ALVPER rows on a live Workfront tenant is the 5 values above.

`EDIT` is what the spec drafts called `CONTRIBUTE`/`MANAGE`. `DELETE` is the top of the read/write tier. `LIMITED_EDIT` is a constrained subset of EDIT (e.g. "edit assignments only"). **`ADD` is a separate axis** — it represents "can create new objects of this type" and is NOT on the linear VIEW→LIMITED_EDIT→EDIT→DELETE progression. Granting EDIT does NOT imply ADD.

## Precedence and short-circuits

In order:

1. **`user.isActive`** — if False, DENY immediately.
2. **`access_level.isAdmin`** — if True, ALLOW immediately. System Admin's `accessLevelPermissions` collection is empty by design; the `isAdmin` flag is the gate.
3. **Ownership** — if `target_object.ownerID == user.ID`, ALLOW immediately. Owner always has implicit DELETE (Workfront's top tier).
4. **Access-level capability** — exact match `(target.objCode, attempted_action)` in the `accessLevelPermissions` collection. If no ALVPER row matches, DENY.
5. **Direct AccessRule** — search target_object.accessRules for `accessorObjCode=USER, accessorID=user.ID`. First exact-coreAction match wins.
6. **Group / Team / Role AccessRules** — same shape, accessor type matches user's memberships.
7. **Inline-inherited rules** — same matcher; the rule's `isInherited=true` + `ancestorID` + `ancestorObjCode` surface the provenance.

> **Removed in v0.15.0:** an earlier "system-wide override" layer (formerly step 4) modelled tenant-wide visibility toggles like "users see all projects". HAR capture #6 (2026-05-18) disproved that those toggles exist as discoverable settings in modern v17.0 — see `07-system-wide-overrides`.

## The exact-match rule (not ordinal)

The resolver requires **exact equality** between `attempted_action` and the rule's `coreAction`. A VIEW rule does NOT satisfy an EDIT request, and vice versa.

This is empirically required because:
- `ADD` is parallel to the others (not ordinal — see above).
- `LIMITED_EDIT` is a constrained sibling of EDIT, not a sub-rank.

Workfront's UI surfaces multiple rules per (user, object) when needed, each at a specific coreAction. The model doesn't compress them onto an ordinal axis.

## `forbiddenActions` are feature-flag denials

A separate field on AccessRule and on ALVPER rows. **Not a coreAction subtraction** (earlier spec drafts had this wrong). Instead, `forbiddenActions` is a `string[]` of granular feature-flag names that get denied even when the broader `coreAction` is granted.

Empirically observed values:

```
ADD_EXPENSES, ADD_TASKS, CHANGE_STATUS, EDIT_ASSIGNMENTS, EDIT_CUSTOMDATA,
EDIT_FINANCE, EDIT_TEAMS_I_AM_ON, SHARE, SHARE_SYSTEMWIDE,
VIEW_CONTACTINFO, VIEW_FINANCE
```

Example: a rule with `coreAction=EDIT` and `forbiddenActions=["EDIT_FINANCE"]` means "can edit the object except for its financial fields."

The resolver's `attempted_feature` parameter lets a caller ask "does my user have the EDIT_FINANCE feature on this object?" — the answer combines the coreAction match plus a check that `attempted_feature` isn't in `forbiddenActions`.

## `fieldAccessPrivileges` is an orthogonal axis

Separate from the ALVPER capability matrix and the `forbiddenActions` feature-flag denials, every AccessLevel carries a `fieldAccessPrivileges: string[]` of per-field-class grants (financial / DE custom-data / time-management / advanced per-object grants). See `02-access-level-reference` for the full 18-code enum and the empirical distribution across the 6 surveyed access levels.

v0.16.0: the resolver surfaces these on every verdict as `field_privileges: {raw, decoded, undecoded}` so an auditor explaining "why can't Adam see project financials?" can see at a glance whether Adam's access level has `VFN` / `EFN` even when the ALVPER `(PROJ, VIEW)` row would otherwise grant.

## Inheritance is inline

Empirical Phase A finding: a child object's `accessRules` collection includes inherited rules **inline**, each with:

- `isInherited: true`
- `ancestorID: <parent object GUID>`
- `ancestorObjCode: PORT` (or PROJ, PROG, etc.)

A single `GET /<obj>/<id>?fields=accessRules:*` returns BOTH direct and inherited rules with provenance. The resolver doesn't need to walk the parent chain explicitly. The `inheritance_walker.py` module remains in the toolkit for the niche case where a caller wants to query parents directly.

## Why "graph not stack"

Two reasons:

1. **Multiple parallel grants.** A user can be granted via direct share + group share + team share simultaneously at different coreActions. The resolver returns the first match in accessor-precedence order; the most permissive coreAction wins.
2. **`isAdmin` short-circuits everything.** A user with an isAdmin access level bypasses all per-object grant logic — their permission graph is "yes" everywhere.

## Cross-references

- `03-accessrule-shape` — full AccessRule field map (post-Phase-A)
- `02-access-level-reference` — ALVPER collection structure + isAdmin semantics
- `06-inheritance-and-ownership` — inline inheritance + ownership semantics
- `07-system-wide-overrides` — VIEW-style override caveats (and what we couldn't pin)
- `09-gotchas` — exact-match coreAction, feature-flag denials, ACSRUL not top-level
