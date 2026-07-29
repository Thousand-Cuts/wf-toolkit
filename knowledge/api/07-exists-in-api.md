# 07 — EXISTS and NOTEXISTS in API Queries

The text-mode `EXISTS` / `NOTEXISTS` pattern works in API filter query strings, with the same shape. Use it whenever a filter needs to reach more than two objects deep, or whenever you want to filter parents by something about their children.

## EXISTS structure

Every EXISTS block has at minimum:

1. A line declaring **what object** you're looking for matches in (`$$OBJCODE=...`)
2. A line declaring **how it joins back** to the current object (`joinField=FIELD:ID` or similar)
3. One or more lines filtering that target object

```
EXISTS:N:$$OBJCODE=<TARGET-OBJCODE>
EXISTS:N:<joinField>=FIELD:<currentObjectField>
EXISTS:N:<filterField>=<value>
EXISTS:N:<filterField>_Mod=<modifier>
```

`N` is a group identifier (`1`, `a`, `b`, ...). Every line in the same EXISTS block must use the same `N`.

OBJCODE values are listed in `03-object-codes.md`.

## Encoding for URL query strings

When sending EXISTS via HTTP:

- URL-encode `$$` (typically `%24%24`), `:` (`%3A`), and any special characters in values.
- Or pass the EXISTS lines as form-encoded body parameters on a POST (the API accepts both for the search action).
- For complex queries, posting form-encoded is more readable than building a query string.

```
POST /attask/api/v<version>/task/search
Content-Type: application/x-www-form-urlencoded

EXISTS:1:$$OBJCODE=ASSGN
EXISTS:1:taskID=FIELD:ID
EXISTS:1:assignedToID=$$USER.ID
EXISTS:1:status=DN
EXISTS:1:status_Mod=notin
```

(Body lines shown one per line for clarity; in practice they're joined by `&` and URL-encoded.)

## Common EXISTS examples

### Tasks where the caller has an incomplete assignment

```
EXISTS:1:$$OBJCODE=ASSGN
EXISTS:1:taskID=FIELD:ID
EXISTS:1:assignedToID=$$USER.ID
EXISTS:1:status=DN
EXISTS:1:status_Mod=notin
```

### Projects with at least one in-progress task assigned to the caller

```
EXISTS:a:$$OBJCODE=TASK
EXISTS:a:projectID=FIELD:ID
EXISTS:a:assignments:assignedToID=$$USER.ID
EXISTS:a:actualCompletionDate=
EXISTS:a:actualCompletionDate_Mod=isnull
```

### Tasks belonging to projects in a specific portfolio (3-hop)

```
EXISTS:1:$$OBJCODE=PROJ
EXISTS:1:ID=FIELD:projectID
EXISTS:1:portfolioID=YOUR_PORTFOLIO_ID
EXISTS:1:portfolioID_Mod=eq
```

### Users assigned to a specific role

```
EXISTS:1:$$OBJCODE=USER
EXISTS:1:ID=FIELD:assignedToID
EXISTS:1:roleID=YOUR_ROLE_ID
EXISTS:1:roleID_Mod=eq
```

## NOTEXISTS

Same syntax, finds records WITHOUT matching children.

### Projects with no open issues

```
NOTEXISTS:1:$$OBJCODE=OPTASK
NOTEXISTS:1:projectID=FIELD:ID
NOTEXISTS:1:status=CPL
NOTEXISTS:1:status_Mod=ne
```

### Tasks with no assignees

```
NOTEXISTS:1:$$OBJCODE=ASSGN
NOTEXISTS:1:taskID=FIELD:ID
```

## EXISTS combined with OR

Prefix the entire EXISTS block with `OR:N:`:

```
status=CUR
status_Mod=eq
OR:1:EXISTS:a:$$OBJCODE=TASK
OR:1:EXISTS:a:projectID=FIELD:ID
OR:1:EXISTS:a:priority=4
OR:1:EXISTS:a:priority_Mod=eq
```

Returns: projects where status = CUR OR projects with any task at priority 4.

## Fastest way to build a complex EXISTS for an API call

Same approach as text mode:

1. Open a report on the **target object** (the object the EXISTS is looking inside) in Workfront's UI.
2. Build the filter in standard mode.
3. Switch to text mode and copy the filter lines.
4. Prefix each line with `EXISTS:N:` (and add the `$$OBJCODE=` + join lines).
5. Drop it into your API request.

Building in the UI first avoids guessing field names.

## Common pitfalls

- **Wrong join direction.** `taskID=FIELD:ID` is correct when the EXISTS is from the parent's perspective looking at child assignments (the assignment's `taskID` equals the parent task's `ID`). Flip it and you get empty results.
- **EXISTS without a `$$OBJCODE` line.** The API returns an error or ignores the block. Always declare the target object first.
- **Mismatched `N` across lines.** All lines in one EXISTS block must share the same `N`. Mixing `1` and `a` splits them into separate blocks.
- **Forgetting to URL-encode.** `$$OBJCODE` and `FIELD:` contain characters that need encoding in URL query strings.
