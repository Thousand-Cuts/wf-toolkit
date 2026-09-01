# 05 — Cross-Object References

## How Traversal Works

A calculated field on a custom form for Object A can reference fields on related objects by adding a traversal prefix. The direction matters.

### Child → Parent (supported)

A **task** calc field can reach its parent **project**:
```
{project}.{name}
{project}.{plannedRevenue}
{project}.{DE:Client Tier}
```

An **issue** calc field can reach its parent project or task:
```
{project}.{name}
{task}.{name}
```

A **task** calc field can reach the task owner or a related user:
```
{assignedTo}.{name}
{owner}.{firstName}
```

### Parent → Child (NOT supported)

A **project** calc field **cannot** reach down into its tasks or issues — these are collections, and collections are not accessible from calculated fields. Attempting to reference `{tasks}.{name}` on a project form will produce an error or blank.

**Workaround:** Use a Fusion scenario to aggregate child data and write the result to a custom field on the parent. The calc field on the project can then reference that written value.

**Verified 2026-09-01** on a sandbox tenant (sandbox, `WF_ENV_TYPE=sandbox`), v22.0. The rejection is at **save time**, not a silent blank: the `PUT /category/<id>` carrying the expression is refused outright and no `CategoryParameter` row is written.

```bash
# Setup: a throwaway PROJ-scoped form (catObjCode=PROJ) + displayType=CALC parameters.
# NOTE: Category create uses `catObjCode`, not `objCode` — `objCode=PROJ` fails with
#   'Cannot invoke "...CategoryObjTypesEnum.getFeature()" because "objTypeEnum" is null'

# Discriminator — downward reference into the child collection
PUT /attask/api/v22.0/category/<catID>
  updates={"categoryParameters":[{"parameterID":"<p>","displayOrder":1,
           "customExpression":"{tasks}.{name}"}]}
#   -> {"error":{"message":"Invalid Expression: \"{tasks}.{name}\" is not a
#       field in your system"}}
#   Read-back: categoryParameters count = 0. Nothing persisted.

# Negative control — identical PUT shape, identical form, upward reference
PUT /attask/api/v22.0/category/<catID>
  updates={"categoryParameters":[{"parameterID":"<p>","displayOrder":1,
           "customExpression":"{portfolio}.{name}"}]}
#   -> 200, row persists, isInvalidExpression: false
```

The control is what makes this load-bearing: same endpoint, same payload shape, same PROJ-scoped form, same `displayType=CALC` parameter type. Only the traversal direction differs, so the refusal is attributable to the downward reference rather than to a malformed request.

**Scope limits.** What is proven is that `{tasks}.{name}` is rejected on save on a PROJ-scoped form on one sandbox tenant at v22.0, while an upward reference on the same form is accepted. Not tested: other collection names (`{issues}`, `{documents}`, `{assignments}`), whether the UI form editor surfaces the same refusal or fails differently, and whether any collection is reachable via a non-collection singular alias. The "produce an error **or blank**" wording above is now settled on the error side for this case; no configuration was found that produces a silent blank instead.

### Sibling / Lateral References

A field can reference its own related objects (owner, portfolio, program, etc.) but not sibling records of the same type. A task cannot reach other tasks; a project cannot reach other projects.

## What Is Reachable

The rule: **a calc field can reference any object found in the "references" section of the object's API Explorer entry**. Navigate to `experienceleague.adobe.com` → API Explorer, select the object (e.g., Task), and look at the References tab to see what's traversable.

Common reference paths:

| On this form | Reachable parents/refs |
|---|---|
| Task | `{project}`, `{assignedTo}`, `{owner}`, `{createdBy}`, `{category}` |
| Issue (OPTASK) | `{project}`, `{task}`, `{assignedTo}`, `{owner}` |
| Project | `{owner}`, `{portfolio}`, `{program}`, `{sponsor}`, `{category}` |
| Portfolio | `{owner}` |
| Document | `{project}`, `{task}`, `{issue}` |

### Multi-hop traversal works — chains resolve past the first parent (verified 2026-08-06)

The table above lists the *first* hop, but traversal is not capped at one. A
two-hop chain resolves and stores a value:

```
{project}.{portfolio}.{name}      on an ISSUE form   ✅ accepted, stores a value
```

Verified live on a sandbox tenant (v17.0, 2026-08-06) by creating a
`dataType=TEXT` / `displayType=CALC` Parameter, attaching it to an `OPTASK`
Category via `PUT /category/<id>` with `updates={"categoryParameters":[…]}`, and
reading the value back off a freshly created issue:

| Expression on an OPTASK form | Result |
|---|---|
| `{project}.{portfolio}.{name}` | ✅ `isInvalidExpression: false`; value populated on create |
| `{project}.{name}` (one-hop control) | ✅ accepted |
| `{project:portfolio:name}` (negative control) | ❌ `Invalid Expression: "…" is not a field in your system` |
| `{project}.{zzzNotAField}` (negative control) | ❌ `Invalid Expression: "…" is not a field in your system` |

