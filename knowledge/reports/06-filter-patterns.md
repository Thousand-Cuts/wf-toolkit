# 06 — Filter Patterns

This file documents the JSON-object shape of `UIFT.definition` — the filter half of a Workfront report. The recipe in `02-create-from-scratch-recipe.md` calls into this file whenever a consultant's NL describes filter logic beyond the simplest field=value case. All examples and operator vocabulary come from an empirical survey of real reports across five client tenants — anonymized throughout as `client-a-sample/…` through `client-e-sample/…` (the raw JSON was removed from the repo for client-data hygiene; the findings below are the distilled, verified result). Every URL in this file uses `v17.0` per `knowledge/api/01-api-fundamentals.md`.

A note on what's in scope here: this file is about the **JSON shape** the API stores and returns. It is NOT about the text-mode authoring surface a consultant pastes into the in-product Text Mode tab (that's `workfront-textmode`). The two are duals — the API JSON shape documented here is what Workfront's UI converts text-mode into on save — but the skill writes the JSON directly and never round-trips through the text-mode parser. When this file says "the value is a TAB-separated string," it means the literal bytes the skill puts in the JSON payload.

## § 1. The basic shape

`UIFT.definition` is a flat `{string: string}` map. Each entry is one of:

- A field-value pair: `"<field>": "<value>"` paired with a sibling `"<field>_Mod": "<operator>"`.
- A control key: an OR-group prefix (`"OR:1:<inner-key>"`), an EXISTS-block prefix (`"EXISTS:a:<inner-key>"`), or a session/control token whose value is a `$$`-prefixed placeholder.
- A UI-builder artifact: the empty-string key `"": ""` round-trips out of the in-product builder on some tenants. Safe to omit; harmless if kept.

That's it. There are no nested objects, no arrays, no JSON booleans, no JSON numbers — every value is a string, even for numeric fields like `percentComplete` or boolean fields like `canStart`. Multi-value sets are encoded as TAB-separated strings (see § 3). Compound logic is encoded by prefixing keys (see § 7 and § 8).

The wrapper around `definition` looks like this on a fresh write or a clone:

```json
{
  "name": "_filter",
  "objCode": "UIFT",
  "uiObjCode": "PROJ",
  "filterType": "REPORT",
  "definition": { /* the map documented in the rest of this file */ }
}
```

A few of those wrapper fields matter to the skill:

- `uiObjCode` — names the object the filter runs against (`PROJ`, `TASK`, `OPTASK`, `DOCU`, etc.). Every key inside `definition` is resolved against this object's field set; see `05-gotchas.md` § 1 for the mismatch failure mode.
- `filterType` — always `"REPORT"` for report filters. Workfront uses other values (`"GLOBAL"`, `"USER"`) for saved-search and inline-filter contexts; the skill only writes `"REPORT"`.
- `name` — the in-product builder writes `"_filter"`. The skill writes `"<report name> — filter"` to make orphaned UIFT rows easier to find during cleanup (see `05-gotchas.md` § 5).

An empty `definition` is legal and means "show everything." Seen in `client-b-sample/PRFAPL-proof-decisions-uift.json` (1/40 samples) — a proof-approval listing with no filter, relying entirely on the report's view and the user's accessRules to scope the row set.

The bare AND case — multiple field-value pairs at the top level — is the most common shape across the survey. Example from `client-d-sample/PROJ-by-condition-uift.json`:

```json
{
  "portfolioID": "68b39b4900004ee82b8550ca09877e05",
  "portfolioID_Mod": "notin",
  "statusEquatesWith": "CUR",
  "statusEquatesWith_Mod": "in"
}
```

Reads as: "projects whose portfolio is NOT the given ID AND whose status equivalence is CUR (Current)." Two field-Mod pairs, AND-joined.

`filterType: "REPORT"` is consistent across every UIFT in the survey — `PROJ-by-condition-uift.json` confirms it for the project case, and the same value appears in every other tenant's UIFTs (40/40 samples). The skill always sends `"REPORT"`; it never has to discover this one at runtime.

## § 2. Operator catalogue

The operator name lives in the sibling `<field>_Mod` key. Every value in the catalogue below is empirical — pulled from a specific UIFT in the survey.

