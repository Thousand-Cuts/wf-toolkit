# 00 — Rubric and Workflow

The `workfront-reports` skill creates new Adobe Workfront reports and modifies existing ones via the REST API. Two flows: **NL-create** authors a report from a natural-language brief; **clone-and-adapt** lifts a known-good report from the firm's own Workfront instance and writes a sanitised copy into a client's instance. This file is the dispatch sheet — when the skill should run, when it should defer, the four-call REST sequence every create follows, and the safety baseline that applies to every run.

## When to use this skill

Trigger phrases that should route here:

- "Create a report of active projects grouped by portfolio."
- "Build me a list-of-overdue-tasks report with columns name, owner, planned completion."
- "Clone the X report from our instance into the client's tenant."
- "Lift and shift this report to <client>."
- "Modify the filter on report `<ID>` to also exclude templates."
- "Change the grouping on this report from portfolio to program."
- "Add a column showing % complete to the report at `<URL>`."

In short: any request that ends in a written REPORT row (or its UIFT / UIGB / UIVW siblings) inside a target Workfront tenant.

## When NOT to use this skill

Route elsewhere if the consultant's actual need is one of these:

- **In-product text-mode tweak the consultant can paste themselves** (no API write needed) → `workfront-textmode`. If the consultant has the report open in the in-product builder and wants help writing the `valueexpression` for one column, no API call is required — they paste into the Text Mode tab and save.
- **Ad-hoc query against the REST surface** (`/project/search`, `/task/search`, …) where no report row gets created → `workfront-api`. The reports skill always creates or mutates a `REPORT` row; if the consultant only wants the data, the underlying object's `/search` is the right tool.
- **Write operations against data records** (projects, tasks, hours, users) — the reports skill writes report *definitions*, not the data the reports show → dedicated bulk-update tooling.
- **Calculated custom-field authoring** (the `Calculated` field type on a custom form) → `workfront-calc-fields`. Reports may *reference* calculated fields via `DE:<name>`, but composing the calculation itself belongs in the calc-fields skill.
- **Fusion scenarios** that read or write Workfront — none of that goes through the REST report endpoint → `workfront-fusion`.

When a request straddles two skills (e.g., "build this calculated field, then create a report that groups by it"), do the calc-fields work first as a peer skill, then come back here for the report.

## The two flows

### NL-create (author from scratch)

The consultant describes the report in natural language. The skill interviews for any missing pieces (`uiObjCode`, name, filter intent, columns, groupBy intent, optional chart, optional sort), composes the four payloads, shows them, and writes on a single typed `apply`. See `02-create-from-scratch-recipe.md` for the end-to-end walkthrough including the modify variant (PUT in place).

### Clone-and-adapt (cross-tenant)

The consultant points at a known-good report living somewhere — usually the firm's own Workfront instance. The skill GETs the report and its three referenced UI-objects, sanitises tenant-specific IDs/dates, flags `DE:<name>` custom-field references for parity check against the destination tenant, applies any requested mutations, then writes into the destination on a single typed `apply`. See `03-clone-and-adapt-recipe.md` for the full procedure.

## Decision tree

```
Is there a similar known-good report in the firm's WF instance the consultant
wants to use as a starting point?
  yes → clone-and-adapt flow (`03-clone-and-adapt-recipe.md`)
  no  → NL-create flow (`02-create-from-scratch-recipe.md`)

Does the consultant want to change an existing client-side report?
  yes → modify flow (variant of NL-create; skips UI-object creation, runs PUTs
        against the existing UIFT/UIGB/UIVW/REPORT rows; see
        `02-create-from-scratch-recipe.md` "Modify flow" section)

Does the request ask for sharing/accessRules, prompts, calendar, matrix, or
dashboard composition?
  yes → out of scope for v1. Surface the limitation, complete what you can,
        point the consultant at the in-product builder for the rest.
```

## The three-/four-call write sequence

Workfront reports are created by 3 or 4 sequential POSTs depending on whether the report has grouping:

| Intent | Calls | What's `null` on the REPORT row |
|---|---|---|
| Analytical / matrix report | 4 | nothing — all three referenced IDs populated |
| List report, no grouping (`reportType:"L"`) | 3 | `groupByID: null` (UIGB POST omitted) |
| View-only report (no filter) | 3 | `groupByID: null` (UIFT POSTed with empty `definition:{}`; UIGB omitted) |

`null` is the literal JSON value, not omitted. `viewID` is always required.

**UIFT is always written**, even when the consultant declines a filter — v0.9.0 convention is to POST `{"definition": {}, ...}` rather than skip the call. 29/30 reports in the empirical survey have a non-null `filterID`; the always-1×UIFT convention matches reality and keeps the Phase F write loop's call count predictable. **UIGB is the only optional UI-object**: skip its POST entirely when no grouping is requested and pass `groupByID: null` on the REPORT.

