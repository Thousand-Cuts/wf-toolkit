# 09 — Tips and Gotchas

A grab-bag of hard-won knowledge that doesn't fit cleanly elsewhere.

## The big "why doesn't this work" list

| Symptom | Likely cause |
|---|---|
| Conditional formatting silently ignored | Column is `valueexpression` or part of a collection — use a calc custom field |
| "Too many hops" error | Filter or grouping going 3+ objects deep — use EXISTS |
| HTML tags showing as literal text in combined column | Inline HTML in `valueexpression` doesn't render — use `column.N.value=` with `width=1` |
| Filter modifier seems ignored | Missing `_Mod` line, or wrong modifier for the field type |
| Custom field returns blank | `DE:` argument must match the parameter's internal `name`, not the UI `label`. When the two diverge (a renamed field), only the `name` resolves. See `01-syntax-fundamentals.md` § "DE: name vs. label" |
| Cross-object reference (`{lastNote:noteText}`, `{program:DE:X}`, `{project:name}`) renders BLANK | Colon-inside-braces is silently rejected at render-time (PUT succeeds without error, cells just come back empty). Rewrite with dotted-brace traversal: `{lastNote}.{noteText}`, `{program}.{DE:X}`, `{project}.{name}`. Confirmed 2026-05-26 across 24 reports |
| Wildcard doesn't expand | Wildcard used in `valuefield` instead of `valueexpression` |
| Sort doesn't apply | `querysort` field name wrong, or grouping overrides it |
| Combined column doesn't combine | One sub-column is missing `sharecol=true`, or the LAST one has it (it shouldn't) |
| `valueexpression` works once then breaks after edit | Expression was wrapped across multiple lines; Workfront treats a newline as end of the directive — force single-line |
| `NOT(...)` returns syntax error or always false | Use `!(...)` instead; `NOT()` is not valid Workfront text mode syntax |
| `NOTBLANK` returns nothing useful | Use `!ISBLANK(...)` instead |
| Parentheses in custom field name cause weirdness in expressions or filters | Strip parens from the field name in Setup; parentheses cause problems in calculated fields and External Lookup substitution |

## Field naming conventions to avoid

These naming choices cause silent failures in calculated fields, External Lookup parameter substitution, and text mode expressions.

| Convention | Rule |
|---|---|
| Parentheses in custom field names | Never suggest names like `Budget (USD)` — use `Budget USD` instead |
| Question marks in field names | Preserve them — some instances have fields like `DE:Approved?`; don't strip the `?` |
| `DE:` prefix | Always prefix custom field references with `DE:` inside expressions and filters |
| Quoting `DE:` references | Don't wrap `DE:` field references in quotes inside expressions or filter values |
| `{project}.` / `{task}.` prefixes | Only add when the report's base object requires reaching a parent (e.g., Assignment report reaching the parent Task). Don't add by default |

When in doubt about a field name, point the user to the API Explorer rather than inventing a name.

## Performance

- **Calculated custom fields** are stored. Faster to display, can be filtered, can be conditionally formatted.
- **`valueexpression` columns** are computed at runtime. Slower, dynamic, can't be filtered or conditionally formatted.
- **Collections** are slow. If you only ever need one related value, don't use a collection.
- **EXISTS** is faster than joining 3 objects through views. Use EXISTS even when you could technically chain.

## Object choice matters

For "one row per X" reporting, pick the right object as the report base:

| You want one row per… | Report on… |
|---|---|
| Project | Project |
| Task | Task |
| Assignee on a task | Assignment |
| User | User |
| Time entry | Hour |
| Approval step | ApproverPath / Approval |

A common mistake: reporting on Tasks when you actually want one row per assignee. A task with three people assigned will be one row in a Task report (with assignees shown as a collection) but three rows in an Assignment report (one per person).

## Useful API Explorer URLs

The API Explorer lives at Adobe Experience League. Search for "Workfront API Explorer." It lets you:
- Browse every field on every object
- See the exact field name (case, spelling)
- See data type (date, string, integer, etc.)
- See related collections and their join fields

When in doubt, look it up there.

## Date math syntax

| Expression | Meaning |
|---|---|
| `$$TODAY` | Today, no time |
| `$$NOW` | Right now, with time |
| `$$TODAY+7d` | 7 days from today |
| `$$TODAY-1m` | One month ago |
| `$$TODAY+1y` | One year from today |
| `$$TODAY+1w` | One week from today |
| `$$TODAY+1q` | One quarter from today |

Date math works in filter values and `valueexpression`.

**`$$NOW` is unsupported in the Resource Planner.** The Resource Planner renderer ignores `$$NOW` wildcards in valueexpression-driven columns and groupings; the column renders blank. `$$TODAY` works fine. If a report drives a Resource Planner view, substitute `$$TODAY` for `$$NOW` — you lose sub-day precision but gain compatibility. Source: Adobe `report-elements/understand-wildcard-filter-variables`.

