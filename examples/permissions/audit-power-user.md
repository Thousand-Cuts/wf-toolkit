# Example — Audit a power user

Flow 2 — "What can user X actually do?" for a power user. Updated 2026-05-18 with the Phase A inverted-query pattern.

## Scenario

> Admin: "Show me everything Jane has access to. She's a senior PM and I want to know what we'd lose if she leaves."

## Calls fired

```bash
# 1. User context
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/user/<janeID> \
  --data-urlencode "fields=ID,name,isActive,accessLevelID,accessLevel:name,
groups:ID,groups:name,teams:ID,teams:name,roles:ID,roles:name"

# 2. Access level (capability matrix via ALVPER collection)
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/accessLevel/<janeAccessLevelID> \
  --data-urlencode "fields=ID,name,isAdmin,licenseType,fieldAccessPrivileges,
accessLevelPermissions:objObjCode,
accessLevelPermissions:coreAction,
accessLevelPermissions:forbiddenActions"

# 3. INVERTED parent queries — Phase A: /accessRule/search doesn't work
# Iterate over parent objCodes the user might have rules on:
for OBJ in project portfolio program task optask report dashboard document template; do
  bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/$OBJ/search \
    --data-urlencode "accessRules:accessorID=<janeID>" \
    --data-urlencode "accessRules:accessorID_Mod=eq" \
    --data-urlencode "fields=ID,name,accessRules:*" \
    --data-urlencode '$$LIMIT=200'
done
# Repeat for each of Jane's groupIDs, teamIDs, roleIDs as accessorID.

# 4. Owned objects:
for OBJ in project portfolio program report dashboard template document; do
  bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/$OBJ/count \
    --data-urlencode "ownerID=<janeID>" --data-urlencode "ownerID_Mod=eq"
done
```

## Output (illustrative)

```
User Jane Doe (jane@example.com) — Access Level: "Senior PM" (isAdmin=false)
  Active: yes
  License type: F
  Home group: PMO
  Groups: PMO, Engineering, Q4-Initiative
  Teams: Strategic-Projects
  Roles: Project Manager

Capability matrix from access level (87 ALVPER rows):
  PROJ:     ADD, VIEW, EDIT, DELETE
  TASK:     ADD, VIEW, EDIT, DELETE
  OPTASK:   ADD, VIEW, EDIT, DELETE
  PORT:     VIEW, EDIT, DELETE  (no ADD)
  PROG:     VIEW, EDIT, DELETE  (no ADD)
  TMPL:     VIEW, EDIT, DELETE
  REPORT:   ADD, VIEW, EDIT, DELETE
  DASHBD:   ADD, VIEW, EDIT, DELETE
  DOCU:     VIEW, EDIT, DELETE
  USER:     VIEW
  ... (sorted by objObjCode)

Field-access privileges (separate axis, 12 codes): VFN, EFN, VDE, EDE,
SDE, TAD, HAD, PAP, TAP, PRE, PDO, PCA

Direct shares: 18 rows
  PROJ "Q4 Marketing Plan"  → coreAction=DELETE (isInherited=false)
  PROJ "Roadmap Refresh"    → coreAction=DELETE (isInherited=false)
  REPORT "Active Projects"  → coreAction=DELETE (isInherited=false)
  ... (15 more)

Inherited / accessor-expansion shares (47 rows, inline isInherited=true
or via group/team accessor):
  PROJ × 42  → coreAction=DELETE (via PMO group, isInherited=false on parent rule)
  PORT "Marketing"  → coreAction=DELETE (via direct group share)
  ... etc

Owned objects (implicit DELETE on each):
  Projects:    12
  Portfolios:  1 ("Marketing")
  Reports:     8
  Dashboards:  3
```

## What this demonstrates

- **The inverted parent-query pattern** instead of `/accessRule/search` (which doesn't work).
- **ALVPER collection** as the capability matrix, with `(objObjCode, coreAction)` granularity.
- **Owner-implicit DELETE** matters for offboarding — ownership doesn't transfer automatically.
- **Field-access privileges** surface as a separate axis from the ALVPER matrix.

## What to do next

If Jane is leaving, the offboarding sequence:

1. **Re-assign owned objects.** Each of the 12 projects, the portfolio, 8 reports, 3 dashboards needs a new owner *before* deactivating Jane.
2. **Audit groups.** If PMO grants DELETE on 42 projects, confirm Jane's replacement also belongs.
3. **Direct shares can be left.** Deactivating the user denies them at layer 1 (user_active) regardless of the rules; cleanup is cosmetic.
