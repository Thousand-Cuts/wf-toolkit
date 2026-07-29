# 01 — Calculated Field Fundamentals

## What Is a Calculated Field?

A **calculated custom field** (also called "calculated custom data") is a field of type **Calculated** on a Workfront custom form. When a user opens or saves an object that has the form attached, the field's stored value is derived from an expression you write in the form editor rather than entered by hand.

Calculated fields **persist as stored values on the record**. This is the key distinction from `valueexpression` columns in text-mode reports, which compute at render time and are never saved.

## Where to Find Them

1. Navigate to **Setup → Custom Forms → Forms**.
2. Open or create a custom form, then drag the **Calculated** field type onto the canvas.
3. Set Label, Instructions, Format, and Permissions, then open the **Calculation** editor to enter your expression.

The form can be attached to Projects, Tasks, Issues, Portfolios, Programs, Users, Documents, and many other object types.

## Format Types

You must choose a format before saving — **the format cannot be changed after the form is first saved**. Choose carefully.

| Format | What it stores | When to use |
|---|---|---|
| **Text** | String | Status labels, concatenated summaries, conditional text output, emoji-decorated labels |
| **Number** | Numeric (decimal) | Counts, differences, ratios, percentages expressed as raw numbers |
| **Currency** | Numeric with currency symbol | Budget variances, cost calculations, revenue deltas |
| **Date** | Date only (no time) | Deadline calculations, date math results where time is irrelevant |
| **Date/Time** | Date + time | Full timestamp calculations; note UTC implications (see below) |

> **Note on Percent:** The standard Workfront custom form field editor offers Text, Number, Currency, Date, and Date/Time as format options. Workfront Planning adds a Percent format, but it is not confirmed as a standard option in the classic custom form editor. If you need a percent display, use **Number** format and multiply by 100, or use a **Text** field and CONCAT the `%` symbol.

> **UTC Warning:** Any calculation that uses `$$TODAY` or `$$NOW`, or that omits a time portion, is evaluated against UTC, not the user's local timezone. If date results appear one day off for users in non-UTC timezones, this is the cause. Document-level advice: avoid `$$TODAY` in calc fields when date-boundary precision matters across timezones.

## Calculation Timing

Understanding when values recalculate is essential — stale data is the number-one gotcha with calculated fields.

| Trigger | Result |
|---|---|
| A **directly referenced field** on the same object is edited | Calculated field **updates automatically** |
| A field on a **referenced parent or related object** changes | Calculated field **does NOT update automatically** — value goes stale |
| A user saves the object or the custom form | Calculated field **recalculates** |
| An admin/user selects **Recalculate Custom Expressions** from the object's More (⋯) menu | Field **recalculates on that object** |
| Bulk edit via a report | **Recalculates all selected objects** — best method for mass refresh |

**Implication:** Never rely on a calculated field for "today minus due date" logic if the date is on a parent object — use a `valueexpression` column in a report instead (it always reflects the current moment).

## Can Calc Fields Reference Other Calc Fields?

Yes. A calculated field can reference another calculated custom field on the same object using `{DE:Other Field Name}`. However:

- The referenced calc field must exist on a form **attached to the same object**.
- If the source calc field is stale, the referencing field inherits that stale value.
- **Transitive updates are not guaranteed.** If Field A references Field B, and Field B references a native field that changes, Field A will only refresh when B has already refreshed — which requires a recalculate trigger.
- Adobe docs note that transitive dependency refresh behavior is not explicitly guaranteed for classic calculated fields (it is being improved in Workfront Planning, but that is a separate product). Treat chained calc fields as best-effort refresh, not guaranteed real-time propagation.

## Calc Fields vs. valueexpression Columns vs. API Computations

See `08-vs-textmode-and-api.md` for a full decision matrix. Quick summary:

| | Calculated Field | valueexpression Column | API Computation |
|---|---|---|---|
| Stored on record | Yes | No | Depends |
| Uses $$TODAY accurately | Risky (stale on cross-ref) | Yes — always current | Yes |
| Groupable / chartable | Yes | Not directly | Depends |
| Conditional formatting in UI | Yes (via native cond format on field) | No | N/A |
| Can be filtered in reports | Yes (via `valuefield=DE:...`) | No | Depends |