The two rejections are what make the acceptance meaningful: the validator
resolves **every** step of the chain, so a bogus step in the same position is
refused. Acceptance is therefore evidence the whole path resolved, not evidence
the validator is permissive.

Note this is a different surface from **report groupings**, which *are* capped at
two objects deep — don't carry that cap over to calc-field expressions.

> ⚠️ **Trap: on an issue, `{project}` is the REQUEST QUEUE project.** An issue in
> a request queue already has a project — the queue itself — so
> `{project}.{portfolio}.{name}` returns the *queue's* portfolio, which is
> identical for every request in that queue. It is **not** the portfolio of the
> project the request will later be converted into (that project does not exist
> yet). Verified 2026-08-06: a throwaway issue created on a request-queue project
> stored the queue's portfolio name, and five pre-existing issues on the same
> queue all resolved to the same portfolio. Negative control: an issue on a
> project with no portfolio returned `portfolio: null`.
>
> This makes the expression a plausible-looking wrong answer for the common ask
> "auto-populate the portfolio on the intake form." It returns a value, so it
> looks like it worked. For a requester-chosen portfolio, use a real dropdown
> field on the request form; for a portfolio derived at conversion, the
> assignment happens on the project after conversion (via the template), not on
> the issue.

_Not tested: whether chains longer than two hops resolve; UI-side rendering of
the stored value (this was verified through the API); recalculation behaviour on
the two-hop chain (the general staleness rule below was not re-tested)._

## Referencing Custom Fields on a Parent Object

Prefix `DE:` with the parent traversal — using **dotted-brace syntax** with separate braces around the traversal step and the field reference:
```
{project}.{DE:Client Name}
{project}.{DE:Approved?}
{project}.{DE:Region}
{program}.{DE:Choose Business Line}
```

### Syntax pitfalls (empirically confirmed 2026-05-26)

**Use separate braces, not colon-traversal.** The natural-looking colon syntax `{program:DE:Field}` is silently rejected with `Invalid Expression: "{program:DE:Field}" is not a field in your system`. Even bare built-in cross-object refs like `{program:name}` are rejected — the entire colon-traversal pattern is unsupported in calc-field expressions. Always use `{program}.{DE:Field}`.

| Syntax | Result |
|---|---|
| `{program}.{DE:Choose Business Line}` | ✅ Accepted |
| `{program:DE:Choose Business Line}` | ❌ Rejected — "is not a field in your system" |
| `{program:name}` | ❌ Rejected — colon-traversal not supported, even for built-in fields |
| `{program}.{name}` | ✅ Accepted (built-in cross-object) |
| `Program.DE:Field` | ❌ Rejected — `Program` not valid in this context |

**The `DE:` argument must be the source parameter's `name`, NOT its `label`.** When the two differ (a common case — a Parameter can be relabeled in the UI while keeping its internal `name`), only the `name` resolves. Empirical examples from a real tenant:

| Parameter `name` | Parameter `label` | Working expression |
|---|---|---|
| `Choose Markets` | `Choose Regions` | `{program}.{DE:Choose Markets}` ✅ — `{DE:Choose Regions}` ❌ |
| `Please provide a brief overview of this request` | `Brief overview of this project` | `{program}.{DE:Please provide a brief overview of this request}` ✅ |
| `MKT - Event Start Date` | `Event/Campaign Start Date` | `{program}.{DE:MKT - Event Start Date}` ✅ — `{DE:Event/Campaign Start Date}` ❌ |
| `Choose Business Line` | `Choose Business Line - this goes away` | `{program}.{DE:Choose Business Line}` ✅ |

To find the `name` of a custom field in this tenant: `GET /attask/api/v22.0/parameter/<paramID>?fields=name,label`. Don't rely on the in-UI label — names and labels diverge whenever a field gets relabeled, and the engine cares about the name.

**Hyphens, slashes, and other punctuation are fine in `name` references** — `{DE:MKT - Event Start Date}` parses cleanly. The earlier "labels with hyphens don't work" hypothesis is wrong; the real issue was always label-vs-name.

### External Lookup / WIDGET-displayType fields

EXTRNL and WIDGET-displayType source fields *can* be referenced via `{program}.{DE:NAME}` — but only when the source `name` resolves correctly. They were the trickiest class to debug because EXTRNL fields tend to live in custom forms where someone has renamed the label away from the name. Validate by `name`, not the UI label.

### Function names are case-sensitive

`CONCAT(...)` works; `Concat(...)` is rejected as "not a valid function." Same for `IF`, `ROUND`, `SUB`, `MUL`, `DIV`, etc. — uppercase only.

## Referencing a Property of an Internal Lookup Field on the Same Object

