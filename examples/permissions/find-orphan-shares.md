# Example — Find orphan shares for deactivated users

Composite audit. Builds on Flow 2 to find AccessRules where the accessor is a deactivated user. Updated 2026-05-18 with the Phase A inverted-query pattern.

## Scenario

> Consultant: "Clean up orphan shares from people who've left. Show me what's outstanding."

## Calls fired

```bash
# Step 1 — all inactive users
./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/user/search \
  --data-urlencode "isActive=false" --data-urlencode "isActive_Mod=eq" \
  --data-urlencode "fields=ID,name,emailAddr,deactivatedAt" \
  --data-urlencode '$$LIMIT=500'

# Step 2 — INVERTED query per parent objCode per inactive user
# (Phase A: /accessRule/search doesn't work — ACSRUL is not a top-level
# object. Iterate over parents and use accessRules:accessorID filter.)
for userID in <list-of-inactive-userIDs>; do
  for OBJ in project portfolio program task optask report dashboard document template; do
    ./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/$OBJ/search \
      --data-urlencode "accessRules:accessorID=$userID" \
      --data-urlencode "accessRules:accessorID_Mod=eq" \
      --data-urlencode "fields=ID,name,accessRules:accessorID,accessRules:coreAction,accessRules:isInherited" \
      --data-urlencode '$$LIMIT=200'
  done
done
```

Performance note: this is `O(N_inactive_users × N_objCodes × pages)`. For
a tenant with 100 deactivated users and 9 parent objCodes paging 200 at a
time, expect 1000-3000 API calls. Worth batching as a background script
rather than an interactive flow.

## Output (illustrative)

```
Inactive users with active AccessRules:

  User                              | Deactivated  | # of orphan rules
  ----------------------------------|--------------|-----------------
  Old Employee 1 <old1@example.com> | 2025-03-12   | 47
  Old Employee 2 <old2@example.com> | 2024-11-08   | 31
  Old Employee 3 <old3@example.com> | 2025-01-20   | 18
  ... (47 more)

Top user — Old Employee 1 (47 rules):

  Object type | Object name                 | coreAction | isInherited
  ------------|------------------------------|------------|------------
  PROJ        | Q1 Campaign Launch           | DELETE     | false
  PROJ        | Roadmap Refresh              | EDIT       | false
  PORT        | Marketing                    | VIEW       | false
  REPORT      | Active Projects              | DELETE     | false
  PROJ        | Brand 2025                   | DELETE     | true  ← inherited from PORT "Marketing"
  ... (42 more)
```

## What this demonstrates

- Inactive users keep their rules — the user is denied at layer 1 (user_active) of the resolver, but the rule remains in the parent's accessRules collection.
- Audit noise: a year of deactivations can accrue hundreds of orphan rules.
- **`isInherited` on rules** — some orphan rules are inherited from parent objects (the orphan shares the share, not the parent's deactivated owner). When cleaning up, deleting the inherited row on the child does nothing; you have to clean up at the ancestor.
- This is a v1 read-only diagnostic; cleanup (bulk DELETE of orphan rules) is dedicated bulk-update tooling territory.

## What to do next

If the consultant wants to remediate:

1. Export this list (CSV).
2. Filter out `isInherited=true` rows — those need cleanup at the ancestor, not the child.
3. Hand off to dedicated bulk-update tooling with a "bulk delete AccessRules where ID in [...]" task targeting the direct rules.
4. Audit-log the deletion (bulk-updates skill handles pre-state capture).

This is exactly the composability the toolkit aims for: read-only `workfront-permissions` produces the target list; write-capable dedicated bulk-update tooling executes the cleanup.
