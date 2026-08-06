# 01 — Object Model

Five linked objects make up a Workfront custom form. ObjCodes are empirically confirmed against a live production tenant v17.0, 2026-05-18 (`/<object>/metadata` responses).

```
              Category (CTGY)
                 │  (form metadata: name, objTypes[], description)
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
  CategoryParameter   ParameterGroup (PGRP)
  (CTGYPA — link;     (sections within the form, optional)
   NOT a top-level
   object)
       │
       ▼
  Parameter (PARAM)
  (the field: name, label, dataType, displayType, formatConstraint)
       │
       ▼ (for displayType=SLCT / CHCK / RDIO)
  ParameterOption (POPT)
  (label, value, displayOrder, isHidden)
```

## Category (CTGY)

A "form" in the UI. Confirmed fields:

| Field | Type | Notes |
|---|---|---|
| `ID` | string | Category GUID |
| `name` | string | Display name (UI-editable). Can contain `[` / `]` for our verification prefix. |
| `objTypes` | string[] | Target objCodes (PROJ, TASK, OPTASK, USER, ...). **Multi-objCode is supported but only via `updates=` JSON, not repeated form params.** |
| `catObjCode` | string | Read-only mirror of `objTypes[0]`. |
| `description` | string | Free text. |
| `categoryOrder` | int | UI display position. |
| `isActive` | boolean | Tenant-wide enable/disable flag. |
| `groupID` | string | Optional access scope. |
| `hasCalculatedFields` | boolean | Derived; true iff any linked Parameter is `displayType=CALC`. |
| `enteredByID`, `lastUpdatedByID`, `customerID` | string | System-managed. |
| `extRefID` | string | External integration reference. |

Forms are attached to records via the **child record's `categoryID` field** — not via a join table. Adding a form to 1,000 projects = 1,000 `categoryID` references on 1,000 project rows.

## Parameter (PARAM)

A field definition. Reusable across forms (linked via CategoryParameter).

| Field | Type | Notes |
|---|---|---|
| `ID` | string | Parameter GUID |
| `name` | string | **API-stable identifier; used in `DE:` filter syntax. Cannot contain `[`.** |
| `label` | string | UI display string. **Also cannot contain `[`**. |
| `dataType` | string | Enum — see `02-parameter-types`. TEXT / NMBR / DATE / CURC / RICH / WIDGET. |
| `displayType` | string | Enum — see `02-parameter-types`. TEXT / SLCT / CHCK / RDIO / TXTA / MULT / TYAH / RICH / CALC / WIDGET / DTXT. |
| `formatConstraint` | string | Free-form render hint (CURRENCY / PERCENT / INTEGER / DECIMAL / DATE / TEXTAREA). |
| `displaySize` | int | UI width hint. |
| `description` | string | **End-user-facing.** Renders under the field label as "Instructions" in the form-fill UI. **Do not write changelogs, action-item IDs, audit notes, or skill-internal metadata here — those leak to every consultant filling out the form.** Leave blank unless the consultant explicitly wants user-facing helper text. |
| `isRequired` | boolean | Whether the UI enforces non-empty. |
| `refObjCode` | string | For USER/GROUP pickers. |
| `extRefID` | string | External integration reference. |
| `fieldDefinition` | map | **Read-only** (PUT does not persist). System-set for some derived parameters. |
| `customerID`, `lastUpdatedByID` | string | System-managed. |

Notably **NOT on Parameter:**

- `calculation` or `formula` — this lives on **CategoryParameter** (per-form-attachment, not per-parameter).
- `displayLogic` — not a field on Parameter itself; it lives on **Category** as the `categoryCascadeRules` collection (CTCSRL/CTCSRM), REST-accessible via GET-modify-PUT on the parent Category. See `07-display-logic`.
- `defaultValue` — not directly settable; `fieldDefinition` is read-only.

## CategoryParameter (CTGYPA)

The link between a Category and a Parameter, plus per-attachment configuration (display order, required flag, formula body).

