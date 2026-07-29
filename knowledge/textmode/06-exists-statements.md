# 06 — EXISTS and NOTEXISTS Statements

## When to use EXISTS

Workfront filters and groupings can only reference 2 objects deep. If you hit "Too many hops" or you need to filter on a related object more than 2 levels away, use `EXISTS`.

**Common scenarios:**
- Filter projects by something about their tasks' assignments
- Filter tasks by something about their parent project's portfolio
- Filter tasks by something about their assignees' roles

## EXISTS structure

Every EXISTS block has at minimum:
1. A line declaring **what object** you're looking for matches in
2. A line declaring **how it joins** back to the current object
3. One or more lines filtering that target object

### Pattern
```
EXISTS:N:$$OBJCODE=TARGETOBJECT
EXISTS:N:joinField=FIELD:ID
EXISTS:N:filterField=value
EXISTS:N:filterField_Mod=modifier
```

`N` is a group identifier (use `1`, `a`, `b`, etc. — must be consistent across all lines in the same EXISTS group).

## Object codes (the values for `$$OBJCODE`)

| Code | Object |
|---|---|
| `PROJ` | Project |
| `TASK` | Task |
| `ASSGN` | Assignment |
| `ISSUE` | Issue |
| `OPTASK` | Issue/Optask (legacy) |
| `USER` | User |
| `ROLE` | Job Role |
| `TEAM` | Team |
| `PORT` | Portfolio |
| `PRGM` | Program |
| `HOUR` | Hour |
| `EXPNS` | Expense |
| `DOCU` | Document |
| `TMPL` | Template |
| `TMPLTSK` | Template Task |

## Common EXISTS examples

### "Tasks where I have an incomplete assignment" (the classic "Done With My Part" filter)
```
EXISTS:1:$$OBJCODE=ASSGN
EXISTS:1:taskID=FIELD:ID
EXISTS:1:assignedToID=$$USER.ID
EXISTS:1:status=DN
EXISTS:1:status_Mod=notin
```

This says: find tasks where there EXISTS an assignment record whose `taskID` matches this task's ID, whose `assignedToID` is the current user, and whose status is NOT "Done."

### "Projects where I have at least one incomplete task"
```
EXISTS:a:$$OBJCODE=TASK
EXISTS:a:projectID=FIELD:ID
EXISTS:a:assignments:assignedToID=$$USER.ID
EXISTS:a:actualCompletionDate=
EXISTS:a:actualCompletionDate_Mod=isnull
```

### "Tasks in projects belonging to a specific portfolio" (3-hop filter)
```
EXISTS:1:$$OBJCODE=PROJ
EXISTS:1:ID=FIELD:projectID
EXISTS:1:portfolioID=YOUR_PORTFOLIO_ID
EXISTS:1:portfolioID_Mod=eq
```

### "Users assigned to a specific role"
```
EXISTS:1:$$OBJCODE=USER
EXISTS:1:ID=FIELD:assignedToID
EXISTS:1:roleID=YOUR_ROLE_ID
EXISTS:1:roleID_Mod=eq
```

## NOTEXISTS

Same syntax, but finds records WITHOUT matching children.

### "Projects with NO open issues"
```
NOTEXISTS:1:$$OBJCODE=OPTASK
NOTEXISTS:1:projectID=FIELD:ID
NOTEXISTS:1:status=CPL
NOTEXISTS:1:status_Mod=ne
```

### "Tasks with no assignees"
```
NOTEXISTS:1:$$OBJCODE=ASSGN
NOTEXISTS:1:taskID=FIELD:ID
```

## EXISTS combined with OR

Prefix the entire block with `OR:N:`:

```
status=CUR
status_Mod=eq
OR:1:EXISTS:a:$$OBJCODE=TASK
OR:1:EXISTS:a:projectID=FIELD:ID
OR:1:EXISTS:a:priority=4
OR:1:EXISTS:a:priority_Mod=eq
```

This finds: projects where status = Current OR where any task has priority = 4.

## The fastest way to build a complex EXISTS

1. Open a report on the **target object** (the one you want to look "inside" of — e.g., if you're filtering Projects by something about their Tasks, open a Task report).
2. Build the filter you want in **standard mode** on that target object.
3. Switch to text mode and copy the filter lines.
4. Go back to your original report (e.g., the Project report).
5. Paste the lines into your filter, prefixing each one with `EXISTS:1:`.
6. Add the join line: `EXISTS:1:joinFieldOnTarget=FIELD:joinFieldOnCurrent` (usually `FIELD:ID`).
7. Add the `$$OBJCODE` line at the top.

This avoids guessing field names and is faster than writing EXISTS from scratch.

## Common errors

- **"Too many hops"** → you have a filter going 3+ levels deep without EXISTS. Convert it.
- **Empty results when you expected matches** → check that the join field is correct. `taskID=FIELD:ID` on a task's children is wrong; it should be `taskID=FIELD:ID` from the assignment's perspective joining to the task's ID.
- **EXISTS treats all lines as AND** → if you need OR inside an EXISTS, you can use `OR:N:` lines WITHIN the EXISTS, but it's clearer to split into two EXISTS blocks combined with outer OR.
