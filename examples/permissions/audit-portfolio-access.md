# Example — Audit "who can see this portfolio?"

Flow 3 — object audit. Phase A simplified this: a single GET on the target with `accessRules:*` returns both direct AND inherited rules inline.

## Scenario

> Admin: "Who can see the Q4 Marketing Plan portfolio? I need the list before we share next quarter's plans."

## Calls fired

```bash
# 1. Direct + inherited rules in one GET
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/portfolio/<portID> \
  --data-urlencode "fields=ID,name,ownerID,accessRules:*"

# 2. Accessor expansion: for each rule with accessor=GROUP, expand to user list:
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/group/<groupID> \
  --data-urlencode "fields=ID,name,users:ID,users:name,users:emailAddr"

# 3. For each rule with accessor=TEAMOB:
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/teamMembership/search \
  --data-urlencode "teamID=<teamID>" --data-urlencode "fields=userID,user:name,user:emailAddr"

# 4. For each rule with accessor=ROLE:
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/user/search \
  --data-urlencode "roleID=<roleID>" --data-urlencode "fields=ID,name,emailAddr"
```

## Output (illustrative)

```
Portfolio "Q4 Marketing Plan" (port-abc-123)
Owner: Sarah Chen <sarah@example.com> — implicit DELETE

Direct shares (isInherited=false): 4 rules
  GROUP "Marketing" (45 users)             → coreAction=DELETE
  GROUP "Exec Team" (8 users)              → coreAction=VIEW
  TEAMOB "Marketing Leadership" (5 users)  → coreAction=EDIT
  USER John Doe                            → coreAction=VIEW

Inherited shares (isInherited=true): 0 rows
  (Portfolio is a top-level object — no ancestors above it.)

Effective access table (deduplicated; strongest grant per user):
  Sarah Chen <sarah@...>         DELETE  (owner — implicit)
  [42 names from Marketing]      DELETE  (group "Marketing")
  Bob Smith <bob@...>            EDIT    (team "Marketing Leadership")
  [4 more from Marketing Leadership team] EDIT
  [8 names from Exec Team]       VIEW    (group "Exec Team")
  John Doe <john@...>            VIEW    (direct share)

Total: 56 unique users with access
Children of this portfolio (10 projects) inherit these shares —
each child project's accessRules collection will surface these as
isInherited=true rules with ancestorObjCode=PORT and ancestorID=<this portfolio>.
```

## What this demonstrates

- **Single GET** with `accessRules:*` covers direct + inherited (Phase A simplification).
- **Owner-implicit DELETE** at the top.
- **Effective table is deduplicated** — users in multiple shares show their strongest coreAction grant.
- **Inheritance flows downward** — sharing the portfolio means the projects inside automatically surface these as inherited rules.

## What to do next

For the stated intent ("before we share next quarter's plans"), the audit gives you the right user list to replicate.
