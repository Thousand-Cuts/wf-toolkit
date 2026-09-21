# Vendored Adobe Workfront REST OpenAPI document

`workflow.json` is Adobe's published OpenAPI 3.0.1 description of the Workfront REST API.

- **Source:** <https://github.com/AdobeDocs/workfront-apis> (`static/workflow.json`)
- **Licence:** MIT, (c) Adobe. See the licence text in that repository.
- **Published equivalent:** <https://developer.adobe.com/workfront/api-explorer/>
- **Snapshot taken:** 2026-09-17
- **Content unmodified.** Vendored byte for byte.

## Two limits to know before relying on it

**It describes API v19.0; this toolkit pins v22.0.** Adobe publishes one OpenAPI document and it
trails the current version. The endpoint surface is the most stable part of the API, so treat this
as a reliable map of what exists, and confirm a specific endpoint against the tenant before
depending on it. `../14-api-version-drift.md` covers v20 through v22.

**It carries no field or enum definitions.** Every `components.schemas` entry is an external
`$ref` (`./Project.json` and similar) that Adobe resolves at build time by reading a live tenant's
`/metadata`. Those files are not in the repository and are not here. What the document does carry,
and what makes it worth vendoring, is each endpoint's **query parameters** — the part that is
otherwise undiscoverable without trial and error.

For field detail, use the live `/metadata` discovery the skills already do
(`skills/workfront-reports/scripts/schema_cache.py` and its siblings).

## Use it through the script

```bash
python3 skills/workfront-api/scripts/api_actions.py object optask
python3 skills/workfront-api/scripts/api_actions.py action bulkCopy
python3 skills/workfront-api/scripts/api_actions.py search template
python3 skills/workfront-api/scripts/api_actions.py generate   # rebuild 17-action-endpoint-catalog.md
```

## Refreshing

Re-download `static/workflow.json` from the upstream repo, replace this file, then run
`api_actions.py generate` and review the diff.
