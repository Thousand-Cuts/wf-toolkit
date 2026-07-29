# Filter: Tasks I'm Not Done With

Apply to a **Task report**. Returns tasks where the current user has at least one assignment that isn't marked Done.

```
EXISTS:1:$$OBJCODE=ASSGN
EXISTS:1:taskID=FIELD:ID
EXISTS:1:assignedToID=$$USER.ID
EXISTS:1:status=DN
EXISTS:1:status_Mod=notin
```

## Variants

### Add: only tasks on Current projects
```
EXISTS:1:$$OBJCODE=ASSGN
EXISTS:1:taskID=FIELD:ID
EXISTS:1:assignedToID=$$USER.ID
EXISTS:1:status=DN
EXISTS:1:status_Mod=notin
project:status=CUR
project:status_Mod=eq
```

### Add: tasks due in the next 14 days
```
EXISTS:1:$$OBJCODE=ASSGN
EXISTS:1:taskID=FIELD:ID
EXISTS:1:assignedToID=$$USER.ID
EXISTS:1:status=DN
EXISTS:1:status_Mod=notin
plannedCompletionDate=$$TODAY
plannedCompletionDate_Mod=gte
plannedCompletionDate=$$TODAY+14d
plannedCompletionDate_Mod=lte
```
