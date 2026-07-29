# 03 — Functions Reference

All functions must be written in ALL UPPERCASE. The syntax for calculated custom fields uses curly-bracket field references `{fieldName}` — not the colon-separated `valuefield` syntax of text-mode reports.

## Logical / Conditional

| Function | Syntax | Notes |
|---|---|---|
| `IF` | `IF(condition, trueResult, falseResult)` | Nests freely; keep on one line |
| `IFIN` | `IFIN(value, v1, v2, ..., trueResult, falseResult)` | Tests if value matches any of the listed values |
| `IN` | `IN(value, v1, v2, ...)` | Returns `true`/`false`; use inside IF |
| `ISBLANK` | `ISBLANK(value)` | Returns `true` if null or empty string |
| `CONTAINS` | `CONTAINS(findText, withinText)` | Returns `true` if findText is a substring of withinText |
| `CASE` | `CASE(indexNumber, result0, result1, ...)` | Selects result by 0-based integer index |
| `SWITCH` | `SWITCH(expression, val1, result1, val2, result2, ..., default)` | Pattern-match on string/number values |

### IF example
```
IF({status}="CPL","Complete",IF({status}="CUR","In Progress","Other"))
```

### IFIN example
```
IFIN({status},"CPL","CUR","Active","Not Active")
```

### CASE example (0-based index)
```
CASE({priority},0,"None",1,"Low",2,"Normal",3,"High",4,"Urgent","Unknown")
```

### SWITCH example (label matching)
```
SWITCH({status},"CPL","Complete","CUR","In Progress","PLN","Planned","ONH","On Hold","Unknown")
```

## String Functions

| Function | Syntax | Notes |
|---|---|---|
| `CONCAT` | `CONCAT(s1, s2, ...)` | Any number of arguments; use for ALL multi-part strings |
| `LEFT` | `LEFT(string, length)` | First N characters |
| `RIGHT` | `RIGHT(string, length)` | Last N characters |
| `SUBSTR` | `SUBSTR(string, start, end)` | 0-based start index |
| `LEN` | `LEN(string)` | Length in characters |
| `UPPER` | `UPPER(string)` | Convert to uppercase |
| `LOWER` | `LOWER(string)` | Convert to lowercase |
| `PASCAL` | `PASCAL(string)` | Convert to PascalCase |
| `TRIM` | `TRIM(string)` | Remove leading/trailing whitespace |
| `REPLACE` | `REPLACE(string, findText, replacement)` | Replace all occurrences |
| `REPLACEPATTERN` | `REPLACEPATTERN(string, regexPattern, replacement)` | Regex-based replacement |
| `SEARCH` | `SEARCH(findText, withinText, startIndex)` | Returns character index (0-based) or `-1` |
| `STRING` | `STRING(number)` | Convert number to string |
| `NUMBER` | `NUMBER(string)` | Convert string to number |
| `ENCODEURL` | `ENCODEURL(string)` | URL-encode special characters |
| `REMOVEACCENTS` | `REMOVEACCENTS(string)` | Strip diacritical marks |
| `FORMAT` | `FORMAT(colorOpt, formatOpt1, ...)` | Conditional color/style; see below |

### FORMAT function (color and style)

`FORMAT` applies visual formatting to a calculated field's display. It does not change the stored value — it changes how the field appears in the custom form and in reports.

Syntax: `IF(condition, FORMAT($$COLOR, $$STYLE), fallback)`

Color options (choose at most one): `$$POSITIVE` (green), `$$INFORMATIVE` (blue), `$$NEGATIVE` (red), `$$NOTICE` (orange).

Style options (up to three): `$$BOLD`, `$$ITALIC`, `$$UNDERLINE`.

```
IF({DE:Budget Remaining}<0,FORMAT($$NEGATIVE,$$BOLD),IF({DE:Budget Remaining}<1000,FORMAT($$NOTICE),""))
```

You can chain up to five FORMAT rules per field.

### ARRAY functions

| Function | Syntax | Notes |
|---|---|---|
| `ARRAY` | `ARRAY(string, "delimiter")` | Split string into array |
| `ARRAYCONTAINS` | `ARRAYCONTAINS(array, value)` | Returns `true`/`false` |
| `ARRAYLENGTH` | `ARRAYLENGTH(array)` | Number of elements |
| `ARRAYELEMENT` | `ARRAYELEMENT(array, index)` | 0-based element retrieval |
| `SORTASCARRAY` | `SORTASCARRAY(array)` | Sort ascending |
| `SORTDESCARRAY` | `SORTDESCARRAY(array)` | Sort descending |

## Date Functions

