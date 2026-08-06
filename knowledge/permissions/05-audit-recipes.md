# 05 — Audit Recipes (Flows 2, 3, 4, and composite)

Updated 2026-05-18 with Phase A empirical findings. Flow 2 (audit user) needed the most rework because `/accessRule/search` doesn't exist as a top-level endpoint — must use the **inverted parent-query pattern**.

## Flow 2 — "What can user X actually do?"

Full effective-access printout for a user. **Cannot use `/accessRule/search` directly** — ACSRUL is not a top-level object. Must invert: query each parent objCode and filter by accessRules collection.

```
1. User context
   GET /user/<userID>?fields=ID,name,isActive,accessLevelID,
       accessLevel:name,
       groups:ID,groups:name,
       teams:ID,teams:name,
       roles:ID,roles:name

2. Access level capability matrix (ALVPER collection)
   GET /accessLevel/<accessLevelID>?fields=ID,name,isAdmin,licenseType,
       fieldAccessPrivileges,
       accessLevelPermissions:objObjCode,accessLevelPermissions:coreAction,
       accessLevelPermissions:forbiddenActions,
       accessLevelPermissions:secondaryActions

3. Direct + group + team + role shares via INVERTED parent queries
   For each parent objCode in [project, portfolio, program, task, optask,
                                report, dashboard, document, template]:
     GET /<objCode>/search
       ?accessRules:accessorID=<userID>
       &accessRules:accessorID_Mod=eq
       &fields=ID,name,accessRules:*
       &$$LIMIT=200
   (Plus repeat for groupID, teamID, roleID accessors with the inverted
    pattern on the user's memberships.)

4. Owned objects
   For each ownerID-supporting objCode (PROJ, PORT, PROG, REPORT, DASHBD,
   TMPL, DOCU):
     GET /<objCode>/search?ownerID=<userID>&fields=ID,name&$$LIMIT=100

5. Print structured summary
```

### Output shape

```
User <name> (<email>) — Access Level: "<name>" (isAdmin=<bool>)
  Active: yes/no
  License type: <single letter, e.g. F>
  Groups: <list>
  Teams: <list>
  Roles: <list>

Capability matrix from access level:
  (If isAdmin=true) ★ Bypass — System Admin grants all actions
  (Else: list of ALVPER rows)
  PROJ: VIEW, EDIT, DELETE, ADD     (4 rows in ALVPER collection)
  TASK: VIEW, EDIT, DELETE          (3 rows)
  REPORT: VIEW, EDIT, DELETE, ADD   (4 rows)
  PORT: VIEW
  TMPL: (no rows — no capability)
  ...

Direct shares: <N rows>
  PROJ "Q4 Marketing Plan"  → coreAction=DELETE (isInherited=false)
  ...

Inherited shares (via groups / teams / roles, surfaced inline):
  PROJ × 47 (via Engineering group at coreAction=EDIT)
  PORT × 1   (via Strategic-Projects team at coreAction=DELETE)
  ...

Owned objects:
  Projects:    12 (implicit DELETE on each)
  Portfolios:  1
  Reports:     8
  Dashboards:  3
```

Realistic output sizes: an admin user may produce a 500-row effective-access table. Paginate / offer CSV when total >50.

## Flow 3 — "Who has access to object Y?"

Direct lookup. Phase A confirmed inherited rules surface inline, so this is **one GET** + accessor expansion.

```
1. Object context with all accessRules
   GET /<objCode>/<objectID>?fields=ID,name,ownerID,accessRules:*

   The accessRules collection includes BOTH direct and inherited rules —
   inherited ones have isInherited=true + ancestorID + ancestorObjCode.

2. Accessor expansion (only if you want to enumerate end users):
   For each rule with accessor=GROUP:
     GET /group/<id>?fields=users:ID,users:name,users:emailAddr
   For each rule with accessor=TEAMOB:
     GET /teamMembership/search?teamID=<id>&fields=userID,user:name,user:emailAddr
   For each rule with accessor=ROLE:
     GET /user/search?roleID=<id>&fields=ID,name,emailAddr

3. Owner — already in step 1 as ownerID; implicit DELETE.

4. Build flat effective-access table:
   User <name> → <ADD|VIEW|LIMITED_EDIT|EDIT|DELETE> via <source>
   sources: "direct share", "group <name>", "team <name>",
            "role <name>", "inherited from <ancestorObjCode> <name>", "owner"

5. Print sorted by coreAction tier (DELETE first, then EDIT, LIMITED_EDIT,
   VIEW, ADD) then user name.
```

