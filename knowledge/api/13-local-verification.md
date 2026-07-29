# 13 — Local Verification (Credentials and Self-Testing)

The workfront-api skill can verify behavior against a real Workfront instance before reporting a documentation divergence. This document explains how the credential store works, how to set it up, and the safety model.

## Scope of use — read this first

**The verification flow exists for one purpose: verifying claims the workfront-api skill's documentation makes.** That means small, focused API calls — run against a sandbox or preview environment you own — to confirm "does the API actually behave the way the skill says it does?" before reporting a divergence (see "How the skill uses it" below).

The verification wrapper is **not** for:
- Running site assessments or health checks of your instance.
- Bulk updates / bulk creates / data migrations (those need a dedicated pre-state-capture and rollback model).
- Pulling instance data into reports, dashboards, or exports.
- Any real work product.

If the user asks to use the verification flow for any of the above, **stop and route them to the right tooling for that purpose**. Repurposing the verification wrapper blurs the safety guarantees (the naming-prefix + audit-log guards assume only API-skill test writes flow through this wrapper).

If you (the skill) catch yourself reaching for `wf-curl.sh` to do real work in the instance, that is a red flag — propose a different tool first.

## Why this exists

The skill makes empirical claims about how the Workfront API behaves (filter modifiers, action endpoints, error responses, etc.). Without a way to test those claims, the skill drifts from reality over time — bugfixes Adobe ships silently invalidate documented gotchas, and users paste in new corrections that haven't been tested.

The verification system gives the skill a live test environment so:
- Suspected divergences can be confirmed before being reported.
- Existing documentation can be re-verified periodically.
- Conflicting community claims can be settled by running the actual call.

## What is and isn't stored

Credentials live **outside** the repo, in the toolkit's shared environment store:

```
~/wf-envs/
  .active                      # one line: the active environment's slug
  <env-slug>/
    .env                       # host + API key, one per environment, mode 600
    audit/                     # pre-write state captures (see Guard 3)
```

The store is managed by the `/wf-env-add`, `/wf-env-use`, `/wf-env-list`, and `/wf-env-remove` commands. Among other fields, each `.env` holds:

```
WF_ENV_LABEL="Acme — Preview"
WF_HOST="acme.preview.workfront.com"
WF_ENV_TYPE="preview"                       # preview | sandbox | prod
WF_API_KEY="..."
```

`preview`/`sandbox` envs write freely. A `prod` env reads freely but refuses writes until an explicit per-session OK — see the safety model below.

**Never committed to git.** Even if someone adds the path to the repo by accident, the credential store is outside the working tree. The repo's `.gitignore` also excludes `*.env` and `secrets/` as defense in depth.

## Helper scripts

Verification helpers live under `skills/workfront-api/scripts/`; credential provisioning goes through the toolkit-wide environment-store commands:

| Script / command | Purpose |
|---|---|
| `/wf-env-add <slug>` (command) | One-step provisioning: creates `~/wf-envs/<slug>/.env` with mode 600, prompts for the API key with hidden input, activates the environment. |
| `/wf-env-use <slug>` (command) | Switch the active environment. List configured environments with no args. |
| `wf-creds-check.sh` | Verify the active credentials are valid; ping the host with a 1-row GET. |
| `wf-curl.sh <path> [curl args]` | Wraps curl. Sources active env, builds URL, places `apiKey` in the query string (required for writes — see `02-authentication.md`). Gates prod writes behind an explicit per-session OK. |
| `wf-cleanup.sh [--delete]` | Find and remove leftover test objects (anything named `[wf-api-verify]*`). Default lists matches; `--delete` hard-deletes with `force=true` after typed confirmation. Honors `WF_VERIFY_KEEP_NAMES` to exclude specific objects (default keeps `[wf-api-verify] scratch project`). |
| `wf-revert.sh <audit-file>` | Replay a captured audit file to restore an object's pre-write state. Supports `--latest` and `--list`. |

## Setup

```bash
# First-time: provision a credential for your sandbox environment.
# One terminal step: prompts for label, host, env type, and the API key
# (hidden input), writes the mode-600 env file, and activates it.
/wf-env-add sandbox

# Confirm it works.
./skills/workfront-api/scripts/wf-creds-check.sh
```

To switch environments later, just re-run `/wf-env-use <other-slug>`.

## Bootstrap: prepare a scratch project

Many verifications need a parent project for issues, tasks, and other child objects. Before the first run that needs one, **manually create a scratch project** so tests have a parent to attach to.

Recommended scratch-project setup (one-time, done in the Workfront UI):

| Field | Value |
|---|---|
| Name | `[wf-api-verify] scratch project` |
| Status | Current |
| Description | "Scratch project for workfront-api skill verification. Test objects created and deleted here." |

