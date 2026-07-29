# 02 — Business Rule Formula Syntax

## Block-on-True Semantics

A **validation** rule's formula is:

```
IF( <condition that describes the BAD state> , "message" )
```

- Condition **TRUE** → the create/edit/delete is **blocked** and the message is shown.
- Condition **FALSE** → the action proceeds.

Write the condition to describe the state you want to **prevent**, never the state you want to allow. This is the number-one authoring mistake.

An **automation** rule uses `true` as the second argument instead of a message: `IF(condition, true)` — condition true → the configured automation fires.

## Same Function Language as Calculated Fields

The property/function syntax is identical to a calculated custom field. Do not restate it here — see the `workfront-calc-fields` skill and `knowledge/calculated-fields/` for the full reference. Key carry-overs:

- `&&` = AND, `||` = OR, `!` = NOT
- `!ISBLANK(...)` never `NOTBLANK(...)`; `!(...)` never `NOT(...)`
- `CONCAT(...)` for string building; `IF`, `IFIN`, `CASE`, `SWITCH`, `DATEDIFF`, `MONTH`, `DAYOFMONTH`, etc. all available
- Keep the **condition on a single line**

## Referencing Fields

- Native fields: `{fieldName}` using the internal name, e.g. `{status}`, `{name}`, `{plannedStartDate}`, `{plannedCompletionDate}`.
- Custom fields: prefix with `DE:` → `{DE:Vendor Name}`.
- Enum comparisons use the **stored code**, not the display label: `{status} = "CPL"` (Complete), `{taskConstraint} = "MSO"` (Must Start On).
- Insert tokens from the editor's **Fields** panel so names/codes match the tenant. The picker is limited to fields on the rule's object type.
- **Finding enum/status codes:** the codes differ per object and are not always obvious (Project Complete = `CPL`; Issue/Task codes differ and custom statuses have tenant-specific codes). Look them up in the **API Explorer** at `experienceleague.adobe.com` (the object's `status`/enum field), or query the object over REST via the `workfront-api` skill. Do not guess a status code — a wrong code makes the rule silently never fire.

## Wildcards

| Wildcard | Meaning | Available on |
|---|---|---|
| `$$BEFORE_STATE.{field}` | the field's value **before** this edit | edit trigger only |
| `$$AFTER_STATE.{field}` | the field's value **after** this edit (same as bare `{field}`) | create + edit |
| `$$ISAPI` | condition true only when the write comes through the **API** (incl. Fusion) | all triggers |
| `!$$ISAPI` | enforce **UI only**, let API/Fusion/integration writes through | all triggers |
| `$$TODAY` | current date | all triggers |
| `$$USER` | the acting user (e.g. `$$USER.ID`, for exemptions) | all triggers |
| `$$OBJCODE` | the object type code of the record | all triggers |

### Change detection

To fire only when a field actually changed on this save:

```
{plannedStartDate} != $$BEFORE_STATE.{plannedStartDate}
```

Without `$$BEFORE_STATE`, an edit rule evaluates on **every** save, not only when the watched field changed.

### UI vs. API scoping

Because rules also fire on API and Fusion writes, add `!$$ISAPI` to keep a rule from breaking your own automations, or `$$ISAPI` to enforce only against programmatic writes:

```
IF({status} = "CPL" && $$ISAPI, "You cannot edit completed projects through the API.")
```

## The Message Parameter

- Plain string shown to the user; make it explain **what went wrong and how to fix it**.
- Supports a **markdown link**: `"You cannot add a project in November. [Learn more](https://intranet/policy)"`.
- Wrap in `TRANSLATE(...)` to serve the user's locale: `IF({status}="CPL", TRANSLATE("You cannot edit completed projects."))`.

## One Rule Per Object Per Trigger — Nesting

Only one rule exists per object/trigger, so combine checks with nested `IF()`. The **first** condition that is true supplies the message, so order the most important/strictest check first:

```
IF($$AFTER_STATE.{status}="CPL", "You cannot edit a completed project.",
IF(MONTH({plannedCompletionDate})=3, "You cannot edit a project due in March."))
```

## Worked Examples (from Adobe docs)

```
IF(MONTH($$TODAY) = 2 && DAYOFMONTH($$TODAY) >= 22, "You cannot add new expenses during the last week of February.")

IF({status} = "CPL" && {name} != $$BEFORE_STATE.{name}, "You cannot edit the project name.")

IF(true, true)                 -- automation: always fire
IF({status} = "APR", true)     -- automation: fire only when approved
```
