# 06 — Filtering Queries

API filters use the same `field=value` + `field_Mod=modifier` syntax as text mode. They appear as URL query parameters on GET requests (typically against the `/search` action) and as form fields on some POST operations.

## Filter syntax basics

Every filter is a pair:

```
fieldName=value
fieldName_Mod=modifier
```

In a URL:

```
GET /attask/api/v<version>/project/search
  ?status=CUR
  &status_Mod=eq
  &priority=3
  &priority_Mod=gte
```

URL-encode special characters in real requests (`$$`, `:`, `+`, spaces, etc.).

## Filter modifiers (full list)

| Modifier | Meaning |
|---|---|
| `eq` | Equal to |
| `ne` | Not equal to |
| `gt` | Greater than |
| `lt` | Less than |
| `gte` | Greater than or equal |
| `lte` | Less than or equal |
| `contains` | Contains substring (case-sensitive) |
| `notcontains` | Does not contain (case-sensitive) |
| `cicontains` | Contains substring (case-insensitive) |
| `like` | SQL-style LIKE (case-sensitive, supports `%` wildcards) |
| `clike` | LIKE, case-insensitive |
| `in` | Value matches one of multiple values. **Safe form:** repeated params (`name=A&name=B&name_Mod=in`). **ID fields** also accept comma-separated (`ID=guid1,guid2&ID_Mod=in`). **String fields** (e.g. `name`) require repeated params — comma-separated silently returns `[]`. Verified v17.0, 2026-05. |
| `notin` | Value is not in the list (same repeated-param rule for string fields) |
| `between` | Value between two bounds. **Requires a companion `<field>_Range` parameter** holding the upper bound; the field value itself holds the lower bound. See "Range filters (`between`)" below. |
| `notbetween` | Value not between two bounds (same `_Range` companion). |
| `isnull` | Value is null |
| `notnull` | Value is not null |
| `isblank` | Value is blank (null or empty) |
| `notblank` | Value is not blank |

### Case-insensitive and prefix/suffix variants

These are documented in Adobe's query-syntax reference (cross-checked against the Workfront MCP reference docs, 2026-06-28). Round-trip against your target object's API Explorer if exact behavior is critical.

| Modifier | Meaning |
|---|---|
| `startswith` | Value starts with (case-sensitive) |
| `cistartswith` | Starts with (case-insensitive) |
| `endswith` | Value ends with (case-sensitive) |
| `ciendswith` | Ends with (case-insensitive) |
| `cieq` | Equals (case-insensitive) |
| `cine` | Not equal (case-insensitive) |
| `ciin` | In list (case-insensitive) |
| `cinotin` | Not in list (case-insensitive) |
| `cicontainsany` | Contains **any** of the space-separated words (case-insensitive) |
| `cicontainsall` | Contains **all** of the space-separated words (case-insensitive) |

> **`ne` also matches NULLs.** A `field_Mod=ne` filter returns rows where the field differs from the value **OR the field is null** (`field <> value OR field IS NULL`) — a classic Workfront footgun. To exclude nulls, AND a `notnull` condition on the same field.

### Range filters (`between`)

`between` / `notbetween` need two bounds. The field value carries the lower bound; a companion `<field>_Range` parameter carries the upper bound:

```
?entryDate=2026-01-01
&entryDate_Mod=between
&entryDate_Range=2026-12-31
```

Returns records with `entryDate` from 2026-01-01 through 2026-12-31 inclusive. Without the `_Range` companion, a `between` filter is incomplete and will not behave as intended.

## AND logic (default)

Multiple filter pairs are AND-ed together automatically.

```
?status=CUR
&status_Mod=eq
&priority=3
&priority_Mod=gte
```

Returns records where status = CUR AND priority >= 3.

## OR logic

Use the `OR:N:` prefix where `N` is a group identifier. All filter pairs sharing the same `N` are OR-ed together. **`OR:N:` works in the REST API** — verified on v17.0 preview, 2026-05 (a `team/search` with `?name=Design&name_Mod=eq&OR:1:name=BEDs&OR:1:name_Mod=eq` returned both teams).

```
?status=CUR
&status_Mod=eq
&OR:1:status=PLN
&OR:1:status_Mod=eq
&OR:1:priority=3
&OR:1:priority_Mod=gte
```

Returns records where status = CUR OR (status = PLN AND priority >= 3).

OR groups can contain EXISTS blocks too — see `07-exists-in-api.md`.

### When to use `OR:N:` vs `_Mod=in`

