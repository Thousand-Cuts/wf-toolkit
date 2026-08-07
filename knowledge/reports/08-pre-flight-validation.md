# 08 — Pre-Flight Validation

Documents the pre-flight validation gate inserted between Phase C (compose payloads) and Phase E (apply gate) in the create and modify recipes. Catches errors like `isTemplate` on `PROJ` — fields that don't exist on the target object — before any byte writes. Builds on top of `schema_cache.py`'s cached `/<uiObjCode>/metadata` per `04-runtime-schema-discovery.md`. Every URL in this file uses `v17.0` per `knowledge/api/01-api-fundamentals.md`.

The algorithm documented here is the contract `scripts/pre_flight_validator.py` (and its test suite) asserts against. The text here is normative: if a future change to the validator disagrees with this file, one of them is wrong and the prose is the tiebreaker until the disagreement is resolved.

## § 1. Why pre-flight exists

Workfront's REST API is generous about what it accepts at POST time. A UIFT/UIGB/UIVW body that references fields the target object doesn't have — `isTemplate` on `PROJ`, `homeTeamID` on `DOCU`, `DE:Approved Hours` on a tenant with no such custom-form parameter — POSTs cleanly. The 200 OK arrives, the row gets created, and the failure mode only surfaces later: the report either renders empty, renders with "Invalid Parameter" in the column header, or refuses to open in the in-product Edit builder. Either way, the consultant has to delete the broken row and start over, and the cleanup of orphaned UIFT/UIGB/UIVW rows (per `05-gotchas.md` § 5) is manual.

Discovered live on 2026-05-13: a `PROJ` report was composed with `"isTemplate": "false"` in `UIFT.definition`. The POST sequence succeeded — UIFT, UIGB, UIVW, REPORT all created — but rendering returned a 200 with no rows and the column header showed "Invalid Parameter: isTemplate." The PROJ object has no `isTemplate` field at all; templates live under a separate objCode (`TMPL`). The fix was obvious in retrospect (drop the filter), but the discovery took 40 minutes of confused log-reading.

Pre-flight is the first line of defense against this class of error. It runs entirely against cached schema data plus a small batched DE-parity probe and produces a structured report the recipe consumes before reaching the `apply` gate. No POSTs happen until pre-flight is green.

The validator does not aim to be exhaustive. Workfront's published filter-hop limit and the runtime behaviour of some operators are not fully documented. The goal is to catch the high-confidence "this field does not exist" and "this DE: parameter is not on any custom form on the destination" cases — the classes of error that have actually surfaced in the firm's clone and create work.

## § 2. When pre-flight fires

The validator runs between Phase C and Phase E of both the create-from-scratch recipe (`02-create-from-scratch-recipe.md`) and the modify variant. The composed-but-unwritten bundle goes in; a structured validation report comes out.

```
A. Setup and schema discovery
B. Interview
C. Compose payloads (2/3/4 JSON bodies prepared, in-memory only)
D. Pre-flight validation                    ← THIS GATE
   → On valid:true:  proceed to E
   → On valid:false: print errors + suggestions; consultant types `edit` to revise
E. Single `apply` gate
F. Write (POST sequence)
G. Post-write verify
```

No bytes are written before pre-flight is green AND `apply` is typed. The two gates are independent: pre-flight can fail and the consultant can correct, then the `apply` gate still has to be passed before the actual POST sequence runs.

On the modify flow (PUT variant in `02-create-from-scratch-recipe.md` § Modify flow), pre-flight fires between "compose the PUT body" and "apply" — same position in the recipe, same gate behaviour.

On the clone flow (`03-clone-and-adapt-recipe.md`), pre-flight runs after the sanitizer has rewritten tenant-specific IDs and dates. The order matters: a sanitized bundle is what gets validated against the destination tenant's schema, not the source-tenant bundle.

The validator never writes to disk except its own stdout; it never makes write API calls; it never asks for additional credentials beyond the `--host` (used to look up the right cached metadata file). It is read-only against the schema cache plus, at most, a single `/parameter/search` GET batched across all `DE:` references in the bundle.

## § 3. Algorithm

Five sub-phases, executed in order. Each is independently testable.

### 3a. Resolve schema

Look up cached `/<uiObjCode>/metadata` for the bundle's `uiObjCode` via `schema_cache.get(host, uiObjCode)`. The cache is documented in `04-runtime-schema-discovery.md`; the validator does not implement its own cache.

```python
schema = schema_cache.get(host, uiObjCode)
if schema is None:
    schema = schema_cache.fetch_and_put(host, uiObjCode)
```

