# Business Rule Example: Require a Field Before a Status Transition

Force a field to be filled in before an object can move to a given status.

**Object:** Issue (works on any object with a status)
**Trigger:** On object edit
**Type:** Validation

```
IF($$AFTER_STATE.{status} = "CPL" && ISBLANK({DE:Resolution Notes}), "Add Resolution Notes before marking this complete.")
```

## How It Reads

*If this edit sets the status to Complete AND Resolution Notes is empty → block the save.*

- `$$AFTER_STATE.{status}` — the value the save is trying to set, so the rule catches the transition itself.
- `ISBLANK({DE:Resolution Notes})` — true when the custom field is empty. (`DE:` prefixes a custom field; use `!ISBLANK(...)`/`ISBLANK(...)`, never `NOTBLANK`.)

## Why a Business Rule and Not "Required Field"

A custom-form **required field** forces a value whenever the form is saved. A business rule lets you require it **only at a specific transition** (here, only when moving to Complete) — the field can stay empty while the issue is still open.

## Adapt It

- Different gate: change `"CPL"` to the target status code.
- Multiple required fields: `... && (ISBLANK({DE:Resolution Notes}) || ISBLANK({DE:Root Cause}))`.
- Only in the UI: append `&& !$$ISAPI` so integrations that set the status programmatically aren't blocked.
