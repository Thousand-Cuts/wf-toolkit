# 01 — Report Object Shape

This file documents the field maps of the four objects a Workfront report writes to:

- **REPORT** — the parent row, objCode `PTLSEC` (PortalSection)
- **UIFT** — the filter
- **UIGB** — the groupBy
- **UIVW** — the view

A "report" in Workfront's REST surface is not a single record. It is a `PTLSEC` row that holds three foreign keys (`filterID`, `groupByID`, `viewID`) into three sibling UI-object tables. The skill's create flow writes the three UI-objects first, then the REPORT row referencing them, in that order.

Field-level pattern detail for `definition` lives in:

- `06-filter-patterns.md` — UIFT.definition (the `<field>` / `<field>_Mod` JSON-object shape, `EXISTS:` blocks, `$$` placeholders).
- `07-view-patterns.md` — UIVW.definition (column[], row[], property) and UIGB.definition (group[]).

This file covers **top-level row fields only**. Every definition shape lives in `06`/`07`.

Empirical grounding: every field-map table below is sourced from an anonymized survey of 33 reports across five client tenants (30 UIFT, ~30 UIGB, 33 UIVW). Counts in the prose ("32/32", "30/30") are survey hit-rates.

---

## 1. The REPORT row (objCode `PTLSEC`)

Endpoint: `$$HOST/attask/api/v17.0/report`

The REPORT row's own `objCode` is **`PTLSEC`** (PortalSection). The legacy three-letter code that one would expect by pattern-matching on `PROJ`/`TASK` does not exist on the v17.0 surface — `/attask/api/v17.0/<that-code>/metadata` returns 404. PTLSEC is the underlying object type for both reports and dashboard sections; `isReport=true` is the discriminator.

