# Grouping: Overdue vs On Track

Apply to a **Project report** or **Task report**. Groups records into two buckets based on whether the planned completion date has passed.

```
group.0.valueexpression=IF(DATEDIFF({plannedCompletionDate},$$TODAY)<0,"Overdue","On Track")
group.0.valueformat=HTML
group.0.displayname=Status
```

## Add a second grouping level

Group first by overdue status, then by status code within each bucket:

```
group.0.valueexpression=IF(DATEDIFF({plannedCompletionDate},$$TODAY)<0,"Overdue","On Track")
group.0.valueformat=HTML
group.0.displayname=Schedule Status

group.1.valuefield=status
group.1.valueformat=HTML
group.1.linkedname=direct
```

## Add an aggregator

Count records in each group by adding to a column (not the group itself):

```
column.0.valuefield=ID
column.0.aggregator.function=COUNT
column.0.aggregator.valueformat=HTML
column.0.displayname=Project
column.0.textmode=true
```

The COUNT shows up in each grouping header row.
