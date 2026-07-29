# Business Rule Example: Prevent Renaming a Completed Project

The canonical "lock a field once a status is reached" pattern.

**Object:** Project
**Trigger:** On object edit
**Type:** Validation

```
IF({status} = "CPL" && {name} != $$BEFORE_STATE.{name}, "You cannot rename a completed project.")
```

## How It Reads

*If the project status is Complete AND the name differs from its pre-edit value → block the save.*

- `{status} = "CPL"` — `CPL` is the stored code for Complete (compare codes, not the "Complete" label).
- `{name} != $$BEFORE_STATE.{name}` — fires only when the name actually changed, so other edits to a completed project still save.

## Adapt It

Swap `{name}` for any field you want frozen at completion, and `"CPL"` for the gating status:

```
IF({status} = "CPL" && {DE:Budget} != $$BEFORE_STATE.{DE:Budget}, "The budget is locked once the project is complete.")
```

Use `$$AFTER_STATE.{status}` instead of `{status}` if you also want the rule to catch the same save that *sets* the status to Complete.
