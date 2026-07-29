# 04 — Fields and Naming

Workfront's API uses the same field names and naming conventions as text mode. The rules are unforgiving — names must match exactly. The API Explorer is the source of truth for every field on every object.

## Field naming conventions

| Convention | Example | Notes |
|---|---|---|
| **camelCase** | `plannedCompletionDate`, `ownerID`, `percentComplete` | First letter lowercase, no underscores, no hyphens |
| **ID suffix on foreign keys** | `projectID`, `assignedToID`, `roleID` | Capital `ID` |
| **Camel-cased nested objects** | `assignedTo`, `project`, `portfolio` | Used to traverse to a related object |

## Custom fields (Data Extensions)

Custom fields require the `DE:` prefix and the field's exact display name — including spaces and capitalization, with no escaping.

```
DE:Region
DE:Vendor Name
DE:Approval Status (Q2)
```

The display name is what shows in the Workfront UI when you edit the field on a custom form. If the form labels it `Vendor Name`, the API filter must reference `DE:Vendor Name` — not `DE:vendor_name`, not `DE:VendorName`, not `vendorName`.

### Never URL-encode `DE:` field names

Even though `:` and space are technically URL-special characters, **Workfront filter parameters expect `DE:` field names un-encoded**. Percent-encoding the colon or spaces breaks the filter silently — the parameter is not recognized and no results are returned.

```
✓ Correct:   ?DE:Vendor Name=Acme&DE:Vendor Name_Mod=eq
✗ Wrong:     ?DE%3AVendor%20Name=Acme&DE%3AVendor%20Name_Mod=eq
```

This applies to query strings, POST bodies, and External Lookup URL templates. Pass the literal `DE:Field Name` string as-is.

### Don't wrap `DE:` references in quotes

`DE:` references in filter parameters and External Lookup URLs must appear unquoted. Wrapping them in single or double quotes causes the filter to fail or the token to resolve as a literal string rather than a field reference.

```
✓ Correct:   &DE:Client Name={DE:Client Name}&DE:Client Name_Mod=eq
✗ Wrong:     &"DE:Client Name"="{DE:Client Name}"&"DE:Client Name_Mod"=eq
```

Only add quotes if the API or a specific endpoint explicitly requires them — which the Workfront API does not.

## Selecting which fields to return: the `fields=` parameter

By default, a GET request returns a small set of fields. To get more, add `fields=` to the query string with a comma-separated list.

### Direct fields on the object

```
GET /attask/api/v<version>/project/<projectID>?fields=name,status,plannedCompletionDate,DE:Region
```

### Fields on a related object

Use colon-separated paths, just like text-mode `valuefield`:

```
GET /attask/api/v<version>/task/<taskID>?fields=name,status,project:name,project:portfolio:name,assignedTo:name
```

### Fields on a collection

Use the collection name, then colon-separated field paths:

```
GET /attask/api/v<version>/project/<projectID>?fields=tasks:name,tasks:status,tasks:assignments:assignedTo:name
```

This returns the project, plus a `tasks` array, each task with a `name` and `status` and an `assignments` array.

See `08-related-objects-and-collections.md` for the deeper treatment.

### Wildcard field selection

The API supports a few wildcards in `fields`:

- `*` — all top-level fields on the object (avoid in production; payload sizes get unpredictable)
- `:*` after a relationship — all fields on the related object

Use named field lists in production code. Wildcards are useful while exploring.

## Custom data wildcards in `fields=`

To pull every custom-form field value on an object in one call, use **`fields=parameterValues`** (or equivalently `fields=parameterValues:*`). Both return the full set of `DE:` field values on that object as a single object keyed by `DE:<field name>`:

```
GET /attask/api/v17.0/project/<id>?fields=name,parameterValues
```

Example response shape (truncated):
```json
{
  "data": {
    "ID": "...",
    "name": "Acme Q3 Launch",
    "objCode": "PROJ",
    "parameterValues": {
      "DE:Region": "North America",
      "DE:Vendor Name": "Acme",
      "DE:Approval Status": "Approved"
    }
  }
}
```

`fields=DE:*` does **NOT** work — the API returns `"no such field: '*'"`. The `:*` relation-fields wildcard does not apply to the `DE:` prefix. Empirically verified on Workfront API v17.0, 2026-05.

If you only want a known subset, list them explicitly: `fields=DE:Region,DE:Vendor Name`. Use `parameterValues` when you want everything regardless of form attachment.

## Discipline rules

1. **Don't guess field names.** The Workfront UI shows display names like "Planned Completion Date" — the API expects `plannedCompletionDate`. If you don't know the camelCase form, look it up.
2. **Don't trust returned-payload field names blindly when writing.** Read-only computed fields (`condition`, `percentComplete`, `progressStatus`) appear in GET payloads but can't all be set with PUT.
3. **The API Explorer lists data type per field.** Use it to disambiguate `string` vs `int` vs `date` — filter modifiers behave differently per type.
4. **Some UI / report fields don't exist on the API object.** "Planned Hours" on a task is the clearest trap: there is no `plannedHours` API field (read *or* write) — the stored effort field is **`workRequired`, in minutes**. When a field shows in reports but a GET errors with `does not support field X`, look for the underlying stored field. See `10-status-and-enum-codes` § Duration Type.

## Where to find field names

Adobe Workfront API Explorer (under Adobe Experience League). It lists:

- Every field on every object, with its exact camelCase name
- Data type (`string`, `int`, `double`, `date`, `boolean`, etc.)
- Whether the field is read-only or writable
- Related collections and their join field names
- Available actions per object

When in doubt, look it up there — don't guess and don't invent.