**Critical: CategoryParameter is NOT a top-level object.** Direct POST to `/categoryParameter` returns `"CTGYPA is not a top level object and can't be requested directly"`. CategoryParameter rows are created via **PUT on the parent Category** with a nested `categoryParameters` collection:

```http
PUT /attask/api/v17.0/category/<categoryID>
Content-Type: application/x-www-form-urlencoded

updates={"categoryParameters":[
  {"parameterID":"<p1>","displayOrder":1,"isRequired":false},
  {"parameterID":"<p2>","displayOrder":2,"customExpression":"1+1"}
]}
```

**Composite key:** `CategoryParameter.ID` is `<categoryID>_<parameterID>` (literal underscore concatenation). One CategoryParameter row per (Category, Parameter) pair — same Parameter cannot be linked to the same Category twice.

| Field | Type | Notes |
|---|---|---|
| `ID` | string | Composite `<categoryID>_<parameterID>`. |
| `categoryID` | string | Parent form. |
| `parameterID` | string | Linked field. |
| `parameterGroupID` | string | Section assignment (null = ungrouped). |
| `displayOrder` | int | Position within the form/group. |
| `isRequired` | boolean | UI requires non-empty on this form. |
| `customExpression` | string | Formula body (for CALC-displayType Parameters). |
| `rawCustomExpression` | string | Canonical form of the formula (mostly mirrors `customExpression`). |
| `isInvalidExpression` | boolean | Server-set; true if formula didn't parse. |
| `hideFormulaFromDescription` | boolean | UI: hide the formula from the field's help text. |
| `updateCalculatedValues` | boolean | Force re-compute on attached records. |
| `securityLevel`, `viewSecurityLevel` | enum | Per-field access; tenant-specific. |
| `isJournaled`, `journaledObjCodes`, `rowShared` | derived | System-set flags. |

PUTting `categoryParameters:[...]` is a **collection-replace** — entries not in the new list disappear. To add a single field, GET the existing collection first, append, and PUT the full list.

## ParameterGroup (PGRP)

Optional "section" within a form (a Category). Top-level object — direct POST works.

| Field | Type | Notes |
|---|---|---|
| `ID` | string | Group GUID |
| `name` | string | Section header text |
| `description` | string | Optional |
| `displayOrder` | int | Section position |
| `isDefault` | boolean | The "no section" default group |
| `extRefID` | string | External integration reference |
| `customerID`, `lastUpdatedByID` | string | System-managed |

## ParameterOption (POPT)

One row per option on a `SLCT` / `CHCK` / `RDIO` parameter. Top-level object — direct POST works (and bulk-POST via `?method=POST` works up to 100 rows per call).

| Field | Type | Notes |
|---|---|---|
| `ID` | string | Option GUID |
| `parameterID` | string | Parameter this option belongs to |
| `label` | string | UI display string. **Safe to rename.** |
| `value` | string | Stored value on records. **Unsafe to rename — orphans every record's stored value.** See `09-gotchas`. |
| `displayOrder` | int | **Integer-only.** Decimals rejected with NumberFormatException. |
| `isHidden` | boolean | UI visibility toggle |
| `isDefault` | boolean | Pre-selected on new records |
| `extRefID` | string | External integration reference |

## Why this matters for cross-tenant clone

Every `*ID` field above is tenant-specific. The clone walker (`form_sanitizer.py`) must:

1. **Drop** customerID, ownerID-style identity fields.
2. **Remap** categoryID / parameterID references — including inside displayLogic if/when v2 reaches it.
3. **Recognise composite CategoryParameter IDs** (`<catID>_<paramID>`) — these decompose into two source IDs that both need remapping.

See `06-clone-and-adapt-recipe`.

## Cross-references

- `02-parameter-types` — full enum for `dataType` and `displayType`
- `07-display-logic` — the `categoryCascadeRules` (CTCSRL/CTCSRM) shape on Category, REST-accessible via GET-modify-PUT
- `09-gotchas` — value-rename destruction, `[` rejection on Parameter
