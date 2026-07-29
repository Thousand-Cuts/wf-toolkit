# 04 — Format Types

## The Format Is Permanent

Once you save a custom form, the **Format of a calculated field cannot be changed**. If you choose the wrong format, you must delete the field and recreate it. This is the most common setup mistake — pick the format before writing the expression.

## Available Formats

### Text

- **Stored as:** string
- **Use when:** the expression produces a label, status name, description, CONCAT result, emoji-decorated text, or any non-numeric output
- **Examples:** `"Complete"`, `"At Risk"`, `"Region: APAC — Owner: Jane Smith"`, `"✅ Done"`
- **Notes:** CASE, SWITCH, IF returning strings, and CONCAT all produce Text. Even numeric results (`ROUND(...)`) should use Text if you want to append a unit like `" days"`.

### Number

- **Stored as:** decimal number
- **Use when:** the expression produces a pure numeric result — counts, differences, ratios, raw percentages
- **Examples:** `DATEDIFF(...)`, `ROUND({percentComplete}, 0)`, `DIV({actualCost}, {plannedCost})`
- **Notes:** Workfront truncates leading zeros (e.g., `07` becomes `7`). For values starting with 0 that need padding, use Text format and `CONCAT` the leading zero manually.

### Currency

- **Stored as:** decimal number, displayed with a currency symbol
- **Use when:** the expression is a monetary value — budget variances, cost calculations, revenue deltas
- **Examples:** `SUB({plannedRevenue}, {actualCost})`, `{DE:Approved Budget}`
- **Notes:** Do NOT wrap currency field references in quotation marks inside expressions. Currency fields should never include quotation marks in the expression. Workfront applies the instance's default currency symbol at display time.

### Date

- **Stored as:** date (no time component)
- **Use when:** the expression produces a date — calculated deadlines, ADDDAYS results, DMIN/DMAX date selections
- **Examples:** `ADDDAYS({plannedCompletionDate}, 14)`, `DMIN({plannedCompletionDate}, {DE:External Deadline})`
- **Notes:** If you use `CLEARTIME(...)` to strip time from a Date/Time value, use **Date** format for the result. UTC offset applies — see fundamentals.

### Date/Time

- **Stored as:** full timestamp (date + time)
- **Use when:** the expression must preserve time, or the referenced fields include timestamps
- **Examples:** `ADDDAYS($$NOW, 1)`, `DMAX({actualStartDate}, {entryDate})`
- **Notes:** UTC evaluation applies. Users in non-UTC timezones may see results that differ from their local interpretation by up to one day. Document this in the field Instructions for users.

## Deciding Between Number and Text for Numeric Results

Use **Number** when:
- You need the value to aggregate in report groupings (SUM, AVG, etc.)
- You need to sort numerically in reports
- You intend to use the stored value in further calculations

Use **Text** when:
- You want to append a unit string (`" days"`, `" hrs"`, `"%"`)
- You need leading-zero padding
- The field is purely for display (a formatted label)

## Percent Note

The classic Workfront custom form editor does not list "Percent" as a format option for calculated fields (as of documented versions). To display a percentage:

- Use **Number** format and store the raw value (e.g., `75` for 75%)
- Or use **Text** format and CONCAT the `%` symbol: `CONCAT(ROUND({percentComplete},0),"%")`

If your Workfront instance is on a newer version and shows a Percent format option, use it for calculations that genuinely represent proportions expressed as percentages. The value `75` will display as `75%`.

## Format and Aggregation in Reports

Only **Number** and **Currency** format fields can be aggregated (SUM, AVG, MIN, MAX) in report groupings. **Date** fields cannot be summed but can be used in group-by clauses. **Text** fields cannot aggregate numerically — if a text field contains a number-looking string, it will not sum correctly in a grouping.
