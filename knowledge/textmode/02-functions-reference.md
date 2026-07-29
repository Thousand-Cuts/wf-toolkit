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
| `DATEDIFF` | Difference in days (calendar) | `DATEDIFF({plannedCompletionDate},$$TODAY)` |
| `WEEKDAYDIFF` | Difference in business days | `WEEKDAYDIFF({actualCompletionDate},{plannedCompletionDate})` |
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