The `[wf-api-verify]` prefix matches the naming convention used by all verification test objects — see below — so it's sweepable by `wf-cleanup.sh` if you later want to start fresh (though the default keep-list preserves this exact name).

## Naming convention for test objects

Every object the skill creates during verification **must** have a name starting with `[wf-api-verify]`. Recommended pattern:

```
[wf-api-verify] <what is being tested> <ISO8601 timestamp>
```

Examples:
- `[wf-api-verify] assignMultiple team-only 2026-05-13T14:22:11Z`
- `[wf-api-verify] _Mod=in name-field 2026-05-13T14:23:02Z`
- `[wf-api-verify] custom-form-cascade 2026-05-13T14:24:55Z`

Why it matters:
- Easy to spot leftovers in the Workfront UI.
- `wf-cleanup.sh` finds and removes them en masse.
- If a verification run crashes mid-test, the residue is unambiguous.

## Cleanup after every test

Two cleanup paths, used together:

**Creates → hard-delete.** Tests that created objects must hard-delete them at the end:

```bash
./skills/workfront-api/scripts/wf-curl.sh -X DELETE "/attask/api/v17.0/<obj>/<id>?force=true"
```

**Important:** quote the URL when it contains `?` so zsh/bash don't glob-expand it.

**Mutations → revert.** Tests that mutated existing objects must run `wf-revert.sh` on each audit file produced during the test. The audit file path is printed by `wf-curl.sh` after every mutation (`wf-curl: audit captured -> ...`).

**End-of-session sweep.** Run `scripts/wf-cleanup.sh` (list mode) to see anything still matching the prefix. Pass `--delete` and type `delete` at the prompt to hard-delete. The bootstrap `[wf-api-verify] scratch project` is automatically excluded via the `WF_VERIFY_KEEP_NAMES` keep-list (override in your env file to extend).

**`wf-cleanup.sh` does NOT sweep programs (PRGM) by default** (empirical, 2026-07-06). Its default `OBJCODES` list is `project,optask,task,team,user,role,group,category,parameter` — `program` is absent, so a `[wf-api-verify]`-prefixed **program** created during a test is invisible to both the list and `--delete` sweep and will silently persist. If a test creates a program, either hard-delete it explicitly (`wf-curl.sh -X DELETE "/attask/api/v17.0/PRGM/<id>?force=true"`) or run the sweep with the objcode added: `WF_VERIFY_OBJCODES="...,program" wf-cleanup.sh --delete`. Note that deleting a program with `force=true` does NOT reliably cascade to its child projects in the same call — delete the child project(s) first, then the program, and confirm each with a follow-up GET (a deleted object returns `exception.norecordfound`).

## Org-level (non-portfolio) objects: users, teams, roles, groups

Some verifications require interacting with objects that don't live inside a portfolio: users, teams, roles, groups, customer-level settings, etc. The wrapper does NOT refuse these writes — by operator choice — but the safety properties are weaker than portfolio writes:

- **Wider blast radius.** A test team appears in assignment pickers, sharing dialogs, and reports for every user in the instance. A test user receives notifications, consumes a license seat, and appears in user pickers everywhere.
- **Soft-delete residue.** Workfront keeps deleted users/teams in historical records and audit logs even after `force=true`. Auditors and reporting tools may still see them.
- **Wrapper flags them.** `wf-curl.sh` prints a NOTE when a write targets an org-level objCode so the wider blast radius is visible. The prefix-on-creates and audit-log-on-mutations guards still apply.

**Practical guidance for the skill:**