The same lookup is performed for any `EXISTS:<letter>:$$OBJCODE` value found in the bundle (each EXISTS block's `$$OBJCODE` becomes a secondary resolution context). The validator may end up holding 1–4 cached metadata documents at once: the outer `uiObjCode`, plus one per EXISTS block, plus any join-target objCodes resolved during 3d.

If a metadata fetch fails (network error, 404, malformed JSON), the validator returns `valid:false` with a single error of `reason: "could not resolve metadata for <objCode> on <host>"` and no field-level checks. The recipe surfaces this as a hard stop — the consultant either fixes credentials or refreshes the schema cache before retrying.

### 3b. Extract every field-name reference from the bundle

Walk the composed bundle and collect every string that names a Workfront field. The collection is a list of `(path, raw)` pairs where `path` is the JSON-pointer-ish location inside the bundle (e.g., `UIFT.definition.isTemplate`) and `raw` is the raw string before any prefix-stripping.

The walk covers:

- **UIFT.definition keys.** Every key in the flat map. Skip the empty-string key `""` (the UI-builder artifact documented in `06-filter-patterns.md` § 10). Skip `_Mod` and `_Range` suffix keys; they are sibling operator names, not field references — but the validator records each `_Mod` key's existence so it can later assert every field key has a matching `_Mod` (a separate validation, § 6).
- **UIVW.definition.column[].valuefield.** One per column. Drop empty-string `valuefield` (some `value`-only static-separator columns from `07-view-patterns.md` § 10 have no `valuefield`).
- **UIVW.definition.column[].querysort.** One per column with `querysort` set. The validator records both the raw value AND a flag indicating this came from a `querysort` slot — § 3c uses that flag to apply the inverted grammar parse (`[<join>:][DE:]<field>` rather than `[DE:][<join>:]<field>`). Citation: `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json` has `"querysort": "program:DE:Promotion Number"` — `program:` precedes `DE:`, which is the inverse of the filter-side grammar.
- **UIVW.definition.column[].aggregator.valuefield.** When the aggregator block is present and uses a single field rather than a `valueexpression`. KEEPS `DE:`; standard `[DE:][<join>:]<field>` grammar.
- **UIVW.definition.column[].aggregator.valueexpression.** When present, parse for `{<fieldname>}` references via best-effort regex (see below). Mutually exclusive with `aggregator.valuefield`.
- **UIVW.definition.column[].link.linkproperty[].valuefield.** Each entry. Usually `"ID"`; sometimes a different field for off-row click-through (e.g., `documentID` per `07-view-patterns.md` § 3).
- **UIVW.definition.column[].link.value.** Parsed for nested(...) chains and other field-reference forms — best-effort only; if the parse fails, the value is emitted as a warning rather than an error (these are URL templates and the validator is not a URL-template parser).
- **UIVW.definition.column[].valueexpression.** When present (mandatory `textmode: "true"` per `07-view-patterns.md` § 6). Parse for `{<fieldname>}` references via best-effort regex.
- **UIVW.definition.column[].styledef** entries. Each `leftmethod` is a field reference; `lefttext` is normally identical. Documented in `07-view-patterns.md` § 7.
- **UIVW.definition.column[].image.styles[].leftmethod/lefttext.** Same pattern, nested one level deeper. `07-view-patterns.md` § 8.
- **UIVW.definition.column[].sharecol[].valuefield / valueexpression.** Each sharecol participant. `07-view-patterns.md` § 10.
- **UIGB.definition.group[].valuefield.** One per group. DROPS `DE:` in the standard form (parallel to UIVW column `valuefield`). Documented in `07-view-patterns.md` § 12.
- **UIGB.definition.group[].valueexpression.** When present (mandatory `textmode: "true"` at both group level and UIGB top level). Parse for `{<fieldname>}` references.
- **REPORT.sortBy / sortBy2 / sortBy3.** When populated. Each is a single field reference; standard grammar.

**Brace-bracket regex parse.** `valueexpression` strings contain `{<field>}` and `{<relation>}.{<field>}` references. The validator extracts these with a regex along the lines of `\{([^{}]+)\}` and treats each match as a field reference at the surrounding object's resolution context (or at the join-target's context, when the brace chains a relation). The parse is best-effort: it does not understand `CONCAT`, `IF`, string literals containing braces, or escaping. False positives on string literals like `"{$$USER}"` are suppressed by skipping any match that begins with `$$`. The calc-language syntax itself is owned by `workfront-textmode`; the validator does not call into that skill.

