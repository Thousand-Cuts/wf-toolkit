# Calculated Field Example: Days Overdue

Apply to a **Project** or **Task** custom form.

**Format:** Number

```
DATEDIFF($$TODAY,{plannedCompletionDate})
```

## How It Works

`DATEDIFF(date1, date2)` returns `date1 − date2` in calendar days.

- Positive result → due date has passed (overdue)
- Zero → due today
- Negative result → due date is in the future

## Usage in Reports

Once stored as `DE:Days Overdue` on the object, you can:

- **Filter** in a text-mode report: `valuefield=DE:Days Overdue` with modifier `gt` and value `0` to show only overdue records.
- **Sort** descending to put most-overdue records first.
- **Apply conditional formatting**: in a report, add a column `valuefield=DE:Days Overdue` and configure conditional formatting to turn red when value > 0.
- **Group and aggregate**: in a Number-format column, reports can show average days overdue per owner or portfolio.

## Recalculation Note

`$$TODAY` is evaluated at UTC and is only accurate when the field was last recalculated. For always-fresh day counts in a report column only, use a `valueexpression` instead:

```
column.0.valueexpression=DATEDIFF($$TODAY,{plannedCompletionDate})
column.0.valueformat=HTML
column.0.displayname=Days Overdue (Live)
column.0.textmode=true
```

The stored calc field version is appropriate when you need to filter or group on the value.

## Variation: Text Flag for Overdue

**Format:** Text

```
IF(DATEDIFF($$TODAY,{plannedCompletionDate})>0,"OVERDUE","")
```

Returns `"OVERDUE"` when past due, empty string otherwise. Useful as a filter value: `DE:Overdue Flag` `eq` `OVERDUE`.
