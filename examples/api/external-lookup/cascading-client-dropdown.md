# External Lookup: Cascading Client Dropdown (Same-Instance)

**What this shows:** An External Lookup field that pulls project records from the same Workfront instance, filtered by a value selected in an upstream External Lookup field. Demonstrates the correct `$$HOST/attask/api/v17.0/...` URL pattern, `&fields=parameterValues`, the exact JSONPath for custom field values, and the Fusion cascade workaround.

## Scenario

A custom form has two External Lookup fields:
1. **"Account Name"** — user picks a client account (driven by another lookup or a static list)
2. **"Active Projects for Client"** — filters projects where `DE:Client Name` equals the selected account

## Field 2 configuration — "Active Projects for Client"

| Setting | Value |
|---|---|
| Label | Active Projects for Client |
| Base API URL | (see below) |
| HTTP Method | Get |
| JSON Path | `$.data[*].parameterValues['DE:Project Display Name']` |
| Dependencies | DE:Account Name |

## Base API URL

```
$$HOST/attask/api/v17.0/proj/search?status=CUR&status_Mod=eq&DE:Client Name={DE:Account Name}&DE:Client Name_Mod=eq&fields=parameterValues
```

Key rules applied here:
- `$$HOST` — resolves to the current org's Workfront domain. Never hardcode a domain.
- `v17.0` — default consulting version.
- `DE:Client Name` — un-encoded, no quotes. The colon and space are passed as-is.
- `{DE:Account Name}` — references the value selected in the upstream field.
- `&fields=parameterValues` — causes each project in the response to include all its custom field values.

## JSONPath explanation

```
$.data[*].parameterValues['DE:Project Display Name']
```

- `$.data[*]` — iterates over all objects in the `data` array.
- `.parameterValues` — accesses the custom fields map returned by `&fields=parameterValues`.
- `['DE:Project Display Name']` — bracket notation is required because the key contains a colon and spaces. Dot notation (`$.data[*].parameterValues.DE:Project Display Name`) is invalid here.

## Cascade limitation and Fusion workaround

This field works correctly in the browser UI — selecting an Account Name immediately re-fires the lookup and filters the project list.

**However:** if a Fusion scenario tries to read the value stored in "Active Projects for Client" via the data-extension API (e.g., `parameterValues['DE:Active Projects for Client']`), it returns empty when the field cascades off another External Lookup. This is a known limitation of how the data-extension API resolves chained lookup fields.

**Workaround for Fusion:** call the Workfront API directly using the `workfront-workfront:custom` Fusion module with the same URL pattern:

```
$$HOST/attask/api/v17.0/proj/search?status=CUR&DE:Client Name={DE:Account Name}&DE:Client Name_Mod=eq&fields=parameterValues
```

Then write the resolved value back to the record using an `updateARecord` operation. This bypasses the cascade issue by replicating the lookup logic directly in the Fusion scenario instead of reading the pre-stored lookup value.

## Notes

- Fields listed in **Dependencies** must be placed above this field on the form.
- The `DE:` field names in the URL must not be URL-encoded — `DE:Client Name` not `DE%3AClient%20Name`.
- The stored value on the record is the string extracted by the JSONPath — in this case, the `DE:Project Display Name` value. If you need the project ID, include it in `fields=` and adjust the JSONPath.
- See `12-external-lookup-fields.md` for the full reference including auth options and failure modes.
