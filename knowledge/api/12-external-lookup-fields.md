# 12 — External Lookup Fields

An External Lookup is a custom form field type that makes an outbound HTTP GET (or POST/PUT) call to an external REST API each time a user opens or interacts with the field, then renders the response as a live dropdown. It is distinct from:

- **Static dropdowns** — options are entered manually at form-design time and never change without an admin edit.
- **Cascading dropdowns (via display logic)** — static options filtered by the value of another static field.
- **Scheduled API integrations** — systems like Fusion that pull data *into* Workfront on a schedule; External Lookup makes the call *on demand from the browser*.

Use External Lookup when the list of options lives in an external system (a CRM, ERP, planning tool, or another Workfront instance) and must always reflect the current state of that system at form-open time.

## Prerequisites and access requirements

| Requirement | Detail |
|---|---|
| Workfront license | Standard or higher for the admin creating the field |
| Admin access | Group admin or higher to create/edit custom forms |
| Feature availability | Available in the Form Designer (the current form builder); not available in the legacy custom form builder |
| Mobile | Filter/search functionality is unavailable on the Workfront mobile app |

No separate org-level toggle is required — External Lookup is available to all orgs using the Form Designer.

## Adding the field to a form

In **Setup → Custom Forms → Form Designer**:

1. Open or create a custom form.
2. In the left panel, locate **External Lookup** (single-select) or **Multi-Select External Lookup**.
3. Drag it onto the canvas.
4. Fill in the field settings in the right panel (described below).

## Field-level configuration

### Required fields

| Setting | Notes |
|---|---|
| **Label** | Display label shown to users |
| **Name** | Internal system name; auto-populated from label; cannot be changed after saving |
| **Base API URL** | The endpoint Workfront will call when the field renders |
| **JSON Path** | JSONPath expression targeting the array of option values in the response |

### Optional fields

| Setting | Notes |
|---|---|
| **HTTP Method** | `Get`, `Post`, or `Put` — nearly always `Get` |
| **Headers** | Key-value pairs sent with every request (see Authentication below) |
| **Format** | Data type of the selected value stored: Text, Number, or Currency |
| **Multi-Select Dropdown** | Allow more than one selection |
| **Required** | Force the user to make a selection before saving |
| **Dependencies** | Declare any fields whose values are referenced in the URL via `{fieldName}` tokens |

### Parameter substitution tokens

| Token | Resolves to |
|---|---|
| `$$HOST` | The current Workfront domain (e.g. `https://company.my.workfront.com`). Workfront handles session auth automatically for same-instance calls — no header needed. |
| `$$QUERY` | The text the user is typing in the search box; enables type-ahead filtering on the external API |
| `{fieldName}` | The current value of a native field on the object (e.g. `{portfolioID}`, `{projectID}`) |
| `{DE:FieldLabel}` | The current value of a custom field on the object (e.g. `{DE:Region}`, `{DE:Status Query}`) |
| `{referenceObject}.{fieldName}` | Cross-object field reference (e.g. `{project}.{status}`) |

Fields used via `{…}` tokens must be declared in the **Dependencies** list so Workfront knows to load their values before the lookup call executes. Fields listed as dependencies must be placed above the External Lookup field on the form.

**Caveat:** The precise set of supported token names and their exact syntax (capitalization, spacing) should be verified in a dev/preview form against your target object. Adobe's docs show consistent examples but do not publish an exhaustive token reference.

### Same-instance URL pattern (consulting standard)

When the External Lookup queries the **same Workfront instance**, the Base API URL must start with `$$HOST/attask/api/v17.0/`. `$$HOST` is the only correct way to reference the org's domain — hardcoding a domain (e.g. `https://company.my.workfront.com/...`) breaks any time the form is copied to another instance or the domain changes. Default to **v17.0** unless the user confirms their instance supports a newer version.

**Standard filter pattern inside the URL:**

```
$$HOST/attask/api/v17.0/proj/search?DE:Field Name={DE:Source Field}&DE:Field Name_Mod=eq
```

Note: `DE:` field names in the URL must not be URL-encoded (no `%3A` for `:`, no `%20` for space). Pass them as literal strings. See `04-fields-and-naming.md` for the full rule.

**To retrieve custom form values from another Workfront object,** add `&fields=parameterValues` to the URL:

