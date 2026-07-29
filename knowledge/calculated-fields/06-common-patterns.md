# 06 — Common Patterns

All examples follow the required format: **Format line is stated first**, then the expression.

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