The full sequence when all four fire:

```
POST /uift   { name, uiObjCode, filterType:"REPORT", isReport:true, isText:false,
               isSavedSearch:false, definition: {...} }                          → filterID
POST /uigb   { name, uiObjCode, isReport:true, isText:false,
               definition: {"group":[{...}], "textmode":"false"} }               → groupByID
POST /uivw   { name, uiObjCode, layoutType:"LIST", uiviewType:"LIST",
               isReport:true, isText:false, isNewFormat:true,
               definition: {"column":[{...}]} }                                  → viewID
POST /report { name, uiObjCode, reportType:"A"|"L"|"M", isReport:true,
               filterID, groupByID, viewID, ...optional fields... }              → reportID
```

Notes:

- **Wire format.** Every POST uses `--data-urlencode 'updates={JSON}'`, NOT raw `-d '{JSON}'` body. The raw-body form is silently rejected with `definition cannot be null`. This is the single most-load-bearing fact about the API.
- **`definition` is a JSON object.** Each of UIFT, UIGB, UIVW has a `definition` field whose value is a structured object — NOT the text-mode `\n`-separated string a consultant sees in the in-product Text Mode tab. See `06-filter-patterns.md` (filter half), `07-view-patterns.md` (view + group halves).
- **UIGB requires ≥1 group entry.** Empty `group: []` is rejected with "No groupings were defined". If you want no grouping, OMIT the UIGB POST entirely and pass `groupByID: null` on the REPORT.
- **Pre-flight validation.** Between composing the payloads and the `apply` gate, the skill runs `pre_flight_validator.py` to check every field reference against cached `/<uiObjCode>/metadata`. Errors block with suggestions. See `08-pre-flight-validation.md`.
- **Order matters.** The REPORT POST references `filterID` / `groupByID` / `viewID`, so the UI-objects must exist first. Capture each returned ID before firing the next call.
- **Modify variant.** When changing an existing report, PUT-in-place against the existing UIFT/UIGB/UIVW rows preserves their IDs and any external references (subscriptions, dashboards). See `05-gotchas.md` #7 for the UI-object re-use warning.

## Safety baseline

The `workfront-reports` skill writes to the destination Workfront tenant. The design choice (per the spec) is "just write it" — reports are cheap to delete, so the heavy multi-stage safety machinery used by dedicated bulk-update tooling is not warranted. The baseline:

- **One `apply` confirmation gate per run.** Not two. Not per-call. The consultant types the literal word `apply` once to authorise the whole four-call sequence (or the PUT sequence on modify). No other word proceeds. `y`, `yes`, `proceed`, `apply now` — none of those count. If the consultant types `edit`, return to the interview with the existing fields prefilled.
- **No backup-and-rollback machinery.** There is no pre-state JSON file, no audit log, no per-record rollback plan. The modify flow GETs the current state of the report + its three UI-objects and prints them inline before writing — *that* is the rollback mechanism. If the consultant needs to revert, they copy the pre-state JSON from terminal scrollback and re-issue it as a PUT.
- **Cross-tenant: never write to source.** In the clone flow, source and destination are pre-registered as separate environment folders. The skill activates the source slug for read phases and the dest slug for write phases via `/wf-env-use`. The wrapper sources `~/wf-envs/.active`, so cross-instance leakage is impossible by design. Every interactive step prints a banner naming both tenants. The single `apply` gate names the destination tenant explicitly.
- **API key is never in chat or context.** Credentials live in `~/wf-envs/<slug>/.env` at mode 600, set by the consultant via `wf-env-setkey.sh` in their terminal. Every API call against a client tenant goes through `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh` — the wrapper sources the active environment's .env and puts `apiKey=` in the URL query string (no key in argv).
- **Prod destination requires explicit acknowledgement.** When the active (destination) client is `WF_ENV_TYPE=prod`, the wrapper refuses every write (exit 3) until `WF_ENV_WRITE_ACK=1` is set per call. After the `apply` gate, surface the prod warning verbatim, get a typed `yes`, then prepend the env var to every wrapper invocation in the 3-or-4-call write sequence.
- **`[wf-reports-verify]` flow is separate.** That flow is exclusively for sanity-checking against the maintainers' own Workfront tenant before suggesting documentation or knowledge-file changes — it uses `wf-curl.sh` + `~/.claude/secrets/workfront/reports-verify.env` + the `[wf-reports-verify]` prefix. See `09-verification-flow.md`. Don't conflate it with the client-side flow.
- **No `uiObjCode` mutation.** A report's `uiObjCode` is the object it reports on (PROJ, TASK, OPTASK, USER, …). Changing it after the fact is destructive — every column in the view becomes invalid because column tokens are resolved against the target object. If the consultant requests a `uiObjCode` change on modify, hard-block and recommend delete-and-recreate. See `05-gotchas.md` #1.
- **Schema discovery before first write.** Before writing to any tenant the skill hasn't seen this session, run the four-call `/metadata` burst (see `04-runtime-schema-discovery.md`). The REPORT object's field schema is not reliably published; runtime discovery is what protects the skill from `uiObjCode`-vs-`reportObjCode` drift.

