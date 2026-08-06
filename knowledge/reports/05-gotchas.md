# 05 — Gotchas

Silent-failure modes and load-bearing conventions specific to Workfront report-authoring via the REST API. Each item is a real failure mode the skill must surface proactively — the consultant won't see most of these from the API response alone. All references assume `v17.0` per `knowledge/api/01-api-fundamentals.md`.

---

## 1. `uiObjCode` mismatch produces silent-empty reports

The `uiObjCode` (or `reportObjCode` — name is tenant-discovered per `04-runtime-schema-discovery.md`) names the object the report reports on: `PROJ`, `TASK`, `OPTASK`, `USER`, `TPRO`, `TTSK`, etc. Every column in the view, every line in the filter, every group is *resolved against that object's field set*.

If the view definition references `portfolio:name` but `uiObjCode=TASK`, the column either renders as a join from task to portfolio (works) or as a blank column (fails silently) depending on whether the join is reachable. If the filter references `plannedCompletionDate` on a `uiObjCode=USER` report, the report row writes successfully — and renders zero rows because USER has no `plannedCompletionDate` field.

**The API does not validate column-to-uiObjCode coherence on POST.** The report row succeeds; the report renders empty.

**What the skill does:** before writing the REPORT row, walk every `column.N.valuefield` and `column.N.valueexpression` in the view definition, every `key=value` line in the filter definition, and every `group.N.valuefield` in the groupBy definition. For each leading token (the part before any `:`), check that it exists on `/<uiObjCode>/metadata`. Print a warning per miss. Do not block — the consultant may know about a deliberate cross-object reference the metadata doesn't surface — but make sure the consultant sees the warning before the `apply` gate.

**Modify-flow corollary:** changing `uiObjCode` after the fact invalidates every column. The skill hard-blocks a `uiObjCode` change on modify and recommends delete-and-recreate. See `02-create-from-scratch-recipe.md` "Hard-block on uiObjCode change".

---

## 2. `categoryID` is for the report row itself, not its columns

When a report's filter references a custom-form data extension (`DE:Project Tier`, `DE:Region`, etc.), consultants sometimes try to set `categoryID` on the REPORT row to "make the form available to the report." This does not do what it looks like it does.

- `categoryID` on the REPORT row attaches a custom form *to the report record itself* — exposing custom fields on the report's own "About" panel. Almost never useful.
- For `DE:Project Tier` to be queryable inside a filter / view / groupBy definition, the **target object** (the project, in this example — whatever `uiObjCode` points at) must have a custom form attached that defines the `Project Tier` parameter. Not the report.

**What the skill does:** if the recipe sees a `DE:<name>` reference in any definition string, print a one-line explainer the first time:

> "`DE:<name>` is a custom-field reference. For this column to render values, the **<uiObjCode>** records being reported on must have a custom form attached that defines `<name>`. Setting `categoryID` on the report row itself does NOT do this."

Pair with the parity check from `03-clone-and-adapt-recipe.md` Phase 5 for the cross-tenant case.

---

## 3. Subscriptions and dashboards are NOT touched by modify

If the consultant modifies a report that has subscriptions (`SCHREP` — scheduled report deliveries) or is embedded in dashboards (`PTLSEC` — portal sections referencing the report), the modify writes against the underlying UIFT/UIGB/UIVW/REPORT rows and leaves those external references in place. The next subscription delivery uses the modified report. That's usually the desired behaviour — but the consultant should know.

**What the skill does:** before any modify-flow PUT, run one extra GET to count consumers:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh /attask/api/v17.0/schrep/search \
  --data-urlencode 'reportID=<reportID>' \
  --data-urlencode '$$LIMIT=1' \
  --data-urlencode 'fields=ID'
# And:
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh /attask/api/v17.0/ptlsec/search \
  --data-urlencode 'reportID=<reportID>' \
  --data-urlencode '$$LIMIT=1' \
  --data-urlencode 'fields=ID'
