# 04 — Views and Groupings

## View column structure

Each column in a view is indexed starting at 0. All directives for one column share the same index.

### Minimal column
```
column.0.valuefield=name
column.0.displayname=Project Name
column.0.textmode=true
```

### Full column with all common directives
```
column.0.valuefield=project:owner:name
column.0.valueformat=HTML
column.0.displayname=Project Owner
column.0.linkedname=direct
column.0.width=150
column.0.stretch=0
column.0.textmode=true
```

## Calculated column with `valueexpression`

```
column.0.valueexpression=CONCAT({owner}.{firstName}," ",{owner}.{lastName})
column.0.valueformat=HTML
column.0.displayname=Owner Full Name
column.0.textmode=true
```

## Three-object-deep references (views only)

Views allow up to 3 object hops. Filters and groupings only allow 2.

### Valid in views
```
column.0.valuefield=project:portfolio:program:name
```

### Equivalent in valueexpression
```
column.0.valueexpression={project}.{portfolio}.{program}.{name}
```

## Less common column attributes

- `column.N.width=0` (or omitting `width=` entirely) **hides the column.** Useful when a column's value is needed for sorting or conditional formatting but should not display. Source: Adobe `text-mode/edit-text-mode-in-view`.
- `column.N.makeFieldEditable=true|false` enables inline editing on list reports. The column has to be a writable scalar (not a `valueexpression`, not a join). Source: Adobe `text-mode/edit-text-mode-in-view`.
- `column.N.link.valuefield=ID&column.N.link.valueformat=string` — when adding a click-through link via `link.*` directives, **both `link.valuefield` and `link.valueformat` must be set.** Omitting `link.valueformat` causes the link to render as a literal value. Source: Adobe `text-mode/edit-text-mode-in-view`.
- `group.N.iscollapsed=true|false` (default `false`) controls whether the grouping renders collapsed by default. Source: Adobe `text-mode/edit-text-mode-in-grouping`.

## Sorting and column widths

```
querysort=project:plannedCompletionDate
sortType=asc
usewidths=true
```

- `querysort` — field to sort by
- `sortType` — `asc` or `desc`
- `usewidths=true` — enforces the `column.N.width` values you set

## Custom links

```
column.0.valueexpression={name}
column.0.valueformat=HTML
column.0.link.url=/project/view?ID={ID}
column.0.link.linkProperty.0.name=ID
column.0.link.linkProperty.0.value={ID}
column.0.textmode=true
```

For standard "click the value to open the record" behavior, just use `column.0.linkedname=direct` instead.

## Groupings

Groupings use `group.N` instead of `column.N`. Same structure otherwise.

### Group by status
```
group.0.valuefield=status
group.0.valueformat=HTML
group.0.linkedname=direct
```

### Group by calculated value
```
group.0.valueexpression=IF(DATEDIFF({plannedCompletionDate},$$TODAY)<0,"Overdue","On Track")
group.0.valueformat=HTML
```

### Nested groupings (two levels)
```
group.0.valuefield=portfolio:name
group.0.valueformat=HTML
group.0.linkedname=direct

group.1.valuefield=program:name
group.1.valueformat=HTML
group.1.linkedname=direct
```

**Limit:** groupings can only reference 2 objects deep. To group by something 3 hops away, build a calculated custom field on the closer object and group on that.

**Grouping count cap: 3 for standard reports, 4 for matrix reports.** Standard list reports support up to 3 levels of grouping. Matrix reports (`reportType: "M"` per `knowledge/reports/01-report-object-shape.md`) support up to 4 levels. Adobe's `text-mode/edit-text-mode-in-grouping` page incorrectly states "max 4" without the split; the canonical source is `report-elements/groupings-overview`. The 4th level on matrix reports MUST be authored in text mode — the builder UI doesn't expose it. Source: Adobe `report-elements/groupings-overview`.

**Groupings can't be sorted directly.** The UI offers no "sort by this grouping" control. To order grouped buckets, mirror the grouping field in a view column and set that column's `querysort=<field>` — the report's row-level sort then determines bucket order. The sort-index prefix pattern in `knowledge/reports/07-view-patterns.md` § 12 ("01: 0% to 10%", "02: 11% to 20%") is the workaround for calculated-grouping range buckets where direct field mirroring isn't an option. Source: Adobe `report-elements/groupings-overview`.

