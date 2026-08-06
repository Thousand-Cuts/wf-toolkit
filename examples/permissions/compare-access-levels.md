# Example — Cross-tenant access level compare

Flow 5 — diff "Standard" between two tenants. Updated 2026-05-18 with the ALVPER-collection diff approach.

## Scenario

> Consultant: "We're migrating Acme onto our reference access-level design. What does their 'Standard' grant that ours doesn't (or vice versa)?"

## Calls fired

```bash
# Pull from SOURCE (firm's tenant)
./skills/workfront-api/scripts/wf-use.sh firm-reference
./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/accessLevel/search \
  --data-urlencode "name=Standard" --data-urlencode "name_Mod=eq" \
  --data-urlencode "fields=ID,name,isAdmin,licenseType,fieldAccessPrivileges,accessRestrictions,accessLevelPermissions:*" \
  > /tmp/firm-standard.json

# Pull from DEST (client tenant)
./skills/workfront-api/scripts/wf-use.sh acme-tenant
./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/accessLevel/search \
  --data-urlencode "name=Standard" --data-urlencode "name_Mod=eq" \
  --data-urlencode "fields=ID,name,isAdmin,licenseType,fieldAccessPrivileges,accessRestrictions,accessLevelPermissions:*" \
  > /tmp/acme-standard.json

# User counts on each side (informs blast radius)
./skills/workfront-api/scripts/wf-use.sh firm-reference
./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/user/count \
  --data-urlencode "accessLevelID=<firmStandardID>" \
  --data-urlencode "accessLevelID_Mod=eq"

./skills/workfront-api/scripts/wf-use.sh acme-tenant
./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/user/count \
  --data-urlencode "accessLevelID=<acmeStandardID>" \
  --data-urlencode "accessLevelID_Mod=eq"
```

## Diff logic

```
1. Build SRC = {(row.objObjCode, row.coreAction): row for row in src.accessLevelPermissions}
2. Build DEST likewise
3. only_src   = set(SRC) - set(DEST)    # grants source has, dest lacks
4. only_dest  = set(DEST) - set(SRC)    # grants dest has, source lacks
5. shared     = set(SRC) & set(DEST)    # in both
6. For each key in shared, sub-diff:
   - forbiddenActions set difference
   - secondaryActions set difference
7. Top-level field diff:
   - isAdmin
   - licenseType
   - fieldAccessPrivileges (string[] set diff)
   - accessRestrictions (string[] set diff)
```

## Output (illustrative)

```
Comparing AccessLevel "Standard"

  SOURCE: firm-reference (192 users hold this level, isAdmin=false, licenseType=F)
  DEST:   acme-tenant   (37 users hold this level, isAdmin=false, licenseType=F)

ALVPER row counts:
  SOURCE: 92 rows
  DEST:   85 rows

Capability diff (objObjCode, coreAction):

  Only on SOURCE (7 rows):
    (PROJ, DELETE)
    (REPORT, ADD)
    (REPORT, DELETE)
    (REPORT, EDIT)
    (DASHBD, ADD)
    (DASHBD, EDIT)
    (DASHBD, VIEW)

  Only on DEST (0 rows):
    (none)

  In both with forbiddenActions diff (2):
    (PROJ, EDIT): SOURCE forbidden=[],
                  DEST forbidden=[EDIT_FINANCE]
    (OPTASK, EDIT): SOURCE forbidden=[],
                    DEST forbidden=[CHANGE_STATUS]

Top-level field diff:
  isAdmin: match (both false)
  licenseType: match (both "F")
  fieldAccessPrivileges: SOURCE has 18 codes, DEST has 16 codes
    Only on SOURCE: VTMAWMG, VALLTM
    Only on DEST: (none)
  accessRestrictions: match (both [])

To make DEST match SOURCE:
  Add ALVPER rows for: PROJ+DELETE, REPORT+ADD/DELETE/EDIT,
                       DASHBD+ADD/EDIT/VIEW (7 new rows)
  Remove from forbiddenActions: EDIT_FINANCE on (PROJ,EDIT);
                                 CHANGE_STATUS on (OPTASK,EDIT)
  Add to fieldAccessPrivileges: VTMAWMG, VALLTM

Blast radius if DEST is updated: 37 users immediately receive new
capabilities. (Per [[01-permission-model]], the additive model means
adding rows can ONLY grant access, never remove it.)
```

## What this demonstrates

- Cross-tenant access-level names mean nothing without the ALVPER diff.
- **ALVPER tuple-set diff** is the right normaliser — different from a flat dict comparison.
- **forbiddenActions sub-diff** is meaningful because feature-flag denials change effective behaviour without changing coreAction.
- User counts gate the "should we do this?" question.
- Output is descriptive only — v1 does NOT author the changes against DEST.

## What to do next

The consultant takes the diff to a discussion with the client. v2 of this skill will be able to author the matching changes against DEST with a dry-run preview and impact-by-user count. For v1, the consultant makes the changes in-product or via dedicated bulk-update tooling if it grows to handle this.
