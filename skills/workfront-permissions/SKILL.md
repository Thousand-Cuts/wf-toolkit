---
name: workfront-permissions
description: Use when an admin needs to debug, audit, or explain Workfront permissions — e.g. "why can't Adam edit project X?", "what access does Jane have?", "who can see the Q4 portfolio?", "what does the 'Standard' access level grant?", "compare 'Standard' between two environments (e.g., sandbox vs production)", "find orphan shares for inactive users". Read-only. Walks the 6-input permission graph (user active → admin bypass → ownership → access-level capability matrix → direct/group/team/role access rules → inherited rules) and names the specific layer that grants or denies access. Triggers: "why can't user X do Y to Z?", "what can user X do?", "who has access to Y?", "what does access level Z grant?", "compare access levels". Distinct from workfront-api (auth failure modes); this skill never writes. Out of scope: authoring custom Access Levels, bulk AccessRule edits, document-folder permission deep model, share-link audit, license management, group/team/role membership editing — all v2. Verified objCode/enum details live in `knowledge/permissions/`.
---

# Workfront Permissions

Diagnostic-first skill for the Workfront permission model. Five flows, all read-only:

1. **Debug** — "why can't user X do Y on object Z?" The headline flow. Walks the 6-input stack and prints the specific layer that grants or denies.
2. **Audit user** — "what can user X actually do?" Effective-access summary.
3. **Audit object** — "who has access to object Y?" Every accessor and the cascade from parents.
4. **Inspect access level** — Capability matrix + user count.
5. **Compare access levels** — Cross-environment diff (e.g., sandbox vs production drift).

This skill makes no writes in v1. The blast radius of an access-level edit (every user holding that level immediately gets new capabilities) needs the dry-run + impact-preview infrastructure deferred to v2. Read `knowledge/permissions/00-rubric-and-workflow.md` before starting any run.

## Scope

- **In scope:** Diagnostic and audit flows above. The 6-input combiner. Up-tree inheritance walk. AccessRule accessor expansion (Group / Team / Role → user list). AccessLevel capability matrix interpretation. Cross-environment AccessLevel comparison. Runtime field-schema discovery via `/<object>/metadata`.
- **Out of scope:** Authoring custom Access Levels, modifying AccessRules in bulk (out of scope for this toolkit — do it in-product), document folder permission deep model, public-link / share-link audit, license management, group / team / role membership editing. All v2.

## Safety / Credentials

Every API call goes through `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh`. The wrapper sources `~/wf-envs/<active>/.env` for the host + key — no key in argv, no key in chat. To register an environment, run one terminal command: `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-setup.sh <slug>` (it prompts for metadata + the API key with hidden input and activates the environment). See `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/env-credentials-and-safety.md`.

**Read-only environment folders recommended.** This skill is hard GET-only (v1 has no write flows). Registering the environment with `WF_READ_ONLY=1` provides defense-in-depth: even if a future skill version added a write call by accident, the wrapper would refuse it.

**No prod-write-ack needed.** Since the skill never writes, the `WF_ENV_WRITE_ACK=1` flow doesn't apply.