## API version

All examples in this knowledge bucket use `v17.0`. The version-selection rule lives in `knowledge/api/01-api-fundamentals.md` — short version: v17.0 is the safe floor that works against virtually every modern Workfront deployment, and the repo pins it everywhere by convention so a future bump is a single search-and-replace.

If a consultant tells the skill their instance is on a newer version (e.g., "we're on 22.3"), the skill may switch — but defer that decision to `workfront-api`. This knowledge bucket assumes `v17.0` everywhere.

## Output artifacts per run

None mandatory. Unlike dedicated bulk-update tooling, this skill does not write plan / pre-state / audit files to disk by default.

What the skill *does* print to terminal scrollback:

- The four resolved JSON payloads before the `apply` gate (so the consultant can copy them if they want a record).
- The returned IDs after each POST (`filterID`, `groupByID`, `viewID`, then `reportID`).
- After the REPORT POST: `Report created: $$HOST/report/<reportID>` and `$$HOST/report/<reportID>/view` (the in-app URL pattern is convention — see `05-gotchas.md` #4).
- The smoke-test GET response: `GET /report/<id>?fields=*,definition`, so the consultant can verify the report row references the UI-objects the skill just created (see the silent-re-resolution gotcha, `05-gotchas.md` #5).
- On modify: the pre-state JSON for the report + its three UI-objects, printed before the PUT sequence. That is the manual-rollback artifact.

For runs the consultant wants to persist (smoke-test JSON, the success URL printout, clone sanitization reports), the recipes write them to `~/wf-envs/<dest-slug>/deliverables/<UTC>-report-<verb>.{json,md}`. See `02-create-from-scratch-recipe.md` Phase G and `03-clone-and-adapt-recipe.md` for the exact paths.

## Closing phase: surface divergences back to the skill

If at any point during a run the live API behaviour or a peer report's structure diverged from what this knowledge bucket documents — a field shape mismatch, a missing required field on a POST body, a `valueexpression` pattern that worked in production but is described as impossible here, a new gotcha that bit the run before the `apply` gate caught it — the skill MUST surface that divergence to the consultant before closing the session.

Concretely, before reporting "done":

1. Name the file the divergence belongs in (`knowledge/reports/05-gotchas.md`, `knowledge/textmode/07-combined-and-shared-columns.md`, etc. — usually the file that gave wrong or incomplete guidance).
2. Show the minimum-viable correction as a diff or a paste-ready snippet.
3. Offer to make the edit and commit it to a `skill-update/<short-slug>` branch off `main`, matching the v0.9.x update pattern. Do not push or PR without explicit instruction.

This is what keeps the skill from rotting against the live API. Memory captured by the auto-memory layer is not enough — it sits in `~/.claude/projects/.../memory/` and never makes it back into the shared knowledge bucket. The consultant has the context to judge whether a one-off observation generalises; surface it explicitly rather than silently filing it in personal memory.

A run that diverged from the bucket and did not surface the divergence is incomplete, even if the report write succeeded.

## Cross-references

- The REPORT / UIFT / UIGB / UIVW field map and the AccessRule shape (sharing — stubbed in v1): `01-report-object-shape.md`.
- The end-to-end NL-create + modify walkthrough: `02-create-from-scratch-recipe.md`.
- The cross-tenant clone-and-adapt procedure: `03-clone-and-adapt-recipe.md`.
- The `/metadata` burst, cache shape, and field-name resolution dance: `04-runtime-schema-discovery.md`.
- The silent-failure modes (uiObjCode mismatch, UI-object re-use, locale leak, etc.): `05-gotchas.md`.
- The filter-half (UIFT.definition) field reference: `06-filter-patterns.md`.
- The view-half (UIVW.definition.column[]) and group-half (UIGB.definition.group[]) field reference: `07-view-patterns.md`.
- The pre-flight validation algorithm: `08-pre-flight-validation.md`.
- Auth, `$$HOST` resolution, API version pinning, pagination, error semantics: `workfront-api`.
- Every byte of authoring inside `definition` strings: `workfront-textmode`.
