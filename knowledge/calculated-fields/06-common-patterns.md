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

## Project Delivery Metrics (Completion, Duration, Late vs Baseline, Template SLA)

A set of Project fields for "how long did it take, was it late, and what did the template promise". Built from expressions verified in a Project calculated field on a client prod tenant 2026-09-30: a new form of 5 calculated fields was attached to 3 projects, and every stored value matched one computed independently from the raw dates. The building blocks verified there are `CLEARTIME(...)`, `DATEDIFF(CLEARTIME(a),CLEARTIME(b))`, `WEEKDAYDIFF({actualStartDate},{actualCompletionDate})`, `{defaultBaseline}.{plannedCompletionDate}`, `DIV({template}.{durationMinutes},480)`, and the `IF(ISBLANK(x) || ISBLANK(y),"",...)` guard.

### Completion Date

**Format:** Date

```
CLEARTIME({actualCompletionDate})
```

### Weekdays to Complete

**Format:** Number

```
IF(ISBLANK({actualStartDate}) || ISBLANK({actualCompletionDate}),"",WEEKDAYDIFF({actualStartDate},{actualCompletionDate}))
```

Weekdays from actual start to actual completion. Weekends are excluded; company holidays are **not**. For calendar days use `DATEDIFF(CLEARTIME({actualCompletionDate}),CLEARTIME({actualStartDate}))`, and note the argument order flips: `DATEDIFF(a,b)` is `a` minus `b`, `WEEKDAYDIFF(a,b)` is `b` minus `a`.

### Finished After Original Schedule (100/0 for a % Late Average)

**Format:** Number

```
IF(ISBLANK({actualCompletionDate}) || ISBLANK({defaultBaseline}.{plannedCompletionDate}),"",IF(DATEDIFF(CLEARTIME({actualCompletionDate}),CLEARTIME({defaultBaseline}.{plannedCompletionDate}))>0,100,0))
```

100 when the project finished on a later day than its baseline (original schedule) planned, 0 when on time. Averaged in a report grouping, it reads directly as "% finished late".

- **Why 100 and not 1:** the `doubleAsPercentRounded` aggregator format appends `%` without multiplying by 100, so an average of 1/0 renders as `1%` (`../textmode/04-views-and-groupings.md` and `../reports/07-view-patterns.md`).
- **Why `""` instead of 0 for incomplete projects:** a blank Number result leaves the field absent from `parameterValues`, so the average skips the project instead of counting it as on time.
- **Why `CLEARTIME` on both sides:** a project completed on the baseline's day, but later in the day than the baseline's time, compares as on time only when both dates drop their time. Verified on the same tenant.

### Template SLA Days

**Format:** Number

```
DIV({template}.{durationMinutes},480)
```

The source template's duration in 8-hour work days (`durationMinutes` is work minutes; 480 is one day). Compare it with Weekdays to Complete to see whether the project beat its template. A project not created from a template has no `{template}`; what this returns there was not checked.

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
2. **Recalc timing applies.** The stamp is written when the object's calculations run (edit-and-save, a form attach through the API, which is itself a save, or a recalc; see 07 § Stale Cross-Object Values and § Recalculation on Form Attachment). A status change with no accompanying recalc event will not stamp until the next one, so the timestamp is "first recalc while in status", not the literal transition instant.
3. **First-touch, not most-recent.** A record that leaves and later re-enters the status keeps the original timestamp. Intended for first-touch stamps; wrong for a most-recent-touch stamp.

<!-- UNVERIFIED -->
The self-reference being accepted and persisting is verified on a live v22.0 tenant (evidence in `07-limitations-and-gotchas.md` § Circular Dependencies). The latch semantics, meaning the stored value surviving recalculation rather than re-evaluating to blank, are community-reported and match two independently built production fields, but have not been exercised in-house because proving it needs a write.

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/best-way-to-report-the-counts-of-selections-from-a-multi-select-field-251655` | the per-option 0/1 indicator pattern for multi-select counts — best answer by Lyndsy-Denk, 2026-07-10 |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-general-23/using-journal-entry-data-for-reporting-on-custom-status-changes-252434` | the self-referencing first-touch timestamp latch and the save-then-calculate ordering requirement; best answer by Richard_Le_, 2026-08-20 |
