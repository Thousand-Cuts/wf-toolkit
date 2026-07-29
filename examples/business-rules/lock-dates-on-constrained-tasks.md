# Business Rule Example: Lock Dates on Constrained Tasks

Prevent users from changing a task's planned dates once the task carries a scheduling constraint.

**Object:** Task
**Trigger:** On object edit
**Type:** Validation

```
IF({taskConstraint} != "ASAP" && ({plannedStartDate} != $$BEFORE_STATE.{plannedStartDate} || {plannedCompletionDate} != $$BEFORE_STATE.{plannedCompletionDate}), "You can't change the dates on a task that has a scheduling constraint. Set the Task Constraint back to As Soon As Possible before adjusting the dates.")
```

## How It Reads

*If the task's constraint is anything other than As Soon As Possible, AND the planned start or planned completion date differs from its value before this edit → block the save.*

- `{taskConstraint} != "ASAP"` — treats any non-default constraint as "has a constraint." `ASAP` is the stored code for As Soon As Possible.
- `$$BEFORE_STATE.{plannedStartDate}` / `$$BEFORE_STATE.{plannedCompletionDate}` — the pre-edit values, so the rule fires **only when a date actually changed**, not on every save.
- Condition true → the edit is blocked and the message is shown.

## Variations

**Only hard date-pinning constraints lock the dates** (let ASAP/ALAP/SNLT/etc. float):

```
IF(IFIN({taskConstraint}, "MSO", "MFO", "FIXEDDATES") && ({plannedStartDate} != $$BEFORE_STATE.{plannedStartDate} || {plannedCompletionDate} != $$BEFORE_STATE.{plannedCompletionDate}), "This task's dates are fixed by its constraint and cannot be changed.")
```

**Also protect the constraint target date** — add `|| {constraintDate} != $$BEFORE_STATE.{constraintDate}` inside the date group.

## Gotchas for This Rule

- **Insert the field tokens from the Fields picker** (Task → Task Constraint, Planned Start Date, Planned Completion Date) so the internal names match the tenant.
- **The scheduler recalculates planned dates** when tasks are rescheduled, which can fire this rule even when the user edited something else. If you see false blocks, append `&& !$$ISAPI` so only direct UI edits are caught and system/API/Fusion recalcs pass through.
- **Enum by code, not label:** compare against `"ASAP"`, `"MSO"`, `"FIXEDDATES"`, not their display names.
- **Test both directions in Preview:** set a constraint and confirm a date edit is blocked; set the constraint back to As Soon As Possible and confirm date edits go through.
