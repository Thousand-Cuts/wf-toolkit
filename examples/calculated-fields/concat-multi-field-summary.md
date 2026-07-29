# Calculated Field Example: CONCAT Multi-Field Summary

Apply to a **Project** or **Task** custom form. Creates a single stored text field that surfaces multiple pieces of information as a human-readable summary — useful as a searchable label or a combined view column.

## Basic project summary

**Format:** Text

```
CONCAT({name}," | Owner: ",{owner}.{name}," | Status: ",{status}," | Due: ",{plannedCompletionDate})
```

Example output: `Website Redesign | Owner: Jane Smith | Status: CUR | Due: 2026-06-30`

## Summary with conditional region append

**Format:** Text

```
CONCAT({name}," | ",{owner}.{name},IF(!ISBLANK({DE:Region}),CONCAT(" | ",{DE:Region}),""))
```

Appends region only when filled in — no trailing separator for records without a region.

## Task summary referencing parent project

**Format:** Text

```
CONCAT({project}.{name}," > ",{name}," | Assigned: ",{assignedTo}.{name}," | Due: ",{plannedCompletionDate})
```

Example output: `Website Redesign > Write Homepage Copy | Assigned: Alex Jones | Due: 2026-05-20`

Requires this field to be on a **Task** custom form. The `{project}.{name}` traversal reaches the parent project.

## Reference number + title combined key

**Format:** Text

```
CONCAT({referenceNumber},": ",{name})
```

Creates a stable reference like `PRJ-4521: Website Redesign`. Useful when Workfront objects need to be referenced in external tools.

## Status-aware summary with emoji

**Format:** Text

```
CONCAT(SWITCH({status},"CPL","✅","CUR","🟢","ONH","⏸","PLN","⏳","❓")," ",{name}," | ",{owner}.{name})
```

Example output: `🟢 Website Redesign | Jane Smith`

## Notes

- `CONCAT` accepts any number of arguments separated by commas.
- String literals (separators, labels) must use straight double quotes `"`.
- `{plannedCompletionDate}` in a CONCAT returns the raw ISO date string. For formatted display, either accept the ISO string or store the formatted value with a separate Text-format field.
- This field type is excellent as a source for report `valuefield=DE:Project Summary` columns — because it is stored, it can be filtered and conditionally formatted, unlike a `valueexpression` column.