| Function | Syntax | Notes |
|---|---|---|
| `ADDDAYS` | `ADDDAYS(date, n)` | Supports fractional days (e.g., `1.5`) |
| `ADDWEEKDAYS` | `ADDWEEKDAYS(date, n)` | Business days only; integer n |
| `ADDMONTHS` | `ADDMONTHS(date, n)` | |
| `ADDYEARS` | `ADDYEARS(date, n)` | |
| `ADDHOURS` | `ADDHOURS(date, n)` | Not available in Workfront Planning |
| `CLEARTIME` | `CLEARTIME(date)` | Strip time, keep date |
| `DATE` | `DATE(string)` | Parse string to date |
| `DATEDIFF` | `DATEDIFF(date1, date2)` | Calendar days between dates (`date1 − date2`) |
| `WEEKDAYDIFF` | `WEEKDAYDIFF(date2, date1)` | Business days between (note argument order) |
| `WORKMINUTESDIFF` | `WORKMINUTESDIFF(date1, date2)` | Working minutes per default schedule |
| `DAYOFMONTH` | `DAYOFMONTH(date)` | Returns 1–31 |
| `DAYOFWEEK` | `DAYOFWEEK(date)` | 1 = Sunday, 7 = Saturday |
| `DAYSINMONTH` | `DAYSINMONTH(date)` | Total days in the month |
| `DAYSINYEAR` | `DAYSINYEAR(date)` | Total days in the year |
| `DAYSINSPLITWEEK` | `DAYSINSPLITWEEK(date)` | Weekdays remaining to week or month boundary |
| `DMAX` | `DMAX(d1, d2, ...)` | Latest date in list |
| `DMIN` | `DMIN(d1, d2, ...)` | Earliest date in list |
| `HOUR` | `HOUR(date)` | 0–23 |
| `MINUTE` | `MINUTE(date)` | 0–59 |
| `SECOND` | `SECOND(date)` | 0–59 |
| `MONTH` | `MONTH(date)` | 1–12 |
| `YEAR` | `YEAR(date)` | 4-digit year |

### Date wildcards

`$$TODAY` and `$$NOW` are available in calculated fields but carry a UTC caveat: the system evaluates them at UTC, not the user's local timezone. For most business-day calculations this is acceptable. For date-boundary logic where one-day-off errors matter, document the limitation explicitly.

`$$TODAY` and `$$NOW` are **not** supported as date modifiers with offset syntax (`$$TODAY+7d`) in calculated fields the way they are in text-mode `valueexpression`. Use `ADDDAYS($$TODAY, 7)` instead.

## Math Functions

| Function | Syntax | Notes |
|---|---|---|
| `ABS` | `ABS(n)` | Absolute value |
| `AVERAGE` | `AVERAGE(n1, n2, ...)` | Arithmetic mean |
| `CEIL` | `CEIL(n)` | Round up to integer |
| `FLOOR` | `FLOOR(n)` | Round down to integer |
| `ROUND` | `ROUND(n, precision)` | Standard round; `ROUND(3.567, 2)` → `3.57` |
| `MAX` | `MAX(n1, n2, ...)` | Maximum value |
| `MIN` | `MIN(n1, n2, ...)` | Minimum value |
| `SUM` | `SUM(n1, n2, ...)` | Sum |
| `SUB` | `SUB(n1, n2, ...)` | Subtraction |
| `DIV` | `DIV(n1, n2, ...)` | Division |
| `PROD` | `PROD(n1, n2, ...)` | Product / multiplication |
| `POWER` | `POWER(base, exp)` | Exponentiation |
| `SQRT` | `SQRT(n)` | Square root |
| `LN` | `LN(n)` | Natural log |
| `LOG` | `LOG(base, n)` | Logarithm |
| `SORTASCNUM` | `SORTASCNUM(n1, n2, ...)` | Sort numbers ascending |
| `SORTDESCNUM` | `SORTDESCNUM(n1, n2, ...)` | Sort numbers descending |

### Note on hours vs. minutes

Duration fields in Workfront (like `actualDurationMinutes`) store values in **minutes**. To display as hours, divide by 60: `DIV({actualDurationMinutes}, 60)`.

## Functions Shared With Text Mode vs. Functions Unique to Calc Fields

The **function set is largely the same** between calculated custom fields and `valueexpression` columns in text-mode reports. The syntax differs (curly brackets and interface names in calc fields; camelCase and `{object}.` traversal in valueexpression), but the available functions are drawn from the same library.

**FORMAT** (color/style) is available in calculated custom fields on the custom form. It is not meaningful in `valueexpression` text-mode columns.

**$$OBJCODE** wildcard is available in both contexts but is particularly useful in calc fields on multi-object forms.

**$$TODAY** offset math (`$$TODAY+7d`) works in `valueexpression` columns but should NOT be relied on in calculated fields — use `ADDDAYS($$TODAY, n)` in calc fields instead.
