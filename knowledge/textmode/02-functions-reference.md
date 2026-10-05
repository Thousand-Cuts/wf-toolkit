# 02 — Functions Reference

All functions are used inside `valueexpression`. They are case-sensitive (uppercase).

## Operators

Use these operators directly inside `valueexpression` and calculated custom field expressions.

| Operator | Meaning | Notes |
|---|---|---|
| `&&` | AND | Combine conditions |
| `\|\|` | OR | Combine conditions |
| `!` | NOT | Negate a condition or expression |
| `==` | Equal | String/number equality test |
| `!=` | Not equal | Preferred over wrapping in `!()` for simple comparisons |

**Never use `NOT(...)`** — always use `!(...)`.
**Never use `NOTBLANK(...)`** — always use `!ISBLANK(...)`.

| Wrong | Right |
|---|---|
| `NOT({status}="ONH")` | `!({status}="ONH")` |
| `NOTBLANK({DE:Field})` | `!ISBLANK({DE:Field})` |

Examples:

```
column.0.valueexpression=IF(!ISBLANK({DE:Field}),"Has value","Blank")
column.0.valueexpression=IF({status}!="CPL","Incomplete","Complete")
column.0.valueexpression=IF(!({status}="ONH"),"Active","On Hold")
```

> **`DATEDIFF` and `WEEKDAYDIFF` take their arguments in OPPOSITE orders.**
> `DATEDIFF(a,b)` returns `a - b`; `WEEKDAYDIFF(a,b)` returns `b - a`. Swapping
> one for the other in place, keeping the argument order, silently inverts the
> sign. Nothing errors and the column still renders numbers, so the mistake
> survives review — especially where the expression also clamps negatives to
> zero, which turns every genuinely late row into `0` and leaves only the early
> rows showing a value. Verified against a rendered report on a client tenant,
> 2026-09-02.
>
> A calculated column's sign is only confirmed by reading it out of the
> RENDERED report. Offline arithmetic over the raw dates re-checks your own
> assumption, not Workfront's behaviour, and an API round-trip proves storage,
> not semantics.

> **`$$TODAY` inside a `valueexpression` is the UTC date, not the viewer's.**
> At 8:39 PM EDT on 2026-09-29, `DATEDIFF(CLEARTIME(<a 2026-09-30 date>),$$TODAY)`
> rendered `0`, and all 8 date-relative buckets on the report matched
> independently computed counts only with "today" = 2026-09-30. So every
> `$$TODAY`-relative column or grouping rolls over to tomorrow in the US
> evening: 8 PM EDT, 5 PM PDT. Verified on a client prod tenant 2026-09-29,
> rendered report. The filter-side `$$TODAY` was not tested. Detail and
> mitigations: `09-tips-and-gotchas.md` § "`$$TODAY` in a valueexpression is
> the UTC date".

### Verified behaviour on a rendered report

Each of these rendered, on PROJ and TASK reports, values matching ones
computed independently from the raw data (client prod tenant 2026-09-29,
rendered report):

| Expression | Behaviour |
|---|---|
| `CLEARTIME({plannedCompletionDate})` | Drops the time of day; use it on both sides of a date comparison. |
| `DATEDIFF(CLEARTIME(a),CLEARTIME(b))` | `a` minus `b` in whole calendar days. |
| `WEEKDAYDIFF(a,b)` | `b` minus `a` in weekdays. Weekends are excluded; **company holidays are not** (it matched `numpy.busday_count(a,b)` with no holiday list). |
| `DIV({durationMinutes},480)` | Work minutes to days: 480 minutes is one 8-hour day. |
| `{defaultBaseline}.{plannedCompletionDate}` | The baseline's planned completion, on a PROJ report. |
| `{template}.{durationMinutes}` | The source template's duration, on a PROJ report. |
| `{templateTask}.{durationMinutes}` | The source template task's duration, on a TASK report. |
| `ISBLANK({templateTaskID})` | True for tasks added by hand rather than from the template. |
| Nested `IF(...,"label",IF(...,"label",...))` | String results render as text, at any depth used here. |

A template-based SLA for a task, in days: `DIV({templateTask}.{durationMinutes},480)`.
Compare it with the task's actual span
(`WEEKDAYDIFF(CLEARTIME({actualStartDate}),CLEARTIME({actualCompletionDate}))`)
and guard hand-added tasks with `ISBLANK({templateTaskID})`, which have no
template duration to compare against.

## Logical / conditional

