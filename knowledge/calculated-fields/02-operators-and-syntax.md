# 02 — Operators and Syntax

## Expression Syntax Basics

Calculated field expressions use curly brackets around field names and periods to traverse object relationships:

```
{fieldName}
{parentObject}.{fieldName}
{DE:Custom Field Name}
{parentObject}.{DE:Custom Field Name}
```

**Field names use the interface display name exactly** — including spaces and capitalization. Workfront resolves field names from the UI label, not camelCase database names (which is the reverse of `valuefield` in text mode).

```
# Correct — matches UI label
{Planned Completion Date}

# Wrong — camelCase is text-mode syntax, not calc field syntax
{plannedCompletionDate}
```

**Function names must be ALL UPPERCASE.** `if(...)` is invalid; `IF(...)` is required.

## Single-Line Rule

Keep the entire expression on a single line. Workfront's calc field editor treats newlines as statement breaks. Wrapping a long expression across lines will produce a "Custom Expression Invalid" error or silently truncate the expression.

## Comparison Operators

| Operator | Meaning |
|---|---|
| `=` | Equal |
| `!=` | Not equal |
| `>` | Greater than |
| `>=` | Greater than or equal to |
| `<` | Less than |
| `<=` | Less than or equal to |

## Logical Operators

| Operator | Meaning | Example |
|---|---|---|
| `&&` | AND | `IF({status}="CUR" && !ISBLANK({DE:Region}),"Active + Region set","")` |
| `\|\|` | OR | `IF({status}="CUR" \|\| {status}="PLN","Active","Inactive")` |
| `!` | NOT (prefix negation) | `IF(!ISBLANK({DE:Notes}),"Has notes","")` |

### NOT / NOTBLANK — Never Use These

| Wrong | Right |
|---|---|
| `NOT({status}="ONH")` | `!({status}="ONH")` |
| `NOTBLANK({DE:Field})` | `!ISBLANK({DE:Field})` |

`NOT(...)` and `NOTBLANK(...)` are not valid in calculated field expressions. Always use `!(...)` and `!ISBLANK(...)`.

## Custom Field References (DE: Prefix)

All custom (Data Extension) fields must be prefixed with `DE:` inside curly brackets:

```
{DE:Approved?}
{DE:Region}
{DE:Budget Amount}
{project}.{DE:Client Tier}
```

**Preserve the exact question mark or other special characters if the field name in Workfront includes them.** A field named `Approved?` in the UI must be referenced as `{DE:Approved?}`.

Do NOT wrap the `DE:` reference in extra quotation marks:

```
# Wrong
IF("{DE:Status Label}"="Active", ...)

# Correct
IF({DE:Status Label}="Active", ...)
```

## Cross-Object Prefixes

Only add `{project}.`, `{task}.`, `{portfolio}.`, etc. when the field lives on a **parent or related object**, not the object the form is on:

```
# On a Task form, referencing the parent project's name — add prefix
{project}.{name}

# On a Task form, referencing the task's own planned completion date — no prefix
{plannedCompletionDate}
```

A task calc field can reach its parent project. A project calc field cannot reach down into its child tasks (collections are not accessible from calc fields — see `07-limitations-and-gotchas.md`).

## Quotation Marks

String literals in expressions must use **straight double quotes** `"`. Curly/smart quotes `"` `"` cause a "Custom Expression Invalid" error. This most often happens when copying expressions from Word, email, or web pages.

## String Concatenation

Use `CONCAT(...)` for all multi-part string building. Do NOT use `+` or `&` as string concatenation operators:

```
# Correct
CONCAT({name}," — ",{DE:Region})

# Wrong — these do not work as string operators in calc fields
{name} + " — " + {DE:Region}
{name} & " — " & {DE:Region}
```

## No Parentheses in Field Names or Labels

Do not suggest field names or labels that include parentheses. Parentheses in field names (e.g., `Budget Amount (Approved)`) cause problems in calc field expressions and in External Lookup parameter substitution. Use plain names: `Budget Amount Approved`.

## The $$OBJCODE Wildcard

On multi-object custom forms (forms attached to both Projects and Tasks, for example), use `$$OBJCODE` in an `IF` expression to branch the calculation by object type:

```
IF($$OBJCODE="PROJ",{plannedRevenue},IF($$OBJCODE="TASK",{project}.{plannedRevenue},""))
```

Common object codes: `PROJ` (Project), `TASK` (Task), `OPTASK` (Issue), `PORT` (Portfolio), `PRGM` (Program), `USER` (User), `DOCU` (Document).