| Operator | Semantics | Value form | Sample citation | Notes |
|---|---|---|---|---|
| `eq` | exact match | scalar string | `client-b-sample/PROJ-exec-report-uift.json` (`program:isActive_Mod=eq`, value `"true"`) | Ubiquitous; default-feel for scalar fields. |
| `ne` | not equal | scalar string | not in 40-sample survey; documented in Workfront API ref | Use `notin` with a single value if uncertain. |
| `in` | value in set | TAB-separated string | `client-d-sample/OPTASK-rush-L-uift.json` (`teamID_Mod=in`, value `"$$USER.teamIDs"`) | See § 3 for the TAB convention. |
| `notin` | value not in set | TAB-separated string | `client-a-sample/TASK-major-roadblocks-uift.json` (`status_Mod=notin`, value `"CPL"`) | Works with a single value too. |
| `isnull` | field is empty | value MUST be `""` | `client-b-sample/TASK-bulk-launch-L-uift.json` (`DE:Launch Date_Mod=isnull`) | The value-string is required even though it's ignored. |
| `notnull` | field is non-empty | value MUST be `""` | `client-c-sample/HOUR-support-hours-uift.json` (`DE:project:Approved Hours_Mod=notnull`) | Different operator from `notblank`; see note below. |
| `notblank` | field is non-empty (string-ish) | value MUST be `""` | `client-d-sample/TASK-pm-audit-late-uift.json` (`assignedToID_Mod=notblank`); `client-b-sample/PROJ-asset-pva-duration-uift.json` (`templateID_Mod=notblank`) | Semantically near-identical to `notnull`; pick whichever the field's metadata names. |
| `gt` | strictly greater | scalar string | `client-b-sample/PROJ-asset-pva-duration-uift.json` (`actualDurationMinutes_Mod=gt`, value `"0"`) | Numeric and date fields. |
| `lt` | strictly less | scalar string | `client-a-sample/TASK-major-roadblocks-uift.json` (`percentComplete_Mod=lt`, value `"100"`); `client-d-sample/TASK-pm-audit-late-uift.json` (`plannedCompletionDate_Mod=lt`, value `"$$TODAY"`) | Numeric and date fields. |
| `gte` | greater or equal | scalar string | `client-c-sample/HOUR-support-hours-uift.json` (`entryDate_Mod=gte`, value `"2025-12-31T19:00:00:000-0500"`) | Inclusive bound. |
| `lte` | less or equal | scalar string | not in 40-sample survey for filters; common in views | Inclusive bound. |
| `cicontains` | case-insensitive substring | scalar string | `client-b-sample/TASK-bulk-launch-L-uift.json` (`parent:name_Mod=cicontains`, value `"Launch"`); `client-d-sample/DOCU-proofs-retail-uift.json` (`currentVersion:proofDecision_Mod=cicontains`, value `"pending"`) | String fields only. |
| `between` | inclusive range | paired value with `<field>_Range` sibling | not in UIFT samples; appears in view styledef (`07-view-patterns.md`) | Rare in filter context; use `gte` + `lte` pair instead. |
| `contains` | substring (case-sensitive) | scalar string | not in 40-sample survey | Prefer `cicontains` unless the field is known case-sensitive. |

**Field-to-field comparison (`field:` value prefix).** A filter value of the literal form `field:<otherFieldName>` triggers a cross-field comparison instead of a literal-value match. Example: "tasks where actual work exceeds planned work":

```json
{
  "actualWorkRequired": "field:plannedWorkRequired",
  "actualWorkRequired_Mod": "gt"
}
```

Reads as: "actualWorkRequired > plannedWorkRequired (per row)." The `field:` prefix is parsed BEFORE the value is type-coerced, so this works on any field pair where `_Mod` is a comparison operator (`eq`, `ne`, `gt`, `lt`, `gte`, `lte`). Adobe's advanced-reporting training day 1 demonstrates the same pattern with `actualHours_Mod=gt&actualHours=field:plannedHours`. The bare-field reference uses camelCase (the API key for the other field), NOT the colon-joined relation form — `field:project:plannedHours` is NOT supported; for cross-relation comparisons, write a `valueexpression` column with a `STRING({this}) != STRING({other})`-style guard instead and filter on that.

