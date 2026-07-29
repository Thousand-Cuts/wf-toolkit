# Search: Tasks Assigned to Me (EXISTS pattern via POST)

**What this shows:** Use a POST body to send a large filter set that applies the EXISTS pattern — filtering tasks where the calling user has an active assignment. POST avoids the 8,892-byte URL limit for complex filters.

## Request

```
POST https://<domain>.my.workfront.com/attask/api/v17.0/task/search
Content-Type: application/x-www-form-urlencoded
sessionID: <your_session_token>

method=GET
&fields=name,status,plannedCompletionDate,project:name
&EXISTS:1:$$OBJCODE=ASSGN
&EXISTS:1:taskID=FIELD:ID
&EXISTS:1:assignedToID=$$USER.ID
&EXISTS:1:status=DN
&EXISTS:1:status_Mod=notin
```

Note: `method=GET` in the POST body tells Workfront to treat this as a GET-style search — required when using POST for `/search`.

## What the filter does

- `EXISTS:1:$$OBJCODE=ASSGN` — joins the Assignment (ASSGN) table
- `EXISTS:1:taskID=FIELD:ID` — binds the assignment's task to the current task row
- `EXISTS:1:assignedToID=$$USER.ID` — limits to assignments owned by the calling user
- `EXISTS:1:status=DN / status_Mod=notin` — excludes assignments already marked Done

Result: tasks where I have at least one assignment that is not Done.

## Variants

### Add: only tasks on Current projects

```
&project:status=CUR
&project:status_Mod=eq
```

### Add: tasks due in the next 14 days

```
&plannedCompletionDate=$$TODAY
&plannedCompletionDate_Mod=gte
&plannedCompletionDate=$$TODAY+14d
&plannedCompletionDate_Mod=lte
```

### Change to NOTEXISTS (tasks with no active assignment from me)

Replace `EXISTS` with `NOTEXISTS` in all four parameter name prefixes.

## Notes

- The EXISTS block number (`1`) must match across all parameters in the same block. A second EXISTS block would use `EXISTS:2:...`.
- When used in a GET query string, the `:` characters in `EXISTS:1:...` do not need to be encoded — but the full URL must stay under 8,892 bytes. Use POST when the filter is large.
- See `07-exists-in-api.md` for the full EXISTS reference and OBJCODE table.
