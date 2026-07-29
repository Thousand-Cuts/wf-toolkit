# View: Project Health Snapshot

Apply to a **Project report**. Columns:
1. Project name (clickable)
2. Owner full name
3. Status
4. % Complete
5. Planned completion date
6. Days remaining (calculated)

```
column.0.valuefield=name
column.0.linkedname=direct
column.0.displayname=Project
column.0.width=250
column.0.textmode=true

column.1.valueexpression=CONCAT({owner}.{firstName}," ",{owner}.{lastName})
column.1.valueformat=HTML
column.1.displayname=Owner
column.1.width=150
column.1.textmode=true

column.2.valuefield=status
column.2.valueformat=HTML
column.2.displayname=Status
column.2.width=120
column.2.textmode=true

column.3.valuefield=percentComplete
column.3.valueformat=doubleAsPercentRounded
column.3.displayname=% Complete
column.3.width=100
column.3.textmode=true

column.4.valuefield=plannedCompletionDate
column.4.valueformat=shortAtDate
column.4.displayname=Due Date
column.4.width=120
column.4.textmode=true

column.5.valueexpression=CONCAT(DATEDIFF({plannedCompletionDate},$$TODAY)," Days")
column.5.valueformat=HTML
column.5.displayname=Days Remaining
column.5.width=120
column.5.textmode=true

querysort=plannedCompletionDate
sortType=asc
usewidths=true
```

## Note on conditional formatting

To color the "Days Remaining" column red when negative (overdue), you cannot apply conditional formatting directly to `column.5` because it's a `valueexpression`.

**Workaround:** create a calculated custom field on Project called `Days Remaining` with the formula `DATEDIFF({plannedCompletionDate},$$TODAY)`, then reference it via `column.5.valuefield=DE:Days Remaining` and apply conditional formatting in standard mode.