```

Surface counts inline:

> "This report has **2 subscriptions** and **1 dashboard section** referencing it. Your modification will affect each of those without further notice. Proceed?"

This is a soft warning, not a block. The consultant types `apply` to proceed.

---

## 4. In-app URL is convention, not documentation

There is no documented public URL pattern for reports — the in-product builder navigates via internal routes. Empirically, both of these forms work in every modern Workfront UI:

```
https://<host>/report/<reportID>
https://<host>/report/<reportID>/view
```

The bare URL opens the report's editor; the `/view` suffix renders the report immediately. The skill prints both after every create or modify so the consultant has one click into either view.

Workfront may change these URL patterns. If a future version breaks them, switch to whatever the in-product builder is generating — there is no API-level fix.

---

## 5. Silent re-resolution of `filterID` / `groupByID` / `viewID`

Workfront sometimes returns a different `filterID` / `groupByID` / `viewID` than the one we POSTed. The behaviour: when the REPORT POST references a UI-object whose `definition` matches an existing UIFT/UIGB/UIVW row byte-for-byte, the server may re-resolve the REPORT row to point at the pre-existing UI-object and orphan the one we just created.

**Symptoms:** the report renders correctly. But the smoke-test GET shows the report row's `filterID` is some other ID — not the one returned by the UIFT POST in call 1 of the four-call sequence.

**Side effects:**
- The orphaned UIFT/UIGB/UIVW row the skill just created is still in the tenant, unreferenced. The consultant may want to delete it.
- The UI-object the report now points at is shared with whichever other report originally created it. Modifying it via PUT-in-place will affect both reports. See gotcha #7 below.

**What the skill does:** after every REPORT POST, run the smoke-test GET:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh /attask/api/v17.0/report/<reportID> \
  --data-urlencode 'fields=*,filterID,groupByID,viewID'
```

Compare the response IDs against the IDs returned by calls 1–3. Print a diff per mismatch:

> "Workfront re-resolved this report's `filterID` to `<existing-uift-id>` (we POSTed `<our-uift-id>`). The report renders correctly, but the UIFT row at `<our-uift-id>` is now orphaned. DELETE curl: `curl -sS -X DELETE ...`"

This is the #1 silent-failure mode for reports authored via API.

---

## 6. Cross-tenant locale leak

Hard-coded dates in source `definition` strings carry the source tenant's timezone interpretation. Example: a filter line `plannedCompletionDate=2026-04-01\nplannedCompletionDate_Mod=lte` in a source tenant configured for `America/Chicago` means "before 2026-04-01 23:59:59 CDT". The same line on a destination tenant configured for `Europe/London` means "before 2026-04-01 23:59:59 BST" — different absolute instant.

For most filter use cases this difference is in the noise. But for time-sensitive reports (financial close, end-of-quarter, end-of-day cut-offs), the difference is meaningful.

**What the skill does:** during clone-flow Phase 4 sanitisation, every hard-coded date inside any `definition` string lands on the `prompt` list. The consultant chooses one of:

- **Keep** — accept the locale-shift; the date stays as a literal.
- **Replace** — substitute a `$$TODAY`-relative token (e.g., `plannedCompletionDate=$$TODAY+30d`). Tenant-neutral; preferred for "rolling window" reports.
- **Drop** — remove the line entirely.

`$$TODAY` / `$$USER` / `$$NOW` and the other `$$`-prefixed tokens are tenant-neutral and pass through unchanged. Only the literal-date case triggers the prompt.

---

## 7. Workfront silently re-uses UI-object IDs across reports

A consequence of gotcha #5 plus the modify-flow design: a single UIFT/UIGB/UIVW row may be referenced by more than one REPORT. Modifying its `definition` via PUT-in-place affects every report that references it.

**When this matters:** the modify flow. If the consultant wants to "change the filter on report X" and the skill PUT-in-place against the UIFT, every other report referencing that UIFT also gets the new filter.