1. **Prefer reads.** Existing org objects already cover ~90% of verification questions about modifiers, response shapes, and filter behavior. Read them.
2. **If a write is unavoidable**, use the `[wf-api-verify]` prefix in the object's `name` so cleanup can find it. Hard-delete immediately after the test. Run `wf-cleanup.sh --delete` after the session to sweep any residue.
3. **Cost-sensitive cases** (e.g., creating users that consume license seats): ask the user first before writing.
4. **Wider-impact cases** (e.g., creating a group, modifying a role's permissions, changing a customer-level setting): refuse and recommend a personal Workfront test-drive instance instead.

## How the skill uses it

If live behavior diverges from what this skill documents: trust the observed behavior for the task at hand, and treat the divergence as possibly environment-specific (Workfront version, package, or configuration). If it looks globally true, offer to draft a GitHub issue at https://github.com/Thousand-Cuts/wf-toolkit/issues with the endpoint, API version, date, and observed-vs-documented behavior. Never edit the installed plugin's files.

The verification flow slots into that policy as the "confirm it first" step:

1. Run `wf-creds-check.sh` to confirm creds are configured.
2. If yes, reproduce the claim via `wf-curl.sh` and cite the command + response in the drafted issue body.
3. If no, draft the issue with a `_needs verification against a live instance_` caveat and offer to set up credentials.

Writes (PUT/POST/DELETE) against a prod environment require explicit user confirmation before running (see Guard 1). Writes against a disposable preview/sandbox env run without a per-call prompt.

## Safety model

The wrapper enforces three guards on every write at the shell level.

**Guard 1 — explicit-OK on non-disposable environments.** `wf-curl.sh` classifies the active env from `WF_ENV_TYPE` (falling back to a hostname heuristic when unset): `preview`, `sandbox`, `dev`, and `test-drive` are disposable and write freely; anything else — notably `prod` — is non-disposable. Writes to a non-disposable env are refused unless `WF_VERIFY_WRITE_ACK=1` is set on that invocation. An environment folder marked read-only (`WF_READ_ONLY` set in its `.env`) refuses all writes regardless of ack. The skill sets it only after surfacing the target host + label and getting a typed "yes" from the user; a user running the command by hand sets it themselves after reading the refusal. This replaced the earlier `WF_SCOPE_PORTFOLIO_ID` portfolio-scope guard, which only checked that an env var was set and never verified the write target — it mirrors the environment-credentials wrapper (`wf-env-curl.sh`, `WF_ENV_WRITE_ACK`).

**Guard 2 — `[wf-api-verify]` prefix on creates.** Any `POST /<objcode>` without an ID in the path must include `name=[wf-api-verify] ...` in the body. The wrapper refuses creates that don't conform. Every created object is unambiguously a throwaway, immediately recognizable in the Workfront UI and sweepable by `wf-cleanup.sh`.

**Guard 3 — audit log on mutations.** Any `PUT`, `DELETE`, or `POST /<id>/<action>` triggers a preflight GET that captures the object's current state (scalar fields plus relevant collections like `assignments`) to a JSON file under `~/wf-envs/<slug>/audit/<UTC>-<method>-<objcode>-<id>.json`. The audit file is the evidence + revert record. Mutations cannot proceed if the preflight GET fails — this prevents writes to objects we couldn't read.

**Permissions.** The environment store and per-environment folders are mode 700; env files are mode 600; audit dirs are mode 700; audit files are mode 600. `wf-curl.sh` refuses to run if env-file mode is wrong.

**Identity.** Show the active `WF_ENV_LABEL` in any skill output so the user always sees which env was tested against.

**Per-user keys.** Workfront API keys are per-user. Each person on the team should hold their own key for each environment, generated in that environment. Don't share keys across people.

**Rotation.** Preview keys are overwritten on the weekly refresh from prod (see `11-tips-and-gotchas.md`). If a preview key stops working unexpectedly, regenerate it in **Setup → System → Customer Info → API Key Settings**.

### POST against `/search` is a read

Workfront documents using `POST /attask/api/vX/<obj>/search` as a workaround for filter strings that exceed the 8,892-byte URL limit (see `11-tips-and-gotchas.md`). `wf-curl.sh` treats `POST /search` as a read — no write-ack gate, no prefix check, no audit log.

### Reverts: `wf-revert.sh`

Every mutation leaves an audit file behind. To restore an object to its captured pre-state:

```bash
./skills/workfront-api/scripts/wf-revert.sh --latest        # revert the most recent audit
./skills/workfront-api/scripts/wf-revert.sh --list          # list captured audit files
./skills/workfront-api/scripts/wf-revert.sh <audit-file>    # revert a specific one
```

Behavior:
- For regular `PUT`/`DELETE` mutations: `wf-revert.sh` PUTs the captured scalar fields back via `updates=<JSON>`. Read-only fields are silently ignored by Workfront.
- For action endpoints (e.g. `assignMultiple`): action reverts are endpoint-specific. The script prints the captured state and emits a recommended revert command for known actions; for unknown actions it prints the state and asks the operator to revert manually. Action endpoints typically act on test objects you created (which get hard-deleted at end), so a manual revert is rarely needed.

Reverts themselves run through `wf-curl.sh` — the same write guards apply (a revert against a prod environment needs the write-ack), and the revert call is itself audit-logged (so you can re-revert if needed).

## When not to use it

- **Production workfront.com hosts:** writes require the explicit `WF_VERIFY_WRITE_ACK=1` OK, but even GET-only verification against your prod environment should be a deliberate choice, not automatic. Prefer preview/sandbox.
- **Divergence reports based on reading docs only:** if a claim comes from Adobe's API reference and there's no behavioral question to verify, just cite the source. Verification is for "does it actually do X" claims, not "is X documented somewhere."
- **Bulk operations:** `wf-curl.sh` is built for single calls. Bulk writes belong in a dedicated bulk-update process with its own pre-state capture and rollback model.

## Multi-tool integration

The environment store under `~/wf-envs/` is intentionally not skill-scoped: the other toolkit skills read the same active credential via the `wf-env-curl.sh` wrapper. The verification flow layers its own guards (prefix on creates, audit log, write-ack) on top of the shared store — the store itself is common infrastructure.