**Cannot group by multi-select custom fields or multi-value built-in fields (e.g., Resource Manager).** The grouping engine requires a scalar bucket key; multi-value fields don't have one. Workaround: derive a scalar key with a calculated custom field (concatenate the values, or pick a representative) and group on the calculated field. Source: Adobe `report-elements/groupings-overview`.

**Parent/child aggregation rules.** When a task report includes a column with an aggregator AND the report contains both parent and child tasks, different field types aggregate differently:

| Field type | Aggregates over |
|---|---|
| Number / Currency / Date custom fields | Children + standalone tasks (NOT parents — parents show the rollup) |
| `actualHours` (built-in) | Main-parent tasks + standalone (NOT children — they roll up to their parent) |
| Custom data fields (calc fields on custom forms) | Everything — parents, children, standalone |

The mismatch between `actualHours` (parent-rollup) and Number-custom-field (children-only) trips admins regularly. To get a uniform rollup, wrap the source value in a calculated custom field. Source: Adobe `report-elements/groupings-overview`.

## Aggregators

Aggregators sit at the bottom of a grouping (subtotals). They are NOT indexed by column — they apply to the column they're declared on.

```
column.0.valuefield=actualWorkRequired
column.0.aggregator.function=SUM
column.0.aggregator.displayformat=minutesAsHoursString
column.0.aggregator.valueformat=HTML
column.0.displayname=Actual Hours
column.0.textmode=true
```

### Aggregator functions
- `SUM`
- `AVG`
- `MAX`
- `MIN`
- `COUNT`

### Aggregator with valueexpression
```
column.0.valueexpression=DATEDIFF({plannedCompletionDate},{actualCompletionDate})
column.0.aggregator.function=AVG
column.0.aggregator.valueformat=HTML
column.0.aggregator.valueexpression=DATEDIFF({plannedCompletionDate},{actualCompletionDate})
column.0.displayname=Avg Days Late
column.0.textmode=true
```

## Full `valueformat` token catalogue

Adobe documents a closed enumeration of valid `column.N.valueformat=` tokens. The empirically-verified tokens, grouped by underlying data type:

**Strings:** `HTML` · `string`

**Dates** (US-locale rendering shown; tenants on other locales see locale-appropriate formats):

| Token | Renders as |
|---|---|
| `atDate` | "1/5/26 9:30 AM" (default — locale-shortest with time) |
| `shortAtDate` | "1/5/26" |
| `mediumAtDate` | "Jan 5, 2026" |
| `longAtDate` | "January 5, 2026" |
| `fullAtDate` | "Monday, January 5, 2026" |
| `partialAtDate` | "Jan 5" (no year — useful for compact recurring-event reports) |

**Numbers:**

| Token | Behavior |
|---|---|
| `int` | Integer; no decimal places |
| `doubleAsInt` | Double rounded to integer for display |
| `doubleAsDouble` | Double with locale-default decimals |
| `doubleAsString` | Double rendered as string verbatim |
| `currencyStringCurrency` | "$1,234.56" (tenant's currency symbol + 2 decimals) |
| `currencyStringCurrencyRounded` | "$1,235" (rounded, no decimals) |
| `doubleAsPercent` | "12.50%" (multiplied by 100, 2 decimals) |
| `doubleAsPercentRounded` | "13%" |
| `doubleAsFinancial` | "(1,234.56)" for negatives (parens, no minus) |
| `doubleAsFinancialRounded` | "(1,235)" for negatives |

**Enum:** `val` (renders the enum's display label, not the storage key).

**Aggregator-specific:** `minutesAsHoursString` (renders stored minutes as "Nh Nm").

The Workfront enumeration may contain additional locale-specific or experimental tokens; this table covers every token observed in the 40-bundle empirical survey plus every token documented by Adobe. Source: Adobe `text-mode/format-dates-in-text-mode-reports`, Adobe `text-mode/format-numbers-in-text-mode-reports`. Snapshot date: 2026-05-14.

## Tips

- **Calculated views vs custom fields:** values in a `valueexpression` column are recalculated every time the report runs (dynamic but slower). Calculated custom fields are stored in the database (faster, persistent, can be filtered/conditionally formatted).
- **Use Assignment reports, not Task reports, when you need one row per assignee.** A task with three assignees shows up as one row in a task report but three rows in an assignment report.
- **Alternating row colors are not supported in text mode views.** Don't waste time trying.
