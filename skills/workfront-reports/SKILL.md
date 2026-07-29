---
name: workfront-reports
description: Use when the user wants to create, modify, or clone an Adobe Workfront report via the REST API — e.g. "create a report of active projects grouped by portfolio", "build an overdue-tasks report", "modify the filter on report <id>", "clone the X report into prod", "lift and shift this report". Runs against the active environment credential store, discovers the REPORT schema at runtime, composes the create sequence, and requires a typed `apply` confirmation before writing. Cross-environment clone lifts a known-good report from a source environment (sandbox/preview) into prod, sanitising environment-specific IDs and flagging DE: custom-field references for parity check. Triggers: "create/build a Workfront report", "modify report <id>", "clone/lift and shift report". Distinct from workfront-textmode (in-product Text Mode edits, no API write) and workfront-api (general /search and ad-hoc REST). Out of scope: sharing/accessRules at create-time, prompts/parameters, calendar/matrix reports, dashboards, row-export via API — all v2.
---

# Workfront Reports

Help a Workfront admin create new reports and modify existing ones via the REST API. Two flows:

1. **NL-create** — author from scratch given a natural-language description.
2. **Clone-and-adapt** — lift a known-good report from a source environment and write a sanitised copy to a destination environment (e.g. sandbox → prod).

This skill writes to the destination Workfront environment. Read `knowledge/reports/00-rubric-and-workflow.md` before starting any run.

## Scope

