# 06 — Common Patterns

All examples follow the required coworker format: **Format line is stated first**, then the expression.

---

## Days Overdue

**Format:** Number

```
DATEDIFF($$TODAY,{plannedCompletionDate})
```

Returns a positive number if the due date has passed (overdue). Returns a negative number if the due date is in the future. Zero = due today.

> Note: `$$TODAY` is evaluated in UTC. If users are in a non-UTC timezone this may read one day off near midnight boundaries.

---

## Overdue Flag (Text Label)

**Format:** Text

```
IF(DATEDIFF($$TODAY,{plannedCompletionDate})>0,"OVERDUE","")
```

Returns `"OVERDUE"` when past due, empty string when not. Safe to use as a filter value in a report (`DE:Overdue Flag` `eq` `OVERDUE`).

---

## Days Remaining (Positive = Future)

**Format:** Number

```
DATEDIFF({plannedCompletionDate},$$TODAY)
```

Returns positive when future, negative when past. Argument order reversed from the overdue pattern.

---

## Status Label With Emoji

**Format:** Text

```
SWITCH({status},"CPL","✅ Complete","CUR","🟢 In Progress","PLN","⏳ Planned","ONH","⏸ On Hold","❓ Other")
```

---

## CASE on Priority (0-based integer)

**Format:** Text

```
CASE({priority},0,"None",1,"Low",2,"Normal",3,"High",4,"Urgent","Unknown")
```

`CASE` is index-based — the first value after the expression is index 0. The last argument is the default if no index matches.

---

## IF + !ISBLANK Guard

**Format:** Text

```
IF(!ISBLANK({DE:Region}),CONCAT("Region: ",{DE:Region}),"Region not set")
```

Use `!ISBLANK` to safely guard against blank fields before building output strings.

---

## CONCAT Multi-Field Summary

**Format:** Text

```
CONCAT({name}," | ",{owner}.{name}," | Due: ",{plannedCompletionDate}," | Status: ",{status})
```

Multi-part summary in a single stored field — useful as a searchable reference column or a display label.

---

## Budget Variance (Currency)

**Format:** Currency

```
SUB({plannedRevenue},{actualCost})
```

Returns the difference between planned revenue and actual cost. Positive = under budget. Negative = over budget.

---

## CONCAT With !ISBLANK Conditional Append

**Format:** Text

```
CONCAT({name},IF(!ISBLANK({DE:Region}),CONCAT(" [",{DE:Region},"]"),""))
```

Appends the region bracket only when a region is set — no trailing bracket for blank records.

---

## Percent Complete Display With % Symbol

**Format:** Text

```
CONCAT(ROUND({percentComplete},0),"%")
```

Stores as text. Not aggregatable, but human-readable. If you need to SUM percent complete in a report grouping, use **Number** format with just `ROUND({percentComplete},0)` instead.

---

## Risk Score: Conditional Weighted Score

**Format:** Number

```
IF({DE:Risk Level}="High",3,IF({DE:Risk Level}="Medium",2,IF({DE:Risk Level}="Low",1,0)))
```

Converts a text-based Risk Level field into a numeric score for report aggregation.

---

## Manager of Issue Creator (Cross-Object)

**Format:** Text

```
{owner}.{manager}.{name}
```

On an Issue form, reaches the issue's owner, then that user's manager, returning the manager's name. Illustrates two-hop traversal.

---

## Duration in Hours (Minutes → Hours)

**Format:** Number

```
DIV({actualDurationMinutes},60)
```

Duration fields store minutes internally. Divide by 60 to convert to hours.

---

## $$OBJCODE Branch for Multi-Object Forms

**Format:** Text

```
IF($$OBJCODE="PROJ",{name},IF($$OBJCODE="TASK",CONCAT("Task: ",{name}),"Unknown object"))
```

---

## FORMAT: Color-Coded Budget Health

**Format:** Text

```
IF(SUB({plannedRevenue},{actualCost})<0,FORMAT($$NEGATIVE,$$BOLD),IF(SUB({plannedRevenue},{actualCost})<1000,FORMAT($$NOTICE),""))
```

Applies red+bold when over budget, orange when close to budget, default otherwise.

---

## Reference a DE: Field on a Parent Project (From Task Form)

**Format:** Text

```
IF(!ISBLANK({project}.{DE:Client Name}),{project}.{DE:Client Name},"No client set")
```

---

## Per-Option 0/1 Indicator for a Multi-Select (Countable)

**Format:** Number

```
IF(CONTAINS("TW",{DE:Country})="true",1,0)
```

<!-- UNVERIFIED -->
A multi-select stores one concatenated string of the selected options' values, and a calc field emits one scalar — so there is no native "count per selection." One Number-format indicator field per option, SUMmed in a report grouping, yields per-option counts. Test against `ParameterOption.value`, never the display label — see `07-limitations-and-gotchas.md` § "CONTAINS on a Multi-Select Tests Option Values, Not Labels" for the silent-zero trap, the substring-collision caution, and why Format must be Number at creation. With many options, house the indicator fields on an admin-only reporting form rather than the user-facing one. Community-reported (see Sources); the `="true"` string compare is the form the source reports working — not lab-verified here.

---

## First-Touch Status Timestamp Latch (Self-Referencing)

**Format:** Date/Time

```
IF({status}="ONH",IF(ISBLANK({DE:On Hold Date}),$$NOW,{DE:On Hold Date}),{DE:On Hold Date})
```

Stamps the first time a record enters a given status, with no Fusion scenario. The field references **itself**: when the status matches and nothing is stored yet, emit `$$NOW`; in every other case re-emit the stored value, so the first stamp sticks.

Requirements and caveats:

1. **Save the form first.** Create the field, save the form to commit it to the database, then edit the field and enter the calculation. An expression can only reference a field that already exists. Direct self-reference is allowed; mutual references between two fields are rejected at save (see `07-limitations-and-gotchas.md` § Circular Dependencies).
2. **Recalc timing applies.** The stamp is written when the object's calculations run (edit-and-save, form attach plus save, or a recalc; see 07 § Stale Cross-Object Values). A status change with no accompanying recalc event will not stamp until the next one, so the timestamp is "first recalc while in status", not the literal transition instant.
3. **First-touch, not most-recent.** A record that leaves and later re-enters the status keeps the original timestamp. Intended for first-touch stamps; wrong for a most-recent-touch stamp.

<!-- UNVERIFIED -->
The self-reference being accepted and persisting is verified on a live v22.0 tenant (evidence in `07-limitations-and-gotchas.md` § Circular Dependencies). The latch semantics, meaning the stored value surviving recalculation rather than re-evaluating to blank, are community-reported and match two independently built production fields, but have not been exercised in-house because proving it needs a write.

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/best-way-to-report-the-counts-of-selections-from-a-multi-select-field-251655` | the per-option 0/1 indicator pattern for multi-select counts — best answer by Lyndsy-Denk, 2026-07-10 |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-general-23/using-journal-entry-data-for-reporting-on-custom-status-changes-252434` | the self-referencing first-touch timestamp latch and the save-then-calculate ordering requirement; best answer by Richard_Le_, 2026-08-20 |