**`notnull` vs `notblank`.** These are two genuinely distinct operators on the wire. Empirically, custom-form `Date` and `Currency` fields prefer `notnull` (Client C's `DE:project:Approved Hours_Mod=notnull`), while object-reference fields like `assignedToID` and `templateID` prefer `notblank` (Client D and Client B samples). The semantic difference is invisible from the API response. The skill defers to pre-flight validation (`08-pre-flight-validation.md`): if the cached `/<uiObjCode>/metadata` flags the target field as a UUID reference, prefer `notblank`; otherwise prefer `notnull`. Either operator generally works against either kind of field, but matching the field's metadata is the safer default.

**Wire encoding for every value.** Even numerics and booleans are JSON strings inside `definition`. Empirically:

- `"actualDurationMinutes": "0"` (not `0`) — `PROJ-asset-pva-duration-uift.json`.
- `"percentComplete": "100"` — `TASK-major-roadblocks-uift.json`.
- `"numberOfChildren": "0"` — `TASK-major-roadblocks-uift.json` and `TASK-pm-audit-late-uift.json`.
- `"canStart": "true"` (not `true`) — `TASK-ready-to-work-uift.json` and `TASK-late-by-individual-uift.json`.
- `"program:isActive": "true"` — `PROJ-exec-report-uift.json`.

If the skill ever serialises a value as a raw JSON number or boolean, Workfront accepts the POST but the round-tripped read comes back stringified — and the in-product builder may then refuse to open the report for edit. Always stringify.

## § 3. Multi-value with TAB separator

When the operator is `in` or `notin`, the field-value is a single string with TAB (`\t`) bytes delimiting the values. NOT a JSON array. NOT comma-separated. NOT space-separated.

Three patterns:

**Bare enum values.** Status codes, equivalence states, and other built-in enums combine straight:

```json
{
  "status": "CPL\tQUE",
  "status_Mod": "notin"
}
```

Reads as: "status is neither CPL (Complete) nor QUE (Queued)." From `client-b-sample/PROJ-exec-report-uift.json`. A second equivalent example: `"status": "CUR\tPLN", "status_Mod": "in"` for "projects in Current OR Planning status" (seen in clone-style patterns; verify before applying).

**UUID lists.** Portfolio, group, team, and program IDs (32-hex-char Workfront UUIDs) chain the same way:

```json
{
  "project:portfolioID": "6989fca100017e3f752d212662c02b2a\t6989fca100017e1347fee6d3fb7d3a70\t6989fca100017e35607fd2aab301d2b3\t6989fca100017e0911114eab94397dfe\t6989fca100017e414e781e46b8bd34b5\t6989fca100017df57015d63706850de0\t6989fca100017e15d536a1fe2bda2a5e\t6989fca100017e17b088e7e0f328ae63",
  "project:portfolioID_Mod": "in"
}
```

From `client-d-sample/DOCU-proofs-retail-uift.json` — eight portfolio UUIDs joined by `\t`. The skill never writes UUIDs from memory; it discovers them via `/portfolio/search` (or accepts them from the consultant) and joins with `"\t".join(ids)` before stringifying into `definition`.

**Mixed session tokens and IDs.** Session tokens (see § 4) can combine with each other or with literal IDs inside one TAB-separated value:

```json
{
  "teamID": "$$USER.teamIDs\t$$USER.homeTeamID",
  "teamID_Mod": "in"
}
```

From `client-d-sample/PROJ-my-teams-active-uift.json`. Reads as: "team is any of the session user's teams OR their home team." Workfront resolves both tokens at render time per-user, so the report row is shareable without parameter-stuffing.

**Encoding.** The TAB character is a literal `\t` (`0x09`) inside the JSON string. When inspecting raw curl output, the byte appears as-is; `python3 -m json.tool` renders it as `\t`. The skill emits real TAB bytes via `"\t".join(...)`, NEVER the two-character escape sequence `\\t`. Workfront's parser treats the escape as a 2-char literal and silently produces a never-matching value.

## § 4. Session and control tokens

Workfront's `$$`-prefixed runtime placeholders are resolved by the server per-render, per-session. They make filters portable across users and time.

| Token | Resolves to | Seen in (sample) |
|---|---|---|
| `$$USER.ID` | the rendering user's UUID (scalar) | `client-b-sample/TASK-ready-to-work-uift.json`, `client-b-sample/DOCU-pending-approval-uift.json` |
| `$$USER.teamIDs` | every team UUID the rendering user is on (multi-value, TAB-separated internally) | `client-d-sample/OPTASK-rush-L-uift.json`, `client-d-sample/PROJ-my-teams-active-uift.json` |
| `$$USER.homeTeamID` | the rendering user's home team UUID (scalar) | `client-c-sample/ASSGN-user-assignments-L-uift.json` |
| `$$TODAY` | today's date in the tenant's server timezone | `client-d-sample/TASK-pm-audit-late-uift.json` |
| `$$TODAY±Nd` | date arithmetic, N days from today (`$$TODAY-30d`, `$$TODAY+7d`, `$$TODAY-1w`, `$$TODAY+1m`) | `client-c-sample/PROJ-revenue-prog-CHART-uift.json` uses a literal date but the arithmetic form is in `workfront-textmode` knowledge |
| `$$NOW` | current timestamp (rare; date-time precision) | not in 40-sample survey; documented in Workfront docs |
| `$$USER.companyID` | the rendering user's company UUID | not in 40-sample survey |
| `$$USER.roleID` | the rendering user's primary role UUID | not in 40-sample survey |

A scalar `$$USER.ID` used with `_Mod=in` is legal — Workfront just resolves the token then matches on the single value. Example from `client-b-sample/TASK-ready-to-work-uift.json`:

```json
{
  "assignedToID": "$$USER.ID",
  "assignedToID_Mod": "in"
}
```

`$$USER.ID` paired with `_Mod=eq` is also legal (`client-b-sample/DOCU-pending-approval-uift.json` inside an EXISTS block uses `eq`). The choice is stylistic — the skill matches whatever the source UIFT uses on a clone, and on a create chooses `eq` for scalar tokens and `in` for multi-value tokens like `$$USER.teamIDs`.

**Sanitizer behaviour.** These tokens are tenant-neutral by construction — they resolve at render time, and any user in any tenant will get a sensible answer (or fall through to "no rows" if the session has no home team). The clone-flow sanitizer in `sanitize_clone.py` passes them through unchanged. The skill does NOT prompt the consultant about them.

**Date format note.** The bare `$$TODAY` token is timezone-aware (it resolves to midnight in the tenant's configured timezone). A literal date string in the same filter slot, like `client-c-sample/PROJ-revenue-prog-CHART-uift.json`'s `"entryDate": "2025-01-01T00:00:00:000-0500"`, IS tenant-specific — the offset (`-0500`) is the tenant's server offset at the moment the report was authored. On a cross-tenant clone, the sanitizer flags literal date strings for the consultant to confirm or replace with `$$TODAY±Nd` arithmetic.

## § 5. Cross-object join paths

A filter key can traverse one or more object relations via colon-separator. The key reads left-to-right as a path from the `uiObjCode` object outward.

Examples from the survey:

- **One hop, scalar field.** `"program:isActive": "true"` — filter on the PROJ's parent program's boolean `isActive` field. From `client-b-sample/PROJ-exec-report-uift.json`. The `_Mod=eq` paired key reads against the joined field, not the outer object.
- **One hop, status field.** `"project:status": "ONH", "project:status_Mod": "notin"` — TASK report filtering the parent project's status. From `client-b-sample/TASK-ready-to-work-uift.json`.
- **One hop, status equivalence.** `"project:statusEquatesWith": "CUR", "project:statusEquatesWith_Mod": "in"` — same pattern with the equivalence-state field. From `client-d-sample/TASK-pm-audit-late-uift.json`.
- **One hop, custom field on a join target.** `"DE:project:Approved Hours_Mod": "notnull"` — HOUR report filtering on a custom field defined on the parent project's custom form. From `client-c-sample/HOUR-support-hours-uift.json`. See § 6 for the `DE:` prefix semantics.
- **Two hops, with a custom field at the end.** `"DE:program:Acme - Program Revenue Reporting  Type": "Variable Revenue"` — PROJ report filtering on its parent program's custom-form field. From `client-c-sample/PROJ-var-rev-PROMPTS-uift.json`. Note the two-space spelling inside `"Reporting  Type"` — preserved verbatim from the source tenant's custom-form field name (consultants get the spelling wrong half the time; the skill never normalizes whitespace inside `DE:` field names).
- **Single-hop with a long relation name.** `"convertedOpTaskOriginator:homeTeamID": "$$USER.teamIDs\t$$USER.homeTeamID"` — the relation `convertedOpTaskOriginator` is one token referring to the origin OPTASK (the request that converted to this project); `homeTeamID` is a field on that joined OPTASK. One syntactic hop (one colon). From `client-d-sample/PROJ-my-teams-active-uift.json`.
- **Two hops, simple object property.** `"currentVersion:proofDecision": "pending", "currentVersion:proofDecision_Mod": "cicontains"` — DOCU report filtering on the current version's proof-decision string. From `client-d-sample/DOCU-proofs-retail-uift.json`.

**Join hop depth.** Workfront's published filter-hop limit is 2 hops. The survey contains single-hop and two-hop join examples; trust the pre-flight validator (`08-pre-flight-validation.md`) to assert each hop resolves against cached `/<objCode>/metadata` rather than enforcing a static depth limit in this file. The validator reports either "all hops resolve" or "hop N is unreachable from object X."

**Filter-on-joined-ID is fine; filter-on-joined-name is also fine.** Both `project:portfolioID` (UUID) and `project:portfolio:name` (string) are legal filter keys. UUIDs are more efficient and avoid case-sensitivity bugs; names are more readable. The skill prefers UUIDs when the consultant gives an ID-shaped value, and falls back to names when the consultant pastes the human-readable label.

## § 6. Custom-field (`DE:`) references in UIFT keys

Data-extension keys reference custom fields defined on the target object's custom form.

**Basic pattern.** `"DE:<field-name>": "<value>"` with `"DE:<field-name>_Mod": "<op>"`. The field name preserves its original casing, spaces, punctuation, and any non-ASCII characters. The `DE:` prefix is literal.

Examples:

- `"DE:Project Priority": "HIGH PRIORITY"` — single-select string field. From `client-b-sample/PRGM-high-priority-uift.json`.
- `"DE:Is this a rush request?": "🔥 Rush"` — UTF-8 emoji preserved exactly. From `client-d-sample/OPTASK-rush-L-uift.json`. The skill emits the emoji byte-for-byte; never escapes it as `🔥` unless the original UIFT used that form (in which case it round-trips through the JSON parser to the same on-wire bytes).
- `"DE:Launch Date_Mod": "isnull"` — date field, null-check operator, with the paired value as `""`. From `client-b-sample/TASK-bulk-launch-L-uift.json`.

**Composite with join paths.** The `DE:` prefix sits BEFORE the join path. The full grammar is `"DE:<hop1>:<hop2>:...:<field-name>"`:

- `"DE:project:Approved Hours_Mod": "notnull"` — HOUR's parent project has a custom form with an "Approved Hours" field. From `client-c-sample/HOUR-support-hours-uift.json`.
- `"DE:program:Acme - Program Revenue Reporting  Type": "Variable Revenue"` — PROJ's parent program. From `client-c-sample/PROJ-var-rev-PROMPTS-uift.json`.

**The `DE:` asymmetry.** The `DE:` prefix is KEPT in three places:

1. UIFT keys (this file).
2. UIVW `column.N.querysort` strings.
3. UIVW `column.N.aggregator.valuefield` strings.

The `DE:` prefix is DROPPED in two places:

1. UIVW `column.N.valuefield` strings (a column displaying the field uses bare `<field-name>`).
2. UIGB `group.N.valuefield` strings.

See `07-view-patterns.md` § custom-fields for the view-side detail. The `sanitize_clone.py` module handles the asymmetry automatically on a clone; the skill just composes whichever form matches the location.

**Parity check on clone.** When the clone flow lifts a UIFT containing a `DE:<name>` reference, it flags the field for the consultant: "this filter references `DE:<name>`, which exists at the source tenant. The destination tenant must have a custom form on `<uiObjCode>` (and on any joined parent objects) defining the same parameter name. Confirm parity before proceeding." See `03-clone-and-adapt-recipe.md` Phase 5.

**See also:** `08-pre-flight-validation.md` § 4d for the hard-coded PSEUDO_FIELDS allowlist (`statusEquatesWith`, `assignmentsListString`) and `09-verification-flow.md` § 6 for the per-tenant whitelist that overlays it. Both are how the pre-flight validator accepts runtime-real fields missing from `/<obj>/metadata`.

## § 7. OR-group filters

Compound OR-logic is encoded with a numeric-group prefix. Workfront has no nested-array structure inside `definition`; OR semantics come entirely from key naming.

**Syntax.** `"OR:<n>:<inner-key>": "<value>"` where `<n>` is a small positive integer (1, 2, 3, ...) identifying the OR-group. The inner-key can be any of the forms described in § 1 through § 6 — bare field, custom field, join path, with or without `_Mod` suffix.

**Logic shape.** Within one OR-group `OR:<n>:`, all keys with that prefix are AND-joined among themselves. The whole group is then OR'd with the bare keys (the ones with no `OR:<n>:` prefix). Multiple OR-groups (`OR:1:`, `OR:2:`, ...) are each independently AND-joined internally, and the whole filter is the conjunction of `(bare_keys) AND (OR:1 group OR OR:2 group OR ...)`. Read it as: `bare AND (group1 OR group2 OR ...)`.

In practice, every empirical sample uses exactly one OR-group at most. Treat multi-group OR as a possible shape but reach for EXISTS (§ 8) or a different filter strategy before attempting `OR:2:` and `OR:3:` keys.

**Prefix order.** `OR:<n>:` attaches BEFORE every other prefix including `DE:`. The full grammar in order is:

```
[OR:<n>:][EXISTS:<letter>:][DE:][<join>:<join>:...]<field>[_Mod]
```

Note that OR and EXISTS prefixes do not co-occur in any empirical sample — they encode different logical structures. Reach for one or the other, not both at once.

**Full example.** From `client-d-sample/OPTASK-rush-L-uift.json`:

```json
{
  "DE:Is this a rush request?": "🔥 Rush",
  "DE:Is this a rush request?_Mod": "in",
  "OR:1:DE:Is this a rush request?": "🔥 Rush",
  "OR:1:DE:Is this a rush request?_Mod": "in",
  "OR:1:assignedToID": "$$USER.ID",
  "OR:1:assignedToID_Mod": "in",
  "OR:1:statusEquatesWith": "NEW",
  "OR:1:statusEquatesWith_Mod": "in",
  "statusEquatesWith": "NEW",
  "statusEquatesWith_Mod": "in",
  "teamID": "$$USER.teamIDs",
  "teamID_Mod": "in"
}
```

Bare keys: `DE:Is this a rush request?=🔥 Rush`, `statusEquatesWith=NEW`, `teamID=$$USER.teamIDs`.

OR:1 group: `DE:Is this a rush request?=🔥 Rush`, `assignedToID=$$USER.ID`, `statusEquatesWith=NEW`.

Reads as: `(rush_request="🔥 Rush" AND status=NEW AND team∈my_teams) AND (rush_request="🔥 Rush" AND assignee=me AND status=NEW)` — which by intersection collapses to `(rush_request="🔥 Rush" AND status=NEW AND assignee=me AND team∈my_teams)`. The duplication of bare-keys inside `OR:1:` is the in-product builder's way of keeping the filter renderable in both AND-view and OR-view; the logical effect with one OR-group is equivalent to a pure AND.

The duplication between bare and `OR:1:` is intentional — the in-product Filter builder writes both halves to preserve the user's intent on round-trip edit. Workfront treats the JSON as-is, and removing the duplicate keys on round-trip would change the in-product builder's ability to display the filter back to the consultant. The skill preserves the duplication on clone and emits it on create when the consultant requests an OR-group.

**Authoring rule.** When a consultant asks for "rows where (A AND B) OR (A AND C)," express it as:

- bare: A
- OR:1: A, B
- OR:1: A, C

The bare `A` becomes the always-true conjunct that ties the OR-group to the rest of the filter. If the consultant means "rows where B OR C" (no shared conjunct), express it as:

- OR:1: B
- OR:1: C

— and omit bare keys entirely on that field.

## § 8. EXISTS blocks

EXISTS encodes a sub-query: "this row has a child or related record matching X." Like OR-groups, EXISTS is name-prefix-driven; there's no nested object structure.

**Syntax.** `"EXISTS:<letter>:<inner-key>": "<value>"` where `<letter>` is a single lowercase alpha (a, b, c, ...) identifying the EXISTS block. Each block needs three control keys plus one or more constraint keys.

**Control keys (REQUIRED per block).**

| Key | Value form | Meaning |
|---|---|---|
| `EXISTS:<l>:$$EXISTSMOD` | `"EXISTS"` or `"NOTEXISTS"` | direction: rows that DO have a matching child (`EXISTS`, default) vs rows that DO NOT (`NOTEXISTS`) |
| `EXISTS:<l>:$$OBJCODE` | `"<objCode>"` | the related object type — `TASK`, `OPTASK`, `ASSGN`, `DOCU`, `HOUR`, `PRFAPL`, etc. |
| `EXISTS:<l>:$$ID` (sometimes `EXISTS:<l>:ID`) | `"FIELD:<outer-field>"` | join key: the outer object's field that links to the related object's `ID`. The `FIELD:` prefix is literal. |

Constraint keys follow the standard `<field>:<op>` shape, scoped inside the block: `"EXISTS:<l>:<related-field>": "<value>"` plus the paired `"EXISTS:<l>:<related-field>_Mod": "<op>"`.

**Full example.** From `client-b-sample/DOCU-pending-approval-uift.json`:

```json
{
  "": "",
  "EXISTS:a:$$EXISTSMOD": "EXISTS",
  "EXISTS:a:$$OBJCODE": "TASK",
  "EXISTS:a:ID": "FIELD:taskID",
  "EXISTS:a:assignedToID": "$$USER.ID",
  "EXISTS:a:assignedToID_Mod": "eq"
}
```

Reads as: "documents where there EXISTS a related TASK (joined via `document.taskID = task.ID`) with `assignedToID = $$USER.ID`."

A few details from this example worth pinning down:

- The outer object is `DOCU` (set in the UIFT wrapper's `uiObjCode`). The inner object is `TASK`.
- The join key `"EXISTS:a:ID": "FIELD:taskID"` reads "the related TASK's `ID` matches the outer DOCU row's `taskID` field." This is the universal join idiom: the inner block's `ID` field is matched against `FIELD:<outer-field>`.
- Empirically, both `EXISTS:<l>:ID` (no `$$` prefix) and `EXISTS:<l>:$$ID` ($$ prefix) appear in the wild. Client B's `DOCU-pending-approval-uift.json` uses bare `ID`. The skill writes whatever the source filter used on a clone, and on a create uses `$$ID` to disambiguate from a constraint on an actual `ID` field.
- The leading `"": ""` empty-key pair is a UI-builder artifact — harmless, safe to omit, see § 10.

**Multiple EXISTS blocks.** Use `EXISTS:a:`, `EXISTS:b:`, ... Each block is internally AND-joined, the blocks are AND-joined with each other and with any bare keys. There's no EXISTS-OR-EXISTS form in the empirical survey; combine via two blocks with `NOTEXISTS` and `EXISTS` if you need set-difference logic.

**NOTEXISTS direction.** Setting `EXISTS:<l>:$$EXISTSMOD` to `"NOTEXISTS"` flips the block to "this row has NO matching child." Useful for "projects with no open issues," "tasks with no time logged," etc. Not in the 40-sample survey but documented in Workfront's text-mode reference.

**Object-code vocabulary.** The `$$OBJCODE` value is one of Workfront's standard codes: `TASK`, `OPTASK`, `PROJ`, `ASSGN`, `DOCU`, `HOUR`, `PRFAPL`, `PRFAPV`, `NOTE`, `TTSK`, `TPRO`, etc. The skill validates the value against `/<objCode>/metadata` at pre-flight (`08-pre-flight-validation.md`); if the metadata 404s, the EXISTS block won't match anything.

## § 9. Tenant convention variance

Across the empirical survey, tenants prefer different equivalent forms:

- **Client B** leans on EXISTS heavily — half their non-trivial filters use at least one EXISTS block, often to scope a DOCU or PRFAPL report to records belonging to tasks/projects the user owns. Example: `DOCU-pending-approval-uift.json` (single EXISTS), and other Client B filters chain two or three blocks.
- **Client D** leans on OR-groups — their queue-style OPTASK reports (`OPTASK-rush-L-uift.json`, `OPTASK-mktg-retail-uift.json`) all use the bare+OR:1 duplication pattern.
- **Client C** uses mostly flat AND filters with deep `DE:` join paths (`PROJ-var-rev-PROMPTS-uift.json`).
- **Client A** uses mostly flat AND filters with no `DE:` or join chains at all (`TASK-major-roadblocks-uift.json`, `TASK-late-by-individual-uift.json` — both identical in structure: five field-pairs all on the TASK object's own fields).
- **The partner sandbox** is sparse — single-condition filters dominate.

None of these is "right." OR-groups and EXISTS blocks express equivalent set logic in different syntactic surfaces, and a tenant's history (who built the first reports, which docs they read, which Adobe consultant trained them) explains most of the variance.

**Authoring rule for the skill.** When composing a new filter from NL, prefer the simpler form:

1. Flat AND (bare field-pairs) if every condition is on the `uiObjCode` object or one hop away.
2. Add a join-path prefix (`project:`, `program:`, etc.) for cross-object conditions that don't need sub-query semantics.
3. Reach for an OR-group only when the consultant explicitly says "or" or "either."
4. Reach for an EXISTS block only when the consultant asks about a child/related record's properties (e.g., "documents where any related task is assigned to me" — that's an EXISTS on TASK).

On clone, preserve whatever shape the source UIFT uses; don't normalize.

## § 10. Common pitfalls

**The empty-string key `"": ""`.** Some round-tripped filters include a `"": ""` pair (citation: `client-b-sample/DOCU-pending-approval-uift.json`). This is an in-product Filter builder artifact — a placeholder row the user clicked but didn't fill in. Safe to omit on create. The sanitizer drops it. If left in place on a clone, it's harmless — Workfront's parser ignores keys with empty values that have no `_Mod` sibling.

**`progressStatus` is a built-in TASK enum.** The field accepts values like `LT` (Late), `BH` (Behind), `OT` (On Time), `LR` (Late Risk), `RS` (At Risk). Citation: `client-a-sample/TASK-major-roadblocks-uift.json` uses `"progressStatus": "LT"`. The companion UIVW column declares `"enumclass": "...ProgressStatusEnum"` to render the label. NOT a `DE:` custom field — easy to confuse on first read. If a consultant says "progress status," check the metadata: if the field is on TASK natively, no `DE:` prefix.

**Boolean filters are stringified.** `"canStart": "true", "canStart_Mod": "eq"` — string `"true"`, not JSON `true`. Citations: `client-a-sample/TASK-late-by-individual-uift.json`, `client-b-sample/TASK-ready-to-work-uift.json`, `client-a-sample/TASK-major-roadblocks-uift.json`. The same stringification applies to `"false"`. See § 2 wire-encoding note.

**`statusEquatesWith` vs `status`.** Workfront's OPTASK and TASK objects have BOTH a literal `status` field (holding the tenant-specific status code, like `NEW`, `IPR`, `CPL`, or any custom code the tenant added) AND a `statusEquatesWith` field (holding an equivalence-state code that maps tenant-custom statuses to a canonical set: `NEW`, `CUR`, `CPL`, etc.). Citations: `client-d-sample/OPTASK-rush-L-uift.json` filters on `statusEquatesWith=NEW`; `client-a-sample/TASK-major-roadblocks-uift.json` filters on `status notin CPL` (literal status code). The choice matters: a clone of a Client D-authored OPTASK report into a tenant that uses different custom OPTASK statuses will keep working if it filters on `statusEquatesWith`, but break silently if it filters on literal `status` codes that don't exist in the destination. The skill's clone flow surfaces this as a parity-check warning when it sees `status_Mod` (not `statusEquatesWith_Mod`) in a cloned UIFT.

**Hex emojis from JSON.dumps.** When pasting JSON from a Python skill into a curl payload, `json.dumps(..., ensure_ascii=True)` (the default) escapes emojis to `🔥` form. Workfront accepts both — the parser normalizes — but the round-tripped read may come back in either form depending on the tenant's locale. Don't be alarmed when the source UIFT shows `"🔥 Rush"` and a clone shows `"🔥 Rush"`. Same bytes, different rendering.

**Whitespace in `DE:` field names.** Custom-form field names preserve all internal whitespace including double spaces. The Client C example `DE:program:Acme - Program Revenue Reporting  Type` has two spaces between "Reporting" and "Type" — the consultant who created the custom form typed it that way, and every reference must match exactly. The sanitizer does NOT collapse whitespace; the skill does NOT correct spelling. Round-trip from the source verbatim.

**TAB-separator escaping.** The TAB must be a literal `\t` byte in the on-wire JSON string, not the two-character escape `\\t`. Python `"\t"` works; literal backslash-t does not. Easy to get wrong in a templated payload.

**`isnull` / `notnull` / `notblank` value requirement.** All three operators require the paired value to be the empty string `""`. Setting the value to anything else (including `null` or omitting the key) causes Workfront to silently switch interpretation modes on some tenants — most often by treating the operator as `eq ""`, which is a substring match against literal empty rather than a NULL check. The skill always emits the empty string as the paired value.

**Date strings in tenant-local offset.** Hard-coded date strings like `"2025-12-31T19:00:00:000-0500"` (Client C's `entryDate`) carry the source tenant's timezone offset. On a cross-tenant clone where the destination tenant runs on a different offset (e.g., `-0800`), the absolute moment shifts. The sanitizer flags literal datetimes for replacement; the skill prefers `$$TODAY±Nd` arithmetic when authoring fresh.

## § 11. Cross-references

- Full text-mode operator catalogue with multi-value escape syntax and the "Not Equal multi-select" gotcha → `knowledge/textmode/03-filters-and-modifiers.md`.

The pre-flight validator (`08-pre-flight-validation.md`) walks every key in `UIFT.definition` and resolves each segment against cached `/<objCode>/metadata` from `04-runtime-schema-discovery.md`. It catches:

- Field names that don't exist on the target object (the `isTemplate` on PROJ class of error — Workfront's PROJ has no `isTemplate`; templates are a separate object `TMPL`).
- Join paths whose hops don't connect (`task:portfolio:name` works because TASK has a `project` relation and PROJ has a `portfolio` relation, but `task:program:name` skips a hop).
- Operators whose value form mismatches the field's metadata type (e.g., `_Mod=cicontains` against a UUID field).
- `DE:` references whose field names don't appear on any custom form attached to the target object (the parity-check failure mode).
- EXISTS blocks whose `$$OBJCODE` value 404s on `/<objCode>/metadata`.
- `_Mod=in`/`_Mod=notin` values that aren't TAB-separated when they contain a `,` (a common consultant-input bug).

For text-mode authoring details — the calc-style syntax that lives inside a UIVW column's `valueexpression` (not in the filter half) — see `07-view-patterns.md` § valueexpression. Defer the authoring of that calc syntax itself to `workfront-textmode`; this skill orchestrates the four-call envelope and shapes the JSON, but the text-mode calc language is owned by its peer.

For the modify-flow PUT semantics — the variant of the four-call sequence that mutates existing UIFT rows in place rather than creating new ones — see `02-create-from-scratch-recipe.md` § Modify flow. The JSON shape documented here is identical between create and modify; only the HTTP verb and target ID differ.

For the clone-flow sanitizer behaviour — which tokens pass through, which IDs get prompted, how literal dates get flagged — see `03-clone-and-adapt-recipe.md` Phase 3 and `skills/workfront-reports/scripts/sanitize_clone.py`.

For the report's outer wrapper fields (`uiObjCode`, `categoryID`, `description`, chart fields, etc.) — none of which live inside `UIFT.definition` — see `01-report-object-shape.md`.
