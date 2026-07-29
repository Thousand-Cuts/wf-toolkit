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
