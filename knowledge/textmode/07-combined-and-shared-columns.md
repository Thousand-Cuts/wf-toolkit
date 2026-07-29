# 07 — Combined and Shared Columns

## What a combined column is

A combined column visually merges multiple text mode columns into a single cell in the report. Common uses:
- Show a project name with the owner name beneath it
- Combine multiple custom field values into one cell with labels
- Build "summary card" style cells

## The shared-column pattern

**`valueformat=HTML` is MANDATORY on every column in a sharecol group, including separator and label-only columns.** Without it, the cell EXPORTS BLANK from Workfront — the in-product view will render visibly, but the Excel/CSV/PDF export drops the cell entirely. This is an export-time failure, not a render-time one, so it's easy to miss in pre-ship testing. Always set `valueformat=HTML` on every sharecol column. Source: Adobe `custom-view-samples/view-merge-columns`.

Use `sharecol=true` on every sub-column EXCEPT the last one. The first column in the group is the "anchor"; the rest share its cell.

### Basic structure (3 sub-columns combined)
```
column.0.valuefield=name
column.0.valueformat=HTML
column.0.textmode=true
column.0.sharecol=true
column.0.displayname=Project Info

column.1.valuefield=owner:name
column.1.valueformat=HTML
column.1.textmode=true
column.1.sharecol=true

column.2.valueexpression=CONCAT("Due: ",{plannedCompletionDate})
column.2.valueformat=HTML
column.2.textmode=true
```

Note: the LAST column (`column.2`) omits `sharecol=true`. That's how Workfront knows the group ends.

## Gotcha: inline HTML in `valueexpression` usually renders as literal text — but not always

The default rule:

```
column.0.valueexpression=CONCAT("<b>Owner:</b> ",{owner}.{name})
column.0.valueformat=HTML
column.0.textmode=true
```

…the output is the literal string `<b>Owner:</b> Jane Doe` — the `<b>` tags do NOT render. `valueformat=HTML` controls how the VALUE TYPE is rendered (date as date, number as number), NOT whether the string is parsed as HTML. For most cells, use the dedicated-label-sub-column pattern in the next section.

### Exception: inside a shared-column group, HTML in `valueexpression` DOES render

When ALL of these are set on the column, Workfront flows the cell through the HTML pipeline and the expression's HTML output renders as markup, not literal text:

- `sharecol=true`
- `textmode=true`
- `valueformat=HTML`

This is the load-bearing combination for the **avatar chip pattern** below. It's also the only way to inject an `<img>`, `<span>` chip, or conditional HTML wrapper next to a data field inside a combined cell. Confirmed against known-good production reports across multiple tenants (2026-05-14).

If you find yourself wanting "an icon plus a field value in the same cell", reach for this pattern — don't reach for the label-sub-column pattern, which only injects static HTML.

### Sub-exception: group headers (`group.N.*`) do NOT render HTML

The HTML pipeline is **column-scoped**. Group headers have no `sharecol` concept — that flag is column-only. A `group.N.valueexpression` returning `<span>` or `<img>` markup renders as **literal text** in the group header, regardless of `valueformat=HTML` or `textmode=true`. You will see the raw `<span style='…'>JD</span>Jane Doe` markup spelled out in the header bar, not a chip.

If you want an avatar associated with a grouping value, you have two options:

1. **Native chip** — `group.N.valuefield=<rel>:name` + `group.N.linkedname=direct`. Whether the photo renders depends on tenant version; in many tenants the header shows the name as plain text without an avatar.
2. **Move the chip to the view** — keep the group header plain text and put the avatar chip valueexpression on the FIRST column of the view's combined cell. Every row in a group has the same grouping value, so the chip repeats per row inside the group — but it's reliably rendered.

The "move it to the view" pattern is the working answer for "grouped-by-person with avatars". Verified against Client E 2026-05-14: a `group.0.valueexpression` returning the chip markup rendered `Assignee: <span style='…'>JD</span>Jane Doe (1)` in every group bar until the UIGB was reverted to a plain `valuefield` and the chip moved into the view.

## Avatar chip pattern (user fields inside a combined column)

Native user-chip rendering with avatar fires only on standalone user columns (no `valueformat=HTML`, no `textmode=true`, just `valuefield=<rel>:name` + `linkedname=direct`). The moment you put a user field inside a `sharecol=true valueformat=HTML` group, Workfront's HTML pipeline takes over and the native chip is suppressed.

To get an avatar chip inside a combined cell, emit the chip yourself via the `valueexpression` exception above. The proven pattern (per relation `owner` / `sponsor` / `assignedTo` / etc.):

```
column.N.valueexpression=IF(ISBLANK({owner}.{avatarDate}),CONCAT("<span style='display:inline-block;width:24px;height:24px;border-radius:50%;background:#6b7280;color:#fff;text-align:center;line-height:24px;font-size:11px;font-weight:600;vertical-align:middle;margin-right:6px'>",SUBSTR({owner}.{firstName},0,1),SUBSTR({owner}.{lastName},0,1),"</span>",{owner}.{name}),CONCAT("<img src='/internal/user/avatar?ID=",{ownerID},"' alt='' style='display:inline-block;width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:6px;object-fit:cover'>",{owner}.{name}))
column.N.valueformat=HTML
column.N.textmode=true
column.N.linkedname=owner
column.N.sharecol=true
```