## Status codes quick reference

| Code | Display |
|---|---|
| `INP` | In Progress |
| `CPL` | Complete |
| `CUR` | Current |
| `PLN` | Planning |
| `DED` | Dead |
| `APV` | Approved |
| `REJ` | Rejected |
| `CPL:A` | Pending Approval (Complete) |
| `CUR:A` | Pending Approval (Current) |

**Note:** organizations can customize status codes. Always verify codes in your specific Workfront instance via Setup → Project Preferences → Statuses.

## Tips for building reports faster

1. **Start in standard mode.** Build as much as you can in the UI. Switch to text mode only to add what the UI can't do.
2. **Copy filters from existing reports.** Don't write from scratch.
3. **Build conditional formatting in standard mode on a temp column,** then copy the `styledef.case` lines to your real column.
4. **Build EXISTS by opening a report on the target object first,** building the filter in standard mode there, then copying the lines and prefixing with `EXISTS:N:`.
5. **Test with a small dataset.** Filter to a single project or a recent date range while iterating.

## What you can't do (and shouldn't try)

- Alternating row colors
- Truly dynamic column widths
- HTML/CSS injection beyond basic tags
- Conditional formatting on collections
- Sorting collections
- Filtering on 3+ objects without EXISTS
- Calculations that reference fields from sibling rows (use a calculated custom field at the parent level)

## When stuck

1. Check the API Explorer for the exact field name.
2. Search the Adobe Experience League community forums — most "weird" issues are documented.
3. Build it incrementally — one column at a time, one filter line at a time. Save and refresh between additions.

## Wildcard reference

Complete enumeration of session and runtime wildcards usable inside `valueexpression` columns and filters. **None of these work in `valuefield`.**

**User-relative (`$$USER.*`):**

| Wildcard | Resolves to | Notes |
|---|---|---|
| `$$USER.ID` | rendering user's UUID | Scalar |
| `$$USER.name` | rendering user's full name | **Text-mode only** — does not work in standard mode |
| `$$USER.firstName` | rendering user's first name | Scalar |
| `$$USER.lastName` | rendering user's last name | Scalar |
| `$$USER.companyID` | rendering user's company UUID | Scalar |
| `$$USER.customerID` | rendering user's tenant (customer) UUID | Scalar; useful in scripts that run cross-tenant |
| `$$USER.categoryID` | rendering user's category (custom-form) UUID | Scalar |
| `$$USER.accessLevelID` | rendering user's access-level UUID | Scalar |
| `$$USER.accessLevelRank` | rendering user's access-level numeric rank | Useful for "show only to admins"-style filters |
| `$$USER.roleID` | rendering user's primary role UUID | Scalar |
| `$$USER.roleIDs` | every role UUID the user holds | TAB-separated; use with `_Mod=in` |
| `$$USER.homeGroupID` | rendering user's home group UUID | Scalar |
| `$$USER.otherGroupIDs` | every non-home group UUID | TAB-separated |
| `$$USER.homeTeamID` | rendering user's home team UUID | Scalar |
| `$$USER.teamIDs` | every team UUID the user is on | TAB-separated |

**Date / time:**

| Wildcard | Resolves to | Notes |
|---|---|---|
| `$$TODAY` | midnight (start of day) in tenant timezone | |
| `$$NOW` | current timestamp (sub-day precision) | Unsupported in Resource Planner — see Date math syntax above |

**Arithmetic grammar** for date wildcards: `<TODAY|NOW><b|e><q|h|d|w|m|y>[+|-N]`

- Position 1: `TODAY` or `NOW` (base).
- Position 2 (optional): `b` for beginning, `e` for end of the unit.
- Position 3 (optional): unit — `q` quarter, `h` hour, `d` day, `w` week, `m` month, `y` year.
- Position 4 (optional): `+N` or `-N` to shift by N units.

Examples:

- `$$TODAY-7d` — seven days before today's midnight.
- `$$TODAYbm` — beginning of this month.
- `$$TODAYey-1` — end of last year (12/31).
- `$$TODAYbq+1` — beginning of next quarter.
- `$$NOWeh` — end of the current hour.

**Object-type:**

| Wildcard | Resolves to | Notes |
|---|---|---|
| `$$OBJCODE` | the current object's objCode (e.g., `PROJ`, `TASK`, `OPTASK`) | Useful inside `valueexpression` IF chains that switch behavior based on object type — e.g., a polymorphic report joining projects and tasks |

Source: Adobe `report-elements/understand-wildcard-filter-variables`. Snapshot date: 2026-05-14; Adobe may add new wildcards over time.
