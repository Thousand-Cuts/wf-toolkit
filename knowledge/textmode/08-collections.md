# 08 — Collections

## What a collection is

A collection represents a **one-to-many** relationship. Examples:
- A project's tasks (one project → many tasks)
- A task's assignments (one task → many assignments)
- A project's documents

A regular `valuefield` lookup gives you a single value. A collection gives you a list of values from related records.

## When to use a collection

Use a collection when you want to:
- Show ALL assignees of a task in one cell
- List ALL custom forms attached to a project
- Show ALL roles assigned to a project

If you only need ONE value (the primary assignee, the first document), use `valuefield` or `valueexpression`, not a collection.

## Collection syntax

```
column.0.listmethod=nested(assignments).lists
column.0.type=iterate
column.0.listdelimiter=,
column.0.listdelimiterend=
column.0.valuefield=assignedTo:name
column.0.displayname=Assignees
column.0.textmode=true
```

Key directives:
- `listmethod=nested(COLLECTIONNAME).lists` — names the collection on the parent object
- `type=iterate` — required; tells Workfront to loop through the collection
- `listdelimiter` — string between items (often `,` or `<br>`)
- `listdelimiterend` — string at the very end (often empty or `.`)
- `valuefield` — the field to pull from each collection item

## Collection valueexpression

You can use `valueexpression` inside a collection, but with caveats. Pattern:

```
column.0.listmethod=nested(projectUsers).lists
column.0.type=iterate
column.0.listdelimiter=<br>
column.0.valueexpression=IF({roleID}="SPECIFIC_ROLE_ID",{name},"")
column.0.valueformat=HTML
column.0.textmode=true
```

This lists only the users assigned to a specific role on the project.

**Watch out:** some collection types don't support `valueexpression` reliably. If you see blank output, switch to `valuefield`.

## Critical limitations