Mechanics:

- `ISBLANK({owner}.{avatarDate})` distinguishes users who have uploaded a photo from those who have not.
  - **Has avatar →** emit `<img src='/internal/user/avatar?ID=<userID>' ...>`. The `/internal/user/avatar` route is Workfront's internal endpoint that returns the uploaded photo.
  - **No avatar →** emit a 24px `<span>` with the user's initials (first letter of first name + first letter of last name) on a neutral gray background. This matches the Workfront UI's native initials chip.
- `{ownerID}` (or `{sponsorID}` / `{assignedToID}`) is the foreign-key field that gets interpolated into the URL. Use the FK directly — `{owner}.{ID}` also works but is one extra hop.
- `linkedname=owner` (not `direct`) makes the whole cell clickable to the user's profile quick-view. Match the relation name to the user field — `linkedname=sponsor` for sponsor, `linkedname=assignedTo` for assignees.
- Keep this column as ONE column in the shared group — don't break it into separate img + name sub-columns. Workfront re-flows the cell as a single HTML run.
- `valueexpression` must stay on a single line — see the single-line rule in `SKILL.md`.

To swap the user relation, search-and-replace `owner` → `<other-relation>` and `ownerID` → `<other-relation>ID` everywhere in the expression. Common substitutions: `sponsor` / `sponsorID`, `assignedTo` / `assignedToID`, `enteredBy` / `enteredByID`, `manager` / `managerID`.

### Initial-only chip (no photo lookup)

If avatar photos are not enabled in your instance or you prefer a uniform look, simplify the expression to always render the initials chip:

```
column.N.valueexpression=CONCAT("<span style='display:inline-block;width:24px;height:24px;border-radius:50%;background:#6b7280;color:#fff;text-align:center;line-height:24px;font-size:11px;font-weight:600;vertical-align:middle;margin-right:6px'>",SUBSTR({owner}.{firstName},0,1),SUBSTR({owner}.{lastName},0,1),"</span>",{owner}.{name})
column.N.valueformat=HTML
column.N.textmode=true
column.N.linkedname=owner
column.N.sharecol=true
```

### Style customisation

The inline styles in the `<span>` and `<img>` are baseline values that match Workfront's native chip dimensions. Tweak them if the report's brand calls for different colours or sizes — `background: <hex>` for the initials chip, `width:` / `height:` to resize. Keep `border-radius:50%` for a circle.

## The correct way to get bold labels and line breaks

Use **dedicated label sub-columns** with `column.N.value=` for the static HTML, alternating with data sub-columns that pull the actual value.

### Pattern: "Owner: Jane Doe" with "Due: 2026-05-15" beneath
```
column.0.value=<b>Owner:</b>&nbsp;
column.0.valueformat=HTML
column.0.textmode=true
column.0.width=1
column.0.sharecol=true
column.0.displayname=Project Info

column.1.valuefield=owner:name
column.1.valueformat=HTML
column.1.textmode=true
column.1.sharecol=true

column.2.value=<br><b>Due:</b>&nbsp;
column.2.valueformat=HTML
column.2.textmode=true
column.2.width=1
column.2.sharecol=true

column.3.valuefield=plannedCompletionDate
column.3.valueformat=shortAtDate
column.3.textmode=true
```

Key points:
- `column.N.value=` (not `valuefield` or `valueexpression`) is used for the static HTML labels
- `width=1` on the label sub-columns makes them invisible structurally — they exist only to inject HTML
- Use `&nbsp;` for a non-breaking space and `<br>` for a line break
- All sub-columns need `textmode=true valueformat=HTML`
- Last sub-column omits `sharecol=true`

## Common combined column patterns

### Two-line cell: Name on top, custom field below
```
column.0.valuefield=name
column.0.valueformat=HTML
column.0.textmode=true
column.0.sharecol=true
column.0.displayname=Project

column.1.value=<br>
column.1.valueformat=HTML
column.1.textmode=true
column.1.width=1
column.1.sharecol=true

column.2.valuefield=DE:Region
column.2.valueformat=HTML
column.2.textmode=true
```

### Multiple labeled fields on separate lines
```
column.0.value=<b>Owner:</b>&nbsp;
column.0.valueformat=HTML
column.0.textmode=true
column.0.width=1
column.0.sharecol=true
column.0.displayname=Details

column.1.valuefield=owner:name
column.1.valueformat=HTML
column.1.textmode=true
column.1.sharecol=true

column.2.value=<br><b>Sponsor:</b>&nbsp;
column.2.valueformat=HTML
column.2.textmode=true
column.2.width=1
column.2.sharecol=true

column.3.valuefield=sponsor:name
column.3.valueformat=HTML
column.3.textmode=true
column.3.sharecol=true

column.4.value=<br><b>Due:</b>&nbsp;
column.4.valueformat=HTML
column.4.textmode=true
column.4.width=1
column.4.sharecol=true

column.5.valuefield=plannedCompletionDate
column.5.valueformat=shortAtDate
column.5.textmode=true
```

## Conditional formatting + shared columns

Conditional formatting on a shared column group must be applied to the **column BEFORE the shared one** — i.e., the first column in the group. Rules placed on later sub-columns are silently ignored.

If you need formatting on a value that's deep in a shared group, restructure so that value is the first (anchor) column.