**What the skill does:** before any modify-flow PUT against a UIFT/UIGB/UIVW row, search for other consumers:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh /attask/api/v17.0/report/search \
  --data-urlencode 'filterID=<filterID>' \
  --data-urlencode 'fields=ID,name' \
  --data-urlencode '$$LIMIT=20'
# Repeat with groupByID=<groupByID> and viewID=<viewID>.
```

If the search returns more than 1 result, the UI-object is shared. Two options the skill surfaces:

1. **PUT in place anyway** — affects every consumer. Useful when the consultant wants the change applied to a family of reports.
2. **POST a new UI-object and re-point only this report.** The skill POSTs a fresh UIFT (or UIGB / UIVW), then PUTs `/report/<reportID>` with `filterID=<new-uift-id>`. The other consumers keep referencing the original.

The default is option 2 — preserve the other consumers — but the consultant decides.

---

## 8. Custom-form parameter parity in clone

A `DE:<name>` reference inside any source `definition` string works on the destination tenant if and only if the destination has a custom field with the exact same name on the same target object. Names are case-sensitive. Spaces matter. Trailing whitespace matters.

The clone flow runs parity checks at Phase 5 per `03-clone-and-adapt-recipe.md`:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh /attask/api/v17.0/parameter/search \
  --data-urlencode 'name=<name>' \
  --data-urlencode 'name_Mod=eq' \
  --data-urlencode 'fields=ID,name,parameterGroup:name' \
  --data-urlencode '$$LIMIT=10'
```

**No match → block.** The skill prints:

> "`DE:<name>` does not exist on `<customer-name-dst>`. Either create the custom field on the destination tenant before re-running, or remove the column / filter line that references it. Type `edit` to revise, anything else to abort."

The skill never auto-strips a `DE:` reference — the consultant's intent matters too much. A missing custom field is almost always a real problem to solve, not a value to silently drop.

**Cross-form ambiguity.** A parameter name may exist on multiple custom forms on the destination. The parity check surfaces the count and the form names; if there's exactly one, it's a match. If there's more than one, the skill warns that the destination has multiple `<name>` parameters and asks the consultant to verify the correct form is attached to the target objects being reported on.

---

## 9. PROJ vs TMPL (and TASK vs TTSK) are SEPARATE objCodes

Adobe Workfront treats project templates (`TMPL`) as a different object type from projects (`PROJ`). A `/project/search` will never return template records — they live at `/template/search`. So filtering a `PROJ`-scoped report with `isTemplate=false` or `isTemplate_Mod=eq` is **invalid** — Workfront responds with `Invalid Parameter: Search Parameter value "isTemplate"` and the report fails to render.

The same applies to TASK vs TTSK (template tasks) — also separate objCodes.

**Empirical evidence:** This was the first error caught in the live v0.8.0 test on 2026-05-13. The "Active Projects" report (`6a04ca1f00d24892550b7385ce2b0b5d` on a live production tenant) was created with a filter that included `isTemplate=false`; the UI rendered an error.

**What the skill does:**
- The pre-flight validator (`08-pre-flight-validation.md`) catches this class of error before the UIFT POST fires. The validator's hard-coded synonym hint table includes `("PROJ", "isTemplate")` → "Templates are a separate objCode (TMPL). Drop this filter or change uiObjCode to TMPL."
- When asked to "exclude templates" from a project report, the right answer is "templates are not in scope of a PROJ report; nothing to exclude." The skill should say this explicitly rather than silently dropping the filter.

Memory: see the `wf-proj-vs-tmpl-objcode` memory in the user's auto-memory store for the canonical version of this rule.

---

## 10. The `DE:` prefix asymmetry across UIFT / UIGB / UIVW

Custom-field references use a `DE:<name>` prefix — but the prefix appears in some locations and is dropped in others. This is a real Workfront convention, not a bug; the skill's sanitizer (`sanitize_clone.py`) and pre-flight validator (`pre_flight_validator.py`) both handle the asymmetry automatically.