The field this row uses to name the object it reports on is **`uiObjCode`**. The intuitive guess "report-prefixed objCode field name" is wrong — there is no such field; `objCode` always equals `"PTLSEC"` (it names the REPORT row's own type, not its target). `uiObjCode` is canonical across every tenant in the survey (33/33).

Total field count from `/report/metadata` and the survey GETs: 58–60 depending on whether the optional `scheduledReportID` and a handful of internal/null-valued fields appear. The table below covers the 30-ish fields that matter for create-flow authoring; the remaining ~30 are auto-populated, internal, or never set.

| Field | Type | Required on POST? | Notes |
|---|---|---|---|
| `name` | string | YES | Display name shown in the in-product UI. Convention: prefix with the uiObjCode in casual reports (e.g. `"PROJ — Active by portfolio"`) is consultant taste; not required. |
| `uiObjCode` | string | YES | The object reported on. Valid values include `PROJ`, `TASK`, `OPTASK`, `USER`, `HOUR`, `ASSGN`, `PARAM`, `PGRP`, `PRFAPL`, `TTSK`, `DOCU`, `PRGM`, plus a long tail of less-common Workfront object codes. The skill's `validate_uiobjcode` pre-flight check resolves this against cached `/<uiObjCode>/metadata`. |
| `reportType` | enum | YES | `"A"` analytical/grouped, `"L"` list (UIGB optional), `"M"` matrix (unverified in survey). See § 1.1. |
| `isReport` | bool | YES | Always `true` for a report row. Distinguishes a report from a raw PTLSEC dashboard section (which uses the same objCode but with `isReport=false`). |
| `filterID` | uuid \| null | YES | UIFT ID written in Phase F.1, or literal `null` for a no-filter report. |
| `groupByID` | uuid \| null | YES | UIGB ID written in Phase F.2, or literal `null` for a list report with no grouping. |
| `viewID` | uuid | YES | UIVW ID written in Phase F.3. Never null — a report always has a view. |
| `description` | string \| null | optional | Free-form description; null is fine. |
| `maxResults` | int | optional | Row cap. Defaults observed in survey: `15` (most common), `100`, `200` (analytics-heavy reports), `0` (treated as "no override"). |
| `sortBy` / `sortType` | string \| null | optional | REPORT-level sort override. Rare; usually null because column-level sort on the view wins. |
| `sortBy2` / `sortType2` / `sortBy3` / `sortType3` | string \| null | optional | Secondary/tertiary sort. Almost always null in survey. |
| `isStandalone` | bool | optional | Hard-code `false` in v0.9.0; 0/33 standalone in survey. Standalone behavior is a v0.10.0 candidate. |
| `enablePromptSecurity` | bool | optional | Set to `false` in v0.9.0; runtime semantics undocumented. |
| `showPrompts` | bool | optional | `true` means "the report exposes user-prompted filter parameters at run time." The actual prompt definitions are NOT stored on this row — they live behind `preferenceID`. See `05-gotchas.md` #12. |
| `defaultTab` | string | optional | UI hint. `"C"` is universal in survey (33/33); means "open to the Columns tab in the in-product builder." |
| `reportFolderID` | uuid \| null | optional | Folder organization. `null` in 33/33 survey samples; populated only when the user has explicitly filed the report. |
| `runAsUserID` / `publicRunAsUserID` / `publicToken` | string \| null | optional | The public-report mechanism (no-auth shareable URL). `null` in 33/33 survey samples; out of scope for v0.9.0. |
| `forceLoad` / `ganttOpen` | bool | optional | UI hints. `false` in survey. |
| `definition` | object | always `{}` for reports | The REPORT row's own `definition` is empty `{}`. The actual filter/group/view definitions live in the referenced UIFT/UIGB/UIVW rows. **Do not** put a filter or column block here — it is silently ignored. |
| `categoryID` | string | NOT SUPPORTED | The v0.8.0 file referenced this; it returns `"APIModel V17_0 does not support field categoryID (PortalSection)"` if you try to set it on v17.0. Custom forms attach to reports via a different mechanism (UI-side; not API-writable in v0.9.0). |

### 1.1 `reportType` enum semantics

| Value | Meaning | Survey count | Pick when |
|---|---|---|---|
| `"A"` | Analytical (grouped, often with subtotals/charts) | 29 + 31 (two surveys) | UIGB is present (`groupByID != null`) |
| `"L"` | List (flat rows, no grouping required) | 17 + 18 | `groupByID: null`; pure list output |
| `"M"` | Matrix (cross-tab) | 0 in survey | Authoring a matrix layout. Unverified; defer in v0.9.0. |

Heuristic for the create flow: if the consultant declined grouping, write `"L"` and `groupByID: null`. If they specified at least one group dimension, write `"A"` and `groupByID: <UIGB ID>`. Never write `"M"` from the v0.9.0 skill.

### 1.2 Auto-populated REPORT fields (do not set on POST)

These appear on GET but the server rejects or overrides them on POST:

`ID`, `appGlobalID`, `controllerClass`, `currency`, `customerID`, `descriptionKey`, `enteredByID`, `extRefID`, `filterControl`, `globalUIKey`, `groupControl`, `isAppGlobalEditable`, `isNewFormat`, `isPublic`, `lastUpdateDate`, `lastUpdatedByID`, `methodName`, `modDate`, `nameKey`, `objID`, `objInterface`, `objObjCode`, `preferenceID`, `scheduledReportID`, `securityAncestorsDisabled`, `securityRootID`, `securityRootObjCode`, `specialView`, `toolBar`, `viewControl`, `width`.

The clone flow's `sanitize_clone.py` strips all of these from the source-tenant copy before re-POSTing into the destination tenant.

### 1.2.1 The `preferenceID` resource (chart + prompts spillover)

`preferenceID` is a UUID that points at a sibling resource holding the report's chart configuration and prompt definitions. The v0.9.0 skill does NOT write this resource directly — `showPrompts:true` and any chart-related booleans set on the REPORT row write through, but the actual chart shape and prompt parameters do not round-trip via the documented `/preference` endpoint. See `05-gotchas.md` #12 for the full write-up. v0.10.0 candidate.

### 1.3 What the REPORT row's `definition` is NOT

The v0.8.0 file described REPORT.definition as a serialized text-mode payload. That description was wrong. The wire shape is a JSON object — and on the REPORT row specifically, it is empty `{}` in 33/33 survey samples. The confusion in v0.8.0 came from the in-product "Text Mode" tab in the report builder, which produces a stringified human-editable representation of the UIFT/UIGB/UIVW definitions. That representation is parsed back into JSON before being stored. The wire format is always a JSON object.

---

## 2. The UIFT row (filter)

Endpoint: `$$HOST/attask/api/v17.0/uift`

Created in Phase F.1 of the create flow. The skill captures the returned `ID` and writes it into the REPORT row's `filterID` in Phase F.4.

| Field | Type | Required on POST? | Notes |
|---|---|---|---|
| `name` | string | YES | Convention: `"<report-name>"` (the in-product UI re-uses the parent report's name) or `"<report-name> — filter"` for the skill's audit log. Either works on POST. |
| `uiObjCode` | string | YES | MUST match the parent REPORT's `uiObjCode`. Pre-flight check `uiObjCode-match` enforces this. |
| `filterType` | enum | YES | `"REPORT"` — NOT `"STANDARD"`. 30/30 in survey. `"STANDARD"` is the filter-bar-only enum (saved filters that don't belong to a report). Writing `"STANDARD"` on a report's UIFT silently produces a filter the parent report can reference but the in-product builder won't load correctly. |
| `isReport` | bool | YES | `true` for filters used in reports. Pair with `filterType:"REPORT"`. |
| `isText` | bool | YES | `false` for filters composed in JSON (the skill's path); `true` if any block was authored via the in-product Text Mode tab. This flag is a hint to the builder UI, not a constraint on the wire format. The definition is JSON either way. |
| `isSavedSearch` | bool | optional | `false` for report filters. `true` is for saved searches (filter-bar) that aren't bound to a report. Default `false`. |
| `definition` | object | YES | The actual filter content. JSON object — see `06-filter-patterns.md` for the `<field>` / `<field>_Mod` shape, EXISTS blocks, and `$$` placeholders. |

### 2.1 Auto-populated UIFT fields

`ID`, `appGlobalID`, `customerID`, `enteredByID`, `extRefID`, `globalUIKey`, `isAppGlobalEditable`, `isPublic`, `lastUpdateDate`, `lastUpdatedByID`, `modDate`, `nameKey`, `objCode` (server sets `"UIFT"`), `objObjCode`, `preferenceID`, `securityAncestorsDisabled`, `securityRootID`, `securityRootObjCode`.

### 2.2 Empty / minimal UIFT

A filter with `definition:{}` is legal — it produces an unfiltered report (every row of the uiObjCode that the user has read access to). The skill writes empty filters when the consultant explicitly declines a filter intent. The alternative is to write `filterID:null` on the REPORT row; both forms render the same in the UI, but the survey shows tenants overwhelmingly write an empty UIFT rather than null (29/30 reports have a non-null `filterID`).

The skill's convention in v0.9.0: write an empty UIFT (consistent with survey practice; downstream modify flows have a record to PUT against).

---

## 3. The UIGB row (groupBy)

Endpoint: `$$HOST/attask/api/v17.0/uigb`

Created in Phase F.2 of the create flow when the consultant has specified grouping. Skipped entirely when they have not (in which case `groupByID:null` on the REPORT row and `reportType:"L"`).

| Field | Type | Required on POST? | Notes |
|---|---|---|---|
| `name` | string | YES | Convention: `"<report-name>"` or `"<report-name> — groupBy"`. |
| `uiObjCode` | string | YES | MUST match the parent REPORT's `uiObjCode`. |
| `isReport` | bool | YES | `true`. |
| `isText` | bool | YES | `false` for skill-authored UIGB; `true` if Text Mode tab was used. Definition is JSON either way. |
| `definition` | object | YES | `{"group": [<one or more group entries>], "textmode": "false"}`. The `group` array must contain at least one entry — empty `[]` is rejected with the server error `"No groupings were defined"`. See `07-view-patterns.md` § 12 for the group-entry field shape. |

### 3.1 Auto-populated UIGB fields

Same shape as UIFT (`ID`, `appGlobalID`, `customerID`, `enteredByID`, audit timestamps, `objCode:"UIGB"`, `objObjCode`, `preferenceID`, `securityRootID`, `securityRootObjCode`, etc.).

### 3.2 The `textmode` string inside UIGB.definition

`definition.textmode` is a stringified boolean (`"false"` / `"true"`), NOT the actual `isText` boolean on the UIGB row. The string is a builder-UI hint that flags whether the group block was authored in the Text Mode tab. Pre-flight does not enforce its value; the skill writes `"false"` by convention.

---

## 4. The UIVW row (view)

Endpoint: `$$HOST/attask/api/v17.0/uivw`

Created in Phase F.3. Always written — a report cannot have `viewID:null`.

| Field | Type | Required on POST? | Notes |
|---|---|---|---|
| `name` | string | YES | Convention: `"<report-name>"` or `"<report-name> — view"`. |
| `uiObjCode` | string | YES | MUST match the parent REPORT's `uiObjCode`. |
| `layoutType` | enum | YES | `"LIST"` is the only verified value in 33/33 survey samples. The Workfront UI exposes `CALENDAR`, `GRID`, `MATRIX` and `TIMELINE` as well; the skill restricts to `"LIST"` in v0.9.0. |
| `uiviewType` | enum | YES | `"LIST"` — same enum range as `layoutType`. Usually identical to `layoutType` (33/33 in survey). The dual-field design predates a planned but never-shipped split; treat as redundant and write the same value. |
| `isReport` | bool | YES | `true`. |
| `isText` | bool | YES | `false` for skill-authored views. UIVW's text-mode flag tracks whether the view as a whole was authored in Text Mode tab; column-level `textmode:"true"` on individual columns (for `valueexpression`-driven columns) does NOT flip the row-level flag. |
| `isNewFormat` | bool | YES | `true` — required for the modern in-product render path. Legacy `false` views are display-only on read-only screens; do not write `false` in v0.9.0. |
| `definition` | object | YES | `{"column": [<column objects>], "row": [<row formatting>], "property": {<view properties>}}`. `column` is required (at least one entry). `row` and `property` are optional. See `07-view-patterns.md` for the full column shape, link blocks, conditional formatting on row[], and the available property keys. |

### 4.1 Auto-populated UIVW fields

`ID`, `appGlobalID`, `customerID`, `enteredByID`, audit timestamps, `objCode:"UIVW"`, `objObjCode`, `preferenceID`, `securityRootID`, `securityRootObjCode`, `isDefault` (defaults to `false` for user-created views; `true` is reserved for system-default views per-object).

### 4.2 `isDefault`

`isDefault:false` is correct for every report-attached view. The `true` value is reserved for views that the platform itself ships as the per-object default (e.g. the default Project list view). The skill never writes `true`.

---

## 5. Why field names are NOT runtime-discovered

The v0.8.0 file documented `/report/metadata` discovery on the assumption that the field naming the target object (`uiObjCode`) was tenant-variable — that a per-tenant metadata fetch was needed to find the correct name. They are not tenant-variable. `uiObjCode` is the canonical name across every Workfront tenant; the survey shows 33/33 tenants using exactly that name, with exactly that casing.

The schema cache (`04-runtime-schema-discovery.md`) is still useful, but for a different purpose:

- **Pre-flight validation of field existence on the target uiObjCode.** When the consultant asks for a column named `isTemplate` on a `PROJ` report, the skill needs to know that `PROJ` does not expose `isTemplate` (that field lives on `TMPL`). The cached `/PROJ/metadata` answers that question.
- **Enum value enumeration.** Cached metadata gives the valid enum values for fields like `status` on `PROJ`, so the filter composer can reject typos.
- **Reference-relation traversal.** Cached metadata tells the skill that `portfolio:name` is a valid reference traversal on `PROJ` (because `PROJ` has a `portfolio` reference, and `PFOLIO` has a `name` field).

The create flow does NOT discover field names like `uiObjCode`, `filterType`, `layoutType`, `isNewFormat`, or any of the other REPORT/UIFT/UIGB/UIVW row-level fields at runtime. Those are hard-coded in `02-create-from-scratch-recipe.md`, frozen against the empirical survey. If Workfront ships a future major API surface that renames them, the skill breaks loudly — and that's the right failure mode for a known-canonical set.

The fixture set under `skills/workfront-reports/tests/fixtures/metadata/` captures the canonical metadata for offline pre-flight tests.

---

## 6. The AccessRule object (sharing — stubbed in v0.9.0)

ObjCode: `ACSRUL`. Endpoint: `$$HOST/attask/api/v17.0/acsrul`.

Fields (per `python-workfront` v40 and Adobe's API explorer):

| Field | Type | Notes |
|---|---|---|
| `accessorID` | uuid | The USER/TEAM/GROUP/ROLE record being granted access |
| `accessorObjCode` | enum | `USER`, `TEAM`, `GROUP`, or `ROLE` |
| `securityObjCode` | string | Set to the report's objCode `"PTLSEC"` |
| `securityObjID` | uuid | The newly-created report's ID |
| `coreAction` | enum | `VIEW` (read-only) or `EDIT` (read-write) |

The v0.9.0 skill documents the shape here but does NOT write AccessRules. Reports created by the skill inherit the consultant's own access; sharing the report with other users/teams/groups is a manual step in the in-product UI after creation, or a v0.10.0 candidate for an `accessRules:[{...}]` slot in the interview.

The clone flow likewise does not carry source-tenant AccessRules into the destination tenant — accessor IDs are tenant-local and would not resolve. The skill prints a manual-share reminder after every clone.

---

## 7. In-app URL pattern

Convention, not documented by Adobe but verified across every tenant in the survey. Both forms work:

- `$$HOST/report/<report-id>` — opens the report editor (the four-tab builder UI: Columns / Groupings / Filters / Chart).
- `$$HOST/report/<report-id>/view` — renders the report immediately (the table or chart output, without the editor chrome).

The skill's Phase H prints both after every create:

```
Report created.
  https://<host>/report/<REPORT_ID>
  https://<host>/report/<REPORT_ID>/view
```

`<report-id>` is the PTLSEC row's `ID` — the same UUID returned in `data.ID` from the Phase F.4 POST.

---

## 8. Cross-references

- **Filter half** (UIFT.definition) → `06-filter-patterns.md`. The `<field>` / `<field>_Mod` JSON-object shape, EXISTS blocks, `$$` placeholders, OR-block grouping, custom-field references (`DE:` prefix).
- **View half** (UIVW.definition) and **group half** (UIGB.definition.group[]) → `07-view-patterns.md`. Column shape, link blocks, conditional formatting on row[], view properties, valueexpression columns, the canonical column field set (`descriptionkey`, `linkedname`, `valuefield`, `valueformat`, `listsort`, `querysort`, `shortview`, `stretch`, `width`).
- **Pre-flight validation** of every payload before POST → `08-pre-flight-validation.md`. Field-existence checks against cached metadata; enum-value checks; uiObjCode-match checks; required-field checks.
- **Schema cache TTL + invalidation** → `04-runtime-schema-discovery.md`. Per-host, per-uiObjCode caching of `/<uiObjCode>/metadata`.
- **Auth, $$HOST resolution, API version pinning** → `workfront-api`. The v0.9.0 skill pins to `v17.0`; auth header is `apiKey: <key>`.
- **Every byte of authoring inside `definition` string values** (e.g. `valueexpression` calc-style syntax inside a UIVW column) → `workfront-textmode`. Text Mode is the column-value DSL; this skill calls into it for column composition.
- **Gotchas** (REPORT row's empty `definition`, silent re-resolution, chart/prompts spillover via `preferenceID`, UI-object re-use on modify) → `05-gotchas.md`.
- **Top-level workflow** (which file to consult in which phase) → `00-rubric-and-workflow.md`.

---

## Appendix A — Quick reference: the four POST bodies

The minimal valid payload set for an analytical report grouped by one dimension with N columns:

**UIFT** (`POST $$HOST/attask/api/v17.0/uift`):
```json
{
  "name": "My Report",
  "uiObjCode": "PROJ",
  "filterType": "REPORT",
  "isReport": true,
  "isText": false,
  "isSavedSearch": false,
  "definition": { "status": "CUR", "status_Mod": "in" }
}
```

**UIGB** (`POST $$HOST/attask/api/v17.0/uigb`):
```json
{
  "name": "My Report",
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

**UIVW** (`POST $$HOST/attask/api/v17.0/uivw`):
```json
{
  "name": "My Report",
  "uiObjCode": "PROJ",
  "layoutType": "LIST",
  "uiviewType": "LIST",
  "isReport": true,
  "isText": false,
  "isNewFormat": true,
  "definition": { "column": [ { "...": "..." } ] }
}
```

**REPORT** (`POST $$HOST/attask/api/v17.0/report`):
```json
{
  "name": "My Report",
  "uiObjCode": "PROJ",
  "reportType": "A",
  "isReport": true,
  "description": null,
  "filterID": "<UIFT-ID-from-step-1>",
  "groupByID": "<UIGB-ID-from-step-2>",
  "viewID": "<UIVW-ID-from-step-3>",
  "maxResults": 15,
  "isStandalone": false
}
```

All four POSTs use `--data-urlencode 'updates=<json>'` wire format; raw JSON body is rejected by the v17.0 endpoint. The full procedural walk-through, error handling, smoke-test verify, and the `apply` gate live in `02-create-from-scratch-recipe.md`.
