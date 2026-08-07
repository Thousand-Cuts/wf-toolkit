# 07 — View Patterns

This file documents the JSON-object shape of `UIVW.definition` (the view half of a Workfront report) AND `UIGB.definition.group[]` (the grouping half). The recipe in `02-create-from-scratch-recipe.md` calls into this file for anything beyond the simplest column-and-grouping case. UIVW top-level required fields (`layoutType`, `uiviewType`, `isReport`, etc.) are documented in `01-report-object-shape.md`; this file covers what goes INSIDE `definition`. All examples and the full vocabulary come from an empirical survey of real reports across five client tenants — anonymized throughout as `client-a-sample/…` through `client-e-sample/…` (the raw JSON was removed from the repo for client-data hygiene; the findings below are the distilled, verified result). Every URL in this file uses `v17.0` per `knowledge/api/01-api-fundamentals.md`.

A note on what's in scope here: this file is about the **JSON shape** the API stores and returns. It is NOT about the text-mode authoring surface a consultant pastes into the in-product Text Mode tab (that's `workfront-textmode`). The two are duals — the API JSON shape documented here is what Workfront's UI converts text-mode into on save — but the skill writes the JSON directly and never round-trips through the text-mode parser. When this file refers to a `valueexpression` containing `CONCAT(...)` or `IF(...)`, the calc-language semantics are owned by `workfront-textmode`; this file only documents the JSON column wrapper around it (§ 6).

A second note on the companion file: `06-filter-patterns.md` documents the filter half (`UIFT.definition`) and previews the `DE:` prefix asymmetry between UIFT keys, UIVW column fields, and UIGB group fields. This file documents the full asymmetry (§ 14) with empirical citations across all three locations.

## § 1. UIVW.definition top-level shape

`UIVW.definition` is a small object with up to four keys:

```json
{
  "column": [ /* one or more column objects — REQUIRED */ ],
  "row":    [ /* zero or more row-styling objects — optional */ ],
  "property": { /* tiny UI-hint map — optional */ },
  "textmode": "false"
}
```

- `column` — array of column objects. REQUIRED; one or more. The render order is the array order. Each entry's shape is documented in § 2.
- `row` — array of row-styling objects (optional). Used for whole-row conditional formatting; see § 11. Parallel to `column[]`, not nested.
- `property` — small object of UI hints (optional). The only key seen in the empirical survey is `"anacondaNewFormat": "true"` — set by Workfront's "new layout" rollout on Client A's tenant (`client-a-sample/PROJ-insertion-sched-NOFILTER-uivw.json`, `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json`). Treated as opaque pass-through by the sanitizer.
- `textmode: "false"` — string-typed, NOT a boolean. Indicates whether the consultant opened the in-product Text Mode tab on the view. Seen across most Client B and Client D samples. Sanitizer pass-through.

`row` and `property` are both optional. The minimal legal `UIVW.definition` is `{"column": [{...one column...}]}`. The maximal observed shape has all four top-level keys plus 10-15 columns.

The wrapper around `definition` looks like this on a fresh write or a clone:

```json
{
  "label": "_view",
  "objCode": "UIVW",
  "uiObjCode": "TASK",
  "uiviewType": "REPORT",
  "isReport": "true",
  "layoutType": "list",
  "definition": { /* the object documented in the rest of this file */ }
}
```

See `01-report-object-shape.md` for the wrapper fields — `uiObjCode`, `layoutType`, `uiviewType`, `isReport`. This file scopes to the inside of `definition`.

## § 2. The canonical column shape

Every common column has these fields. Order doesn't matter; all values are strings unless noted (Workfront's JSON shape for columns is uniformly string-typed, same as UIFT — see `06-filter-patterns.md` § 2 wire-encoding note).

- `namekey` — i18n key for the column header (e.g. `"name.abbr"`, `"plannedcompletiondate"`, `"status"`). NOT a free string — Workfront looks up its i18n table for the canonical label. The skill emits known stable keys; for fields with no canonical key, fall back to `displayname` (§ 6).
- `descriptionkey` — i18n key for the column tooltip; sometimes same as `namekey`, sometimes a stem (`client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json` uses `descriptionkey: "name"` paired with `namekey: "name.abbr"` on the project-name column — abbr label, full tooltip).
- `valuefield` — the data field name. KEEPS `:`-separated join paths (e.g. `"owner:name"`, `"project:portfolio:name"`). DROPS the `DE:` prefix in regular columns. See § 14 for the asymmetry and its exceptions.
- `valueformat` — how the value renders. The enumeration is fixed by Workfront; the full table follows below.
- `linkedname` — describes what relation this column is rendering. Values seen: `"direct"` (the row's own record's own field), `"owner"`, `"portfolio"`, `"project"`, `"task"`, `"program"`, `"template"`, `"parent"`, `"milestone"`, `"approver"`, plus custom-field names verbatim for reference-type DE: fields (e.g. `"Project Sponsor"`). For aggregator columns rendering a joined custom field, this also takes the relation alias (`"linkedname": "project"` paired with `valuefield: "project:Approved Hours"` in `client-c-sample/HOUR-support-hours-uivw.json`).
- `listsort` — sort algorithm directive, names the sort routine and the field together (e.g. `"string(name)"`, `"intAsInt(referenceNumber)"`, `"atDateAsAtDate(plannedCompletionDate)"`, `"doubleAsDouble(percentComplete)"`). The function name maps to a Workfront-internal comparator; the inner argument is the field reference.
- `querysort` — DB-side sort field for stable pagination. KEEPS `DE:` prefix even when the column's `valuefield` drops it. Confirmed in `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json`: every DE: column has `valuefield: "Week"` paired with `querysort: "DE:Week"`, `valuefield: "Primary Focus"` paired with `querysort: "DE:Primary Focus"`, etc.
- `section` — UI grouping section, almost always `"0"`. Workfront's older "Group Header" feature carved columns into sections; modern reports use one section.
- `shortview` — `"true"` to include in compact view; `"false"` to show only in expanded view. Default unset = visible.
- `stretch` — column auto-stretch weight (numeric string, e.g. `"0"`, `"30"`, `"100"`). Higher value gets more residual width when the row stretches.
- `width` — explicit pixel width (numeric string, e.g. `"150"`, `"200"`, `"600"`). Coexists with `stretch` — stretch redistributes residual space, width sets the floor.
- `valuedatatype` — Java type hint, optional (e.g. `"class java.lang.String"`, `"int"`). Workfront fills this on round-trip; skill omits on create unless cloning.
- `viewalias` — alternate short ID, optional (e.g. `"assignments"`, `"duration"`, `"project:actualworkrequireddouble"`). Used by Workfront's URL-state encoding for sort/group permalinks.
- `isInlineEditable` — `"true"` / `"false"` string, optional. Controls whether the cell becomes an inline editor on click.
- `sortOrder` — column-scoped sort priority (`"1"`, `"2"`, ...), optional. The first three sort priorities work in the renderer; higher values are accepted but typically inert. Empty string `""` is valid and means "no sort on this column."
- `sortType` — `"asc"` / `"desc"` / `""`. Pairs with `sortOrder`.
- `usewidths` — `"true"` forces fixed widths even when `sharecol`-merged. Seen on Client A (`PROJ-planning-grid-NOFILTER-uivw.json`).
- `delimiter` — string used in iterate columns; e.g. `"&nbsp"`, `"<br>"`, `"<div style=margin-bottom:6px>"`.

**`valueformat` enumeration.** Every empirical value seen in the survey, mapped to its renderer:

| Value | Renders as | Example field/citation |
|---|---|---|
| `"HTML"` | unsanitized HTML (`<a>`/`<strong>`/etc. allowed) | name with click-link; valueexpression with HTML output |
| `"string"` | plain text | `owner:name`, `portfolio:name` |
| `"int"` | integer | `referenceNumber`, `sortOrder` |
| `"val"` | enum value (rendered via `enumclass` lookup) | `status`, `priority` |
| `"enumIcon"` | enum icon (status icon, etc.) | `status` (icon variant) |
| `"atDate"` | compact date | `plannedCompletionDate`, `entryDate` |
| `"shortDate"` | short date | `plannedCompletionDate` compact form |
| `"atDateAsAtDate"` | full date+time | `actualCompletionDate` |
| `"atDateAsMonthOfYearString"` | "Apr 2026" style | UIGB date-bucket grouping (`client-b-sample/PROJ-exec-report-uigb.json`) |
| `"atDateAsQuarterOfYearString"` | "Q2 2026" style | matrix UIGB quarter-bucket (`client-b-sample/proj-labor-by-month-uigb.json`) |
| `"asPercent"` | "75%" | `percentComplete` |
| `"booleanMessage"` | "Yes"/"No" rendered from boolean | `isAwaitingDecision` |
| `"customDataLabelsAsString"` | DE: lookup-list value | DE: External-Lookup or single-select fields; UIGB DE: custom-field group |
| `"customReferenceObjectAsString"` | DE: reference-object value | DE: object-reference fields |
| `"customDateAsString"` | DE: date custom field | DE: date fields |
| `"customNumberAsString"` | DE: numeric custom field (display string) | aggregator `displayformat` for DE: numbers |
| `"customNumberAsDouble"` | DE: numeric custom field (typed double) | aggregator `valueformat` for DE: numbers (`client-b-sample/PROJ-asset-pva-duration-uivw.json`) |
| `"customNumberAsCurrencyStringRounded"` | DE: number as currency, rounded | aggregator (Client C variants) |
| `"compound"` | duration + unit suffix | `durationMinutes + durationUnit`; aggregator `displayformat` for hours |
| `"doubleAsRounded"` | rounded float | aggregator |
| `"doubleAsString"` | unrounded float | aggregator (Client C `HOUR-support-hours-uivw.json` valueexpression aggregator) |
| `"doubleAsDouble"` | typed double | aggregator `valueformat` with valueexpression |
| `"currencyStringCurrencyRounded"` | currency string, rounded | aggregator `displayformat` (Client C) |
| `""` (empty string) | renderer's default | last column in `client-b-sample/PROJ-exec-report-uivw.json` |