```
$$HOST/attask/api/v17.0/proj/search?status=CUR&ownerID={ownerID}&fields=parameterValues
```

This causes each object in the response to include a `parameterValues` map with all its custom field values.

**JSONPath for custom form values:**

When using `&fields=parameterValues`, the correct JSONPath to extract a specific custom field value is:

```
$.data[*].parameterValues['DE:Custom Field Name']
```

Do not use dot notation for the `DE:` key (e.g. `$.data[*].parameterValues.DE:Custom Field Name`) — the colon and spaces make dot notation invalid here. Bracket notation with single quotes is required.

**Chained lookups — referencing another External Lookup field:**

When one External Lookup depends on the selected value of another External Lookup field on the same form, reference it directly with the `{DE:Field Name}` token pattern:

```
$$HOST/attask/api/v17.0/task/search?DE:Client Name={DE:Client Lookup Field}&DE:Client Name_Mod=eq&fields=parameterValues
```

Declare the upstream External Lookup field in the **Dependencies** list. No special syntax beyond the standard `{DE:FieldLabel}` token is needed.

> **Cascade limitation — important gotcha:** External Lookup fields that cascade off other External Lookup fields work correctly in the browser UI. However, **the data-extension API returns empty results when called from Adobe Workfront Fusion** for chained lookups. If you need to read a cascaded External Lookup value via Fusion, use the Workfront API directly via the `workfront-workfront:custom` Fusion module to call the same `$$HOST/attask/api/v17.0/...` endpoint, then write the result back to the record using `updateARecord`. This is a non-obvious consulting gotcha — it only surfaces when a Fusion scenario tries to read or validate cascaded lookup values programmatically.

## Expected response format