Resolve the active environment at the start of any flow:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh
```

Exit 2 = no active environment; run `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-setup.sh <slug>` (one command; answer 'yes' to read-only for this GET-only skill).

## Safety baseline

- **Read-only.** No PUT/POST/DELETE in v1.
- **Pin `v17.0`** in every URL. Repo convention.
- **Admin-tier API key recommended.** The skill's audit flows need to read `/accessLevel/*` and `/accessRule/search` (via inverted parent queries) — most tenants gate these behind admin access. If the calling user lacks read, the skill surfaces the auth failure rather than producing a misleading verdict.
- **Citing the active environment.** Every printout names the active environment's `WF_ENV_LABEL` so you always see which environment was tested against.
- **If live behavior diverges from what this skill documents:** trust the observed behavior for the task at hand and treat the divergence as possibly environment-specific (Workfront version, package, or configuration); if it looks globally true, offer to draft a GitHub issue at https://github.com/Thousand-Cuts/wf-toolkit/issues with the endpoint, API version, date, and observed-vs-documented behavior — never edit the installed plugin's files.

## Defer to peer skills

This skill is narrow. The following are owned elsewhere:

- **Authentication, `$$HOST` resolution, API version pinning, pagination, error semantics:** `workfront-api`
- **Any text-mode audit output rendered as a tenant Workfront report:** `workfront-textmode` (v2 candidate)
- **Bulk sharing changes / access-level edits:** out of scope for this toolkit — do them in-product with appropriate change control

If a question belongs in one of those skills, route there.

## Knowledge files

Read in this order on first run; re-read just the relevant file on subsequent runs:

- `../../knowledge/permissions/00-rubric-and-workflow.md` — when to use, interview script, decision tree for which of the 5 flows to run. **Read when:** any permissions task.
- `../../knowledge/permissions/01-permission-model.md` — the 6-input combination rule with diagram. The additive nature ("no deny rules except `forbiddenActions`") is the central insight. **Read when:** first run, or any "I thought permissions worked differently" surprise.
- `../../knowledge/permissions/02-access-level-reference.md` — default access levels and their capability matrices. Tenants customise these heavily; this file is a starting point only. **Read when:** Flow 4 (inspect access level) or Flow 5 (compare).
- `../../knowledge/permissions/03-accessrule-shape.md` — full ACSRLE field map, `coreAction` enum, `forbiddenActions` shape, cascading flags. **Read when:** parsing or constructing AccessRule queries.
- `../../knowledge/permissions/04-debug-playbook.md` — the Flow 1 step-by-step procedure with the exact GET sequence per layer. **Read when:** "why can't user X do Y?"
- `../../knowledge/permissions/05-audit-recipes.md` — Flows 2, 3, 4. Each playbook with GET sequences, expected output shapes, pagination guidance. **Read when:** any audit-style question.
- `../../knowledge/permissions/06-inheritance-and-ownership.md` — cascade rules (PORT → PROJ → TASK / OPTASK / DOCU / HOUR / EXPNS), ownership semantics. **Read when:** debug flow walks up the parent chain.
- `../../knowledge/permissions/07-system-wide-overrides.md` — historical record of the v0.14.x "system-wide override" layer that v0.15.0 removed. **Read when:** debugging an instance where someone insists "users see all projects" is a real toggle, or for v2 OAuth2-gated `/internal/*` work.
- `../../knowledge/permissions/08-runtime-schema-discovery.md` — 3-GET `/metadata` flow + per-tenant schema cache. **Read when:** before any audit against an environment the skill hasn't seen this session.
- `../../knowledge/permissions/09-gotchas.md` — additive model surprises, public-link bypass, cross-environment naming mismatches, deactivated-user orphan rules. **Read when:** any unexpected diagnosis.

## Helper scripts

Under `scripts/`:

- `permission_resolver.py` — the 6-input combiner. Pure function; no API calls. Caller pre-fetches user + access level + target object (with accessRules and parents populated). Returns a structured verdict with the matched layer and suggestions.
- `inheritance_walker.py` — up-tree parent map. Tells the caller which parent objCodes to fetch given a target objCode; caps DOCU folder hierarchy at 10 levels.
- `accessor_expander.py` — Group / Team / Role / User → user-list resolution with cascade flag support (parent groups, subgroups) and cycle protection.
- `schema_cache.py` — host-hashed 24h schema cache for runtime metadata.

All four are pytest-covered (`tests/test_permission_resolver.py`, `tests/test_inheritance_walker.py`, `tests/test_accessor_expander.py`). No tenant required to validate.

## Workflow at a glance

```
Admin question
    │
    ├── "why can't X do Y on Z?"           → Flow 1 (debug)            → 04-debug-playbook.md
    ├── "what can user X do?"               → Flow 2 (user audit)       → 05-audit-recipes.md
    ├── "who has access to Y?"              → Flow 3 (object audit)     → 05-audit-recipes.md
    ├── "what does access level Z grant?"   → Flow 4 (level inspection) → 05-audit-recipes.md
    └── "compare level Z across environments" → Flow 5 (cross-environment diff) → 02-access-level-reference.md

Each flow:
    1. Confirm the active environment resolves and creds work (wf-env-resolve.sh + a cheap handshake GET; admin-tier recommended — surface degradation if not)
    2. Schema discovery (cached if recent)
    3. Resolve inputs from natural-language (email → userID, project name → projectID, etc.)
    4. Pull required data via /attask/api/v17.0/... GETs
    5. Run the combiner / audit / diff
    6. Print the structured verdict + per-layer summary
```

Out-of-scope asks (write operations, bulk sharing, etc.) get a one-line explanation and a pointer to the in-product UI. Refuse rather than drift.

## Examples

Worked end-to-end walkthroughs — read the one matching your flow:

- `../../examples/permissions/debug-cannot-edit-project.md` — Flow 1 (debug "why can't X edit Y?") end-to-end.
- `../../examples/permissions/audit-power-user.md` — Flow 2 ("what can user X do?") via the inverted-query pattern.
- `../../examples/permissions/audit-portfolio-access.md` — Flow 3 ("who can see object Y?").
- `../../examples/permissions/compare-access-levels.md` — Flow 5 (cross-environment access-level diff).
- `../../examples/permissions/find-orphan-shares.md` — composite audit: shares whose accessor is a deactivated user.
