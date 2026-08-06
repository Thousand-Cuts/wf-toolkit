# 05 — Conditional Formatting

## What conditional formatting CAN do

- Change cell background color
- Change text color
- Apply bold/italic
- Show icons (✓, ✗, warning triangles, etc.)
- Replace cell value with custom text
- Show images

## What conditional formatting CANNOT do

These are the most common reasons consultants get stuck:

1. **It does not work on `valueexpression` columns.** The rules are silently ignored.
2. **It does not work on collections.** Same — silently ignored.
3. **It does not provide alternating row colors.** No way to achieve this.
4. **It does not work cleanly on a column that's part of a shared column group** unless applied to the first (non-shared) column.

### Workaround for `valueexpression` columns

Build a **calculated custom field** at the object level (Setup → Custom Forms → add a calculated field). The calculation persists in the database, so it can be referenced like any other field — and conditional formatting works on it.

Example: instead of `valueexpression=CONCAT(DATEDIFF({plannedCompletionDate},$$TODAY)," Days")` in your column, create a calculated custom field `Days Remaining` with that formula, then reference `DE:Days Remaining` in your view and apply conditional formatting to it.

**Tradeoff: calc-column vs calc-custom-field for conditionally-formatted derived values.** When the value you want to conditionally format is itself derived (e.g., "days since last update"), you have two paths:

- **Calculated column** (`valueexpression` in the view) — recomputes on every report render, sees `$$TODAY`/`$$NOW`, but CANNOT carry conditional formatting (the styledef engine ignores valueexpression-derived values).
- **Calculated custom field** — can carry conditional formatting via styledef, but stores its value at custom-form save time and only recomputes on object save or bulk "Recalculate Custom Expressions" — and cannot reference `$$TODAY`/`$$NOW`.

For "stale OK, formatting needed" — pick the custom field. For "live OK, formatting via cell color not needed" — pick the column. For "live AND formatting needed" — there's no clean path; use the column with `<span style='color:red'>` HTML inside the valueexpression, which works but is verbose. Source: Adobe `calculated-custom-data/calculated-custom-fields-calculated-columns`.

## Conditional formatting syntax

Conditional formatting uses `styledef` directives. Each rule is one `case`.

### Basic structure
```
column.0.styledef.case.0.comparison.lefttype=value
column.0.styledef.case.0.comparison.righttype=value
column.0.styledef.case.0.comparison.operator=eq
column.0.styledef.case.0.comparison.leftvalue=
column.0.styledef.case.0.comparison.rightvalue=CPL
column.0.styledef.case.0.comparison.true-color=2E844A
column.0.styledef.case.0.comparison.true-text-color=FFFFFF
column.0.styledef.case.0.comparison.true-bgcolor=2E844A
column.0.styledef.case.0.comparison.true-font-weight=bold
```

### Easier path: build it in the UI, then copy to text mode

1. Switch to standard mode and add a temporary copy of the column you want formatted.
2. Use the UI to configure conditional formatting on that temp column.
3. Switch back to text mode.
4. Copy the `styledef.case.0.*` lines from the temp column.
5. Paste them under your real column, updating the column index (`column.0`, `column.1`, etc.).
6. Delete the temp column.

This avoids hand-writing `styledef` syntax and ensures it's valid.

## Common patterns

### Color status values
Build the conditional formatting on a standard `status` column first, then copy the rules.

### Show an icon for overdue tasks
Use `true-image-url=` to point at an icon. Set `icon=true` on the column.

```
column.0.styledef.case.0.comparison.icon=true
column.0.styledef.case.0.comparison.true-image-url=/images/icons/warning.png
```

### Replace the cell value
```
column.0.styledef.case.0.comparison.truetext=OVERDUE
```

### Cell color based on comparison to another field
```
column.0.styledef.case.0.comparison.lefttype=field
column.0.styledef.case.0.comparison.leftmethod=plannedCompletionDate
column.0.styledef.case.0.comparison.righttype=field
column.0.styledef.case.0.comparison.rightmethod=projectedCompletionDate
column.0.styledef.case.0.comparison.operator=lt
column.0.styledef.case.0.comparison.true-bgcolor=FCE4E4
```

## Multiple rules

Rules are evaluated in order, lowest case number first. The first matching rule wins.

```
column.0.styledef.case.0.comparison...   # checked first
column.0.styledef.case.1.comparison...   # checked second
column.0.styledef.case.2.comparison...   # checked third
```

To add a default fallback, make the last case match anything that didn't match earlier.
