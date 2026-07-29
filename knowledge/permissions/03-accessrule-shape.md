# 03 — AccessRule Shape

`AccessRule` is the API representation of every per-object share in Workfront. ObjCode **`ACSRUL`** (Phase A correction — earlier spec drafts used `ACSRLE` which doesn't exist).

Updated 2026-05-18 with Phase A empirical findings.

## Critical: NOT a top-level object

`/accessRule/search` is rejected: `"ACSRUL is not a top level object and can't be requested directly in internal"`. Same constraint as `CategoryParameter` (CTGYPA) in custom-forms.

AccessRules are accessed via **the parent object's `accessRules` collection**:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/<objCode>/<objID> \
  --data-urlencode "fields=ID,name,accessRules:*"
```

For user-centric audits ("what does Adam have access to?"), use the **inverted query** pattern — query the parent objCode and filter by the accessRules collection's accessor field:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/project/search \
  --data-urlencode "accessRules:accessorID=<userID>" \
  --data-urlencode "accessRules:accessorID_Mod=eq" \
  --data-urlencode "fields=ID,name,accessRules:accessorID,accessRules:coreAction,accessRules:isInherited"
```

For Flow 2 (audit user), the implementation must iterate over a list of potential parent objCodes (PROJ, PORT, PROG, TASK, OPTASK, REPORT, DASHBD, DOCU, ...) and run the inverted query against each. See `05-audit-recipes`.

## Field map (empirical)

| Field | Type | Notes |
|---|---|---|
| `ID` | string | Rule GUID |
| `objCode` | string | Always `"ACSRUL"` |
| `accessorID` | string | The user / group / team / role GUID (NOT `accessorObjID`) |
| `accessorObjCode` | string | `USER` / `GROUP` / `TEAMOB` / `ROLE` |
| `securityObjCode` | string | The objCode of the object being shared (PROJ, TASK, ...) |
| `securityObjID` | string | The ID of the object being shared |
| `coreAction` | string | Single value from `ActionTypeEnum` — see below |
| `forbiddenActions` | string[] | Feature-flag denials |
| `secondaryActions` | string[] | Extra named grants beyond coreAction |
| `isInherited` | boolean | True when this rule was inherited from a parent object |
| `ancestorID` | string | When inherited, the ancestor object's GUID |
| `ancestorObjCode` | string | When inherited, e.g. `PORT` |
| `customerID` | string | System-managed |

Empirical confirmation: a project shared with a user has 1 direct rule (`isInherited=false`, `ancestorID=null`) plus 1 inherited rule from the portfolio (`isInherited=true`, `ancestorID=<port-guid>`, `ancestorObjCode="PORT"`).

## `coreAction` enum

```
ADD, DELETE, EDIT, LIMITED_EDIT, VIEW
```

5 values total. NOT VIEW/CONTRIBUTE/MANAGE/DELETE (early spec). See `01-permission-model` for the rationale.

The resolver requires **exact equality** between the attempted action and the rule's coreAction. A VIEW rule does NOT satisfy an EDIT request, etc. (Phase A confirmed: coreAction is not strictly ordinal; ADD is a separate axis from VIEW→EDIT→DELETE.)

## `forbiddenActions` — 11 named values observed

These are granular feature-flag denials applied on top of a `coreAction` grant:

```
ADD_EXPENSES, ADD_TASKS, CHANGE_STATUS, EDIT_ASSIGNMENTS, EDIT_CUSTOMDATA,
EDIT_FINANCE, EDIT_TEAMS_I_AM_ON, SHARE, SHARE_SYSTEMWIDE,
VIEW_CONTACTINFO, VIEW_FINANCE
```

Example: a rule with `coreAction=EDIT, forbiddenActions=["EDIT_FINANCE"]` means the accessor can edit the object's general fields but NOT its financial fields.

## `secondaryActions` — 3 named values observed

Less common; represents extra named grants on top of `coreAction`:

```
BUDGETING_INFORMATION, EDIT_ACCESSLEVEL, EDIT_ROLE_GROUP
```

Most rules have `secondaryActions: []`.

## Inheritance fields

When a rule was inherited from a parent object (Phase A confirmed: surfaces inline):

```json
{
  "ID": "<rule-guid>",
  "accessorID": "<user-guid>",
  "accessorObjCode": "USER",
  "coreAction": "DELETE",
  "forbiddenActions": [],
  "isInherited": true,
  "ancestorID": "<portfolio-guid>",
  "ancestorObjCode": "PORT",
  ...
}
```

The presence of `isInherited=true` + `ancestorID` + `ancestorObjCode` means **no separate parent-walk GET is required** for headline Flow 1 ("why can user X do Y on Z?"). The target's `accessRules:*` expansion returns both direct and inherited rules.

## Querying

### "Who has access to object X?" (Flow 3)

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/<objCode>/<id> \
  --data-urlencode "fields=ID,name,ownerID,accessRules:*"
```

### "Find rules where user X is the accessor across all projects" (Flow 2 fragment)

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/project/search \
  --data-urlencode "accessRules:accessorID=<userID>" \
  --data-urlencode "accessRules:accessorID_Mod=eq" \
  --data-urlencode "fields=ID,name,accessRules:*" \
  --data-urlencode '$$LIMIT=200'
```

Repeat across `portfolio`, `program`, `task`, `optask`, `report`, etc. for full coverage. The expansion includes ALL accessRules on each returned project (not just the user's), so client-side filtering is needed.

### Inverted-query gotcha

The inverted query returns a `project` (or other parent) row whenever the user is an accessor on ANY of its accessRules — even via group/team/role expansion further down. Make sure the filter is on `accessRules:accessorID` (matches the exact user) rather than `accessRules:accessorObjID` (which doesn't exist).

## Cross-references

- `01-permission-model` — how AccessRule fits in the 6-input model
- `02-access-level-reference` — AccessLevel + ALVPER (a different object — per-user, not per-object)
- `05-audit-recipes` — Flow 2 (inverted parent queries) and Flow 3 (direct accessRules expand)
- `06-inheritance-and-ownership` — when isInherited surfaces inline; how the walker is now optional
- `09-gotchas` — ACSRUL not top-level; accessorID not accessorObjID; coreAction exact-match