Other formats exist in Workfront's renderer (`time`, `date`, etc.) but did not appear in the 40-sample survey. The pre-flight validator (`08-pre-flight-validation.md`) treats unknown `valueformat` values as warnings, not errors — Workfront ignores any value it doesn't recognise and falls back to string rendering.

**Minimal column example.** A status column on TASK:

```json
{
  "linkedname": "direct",
  "namekey": "status",
  "valuefield": "status",
  "valueformat": "val",
  "type": "enum",
  "enumclass": "com.attask.common.constants.TaskStatusEnum",
  "enumtype": "TASK"
}
```

That's seven fields. The skill emits no more than necessary on create; cloning preserves whatever the source had.

## § 3. The `link` block — column click-through

Optional nested object on a column. Controls what clicking the cell opens. Empty `link` is also legal (some round-tripped views carry `"link": {}` and the renderer treats it as "no click target").

```json
"link": {
  "lookup": "link.view",
  "valuefield": "objCode",
  "valueformat": "val",
  "linkproperty": [
    {"name": "ID", "valuefield": "ID", "valueformat": "int"}
  ],
  "value": "val(objCode)"
}
```

- `lookup` — one of:
  - `"link.view"` — standard "open the record's detail page." Most common.
  - `"document.directory"` — open the document directory (folder browse). Seen in `client-d-sample/DOCU-proofs-retail-uivw.json` paired with `value: "val(isDir)"` so it adapts to row-by-row whether to open a folder or a doc.
  - `nested(<rel>).val(objCode)` shape — see below.
- `linkproperty` — array of {name, valuefield, valueformat} triples mapping URL parameters. The standard is one entry mapping `ID` to the outer row's `ID`. The renderer uses `linkproperty` to build the destination URL.
- `value` — optional dispatch expression. Two forms in the wild:
  - `"val(objCode)"` — use the outer row's `objCode` field as the dispatch type (`TASK`, `PROJ`, etc.).
  - `"nested(<rel1>).nested(<rel2>).val(<field>)"` — walk the relation graph and use the resolved field as dispatch. Cited from `client-d-sample/PRFAPL-completed-L-uivw.json`:
    ```json
    "link": {
      "linkproperty": [{"name": "ID", "valuefield": "documentID", "valueformat": "string"}],
      "lookup": "link.view",
      "value": "nested(documentVersion).nested(document).val(objCode)"
    }
    ```
    Reads as: "from this proof-approval row, walk to its `documentVersion`, then to its `document`, then dispatch the click on that document's `objCode` (DOCU). Use the row's own `documentID` as the URL `ID` parameter."

A column without a `link` block is unclickable — the cell renders as static text. A column WITH a `link` block but no `linkproperty` falls back to the row's own `ID`.

## § 4. Enum columns

For columns rendering Workfront enum values (status, priority, condition):

```json
{
  "namekey": "status",
  "valuefield": "status",
  "valueformat": "val",
  "type": "enum",
  "enumclass": "com.attask.common.constants.TaskStatusEnum",
  "enumtype": "TASK"
}
```

- `enumclass` — fully-qualified Java class path. Known classes from the survey:
  - `com.attask.common.constants.TaskStatusEnum` — TASK `status` (`NEW`, `IPR`, `CPL`, ...)
  - `com.attask.common.constants.OpTaskStatusEnum` — OPTASK `status`
  - `com.attask.common.constants.TimelinePriorityEnum` — TASK/PROJ/OPTASK `priority` (1-4)
  - `com.attask.common.constants.ProjectConditionEnum` — PROJ `condition` (`ON`/`AB`/`AT`)
  - `com.attask.common.constants.ProjectStatusEnum` — PROJ `status`
  - `com.attask.common.constants.HourStatusEnum` — HOUR `status`
  - `com.attask.common.constants.ParameterDisplayTypeEnum` — PARAM `displayType` (seen on `client-c-sample/PARAM-calc-only-L-uivw.json`)
  - `com.attask.common.constants.ProgressStatusEnum` — TASK `progressStatus` (`LT`/`BH`/`OT`/`LR`/`RS`)
