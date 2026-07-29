# Calculated Field Example: IF + !ISBLANK Guard

Apply to any custom form. This pattern prevents blank-field errors and produces clean output when optional fields are not filled in.

## Basic guard: show field or fallback

**Format:** Text

```
IF(!ISBLANK({DE:Region}),{DE:Region},"Region not set")
```

Returns the field value when present, a fallback string when blank.

## Guard before CONCAT (prevent orphaned separators)

**Format:** Text

```
CONCAT({name},IF(!ISBLANK({DE:Region}),CONCAT(" [",{DE:Region},"]"),""))
```

Appends `[Region]` to the project name only when Region is filled in. Without the guard, you'd get `"Project Name []"` for records with no region.

## Guard to protect division from zero

**Format:** Number

```
IF({plannedCost}=0,0,DIV({actualCost},{plannedCost}))
```

Returns 0 when planned cost is zero, avoiding a division-by-zero error.

## Chained guards for multi-field conditional output

**Format:** Text

```
IF(!ISBLANK({DE:Risk Level}),IF(!ISBLANK({DE:Risk Notes}),CONCAT({DE:Risk Level},": ",{DE:Risk Notes}),{DE:Risk Level}),"No risk assessed")
```

- Both Risk Level and Risk Notes filled: `"High: Budget overrun possible"`
- Risk Level only: `"High"`
- Neither filled: `"No risk assessed"`

## Guard on a cross-object reference

**Format:** Text

```
IF(!ISBLANK({project}.{DE:Client Name}),{project}.{DE:Client Name},"No client assigned")
```

Cross-object fields may legitimately be blank (form not attached to the parent, or field not filled). Always guard them.

## Notes

- `ISBLANK(value)` returns `true` for both `null` (field never set) and an empty string. This covers both cases cleanly.
- `!ISBLANK(...)` is the correct negation. Never use `NOTBLANK(...)` — it is not valid syntax in calculated fields.
- Never use `NOT(ISBLANK(...))` — always use `!ISBLANK(...)`.
