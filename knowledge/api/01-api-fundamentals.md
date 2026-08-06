# 01 — API Fundamentals

The Workfront REST API exposes the same objects, fields, filters, and query syntax as text mode — accessed over HTTP. Use it for automation, integrations, bulk operations, and data extraction beyond what reports can do.

If you already know text mode, you already know most of the API's filter and field syntax. The differences are wrapping (HTTP method, URL, headers, JSON body) — not the underlying query language.

## Base URL

```
https://<yourdomain>.my.workfront.com/attask/api/v<version>/<objectType>/<objectID>
```

Find `<yourdomain>` in **Setup → System → Customer Info**. The object type is case-insensitive and accepts either the abbreviated OBJCODE (`proj`) or the full name (`project`). See `03-object-codes.md` for the full list.

**Environment URLs:**

| Environment | URL pattern |
|---|---|
| Production | `https://<domain>.my.workfront.com/attask/api/v<version>/...` |
| Preview / Sandbox | `https://<domain>.preview.workfront.com/attask/api/v<version>/...` |

The Preview Sandbox refreshes weekly from production (Friday → Monday). Credentials match production credentials as of the last refresh. Email notifications and report delivery are disabled in Preview.

## API Versioning

The version segment (`v15.0`, `v17.0`, etc.) is required in every URL. Omitting it routes to the default version, which changes with each release — integrations relying on the default version break silently when Workfront releases a new API version. Always pin a version.

**Current supported versions (as of 2026-05):**

| Version | Released | Unsupported from |
|---|---|---|
| 22 | May 2026 | ~2029 |
| 21 | Oct 2025 | ~2028 |
| 20 | May 2025 | ~2028 |
| 19 | Oct 2024 | ~2027 |
| 18 | Apr 2024 | ~2027 |
| 17 | Oct 2023 | ~2026 |
| 16 | Apr 2023 | ~2026 |
| 15 | H1 2022 | Deprecated Dec 2025 |

Each version is supported for 3 years, then enters a 1-year deprecated state (still accessible, not fixed), then removed. Versions 1–14 were removed September 30, 2025.

**`api-internal`** — An unversioned path that always reflects the latest internal build. Subject to change without notice. Do not use in production. Replace with a versioned URL.

## Choosing a version (consulting default)

When you don't know which version a client's instance supports, default to **v17.0**. It has been stable across virtually every modern Workfront deployment and avoids breaking against older instances. Use a newer version only when the user explicitly confirms — or you can verify — that their instance supports it.

Newer API versions introduce new behaviors and fields, but consulting work usually targets the lowest common denominator. v17.0 is the safe floor: it predates several breaking changes introduced in v18+ while still supporting all common authentication flows, filter patterns, External Lookup fields, and `parameterValues` access.

**In practice:** if a user says "our instance is on 22.3," switch to the version they need. If they don't know or don't say, write all examples with `v17.0` and note the assumption.

## JSON Response Envelope

Every response is JSON. The envelope shape depends on whether the call succeeded or failed.

**Success (single object):**
```json
{
  "data": {
    "ID": "4c78821c0000d6fa8d5e52f07a1d54d0",
    "name": "My Project",
    "status": "CUR"
  }
}
```

**Success (list / search):**
```json
{
  "data": [
    { "ID": "...", "name": "Project A" },
    { "ID": "...", "name": "Project B" }
  ]
}
```

**Error:**
```json
{
  "error": {
    "error": "Invalid session ID.",
    "class": "com.attask...",
    "attributes": {}
  }
}
```

An error response always has an `error` key at the top level (never `data`). The inner `error` field contains the human-readable message.

**Count response** (from the `/count` endpoint):
```json
{ "count": 42 }
```

## HTTP Status Codes

Workfront does not exhaustively document which HTTP codes it returns for which errors. What's confirmed from documentation and community observation:

| Code | When |
|---|---|
| `200 OK` | Successful GET, PUT, DELETE |
| `201 Created` | Successful POST (object created) |
| `400 Bad Request` | Malformed request, invalid field/value |
| `401 Unauthorized` | Missing or invalid session / API key |
| `403 Forbidden` | Valid credentials but insufficient permission |
| `404 Not Found` | Object ID doesn't exist |
| `429 Too Many Requests` | Concurrent request limit hit |

HTTP `429` is the rate-limit signal. See `09-pagination-and-limits.md` for more on concurrency throttling.

## Content Types

**Requests:** Workfront accepts two formats for request body parameters:

- **Form-encoded** (default for most operations): `Content-Type: application/x-www-form-urlencoded`
- **JSON via `updates` parameter:** pass a JSON string as the value of the `updates` form parameter on PUT/POST calls

```
PUT /attask/api/v17.0/project/4c7...
Content-Type: application/x-www-form-urlencoded

updates={"name":"New Name","status":"CUR"}
```

For complex nested updates, the `updates` JSON approach is cleaner than trying to encode nested structures in form parameters.

**Responses:** Always `application/json`.

## Query Parameters vs. Request Body

For GET requests, all parameters go in the query string. For POST/PUT, parameters can go in the query string or the body (form-encoded). When both are present, query string parameters take precedence. URL query strings have an **8,892-byte maximum** (enforced by the Workfront CDN for production, preview, and test-drive environments) — for large filter sets, use a POST body instead.

## What you can rely on from text-mode knowledge

Every concept in the text-mode knowledge folder maps to the API:

- **OBJCODEs** (file `03-object-codes.md`) — same `PROJ`, `TASK`, `ASSGN` codes in URLs and request bodies.
- **Field names** (file `04-fields-and-naming.md`) — same camelCase, same `DE:` prefix for custom fields.
- **Filter modifiers** (file `06-filtering-queries.md`) — `eq`, `ne`, `cicontains`, `in`, `isnull` work identically as URL query parameters.
- **EXISTS / NOTEXISTS** (file `07-exists-in-api.md`) — same pattern, URL-encoded in query strings.
- **Wildcards** (file `06-filtering-queries.md`) — `$$USER.ID`, `$$TODAY`, date math work in API filter values.

## When to use the API vs text mode vs Fusion

- **Text mode reports:** the user wants to see data inside Workfront. The audience is a Workfront user clicking around.
- **API:** the user wants data outside Workfront, or wants to push changes programmatically. The caller is a script, an integration, or a dashboard.
- **Adobe Workfront Fusion:** low-code orchestration. Often calls the API under the hood. Prefer Fusion when the work is integration-shaped (move data between systems) and the API when the work is custom-scripted or one-off bulk.

Pick based on consumer, not capability — the API can do almost everything text mode can, and vice versa for read paths.

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/api-general-information/api-basics` | Base URL format, response envelope, HTTP methods, pagination, rate limit notes, content types, session auth |
| `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/api-notes/api-version-support-schedule` | Full version support table with release and deprecation dates |
| `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/api-notes/specify-api-version-integrations` | Versioning best practices, default version behavior |
| `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/tips-troubleshooting-apis/locate-domain-for-api` | Production domain format |
| `https://experienceleague.adobe.com/en/docs/workfront/using/administration-and-setup/set-up-wf/testing-environments/wf-preview-sandbox-environment` | Preview sandbox URL format, refresh cadence, auth behavior |
| `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/api-notes/deprecation-api-internal` | api-internal deprecation guidance |
