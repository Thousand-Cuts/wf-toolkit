# Filter: Projects Where I Have Open Tasks

Apply to a **Project report**. Returns projects that contain at least one task assigned to the current user that isn't complete.

```
EXISTS:a:$$OBJCODE=TASK
EXISTS:a:projectID=FIELD:ID
EXISTS:a:assignments:assignedToID=$$USER.ID
EXISTS:a:actualCompletionDate=
EXISTS:a:actualCompletionDate_Mod=isnull
```

## How this works

- The outer report is on Project (one row per project)
- EXISTS looks inside Task for matches
- The join is `projectID=FIELD:ID` — find tasks whose `projectID` equals the current project's ID
- `assignments:assignedToID=$$USER.ID` reaches into the task's assignments collection to filter by assignee
- `actualCompletionDate isnull` means the task hasn't been completed

## Add: only projects with status Current
Combine with a top-level filter (no EXISTS prefix):

```
status=CUR
status_Mod=eq
EXISTS:a:$$OBJCODE=TASK
EXISTS:a:projectID=FIELD:ID
EXISTS:a:assignments:assignedToID=$$USER.ID
EXISTS:a:actualCompletionDate=
EXISTS:a:actualCompletionDate_Mod=isnull
```
