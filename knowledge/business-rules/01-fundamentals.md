# 01 — Business Rules Fundamentals

## What Is a Business Rule?

A **business rule** is a system-level constraint that runs an `IF()` formula whenever a user (or the API) tries to **create, edit, or delete** an object. It enforces data integrity at save time — blocking an action, or (on the top package) triggering an automation — without any custom code or Fusion scenario.

A rule is bound to exactly **one object type** and **one trigger**. The formula uses the same expression language as calculated custom fields.

## Where to Create Them

**Setup → System → Business Rules → New Business Rule.** Each rule has:

- **Name** and **Description**
- **Is active** — Yes/No toggle (build inactive, test, then activate)
- **Object** — the record type the rule governs (chosen when the rule is created)
- **Trigger** — On object creation / On object edit / On object delete
- **Formula** — the `IF()` expression (right-hand panel offers Expressions, Fields, and function categories)

## Packaging, Licensing, and Access

| Requirement | Detail |
|---|---|
| **Who can create** | System administrators only |
| **License to be affected** | Standard license or higher (rules apply to those users) |
| **Validation rules** | **Ultimate** or **Workflow Ultimate** package |
| **Automation rules** | **Workflow Ultimate** package only |

If the tenant is not on Ultimate / Workflow Ultimate, business rules are unavailable. Fall back to required fields + display logic on the custom form, or a Fusion scenario.

## Supported Object Types

Business rules can target these object types:

Project, Task, Issue/Request, Portfolio, Program, Document, Expense, User, Company, Iteration, Billing Record, Group, Risk, Rate Card, Assignment, Job Role, Resource Pool, Time Off, Hour, Template.

The Fields picker for a rule is **limited to fields on that object type** (plus reachable parent references, following calc-field cross-object rules).

## The Three Triggers

| Trigger | Fires when a user attempts to… | Use for |
|---|---|---|
| **On object creation** | create the object | required-at-creation checks, blocking creation in a window |
| **On object edit** | edit the object | preventing a field change, locking by status, guarding transitions |
| **On object delete** | delete the object | blocking deletion of objects that should be retained |

"Prevent someone from **changing** X" is always **On object edit** — and needs `$$BEFORE_STATE` change detection (see `02-formula-syntax.md`).

## Validation vs. Automation Rules

| | **Validation** | **Automation** |
|---|---|---|
| Formula | `IF(condition, "message")` | `IF(condition, true)` |
| Effect when condition is TRUE | **Blocks** the action, shows the message | **Triggers an automation** (share the object, attach a custom form) |
| Message | Required | Not used |
| Package | Ultimate or Workflow Ultimate | Workflow Ultimate only |

`IF(true, true)` runs the automation on every matching action; `IF({status}="APR", true)` runs it only when the condition holds.

## Priority vs. Access Levels and Sharing

**Access levels and object sharing have higher priority than business rules.** A rule can only restrict actions a user could otherwise perform — it cannot grant access, and it does not override permissions. There is **no built-in "exempt admins" switch**: system administrators are subject to active rules just like anyone else. To exempt a specific person, encode it in the formula (e.g. `&& $$USER.ID != "641f...`).

## Multiple Rules

Only **one business rule per object per trigger** is allowed. Put several checks in one rule with nested `IF()`. If more than one *rule* applies to an action (e.g. across different triggers), **all applicable rules run, in no guaranteed order**.

## Scope of Enforcement

Business rules apply to **creating, editing, and deleting objects through the API as well as in the Workfront interface** — including Fusion and bulk-update scripts. Scope UI-only vs API-only with `$$ISAPI` / `!$$ISAPI` (see `02-formula-syntax.md`).

## Sandbox First

Always configure and test business rules in a **sandbox or Preview** environment and verify them thoroughly before enabling in production. A miswritten validation rule can block legitimate work (including integrations) tenant-wide the moment it is activated.

## Choosing the Right Enforcement Tool

| Need | Tool |
|---|---|
| Block a save / create / delete on a condition | **Business rule (validation)** |
| Auto-share or auto-attach a form on a condition | **Business rule (automation)** |
| Show, hide, or require a field on the form UI | Custom-form **display/skip logic** (`workfront-custom-forms`) |
| Compute and store a derived value | **Calculated field** (`workfront-calc-fields`) |
| Multi-step side effects, external calls, scheduled writes | **Fusion** (`workfront-fusion`) |