An **Internal Lookup** field (`displayType` `INTRNL` / `MULTINTRNL`) stores a *reference to a Workfront object*, not a string. A calc field on the same object can reach into that reference and pull one property off it — using the same dotted-brace form as parent traversal, with the `DE:` field itself as the traversal root:

<!-- UNVERIFIED -->
```
{DE:Project}.{ID}
{DE:Project}.{name}
```

Community report (thread in `## Sources`, best answer by ninoskuflic, 2026-07-26): this **replaces the legacy Typeahead child-reference form** `{DE:<typeahead field>:ID}` — the colon-inside-the-`DE:`-reference syntax. Consultants migrating a Typeahead picker to an Internal Lookup field must rewrite every calc field that reached a child property. Unverified because confirming that an expression resolves requires creating or validating a Parameter, which is a write; this routine is read-only. Also unconfirmed: the thread asserts the new form but nobody in it posted the rejection message for the old one, so "the legacy form stops working" is the asker's account, not a reproduced result.

**Why a dot works here — the stored value is an envelope.** Verified 2026-08-08 on `a sandbox tenant.workfront.com` (sandbox), v20.0: reading an `INTRNL` field with `refObjCode=USER` off seven portfolios via `GET /port/search?fields=ID,name,DE:spark451_primary_ae` returns a three-key envelope per record —

```json
{"ID": "69b2fc2a001cd2235ccccf3381accc9a", "name": "Julie Pretko", "objCode": "USER"}
```

The dotted suffix selects a key from that envelope, which is why `{ID}`, `{name}`, and `{objCode}` are the properties on offer. Same envelope documented for typed Typeahead fields in `../custom-forms/09-gotchas.md` § 30 — which is the reason the two field families ever shared a child-reference idiom.

**Version floor — `INTRNL` does not exist on v17.0.** Verified 2026-08-08 on the same tenant: `GET /param/metadata` returns a `displayType` enum of **12** values on **v17.0**, with no `INTRNL`/`MULTINTRNL`; **v20.0** returns 26 including both; **v22.0** returns 27 (adds `SNGLROLLUP`). A caller pinned to v17.0 — the toolkit's default until v0.41.0 — sees no Internal Lookup field at all, so this syntax has nothing to reference there; on the current v22.0 default the field type is visible. See `../api/14-api-version-drift.md`.

**Consistent with the colon-traversal ban above.** The 28 real calc expressions on that sandbox use dotted-brace traversal exclusively — 9 cross-object, e.g. `{program}.{DE:spark451_planned_segments}`, `{portfolio}.{name}`, `{queueTopic}.{name}` — and **zero** use any colon form. Verified 2026-08-08 via `GET /category/search?fields=categoryParameters:customExpression,categoryParameters:parameter:name,categoryParameters:parameter:displayType`. That same scan found zero in-the-wild uses of `{DE:x}.{y}`, so the sandbox corroborates the *shape* of the claim without exercising it.

## Multi-Object Forms and $$OBJCODE

When a custom form is attached to multiple object types (e.g., Projects AND Tasks), a single calculated field can contain different logic per object type using `$$OBJCODE`:

```
IF($$OBJCODE="PROJ",{plannedRevenue},IF($$OBJCODE="TASK",{project}.{plannedRevenue},"N/A"))
```

Common object codes:
- `PROJ` — Project
- `TASK` — Task
- `OPTASK` — Issue
- `PORT` — Portfolio
- `PRGM` — Program
- `USER` — User
- `DOCU` — Document
- `TMPL` — Template

## Recalculation Behavior on Cross-Object References

When a field on a **parent or related object** changes, the calculated field on the child does **not** automatically update. The child's stored value goes stale until:
1. The child object itself is edited and saved.
2. A user manually triggers **Recalculate Custom Expressions** from the More menu.
3. A bulk edit runs against the child records in a report.

This makes cross-object calculated fields suitable for relatively static data (client tier, region, program name) but unsuitable for frequently-changing values where fresh data is critical.

## Referencing Another Calc Field on the Same Object

```
{DE:Days Overdue}
{DE:Risk Score}
```

The referenced calc field must be on a form that is currently attached to the same object. If the form is detached, the reference returns blank.

## Calculated Field Reuse Across Forms

You can add the same calculated field to multiple custom forms (for different object types). However, the **calculation expression must be re-entered on each form** — the formula does not transfer automatically. If the same named field appears on two forms attached to the same object, the formulas on both forms must be identical, or Workfront will display a configuration error.

## Cross-references

- Internal Lookup / Typeahead field authoring, `refObjCode`, and the stored envelope: `../custom-forms/02-parameter-types.md`, `../custom-forms/09-gotchas.md` §§ 30, 33, 34.
- Which API version each `displayType` first appears in: `../api/14-api-version-drift.md`.

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/using-internal-lookup-field-in-calculated-field-251910` | the `{DE:<internal lookup>}.{ID}` child-property syntax and its legacy-Typeahead `{DE:field:ID}` predecessor — best answer by ninoskuflic, 2026-07-26 |