Workfront makes the HTTP request from its server infrastructure (not from the user's browser). The API must return a `2xx` status and a JSON body. Workfront uses the **JSON Path** expression to extract an array of strings or objects.

**Simplest form — flat string array:**
```json
["Option A", "Option B", "Option C"]
```
JSON Path: `$[*]`

**Object array with a display value:**
```json
{
  "data": [
    { "id": "acct-001", "name": "Acme Corp" },
    { "id": "acct-002", "name": "Globex Ltd" }
  ]
}
```
JSON Path to show names: `$.data[*].name`

The stored value on the Workfront record is the string extracted by the JSON Path (i.e., the display value, not an internal ID). If you need to store a structured value (e.g. an ID alongside a name), you must encode it into the string the API returns, or use a separate calculated field.

**Nested custom field values (same-instance call, using `&fields=parameterValues`):**
```json
{
  "data": [
    { "parameterValues": { "DE:Combo Colors": "Red" } }
  ]
}
```
JSON Path: `$.data[*].parameterValues['DE:Combo Colors']`

Note the bracket notation with single quotes — the colon and spaces in the `DE:` key name make dot notation invalid. The form `$.data[*].parameterValues.["DE:Combo Colors"]` does not work; use `['DE:...']` consistently.

**Maximum options returned:** 2,000 unique values. Options beyond that are silently dropped.

## Worked example — CRM client list

**Scenario:** A project request form needs a "Client" field populated from a hypothetical CRM whose REST API exposes a client search endpoint.

**CRM endpoint (fictitious):**
```
https://crm.example.com/api/v1/clients?search=$$QUERY&region={DE:Region}&active=true
```

**CRM response:**
```json
{
  "results": [
    { "clientId": "C-100", "displayName": "Acme Corp" },
    { "clientId": "C-101", "displayName": "Globex Ltd" }
  ]
}
```

**Field configuration:**

| Setting | Value |
|---|---|
| Label | Client |
| Base API URL | `https://crm.example.com/api/v1/clients?search=$$QUERY&region={DE:Region}&active=true` |
| HTTP Method | Get |
| JSON Path | `$.results[*].displayName` |
| Headers | `X-Api-Key: <your-crm-api-key>` |
| Dependencies | DE:Region |

**Result:** When a user types in the Client field, Workfront passes the typed text as `$$QUERY` and the value of the "Region" custom field as `{DE:Region}`, calls the CRM, and renders matching client display names as dropdown options.

## Authentication for the outbound call

| Method | How | Caution |
|---|---|---|
| No auth | Omit headers entirely | Only viable for public APIs |
| API key in header | Add `X-Api-Key: <key>` (or `Authorization: ApiKey <key>`) as a Header row | **Headers are visible to any admin who can edit the form and to any Workfront admin who can view Setup. Do not use this for high-privilege credentials.** |
| Bearer token | Add `Authorization: Bearer <static_token>` as a Header row | Same visibility caveat; if the token expires the lookup silently breaks |
| OAuth2 (dynamic) | Not supported natively — External Lookup cannot initiate an OAuth2 token exchange | Workaround: proxy through Workfront Fusion or a middleware layer that injects a fresh token |
| Same-instance Workfront API | Use `$$HOST`; no header required | Workfront injects the calling user's session; results are permission-filtered to that user |

Adobe's documentation explicitly warns: *"The Header fields are not a secure place to store credentials."* For production integrations with sensitive credentials, proxy the call through a Fusion scenario or a lightweight serverless function that handles auth and returns the filtered options.

## Caching behavior

Adobe's documentation does not specify whether External Lookup responses are cached per user, per session, or per field load. Based on community reports:

- The call appears to fire each time the field is rendered (form open) and each time the user types with `$$QUERY`.
- There is **no documented client-side or server-side cache** for the lookup result.
- Slow external APIs will block form interactivity — Workfront imposes a **30-second timeout** per call; the call retries **3 times** at 500 ms intervals before giving up.

**Verify in your instance** whether repeated opens of the same form within a session re-fire the API call.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Dropdown shows nothing (empty) | API returned a non-2xx status, the JSON Path didn't match any values, or the call timed out | Test the URL directly in a browser/Postman; confirm path against actual response shape |
| Dropdown empty in form preview | `{DE:FieldName}` tokens only resolve when the form is attached to a real object; preview has no object context | Test on an actual task/project/etc., not in the form designer preview |
| Dropdown shows `null` entries | The JSON path is matching a key whose value is null for some records | Add a filter in your API or tighten the JSON path |
| Options appear then immediately disappear | Dependency field above it changes and triggers a re-call; the replacement call is slower | Expected behavior; not an error |
| "Could not retrieve options" or silent blank | CORS — the external API is blocking the request from Workfront's server origin | CORS does not apply to server-side calls; if you're seeing this, the call may be firing client-side in some contexts. Confirm your external API allows requests from Workfront's IP ranges. |
| Static credential in header stops working | Bearer token or API key expired | Rotate the credential and update the Header row; anyone with form-edit rights can do this |
| Multi-select dependency yields string not array | Known behavior: if a multi-select External Lookup feeds a subsequent lookup via `{DE:Field}`, its value arrives as a string representation of the array | Validate in a dev environment; may require middleware normalization |

## Differences from related field types

| Feature | Static Dropdown | Cascading Dropdown (display logic) | External Lookup |
|---|---|---|---|
| Options source | Entered at design time | Entered at design time | Live API call at form-open time |
| Options update without admin | No | No | Yes (API controls the list) |
| Filterable by another field | No | Yes (via display/skip logic) | Yes (via URL tokens + dependencies) |
| Searchable by user input | No | No | Yes (via `$$QUERY`) |
| Reportable | Yes | Yes | Yes (value stored as a string) |
| Works in list views | Yes | Yes | Limited (see access restrictions above) |
| Requires external endpoint | No | No | Yes |

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleague.adobe.com/en/docs/workfront/using/administration-and-setup/customize/custom-forms/design-a-form/design-a-form` | Core configuration options, field settings, token reference, 2000-item cap, 30-second timeout, retry behavior |
| `https://experienceleague.adobe.com/en/docs/workfront/using/administration-and-setup/customize/custom-forms/design-a-form/external-lookup-examples` | Worked examples with exact URL patterns, JSON path syntax, $$HOST/$$QUERY/DE: token usage, authentication note for same-instance calls |
| Web search: "Workfront external lookup field custom form configuration URL response format JSON" | Confirmed JSON path syntax, maximum options (2000), dependency requirements, multi-select behavior, community-reported edge cases |
| Web search: "Workfront external lookup field caching behavior failure modes CORS" | Community-identified failure modes: preview-vs-object context, multi-select string/array mismatch, timeout/retry behavior |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/external-lookup-fields-host-currently-observed-behaviors-131405` | Community-documented $$HOST behaviors and observed edge cases |