- `enumtype` — the SHORT objCode (`TASK`, `PROJ`, `OPTASK`, `PARAM`). NOT the long Java class name. NOT redundant with `enumclass` — when the same enum class is reused across multiple uiObjCodes (e.g. `TimelinePriorityEnum` applies to TASK and PROJ), `enumtype` picks the per-object localisation.
- `type: "enum"` is the column-type discriminator; required for enum rendering.
- **`enumclass` and `enumtype` coexist** — both are typically present on enum columns. Citation: `client-c-sample/PARAM-calc-only-L-uivw.json` has `enumclass: "com.attask.common.constants.ParameterDisplayTypeEnum"` and `enumtype: "PARAM"` on the same column. Likewise `client-b-sample/TASK-ready-to-work-uivw.json` Priority column has both (`TimelinePriorityEnum` + `enumtype: "PROJ"` because the column shows the parent project's priority via `linkedname: "project"`). Earlier internal notes treated them as alternatives; that was wrong. Either one alone is also legal, but the canonical shape carries both.

**Cross-object priority.** When an enum column shows a joined record's enum (e.g. TASK report column displaying `project:priority`), the `enumtype` is the JOINED object's objCode, not the report's outer object. Cite `client-b-sample/TASK-ready-to-work-uivw.json`'s Priority column: outer object is TASK, but `enumtype: "PROJ"` because the column shows `project:priority`.

## § 5. Aggregator columns

> **See also:** Full `valueformat` token catalogue (6 date tokens + 10 numeric tokens + enum + aggregator-specific) at `knowledge/textmode/04-views-and-groupings.md` § Full `valueformat` token catalogue.


Embedded INSIDE a column object — group-boundary totals/averages. Renders an extra row at every group break (and at the report total).

```json
{
  "namekey": "duration",
  "valuefield": "Duration Delta 2",
  "valueformat": "customNumberAsString",
  "querysort": "DE:Duration Delta 2",
  "aggregator": {
    "function": "AVG",
    "valuefield": "DE:Duration Delta 2",
    "valueformat": "customNumberAsDouble",
    "displayformat": "customNumberAsString",
    "namekey": "Duration Delta 2"
  }
}
```

Citation: `client-b-sample/PROJ-asset-pva-duration-uivw.json`. Note three different fields all describing the same DE: custom field:

- Column `valuefield`: `"Duration Delta 2"` — DROPS `DE:` (display-side, follows the standard rule from § 14).
- Column `querysort`: `"DE:Duration Delta 2"` — KEEPS `DE:` (DB-side sort).
- Aggregator `valuefield`: `"DE:Duration Delta 2"` — KEEPS `DE:` (the aggregator resolves the custom field by DB column, not by display alias).

This three-way asymmetry on the SAME column is the loudest empirical evidence that DE: handling is location-based, not field-based. The skill applies the rule by location; see § 14.

**Aggregator fields:**

- `function` — `"SUM"`, `"AVG"`, `"MAX"`, `"MIN"`, `"COUNT"`. Confirmed empirically: `SUM`, `AVG`, `MAX`. `MIN` and `COUNT` are documented in Workfront's text-mode reference but not in the 40-sample survey. `MEDIAN` is documented too; treat as untested.
- `valuefield` — the field to aggregate. KEEPS `DE:` prefix when present.
- `valueformat` — typing of the aggregate's typed value (e.g. `customNumberAsDouble` for DE: numbers, `doubleAsDouble` for native doubles, `val` for compound).
- `displayformat` — how the aggregate renders to the user (e.g. `customNumberAsString`, `currencyStringCurrencyRounded`, `doubleAsString`, `compound`). Distinct from `valueformat` — the typed value is internal, the display value is user-facing.
- `namekey` — i18n key for the aggregate row's label.
- `namekeyargkey` — array of i18n template arguments, used when `namekey: "view.relatedcolumn"` and the label is constructed from a relation alias + a field. Cite `client-c-sample/HOUR-support-hours-uivw.json`:
  ```json
  "namekey": "view.relatedcolumn",
  "namekeyargkey": ["project", "Approved Hours"]
  ```
  Workfront expands "view.relatedcolumn" with the two args to produce a label like "Project: Approved Hours."

**Alternative: `valueexpression`-based aggregator.** When the aggregate is a derived expression, not a single field:

```json
"aggregator": {
  "function": "MAX",
  "valueexpression": "ROUND(SUB({project}.{DE:Approved Hours},{project}.{actualWorkRequiredDouble}),1)",
  "valueformat": "doubleAsString",
  "displayformat": "doubleAsString"
}
```

Citation: `client-c-sample/HOUR-support-hours-uivw.json` "What's Left" column — both the column and its aggregator use the same `valueexpression`. The aggregator's `valuefield` is absent when `valueexpression` is present; mutually exclusive. See § 6 for the calc-language wrapper rules; defer the calc syntax itself to `workfront-textmode`.

A second cite from the same file shows a labelled SUM aggregator with both `namekey` and `namekeyargkey`:

```json
"aggregator": {
  "function": "SUM",
  "valueexpression": "IF({owner}.{DE:Dept}=\"100 Operations and Support\",{hours},0)",
  "valueformat": "doubleAsDouble",
  "displayformat": "currencyStringCurrencyRounded",
  "namekey": "view.relatedcolumn",
  "namekeyargkey": ["dept", "100 Ops"]
}
```

The `IF(...)` resolves to either `{hours}` or `0` per row, then `SUM` totals the resolved values across the group. Cross-tab pattern in plain JSON.

**Multi-aggregator on the same group.** Each column carries at most one aggregator, but a view can carry many aggregator columns. `client-b-sample/PROJ-exec-report-uivw.json` has a MAX aggregator and the per-column aggregators stack at every group break.

## § 6. `valueexpression` columns (custom calc)

Column without `valuefield` — value computed by an expression.

```json
{
  "displayname": "Launch Date",
  "textmode": "true",
  "valueexpression": "IF({name}=\"Launch\",{plannedCompletionDate})",
  "valueformat": "shortDate"
}
```

**The four MUST rules for valueexpression columns:**

1. `textmode: "true"` is MANDATORY. Without it, Workfront tries to parse `valueexpression` as a literal field name (and fails silently with an empty column).
2. `displayname` REPLACES `namekey` for the header. The i18n lookup is bypassed; the literal string is shown.
3. `valuefield` is OMITTED entirely. Setting both `valuefield` AND `valueexpression` causes one of them to be silently dropped on round-trip — which one is tenant-dependent. Pick one.
4. The expression itself uses brace-bracketed field references — `{plannedCompletionDate}`, `{project}.{name}`, `{owner}.{DE:Dept}`. Calc-language syntax for CONCAT/IF/CASE/ROUND/SUB/ISBLANK/STRING/etc. is documented by `workfront-textmode`; this file documents only how to WRAP the expression as a column.

**HTML output via `valueformat: "HTML"`:**

```json
{
  "displayname": "Task Link",
  "textmode": "true",
  "valueexpression": "CONCAT(\"<strong>Task Name:</strong> <a href='/task/view?ID=\",{ID},\"'>\",{name},\"</a>\")",
  "valueformat": "HTML",
  "width": "250"
}
```

Citation: `client-b-sample/TASK-ready-to-work-uivw.json` first column. The HTML is rendered raw by Workfront's view — no sanitization. Use carefully on cross-tenant clones because a hard-coded host in an `<a href>` (e.g. `https://client-e.my.workfront.com/...`) leaks the source tenant's name. The `sanitize_clone.py` module's `host_rewrite` bucket detects and prompts on these.

**Iterate columns (one cell, many child rows).** When the column should project one value per matching child record:

```json
{
  "displayname": "Calculated Fields and Formulas",
  "listdelimiter": "<div style=margin-bottom:6px>",
  "listmethod": "nested(categoryParameters).lists",
  "name": "categoryParameters",
  "textmode": "true",
  "type": "iterate",
  "valueexpression": "CONCAT({parameter}.{displayName},\": \",{customExpression})",
  "valueformat": "HTML",
  "width": "600"
}
```

Citation: `client-c-sample/PGRP-paramgroup-L-uivw.json`. Fields:

- `type: "iterate"` — projection mode.
- `listmethod` — relation expression returning a list. Form: `"nested(<rel>).lists"` or `"nested(<rel1>).nested(<rel2>).lists"`.
- `listdelimiter` — separator between rendered children. The empirical samples use `"<br>"`, `"&nbsp"`, and HTML opening tags like `"<div style=margin-bottom:6px>"` (the opening tag becomes the separator; the closing-tag balance is implicit).
- `valueexpression` — evaluated once per child; `{parameter}.{displayName}` resolves relative to the iterating child, not the outer row.
- `name` — used in PARAM/PGRP column variants (§ 13).

This file scopes to the JSON wrapper. The calc-string syntax inside `valueexpression` is owned by `workfront-textmode` — CONCAT, IF, CASE, ROUND, SUB, ISBLANK, STRING, DATE arithmetic, and the brace-bracket field references all live there. The pre-flight validator (`08-pre-flight-validation.md`) checks `textmode: "true"` is set whenever `valueexpression` is present, and that `valuefield` is absent — but does NOT parse the expression body.

**Quote characters: straight ASCII only.** Workfront's text-mode parser recognises ONLY straight ASCII quotes — `"` (U+0022) and `'` (U+0027). Unicode curly / smart quotes — `"` (U+201C), `"` (U+201D), `'` (U+2018), `'` (U+2019) — are NOT recognised. A `valueexpression` like `IF({percentComplete}=0,"0% complete","other")` (curly) silently fails: the parser walks past the opening `"`, treats everything until the closing `"` as one token, and the IF chain breaks. The column renders empty or shows the raw expression. Same rule applies inside `valueexpression` strings in UIGB calculated groupings.

This bites HARDEST when consultants compose long IF chains in Google Docs / Word / Slack DMs (all of which auto-substitute curly quotes) and paste into the in-product Text Mode tab. Standard fix: paste into a plain-text editor (TextEdit on macOS in plain mode, Notepad on Windows, or `pbpaste | sed "s/[“”]/\"/g; s/[‘’]/'/g" | pbcopy`) before pasting into Workfront. Or use the in-product text mode's "find and replace" to swap curly for straight after pasting.

The pre-flight validator does NOT yet detect curly quotes (v0.11.0 candidate). On a clone, the source bundle's `valueexpression` strings are already straight-quoted (they round-tripped through the API once) — so the curly-quote risk is purely an authoring-from-scratch issue, not a clone issue.

**Wrap signed date-diffs in `ABS(...)` for "ahead/behind by N days"-style labels.** A naive expression like `CONCAT("Behind by ", DATEDIFF({plannedCompletionDate},{actualCompletionDate}), " days")` produces awkward renders when the diff is negative (`"Behind by -3 days"` reads worse than `"Ahead by 3 days"`). Resolve the sign explicitly with `IF(DATEDIFF(...)>0, "Behind by ", "Ahead by ")` plus an `ABS(DATEDIFF(...))` for the magnitude:

```
IF({actualCompletionDate}<{plannedCompletionDate},
   CONCAT("Ahead by ", ABS(DATEDIFF({plannedCompletionDate},{actualCompletionDate})), " days"),
   CONCAT("Behind by ", ABS(DATEDIFF({plannedCompletionDate},{actualCompletionDate})), " days"))
```

Cite: Adobe Skill Exchange "Elevate Workfront Reporting with Advanced Text Mode" (Aug 2025) — the trainer demos this exact pattern for a "schedule status" column showing days-ahead / days-behind on completed projects. ABS is supported across all numeric inputs.

## § 7. Conditional formatting via `styledef`

Per-cell or per-row visual rules. Lives INSIDE a column object — sibling to `valuefield`/`valueformat`/etc.

```json
"styledef": {
  "case": [
    {
      "comparison": {
        "icon": "false",
        "isrowcase": "true",
        "leftmethod": "plannedCompletionDate",
        "lefttext": "plannedCompletionDate",
        "operator": "lt",
        "operatortype": "date",
        "righttext": "$$TODAY",
        "trueproperty": [
          {"name": "bgcolor", "value": "FFE0E0"}
        ]
      }
    },
    {
      "comparison": {
        "icon": "false",
        "isrowcase": "true",
        "leftmethod": "plannedCompletionDate",
        "lefttext": "plannedCompletionDate",
        "operator": "between",
        "operatortype": "date",
        "righttext": "$$TODAY",
        "righttextrange": "$$TODAY+2d",
        "trueproperty": [{"name": "bgcolor", "value": "FEECC8"}]
      }
    }
  ]
}
```

Citation: `client-b-sample/TASK-ready-to-work-uivw.json` Planned Dates column. Two cases: overdue (red) and due-within-2-days (amber).

**Anatomy:**

- `case[]` — array of conditional rules. Evaluates in order; first match wins by default. Add `applyallcases: "true"` at the `styledef` level to stack all matching cases (see § 11 for row-level use).
- `case[].comparison` — the single rule. Every comparison has:
  - `leftmethod` — the field to test (Workfront's internal method-name format; usually identical to the field path).
  - `lefttext` — duplicate of `leftmethod` for the in-product builder's display layer. Skill emits both as the same string.
  - `operator` — see table below.
  - `operatortype` — `date`, `string`, `int`, `boolean`.
  - `righttext` — the comparison value, or the empty string for null-checks.
  - `righttextrange` — REQUIRED when `operator` is `between`. Both bounds support `$$TODAY±Nd` arithmetic (cite same file: `righttext: "$$TODAY"`, `righttextrange: "$$TODAY+2d"`).
  - `trueproperty[]` — array of style property triples that apply when the comparison is true.
  - `icon` — `"false"` for color rules, `"true"` for icon rules (see § 8).
  - `isrowcase` — `"true"` to paint the whole row when the rule fires; `"false"` to paint only the cell.

**`operator` values (empirical):**

| Operator | Meaning | Sample citation |
|---|---|---|
| `lt` | less than | `client-b-sample/TASK-ready-to-work-uivw.json` (date overdue check) |
| `gt` | greater than | `client-b-sample/PROJ-exec-report-uivw.json` |
| `lte` | less or equal | view styledef common |
| `gte` | greater or equal | view styledef common |
| `eq` | equals | view styledef common |
| `ne` | not equals | view styledef common |
| `in` | value-in-set; pair with TAB-separated `righttext` | `client-b-sample/TASK-ready-to-work-uivw.json` Priority column (`righttext: "3\t4"`) |
| `notin` | value-not-in-set; TAB-separated | view styledef variant |
| `isblank` | left is empty/null | view styledef common |
| `notblank` | left is non-empty | `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json` image cases |
| `between` | inclusive range; requires `righttextrange` | `client-b-sample/TASK-ready-to-work-uivw.json` (due-in-2-days amber) |
| `cicontains` | case-insensitive substring | view styledef variant |

**`operatortype` values:** `"date"`, `"string"`, `"int"`, `"boolean"`. Pick whichever matches the field's metadata type — see `08-pre-flight-validation.md` for the resolution rule.

**`trueproperty` names (empirical):**

- `bgcolor` — 6-char hex no `#` (e.g. `"FFE0E0"`, `"FEECC8"`, `"81CCF7"`, `"E8E8E8"`, `"FFC2C2"`).
- `fontstyle` — `bold`, `italic`, `underline`. Stackable via separate triples.
- `textcolor` — 6-char hex no `#`.
- `fontcolor` — synonym for `textcolor` on some round-tripped rows; the renderer accepts both. Skill emits `textcolor` on create.

**`DE:` prefix in styledef.** Both `leftmethod` and `lefttext` KEEP the `DE:` prefix when the column tests a custom field. Citations:

- `client-d-sample/OPTASK-rush-L-uivw.json` Rush column:
  ```json
  "leftmethod": "DE:Is this a rush request?",
  "lefttext": "DE:Is this a rush request?",
  "operator": "in",
  "righttext": "Yes"
  ```
- `client-a-sample/PROJ-insertion-sched-NOFILTER-uivw.json`: every styledef on a DE: column uses `DE:Weekly Promotion Type` in both `leftmethod` and `lefttext`.

This is one of the locations where the `DE:` prefix is KEPT (see § 14). It contrasts with the column's outer `valuefield` on the same column, which drops the prefix.

**On joined fields.** `leftmethod` keeps join-path colons too: `"leftmethod": "project:priority"`, `"lefttext": "project:priority"` from `client-b-sample/TASK-ready-to-work-uivw.json` Priority column.

## § 8. Column-level `image` block (conditional icon)

Renders an icon based on a comparison. Same `case[]` shape as `styledef` but `truetext` is an icon URL.

```json
"image": {
  "namevalue": "DE:Additional Print Detail",
  "case": [
    {
      "comparison": {
        "icon": "true",
        "leftmethod": "DE:Additional Print Detail",
        "lefttext": "DE:Additional Print Detail",
        "operator": "notblank",
        "operatortype": "string",
        "righttext": "",
        "truetext": "/static/img/r15/icons/casebuilder/light_purple.gif"
      }
    }
  ]
}
```

Citation: `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json` Additional Print Detail column.

**Anatomy:**

- `namevalue` — top-level pointer to the field this icon is annotating. Usually matches the comparison's `leftmethod`.
- `case[]` — same array-of-comparisons shape as `styledef`. First match wins.
- `case[].comparison.icon` — set to `"true"` (vs `"false"` for color rules in `styledef`).
- `case[].comparison.truetext` — icon URL, not a hex color. Two forms seen:
  - Workfront-internal path: `"/static/img/r15/icons/casebuilder/light_purple.gif"` (Client A). Resolves against the tenant's host; portable across tenants (every WF tenant serves the same `/static/...` tree).
  - Fully-qualified URL: `"https://<tenant-host>/...icon.png"`. NOT portable; the source tenant's host leaks.
- All other fields (`leftmethod`/`lefttext`/`operator`/`operatortype`/`righttext`) work identically to § 7.

**Sanitizer note.** Fully-qualified icon URLs starting with `https://<host>/...` are tenant-specific and flagged by `sanitize_clone.py`'s `host_rewrite` bucket. The `/static/...` form is safe and passes through unchanged.

**Coexistence with valuefield.** A column with `image` typically ALSO renders the field value beside the icon. Client A's Additional Print Detail column has `valuefield: "DE:Additional Print Detail"`, `valueformat: "HTML"`, AND the `image` block — the icon precedes the text in the rendered cell. Note this column keeps `DE:` in its `valuefield` (a § 14 exception: columns with `textmode: "true"` and HTML format on a DE: field sometimes keep the prefix because the renderer dereferences the value through the calc evaluator rather than the display alias).

## § 9. `tile` columns (rendered components)

Workfront provides built-in renderable components. Render via:

```json
{
  "descriptionkey": "assignments",
  "linkedname": "direct",
  "namekey": "assignments",
  "tile": {"name": "component.assignmentslist"},
  "type": "tile",
  "valuefield": "assignmentsListString",
  "valueformat": "HTML",
  "viewalias": "assignments",
  "width": "140"
}
```

Citation: `client-a-sample/TASK-late-by-individual-uivw.json` Assignments column.

**Known tile names** (every empirical occurrence):

- `component.assignmentslist` — chip-list of assignees with role icons.
- `component.assignmentsliststatuses` — variant that also shows each assignee's task status.
- `component.documentviewicons` — file-type icons for the document list.
- `component.predecessorslist` — predecessor task chips.
- `component.percentcompletelistview` — progress bar; takes `tile.attribute.height` to set bar thickness:
  ```json
  "tile": {"name": "component.percentcompletelistview", "attribute": {"height": "12"}}
  ```
- `component.referenceobject` — used on polymorphic parent references (HOUR's parent object, which can be PROJ, TASK, OPTASK).

**Anatomy:**

- `tile.name` — REQUIRED. Identifies the component.
- `tile.attribute` — optional small object of component-specific knobs. Only `height` seen in the survey.
- `type: "tile"` — column-type discriminator. Optional in practice (the presence of `tile.name` is sufficient), but emitted by Workfront's in-product builder for clarity.
- `valuefield` — the data feeding the component. For `component.assignmentslist` it's `assignmentsListString` (a Workfront-rendered string); for `component.percentcompletelistview` it's `percentComplete`. Each tile expects a specific data shape.

**Authoring rule.** The skill emits tile columns only when the consultant explicitly asks for "the assignments chip-list" or "the progress bar" etc. — there's no automatic mapping from "assignments" in NL to the tile. A bare `valuefield: "assignmentsList"` is a different (less polished) rendering.

## § 10. `sharecol` — merge adjacent columns

Two or more adjacent columns rendered into one cell. The first column is the visual host; subsequent columns join it.

```json
"column": [
  {
    "displayname": "Asset and Task",
    "sharecol": "true",
    "textmode": "true",
    "valueexpression": "CONCAT(\"<strong>Asset Name:</strong> <a href='/project/view?ID=\", {project}.{ID}, \"'>\", {project}.{name}, \"</a>\")",
    "valueformat": "HTML",
    "width": "250"
  },
  {
    "sharecol": "true",
    "textmode": "true",
    "value": "<hr>",
    "valueformat": "HTML"
  },
  {
    "textmode": "true",
    "valueexpression": "CONCAT(\"<strong>Task Name:</strong> <a href='/task/view?ID=\", {ID}, \"'>\", {name}, \"</a>\")",
    "valueformat": "HTML"
  }
]
```

Citation: `client-b-sample/TASK-ready-to-work-uivw.json` first three columns. Renders as one cell with the asset name, a divider, and the task name.

**Anatomy:**

- `sharecol: "true"` is a **group marker, not a join indicator.** Every column in the merged-cell run carries `sharecol: "true"` — INCLUDING the first one. A contiguous run of columns with `sharecol: "true"` forms one shared cell; the first non-sharecol column (or the end of the array) closes the run.
- **The first column in a sharecol group establishes the cell's header, width, and click-through link.** Its `displayname` becomes the column header for the whole merged cell. Its `width` controls the cell width.
- **A column WITHOUT `sharecol: "true"` cannot be merged into a sharecol cell** — it stands alone. The most common v0.9.x pitfall (live-tested 2026-05-14 on a live tenant): omitting `sharecol: "true"` from the primary name column. Result: the name renders as a standalone column with header "Request"/"Task"/etc., AND the breadcrumb columns 1+ render as a SECOND, header-less column to the right. Fix: add `sharecol: "true"` to column 0.
- Each sharecol participant carries its own `valueexpression` / `valuefield` and renders independently within the shared cell.

**Static separator columns.** A sharecol entry with `value` instead of `valuefield`:

```json
{
  "sharecol": "true",
  "textmode": "true",
  "value": "<hr>",
  "valueformat": "HTML"
}
```

- `value` (not `valuefield`) — a literal string emitted into the rendered HTML.
- Common content: `"<hr>"` (horizontal rule), `"<br>"` (line break), small style fragments.

**Where sharecol shines.** Client D's marketing queue reports (`client-d-sample/OPTASK-rush-L-uivw.json`, `client-d-sample/PROJ-my-teams-active-uivw.json`) use it heavily for compact "details" cells that stack 4-6 attributes into one visual column. Client A's planning-grid uses it for icon-plus-text cells.

**Authoring rule.** Sharecol with three or more participants is robust. Five-plus participants tend to wrap awkwardly on narrow viewports; the skill warns when an NL request implies a sharecol group with more than four entries. **Hard limit: 20 columns** can be combined into one sharecol group — beyond that the renderer truncates silently (Adobe advanced-reporting training, day 2 transcript). The skill caps interview-composed sharecol groups at 8 participants.

**Case-sensitivity.** Both the attribute name AND the value are case-sensitive: `sharecol: "true"` works; `Sharecol: "true"`, `sharecol: "True"`, `sharecol: "TRUE"` all silently no-op. Same rule for `textmode: "true"` and `valueformat: "HTML"` (the format name is conventionally uppercase; lowercase `"html"` is rejected by the renderer). When pasting text-mode strings from a doc that auto-capitalises sentence-initial words, double-check column-0 attribute casing.

**Static separator: `value="<br>"` vs `value="break"`.** Two equivalent forms for "this column emits a line break inside the shared cell":

```json
{"sharecol": "true", "textmode": "true", "value": "<br>", "valueformat": "HTML"}
{"sharecol": "true", "textmode": "true", "value": "break", "valueformat": "HTML"}
```

The literal `"break"` is a Workfront-recognised shorthand that the renderer translates to `<br>` at display time (Adobe training day 2). It exists for in-product builder ergonomics — the builder's separator-column quick-add emits `value: "break"`, not the HTML literal. Both forms round-trip identically through GET / POST. The skill emits `"<br>"` for new authoring (more self-documenting) but recognises `"break"` on clone and does NOT rewrite it.

**Formatting rule — labeled stacked rows (preferred for breadcrumb-style metadata cells).** When a sharecol group's purpose is to show multiple labeled attributes (`Priority: Normal`, `Entered: 1/5/26`, `#: 41100`), the empirically-best layout is **labeled-value-per-line** rather than separator-delimited inline. The bad form runs values together; the good form bolds the label and `<br>`s between rows.

**Bad (inline `·` separators AND missing `sharecol` on column 0 — breadcrumb orphans into a header-less second column):**
```json
[
  {"valuefield": "name", "valueformat": "HTML", "width": "300", "displayname": "Request"},
  {"sharecol": "true", "textmode": "true", "value": " · Priority: ", "valueformat": "HTML"},
  {"sharecol": "true", "valuefield": "priority", "valueformat": "val", "type": "enum", ...},
  {"sharecol": "true", "textmode": "true", "value": " · Entered ", "valueformat": "HTML"},
  {"sharecol": "true", "valuefield": "entryDate", "valueformat": "atDate"}
]
```
Two problems: (a) adjacent whitespace inside `value` strings is collapsed by the HTML renderer, so values run together; (b) column 0 has no `sharecol: "true"`, so the breadcrumb columns 1-4 render as a SEPARATE column to the right of the "Request" column, with no header. Caught on live test 2026-05-14.

**Good (bold labels + `<br>` rows + `sharecol:"true"` on column 0):**
```json
[
  {
    "sharecol": "true",
    "displayname": "Request",
    "namekey": "name.abbr",
    "valuefield": "name",
    "valueformat": "HTML",
    "width": "320",
    "link": { ... standard click-through ... }
  },
  {"sharecol": "true", "textmode": "true",
   "value": "<hr style='margin:4px 0;border:0;border-top:1px solid #ddd'>",
   "valueformat": "HTML"},
  {"sharecol": "true", "textmode": "true", "value": "<b>#: </b>", "valueformat": "HTML"},
  {"sharecol": "true", "valuefield": "referenceNumber", "valueformat": "int"},
  {"sharecol": "true", "textmode": "true", "value": "<br><b>Priority: </b>", "valueformat": "HTML"},
  {"sharecol": "true", "valuefield": "priority", "valueformat": "val", "type": "enum", ...},
  {"sharecol": "true", "textmode": "true", "value": "<br><b>Entered: </b>", "valueformat": "HTML"},
  {"sharecol": "true", "valuefield": "entryDate", "valueformat": "atDate"}
]
```

Renders as:
```
Task Name
─────────────
#: 41100
Priority: Normal
Entered: 1/5/26
```

**Rules of thumb for labeled sharecol metadata:**

1. **Use `<b>Label: </b>` (NOT `<bold>` — that's not a real HTML tag; the in-product renderer ignores it).** Put the colon AND the trailing space INSIDE the `<b>` tag — `<b>Label: </b>`, not `<b>Label:</b> `. The trailing space after `</b>` is collapsed by HTML whitespace rules, producing `Label:value` with no gap. Inside the bold scope, the space is preserved (and bold styling on whitespace is invisible anyway). Live-test confirmed 2026-05-14: `<b>Reference #:</b> 10755` rendered as `Reference #:10755`; switching to `<b>Reference #: </b>` produced `Reference #: 10755`.
2. **Use `<br>` between each labeled row, NOT `·` or `|` inline separators.** Adjacent-whitespace collapse will mash everything together; `<br>` produces real line breaks.
3. **Optional `<hr>` between the primary name column and the metadata rows.** Inline-style the `<hr>` to be subtle: `style='margin:4px 0;border:0;border-top:1px solid #ddd'`. Plain `<hr>` is also fine but renders heavier.
4. **Use `<strong>` instead of `<b>` if the file already uses `<strong>` elsewhere** (e.g., `client-b-sample/TASK-ready-to-work-uivw.json` uses `<strong>`). Both render bold; pick one and stay consistent within a single file.
5. **Don't pad with `&nbsp;`.** The renderer respects single `&nbsp;` but multiple won't add expected width — use proper CSS spacing inside an inline `<span style='...'>` if a wider gap is needed.

**Column header rule — `displayname` is mandatory on the first sharecol column.** When the first column in a sharecol group is named after a single field (e.g., `valuefield: "name"`), its column header defaults to that field's i18n label — usually "Name". That's misleading once you stack 3-4 metadata rows underneath: the header says "Name" but the cell contains name + reference + priority + entered-date. Set an explicit `displayname` on column 0 that describes the cell's content type as a whole:

```json
{
  "sharecol": "true",                  // ← REQUIRED: marks col 0 as part of the merged group
  "descriptionkey": "name",
  "displayname": "Request",            // ← REQUIRED: becomes the header for the whole merged cell
  "namekey": "name.abbr",              // kept for the in-product builder's field-picker
  "valuefield": "name",
  "valueformat": "HTML",
  "querysort": "name",
  "width": "320",
  "link": { ... }
},
{"sharecol": "true", "textmode": "true", "value": "<hr ...>", "valueformat": "HTML"},
{"sharecol": "true", "textmode": "true", "value": "<b>Reference #: </b>", "valueformat": "HTML"},
{"sharecol": "true", "valuefield": "referenceNumber", "valueformat": "int"},
...
```

- **`displayname` replaces the `namekey` i18n lookup at render time.** The header shows the literal `displayname` string, not the i18n key's value.
- **Keep `namekey` set** alongside `displayname` — it's still used by the in-product builder's field-picker UI and by some sort/group dropdowns.
- **Pick a single noun that names the cell's content type**: "Project", "Task", "Request", "Document", "Hour Entry". Avoid composite headers like "Project / Owner / Due" — they wrap awkwardly in narrow viewports and consultants will edit them anyway.
- **The interview MUST also set `sharecol: "true"` on column 0** when composing a merged-cell group. Without it, the breadcrumb columns orphan into a header-less second column (live-test failure mode, 2026-05-14).

The skill's interview MUST auto-set BOTH `sharecol: "true"` AND `displayname` on column 0 whenever it composes a sharecol group with 2+ metadata pairs in the cell.

**Detail view vs Tabular view — non-sharecol columns squish in Detail.** Workfront's report viewer offers two render modes:

- **Tabular view** (`$$HOST/report/<id>/view` or `/view`) — every column gets its own visual cell with its own column header. `sharecol` columns merge into one cell; non-sharecol columns stand alone with their `namekey`/`displayname` rendered as the header.
- **Detail view** (`$$HOST/report/<id>/detail` or default in some entry points) — each row renders as a stacked block. Every column's value renders inline within the block, but **non-sharecol columns do NOT render their header labels**. Only sharecol columns with explicit `<b>Label:</b>` separators (per the labeled-row rule above) keep their labels visible. Standalone columns produce header-less values that flow immediately after the previous column.

Symptoms (live-test 2026-05-14):

- **Round 1:** Report 3 had `lastUpdateDate` as a standalone column with `namekey:"lastupdatedate.abbr"`. In Tabular view it rendered as its own "Last Update" column; in Detail view it rendered as a bare date appended directly after `entryDate`, producing `Entered:11/19/242/27/25` — two dates concatenated with no separator and no second label.
- **Round 2:** After rolling `lastUpdateDate` into the sharecol, the next standalone column (`status` with `valueformat:"val"` + `type:"enum"`) exhibited the same symptom: bare `New` appended directly after the date, producing `Last Update:2/27/25New`. **Enum status columns do NOT get any visual whitespace, chip, or separator from Workfront's renderer in Detail view.** My earlier guess otherwise was wrong; corrected here.

**Authoring rule for Detail-mode-target reports.** Every column must be `sharecol:"true"` and every data column must be preceded by a `<br><b>Label:</b>`-bearing static `value` separator. There are NO standalone-column escape hatches in Detail view — enum, date, percent, int, string all render identically (bare value, no header, no whitespace). When in doubt, the skill's interview should default to "everything in the sharecol" — there's no trade-off worth taking in Detail mode.

**Tabular-mode-target reports** can still mix sharecol + standalone columns freely, because Tabular view DOES render the standalone columns with their own headers in their own cells. The skill's interview should ask the consultant up front which view mode the report targets, and compose accordingly. When unspecified, default to "all-sharecol" — it's correct in BOTH modes (the Tabular rendering just becomes a single wide cell instead of multiple cells, which is acceptable).

## § 10c. HTML output inside `valueexpression` — sanitizer rules

Workfront's report renderer runs every `valueformat:"HTML"` output through a sanitizer + auto-linkifier pipeline. Two empirically-verified rules from live tests on 2026-05-14:

**Rule 1 — `<img>` tags survive, but absolute `https://` URLs in `src` attributes are auto-linkified and break.** The sanitizer scans every emitted string for `https://` substrings and wraps them in `<a href="..." rel="noopener noreferrer" target="_blank">...</a>`. This happens even INSIDE attribute values — so `<img src="https://...">` becomes `<img src="<a href='https://...'>https://...</a>">` and the browser tries to load the literal `<a>` HTML as the image source, producing a broken-image icon.

**Workaround that does NOT work:** HTML-entity-encoding the colon (`https&#58;//...`) — Workfront's sanitizer encodes the `&` to `&amp;` BEFORE the browser can decode it, so the browser sees the literal string `https&#58;//...` (not a valid URL) and the image fails to load.

**Workaround that DOES work:** **use a relative URL** (path-only, no scheme + host). The auto-linkifier doesn't recognize path-only strings as URLs, so it passes through cleanly. The browser resolves the path against the report's own origin (the Workfront tenant host) — which is what you want anyway. Example:

```javascript
CONCAT("<img src='/internal/user/avatar?ID=", {ownerID}, "' alt='' style='width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:6px;object-fit:cover'>", {owner}.{name})
```

This pattern was confirmed working in a sandbox "Active Projects At-A-Glance" report (created via API, viewed in Detail mode, owner photo rendered correctly for users with uploaded avatars; Workfront's silhouette default rendered for users without).

**Rule 2 — `<span>` and inline styles survive intact.** The sanitizer doesn't strip `<span>`, `<b>`, `<strong>`, `<i>`, `<em>`, or `<br>` tags. Inline `style="..."` attributes pass through with `display`, `width`, `height`, `border-radius`, `background`, `color`, `text-align`, `line-height`, `font-size`, `font-weight`, `vertical-align`, `margin-right`, `object-fit` properties confirmed (live-tested). Single-quotes around attribute values are preferred (avoids JSON escaping inside the calc expression).

### Rule 3 — Not every USER field surfaces through `{<relation>}.{...}` in calc

A field that exists on USER's `/user/metadata` (and that you can GET via `/user/<id>?fields=...`) may NOT be accessible through a join from a parent object's calc context. Tested 2026-05-14:

```
{owner}.{avatarDownloadURL} → ""     (always empty, even for users WITH avatars)
{owner}.{avatarDate}        → date   (populated only when avatar uploaded)
{owner}.{avatarSize}        → int    (0 when no avatar; positive when one exists)
```

`avatarDownloadURL` exists on USER's metadata and returns a value when read via `/user/<id>?fields=avatarDownloadURL` — but in the report calc engine, `{owner}.{avatarDownloadURL}` returns blank for everyone. Workfront's calc engine appears to gate which fields cross relation boundaries; the rule for which fields make it through isn't documented.

**Workaround for the avatar use case:** use `{owner}.{avatarDate}` (or `{owner}.{avatarSize}`) for the existence check instead of `{owner}.{avatarDownloadURL}`. The user's ID is still accessible as `{ownerID}` and remains valid for constructing the avatar URL.

**General rule:** when an `ISBLANK({owner}.{field})` test returns true unexpectedly (the field is populated on direct GET but blank in calc), assume the relation gate; try a sibling field on the same object.

### Rule 4 — `/internal/user/avatar` `<img>` renders as block by default

Workfront's renderer recognizes `/internal/user/avatar?ID=...` paths in `<img src>` and inlines the avatar correctly — but it ALSO appears to wrap the result in a block-level container (likely a user-mini-card component). That causes a line break before AND after the avatar even though the surrounding text expects inline flow:

```
Owner:
[avatar]
Jane Admin
```

**Fix:** explicitly set `display:inline-block` on the `<img>` style. Workfront passes the style through and the rendered avatar stays inline:

```
Owner: [avatar] Jane Admin
```

The `<span>` initials chip already has `display:inline-block` for the same reason (its background+border-radius+text-align combination requires explicit block-context). Apply the same to the `<img>` for consistent inline rendering across both branches.

### Canonical "user avatar with initials fallback" pattern (empirically verified)

Tested 2026-05-14 against a live production tenant. Renders an actual round photo for users with an uploaded avatar; a 24×24 grey circle with their first+last initials for users without. Both stay inline with the surrounding text.

```json
{
  "sharecol": "true",
  "textmode": "true",
  "linkedname": "owner",
  "valueexpression": "IF(ISBLANK({owner}.{avatarDate}),CONCAT(\"<span style='display:inline-block;width:24px;height:24px;border-radius:50%;background:#6b7280;color:#fff;text-align:center;line-height:24px;font-size:11px;font-weight:600;vertical-align:middle;margin-right:6px'>\",SUBSTR({owner}.{firstName},0,1),SUBSTR({owner}.{lastName},0,1),\"</span>\",{owner}.{name}),CONCAT(\"<img src='/internal/user/avatar?ID=\",{ownerID},\"' alt='' style='display:inline-block;width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:6px;object-fit:cover'>\",{owner}.{name}))",
  "valueformat": "HTML"
}
```

What this does:
- Tests `{owner}.{avatarDate}` for blank (note: NOT `avatarDownloadURL` — that doesn't surface through the relation; see Rule 3 above).
- **Avatar branch:** emits a 24×24 round `<img>` with `src='/internal/user/avatar?ID=<ownerID>'` (relative URL, dodges the auto-linkifier per Rule 1) AND `display:inline-block` (forces inline rendering per Rule 4), followed by the owner's name.
- **Initials branch:** emits a 24×24 round grey `<span style='display:inline-block;...'>` containing `firstName[0] + lastName[0]` followed by the owner's name. Used when no avatar is uploaded.

For OTHER object joins (a column showing a TASK's `assignedTo` user, a Document's `creator`, etc.), substitute the relation name: replace `{owner}.{avatarDate}` → `{<relation>}.{avatarDate}`, `{ownerID}` → `{<relation>ID}`, `{owner}.{firstName/lastName/name}` → `{<relation>}.{firstName/lastName/name}`. The `/internal/user/avatar?ID=<userID>` path is the same regardless of which relation surfaced the user.

## § 11. View-level `definition.row[]` — row-styling

Parallel to `column[]`; row-level conditional formatting. Lives at the same level as `column` inside `definition`, not nested.

```json
"row": [
  {
    "styledef": {
      "applyallcases": "true",
      "case": [
        {
          "comparison": {
            "icon": "false",
            "isrowcase": "true",
            "leftmethod": "DE:Weekly Promotion Type",
            "lefttext": "DE:Weekly Promotion Type",
            "operator": "in",
            "operatortype": "string",
            "righttext": "Digital",
            "trueproperty": [{"name": "bgcolor", "value": "E8E8E8"}]
          }
        },
        {
          "comparison": {
            "icon": "false",
            "isrowcase": "true",
            "leftmethod": "DE:Weekly Promotion Type",
            "lefttext": "DE:Weekly Promotion Type",
            "operator": "in",
            "operatortype": "string",
            "righttext": "Ag Insert",
            "trueproperty": [{"name": "bgcolor", "value": "81CCF7"}]
          }
        }
      ]
    }
  }
]
```

Citation: `client-a-sample/PROJ-insertion-sched-NOFILTER-uivw.json`. Reads as: "rows whose `DE:Weekly Promotion Type` is `Digital` get a light-grey background; rows whose value is `Ag Insert` get light-blue."

**Anatomy:**

- Each entry in `row[]` has a single `styledef` with the same shape as the column-level styledef (§ 7).
- `isrowcase: "true"` is REQUIRED in every row-level case (vs optional at column level). Without it the case is ignored.
- `applyallcases: "true"` stacks all matching cases (vs first-wins at the column level). When two row-styles match — e.g. an overdue rule AND a high-priority rule — both `bgcolor`/`fontstyle` properties apply. The two `trueproperty` arrays are merged at render time.
- The row's `styledef` evaluates against the row's outer record. Joined-record references (`project:status`) work; nested grandchild references do not (Workfront resolves one hop).

**Multiple row-styling rules.** The `row[]` array can carry multiple entries, each with its own `styledef`. Each entry's cases evaluate against the row independently; `applyallcases` applies within a single entry's cases. Cross-entry semantics is also "all matching apply" — the renderer composes the property bag from every matching case in every entry.

## § 12. UIGB.definition.group[] — group entry shape

The grouping half of the report. Each entry in `group[]` describes one grouping level.

```json
{
  "linkedname": "direct",
  "namekey": "status",
  "valuefield": "status",
  "valueformat": "val",
  "type": "enum",
  "enumclass": "com.attask.common.constants.TaskStatusEnum",
  "enumtype": "TASK"
}
```

Citation: `client-b-sample/TASK-ready-to-work-uigb.json`. Group on TASK status.

**Common fields:**

- `linkedname` — relation alias or `"direct"` for the row's own object. Same semantics as in `column[]`.
- `namekey` — i18n key for the group header.
- `valuefield` — the field to group by. DROPS the `DE:` prefix on custom fields (see § 14).
- `valueformat` — how the group label renders. Same enumeration as column `valueformat`.
- `type: "enum"` — optional discriminator for enum groups; `enumclass` + `enumtype` work the same as in § 4.
- `iscollapsed` — `"true"` for default-collapsed in render; `"false"` or absent for default-expanded.

**Multi-group: array order is outermost-first.** Three-level grouping example:

```json
"group": [
  {
    "groupdatesby": "M",
    "linkedname": "direct",
    "namekey": "plannedCompletionDate",
    "notime": "false",
    "valuefield": "plannedCompletionDate",
    "valueformat": "atDateAsMonthOfYearString"
  },
  {
    "linkedname": "program",
    "namekey": "view.relatedcolumn",
    "namekeyargkey": ["program", "name"],
    "valuefield": "program:name",
    "valueformat": "string"
  },
  {
    "linkedname": "direct",
    "namekey": "Asset Tag",
    "valuefield": "Asset Tag",
    "valueformat": "customDataLabelsAsString"
  }
]
```

Citation: `client-b-sample/PROJ-exec-report-uigb.json`. Reads as: first group by completion-month, then by program name, then by `DE:Asset Tag` (DE: dropped in `valuefield`).

**Date-bucket grouping.** Use `groupdatesby` to bucket dates by month/quarter/year:

| `groupdatesby` | Paired `valueformat` | Renders as |
|---|---|---|
| `"M"` | `"atDateAsMonthOfYearString"` | "Apr 2026" (citation: `PROJ-exec-report-uigb.json`) |
| `"Y"` | `"atDateAsYearString"` (assumed) | "2026" |
| `"D"` | `"atDate"` | per-day buckets |
| `"QY"` | `"atDateAsQuarterOfYearString"` | "Q2 2026" (citation: `client-b-sample/proj-labor-by-month-uigb.json`) |
| `"MY"` | `"atDateAsMonthOfYearString"` | month-of-year (citation: same file) |
| `"WY"` | `"atDateAsWeekOfYearString"` (assumed) | week-of-year |

Pair with `notime: "false"` to keep time-of-day in the underlying value (default) or `"true"` to suppress.

Only `M`, `QY`, and `MY` are empirically confirmed in the 40-sample survey. The others are documented in Workfront's text-mode reference; treat as untested but legal.

**Matrix groupings.** Add `orientation: "H"` (horizontal row axis) or `orientation: "V"` (vertical column axis) for matrix reports:

```json
"group": [
  {
    "linkedname": "direct",
    "namekey": "name",
    "orientation": "H",
    "valuefield": "name",
    "valueformat": "string"
  },
  {
    "groupdatesby": "QY",
    "linkedname": "direct",
    "namekey": "actualstartdate",
    "orientation": "V",
    "valuefield": "actualStartDate",
    "valueformat": "atDateAsQuarterOfYearString"
  },
  {
    "groupdatesby": "MY",
    "insertPlaceholder": "true",
    "linkedname": "direct",
    "namekey": "actualstartdate",
    "orientation": "V",
    "valuefield": "actualStartDate",
    "valueformat": "atDateAsMonthOfYearString"
  }
]
```

Citation: `client-b-sample/proj-labor-by-month-uigb.json`. Reads as: projects on the H axis, quarters then months on the V axis. The UIVW wrapper carries `reportType: "M"` (matrix) — see `01-report-object-shape.md`. Matrix view creation is mentioned for completeness; the v0.9.0 skill targets list reports (`layoutType: "list"`) and does not write matrix views from scratch. Cloning a matrix view preserves orientation pass-through.

`insertPlaceholder: "true"` on the inner-most group level inserts empty buckets between non-contiguous periods (so a matrix with no rows for March still shows the March column). Cite same file.

**Custom-field group.** Group on a DE: custom field — DROPS the `DE:` prefix in `valuefield`:

```json
{
  "linkedname": "direct",
  "namekey": "Asset Tag",
  "valuefield": "Asset Tag",
  "valueformat": "customDataLabelsAsString"
}
```

NOT `valuefield: "DE:Asset Tag"`. Citation: `client-b-sample/PROJ-exec-report-uigb.json` third group level. This is one of the two locations where the DE: prefix is consistently DROPPED — see § 14.

**`valueexpression` group.** When the group label is a derived expression:

```json
{
  "displayname": "",
  "iscollapsed": "true",
  "textmode": "true",
  "valueexpression": "{project}.{portfolio}.{name}",
  "valueformat": "string"
}
```

Citation: `client-d-sample/DOCU-proofs-retail-uigb.json`. Reads as: group DOCU rows by the parent project's portfolio name.

Rules (same as column-level valueexpression — § 6):

- `textmode: "true"` REQUIRED on the group item.
- `definition.textmode: "true"` REQUIRED at the UIGB top level. Citation: same file has both. Without the top-level flag, Workfront refuses to parse the group's expression.
- `valuefield` is OMITTED.
- `displayname` REPLACES `namekey`. Empty string `""` is legal — the group header just shows the resolved value with no preceding label.

**`namekey: "view.relatedcolumn"`.** When the group label comes from a joined record's field, the canonical i18n key is `"view.relatedcolumn"` paired with a two-element `namekeyargkey: [<relation>, <field>]`. Workfront expands this to "Relation: Field" at render time. Citation: `client-b-sample/PROJ-exec-report-uigb.json` middle group level uses `namekeyargkey: ["program", "name"]`.

**Calculated-grouping range buckets — sort-index prefix.** When a `valueexpression` group emits range-label strings — `"0% complete"`, `"1% to 10%"`, `"11% to 20%"`, ..., `"91% to 100%"` — Workfront sorts the group headers alphabetically by the rendered label. Alphabetical ordering of those literal strings is `0%`, `1% to 10%`, `100%`, `11% to 20%`, `21% to 30%`, ... — visually wrong. The empirically-verified fix is a numeric sort-prefix inside the label:

```
IF({percentComplete}=0,"01: 0%",
IF({percentComplete}<11,"02: 1% to 10%",
IF({percentComplete}<21,"03: 11% to 20%",
IF({percentComplete}<31,"04: 21% to 30%",
... ,
IF({percentComplete}=100,"11: 100%","12: other")))))
```

The `01:` / `02:` / ... prefix forces the alphabetical sort to produce the intended order. The prefix is visually mild — consultants either accept it ("01: 0%") or strip it visually with a post-processing CONCAT that drops the first 4 chars before rendering (but doing so reintroduces the sort bug — leave the prefix in). Adobe's advanced-reporting training day 3 walks through this exact problem; the trainer's workaround is the same. Pre-flight does not lint for this; the symptom is purely visual (the report renders, just with rows in the wrong order).

## § 13. UIGB.definition top-level

Just `group[]` plus optional `textmode: "false"` (string) at the top:

```json
{
  "group": [ /* one or more group entries */ ],
  "textmode": "false"
}
```

`textmode` is OPTIONAL — `client-c-sample/HOUR-support-hours-uigb.json` has `"textmode": "false"`, `client-b-sample/TASK-ready-to-work-uigb.json` has `"textmode": "true"` because at least one group uses `valueexpression`, and `client-d-sample/TTSK-tmpl-digital-role-uigb.json` omits `textmode` entirely. The renderer treats absent and `"false"` as equivalent.

The UIGB wrapper around `definition` looks like this:

```json
{
  "label": "_grouping",
  "objCode": "UIGB",
  "uiObjCode": "TASK",
  "groupingType": "REPORT",
  "definition": { "group": [...] }
}
```

`groupingType: "REPORT"` is consistent across all 40 UIGBs in the survey (parallel to `filterType: "REPORT"` on UIFTs — see `06-filter-patterns.md`). Always emit `"REPORT"` on create.

**Empty grouping.** A report with no grouping omits the UIGB row entirely OR writes `{"group": []}` — both work. List-style ASSGN reports omit UIGB entirely (cite `client-c-sample/ASSGN-user-assignments-L-report.json` whose `groupByID: null`); the report renders as one flat list. The four-call create sequence in `02-create-from-scratch-recipe.md` always writes a UIGB row even when empty, to keep the wrapper invariant simple.

## § 14. The `DE:` prefix asymmetry, in full

The skill's clone sanitizer and pre-flight validator both depend on a precise reading of where `DE:` is KEPT and where it is DROPPED. The rule is **by location, not by field**. Here is the full table, with empirical citations on the same custom field across all locations where possible.

**Locations where `DE:` is KEPT:**

| Location | Example | Citation |
|---|---|---|
| UIFT key | `"DE:Duration Delta 2_Mod": "gt"` | (hypothetical for this field; see `06-filter-patterns.md` § 6 for cited examples on other DE: fields) |
| UIVW column `querysort` | `"querysort": "DE:Duration Delta 2"` | `client-b-sample/PROJ-asset-pva-duration-uivw.json` |
| UIVW column `aggregator.valuefield` | `"valuefield": "DE:Duration Delta 2"` (inside aggregator) | same file |
| UIVW styledef `leftmethod` and `lefttext` | `"leftmethod": "DE:Is this a rush request?"` | `client-d-sample/OPTASK-rush-L-uivw.json` |
| UIVW image `leftmethod`, `lefttext`, `namevalue` | `"namevalue": "DE:Additional Print Detail"` | `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json` |
| UIVW row[] styledef `leftmethod` and `lefttext` | `"leftmethod": "DE:Weekly Promotion Type"` | `client-a-sample/PROJ-insertion-sched-NOFILTER-uivw.json` |
| UIVW `valueexpression` brace-references | `{DE:Approved Hours}` inside an expression | `client-c-sample/HOUR-support-hours-uivw.json` |

**Inverted grammar in `querysort`.** Filter-side keys use `[DE:][<join>:...]<field>` ordering (06-filter-patterns.md § 5-6). UIVW column `querysort` uses the INVERTED form: `[<join>:][DE:]<field>` — the join hop comes before the DE: prefix, not after. Empirical: `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json` has `"querysort": "program:DE:Promotion Number"` and `"querysort": "program:DE:Rewards Number"`. The pre-flight validator must parse both orderings.

**Locations where `DE:` is DROPPED:**

| Location | Example | Citation |
|---|---|---|
| UIVW column `valuefield` (regular columns) | `"valuefield": "Duration Delta 2"` | `client-b-sample/PROJ-asset-pva-duration-uivw.json` |
| UIGB group `valuefield` | `"valuefield": "Asset Tag"` | `client-b-sample/PROJ-exec-report-uigb.json` |

**Three-way split on the SAME field.** `client-b-sample/PROJ-asset-pva-duration-uivw.json` carries the custom field `DE:Duration Delta 2` in three locations on one column:

```json
{
  "valuefield": "Duration Delta 2",       // DROPPED
  "querysort": "DE:Duration Delta 2",     // KEPT
  "aggregator": {
    "valuefield": "DE:Duration Delta 2",  // KEPT
    "function": "AVG",
    ...
  }
}
```

This is the loudest empirical evidence that the rule is by location.

**Edge case: `textmode:"true"` columns without `valueexpression`.** A column that opts into Text Mode but doesn't supply a `valueexpression` is a "user wrote the column in text-mode-tab" signal. Empirical evidence (1 case, `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json`): such columns KEEP the `DE:` prefix in `valuefield`. No negative case observed in the 33-report survey. The pre-flight validator should accept BOTH the standard form (DE: DROPPED in valuefield) AND the textmode-edge form (DE: KEPT in valuefield) when `textmode:"true"` is set without a `valueexpression`. When in doubt, prefer the empirical form on the source side and let pre-flight decide.

Treat as an edge case the sanitizer accepts both ways — the skill emits with DE: DROPPED on create, but preserves whatever the source had on clone. The renderer accepts both forms in this slot.

**Pre-flight validator implication.** `08-pre-flight-validation.md` walks every column and group and validates DE: presence per-location:

- `valuefield` on regular columns must NOT have `DE:` (warn if present, except for the textmode+HTML edge case).
- `querysort` on a DE: column must HAVE `DE:`.
- `aggregator.valuefield` must HAVE `DE:` when aggregating a custom field.
- Group `valuefield` on a DE: field must NOT have `DE:`.

**Sanitizer implication.** The clone-flow `sanitize_clone.py` does NOT rewrite the DE: prefix per-location — it preserves whatever was at the source. The destination tenant must have a custom form with the same field name attached to the same object (see `03-clone-and-adapt-recipe.md` Phase 5 parity check). What the sanitizer DOES flag is the field NAME itself — every distinct DE: field in the bundle becomes a parity-check item for the consultant to confirm.

## § 15. Per-uiObjCode column variants — PARAM and PGRP

Two niche objects use a different column shape. The standard column key set (§ 2) does not apply; instead, PARAM and PGRP columns use `name` and `descriptiveText`.

**PARAM (custom-field parameter rows).** Reports against the PARAM object — lists of custom-field definitions — use `name` (data field) and `descriptiveText` (user-facing label). Citation: `client-c-sample/PARAM-calc-only-L-uivw.json`:

```json
{
  "descriptiveText": "Field Label",
  "name": "displayName",
  "querysort": "displayName",
  "textmode": "true",
  "valuefield": "displayName",
  "valueformat": "string",
  "width": "200"
}
```

Note: PARAM columns carry BOTH `name` AND `valuefield` (they're typically the same string). They also carry `descriptiveText` (no i18n lookup — literal label). `namekey` is absent. `linkedname` is absent. The PARAM column shape is closer to a system-table-row schema than the polished report-column schema for first-class objects like TASK and PROJ.

**Enum columns on PARAM keep the canonical shape.** Citation: same file, `displayType` column:

```json
{
  "enumclass": "com.attask.common.constants.ParameterDisplayTypeEnum",
  "enumtype": "PARAM",
  "linkedname": "direct",
  "namekey": "displayType",
  "querysort": "displayType",
  "type": "enum",
  "valuefield": "displayType",
  "valueformat": "val"
}
```

The enum column has `namekey` + `linkedname` (canonical shape), NOT `name` + `descriptiveText`. The variant only applies to non-enum PARAM columns.

**PGRP (parameter group / custom-form rows).** Same `name` + `descriptiveText` pattern. Citation: `client-c-sample/PGRP-paramgroup-L-uivw.json`:

```json
{
  "descriptiveText": "Custom Form",
  "name": "name",
  "querysort": "name",
  "textmode": "true",
  "valuefield": "name",
  "valueformat": "string",
  "width": "200"
}
```

Iterate columns on PGRP — for showing the constituent parameters of a custom form — combine the variant shape with `type: "iterate"`. Citation: same file, third column:

```json
{
  "descriptiveText": "Calculated Fields and Formulas",
  "listdelimiter": "<div style=margin-bottom:6px>",
  "listmethod": "nested(categoryParameters).lists",
  "name": "categoryParameters",
  "textmode": "true",
  "type": "iterate",
  "valueexpression": "CONCAT({parameter}.{displayName},\": \",{customExpression})",
  "valueformat": "HTML",
  "width": "600"
}
```

**Pre-flight branch.** The validator (`08-pre-flight-validation.md`) checks `uiObjCode` and branches column-key validation:

- If `uiObjCode in {PARAM, PGRP}`: REQUIRED keys are `name`, `valuefield`, and either `descriptiveText` or `namekey`. `linkedname` is OPTIONAL.
- Otherwise: REQUIRED keys are `valuefield` (unless `valueexpression` is present), `valueformat`, and at least one of `namekey` / `displayname`.

Cloning a PARAM or PGRP report from one tenant to another preserves the variant shape on a round-trip; the skill does NOT normalize PARAM columns into the canonical column shape.

**Other niche objects.** TTSK (template tasks), TPRO (template projects), and CTGY (category / custom form) reports use the canonical column shape with no variant. The PARAM/PGRP variant is the only one observed in the 40-sample survey.

## § 16. Cross-references

- **Filter half (`UIFT.definition`)** — see `06-filter-patterns.md`. Operator catalogue, `_Mod` suffixes, OR-groups, EXISTS blocks, session tokens, TAB-separated multi-values.
- **Pre-flight validation of column references and join paths** — see `08-pre-flight-validation.md`. Walks every column and group; checks DE: prefix per-location (§ 14); branches on `uiObjCode` for PARAM/PGRP (§ 15); validates `valueformat` against field metadata.
- **Authoring of `valueexpression` calc strings (CONCAT, IF, CASE, ROUND, SUB, ISBLANK, STRING, DATEDIFF, brace-bracket field references)** — see `workfront-textmode`. This file documents only the JSON wrapper around `valueexpression`; the calc language itself is owned by its peer skill.
- **Text-mode authoring inside the `comparison` block of `styledef` / `image`** — also see `workfront-textmode`. The right-side `righttext` value supports `$$TODAY±Nd` arithmetic and the same calc-language idioms.
- **The four-call create sequence (UIFT → UIGB → UIVW → REPORT)** — see `02-create-from-scratch-recipe.md`. The view-half assembly composes a UIVW.definition matching the patterns documented here, and a UIGB.definition matching §§ 12-13.
- **The modify-flow PUT semantics** — see `02-create-from-scratch-recipe.md` § Modify flow. The JSON shape documented in this file is identical between create and modify; only the HTTP verb and target ID differ.
- **The clone-flow sanitizer behaviour** — DE: prefix preservation, host-rewrite for static-icon URLs and HTML links, tenant-specific date strings — see `03-clone-and-adapt-recipe.md` Phase 3 and `skills/workfront-reports/scripts/sanitize_clone.py`. The `host_rewrite` bucket specifically handles fully-qualified URLs inside `image.case[].comparison.truetext` (§ 8) and inside `valueexpression` HTML output (§ 6).
- **The report's outer wrapper fields** (`uiObjCode`, `categoryID`, `description`, chart fields, `layoutType`, `reportType: "M"` for matrix views, etc.) — none of which live inside `UIVW.definition` or `UIGB.definition` — see `01-report-object-shape.md`.
