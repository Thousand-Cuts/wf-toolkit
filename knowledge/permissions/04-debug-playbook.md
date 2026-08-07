# 04 — Debug Playbook (Flow 1)

The headline flow: "why can't user X do Y on object Z?"

Updated 2026-05-18 with Phase A empirical findings. The GET sequence is simpler than the spec drafts implied — inheritance surfaces inline, so the explicit parent walk is optional.

## Procedure

```
1. Confirm credentials (admin-tier API key recommended)
   bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh
   # (sources ~/wf-envs/<active>/.env; refuses if no active environment)

2. Resolve inputs
   - userID from email/name:
       GET /user/search?emailAddr=<email>&emailAddr_Mod=cieq&fields=ID,name,isActive
   - objectID + objCode from URL/name
   - attempted-action from the verb:
       "see"     → VIEW
       "edit"    → EDIT
       "delete"  → DELETE
       "create"  → ADD
       "fully manage" → DELETE (top tier)

3. Pull user context
   GET /user/<userID>?fields=ID,name,isActive,
       accessLevelID,
       groups:ID,groups:name,
       teams:ID,teams:name,
       roles:ID,roles:name

4. Pull access level WITH its ALVPER collection
   GET /accessLevel/<accessLevelID>?fields=*,accessLevelPermissions:*
   Look at: isAdmin, accessLevelPermissions (array of {objObjCode, coreAction, ...})

5. Pull target object with accessRules
   GET /<objCode>/<objectID>?fields=ID,name,objCode,ownerID,accessRules:*
   The accessRules collection includes BOTH direct and inherited rules
   (inherited rules have isInherited=true + ancestorID + ancestorObjCode).

6. Run the resolver
   permission_resolver.resolve(
     user=user,
     access_level=access_level,
     target_object=target_object,
     attempted_action=action,
     attempted_feature=<optional feature-flag name>,
   )

7. Print the verdict
```

## Output format

```
User <name> (<email>) — <action> on <objCode> "<name>": <ALLOW|DENY>

Reason: <reason-code>
Matched accessor: <type> "<name>" (or owner / is_admin)
Inherited from: <ancestor objCode> "<ancestor name>" (if applicable)

Layers checked:
  ✓ user_active                 — user is active
  ✗ is_admin                    — access level is not isAdmin=true
  ✗ owner                       — not the owner (ownerID differs)
  ✗ access_level_capability     — no ALVPER row for (PROJ, EDIT)
  · direct_or_accessor_share    — not reached (denied earlier)

Suggestions (least blast radius first):
  - Add a direct AccessRule for <user> with coreAction=EDIT on this PROJ
  - Or share this PROJ with a group <user> belongs to at coreAction=EDIT
  - Or grant access level "<name>" the capability EDIT on PROJ
    (adds an ALVPER row — affects every user holding this access level)
```

## Worked example: "Adam can't edit project X"

> TODO: replace with a real captured walkthrough once consultants run this against live tenants. The structure below uses post-Phase-A field names.

```
Inputs:
  user:     adam@example.com → userID 64f91a53...
  object:   project URL → projectID 6a04ae7f...
  action:   "edit" → EDIT

Pulled:
  user.isActive = true
  user.accessLevelID = <worker-level-guid>
  user.groups = [Engineering]
  accessLevel.name = "Worker"
  accessLevel.isAdmin = false
  accessLevel.accessLevelPermissions = [
    {objObjCode: PROJ, coreAction: VIEW},
    {objObjCode: TASK, coreAction: EDIT},
    {objObjCode: TASK, coreAction: DELETE},
    ... (no PROJ+EDIT row)
  ]
  project.ownerID = (other user)
  project.accessRules = [
    {accessorID: <Engineering-guid>, accessorObjCode: GROUP,
     coreAction: VIEW, isInherited: false},
  ]

Resolver verdict:
  DENY at access_level_capability layer.
  "Worker" has no ALVPER row for (PROJ, EDIT).

Suggestions:
  1. Add a direct AccessRule for Adam with coreAction=EDIT — affects Adam only
  2. Share PROJ with a group at coreAction=EDIT — affects all group members
  3. Grant the "Worker" access level a new ALVPER row for (PROJ, EDIT) —
     adds the capability for every user on Worker level (estimated impact:
     47 users — query /user/count?accessLevelID=<id> for the live number)
  4. Change Adam's access level to one that already has (PROJ, EDIT) —
     single user; larger blast change
```

## Edge cases

- **Inactive user.** Short-circuit DENY at layer 1.
- **isAdmin level.** Short-circuit ALLOW at layer 2 regardless of anything else.
- **Owner.** Implicit DELETE (top tier) — wins over almost everything.
- **Public-link bypass on REPORT/DASHBD.** Out of scope for v1.
- **Feature-flag denial.** If the caller supplied `attempted_feature=<flag>` and the matched rule has it in `forbiddenActions`, verdict downgrades to DENY with `REASON_FORBIDDEN_FEATURE_FLAG`.

## When the verdict is ALLOW but the consultant says "user still can't"

The resolver only sees the REST-modelled layers. A handful of operational blockers sit above it and are invisible to the API. Surface these in the printout as "non-model causes" when verdict is ALLOW:

1. **Layout Template hides the UI.** #1 cause. Layout Templates gate tab/section/button visibility per-access-level/group/user and are not REST-readable in v17. See `09-gotchas` #18.
2. **External document provider not linked.** If the project's doc store is SharePoint/GDrive, the user needs that integration linked on their profile.
3. **Stale session.** Permission changes don't propagate to active sessions — sign out + back in.
4. **Adobe Experience Cloud account mismatch.** The user may be signed in as a different Adobe ID than the WF user we audited.

## Exact-match coreAction caveat

Workfront's coreAction is **not strictly ordinal**. Granting a user `coreAction=DELETE` on a project does NOT automatically grant `coreAction=EDIT` or `VIEW` from the resolver's perspective. The resolver matches exactly.

In practice Workfront's UI configures shares such that a "Manage" grant has multiple rules (one per coreAction the user gets). The resolver checks each via separate `resolve()` calls or against a list of attempted actions.

For audit-style use cases ("what's the highest action this user has?"), the caller iterates the 5 coreActions in priority order and accepts the first ALLOW.

## Cross-references

- `01-permission-model` — the 6-input combination rule
- `02-access-level-reference` — ALVPER collection traversal
- `03-accessrule-shape` — accessRule field map (post-Phase-A)
- `06-inheritance-and-ownership` — inline inheritance + ownership
- `09-gotchas` — the most common surprise patterns
