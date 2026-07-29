# 00 — Rubric and Workflow

When to use the `workfront-permissions` skill, the interview script for each flow, and the decision tree for routing.

## When to use this skill

Use when you have a permissions question that's already happened (or about to happen):

- "User X can't see / edit / delete object Y — why?"
- "What can user X actually do?"
- "Who has access to object Y?"
- "What does access level Z grant?"
- "Compare access level Z between two environments (e.g., sandbox and production)."
- "Find AccessRules pointing at deactivated users." (composite audit)

Do **not** use when:

- You want to *change* a permission (read-only in v1; bulk sharing changes are out of scope for this toolkit — do them in-product; v2 will own access-level authoring).
- The question is about login failures or token expiry (route to `workfront-api` knowledge file 02).
- The question is part of a broader assessment / health check (out of scope for this toolkit — this skill answers specific permission questions, not scorecards).

## Flow decision tree

```
Admin intent
  ├── "why can't <user> <do thing> <to object>?"   → Flow 1 (debug)
  ├── "what can <user> do?" / "everything <user> has access to"  → Flow 2 (user audit)
  ├── "who can see/edit <object>?"                  → Flow 3 (object audit)
  ├── "what does access level <name> grant?"        → Flow 4 (level inspection)
  ├── "compare access level <name> between <a> and <b>"  → Flow 5 (cross-environment diff)
  └── ad-hoc audit (orphan shares, etc.)            → 05-audit-recipes.md "composite audits"
```

## Interview script per flow

### Flow 1 — Debug

Resolve these inputs (ask only what's missing from the request):

| Input | How to resolve |
|---|---|
| `userID` | From email / login / display name via `/user/search` |
| `objectID` + `objCode` | From URL / direct ID / object name |
| `attempted-action` | Inferred from the verb (Phase A enum is `ADD/DELETE/EDIT/LIMITED_EDIT/VIEW`): see → `VIEW`, edit → `EDIT`, fully-manage → `DELETE`, create-new → `ADD`. Confirm if ambiguous. `CONTRIBUTE` / `MANAGE` from earlier spec drafts do NOT exist. |
| `attempted-feature` (opt) | Specific feature flag the user wants to use (e.g. `EDIT_FINANCE`). If supplied, the resolver checks `forbiddenActions` for a feature-flag denial. See `03-accessrule-shape`. |

### Flow 2 — User audit

Single input: userID (resolve from email/name if needed). No further interview — the audit is comprehensive.

### Flow 3 — Object audit

Single input: objectID + objCode. Ask whether to expand group accessors to user lists (default: yes, with a "page output if >50 effective users" cap).

### Flow 4 — Access level inspection

Single input: access level name or ID. Resolve via `/accessLevel/search` if name given.

### Flow 5 — Cross-environment diff

Inputs: access level name (string), source $$HOST, destination $$HOST. Both environments registered (per `workfront-api` `knowledge/api/13-local-verification.md`).

## Safety baseline (also in SKILL.md)

- Read-only — no PUT/POST/DELETE
- Pin `v17.0` per repo convention
- Admin-tier API key recommended; degrade gracefully if not present
- **Credentials via wrapper.** Every API call goes through `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh`, which sources `~/wf-envs/<active>/.env` (set via `wf-env-setkey.sh` in your terminal — no key in chat). Read-only environment folders (`WF_READ_ONLY=1`) are recommended; this skill is hard GET-only.
- Surface `WF_ENV_LABEL` in every printout

## Closing phase: divergence policy

If live behavior diverges from what this skill documents: trust the observed behavior for the task at hand, and treat the divergence as possibly environment-specific (Workfront version, package, or configuration). If it looks globally true, offer to draft a GitHub issue at https://github.com/Thousand-Cuts/wf-toolkit/issues with the endpoint, API version, date, and observed-vs-documented behavior. Never edit the installed plugin's files.

## Cross-skill references

- `workfront-api` — auth + pagination + 13-local-verification for creds
