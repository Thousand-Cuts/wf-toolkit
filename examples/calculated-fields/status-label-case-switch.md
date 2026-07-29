# Calculated Field Example: Status Label With CASE / SWITCH

Apply to a **Project**, **Task**, or **Issue** custom form.

## SWITCH version (recommended for status codes)

**Format:** Text

```
SWITCH({status},"CPL","✅ Complete","CUR","🟢 In Progress","PLN","⏳ Planned","ONH","⏸ On Hold","DED","💀 Dead","❓ Other")
```

`SWITCH` matches the expression value against each pair's left-side string and returns the corresponding right-side string. The final unpaired argument is the default.

## CASE version (for 0-based integer fields like Priority)

**Format:** Text

```
CASE({priority},0,"None",1,"Low",2,"Normal",3,"High",4,"Urgent","Unknown")
```

`CASE` takes an integer index (0-based). `{priority}` is stored as 0–4 in Workfront (None through Urgent). The last argument is the default fallback.

## Nested IF version (when you need compound conditions)

**Format:** Text

```
IF({status}="CPL","✅ Complete",IF({status}="CUR","🟢 In Progress",IF({status}="PLN","⏳ Planned",IF({status}="ONH","⏸ On Hold","❓ Other"))))
```

Nested IFs are equivalent to SWITCH for simple value-matching but are more flexible when conditions involve operators or multiple fields.

## Notes

- Status codes are case-sensitive string values stored in Workfront. Common project status codes: `CPL` (Complete), `CUR` (Current/In Progress), `PLN` (Planning), `ONH` (On Hold), `DED` (Dead). Verify the exact codes for your instance.
- Emoji render in custom form fields and in report columns. Some clients prefer plain text labels — confirm before deploying emoji.
- This field is best used to drive a display label that users see on the custom form, and can also be referenced in a text-mode `valuefield=DE:Status Label` column to enable conditional formatting in reports (conditional formatting cannot be applied to `valueexpression` columns).
