# View: Combined Column with Bold Labels

Apply to a **Project report**. Creates a single cell showing project name, owner, and due date with bold labels and line breaks.

Visual output (one cell):
```
Big Migration Project
Owner: Jane Doe
Due: 05/15/2026
```

```
column.0.valuefield=name
column.0.valueformat=HTML
column.0.textmode=true
column.0.sharecol=true
column.0.displayname=Project Info

column.1.value=<br><b>Owner:</b>&nbsp;
column.1.valueformat=HTML
column.1.textmode=true
column.1.width=1
column.1.sharecol=true

column.2.valueexpression=CONCAT({owner}.{firstName}," ",{owner}.{lastName})
column.2.valueformat=HTML
column.2.textmode=true
column.2.sharecol=true

column.3.value=<br><b>Due:</b>&nbsp;
column.3.valueformat=HTML
column.3.textmode=true
column.3.width=1
column.3.sharecol=true

column.4.valuefield=plannedCompletionDate
column.4.valueformat=shortAtDate
column.4.textmode=true
```

## Key points

- The static HTML labels (`<b>Owner:</b>`, `<b>Due:</b>`) use `column.N.value=`, NOT `valueexpression`. Inline HTML inside a `valueexpression` would render as literal text.
- Label sub-columns get `width=1` so they take no visible width.
- Every sub-column has `textmode=true` and `valueformat=HTML`.
- Every sub-column EXCEPT THE LAST has `sharecol=true`. The last one ends the group.
- The first sub-column carries the `displayname` for the merged cell's header.
