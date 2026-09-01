# 07 — Limitations and Gotchas

## Format Is Permanent

Once a custom form containing a calculated field is **saved for the first time**, the Format (Text, Number, Currency, Date, Date/Time) cannot be changed. Deleting the field and recreating it is the only option. Always confirm the format before saving.

## No Collection Access

Calculated fields **cannot reach into collections** — meaning they cannot aggregate child records. A project calc field cannot sum up its tasks' planned hours. A project calc field cannot reference any task field. The access direction is strictly child → parent, not parent → child.

**Workaround:** Use Fusion to aggregate child data and write the result to a custom field on the parent object. The calc field then references that written value normally.

## Stale Cross-Object Values

When a field on a **parent or related object** changes, the calculated field on the child does NOT update automatically. The stored value goes stale. This is the most common source of data inconsistency in Workfront implementations.

Practical consequence: never display cross-object calculated field values to stakeholders without a documented recalc process in place.

**Ways to recalculate:**
1. Edit and save the child object (any edit triggers recalc).
2. **Recalculate Custom Expressions** from the object's More (⋯) menu.
3. Bulk edit via a report: select all relevant records → Edit → make a trivial change → Save.
4. API: `PUT /attask/api/v22.0/PROJ/recalculateCustomFields` (or equivalent for the object type).

## $$TODAY and $$NOW Go Stale

`$$TODAY` and `$$NOW` are evaluated at the time the calculated field **last ran**, not at the time the field is viewed. A "Days Overdue" field using `DATEDIFF($$TODAY, {plannedCompletionDate})` that hasn't been recalculated in two weeks is two weeks stale.

**Rule:** Do not use `$$TODAY` or `$$NOW` in a calculated field when real-time freshness is required. Use a `valueexpression` column in a text-mode report instead — it computes at render time.

## UTC Timezone Evaluation

`$$TODAY` and `$$NOW` are evaluated against UTC, not the user's local timezone. Users in timezones ahead of UTC (e.g., AEST = UTC+10) may see dates that appear one day off around midnight. Document this in the field's Instructions text.

## Circular Dependencies

**Mutual references between calculated fields are rejected.** If Field A references Field B, and Field B references Field A, Workfront detects the circular reference and refuses to save; the form editor surfaces an error. There is no workaround within calculated fields: break the cycle by restructuring the logic.