- **In scope:** Creating list/table reports (objCode + view + filter + groupBy + basic chart). Modifying existing reports (filter / view / groupBy / chart / name / description). Cross-environment clone with interactive sanitisation. Runtime field-schema discovery via `/<object>/metadata`.
- **Out of scope:** Sharing/accessRules at create-time, prompts (report parameters), calendar reports, matrix reports (rowGroupBy + columnGroupBy), dashboard composition, row-export (use the underlying object's `/search` from `workfront-api` instead), auto-rollback on modify, API versions other than `v17.0`.

If the admin asks for something out of scope, redirect — don't drift.

## Safety baseline

- **One `apply` gate per run.** Not two. Not per-call. The admin types the literal word `apply` once to authorise the whole sequence.
- **Cross-environment: never write to source.** Banner at every interactive step names the destination host + customer name. Source and dest are pre-registered as separate environment folders; the skill activates the right one for each phase.
- **No auto-rollback.** Modify flow GETs current state and prints it before writing — that's the manual rollback mechanism (admin copies the pre-state from terminal scrollback if needed).
- **Pin `v17.0`** in every URL. Repo convention.
- **Credentials live in `~/wf-envs/<slug>/.env`**, set by the admin via `wf-env-setkey.sh` in their terminal. Every API call against an environment goes through `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh`. The wrapper sources the active environment's .env (no key in argv, no key in chat).
- **Prod writes require explicit acknowledgement.** When the active (destination) environment is `WF_ENV_TYPE=prod`, the wrapper refuses every write (exit 3) until `WF_ENV_WRITE_ACK=1` is set per call. After the `apply` gate, surface the prod warning verbatim, get a typed `yes`, then prepend the env var to every wrapper invocation in the 3-or-4-call write sequence.
- **`[wf-reports-verify]` flow is separate.** That flow targets your own Workfront sandbox for sanity-checking observed-vs-documented behavior — it runs against a sandbox credential registered via `/wf-env-add` and uses the `[wf-reports-verify]` prefix. See `knowledge/reports/09-verification-flow.md`. Don't conflate it with the main reports flow.
- **Pre-flight `--force` triggers auto-capture.** When the admin overrides pre-flight errors with `--force`, the bundle goes through the write sequence; on REPORT-POST HTTP 200, the skill invokes `pre_flight_validator.py --learn-from-blocked /tmp/preflight-forced.json --learn-objcode <UIOBJCODE>` to persist the forced findings into `~/.cache/wf-toolkit/reports-pseudo-fields-<host-hash>.json`. Auto-capture is gated on HTTP 200 from REPORT POST; a failure earlier in the 4-call sequence does NOT write to the whitelist.
- **Verify tenant-specific enum / status / option values against the live tenant before composing filters.** When a filter, groupBy, or column references a value that varies per tenant — status codes (`CPL` vs custom `LTE`/`DONE`/etc.), priority codes, severity codes, custom-form option `value` strings, condition codes — do NOT assume the canonical Workfront value. Probe the tenant first: `GET /attask/api/v17.0/<objcode>/count?status=<candidate>` (or `/search?status=<x>&fields=status&$$LIMIT=1`) for status, `GET /parameter/<id>?fields=parameterOptions:value` for option values. Report back which codes exist and how many records use each before proposing the filter. The cost of one extra GET is small; the cost of a report that silently filters out 30% of completed tasks because the tenant uses a custom complete-equivalent status is large. Same rule for any enum mentioned in `06-filter-patterns.md` examples (statuses, priorities, severities, conditions). Confirmed pattern against a real production tenant, 2026-05-26.
- **If live behavior diverges from what this skill documents:** trust the observed behavior for the task at hand and treat the divergence as possibly environment-specific (Workfront version, package, or configuration); if it looks globally true, offer to draft a GitHub issue at https://github.com/Thousand-Cuts/wf-toolkit/issues with the endpoint, API version, date, and observed-vs-documented behavior — never edit the installed plugin's files.

## Defer to peer skills

This skill is narrow. The following are owned elsewhere:

- **Authentication, `$$HOST` resolution, API version pinning, pagination, error semantics, External Lookup:** `workfront-api`
- **Every text-mode authoring decision inside `definition` strings (`column.N.name=`, `valueexpression`, `valuefield`, `displayname`, `EXISTS:N:`, `sharecol`, `textmode=`, the `chart=` block, `$$USER`/`$$TODAY` tokens, conditional formatting):** `workfront-textmode`

If an admin asks a question that belongs in one of those skills, route there.

## Knowledge files

Read in this order on first run; re-read just the relevant file on subsequent runs:

- `../../knowledge/reports/00-rubric-and-workflow.md` — when to use, decision tree, the 3-or-4-call REST sequence, safety baseline. **Read when:** any reports task.
- `../../knowledge/reports/01-report-object-shape.md` — REPORT + UIVW/UIFT/UIGB + AccessRule empirical field maps. **Read when:** composing payloads.
- `../../knowledge/reports/02-create-from-scratch-recipe.md` — NL-create + modify flows, end-to-end with pre-flight gate. **Read when:** authoring from scratch or modifying.
- `../../knowledge/reports/03-clone-and-adapt-recipe.md` — cross-environment clone, JSON-object sanitization, DE: parity check, host-rewrite. **Read when:** admin said "clone", "lift and shift", or named a source environment.
- `../../knowledge/reports/04-runtime-schema-discovery.md` — `/metadata` burst, cache shape, pre-flight integration. **Read when:** before any write to a tenant the skill hasn't seen this session.
- `../../knowledge/reports/05-gotchas.md` — silent-empty reports, UI-object re-use, locale leak, PROJ-vs-TMPL, DE: asymmetry, host-URL leakage, preferenceID orphans. **Read when:** modifying a report OR cross-environment cloning.
- `../../knowledge/reports/06-filter-patterns.md` — UIFT.definition JSON-object shape: operators, multi-value TAB-separator, session tokens, OR-groups, EXISTS blocks, DE: rules. **Read when:** composing a UIFT.definition object.
- `../../knowledge/reports/07-view-patterns.md` — UIVW.definition + UIGB.definition.group[] JSON-object shape: column fields, link block, enum columns, aggregator, valueexpression, styledef, image, tile, sharecol, row[], property; per-uiObjCode column variants. **Read when:** composing a UIVW.definition or UIGB.definition object.
- `../../knowledge/reports/08-pre-flight-validation.md` — algorithm for the field-existence check inserted between compose and apply. **Read when:** debugging a pre-flight block.
- `../../knowledge/reports/09-verification-flow.md` — `[wf-reports-verify]` flow + revert + cleanup + pre-flight `--force`/`--learn` loop. **Read when:** admin says "verify against my sandbox" or before any `[wf-reports-verify]` write.

## Scripts

- `scripts/schema_cache.py` — host-hashed cache for `/metadata` responses. Subcommands: `put`, `get`, `inspect`, `refresh`. See `04-runtime-schema-discovery.md`.
- `scripts/sanitize_clone.py` — JSON-object walker that flags environment-specific values in a cloned source payload. 5-bucket output (strip / prompt / parity_check / host_rewrite / cleaned). See `03-clone-and-adapt-recipe.md`.
- `scripts/pre_flight_validator.py` — checks every field reference in an about-to-POST bundle against cached `/<uiObjCode>/metadata`. Catches the PROJ-vs-TMPL class of error before any write. See `08-pre-flight-validation.md`.

## The flow at runtime

### NL-create

1. **Resolve the destination environment.** Run `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --dest`. Exit 0: read `~/wf-envs/<slug>/.env` for the host, label, and env type. Echo back: `"Writing report to <label> at <host>, WF_ENV_TYPE=<type> — correct? [y/n]"`. Refuse if `WF_READ_ONLY="1"` (this skill writes). For a prod destination, warn that the write needs an explicit OK and the skill will prepend `WF_ENV_WRITE_ACK=1` only after the admin confirms. Exit 2: surface a "no active environment" message instructing the admin to run `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-setup.sh <slug>` (one command) first. Handshake via `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/user/search --data-urlencode '$$LIMIT=1' --data-urlencode 'fields=customer:name'`; echo the customer name and require `y`.
2. **Discover schema** for `report`, `uivw`, `uift`, `uigb`, plus `/<uiObjCode>/metadata` for the report's target object (PROJ/TASK/...). Cache via `scripts/schema_cache.py put`.
3. **Interview** for: uiObjCode, name, description (opt), filter (NL → JSON object via `06-filter-patterns.md`), columns (NL → JSON object via `07-view-patterns.md`), groupBy (opt), chart (opt — `05-gotchas.md` #12), sort (opt).
   - **Sharecol auto-default.** If the admin's NL describes 2+ metadata pairs for the primary entity's display cell (e.g., "show the request name with reference # and priority below it"), auto-compose a sharecol group using the `<b>Label: </b>value<br>` stacked layout from `07-view-patterns.md` § 10. The skill does NOT prompt the admin for the HTML. Column 0 carries `sharecol:"true"`, `displayname` set from the entity type (Project/Task/Request/Document/etc.), `<hr>` separator, then `<b>Label: </b>` + field for each pair, joined with `<br>`. Always set `display:inline-block` on any embedded `<img>` per § 10c rule 4. The admin only sees the final payload at Phase C compose and can `edit` if they want a different layout.
4. **Compose payloads.** Print the 3-or-4 JSON bodies the skill is about to POST.
5. **Pre-flight validation.** Run `scripts/pre_flight_validator.py` against the bundle. On `valid:false`, print errors + suggestions; admin types `edit` to revise. No writes before pre-flight is green.
6. **Single `apply` gate.** Admin types `apply`. Any other word stops the flow (`edit` returns to step 3).
7. **Write in order:** POST `/uift` → POST `/uigb` → POST `/uivw` → POST `/report`. Each uses `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh -X POST /attask/api/v17.0/<objcode> --data-urlencode 'updates={JSON}'`. UIFT is always written (with empty `definition:{}` when no filter); UIGB is skipped when no grouping is requested (`groupByID: null` on REPORT). See `00-rubric-and-workflow.md` for the 3-or-4-call convention. **If the destination is prod** (`WF_ENV_TYPE=prod` on the active environment's .env): before the first POST, surface the prod-write warning verbatim, get a typed `yes`, then prepend `WF_ENV_WRITE_ACK=1` to every wrapper invocation in this step:
   ```bash
   WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh -X POST ...
   ```
8. **Print URL:** `$$HOST/report/<id>` and `$$HOST/report/<id>/view`.
9. **Smoke test:** GET the report back with `fields=*,definition`. Diff the response's `filterID`/`groupByID`/`viewID` against what was sent. Surface any silent re-resolution (see `05-gotchas.md` #5).

### Modify

Variant of NL-create. Skips object creation; runs PUTs in-place against the report's existing UIFT/UIGB/UIVW IDs via `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh -X PUT ...`. After GET-current-state and the UI-object re-use check (see `05-gotchas.md` #7), **run pre-flight against the new bundle** before the `apply` gate. Hard-blocks PUTs to `uiObjCode` (destructive — column scope is determined by it). If the destination is prod, the same `WF_ENV_WRITE_ACK=1` flow applies: warning + typed `yes` before the first PUT, then env var on every wrapper invocation in this batch.

### Clone-and-adapt

Per `03-clone-and-adapt-recipe.md`. Two environment folders in play:

1. **Source** — resolved via `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --source`. Defaults to the active environment slug; the admin can pick any other registered environment folder (e.g. the sandbox or preview environment where the known-good report was built and verified).
2. **Destination** — resolved via `wf-env-resolve.sh --dest` (the active environment folder).

The skill activates source first (`/wf-env-use` for the source slug), reads the full bundle through the wrapper, sanitises via `scripts/sanitize_clone.py` (5-bucket output incl. `host_rewrite`), runs the DE: parity check against destination, runs pre-flight at Phase 9, then activates the dest slug and POSTs the cleaned bundle. Prod-write-ack on the dest write phase if dest is prod. Banner at every interactive step names BOTH source and dest environments — never confuse them.

## Error handling

Inline, not raw-bubbled:

- Pre-flight blocks → stop; print errors with suggestions; admin types `edit` to revise. No writes until green.
- Chart/prompts requested → v0.9.0 limitation per `05-gotchas.md` #12. The skill writes the report as a table and directs the admin to finish chart/prompt configuration in the in-product builder. (v0.10.0 will probe `preferenceID` and lift this limitation.)
- `/metadata` GET 401/403 → stop; surface auth failure; point at `workfront-api`. No writes.
- UIFT/UIGB/UIVW POST fails mid-sequence → print IDs already created + exact DELETE curls + which payload field the error referenced.
- REPORT POST returns success but smoke-test shows re-resolution → print the diff so the admin sees the silent UI-object substitution.
- `uiObjCode` value rejected → print the valid enum from cached `/report/metadata`.
- Clone-flow source GET returns 404 → distinguish "doesn't exist" from "no read access" via `/report/search?ID=<id>`.
- Clone-flow DE: parity miss → block; numbered list of missing fields + source-environment form names; admin either creates the field on dest or removes the column.
- Modify-flow PUT to `uiObjCode` requested → hard-block.

## Examples

- `../../examples/reports/active-projects-list.json` — canonical NL-create POST bodies (PROJ).
- `../../examples/reports/overdue-tasks-by-portfolio.json` — adds groupBy + chart (TASK).
- `../../examples/reports/user-activity-30d.json` — different uiObjCode (USER), date filter via `$$TODAY-30D`.
- `../../examples/reports/clone-between-environments.md` — narrated cross-environment clone walkthrough.

## Slash commands

None in v1. The skill activates from NL triggers only.
