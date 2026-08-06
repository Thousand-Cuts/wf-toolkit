# 01 — Syntax Fundamentals

## `valuefield` vs `valueexpression`

These are the two ways to pull data into a text mode column, grouping, or filter. They are NOT interchangeable.

| | `valuefield` | `valueexpression` |
|---|---|---|
| Separator | Colon (`:`) | Period (`.`) inside curly braces |
| Use case | Direct database field reference | Calculations, concatenations, conditionals |
| Wildcards | NOT supported | Supported (`$$TODAY`, `$$USER.ID`, etc.) |
| Case | Match DB exactly | camelCase |
| Example | `column.0.valuefield=project:name` | `column.0.valueexpression={project}.{name}` |

**Rule of thumb:** if all you need is a field value, use `valuefield`. If you need to calculate, concatenate, conditionalize, or use a wildcard, use `valueexpression`.

**Not every API-reportable field is text-mode-reachable.** Some fields appear in the API Explorer and respond to `/search` queries but render blank when used as a `valuefield` in a UIVW column. The class is small and usually involves computed or runtime-only fields (some workflow state internals, some scorecard-derived rollups). The fix is empirical: try the field; if the column renders blank, route through a `valueexpression` with `STRING(<field>)` or a calculated custom field instead. Source: Adobe `text-mode/understand-text-mode`.

## Object depth

- **Views** can reference up to **3 objects deep** (e.g., `task:project:portfolio:name`)
- **Filters, groupings, AND custom prompts** can only reference **2 objects deep**
- To bypass the 2-level limit on filters, use `EXISTS` statements (see file 06)
- A filter (across all its `EXISTS` blocks plus join hops) can reference at most **5 objects beyond the report object itself** — Adobe's stated engine cap. See `03-filters-and-modifiers.md` for the failure mode beyond 5.

Source: Adobe `text-mode-syntax-overview`, Adobe `report-elements/filters-overview`.

## Value formats

### Default
- `HTML` — default for `valueexpression`, renders HTML in the value (but see combined columns caveat)

### Date formats
- `atDate` — full date with time
- `longAtDate` — long format
- `shortAtDate` — short format (MM/DD/YYYY)
- `mediumAtDate` — medium format
- `partialAtDate` — partial
- `fullAtDate` — fully spelled out

### Number formats
- `doubleAsString`
- `doubleAsInt`
- `doubleAsDouble`
- `doubleAsPercent`
- `doubleAsPercentRounded`
- `currencyStringCurrency`
- `currencyStringCurrencyRounded`

### Duration
- `minutesAsHoursString` — converts minutes to "Xh Ym" format (useful for aggregators)

## Custom field references

Custom fields (Data Extensions) require special syntax:

```
# In valuefield — colon-separated path
column.0.valuefield=project:DE:Field Name

# In valueexpression — dotted-brace traversal (NEVER colon inside braces)
column.0.valueexpression={DE:Field Name}                         # same-object
column.0.valueexpression={project}.{DE:Field Name}               # cross-object
column.0.valueexpression={lastNote}.{noteText}                   # built-in field on a parent
```

### Important: traversal syntax differs between `valuefield` and `valueexpression`

| Where | Syntax | Example |
|---|---|---|
| `valuefield` | colon path | `lastNote:noteText` |
| `valueexpression` braces | **dotted-brace traversal** | `{lastNote}.{noteText}` |

**`{lastNote:noteText}` inside a valueexpression renders BLANK at runtime** — the report PUT succeeds with no validation error, but every row's cell comes back empty. Confirmed empirically against client-d sandbox 2026-05-26 (a `Latest Update` column on 24 reports was authored with the colon path inside braces; all rendered blank until rewritten with `{lastNote}.{noteText}`). The textmode and calc-field expression engines share this rule — colon-inside-braces is silently rejected wherever it appears (`{project:name}`, `{program:DE:Field}`, `{lastNote:noteText}` all fail the same way).

### DE: name vs. label

`DE:` lookups inside `{...}` use the source parameter's internal **`name`**, NOT its UI **`label`**. When the two differ (someone relabeled the field via the UI but the underlying `name` is unchanged), only the `name` resolves; the label is silently rejected as "is not a field in your system." Verify by `GET /attask/api/v17.0/parameter/<paramID>?fields=name,label`. See `calculated-fields/05-cross-object-references.md` for the empirical examples and the matching rule in calc-fields.

Field names must match the parameter's internal `name` exactly, including spaces, capitalization, and any punctuation (hyphens / slashes / etc. are fine in `name`). There is no escaping.

## Wildcards

Wildcards work in `valueexpression` and filter values, but NOT in `valuefield`. For the complete enumeration plus the formal arithmetic grammar, see `09-tips-and-gotchas.md` § Wildcard reference. Quick-reference of the most common:

| Wildcard | Returns |
|---|---|
| `$$TODAY` | Today at midnight, tenant timezone |
| `$$NOW` | Current timestamp (sub-day precision; unsupported in Resource Planner) |
| `$$USER.ID` | Rendering user's UUID |
| `$$USER.name` | Rendering user's full name (text-mode only) |
| `$$USER.homeGroupID` | Rendering user's home group UUID |
| `$$USER.teamIDs` | TAB-separated list of every team UUID the user is on |
| `$$USER.roleIDs` | TAB-separated list of every role UUID the user holds |
| `$$OBJCODE` | The current object's objCode (`PROJ`, `TASK`, etc.) |

Date math: `$$TODAY+7d`, `$$TODAY-1m`, `$$TODAY+1y`, `$$TODAYbm` (begin of month), `$$TODAYey-1` (end of last year), `$$TODAYbq+1` (begin of next quarter). Formal grammar in `09-tips-and-gotchas.md` § Wildcard reference.

Source: Adobe `report-elements/understand-wildcard-filter-variables`.

## Common directives

**Note on `textmode=true`:** When you edit a column in the in-product Text Mode tab and save, Workfront auto-injects `column.N.textmode=true` on every column you touched. It's a marker the system uses to know which columns to re-parse on next render — not something the author must set manually. When authoring from scratch in this file's snippets, set it explicitly; on round-trips, expect every touched column to carry it.

### Column-level
```
column.0.valuefield=...
column.0.valueexpression=...
column.0.valueformat=...
column.0.displayname=...        # Header text
column.0.linkedname=direct      # Makes the value a clickable link
column.0.namekey=...            # Localization key
column.0.width=120              # Column width in pixels
column.0.stretch=0              # 0=no stretch, 1=stretch
column.0.link.url=...           # Custom URL for the link
column.0.textmode=true          # Required when building from scratch
```

### Grouping-level
```
group.0.valuefield=...
group.0.valueexpression=...
group.0.valueformat=...
group.0.linkedname=...
```

### Aggregators
```
aggregator.function=SUM          # or AVG, MAX, MIN, COUNT
aggregator.valueformat=...
aggregator.valueexpression=...
aggregator.displayformat=minutesAsHoursString
```