**Direct self-reference is allowed.** A calculated field can reference itself (`{DE:X}` inside field X's own expression), subject to an ordering requirement: create the field, save the form once to commit it to the database, then edit the field and enter the calculation. An expression can only name a field that already exists. This is the basis of the first-touch timestamp latch pattern in `06-common-patterns.md` § "First-Touch Status Timestamp Latch":

```
IF({status}="ONH",IF(ISBLANK({DE:On Hold Date}),$$NOW,{DE:On Hold Date}),{DE:On Hold Date})
```

An earlier revision of this section claimed self-reference was disallowed outright ("Workfront will detect the circular reference and refuse to save"), conflating the direct case with the mutual case above. Corrected 2026-09-01 after a community report and live evidence; the mutual-case prohibition stands unchanged.

Verified 2026-08-31 on a sandbox tenant (sandbox), v22.0: two independent self-referencing calculated
fields exist and persist, both with `isInvalidExpression: false`, read via
`GET /CTGY/search?fields=categoryParameters:customExpression,categoryParameters:isInvalidExpression,categoryParameters:parameter:name`:

| Form | Field | Expression |
|---|---|---|
| Additional Task Details | `INPSTATUSDATE` | `IF({status}="INP",IF(ISBLANK({DE:INPSTATUSDATE}), $$NOW, {DE:INPSTATUSDATE}))` |
| PMO Project Brief | `Job Number` | `IF(ISBLANK({DE:Job Number})||LEN({DE:Job Number})!=LEN(CONCAT(...)),CONCAT(...),{DE:Job Number})` |

`INPSTATUSDATE` is the same latch shape the community thread describes, applied to `INP` instead of `ONH`,
arrived at independently by whoever built that form. Negative control: `categoryParameters:bogusFieldXyz` on
the same endpoint is rejected with `APIModel V22_0 does not support field bogusFieldXyz (CategoryParameter)`,
so these field names resolving is evidence rather than silent tolerance.

**Verification scope:**

- **Verified:** a direct self-reference is accepted and persists on a live v22.0 tenant, on two unrelated
  forms.
- **Not verified:** the runtime latching behavior. Whether the stored value actually sticks across
  recalculation, rather than re-evaluating to blank or to a fresh `$$NOW`, requires observing a recalc, which
  needs a write. <!-- UNVERIFIED --> The latch semantics rest on the community thread and the pattern's wide
  community circulation.
- **Not retested:** the mutual case (Field A references Field B, Field B references Field A). The prohibition
  above stands on the original claim, which the evidence never contradicted.
- **Weak signal, stated so it is not over-read:** `isInvalidExpression` was `false` on all 647 category
  parameters in the tenant, so it never discriminates here. The load-bearing evidence is that the expressions
  persist at all, not that the flag says they are valid.

## Chained Calc Fields: Transitive Refresh Not Guaranteed

If Field A references Field B, and Field B references Field C (which references a native field), updating the native field will refresh Field B but may NOT automatically cascade to Field A. Transitive refresh behavior is not explicitly guaranteed in official docs for classic calculated custom fields. Treat chained calc fields as eventually consistent, not immediately consistent.

## Same Field Name on Multiple Forms

If a calculated field with the same **parameter name** appears on two custom forms attached to the same object, both formulas must be **identical**. If they differ, Workfront shows the error: _"There is a slight problem. That field is used in a multi-form configuration."_ The field becomes locked — neither formula can be edited until the conflict is resolved. Resolution: remove the field from one form, edit the formula on the other, then re-add if needed.

## Cannot Store Arrays or Collections as Values

A calculated field stores a single scalar value (string, number, date). It cannot store a list or array. ARRAY functions can be used within an expression as intermediate values, but the final output must be a single value of the chosen format.

## Maximum Fields Per Form

A custom form can hold a maximum of **500 fields and widgets**. Performance degrades noticeably beyond approximately 100 fields. For forms with many calculated fields (especially those using cross-object references), save times can increase significantly.

## Curved Quotation Marks

Smart/curly quotes (`"` `"`) copied from Word, email, or web pages will cause a "Custom Expression Invalid" error. Always verify that string literals use straight double quotes `"`.

## Hours Stored as Minutes

Duration and time-related fields (e.g., `actualDurationMinutes`, `workRequired`) store values in **minutes**. Divide by 60 to convert to hours: `DIV({actualDurationMinutes}, 60)`. Forgetting this produces results that are 60× too large.

## Recalculation on Form Attachment

When a custom form with a calculated field is attached to an existing object, the calculated field is **not automatically computed** until the object is saved or recalculated. Newly attached forms show blank calc field values until the first recalc event.

## CONTAINS on a Multi-Select Tests Option Values, Not Labels

<!-- UNVERIFIED -->
A probe like `IF(CONTAINS("Taiwan",{DE:Country})="true",1,0)` silently evaluates to 0 on every record whenever the option's displayed **label** differs from its stored **value** (label "Taiwan" / value "TW" — the working probe is `CONTAINS("TW",…)`). No error is raised — just a wrong 0. A multi-select's stored value is a single concatenated string of the selected options' `ParameterOption.value` entries; `label` is display-only and never stored (the same value-vs-label fact is documented for the API layer in `custom-forms/09-gotchas.md` #9 and `custom-forms/03-create-form-recipe.md` § Label vs value handling — this is its calc-expression consequence). Before writing the expression, pull the option list and read the `value` column: `GET /parameterOption/search?parameterID=<id>&fields=ID,label,value`.

Two cautions the community source did not raise: (a) `CONTAINS` is a raw substring test — option values that are prefixes/substrings of each other (e.g. "Design" and "Design Review") double-count; guarantee non-overlapping values before shipping the pattern. (b) If the probe feeds report aggregation, the field's Format must be **Number** at creation — format is permanent after first save (see "Format Is Permanent" above and `04-format-types.md`).

Community-reported, not reproduced in-house: all 200 `parameterOption` rows sampled on the surveyed sandbox tenant 2026-08-07 had `value == label`, so the divergence case could not be exercised there. Provenance in Sources below.

## What Calculated Fields Cannot Do

- Cannot aggregate across children (no SUM of task hours on a project)
- Cannot call external systems or APIs
- Cannot reference fields from unrelated objects (only objects in the API Explorer "references" tab)
- Cannot reference fields on sibling objects (other tasks on the same project, other projects in the same portfolio)
- Cannot produce multiple output values (one scalar per field)
- Cannot use JavaScript, HTML, or Markdown in the stored value
- Cannot access user-session context (logged-in user, current date with local timezone) reliably

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/best-way-to-report-the-counts-of-selections-from-a-multi-select-field-251655` | CONTAINS-on-multi-select matches `ParameterOption.value`, not `.label` — best answer by Lyndsy-Denk, 2026-07-10 |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-general-23/using-journal-entry-data-for-reporting-on-custom-status-changes-252434` | Self-referencing calculated field as a first-touch status timestamp latch, plus the save-then-calculate ordering requirement. Contradicted the prior Circular Dependencies claim; arbitrated 2026-09-01 in favor of the thread and the claim rescoped to mutual references. Best answer by Richard_Le_, 2026-08-20 |
