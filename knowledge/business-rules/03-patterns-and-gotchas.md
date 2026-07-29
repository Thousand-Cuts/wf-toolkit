# 03 — Business Rule Patterns and Gotchas

All patterns below are **Validation** rules unless noted. Declare the **Trigger** and **Type** in the UI; the formula holds only the condition + message.

## Pattern: Lock a field once a status is reached

**Trigger:** On object edit

```
IF({status} = "CPL" && {name} != $$BEFORE_STATE.{name}, "You cannot rename a completed project.")
```

Generalize: `{status} = "<code>" && {watchedField} != $$BEFORE_STATE.{watchedField}`.

## Pattern: Prevent any change to a field

**Trigger:** On object edit

```
IF({DE:Contract ID} != $$BEFORE_STATE.{DE:Contract ID}, "The Contract ID is set at creation and cannot be changed.")
```

Add `&& !$$ISAPI` if a Fusion scenario or bulk script legitimately updates the field.

## Pattern: Require a field before a status transition

**Trigger:** On object edit

```
IF($$AFTER_STATE.{status} = "CPL" && ISBLANK({DE:Resolution Notes}), "Add Resolution Notes before marking this complete.")
```

## Pattern: Block a delete

**Trigger:** On object delete

```
IF({status} != "DED", "Only cancelled tasks can be deleted. Change the status first.")
```

## Pattern: Restrict an action to a date window

**Trigger:** On object creation

```
IF(MONTH($$TODAY) = 11, "New projects cannot be created in November. [Policy](https://intranet/eoy)")
```

## Pattern: Enforce in the UI only (spare integrations)

Append `&& !$$ISAPI` to any condition so Fusion, bulk-update scripts, and system writes pass through while human edits are blocked.

## Pattern: Exempt a specific user

There is no admin-exemption switch. Encode it:

```
IF({plannedStartDate} != $$BEFORE_STATE.{plannedStartDate} && $$USER.ID != "641f0aaa0001abcdEXAMPLE", "Dates are locked. Contact the PMO to change them.")
```

## Gotchas

**Condition describes what's blocked.** Reading a rule as "what's allowed" inverts it. Confirm: condition true → blocked.

**Access levels and sharing outrank rules.** A rule cannot grant access, and it does not exempt system admins. If a user already lacks access, that wins before the rule is even evaluated.

**Rules fire on API and Fusion writes.** A "lock the field" rule with no `!$$ISAPI` will also block your own scenarios and bulk scripts. This is the most common production surprise.

**The scheduler recalculates dates.** On edit rules that compare `plannedStartDate`/`plannedCompletionDate` against `$$BEFORE_STATE`, Workfront's own rescheduling can change those dates when the user edited something else entirely, tripping the rule. Scope with `!$$ISAPI` and/or tighten the condition (e.g. also require the constraint field to be non-default).

**One rule per object per trigger; nested-IF order decides the message.** The first true branch supplies the message — order strictest first.

**No collection access.** Like calculated fields, a rule cannot iterate a child collection (e.g. "block if any child task is open"). Use a rollup calc field on the parent and reference that, or move the logic to Fusion.

**Package gating.** Validation needs Ultimate/Workflow Ultimate; Automation needs Workflow Ultimate. Confirm the package before promising a rule.

**Sandbox first, then activate.** Build with **Is active = No** or in Preview, exercise the exact create/edit/delete path, then enable in production. Also test the negative case (the action you intend to *allow* still goes through).

## Task-date note (from field experience)

When working with task scheduling constraints (`taskConstraint`), the codes you will compare against are `ASAP` (As Soon As Possible, the default), `MSO` (Must Start On), `MFO` (Must Finish On), `SNLT`/`FNLT` (Start/Finish No Later Than), `SNET`/`FNET` (Start/Finish No Earlier Than), `FIXEDDATES` (Fixed Dates), `ALAP` (As Late As Possible), `EAP`/`LAP` (Earliest/Latest Available Time). Note that over the **REST API** `FIXEDDATES` is silently ignored and `MSO` is the constraint that actually takes — relevant if a rule and an integration touch the same tasks.
