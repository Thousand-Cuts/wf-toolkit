# Example — Debug "user can't edit project"

Flow 1 end-to-end. Updated 2026-05-18 with Phase A field names + enum.

## Scenario

> Consultant: "Adam Gray can't edit the Q4 Marketing Plan project. Why?"

## Inputs resolved

```
user:    adam@example.com → userID 64f91a53...
object:  project URL → projectID 6a04ae7f...
action:  "edit" → EDIT
```

## Calls fired

```bash
# User context
./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/user/64f91a53... \
  --data-urlencode "fields=ID,name,isActive,accessLevelID,accessLevel:name,
groups:ID,groups:name,teams:ID,roles:ID"

# Access level WITH its ALVPER collection (the capability matrix)
./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/accessLevel/<accessLevelID> \
  --data-urlencode "fields=ID,name,isAdmin,licenseType,accessLevelPermissions:*"

# Project with accessRules (inline includes inherited)
./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/project/6a04ae7f... \
  --data-urlencode "fields=ID,name,ownerID,accessRules:*"
```

No separate parent-walk GET — inherited rules show up inline in `accessRules:*`.

## Resolver output (illustrative)

```
User Adam Gray (adam@example.com) — EDIT on PROJ "Q4 Marketing Plan": DENY

Reason: access_level_lacks_capability
Matched accessor: —

Layers checked:
  ✓ user_active                 — Adam is active
  ✗ is_admin                    — accessLevel.isAdmin = false
  ✗ owner                       — not the owner (ownerID differs)
  ✗ access_level_capability     — accessLevel "Worker" has no ALVPER row
                                  for (objObjCode=PROJ, coreAction=EDIT)

Suggestions (least blast radius first):
  - Add a direct AccessRule for Adam with coreAction=EDIT on this project
  - Share PROJ with a group Adam belongs to (Engineering) at coreAction=EDIT
  - Grant access level "Worker" a new ALVPER row for (PROJ, EDIT) —
    affects every user holding this access level
    (estimated impact: ~47 users — query /user/count?accessLevelID=<id>)
```

## What this demonstrates

- The **5-layer walk** with short-circuit logic (stops at access_level_capability once denied).
- **isAdmin gate** is checked early (Phase A: it's the System Admin bypass).
- **ALVPER collection traversal** for the capability check (not a flat dict lookup).
- **Exact-match coreAction** — Worker has VIEW on PROJ but that doesn't satisfy an EDIT request.
- "Least blast radius" ordering of suggestions, with the user-count as the gating context for the heavyweight option.

## What to do next

Apply the lowest-blast-radius suggestion. In practice, the consultant usually picks option 2 (group share) because the user belongs to a group that should reasonably have access.

## Variant: feature-flag check

If Adam can EDIT the project's general fields but not financial fields:

```
attempted_feature = "EDIT_FINANCE"
```

If the matched rule has `forbiddenActions: ["EDIT_FINANCE"]`, the resolver
returns DENY with `reason=forbidden_feature_flag` and explains:

```
The matching AccessRule grants EDIT but forbids the feature 'EDIT_FINANCE'.
Remove it from forbiddenActions on this rule, or grant via a different
rule without this denial.
```
