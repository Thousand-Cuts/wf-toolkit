# Conditional Formatting: Status Color Coding

Apply to a **status column** in any report. Colors the cell background based on the status value.

```
column.0.valuefield=status
column.0.valueformat=HTML
column.0.linkedname=direct
column.0.displayname=Status
column.0.textmode=true

column.0.styledef.case.0.comparison.lefttype=value
column.0.styledef.case.0.comparison.righttype=value
column.0.styledef.case.0.comparison.operator=eq
column.0.styledef.case.0.comparison.leftvalue=
column.0.styledef.case.0.comparison.rightvalue=CPL
column.0.styledef.case.0.comparison.true-bgcolor=D5E8D4
column.0.styledef.case.0.comparison.true-text-color=000000

column.0.styledef.case.1.comparison.lefttype=value
column.0.styledef.case.1.comparison.righttype=value
column.0.styledef.case.1.comparison.operator=eq
column.0.styledef.case.1.comparison.leftvalue=
column.0.styledef.case.1.comparison.rightvalue=CUR
column.0.styledef.case.1.comparison.true-bgcolor=DAE8FC
column.0.styledef.case.1.comparison.true-text-color=000000

column.0.styledef.case.2.comparison.lefttype=value
column.0.styledef.case.2.comparison.righttype=value
column.0.styledef.case.2.comparison.operator=eq
column.0.styledef.case.2.comparison.leftvalue=
column.0.styledef.case.2.comparison.rightvalue=PLN
column.0.styledef.case.2.comparison.true-bgcolor=FFF2CC
column.0.styledef.case.2.comparison.true-text-color=000000

column.0.styledef.case.3.comparison.lefttype=value
column.0.styledef.case.3.comparison.righttype=value
column.0.styledef.case.3.comparison.operator=eq
column.0.styledef.case.3.comparison.leftvalue=
column.0.styledef.case.3.comparison.rightvalue=DED
column.0.styledef.case.3.comparison.true-bgcolor=F8CECC
column.0.styledef.case.3.comparison.true-text-color=000000
```

## Color reference

| Status | Hex | Meaning |
|---|---|---|
| `CPL` Complete | `D5E8D4` | Light green |
| `CUR` Current | `DAE8FC` | Light blue |
| `PLN` Planning | `FFF2CC` | Light yellow |
| `DED` Dead | `F8CECC` | Light red |

Adjust hex values to your organization's brand colors.

## Building this faster

Don't write `styledef` by hand. Switch to standard mode, configure conditional formatting on a status column using the UI, then switch back to text mode and copy the `styledef.case.*` lines.
