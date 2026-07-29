# 08 — Calculated Fields vs. Text-Mode Columns vs. API Computations

## Decision Matrix

| Criterion | Calculated Custom Field | valueexpression Column (Text Mode) | API/Fusion Computation |
|---|---|---|---|
| **Stored on record** | Yes — persists as a field value | No — computed at report render only | Yes (if written back via PUT) |
| **Survives outside reports** | Yes — visible on forms, object detail | No — only in the report it's defined in | Yes (if stored in a field) |
| **Real-time / always fresh** | No — recalcs on triggers only | Yes — computed every time the report runs | Depends on schedule/trigger |
| **$$TODAY accuracy** | Risky — goes stale; also UTC | Always current; also UTC | Always current |
| **Groupable / chartable** | Yes (Number/Currency formats) | Not directly — can't group on valueexpression | Depends |
| **Filterable in reports** | Yes — `valuefield=DE:Field Name` | No — valueexpression columns cannot be filtered | Depends on stored field |
| **Conditional formatting in UI** | Yes — native UI formatting on field | No — valueexpression blocks cond format | N/A |
| **Cross-object aggregation** | No — can't reach child collections | No — same limitation | Yes — Fusion can aggregate |
| **Setup location** | Custom Forms (Setup) | Report column text mode | External or Fusion |
| **No-code friendly** | Mostly yes | Yes (with text mode knowledge) | No — requires dev/admin |

## When to Use a Calculated Custom Field

Use a calculated field when you need the computed value to:

1. **Persist on the record** — so it's visible on the object's custom form view, searchable, and available outside reports.
2. **Drive grouping or charting** — report groupings and charts require a stored value; they cannot aggregate a `valueexpression`.
3. **Feed a report filter** — `valuefield=DE:Field Name` in a text-mode filter references a stored calc field value; you cannot filter on a `valueexpression` column.
4. **Support conditional formatting in the object view** — native conditional formatting on a field in a custom form view requires the value to be stored.
5. **Be referenced by other fields** — another calc field can reference `{DE:Your Calc Field}`.

**Good fits:** status labels, risk scores, budget variance, overdue flags, concatenated summaries, cross-object lookups (client name, region, project tier on a task form).

## When to Use a valueexpression Column in Text Mode

Use a `valueexpression` column when:

1. **You need always-current date math** — `DATEDIFF({plannedCompletionDate},$$TODAY)` in a valueexpression always reflects today; in a calc field, it's only accurate when the field was last recalculated.
2. **The value only needs to exist in a report** — there's no reason to store it on the object.
3. **You want to avoid the format-is-permanent constraint** — report columns can be changed at any time.
4. **You need $$USER.ID / $$USER.name context** — these wildcards work in valueexpression and reflect the logged-in user at render time. Calculated fields do not have access to the viewing user's context.

**Good fits:** days-remaining countdown columns, logged-in-user comparisons, report-specific display formatting, columns you'll use in conditional formatting (with the workaround that the underlying value comes from a stored calc field).

> **Key interaction:** A common pattern is to build a calculated field that stores a computed value, then reference it in a text-mode `valuefield=DE:Field Name` column so conditional formatting can be applied to it in the report.

## When to Use an API / Fusion Computation

Use Fusion (or direct API) when:

1. **You need to aggregate child records** — sum task hours onto a project, count issues per project, etc. Calc fields cannot reach collections; Fusion can.
2. **You need cross-instance or cross-system data** — fetching data from another Workfront instance, Salesforce, Jira, etc.
3. **You need real-time freshness on a stored field** — trigger a Fusion scenario on object-change events to keep the field current.
4. **You need complex logic that exceeds expression length or nesting limits** — Fusion handles arbitrarily complex logic.
5. **You need to write to multiple fields at once** — a single Fusion module can update many fields atomically.

**Cost:** Fusion requires a license and technical setup. Calc fields are free within Workfront administration.

## Quick Decision Guide

```
Does the value need to persist on the record?
  No → valueexpression column in text mode
  Yes →
    Does it require aggregation across child records?
      Yes → API / Fusion writes to a stored field
      No →
        Is always-current date math critical (e.g., "days overdue" refreshed daily)?
          Yes → Consider valueexpression column, or accept Fusion for daily recalc
          No → Calculated custom field
```

## Syntax Reference at a Glance

| Context | Field reference syntax | Date wildcard | Object traversal |
|---|---|---|---|
| Calc field | `{fieldName}` or `{DE:Field Name}` | `$$TODAY`, `$$NOW` (UTC, stale) | `{project}.{fieldName}` |
| valueexpression | `{fieldName}` or `{DE:Field Name}` | `$$TODAY`, `$$TODAY+7d` | `{project}.{fieldName}` |
| valuefield | `fieldName` (no braces, colon-separated) | Not supported | `project:fieldName` |
| API filter | camelCase field name | `$$TODAY`, `$$USER.ID` | Flat namespace for most /search |