### Note on the `ancestor` provenance

When a rule has `isInherited=true`, its `ancestorID` + `ancestorObjCode` name the parent that granted it. The source string in the output should be `"inherited from <ancestorObjCode> '<name>'"` (resolve `<name>` via a separate GET on the ancestor if needed for readability).

## Flow 4 — "What does access level Z grant?"

```
1. Resolve: GET /accessLevel/search?name=<name>&name_Mod=cieq → ID
2. Inspect: GET /accessLevel/<id>?fields=ID,name,description,isAdmin,
                                       licenseType,securityModelType,
                                       fieldAccessPrivileges,
                                       accessLevelPermissions:*
3. User count: GET /user/count?accessLevelID=<id>&accessLevelID_Mod=eq
4. Print capability matrix + user count
```

The user count is critical context: "Standard with 47 users" means any change affects 47 users.

### Output shape

```
Access Level: <name> (<id>)
  isAdmin: <bool>            ← if true: "bypasses per-object grants entirely"
  licenseType: <letter>
  fieldAccessPrivileges: [list of codes]   ← per-field privileges (separate axis)
  accessRestrictions: [list]
  Users holding this level: <count>

Capability matrix (accessLevelPermissions collection — <N> rows):
  <objObjCode>      <coreAction>     forbidden: <list>   secondary: <list>
  PROJ              ADD              []                  []
  PROJ              DELETE           []                  []
  PROJ              EDIT             [EDIT_FINANCE]      []
  PROJ              VIEW             []                  []
  TASK              ADD              []                  []
  ... (sorted by objObjCode then coreAction)
```

## Flow 5 — Cross-tenant compare

Read both, normalise to a (objObjCode, coreAction) tuple set, diff.

```
1. Collect SOURCE creds: ./scripts/wf-use.sh firm-reference
2. Collect DEST creds:   confirm WF_LABEL names a different host

3. Source pull: GET source/accessLevel/<src-id>?fields=*,accessLevelPermissions:*
4. Dest pull:   GET dest/accessLevel/<dest-id>?fields=*,accessLevelPermissions:*

5. Diff:
   - Build src_tuples = {(row.objObjCode, row.coreAction): row for row in src.ALVPER}
   - Build dest_tuples likewise
   - Symmetric difference yields what's missing on each side
   - Within matching tuples, sub-diff forbiddenActions and secondaryActions

6. Flag tenant-specific feature differences:
   - isAdmin difference
   - licenseType difference
   - fieldAccessPrivileges set difference
   - accessRestrictions difference

7. Print "to make DEST match SOURCE, the following ALVPER changes are
   needed: ..." (descriptive only — v1 does not author)
```

## Composite audits

### Find orphan shares for deactivated users

```
1. GET /user/search?isActive=false&fields=ID,name,emailAddr&$$LIMIT=500 (paginated)

2. For each inactive userID, run inverted queries across parent objCodes
   (same pattern as Flow 2 step 3) — cannot use /accessRule/search.

3. List the parent objects with orphan shares + sort by count.

4. Surface for cleanup via dedicated bulk-update tooling.
```

### Find every object shared with a group

Inverted pattern:

```
For parent objCode in [project, portfolio, program, task, optask, ...]:
  GET /<objCode>/search
    ?accessRules:accessorID=<groupID>
    &accessRules:accessorObjCode=GROUP
    &fields=ID,name,accessRules:coreAction
```

Useful when retiring a group — you'd want to know what objects need re-sharing first.

### Find objects owned by departed users

For each deactivated user, iterate ownerID-supporting objCodes:

```
For each objCode in [project, portfolio, program, report, dashboard, template, document]:
  GET /<objCode>/search?ownerID=<userID>&fields=ID,name
```

Surface for re-ownership — a deactivated user's owned objects still have them as `ownerID`, and the owner-implicit-`DELETE` never gets a new holder.

## Pagination

All flows can exceed default `$$LIMIT` on large tenants. Use `workfront-api` `knowledge/api/09-pagination-and-limits.md`. Common patterns:

- `$$LIMIT=200` per page; iterate `$$FIRST` until empty
- For total counts: hit `/count` first (where supported)
- Offer CSV export when total > 200

## Cross-references

- `01-permission-model` — exact-match coreAction + isAdmin bypass
- `02-access-level-reference` — ALVPER collection traversal
- `03-accessrule-shape` — inverted-query pattern + field map
- `06-inheritance-and-ownership` — inline isInherited
- `09-gotchas` — ACSRUL not top-level (#4), value-rename impact on audits