**Skip categories.** The walk skips, in order: the empty-string key, control keys (`$$EXISTSMOD`, `$$OBJCODE`, `$$ID`, bare `ID` inside an EXISTS block's join slot — these are EXISTS-block control rather than field references), `_Mod` and `_Range` suffix keys (recorded but not field-resolved), session-token VALUES (`$$USER.*`, `$$TODAY*`, `$$NOW` appearing on the right side of a key/value pair — these are tenant-neutral runtime placeholders per `06-filter-patterns.md` § 4), and the `categoryID` / `viewID` / `filterID` / `groupByID` fields on the REPORT row (these are UUID references handled by the create-recipe's own UI-row-ID wiring, not field-name references).

### 3c. Normalize each reference into a 3-tuple

For each `(path, raw)` pair from 3b, produce a 3-tuple `(prefix, joinPath, baseField)`. The prefix captures `DE:`, `OR:<n>:`, and `EXISTS:<l>:` markers. The joinPath captures the chain of relation hops. The baseField is the leaf field name on the final resolution target.

Two grammars apply, depending on the source slot:

**Standard grammar (UIFT keys, UIVW `valuefield`, UIVW `aggregator.valuefield`, UIGB `valuefield`, REPORT.sortBy*, styledef `leftmethod`):**

```
[OR:<n>:][EXISTS:<letter>:][DE:][<hop>:<hop>:...]<field>[_Mod|_Range]
```

The DE: prefix sits BEFORE the join path. The `OR:<n>:` and `EXISTS:<letter>:` prefixes (when present) sit BEFORE `DE:`. The `_Mod` / `_Range` suffix is recorded separately and not part of the baseField. This matches `06-filter-patterns.md` § 7 and § 8.

**Inverted querysort grammar (UIVW `column.querysort` only):**

```
[<hop>:<hop>:...][DE:]<field>
```

The join path comes FIRST, then `DE:`, then the field name. No `OR:` or `EXISTS:` prefixes apply (querysort lives inside a column, not inside a filter). The `_Mod` / `_Range` suffix does not apply. Citation: `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json` has `"querysort": "program:DE:Promotion Number"` and `"querysort": "program:DE:Rewards Number"` — `program:` is the relation hop, `DE:` follows, then the field name. The same file's non-joined DE: columns use the simpler `"querysort": "DE:Week"` form (no join, DE: at the front).

The validator selects the grammar by source slot, not by trying both. Tests in `pre_flight_validator.py`'s suite assert this branching explicitly: a fixture with `program:DE:Foo` in a `querysort` slot must parse as `(prefix="DE", joinPath=["program"], baseField="Foo")`, and the same string in a UIFT key slot must parse as `(prefix=None, joinPath=["program", "DE"], baseField="Foo")` — which then fails resolution because `DE` is not a relation on PROJ, surfacing the slot/grammar mismatch as an error.

**Normalization table:**

| Raw key/value | Source slot | (prefix, joinPath, baseField) | Notes |
|---|---|---|---|
| `"status"` | UIFT key | `(None, [], "status")` | bare field on uiObjCode |
| `"status_Mod"` | UIFT key | `(None, [], "status")` | strip `_Mod` suffix; record op |
| `"DE:Project Tier"` | UIFT key | `("DE", [], "Project Tier")` | custom-field; needs `/parameter/search` |
| `"DE:Project Tier_Mod"` | UIFT key | `("DE", [], "Project Tier")` | DE: with `_Mod` |
| `"DE:program:Acme Field"` | UIFT key | `("DE", ["program"], "Acme Field")` | DE: with join path |
| `"OR:1:DE:Project Tier"` | UIFT key | `("OR:1+DE", [], "Project Tier")` | OR-group + DE: |
| `"EXISTS:a:assignedToID"` | UIFT key | `("EXISTS:a", [], "assignedToID")` | EXISTS block; context is block's `$$OBJCODE` |
| `"EXISTS:a:$$EXISTSMOD"` | UIFT key | CONTROL — always valid; skip | EXISTS direction control |
| `"EXISTS:a:$$OBJCODE"` | UIFT key | CONTROL — always valid; skip | provides EXISTS context |
| `"EXISTS:a:$$ID"` | UIFT key | CONTROL — always valid; skip | join key spec |
| `"EXISTS:a:ID"` | UIFT key | `("EXISTS:a", [], "ID")` | resolved against the EXISTS block's `$$OBJCODE` sub-context; bare `ID` exists on every Workfront objCode so this is almost always valid — the resolution exists for completeness and would catch a hypothetical malformed bundle |
| `"project:status_Mod"` | UIFT key | `(None, ["project"], "status")` | join 1 hop |
| `"convertedOpTaskOriginator:homeTeamID"` | UIFT key | `(None, ["convertedOpTaskOriginator"], "homeTeamID")` | join 1 hop (deep relation name) |
| `"$$USER.teamIDs"` | UIFT value | SESSION token — skip | tenant-neutral runtime |
| `"$$TODAY-30d"` | UIFT value | SESSION token — skip | session-resolved |
| `""` | UIFT key | UI-builder artifact — skip | round-trip noise |
| `"status"` | UIVW valuefield | `(None, [], "status")` | bare field |
| `"owner:name"` | UIVW valuefield | `(None, ["owner"], "name")` | join 1 hop |
| `"Week"` | UIVW valuefield | `(None, [], "Week")` | DE: dropped in valuefield (standard) |
| `"DE:Approved Hours"` | UIVW valuefield | `("DE", [], "Approved Hours")` | textmode edge case; see § 6 |
| `"DE:Week"` | UIVW querysort | `("DE", [], "Week")` | DE: kept; querysort grammar |
| `"program:DE:Promotion Number"` | UIVW querysort | `("DE", ["program"], "Promotion Number")` | INVERTED querysort grammar |
| `"DE:Duration Delta 2"` | aggregator valuefield | `("DE", [], "Duration Delta 2")` | DE: kept |
| `"sortBy: name"` | REPORT.sortBy | `(None, [], "name")` | bare field on uiObjCode |