| Location | Has `DE:` prefix? | Example |
|---|---|---|
| UIFT.definition KEY | **Yes** | `"DE:Project Tier": "HIGH"` |
| UIVW.column[].querysort | **Yes** | `"querysort": "DE:Launch Date"` |
| UIVW.column[].aggregator.valuefield | **Yes** | `"valuefield": "DE:Duration Delta 2"` |
| UIVW.column[].valuefield | **No** | `"valuefield": "Project Tier"` (drops `DE:`) |
| UIGB.group[].valuefield | **No** | `"valuefield": "Asset Tag"` (drops `DE:`) |

When authoring a filter, ALWAYS write `"DE:<name>"`. When authoring a column or group's `valuefield`, write the bare name. The sanitizer's parity-check phase normalizes across all locations to a single deduplicated set of DE: names per bundle.

**Empirical evidence:** Across 32 reports in the survey, this pattern is universal. Cite `PRGM-high-priority` (UIFT keep) vs `PROJ-exec-report-uivw.json` group (UIGB drop) vs `PROJ-asset-pva-duration-uivw.json` aggregator (UIVW aggregator keep).

---

## 11. Hard-coded host URLs leak through `valueexpression` columns on clone

`valueexpression` columns occasionally embed full `https://<host>.my.workfront.com/<path>` URLs to construct clickable links inside HTML output. Example:

```json
{
  "displayname": "Proof Link",
  "textmode": "true",
  "valueexpression": "CONCAT(\"<a href='https://a live production tenant/document/\",{ID},\"'>View</a>\")",
  "valueformat": "HTML"
}
```

When the consultant clones this report from Client D to a different tenant (Client E, say), the `https://a live production tenant/...` literal goes along for the ride — clicking the link in the cloned report opens Client D's tenant, not the destination's. Embarrassing in front of a client.

**What the skill does:** During clone-flow Phase 4 sanitization, the walker scans every `valueexpression` for `https://[a-z][a-z0-9-]+\.(my|sb01|preview)\.workfront\.com/` patterns. Matches land in the new `host_rewrite` bucket. The interactive review at Phase 5 asks per-entry:

- **Auto-rewrite** — substitute the source host with the destination host (default for most cases)
- **Keep** — leave as-is (rare; only if pointing at a third-party asset that's the same across tenants)
- **Drop** — strip the containing column/expression entirely

**Empirical evidence:** Client D's `OPTASK-rush-L-uivw.json`, `OPTASK-mktg-retail-uivw.json`, `DOCU-proofs-retail-uivw.json`, and `PRFAPL-completed-L-uivw.json` all carry hard-coded `https://a live production tenant/...` strings inside `valueexpression`.

---

## 12. `preferenceID` orphans — chart and prompt configurations are NOT round-tripped

Every Workfront REPORT row carries a `preferenceID` pointing at a sibling resource that holds user-personalization state — including the report's chart configuration (chart type, axis fields) and its prompt (parameter) definitions.

**The v0.9.0 skill does not read or write that sibling resource.** Consequences:

- When the skill CREATES a report, `preferenceID` is auto-minted by Workfront. The report renders correctly as a TABLE. Any chart the consultant requested via interview is documented but not persisted; the consultant must open the report in the in-product builder and configure the chart there.
- When the skill CLONES a report from a source tenant to a destination tenant, the preferenceID points at a source-tenant resource that doesn't exist on the destination. The cloned report renders correctly as a table; charts and prompts that existed on the source are silently NOT carried over.

**Mitigation:** v0.9.0's recipes explicitly route consultants asking for charts/prompts to "set the boolean flag, finish configuration in the in-product builder." See `02-create-from-scratch-recipe.md` § Chart and Prompts.

**v0.10.0 follow-up:** Probe the `preferenceID` resource against Client C's 2 chart reports to figure out the round-trip. Tracked in `docs/roadmap.md`.

---

## 13. Pseudo-fields: real-at-runtime, missing from `/metadata`

Some Workfront query-time field names are **real and accepted by the API** but DO NOT appear in the corresponding `/<uiObjCode>/metadata` response. The pre-flight validator (v0.9.0) blocks them as "no such field on `<uiObjCode>`" — a false positive that forces the consultant to either edit the bundle or override pre-flight.

**Empirical examples (discovered during v0.9.1 live test on a live production tenant, 2026-05-14):**

| uiObjCode | Pseudo-field | Where it's used | In `/metadata`? | Status |
|---|---|---|---|---|
| `OPTASK` | `statusEquatesWith` | Filter key (`statusEquatesWith=NEW`, `_Mod=in`) | NO | Real — Client D's `OPTASK-rush-L` report uses it heavily |
| `OPTASK` | `assignmentsListString` | UIVW column `valuefield` paired with `tile: {"name": "component.assignmentslist"}` | NO | Real — Client B's `DOCU-pending-approval` and others use it as the tile's data source |
| `TASK` | `assignmentsListString` | Same — tile rendering | NO (presumed) | Likely real; same convention as OPTASK |

The class is "query-time pseudo-fields": Workfront's `/search` and `/report` endpoints translate them to canonical fields server-side (e.g., `statusEquatesWith` → an equivalence comparison against `status` + a state table), but they're not exposed as object fields.

**What the skill does (v0.9.1):**
- Pre-flight blocks on the pseudo-field with the standard "no such field" error.
- Consultant workarounds:
  - **For filters:** substitute the canonical field where possible (`statusEquatesWith: "NEW"` → `status: "NEW"`).
  - **For tile valuefields:** replace the tile column with a simpler rendering (e.g., a `<br>`-separated breadcrumb in a sharecol block instead of the assignmentslist tile).

**v0.10.0 fix (planned):** add a hard-coded `PSEUDO_FIELDS` allowlist to `pre_flight_validator.py` keyed on `(uiObjCode, fieldname[, slot])`. Initial entries:
- `(OPTASK, "statusEquatesWith")` → "Query-time pseudo-field for state-equivalence comparison; accepted in UIFT keys."
- `(OPTASK, "assignmentsListString", "uivw.column.valuefield")` → "Tile data source for `component.assignmentslist`; accepted only inside a column with `tile.name = "component.assignmentslist"`."

**v0.11.0+ (self-learning, analog of `workfront-api`'s `[wf-api-verify]` flow):** the validator gains a `--learn` flag; when a consultant says "this field works, trust me" after a pre-flight block, the field name is recorded in a per-tenant whitelist (`~/.cache/wf-claude-toolkit/reports-pseudo-fields-<host-hash>.json`) so future runs against the same tenant accept it. Mirrors `workfront-api`'s self-teaching loop (`skills/workfront-api/SKILL.md` § 92 and `knowledge/api/13-local-verification.md`) where verified gaps land back in the skill knowledge after the consultant confirms.

---

## 14. Curly quotes silently break `valueexpression` and calc fields

Workfront's text-mode parser recognises ONLY straight ASCII quotes — `"` (U+0022) and `'` (U+0027). The Unicode "smart" curlies — `"` (U+201C), `"` (U+201D), `'` (U+2018), `'` (U+2019) — are NOT recognised. A `valueexpression` like `IF({percentComplete}=0,"0% complete","other")` (curly) parses as a single unterminated string token; the IF chain breaks; the column renders empty or shows the raw expression with no error.

This bites HARDEST when consultants compose long IF chains in Google Docs / Word / Slack / Notion (all of which auto-substitute curly quotes on insertion) and paste into the in-product Text Mode tab. Standard fix: paste through a plain-text editor first (TextEdit on macOS in plain mode, Notepad on Windows), or pipe through `sed`:

```bash
pbpaste | sed 's/[“”]/"/g; s/[‘’]/'"'"'/g' | pbcopy
```

The same rule applies to calculated custom-field formulas in custom forms — the form-builder's "Calculated" field type uses the same parser. Round-tripped bundles are safe: every `valueexpression` and formula that has been through a successful POST / GET cycle is already straight-quoted, because the parser strips invalid input on store. The curly-quote risk is purely an authoring-from-scratch issue, not a clone issue.

**Pre-flight detection (v0.16.1+):** `pre_flight_validator.py` scans every `valueexpression`, `aggregator.valueexpression`, and `group.valueexpression` string in the bundle for the four curly chars and emits a hard error per match — with the path, the offending value, and a sed-fix suggestion. The lint runs BEFORE the brace-reference scan since a curly-quoted expression is syntactically broken anyway. The authoring interview still echoes composed expressions back for visual confirmation as a belt-and-braces check; the lint catches the case where a consultant pastes a pre-built expression past the interview.

Cross-link: `knowledge/reports/07-view-patterns.md` § 6 "Quote characters: straight ASCII only" has the rendering-side detail.

## 15. Hours-suffix `H` works on `actualWork` but NOT `actualWorkRequired`

Workfront stores all duration fields in **minutes** internally. The `_Mod=gt`/`_Mod=lt` filters compare in minutes. So a naive filter "tasks with more than 10 actual hours" fails:

```json
{ "actualWorkRequired": "10", "actualWorkRequired_Mod": "gt" }   // matches >10 MINUTES — wrong
```

Two fixes, with a non-obvious split:

**Fix A — explicit minutes.** Multiply the hours by 60 and stringify:

```json
{ "actualWorkRequired": "600", "actualWorkRequired_Mod": "gt" }  // >10 hours, correct
```

Works on every duration field; portable.

**Fix B — `H` suffix shorthand, BUT only on `actualWork` (not `actualWorkRequired`).**

```json
{ "actualWork": "10H", "actualWork_Mod": "gt" }   // works
{ "actualWorkRequired": "10H", "actualWorkRequired_Mod": "gt" }   // DOES NOT WORK
```

Adobe's advanced-reporting training day 1 documents this asymmetry empirically: the trainer demonstrated `actualWorkRequired=10H` failing (returns zero matches even when matching rows exist), then switched to `actualWork=10H` which worked, then switched back to `actualWorkRequired` with `600` (explicit minutes) which also worked. Same pattern on `plannedWork` vs `plannedWorkRequired` (the `*Required` variants reject the suffix).

The split is undocumented in Workfront's API reference. Empirically: the bare `actualWork` / `plannedWork` fields run through a display-formatter that recognises `H`/`h`, `D`/`d`, `W`/`w`, `M`/`m` suffixes; the `*Required` variants compare raw stored minutes and treat the suffix as part of the literal value (so `"10H"` is parsed as a non-numeric string and fails the numeric comparison silently).

**Skill behaviour.** When the consultant says "tasks with more than 10 hours of actual work," the interview asks which field. Default: `actualWorkRequired` with explicit-minutes value (`600`), because `actualWorkRequired` is the canonical reporting field most existing reports use. The `actualWork` form with `H` suffix is offered as a shorthand alternative; consultant chooses.

## 16. Custom-form calculated fields don't auto-update existing records

A formula change in a custom-form Calculated field (e.g., changing `Project.ActualHours - Project.PlannedHours` to `Project.PlannedHours - Project.ActualHours`) does NOT retroactively recompute the field on existing records. Every record retains its last-computed value until something triggers a recalc. Three triggers:

- The record is saved through the in-product UI (any save — including the user editing an unrelated field — recomputes all calculated fields on that record).
- A bulk "Recalculate Custom Expressions" action is run from the record list (Project / Task / Issue / etc. list view → "Edit" → bulk-edit dialog → "Recalculate Custom Expressions" checkbox → Save).
- The record is touched via the `POST /attask/api/v17.0/<objcode>/<id>` endpoint with `updates={...}` (any update body — even empty `updates={}` — triggers recalc on save).

**Why it matters for reports.** A report column that references a calculated field via `valuefield: "DE:My Calc Field"` shows STALE values for records that haven't been touched since the formula changed. Symptoms: a fresh report after a formula bugfix shows half the rows with the old wrong values and half with the new right ones, depending on which records have been saved recently. The fix is operational (run the bulk recalc), not in the report itself.

**Cross-skill note.** This is properly a `workfront-calc-fields` concern; the gotcha is restated here because the symptom surfaces FIRST in a report. The dedicated bulk-update tooling skill has a recipe for the bulk-recalc trigger.

Calculated COLUMNS (defined in the UIVW via `valueexpression`, NOT in a custom form) recompute on every report render — they have no staleness problem. The split between "calculated field" (stored, stale until recalc) and "calculated column" (computed at render, never stale) is documented in Adobe's advanced-reporting training day 2.

## 17. EXISTS filters: Adobe documents 5 as the hard cap; prompts are the escape hatch

Adobe's filters-overview docs ([experienceleague.adobe.com](https://experienceleague.adobe.com/en/docs/workfront/using/reporting/reports/report-elements/filters-overview)) pin the limit explicitly: a filter "can reference only five objects, excluding the report object." Beyond that, Workfront's reporting engine usually errors out — Adobe's Aug 2025 Skill Exchange session "Elevate Workfront Reporting with Advanced Text Mode" (Nathan Johnson) confirms it empirically: large EXISTS-stacks return a server error rather than a slow render. The exact failure point above 5 is tenant-dependent (data volume affects when the join planner runs out of budget); 5 is the documented stated cap.

**The escape hatch is custom prompts.** A custom prompt lets you declare 10, 20, 30 EXISTS conditions in the prompt definition, but only ONE of them fires per query — the one the consultant picked from the prompt dropdown. Each prompt option is parsed as a self-contained EXISTS clause on a single line (joined with `&` in place of newlines per the prompt-line-break convention; see § 11 prompts roadmap entry and `09-verification-flow.md`).

**Skill behaviour (v0.16.2+).** Pre-flight counts distinct `EXISTS:<letter>:` letter blocks in `UIFT.definition` keys. At 4 (one shy of Adobe's stated cap), the validator emits a warning ("approaching the EXISTS-per-report cap; consider migrating to prompt-driven filtering"). At 5+ it emits a hard error that `--force` overrides for the rare tenants tolerating 6. The consultant's typical response is to refactor: hoist the EXISTS blocks into a custom prompt with one option per intended filter, or split the report into two.

**Confirmed in production.** The Client A bundle (`PROJ-planning-grid-NOFILTER`) deliberately ships with zero EXISTS clauses for this reason — the report runs on a base UIFT, and the consultant filters interactively. Client D's `OPTASK-rush-L` uses 2 EXISTS blocks and is safely below the limit.

## 18. `actualCompletionDate` is sticky across close-reopen-reclose cycles

When a project (or task) is first marked Complete, Workfront populates `actualCompletionDate` with the timestamp. **Reopening the record does NOT clear the field.** Marking the record Complete a SECOND time OVERWRITES the field with the new timestamp. The original first-complete date is lost.

Adobe's Aug 2025 Skill Exchange Q&A documents this as a real customer pain point: a project marked complete on 2024-12-01, reopened on 2025-01-15, then re-completed on 2025-03-22 reports `actualCompletionDate = 2025-03-22`, with no system-side record of the original 2024-12-01 close. Reports that show "projects completed in December 2024" miss this project; reports that show "projects completed in 2025 Q1" include it.

**Workaround pattern — custom calculated field with self-blank guard.** A custom form field with the formula:

```
IF(ISBLANK({First Completed Date}), {actualCompletionDate}, {First Completed Date})
```

…captures the first non-blank value and HOLDS it across subsequent reopen/reclose cycles. The field references ITSELF (`{First Completed Date}` is the field's own name). On first save with the project complete, the formula evaluates `IF(ISBLANK(<blank>), <today>, <blank>) → <today>` and stores it. On every subsequent recalc — including after a reopen-reclose — the formula evaluates `IF(ISBLANK(<originally-captured>), <new>, <originally-captured>) → <originally-captured>` and the value sticks.

**Caveat per gotcha #16:** custom-form calculated fields don't auto-update existing records when the formula changes, AND don't recalculate unless something triggers a save. The first-completion capture only fires once Workfront's recalc runs against a record with a non-blank `actualCompletionDate`. Backfilling historical data requires a bulk "Recalculate Custom Expressions" on the records that were already complete before the field was added.

**Skill behaviour.** A reports-flow query that filters or groups on `actualCompletionDate` and aims at "first completion" semantics should prompt the consultant: "actualCompletionDate is sticky across reopen/reclose; if you need the original first-complete date, use a custom captured field instead." The skill does NOT auto-substitute (the consultant may genuinely want last-completion semantics).

## 19. Text-mode groupings break the Summary tab and any chart on the report

When a UIGB uses a `valueexpression`-based grouping (any group entry with `textmode: "true"` and a `valueexpression` instead of a bare `valuefield`), Workfront's Summary tab and any auto-chart configured on the report **silently break**: the Summary page renders empty rows, and a configured chart either fails to render or shows zero-count buckets for every value-expression-grouped result.

Adobe's Aug 2025 Skill Exchange session confirms this is a known engine limitation, not a configuration bug: "if you're using text mode in your groupings, it's probably going to break your charts and the summary page" (Nathan Johnson). The Workfront chart renderer expects a flat, server-resolvable field reference for its group axis; valueexpression-grouped buckets are resolved post-aggregation and the chart layer doesn't see them.

**Workaround pattern — push the calc into a custom-form field.** Instead of grouping on a `valueexpression` in the UIGB, create a custom calculated field on the underlying object with the same formula, then group on the custom field as a bare `valuefield`:

```
// Custom form field "Percent Range" on Project:
//   Calculated formula:
//     IF(percentComplete=0,"0%",IF(percentComplete<11,"1% to 10%", ...))

// In the UIGB.definition.group entry:
{
  "linkedname": "direct",
  "namekey": "Percent Range",
  "valuefield": "Percent Range",
  "valueformat": "customDataLabelsAsString"
}
```

The grouping now references a stored field (the form field's pre-computed value), which the Summary tab and the chart engine both understand. Trade-off: the custom-form field doesn't auto-update on formula changes (gotcha #16) and doesn't recompute live (gotcha #15 cross-link).

**Skill behaviour.** When the consultant requests a grouped report AND specifies "with a chart" or "with the summary view enabled," and the grouping logic is non-trivial (range buckets, conditional categories, etc.), the interview offers two paths: (a) text-mode-grouped report WITHOUT a working chart/summary, or (b) custom-form-field-backed grouping WITH a working chart/summary. The consultant picks; the skill does not silently choose. Cross-link to `workfront-calc-fields` for the field setup.

---

## Cross-references

- The REPORT / UIFT / UIGB / UIVW field map: `01-report-object-shape.md`.
- The recipes that surface each of these gotchas inline: `02-create-from-scratch-recipe.md`, `03-clone-and-adapt-recipe.md`.
- The `/metadata` burst and cache that powers gotcha #1's column-coherence check: `04-runtime-schema-discovery.md`.
- The text-mode language the gotchas reference (`DE:<name>`, `$$TODAY`, `EXISTS:N:`, etc.): `workfront-textmode`.
- Auth, `$$HOST`, version pinning: `workfront-api`.