| Use | When |
|---|---|
| `_Mod=in` with repeated params | Matching multiple values on the **same field** (e.g. several team names). Simpler, fewer params. |
| `OR:N:` groups | Matching different fields, or combining ANDs and ORs (e.g. `status=A` OR (`status=B` AND `priority>=3`)). |

For same-field multi-value filters on **string fields**, use repeated params: `name=A&name=B&name_Mod=in`. Comma-separated (`name=A,B&name_Mod=in`) silently returns `[]` for string fields, but works for ID fields.

## Wildcards in filter values

| Wildcard | Returns |
|---|---|
| `$$USER` | Calling user's ID (bare form; same as `$$USER.ID`) |
| `$$USER.ID` | Calling user's ID |
| `$$USER.name` | Calling user's display name |
| `$$USER.homeGroupID` | Calling user's home group ID |
| `$$USER.otherGroupIDs` | All of the user's other group IDs (use with `_Mod=in`) |
| `$$USER.roleID` | User's primary role ID |
| `$$USER.roleIDs` | All of the user's role IDs (use with `_Mod=in`) |
| `$$USER.accessLevelID` | User's access level ID |
| `$$USER.accessLevelRank` | User's access level rank |
| `$$USER.companyID` | User's company ID |
| `$$USER.categoryID` | User's category ID |
| `$$TODAY` | Current date (no time) |
| `$$NOW` | Current date and time |

`$$USER.roleIDs` and `$$USER.otherGroupIDs` resolve to lists — pair them with `_Mod=in` (e.g. `?roleID=$$USER.roleIDs&roleID_Mod=in`). Attribute coverage cross-checked against the Workfront MCP wildcards reference (2026-06-28).

**Caveat:** `$$USER.*` resolves to whichever user the API request authenticated as. For server-to-server auth (a service account), this may not be the user you expect — pass an explicit user ID rather than relying on the wildcard for impersonation cases.

### Date math

```
?plannedCompletionDate=$$TODAY+30d
&plannedCompletionDate_Mod=lte
```

| Suffix | Unit |
|---|---|
| `d` | days |
| `w` | weeks |
| `m` | months |
| `q` | quarters |
| `y` | years |

Date math works in both directions: `$$TODAY-1m`, `$$TODAY+7d`.

#### Period-boundary suffixes

Beyond fixed offsets, `$$TODAY` / `$$NOW` accept beginning/end-of-period suffixes — useful for "this month", "this quarter to date" filters without computing dates yourself (cross-checked against the Workfront MCP wildcards reference, 2026-06-28):

| Suffix | Resolves to |
|---|---|
| `b` / `e` | Beginning / end of the current day |
| `bw` / `ew` | Beginning / end of this week |
| `bm` / `em` | Beginning / end of this month |
| `bq` | Beginning of this quarter |
| `by` | Beginning of this year |

Suffixes combine with offsets: `$$TODAYbm` = first of this month; `$$TODAYem` = end of this month; `$$TODAYe+1w` = end of next week.

```
?plannedCompletionDate=$$TODAYbm
&plannedCompletionDate_Mod=gte
&plannedCompletionDate=$$TODAYem
&plannedCompletionDate_Mod=lte
```

Returns records due at any point in the current month.

## Common API filter patterns

### Active projects I own

```
?ownerID=$$USER.ID
&ownerID_Mod=eq
&status=CUR
&status_Mod=eq
```

### Tasks due in the next 7 days, not complete

```
?plannedCompletionDate=$$TODAY
&plannedCompletionDate_Mod=gte
&plannedCompletionDate=$$TODAY+7d
&plannedCompletionDate_Mod=lte
&percentComplete=100
&percentComplete_Mod=lt
```

### Projects in a list of portfolios

```
?portfolioID=PORTFOLIO_ID_1,PORTFOLIO_ID_2,PORTFOLIO_ID_3
&portfolioID_Mod=in
```

### Custom field is blank

```
?DE:Vendor Name=
&DE:Vendor Name_Mod=isblank
```

(URL-encode the space in `DE:Vendor Name` as `%20` or `+` per your client's conventions.)

## Status codes in filter values

Use the underlying codes, not display names. See `10-status-and-enum-codes.md` for the full list.

```
?status=CPL
&status_Mod=eq
```

For "pending approval to enter status X", append `:A`:

```
?status=CPL:A
&status_Mod=eq
```

## Where to find field names

The API Explorer lists every filterable field on every object. Don't guess.