**Default grammar for slots not listed above.** Any extraction slot not covered by the table — `styledef.leftmethod`, `image.case[].comparison.leftmethod`, `sharecol.valuefield`, `link.linkproperty[].valuefield`, aggregator `valueexpression` field refs (parsed via `{fieldname}` regex from the expression body) — uses STANDARD grammar: `[DE:][join:...]field`. The INVERTED grammar (`[join:][DE:]field`) is unique to UIVW column `querysort` and the few other slots flagged explicitly. When in doubt, parse standard first; fall back to inverted only when explicit per slot.

### 3d. Resolve each tuple

Each normalized tuple is resolved against cached metadata. The resolution rules:

- **CONTROL keys** (`$$EXISTSMOD`, `$$OBJCODE`, `$$ID`, bare `ID` in EXISTS join slot): always valid; never resolved against metadata.
- **SESSION tokens** (`$$USER.*`, `$$TODAY*`, `$$NOW`, appearing as VALUES on the right side of a key/value pair): always valid; never resolved (they are tenant-neutral runtime placeholders).
- **Plain field** (`prefix=None`, `joinPath=[]`): assert `baseField` is in cached `fields` for the current resolution context (initially the bundle's `uiObjCode`). On miss: error with Levenshtein-3 suggestions from the field list (§ 4a) and, if the (objCode, field) pair is in `SYNONYM_HINTS` (§ 4b), the hint is appended verbatim.
- **`DE:` prefix, no join** (`prefix="DE"`, `joinPath=[]`): batch the baseField into a single `/parameter/search?name=<base1>&name=<base2>&...&name_Mod=in&fields=customerID,group,objCode,parameterGroup` query (one round-trip for the whole bundle, not per-field). Match → valid. No match → error listing the custom forms (if any) on the destination that have a parameter by that name, plus a suggestion to check custom-form parity on the destination tenant.
- **Join path** (`joinPath` non-empty): walk hop by hop. For each hop `h_i`, assert that `h_i` exists as a relation on the current context's metadata `references` block. Read the relation's `targetTypeObjCode` (or the field metadata's `referencedObjectObjCode`, depending on the metadata shape — `04-runtime-schema-discovery.md` documents both forms). Set that as the new resolution context. After all hops, apply the baseField check on the final context.
- **`EXISTS:<letter>`** (`prefix` starts with `EXISTS:`): extract the EXISTS block's `$$OBJCODE` from the same bundle (looking up the sibling key `"EXISTS:<letter>:$$OBJCODE"` in `UIFT.definition`). Use that objCode as the resolution context for everything inside that block. Resolve the rest of the tuple against the EXISTS context's cached metadata (which 3a fetched if not already cached).
- **`OR:<n>:`** (`prefix` starts with `OR:`): the OR-group prefix does not change the resolution context. Inherit the same uiObjCode context as bare keys. Strip the OR prefix; resolve the remainder normally. OR-groups condition logic, not scope.
- **Decomposition of combined prefixes.** When the prefix tuple contains `+` (e.g., `"OR:1+DE"`, `"EXISTS:a+DE"`), split on `+` and apply each prefix's resolution rule in sequence. For `OR:1+DE`: first strip the OR-group context (inherits same uiObjCode as bare keys), then apply DE: parity check against the destination tenant (no metadata lookup). For `EXISTS:a+DE`: first resolve to the EXISTS block's `$$OBJCODE` sub-context, then apply DE: parity check against that sub-context.
- **`DE:` inside a join** (`prefix="DE"`, `joinPath` non-empty): resolve the join first to get the join target's objCode; then run the DE: parameter check against the join target (the destination tenant must have a custom form on the joined object's objCode with a parameter by that name).

The walk is deterministic and produces, for each tuple, exactly one of: `valid`, `error` (with reason + suggestions), or `warning` (when the validator is uncertain — e.g., URL-template parses).

### 3e. Return validation report

Output is a single JSON document on stdout:

```json
{
  "valid": false,
  "errors": [
    {
      "path": "UIFT.definition.isTemplate",
      "value": "false",
      "reason": "PROJ has no field 'isTemplate'. Templates are stored under a separate objCode (TMPL).",
      "suggestions": [
        "Drop this filter — PROJ /search never returns templates",
        "If you want to filter templates, change uiObjCode to TMPL"
      ]
    }
  ],
  "warnings": [
    {
      "path": "UIVW.definition.column[3].link.value",
      "value": "/document/view?ID={ID}&extra={someFunc(...)}",
      "reason": "Could not parse link template; field references inside may not be checked."
    }
  ]
}
```

The top-level `valid` is `true` if and only if `errors` is empty. Warnings do not affect `valid`.

`errors[].path` uses dotted-and-bracketed JSON-pointer-ish syntax (`UIVW.definition.column[2].valuefield`, `UIFT.definition.OR:1:assignedToID`) so the recipe can echo the exact location back to the consultant.

`errors[].suggestions` is always an array (possibly empty). Levenshtein-3 matches are formatted as `did you mean \`<field>\`?`. Synonym hints are appended verbatim from the `SYNONYM_HINTS` table.

`warnings[]` covers cases where the validator can't definitively check — link.value parses, valueexpression brace-references that look like literals, EXISTS blocks missing their `$$OBJCODE` control key (which is malformed but recoverable), and `_Mod`-without-paired-key or paired-key-without-`_Mod` mismatches.

## § 4. Suggestion engine

Two layers: a generic fuzzy-match against the cached field list, and a small hard-coded table of cross-objCode confusions discovered live.

### 4a. Levenshtein-3 fuzzy match

For a missing plain field, compute Levenshtein distance against every field in the current resolution context's cached `fields` list. Return up to 3 fields with distance ≤ 3, sorted ascending by distance. Format: `did you mean \`<field>\`?`.

Distance 0 doesn't happen (the resolution check already passed on exact match). Distance 1 catches the common single-typo case (`statusEqautesWith` → `statusEquatesWith`). Distance 2 catches transpositions and double-typos (`asignedToID` → `assignedToID`). Distance 3 starts to produce false positives but is empirically still useful (`compleitonDate` → `plannedCompletionDate` matches at 4, so distance 3 is the practical ceiling).

The match is case-insensitive at compare time but the suggestion preserves the canonical casing from the metadata (`assignedToID`, not `assignedtoid`). The match ignores the `_Mod` / `_Range` suffix on both sides.

### 4b. Hard-coded synonym hints

Small lookup table for known cross-objCode confusions, keyed by `(uiObjCode, missing-field)`. When the resolution fails AND the pair appears in this table, the hint is appended verbatim to the `suggestions` array, after any Levenshtein matches.

```python
SYNONYM_HINTS = {
    ("PROJ",   "isTemplate"): "Templates are a separate objCode (TMPL). Drop this filter or change uiObjCode to TMPL.",
    ("TASK",   "isTemplate"): "Template tasks are a separate objCode (TTSK). Drop this filter or change uiObjCode to TTSK.",
    ("TASK",   "isComplete"): "Use `status` enum compared with COMPLETE state (e.g. `status_Mod=in` with value `CPL`).",
    ("PROJ",   "isComplete"): "Use `status` enum compared with COMPLETE state.",
    ("USER",   "isPrimary"):  "USER doesn't track that flag; check ROLE or TEAM membership instead.",
    ("OPTASK", "isComplete"): "Use `statusEquatesWith` compared with COMPLETE state.",
}
```

The PROJ-vs-TMPL pair is the most important entry; it's the error that motivated the validator in the first place (live test, 2026-05-13 — see § 1). The TASK-vs-TTSK pair is its sibling: template tasks live under `TTSK`, not under `TASK` with an `isTemplate=true` flag. The `isComplete` entries cover the common consultant assumption that Workfront has a boolean completion field; in reality, completion is encoded in the `status` enum (literal status code, varies per tenant) plus `statusEquatesWith` (canonical equivalence state, stable across tenants — `06-filter-patterns.md` § 10 documents the choice).

The table is extensible. v0.9.0 ships with the six entries above. When a consultant hits a "no field X" error without a useful suggestion, the follow-up is a one-line PR to add an entry — file under `docs/roadmap.md` if it's not immediately actionable.

### 4c. DE: form-context suggestion

When a `DE:` parity check returns zero matches on the destination tenant, the suggestion lists which custom forms exist on the destination that have a parameter (parameter = the custom-field configuration row) so the consultant can manually add the missing parameter to the right form. The suggestion text looks like:

```
DE:Approved Hours not found on destination. Custom forms on PROJ with parameters: "Project Intake" (12 params), "Asset PVA" (4 params), "Promo Brief" (6 params). Add the parameter to whichever form is intended.
```

The form list comes from a single `/customform/search?objCode=<uiObjCode>&fields=name,parameters:ID` GET, made only when at least one DE: parity check fails. If every DE: reference resolves, the validator skips this query entirely.

### 4d. PSEUDO_FIELDS allowlist

A small hard-coded table of runtime-real fields that are absent from `/<obj>/metadata`. Mirrors `SYNONYM_HINTS` (§ 4b) but for the opposite class of issue: the field exists; metadata just doesn't list it. Each entry constrains the field to specific slots.

```python
PSEUDO_FIELDS = {
    ("OPTASK", "statusEquatesWith"): {
        "slots": ["uift.definition"],
        "reason": "Query-time pseudo-field for state-equivalence comparison.",
    },
    ("OPTASK", "assignmentsListString"): {
        "slots": ["uivw.column.valuefield"],
        "reason": "Tile data source for component.assignmentslist.",
    },
    ("TASK", "assignmentsListString"): {
        "slots": ["uivw.column.valuefield"],
        "reason": "Same as OPTASK — tile data source.",
    },
}
```

Slot constraint matters: `statusEquatesWith` is valid in UIFT keys but NOT in UIVW column valuefield. The validator emits a "wrong slot" error in the latter case rather than silently accepting.

The per-tenant whitelist at `~/.cache/wf-claude-toolkit/reports-pseudo-fields-<host-hash>.json` overlays this global table — see `09-verification-flow.md` for the auto-capture flow that populates it from `--force` writes.

## § 5. Performance and blast radius

Pre-flight is sub-second on typical bundles. Bundle size in practice is 10–30 field references against cached metadata, all resolved in-memory.

- **`/parameter/search` calls are batched.** One query with multiple OR-prefixed `name=` clauses covers every `DE:` reference in the bundle. The query is skipped entirely when the bundle has no `DE:` references.
- **`/customform/search` is conditional.** Only fired when at least one DE: parameter check fails, and the response is used to enrich suggestions, not to gate validity.
- **Schema-cache hit path: zero network calls** beyond the (conditional) DE: parity probe. Schema reads come from `~/.cache/wf-claude-toolkit/reports-schema-<host-hash>.json`.
- **Schema-cache miss path: one `/<objCode>/metadata` GET per missing objCode.** Handled by `schema_cache.fetch_and_put`. EXISTS blocks may cause additional misses (one per distinct `$$OBJCODE`), but in practice every EXISTS objCode (`TASK`, `OPTASK`, `DOCU`, `HOUR`, `PRFAPL`) is part of the standard 4-call burst that `04-runtime-schema-discovery.md` documents, so the cache is usually warm.

The validator does not parallelize anything; it's already fast enough on cached data, and the conditional API calls are at most one or two round-trips. The cost ceiling is bounded by `O(N)` in number of field references and `O(1)` in network round-trips when the cache is warm.

The blast radius of a wrong pre-flight result is limited. A false positive (validator says invalid when the field actually exists) costs the consultant a round of clarification — the recipe prints the error and asks to revise; the consultant can type `force` to override (see § 7 CLI flags). A false negative (validator says valid when the field doesn't exist) lets a broken report POST through — the same outcome as no pre-flight at all, so this case is no worse than the v0.8.0 baseline. The validator's job is to convert as many false negatives as possible into true positives, not to be exhaustive.

## § 6. Limitations

- **Best-effort, not a guarantee.** The validator's coverage of join paths is limited to what's expressed in the cached `/metadata` response. Workfront's relation-hop limit is undocumented; a deeply nested join might pass pre-flight (all hops resolve in metadata) but fail at POST or at render. The validator does not enforce a static hop depth — it defers to the metadata.
- **Hard-coded synonym hints are curated, not exhaustive.** If a consultant hits a "no field X" error without a useful suggestion, file a `docs/roadmap.md` follow-up to extend `SYNONYM_HINTS`. The validator does not learn from the consultant's session.
- **DE: parity assumes the schema cache is populated.** On a fresh destination tenant (first session, no cache), pre-flight runs the 4-call burst first (per `04-runtime-schema-discovery.md`). If `/customform/search` is unavailable (the consultant's API key lacks the permission), the DE: form-context suggestion (§ 4c) is suppressed and the validator falls back to the generic "DE:`<name>` not found on destination — add the parameter to the right custom form" reason without the form list.
- **Calc-language semantics inside `valueexpression` are not validated.** The validator extracts `{<field>}` references via regex and resolves those as ordinary field references, but it does not parse `CONCAT`, `IF`, `CASE`, `ROUND`, `SUB`, `ISBLANK`, `STRING`, or any other calc function. Syntax errors inside `valueexpression` strings are surfaced as warnings (the regex either fails or produces nonsensical "fields" that don't resolve), but the validator does not assert calc-function arity or argument types. That validation, if it's ever needed, lives in `workfront-textmode`.
- **Matrix reports** (`REPORT.reportType: "M"`) are unverified by the empirical survey. Pre-flight passes them as-is.
- **`textmode:"true"` columns without `valueexpression`.** A column that opts into Text Mode but doesn't supply a `valueexpression` may KEEP the `DE:` prefix in `valuefield` rather than dropping it (the standard rule). Empirical: `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json` has a `"textmode": "true"` column with `"valuefield": "DE:Week"` — the `DE:` is kept, not dropped. The validator accepts BOTH forms (`DE:` kept AND `DE:` dropped) when the column has `textmode: "true"` and no `valueexpression`. In all other column slots, only the standard form (DE: dropped in `valuefield`, kept in `querysort` and `aggregator.valuefield`) is accepted.
- **The 4-call sequence's POST ordering** is not pre-flight's concern. Validation runs against the composed bundle as a single object; the recipe's POST sequencing (UIFT → UIGB → UIVW → REPORT) is enforced in Phase F.
- **Live URL fetches inside `link.value`.** The validator does not follow URLs or assert that an in-app URL actually resolves. The `linkproperty` array's field references are validated; the `value` URL template is parsed best-effort and emitted as a warning when the parse is ambiguous.

## § 7. CLI

```bash
# WF_HOST / WF_API_KEY exported first, e.g. via
# `set -a; source ~/wf-envs/<slug>/.env; set +a`
python3 skills/workfront-reports/scripts/pre_flight_validator.py \
    --from-stdin \
    < bundle.json
```

Credentials come from the environment: the validator reads `WF_HOST` and `WF_API_KEY` when the corresponding flags are omitted, keeping the API key out of the process argv (argv is visible in `ps` — the toolkit's no-key-in-argv rule).

Flags:

- `--from-stdin` (required): read the JSON bundle from stdin. The bundle is the in-memory document the recipe composed at Phase C — a single JSON object with top-level keys `uift` (optional — empty `definition:{}` when no filter), `uigb` (optional — omitted when no grouping), `uivw`, `report` matching the pieces the recipe will POST. (Keys are lowercase, matching both recipes' compose phase and the `pre_flight_validator.py` `bundle.get("uift")` lookup.)
- `--host` (optional when `WF_HOST` is exported): destination tenant host (e.g., `acme.my.workfront.com`); falls back to the `WF_HOST` env var. Used to look up the right schema-cache file. Usage error (exit 2) when neither the flag nor the env var is set.
- `--api-key <key>` (optional, backward compat only): prefer exporting `WF_API_KEY` — a key passed as a flag lands in the process argv, visible in `ps`. The key is only consulted at all when the validator needs to run the DE: parity probe (or fetch metadata on a cold cache); the recipe normally pre-populates the cache first, so it's usually unused either way.
- `--force` (optional): set `valid:true` in the output regardless of errors; errors are downgraded to warnings with `forced:true`. The recipe surfaces this as a consultant override after a clarifying conversation. Use sparingly — `--force` exists for the edge case where the consultant knows something the validator doesn't (e.g., a tenant with a non-standard custom form not visible to `/customform/search`).
- `--learn` (optional): take `uiObjCode:fieldname[:slot]` plus `--host` and record the field into the per-tenant whitelist at `~/.cache/wf-claude-toolkit/reports-pseudo-fields-<host-hash>.json`. The next pre-flight run on the same host accepts the field without `--force`. Used for one-off consultant-confirmed pseudo-fields the global PSEUDO_FIELDS table doesn't know about.
- `--learn-from-blocked` (optional): convenience form of `--learn` that reads the most recent blocked references from the prior session's pre-flight report and prompts the consultant to confirm each one for whitelist capture. Avoids re-typing the `uiObjCode:fieldname` tuple.
- `--learn-objcode <code>` (optional, paired with `--learn`): specify the uiObjCode for the field being learned when it can't be inferred from the host's last bundle.
- `--forget <uiObjCode:fieldname>` (optional): remove a single entry from the per-tenant whitelist. The opposite of `--learn`.
- `--forget-all` (optional): clear the entire per-tenant whitelist for `--host`. Used when migrating to a new schema or when the auto-captured entries have drifted.
- `--whitelist-dir <path>` (optional): override the default whitelist cache directory (`~/.cache/wf-claude-toolkit/`). Used in tests; consultants normally leave this unset.

Output:

- **stdout**: the validation report JSON (§ 3e), pretty-printed.
- **stderr**: progress and timing lines (one per phase), useful when running interactively. Empty on success when called by the recipe.

Exit codes:

- `0` — `valid: true` (no errors; warnings may be present).
- `1` — `valid: false` (one or more errors).
- `2` — usage error (missing required flag, malformed stdin, schema-fetch failure).

The recipe distinguishes 1 from 2: a 1 returns to Phase B (the consultant edits the composition); a 2 stops the run and surfaces the error verbatim.

## § 8. Integration in SKILL.md

The runtime flow invokes the script between Phase C (compose) and Phase E (apply gate). The recipe's bash glue:

```bash
python3 skills/workfront-reports/scripts/pre_flight_validator.py \
    --from-stdin --host "$HOST" \
    < /tmp/bundle.json \
    > /tmp/preflight.json

if jq -e '.valid' /tmp/preflight.json > /dev/null; then
    echo "Pre-flight: clean"
    # proceed to E. apply gate
else
    echo "Pre-flight: errors"
    jq -r '.errors[] | "- " + .path + ": " + .reason + "\n  " + (.suggestions | join("\n  "))' /tmp/preflight.json
    # consultant types `edit` to revise, `apply` to override (requires --force)
fi
```

The skill's `SKILL.md` describes this insertion at the Phase C/E boundary. The four-call write sequence section (which `00-rubric-and-workflow.md` documents) is unchanged by pre-flight — the POSTs still go UIFT → UIGB → UIVW → REPORT in Phase F; pre-flight just runs before the gate that authorizes them.

The Claude.ai recipe parallels the same shape: compose → pre-flight → apply → write. On the Claude.ai surface (no shell), the validator's JSON output is rendered inline and the consultant types `edit` or `apply` directly into the conversation.

## § 9. Cross-references

- The schema cache and the 4-call burst → `04-runtime-schema-discovery.md`.
- What field references look like in filter keys (UIFT) → `06-filter-patterns.md` § 1–§ 8.
- What field references look like in view columns and group entries (UIVW / UIGB) → `07-view-patterns.md` § 2, § 5, § 6, § 12.
- The `DE:` prefix asymmetry across UIFT keys, UIVW `valuefield`, UIVW `querysort`, UIVW `aggregator.valuefield`, UIGB `valuefield`, plus the `textmode:"true"` edge case → `07-view-patterns.md` § 14 (and the brief preview in `06-filter-patterns.md` § 6).
- The inverted querysort grammar (`[<join>:][DE:]<field>` instead of `[DE:][<join>:]<field>`) the validator must parse separately → `07-view-patterns.md` § 14 "Inverted grammar in querysort" with citation `client-a-sample/PROJ-planning-grid-NOFILTER-uivw.json`.
- The recipe's Phase D integration point → `02-create-from-scratch-recipe.md` § Phase D (and the parallel slot in the modify flow).
- The clone-flow integration — pre-flight runs after the sanitizer rewrites tenant-specific IDs and dates → `03-clone-and-adapt-recipe.md` Phase 5–Phase 6.
- The PROJ-vs-TMPL gotcha that motivated this validator → `05-gotchas.md` (and the live-error log from 2026-05-13 documented in § 1 above).
- The four-call write-sequence rubric (UIFT → UIGB → UIVW → REPORT, plus the 2/3/4-call variants by intent) → `00-rubric-and-workflow.md`.
- The script implementing the algorithm → `skills/workfront-reports/scripts/pre_flight_validator.py` (Task 10 of v0.9.0).
- The text-mode authoring surface that owns `valueexpression`'s calc-language syntax (which the validator does not parse) → `workfront-textmode`.
- Auth headers and host resolution for the conditional `/parameter/search` and `/customform/search` calls → `workfront-api`.
