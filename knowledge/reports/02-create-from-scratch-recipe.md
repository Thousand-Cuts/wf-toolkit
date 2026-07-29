# 02 — Create From Scratch (NL-Create Recipe)

End-to-end walkthrough for creating a new Workfront report via the REST API. Same recipe covers the modify variant (PUT-in-place against existing UI-objects). All wire calls use `--data-urlencode 'updates={JSON}'` form-encoded; raw JSON request body is rejected by the v17.0 endpoint. The `definition` field is a JSON object on every UI-object row, not a stringified DSL payload (see `01-report-object-shape.md` § 1.3). 2, 3, or 4 calls fire depending on whether the report has a filter and a grouping. Every URL uses `v17.0` per `knowledge/api/01-api-fundamentals.md`.

The flow has eight phases. Each phase has a hard handoff — no phase begins until the previous one is acknowledged by the admin. The `apply` gate (Phase E) and the pre-flight gate (Phase D) are both required; neither can be skipped.

```
A. Setup and schema discovery
B. Interview (slot fill)
C. Compose payloads (2/3/4 JSON bodies prepared, in-memory only)
D. Pre-flight validation
E. Single `apply` gate
F. Write (POST sequence)
G. Smoke-test verify
H. Print URLs
```

## Phase A — Setup and schema discovery

### A.1 Resolve the destination environment

Run:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --dest
```

- Exit 0: prints the active slug (the destination environment). Read `~/wf-envs/<slug>/.env` for `WF_HOST`, `WF_ENV_LABEL`, `WF_ENV_TYPE`, `WF_SCOPE_PORTFOLIO_ID`. Echo back for confirmation. Refuse if `WF_READ_ONLY="1"` (this recipe writes).
- Exit 2: no active environment. Tell the admin to register one via `/wf-env-add <slug>`, set the key with `wf-env-setkey.sh <slug>` in their terminal, then `/wf-env-use <slug>`, and re-invoke.

The wrapper handles auth; you never see the API key. Auth specifics (sessionID vs API key vs OAuth2 vs JWT) live in `workfront-api`; this recipe uses the `wf-env-curl.sh` wrapper which puts `apiKey=` in the URL query string.

### A.2 Handshake — confirm the tenant

Before any work, verify the active environment folder's host + key combination points at the customer the admin thinks it does:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/user/search \
  --data-urlencode '$$LIMIT=1' \
  --data-urlencode 'fields=ID,customer:name'
```

Extract `data[0].customer.name` from the response and echo back:

> "Connecting to **<customer-name>** at **<host>** — correct? [y/n]"

On 401/403 — tell the admin to rotate via `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-setkey.sh <slug> --rotate`. On `y` — proceed. No write happens before this `y`.

### A.3 Schema discovery burst

Before the first write of a session against this tenant, run the schema-discovery burst documented in `04-runtime-schema-discovery.md`. The burst now covers FIVE endpoints (v0.9.0 expansion):

- `/report/metadata`
- `/uift/metadata`
- `/uigb/metadata`
- `/uivw/metadata`
- `/<uiObjCode>/metadata` for the target object (e.g., `/proj/metadata` if the report is on PROJ)

The first four are session-wide; the fifth is per-target-object and fetched on first reference. The cache key is host-hashed for 24 hours per `04`. The target-object metadata is what Phase D's pre-flight validator uses to assert field references against the actual target-object field set — catching the PROJ-vs-TMPL "templates are a separate objCode" class of error before any bytes write, per `05-gotchas.md` #9.

If the burst returns 401/403, stop. Auth issues belong in `workfront-api`; this recipe does not retry past a metadata 401.

## Phase B — Interview

The skill walks the admin through the missing slots. Ask only for what the NL brief did not provide. Each ask has a single canonical form:

| Slot | Prompt | Notes |
|---|---|---|
| `uiObjCode` | "What object does this report report on?" | Valid values: PROJ, TASK, OPTASK, USER, HOUR, ASSGN, TPRO, TTSK, DOCU, PRGM, PRFAPL, PARAM, PGRP, and the long tail of standard Workfront object codes. Stored on REPORT, UIFT, UIGB, UIVW (must match on all four). |
| `name` | "What should the report be called?" | This becomes the REPORT row's `name` and the prefix for the three sibling UI-object names (`"<name> — filter"`, etc.). |
| `description` | "Optional description for the report's About panel?" | May be `null`. |
| Filter intent | "What records should this report show? (NL is fine.)" | Convert via `06-filter-patterns.md` to a `UIFT.definition` JSON object. If the admin declines a filter, the skill still writes an empty UIFT (`definition: {}`) per `01-report-object-shape.md` § 2.2. |
| Columns | "What columns should the report show?" | Convert via `07-view-patterns.md` to a `UIVW.definition.column[]` array. The view is always written — a report cannot have `viewID:null`. |
| GroupBy intent | "Should the report group by anything? (Optional.)" | If yes → UIGB.definition.group[] per `07-view-patterns.md` § 12. If no → SKIP the UIGB POST entirely; the REPORT row gets `groupByID: null` and `reportType: "L"` (list) instead of `"A"` (analytical). |
| Chart intent | "Should the report include a chart?" | **v0.9.0 limitation:** the skill can set chart-related booleans on the REPORT row, but the actual chart configuration is NOT persisted via the v0.9.0 API surface (it lives behind `preferenceID`, see `05-gotchas.md` #12). When asked, the skill creates the report as a TABLE and tells the admin to finish chart configuration in the in-product builder at `$$HOST/report/<id>`. |
| Prompts | "Should this report take user-prompted filter parameters?" | Same v0.9.0 limitation as chart. Setting `showPrompts:true` writes through; the prompt parameter definitions do not. v0.10.0 candidate. |
| Sort | "Any sort order? (Optional.)" | Column-level: `column.sortOrder` / `column.sortType` per `07-view-patterns.md` § 2. REPORT-level: `REPORT.sortBy` / `sortType` (rare; only used as a cross-view override). |

If the admin types `edit` at any later phase, return here with prior answers prefilled.

The interview never speculates about filter or column syntax inline. NL ("show projects that are active") becomes a JSON-object filter via the patterns in `06-filter-patterns.md`. NL ("show name, owner, planned completion") becomes a `column[]` array via the patterns in `07-view-patterns.md`. The skill consults those files, not its own memory, on every interview pass.

**Sharecol breadcrumb defaulting.** If the interview surfaces 2 or more metadata pairs that all decorate the primary entity's display cell, compose a sharecol group rather than separate columns. The default layout is `<b>Label: </b>value<br>` stacked, with `displayname` set from the entity type and `<hr>` between the header and the body. Don't prompt the admin for the HTML; surface it at Phase C compose. Reference: `07-view-patterns.md` § 10 has the canonical pattern, the 4 sanitizer rules, and the v0.9.2 live-test rationale (run-together formatting from inline whitespace collapse).

## Phase C — Compose payloads

Print the 2-4 JSON bodies the skill is about to POST, in the order they will fire. The example below uses the canonical brief:

> "Active projects grouped by portfolio with columns name / owner / portfolio / planned completion / % complete."

This is an analytical report — `reportType: "A"`, with a UIGB.

### C.1 UIFT payload (filter)

`POST $$HOST/attask/api/v17.0/uift`

```json
{
  "name": "Active Projects — filter",
  "uiObjCode": "PROJ",
  "filterType": "REPORT",
  "isReport": true,
  "isText": false,
  "isSavedSearch": false,
  "definition": {
    "status": "CUR",
    "status_Mod": "in"
  }
}
```

Required fields per `01-report-object-shape.md` § 2: `name`, `uiObjCode`, `filterType:"REPORT"`, `isReport:true`, `isText:false`, `definition`. `isSavedSearch:false` is conventional. The example's `definition` carries the single `status=CUR` pair and nothing else — **resist the temptation to add a template-exclusion filter on a PROJ report**. PROJ does not expose a template-flag field of its own; templates live under the separate objCode `TMPL`, and trying to filter them out on PROJ causes Workfront to render the report with "Invalid Parameter" in the column header. This is the exact error that broke the v0.8.0 live test on 2026-05-13; see `05-gotchas.md` #9. The Phase D pre-flight validator catches this class of error before any bytes write.

The skill consults `06-filter-patterns.md` § 1-2 for the operator catalogue and the basic `<field>` / `<field>_Mod` shape.

### C.2 UIGB payload (groupBy)

`POST $$HOST/attask/api/v17.0/uigb` — **OMIT this entire call if the admin declined grouping.**

```json
{
  "name": "Active Projects — groupBy",
  "uiObjCode": "PROJ",
  "isReport": true,
  "isText": false,
  "definition": {
    "group": [
      {
        "linkedname": "portfolio",
        "namekey": "portfolio",
        "valuefield": "portfolio:name",
        "valueformat": "string"
      }
    ],
    "textmode": "false"
  }
}
```

Required fields per `01-report-object-shape.md` § 3: `name`, `uiObjCode`, `isReport:true`, `isText:false`, `definition`. The `definition.group` array must contain at least one entry — empty `[]` is rejected by the server with `"No groupings were defined"`. The `definition.textmode` value is a STRING (`"false"` / `"true"`), not a boolean — see `07-view-patterns.md` § 13.

The skill consults `07-view-patterns.md` § 12 for the group-entry field shape.

### C.3 UIVW payload (view)

`POST $$HOST/attask/api/v17.0/uivw`

```json
{
  "name": "Active Projects — view",
  "uiObjCode": "PROJ",
  "layoutType": "LIST",
  "uiviewType": "LIST",
  "isReport": true,
  "isText": false,
  "isNewFormat": true,
  "definition": {
    "column": [
      {
        "descriptionkey": "name",
        "linkedname": "direct",
        "namekey": "name.abbr",
        "valuefield": "name",
        "valueformat": "HTML",
        "listsort": "string(name)",
        "querysort": "name",
        "shortview": "false",
        "stretch": "30",
        "width": "200",
        "link": {
          "lookup": "link.view",
          "linkproperty": [
            {"name": "ID", "valuefield": "ID", "valueformat": "int"}
          ],
          "value": "val(objCode)"
        }
      },
      {
        "descriptionkey": "owner",
        "linkedname": "owner",
        "namekey": "view.relatedcolumn",
        "namekeyargkey": ["owner", "name"],
        "valuefield": "owner:name",
        "valueformat": "string",
        "listsort": "string(owner:name)",
        "querysort": "owner:name",
        "shortview": "false",
        "stretch": "0",
        "width": "150"
      },
      {
        "descriptionkey": "portfolio",
        "linkedname": "portfolio",
        "namekey": "view.relatedcolumn",
        "namekeyargkey": ["portfolio", "name"],
        "valuefield": "portfolio:name",
        "valueformat": "string",
        "listsort": "string(portfolio:name)",
        "querysort": "portfolio:name",
        "shortview": "false",
        "stretch": "0",
        "width": "150"
      },
      {
        "descriptionkey": "plannedcompletiondate",
        "linkedname": "direct",
        "namekey": "plannedcompletiondate",
        "valuefield": "plannedCompletionDate",
        "valueformat": "atDate",
        "listsort": "atDateAsAtDate(plannedCompletionDate)",
        "querysort": "plannedCompletionDate",
        "shortview": "false",
        "stretch": "0",
        "width": "120"
      },
      {
        "descriptionkey": "percentcomplete",
        "linkedname": "direct",
        "namekey": "percentcomplete",
        "valuefield": "percentComplete",
        "valueformat": "asPercent",
        "listsort": "doubleAsDouble(percentComplete)",
        "querysort": "percentComplete",
        "shortview": "false",
        "stretch": "0",
        "width": "100"
      }
    ]
  }
}
```

Required fields per `01-report-object-shape.md` § 4: `name`, `uiObjCode`, `layoutType:"LIST"`, `uiviewType:"LIST"`, `isReport:true`, `isText:false`, `isNewFormat:true`, `definition`. The `definition.column` array must contain at least one entry.

Each column carries the canonical field set documented in `07-view-patterns.md` § 2: `descriptionkey`, `linkedname`, `namekey` (or `namekey:"view.relatedcolumn"` paired with `namekeyargkey:[<relation>, <field>]` for joined-record columns), `valuefield`, `valueformat`, `listsort`, `querysort`, `shortview`, `stretch`, `width`. The primary-name column (first column above) gets a `link` block with `linkproperty[]` per `07-view-patterns.md` § 3 so clicking the row opens the project's detail page.

### C.4 REPORT payload

`POST $$HOST/attask/api/v17.0/report` — fired LAST, after UIFT/UIGB/UIVW have returned IDs.

```json
{
  "name": "Active Projects",
  "uiObjCode": "PROJ",
  "reportType": "A",
  "isReport": true,
  "description": "Active projects grouped by portfolio.",
  "filterID": "<UIFT-ID-from-C.1>",
  "groupByID": "<UIGB-ID-from-C.2>",
  "viewID": "<UIVW-ID-from-C.3>",
  "maxResults": 15,
  "sortBy": null,
  "sortType": null,
  "isStandalone": false
}
```

Required fields per `01-report-object-shape.md` § 1: `name`, `uiObjCode`, `reportType`, `isReport:true`, `filterID`, `groupByID`, `viewID`. Optional but commonly set: `description`, `maxResults` (default 15), `sortBy` / `sortType` (null when column-level sort wins), `isStandalone:false` (hard-coded false in v0.9.0).

`reportType` picks from `"A"` (analytical, grouped) / `"L"` (list, no grouping) / `"M"` (matrix, not supported in v0.9.0):

- If the admin specified at least one group → `"A"` with `groupByID` set.
- If the admin declined grouping → `"L"` with `groupByID: null`.
- Never `"M"` from v0.9.0.

See `01-report-object-shape.md` § 1.1 for the enum semantics.

The skill prints all 2-4 payloads to terminal before Phase D, named with their target endpoint. The admin can request edits at this point; `edit` returns to Phase B with prior answers prefilled.

## Phase D — Pre-flight validation

Run the pre-flight validator against the composed bundle. This is the v0.9.0 gate that catches the "field does not exist on the target object" class of error — the PROJ-vs-TMPL trap from `05-gotchas.md` #9 — before any bytes write.

Source the active environment's .env to make `WF_HOST` and `WF_API_KEY` available to the validator. The script's CLI is unchanged.

```bash
set -a; source ~/wf-envs/<active-slug>/.env; set +a
jq -n \
   --arg uift   "$(cat /tmp/uift-payload.json)" \
   --arg uigb   "$(cat /tmp/uigb-payload.json)" \
   --arg uivw   "$(cat /tmp/uivw-payload.json)" \
   --arg report "$(cat /tmp/report-payload.json)" \
   '{uift: ($uift|fromjson), uigb: ($uigb|fromjson), uivw: ($uivw|fromjson), report: ($report|fromjson)}' \
  | python3 ${CLAUDE_PLUGIN_ROOT}/skills/workfront-reports/scripts/pre_flight_validator.py \
    --from-stdin --host "$WF_HOST" --api-key "$WF_API_KEY" \
  > /tmp/preflight.json
```

The validator returns a structured JSON report with `valid:true|false`, an `errors` array, a `warnings` array, and per-entry suggestions. Algorithm details in `08-pre-flight-validation.md`.

**On `valid:false`** — print the errors with suggestions (e.g., "the template-flag field you referenced is not on PROJ; templates are a separate objCode `TMPL` — drop this filter, or change `uiObjCode` to `TMPL`"). The admin types `edit` to revise. No bytes write. Loop back to Phase B with the offending slot pre-selected for revision.

**On `valid:true` with warnings** — surface the warnings (column-to-uiObjCode coherence checks per `05-gotchas.md` #1, locale-shift on hard-coded dates per `05-gotchas.md` #6) and proceed to Phase E. Warnings are soft signals the admin should see before authorizing the write; they don't block.

**On `valid:true` with zero errors and zero warnings** — proceed to Phase E.

Pre-flight does not write to disk; it does not make write API calls; it reads only from the cached metadata (Phase A.3) plus, at most, a single batched `/parameter/search` GET for DE: field parity. See `08-pre-flight-validation.md` § 2.

## Phase E — Single `apply` gate

Banner template (substitute live values for the placeholders):

> "Writing to **<customer-name>** at **<host>**. Will POST **N×** UIFT, **N×** UIGB, **1×** UIVW, then **1×** REPORT referencing those IDs. Pre-flight: **GREEN** (0 errors, N warnings). Type `apply` to proceed, `edit` to change a field, or anything else to abort."

`N×` for UIFT is `1` (always written, even when empty) and for UIGB is `0` or `1` (0 if the admin declined grouping; 1 otherwise). UIVW and REPORT are always 1 each.

Only the literal string `apply` proceeds. `y`, `yes`, `apply now`, blank-Enter — none of those count. `edit` returns to Phase B with fields prefilled. Anything else aborts.

## Phase F — Write

2-4 POSTs in sequence. Each uses `--data-urlencode 'updates=<json>'` form-encoded; raw JSON body via `-d` is rejected by the v17.0 endpoint. Capture the returned ID from each before firing the next.

If the destination is prod, prepend `WF_ENV_WRITE_ACK=1` after the admin types `yes` at the prod-write-ack prompt (see SKILL.md safety baseline).

```bash
# 1. UIFT (filter)
FILTER_ID=$(WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  -X POST /attask/api/v17.0/uift \
  --data-urlencode "updates=$(cat /tmp/uift-payload.json)" \
  | jq -r '.data.ID')
echo "[1/4] UIFT created: $FILTER_ID"

# 2. UIGB (groupBy) — SKIP this entire block if the admin declined grouping.
GROUP_ID=$(WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  -X POST /attask/api/v17.0/uigb \
  --data-urlencode "updates=$(cat /tmp/uigb-payload.json)" \
  | jq -r '.data.ID')
echo "[2/4] UIGB created: $GROUP_ID"

# 3. UIVW (view)
VIEW_ID=$(WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  -X POST /attask/api/v17.0/uivw \
  --data-urlencode "updates=$(cat /tmp/uivw-payload.json)" \
  | jq -r '.data.ID')
echo "[3/4] UIVW created: $VIEW_ID"

# 4. REPORT — patch the three IDs into the payload first, then POST.
jq --arg fid "$FILTER_ID" --arg gid "$GROUP_ID" --arg vid "$VIEW_ID" \
   '.filterID=$fid | .groupByID=$gid | .viewID=$vid' \
   /tmp/report-payload.json \
   > /tmp/report-payload-resolved.json
REPORT_ID=$(WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  -X POST /attask/api/v17.0/report \
  --data-urlencode "updates=$(cat /tmp/report-payload-resolved.json)" \
  | jq -r '.data.ID')
echo "[4/4] REPORT created: $REPORT_ID"
```

If the admin declined grouping → omit step 2 and pass `null` for `groupByID` in step 4's jq patch (`.groupByID=null` rather than `.groupByID=$gid`).

Wire-format anchors worth repeating:

- The body is `updates=<json>` form-encoded, not raw JSON. Use `--data-urlencode 'updates=...'` so the URL-encoding of the JSON (escaped `{`, `}`, `"`, etc.) is handled by curl.
- The Content-Type header is NOT set. curl's default `application/x-www-form-urlencoded` is what the endpoint expects with `--data-urlencode`.
- The `definition` field inside the JSON is a JSON OBJECT (`{...}`), not a string. The v0.8.0 file described it as a stringified DSL payload; that was wrong (see `01-report-object-shape.md` § 1.3). The in-product Text Mode tab in the report builder produces a stringified human-editable representation; Workfront's UI parses that back into JSON before storing. The wire format is always a JSON object.

## Phase G — Smoke-test verify

Immediately after the REPORT POST returns, GET the report back to detect silent re-resolution per `05-gotchas.md` #5. Save the result to the destination environment's exports folder for the audit trail:

```bash
DEST_SLUG=$(bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --dest)
SMOKE_OUT=~/wf-envs/${DEST_SLUG}/exports/$(date -u +%Y%m%dT%H%M%SZ)-report-create-smoke.json
mkdir -p ~/wf-envs/${DEST_SLUG}/exports
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  /attask/api/v17.0/report/$REPORT_ID \
  --data-urlencode 'fields=*,definition,filterID,groupByID,viewID' \
  | tee "$SMOKE_OUT" | python3 -m json.tool
echo "Smoke-test saved to $SMOKE_OUT"
```

Compare the response's `filterID` / `groupByID` / `viewID` against the IDs captured in Phase F.1, F.2, F.3. If any differ, Workfront silently re-resolved the report to point at a pre-existing UI-object whose `definition` matches byte-for-byte. The report renders correctly, but the UI-object the skill POSTed is now orphaned in the tenant.

Print the diff so the admin knows which sub-objects they actually own:

> "Workfront re-resolved this report's `filterID` to `<existing-uift-id>` (we POSTed `<our-uift-id>`). The report renders correctly, but the UIFT row at `<our-uift-id>` is now orphaned. DELETE curl: `WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh -X DELETE /attask/api/v17.0/uift/<our-uift-id>`."

This is the #1 silent-failure mode for reports authored via API. The smoke-test catches it; without the smoke-test, the admin has no signal.

## Phase H — Print URLs

In-app URL convention per `05-gotchas.md` #4 and `01-report-object-shape.md` § 7. Both forms work:

```
Report created.
  https://<host>/report/<REPORT_ID>
  https://<host>/report/<REPORT_ID>/view
```

The bare URL opens the report's editor (Columns / Groupings / Filters / Chart tabs). The `/view` suffix renders the report immediately as a table or chart. The skill prints both after every create.

## Error handling

Inline only — no auto-rollback, no retry beyond what's listed here. The skill streams DELETE curls for the orphaned UI-objects so the admin has manual rollback in terminal scrollback.

| Failure | Skill response |
|---|---|
| Pre-flight (Phase D) returns `valid:false` | Print errors + per-entry suggestions. Admin types `edit` to revise. No bytes write. |
| UIFT POST fails (Phase F.1) | No UI-objects created yet. Print the API error verbatim. Stop. |
| UIGB POST fails (Phase F.2) | Print: `UIFT created, ID=<filterID>. DELETE curl: WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh -X DELETE /attask/api/v17.0/uift/<filterID>`. Print the API error. Stop. |
| UIVW POST fails (Phase F.3) | Print DELETE curls for both UIFT and UIGB. Print the API error. Stop. |
| REPORT POST fails (Phase F.4) | Print DELETE curls for all three UI-objects. Print the API error. If the error names a specific field, surface the field name and the cached metadata's enum (if applicable). Stop. |
| `uiObjCode` value rejected (Phase F.4) | Print the valid enum from the cached `/report/metadata`. Ask the admin for a new value and retry F.4 with the three UI-objects still in place. The UI-objects' `uiObjCode` does NOT have to match the REPORT row's `uiObjCode` on POST — but the report won't render correctly until it does, so the skill warns. |
| REPORT POST returns success but smoke-test shows re-resolution | Print the diff per Phase G. The report renders correctly; the orphaned UI-objects need manual cleanup. See `05-gotchas.md` #5. |
| Smoke-test GET fails (Phase G) | Likely a permissions issue on the new report (rare). Print the URL and let the admin verify in the UI. |

## Modify flow (the PUT variant)

When the admin gives a report ID or URL and a change ("change the filter to only show projects with planned completion in the next 30 days"), the recipe is a variant of create — GET-then-PUT in place. Same wire-format correction (`--data-urlencode 'updates=...'`). Same pre-flight gate inserted between compose and apply.

1. **GET the report** with everything that might change:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
     /attask/api/v17.0/report/<reportID> \
     --data-urlencode 'fields=*,definition,filterID,groupByID,viewID,uiObjCode' \
     | python3 -m json.tool
   ```
   Note: do NOT request `categoryID` in the fields list. The v0.8.0 file did; the v17.0 endpoint responds with `"APIModel V17_0 does not support field categoryID (PortalSection)"`. Custom-form attachment is via a different (UI-side) mechanism and is not API-writable in v0.9.0. See `01-report-object-shape.md` § 1.

2. **GET each referenced UI-object** with `fields=*,definition`:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
     /attask/api/v17.0/uift/<filterID> \
     --data-urlencode 'fields=*,definition'
   # Repeat for /uigb/<groupByID> and /uivw/<viewID>. Skip a GET if its ID is null.
   ```

3. **Print the current state** — the full JSON for the report and its three UI-objects. This is the rollback artifact; the admin copies it from terminal scrollback if they need to revert. There is no auto-rollback in v0.9.0.

4. **UI-object re-use check.** Before any PUT, search for other reports that reference the same UI-object IDs:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
     /attask/api/v17.0/report/search \
     --data-urlencode 'filterID=<filterID>' \
     --data-urlencode 'fields=ID,name' \
     --data-urlencode '$$LIMIT=20'
   # Repeat with groupByID=<groupByID> and viewID=<viewID>.
   ```
   If more than 1 result comes back per UI-object, it is shared with other reports. PUT-in-place affects every consumer. Two options the skill surfaces:
   1. **PUT in place anyway** — affects every consumer. Useful when the admin wants the change applied to a family of reports.
   2. **POST a new UI-object and re-point only this report.** The skill POSTs a fresh UIFT (or UIGB / UIVW), then PUTs `/report/<reportID>` with `filterID=<new-uift-id>`. The other consumers keep referencing the original.

   The default is option 2 — preserve the other consumers. The admin decides. See `05-gotchas.md` #7.

5. **Compose the new definitions** via `06-filter-patterns.md` / `07-view-patterns.md`. The composed JSON-object `definition` replaces the old one on PUT.

6. **Pre-flight validation** of the new bundle. Same gate as Phase D of create. The validator runs against the composed `{report, uift, uigb, uivw}` shape regardless of whether the bundle is for create or modify.

7. **Single `apply` gate** with a banner naming the destination environment and the IDs that will be mutated. Same wording as Phase E.

8. **PUT in place** against the existing UI-object IDs (preserves IDs and external references). Same wire format as create — `--data-urlencode 'updates=...'`:

   If the destination is prod, prepend `WF_ENV_WRITE_ACK=1` after the admin types `yes` at the prod-write-ack prompt (see SKILL.md safety baseline).

   ```bash
   WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
     -X PUT /attask/api/v17.0/uift/<filterID> \
     --data-urlencode 'updates={"definition":{"status":"CUR","status_Mod":"in","plannedCompletionDate":"$$TODAY+30d","plannedCompletionDate_Mod":"lte"}}'
   ```
   PUT only the fields that need to change — the server merges the patch on top of the existing record. PUT against `/report/<reportID>` when REPORT-level fields change (name, description, sort, maxResults). Repeat the PUT pattern for whichever sub-objects changed; skip the ones that didn't.

9. **Smoke-test GET** as in Phase G of create. PUT can silently re-resolve too (rare but possible — same mechanism as create-time re-resolution per `05-gotchas.md` #5).

### Hard-block on `uiObjCode` change

If the admin requests a `uiObjCode` mutation on modify, **hard-block**. Print:

> "Changing `uiObjCode` is destructive — every column in the view is resolved against the target object, so the report will render empty after the change. Every filter line is similarly resolved. Delete and recreate the report instead."

Then offer to run the create flow with the new `uiObjCode`. See `05-gotchas.md` #1.

## Chart and Prompts (v0.9.0 limitation)

**Charts and prompts are NOT round-tripped via the v0.9.0 API surface.** The chart configuration (chart type, axis fields, color scheme) and the prompt parameter definitions live behind a sibling `preferenceID` resource that the skill does not currently read or write. See `05-gotchas.md` #12 for the full write-up.

What this means in practice:

- The interview's `Chart intent` and `Prompts` slots are captured for the admin's record, but the skill creates the report as a **TABLE**.
- The skill prints: "I've created the report as a table at `$$HOST/report/<id>`. The chart configuration is stored behind a `preferenceID` resource we don't yet write — open the report's editor and use the Chart tab to finish configuration."
- Setting `showPrompts:true` on the REPORT row writes through, but the actual prompt parameter definitions do not. The admin must add prompts via the in-product builder's Prompts tab.

v0.10.0 candidate: probe the `preferenceID` resource against Client C's 2 chart reports to figure out the round-trip.

## Cross-references

- The REPORT / UIFT / UIGB / UIVW field map: `01-report-object-shape.md`. Required-field set per object; auto-populated fields the skill must not set on POST; the `preferenceID` chart-and-prompts spillover.
- Filter JSON-object authoring (`UIFT.definition`): `06-filter-patterns.md`. Operator catalogue, `_Mod` suffixes, OR-groups, EXISTS blocks, session tokens, TAB-separated multi-values, `DE:` prefix on UIFT keys.
- View and group JSON-object authoring (`UIVW.definition`, `UIGB.definition.group[]`): `07-view-patterns.md`. Canonical column shape, link blocks, conditional formatting on row[] / styledef / image, view properties, `valueexpression` columns, the `DE:` prefix asymmetry across UIFT / UIGB / UIVW.
- Pre-flight validation algorithm (Phase D gate): `08-pre-flight-validation.md`. Field-existence checks against cached metadata; enum-value checks; uiObjCode-match checks; required-field checks per object; DE: parity probe.
- Schema cache and the metadata burst: `04-runtime-schema-discovery.md`. Per-host-hash cache; 24-hour TTL; the 5-call burst in Phase A.3.
- Gotchas (REPORT row's empty `definition`, silent re-resolution, chart/prompts spillover via `preferenceID`, UI-object re-use on modify, PROJ-vs-TMPL invalid-field class of error, DE: prefix asymmetry, hard-coded host URLs in `valueexpression`): `05-gotchas.md`.
- The cross-environment clone variant of this recipe: `03-clone-and-adapt-recipe.md`. Same compose → pre-flight → apply → write spine; sanitization phase inserted before compose.
- Auth, `$$HOST` resolution, API version pinning: `workfront-api`. The v0.9.0 skill pins to `v17.0`; auth is handled by the `wf-env-curl.sh` wrapper (API key injected from the active environment's `.env`).
- Text-mode authoring inside `valueexpression` strings (CONCAT, IF, CASE, ROUND, SUB, ISBLANK, brace-bracket field references): `workfront-textmode`. This recipe writes JSON; `workfront-textmode` owns the calc-language DSL inside any `valueexpression` value.