| Function | Purpose | Example |
|---|---|---|
| `IF` | Conditional return | `IF({status}="CPL","Done","Not Done")` |
| `IFIN` | If value is in a list | `IFIN({status},"CPL","CUR","Active","Inactive")` |
| `IN` | Membership test | `IN({status},"CPL","CUR")` |
| `ISBLANK` | Test for blank | `IF(ISBLANK({DE:Region}),"None",{DE:Region})` |
| `CONTAINS` | Substring test | `IF(CONTAINS({name},"DRAFT"),"Yes","No")` |
| `CASE` | Multi-branch | `CASE({priority},0,"None",1,"Low",2,"Normal","Other")` |
| `SWITCH` | Similar to CASE | `SWITCH({status},"CPL","Done","CUR","In Progress","Other")` |

## String

| Function | Purpose |
|---|---|
| `CONCAT` | Join strings: `CONCAT("Owner: ",{owner}.{name})` |
| `SUBSTR` | Substring: `SUBSTR({name},0,10)` |
| `LEFT` | Leftmost characters: `LEFT({name},5)` |
| `RIGHT` | Rightmost characters: `RIGHT({name},5)` |
| `LEN` | String length |
| `UPPER` / `LOWER` | Case conversion |
| `REPLACE` | Find and replace |
| `TRIM` | Strip whitespace |
| `SEARCH` | Find substring position |
| `FORMAT` | Format value |
| `STRING` | Convert to string |
| `NUMBER` | Convert to number |
| `ARRAY` | Create an array |

## Date

| Function | Purpose | Example |
|---|---|---|
| `ADDDAYS` | Add calendar days | `ADDDAYS({plannedCompletionDate},7)` |
| `ADDWEEKDAYS` | Add business days | `ADDWEEKDAYS($$TODAY,5)` |
| `ADDMONTHS` | Add months | `ADDMONTHS({plannedCompletionDate},1)` |
| `ADDYEARS` | Add years | `ADDYEARS({plannedCompletionDate},1)` |
| `CLEARTIME` | Strip time portion | `CLEARTIME($$NOW)` |
| `DATE` | Construct a date | `DATE(2026,1,15)` |
| `DATEDIFF` | Difference in days (calendar), **first minus second**. Wrap both sides in `CLEARTIME` for whole days. | `DATEDIFF({plannedCompletionDate},$$TODAY)` = days remaining |
| `WEEKDAYDIFF` | Difference in weekdays, **second minus first**. Skips weekends, not company holidays. | `WEEKDAYDIFF({plannedCompletionDate},{actualCompletionDate})` = days late |
| `WORKMINUTESDIFF` | Difference in working minutes (respects schedule) | |
| `DAYOFMONTH` | Day number | |
| `DAYOFWEEK` | 1=Sunday … 7=Saturday | |
| `MONTH` | Month number | |
| `YEAR` | Year | |
| `DMAX` | Max of dates | |
| `DMIN` | Min of dates | |

## Math

| Function | Purpose |
|---|---|
| `ABS` | Absolute value |
| `AVERAGE` | Mean |
| `CEIL` | Round up |
| `FLOOR` | Round down |
| `ROUND` | Standard rounding: `ROUND({percentComplete},0)` |
| `MAX` / `MIN` | Max/min of values |
| `SUM` | Sum |
| `PROD` | Product |
| `DIV` / `SUB` | Divide / subtract |
| `POWER` | Exponent |
| `SQRT` | Square root |
| `LN` / `LOG` | Logarithms |
| `SORTASCNUM` / `SORTDESCNUM` | Numeric sort |

## Common patterns

### Days remaining
```
column.0.valueexpression=CONCAT(DATEDIFF({plannedCompletionDate},$$TODAY)," Days")
column.0.valueformat=HTML
column.0.displayname=Days Remaining
column.0.textmode=true
```

### Status label with emoji
```
column.0.valueexpression=CASE({status},"CPL","✅ Done","CUR","🟢 In Progress","PLN","⏳ Planned","❓ Other")
column.0.valueformat=HTML
column.0.displayname=Status
column.0.textmode=true
```

### Overdue flag
```
column.0.valueexpression=IF(DATEDIFF({plannedCompletionDate},$$TODAY)<0,"OVERDUE","")
column.0.valueformat=HTML
column.0.textmode=true
```

### Percent complete with format
```
column.0.valueexpression=ROUND({percentComplete},0)
column.0.valueformat=doubleAsPercentRounded
column.0.displayname=% Complete
column.0.textmode=true
```

`percentComplete` is already 0 to 100, which is what this needs: as an
aggregator `displayformat`, `doubleAsPercentRounded` rounds and appends `%`
without multiplying by 100 (verified, see `04-views-and-groupings.md`
§ Aggregators). The column-level `valueformat` was not tested separately.