Collections **cannot**:
- Be **sorted** (the items appear in Workfront's default order)
- Have **conditional formatting** applied
- Be made **clickable** with `linkedname=direct`

If you need any of those, you cannot use a collection. Use a related report or a calculated custom field instead.

## Common collection patterns

### All assignees of a task
```
column.0.listmethod=nested(assignments).lists
column.0.type=iterate
column.0.listdelimiter=, 
column.0.valuefield=assignedTo:name
column.0.displayname=Assignees
column.0.textmode=true
```

### Assignees, each on a new line
```
column.0.listmethod=nested(assignments).lists
column.0.type=iterate
column.0.listdelimiter=<br>
column.0.valuefield=assignedTo:name
column.0.valueformat=HTML
column.0.displayname=Assignees
column.0.textmode=true
```

### All documents on a project
```
column.0.listmethod=nested(documents).lists
column.0.type=iterate
column.0.listdelimiter=<br>
column.0.valuefield=name
column.0.valueformat=HTML
column.0.displayname=Documents
column.0.textmode=true
```

### Only users with a specific role
```
column.0.listmethod=nested(projectUsers).lists
column.0.type=iterate
column.0.listdelimiter=<br>
column.0.valueexpression=IF({roleID}="ROLE_ID_HERE",{name},"")
column.0.valueformat=HTML
column.0.displayname=Approvers
column.0.textmode=true
```

Note: this will produce blank lines for non-matching users because the IF returns an empty string. There's no clean way to skip them entirely in a collection.

## Common collection method names

These vary by object. A few common ones:

### On Project
- `nested(tasks).lists`
- `nested(assignments).lists` (where applicable)
- `nested(documents).lists`
- `nested(projectUsers).lists`
- `nested(milestones).lists`
- `nested(issues).lists`

### On Task
- `nested(assignments).lists`
- `nested(predecessors).lists`
- `nested(documents).lists`

### On User
- `nested(roles).lists`
- `nested(teams).lists`

Always verify the exact name in the API Explorer — collection names use camelCase.

## Collections that hang off a *related* object

`listmethod` is not restricted to collections on the report's own base object. A **dotted path inside a single `nested(...)`** walks a relation first, then names a collection on whatever it lands on:

```
listmethod=nested(resolveProject.tasks).lists
```

<!-- UNVERIFIED -->
On an **Issue** report that iterates the tasks of the project the issue resolved into (`OPTASK` → `resolveProject` → the project's `tasks`). This is a third form alongside the two `reports/07-view-patterns.md` § 6 records for the JSON wrapper:

| Form | Meaning |
|---|---|
| `nested(<collection>).lists` | a collection directly on the base object |
| `nested(<rel1>).nested(<rel2>).lists` | chained `nested()` calls |
| `nested(<rel>.<collection>).lists` | walk one relation, then take a collection on it |

Practical consequence: you do **not** have to rebase the report on the child's parent to iterate that parent's children. An Issue report can iterate the resolved project's tasks directly.

## Reference frame inside `type=iterate`

A `valueexpression` on an iterating column is evaluated **once per child**, and every unqualified `{field}` resolves against **that child** — not against the report's base object. `reports/07-view-patterns.md` § 6 states the same rule from the JSON side (`{parameter}.{displayName}` resolves relative to the iterating child, not the outer row).

The corollary is the part that bites: **to reach a field on an ancestor, traverse from the child, using the child's own relation name.** The relation name the base object uses does not apply inside the iterate, even though it works in every non-iterating column of the same report.

<!-- UNVERIFIED -->
Reaching the project's `entryDate` from an **Issue** report:

| Where | Traversal |
|---|---|
| an ordinary column (frame = the issue) | `{resolveProject}.{entryDate}` |
| inside `nested(resolveProject.tasks).lists` (frame = a task) | `{project}.{entryDate}` |

Both name the same project. They differ because the frame moved, and swapping one for the other is a silent blank rather than an error — the same failure signature as every other bad reference in a `valueexpression`.

### Pattern: date math between a base-object field and one specific child

This is the general recipe for "how long between *this* record's date and the date of the one child named X" — the case a plain `valuefield` cannot express at all.

```
displayname=# of days between project entry and kickoff
listdelimiter=<div>
listmethod=nested(resolveProject.tasks).lists
type=iterate
valueexpression=IF(CONTAINS("Kickoff",{name}),WEEKDAYDIFF({project}.{entryDate},{actualStartDate}))
valueformat=HTML
```

Read it as three moves: iterate the related object's children; select the one you want with `IF(CONTAINS(...))` against a child field; pull the base-object side of the arithmetic back through the child's parent relation.

Caveats, both of which follow from rules stated above:
- Non-matching children still render an entry (a blank one) — the `IF` has no else-skip. See § Common collection patterns.
- Selecting by `CONTAINS` on `{name}` matches **every** task whose name contains the string, so a project with "Kickoff" and "Kickoff Prep" emits two values. Match on a task custom field or a milestone if the naming is not disciplined — or, on template-generated projects, on `{templateTaskID}`; see § Pattern: selecting one specific child by template identity below.

Swap `{actualStartDate}` for `{plannedStartDate}` / `{plannedCompletionDate}` as the question requires; the surrounding shape is unchanged.

### Pattern: selecting one specific child by template identity

<!-- UNVERIFIED -->
The selector problem above — "I want *this one* child, and name matching is too loose" — has a stable answer whenever the project was created from a template. **`{templateTaskID}` on a task holds the ID of the template task (`TTSK`) it was generated from**, and that ID is the *same value* on the corresponding task in every project created from that template. So one hardcoded ID picks out "the same task" across the whole portfolio, where `{name}` matching depends on nobody having renamed or duplicated anything:

```
displayname=Specific Milestones
listdelimiter=<p>
listmethod=nested(tasks).lists
type=iterate
valueexpression=IF({templateTaskID}="aecf4d570693db8fe0539260720a5552",IF(!ISBLANK({milestoneID}),IF({canStart}="true",IF({project}.{status}!="CPL",{name}))))
valueformat=HTML
```

The nesting reads as a filter chain, each `IF` narrowing the last: it is that one template task, **and** it is flagged as a milestone (`!ISBLANK({milestoneID})`), **and** it is ready to execute (`{canStart}`), **and** its project is not complete — then emit `{name}`. Note the reach-back to `{project}.{status}` from inside the iterate, per § Reference frame inside `type=iterate`.

Where to get the ID: open the template task and take the ID from the URL, or `GET /attask/api/v22.0/tmplTask/search?fields=ID,name&templateID=<id>`.

**Two limits, and the second is the more important one.**

1. The ID is **template-scoped and environment-specific**. A project created ad hoc, or from a *different* template, has a different `templateTaskID` (or none), so the column silently renders empty for it rather than erroring — the same blank-cell signature as any other non-matching `IF`. The literal also differs between sandbox and production, so a view promoted between environments needs the ID swapped. This is the text-mode instance of the hardcoded-ID portability concern the Fusion bucket already tracks (`../fusion/08-scenario-creation-checklist.md`).

2. <!-- UNVERIFIED --> **There is no way to take "the first N" of an iterate.** The thread this came from asked for *only the first active milestone when several are active*, and the accepted answer does not deliver that — it substitutes pinning one known identity. That substitution is the finding: `type=iterate` has no rank, limit, index, or short-circuit construct, so a `valueexpression` cannot express "whichever of these matches first". Every child that satisfies the `IF` renders, and ordering is whatever the collection returns. The workarounds are all upstream of text mode — pin an identity as above, tighten the predicate until exactly one child can match, or (the answerer's own practice) chain milestones with predecessors so that only one is ever `canStart` at a time, making the report's "only one" a property of the schedule rather than of the column.

Treat "show me the first/latest/highest child" requests as a modeling question, not a syntax question.

## Sources

| Source | What it provided |
|---|---|
| https://experienceleaguecommunities.adobe.com/adobe-workfront-general-23/weekdaydiff-between-native-field-and-the-date-of-specific-task-252589 | The `nested(<rel>.<collection>).lists` dotted form, the `{project}.{entryDate}` reach-back from inside an iterate, and the WEEKDAYDIFF-to-a-named-child pattern — best answer by NicholeVargas, 2026-09-01 |
| https://experienceleaguecommunities.adobe.com/adobe-workfront-general-23/show-only-1-active-milestone-in-a-project-report-252441 | `{templateTaskID}` as a stable per-template selector inside a `nested(tasks).lists` iterate, the milestone/`canStart`/project-status filter chain, and — by what the answer declines to do — the absence of any first/limit construct in an iterate; the predecessor-chaining modeling workaround is the answerer's own practice. Best answer by NicholeVargas, 2026-09-03 |

## Cross-references

- `01-syntax-fundamentals.md` — `valuefield` vs `valueexpression`, dotted-brace traversal, why colon-inside-braces renders blank.
- `04-views-and-groupings.md` — the view-level directives these collection columns sit inside.
- `09-tips-and-gotchas.md` — the blank-cell symptom table, including the iterate reference-frame row.
- `../reports/07-view-patterns.md` § 6 — the same collection column expressed as UIVW JSON, and the per-child evaluation rule.
- `../fusion/08-scenario-creation-checklist.md` — the hardcoded environment-specific ID concern that § Pattern: selecting one specific child by template identity inherits.
