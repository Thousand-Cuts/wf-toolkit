# 04 — Runtime Schema Discovery

The safety mechanism that lets `workfront-reports` survive Workfront's under-documented REPORT schema. Before any write to a tenant the skill hasn't seen this session, four parallel GETs against `/<object>/metadata` populate a host-hashed cache of live field names. Every subsequent write checks names against the cache instead of hard-coding. All examples use `v17.0` per `knowledge/api/01-api-fundamentals.md`.

## Why

Two facts force the runtime-discovery design:

1. **The REPORT object's field schema is not reliably published.** The `workfront-objcodes` npm package and the `python-workfront` v40 schema both omit Report-specific fields. Hard-coding any of them is fragile.
2. **Community evidence is split on the target-object field name** — some sources call it `uiObjCode`, others `reportObjCode`. Both refer to the same concept (the objCode the report reports on). The actual name depends on the tenant's Workfront version and configuration.

The skill resolves both at runtime by asking the destination environment directly: "what fields does your REPORT (and UIFT/UIGB/UIVW) accept?" — that's what `/<object>/metadata` returns.

## The 4-call burst

First write of a session against a given host. Four parallel GETs, then cache.

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/report/metadata > /tmp/report-meta.json &
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/uivw/metadata   > /tmp/uivw-meta.json   &
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/uift/metadata   > /tmp/uift-meta.json   &
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/uigb/metadata   > /tmp/uigb-meta.json   &
wait
```

The wrapper sources `~/wf-envs/<active>/.env` for the host and key — no `<key>` or `<host>` placeholders needed. These are GETs, so no `WF_ENV_WRITE_ACK` env var. In the clone flow, make sure the intended slug (source or destination) is active via `/wf-env-use` before running the burst.

Each response is the standard Workfront metadata envelope:

```json
{
  "data": {
    "name": "Report",
    "objCode": "REPORT",
    "fields": {
      "name": { "type": "string", "label": "Name" },
      "description": { "type": "string", "label": "Description" },
      "uiObjCode": { "type": "string", "label": "Report Object" },
      "filterID": { "type": "string", "label": "Filter ID" },
      "groupByID": { "type": "string", "label": "Group By ID" },
      "viewID": { "type": "string", "label": "View ID" },
      "categoryID": { "type": "string", "label": "Category ID" }
    },
    "collections": { /* ... */ },
    "references": { /* ... */ }
  }
}
```

The shape varies slightly across Workfront versions — that variability is exactly why the cache key includes a `schemaHash` (below).

## Caching

The skill invokes `scripts/schema_cache.py` to write the four responses into a single host-hashed JSON file:

```
~/.cache/wf-toolkit/reports-schema-<host-hash>.json
```

`<host-hash>` is the first 12 hex chars of `SHA-256(host)` — short enough to read, long enough that two real hosts never collide. Host-hashed (not host-literal) so the cache file name is opaque if the admin looks at the directory listing, and so multiple environments in one session (the clone flow) get independent caches.

The cache file's shape:

```json
{
  "host": "acme.my.workfront.com",
  "fetchedAt": "2026-05-13T14:22:55Z",
  "report": {
    "schemaHash": "sha256:9f1c...",
    "fields": ["name", "description", "uiObjCode", "filterID", "groupByID", "viewID", "categoryID", "..."]
  },
  "uivw": { "schemaHash": "sha256:...", "fields": ["name", "definition", "..."] },
  "uift": { "schemaHash": "sha256:...", "fields": ["name", "definition", "..."] },
  "uigb": { "schemaHash": "sha256:...", "fields": ["name", "definition", "..."] }
}
```

`schemaHash` is `SHA-256(<raw metadata response body>)`. The cache stores it alongside the parsed field list. If a future read sees the cache file fresh (within TTL) but a live metadata response with a different `schemaHash`, the cache invalidates and re-fetches — that protects against a tenant-side schema change inside the TTL window.

## Lookup

Before every write, the skill invokes `scripts/schema_cache.py get <host> <objCode>` to fetch the cached field list. The script:

1. Reads `~/.cache/wf-toolkit/reports-schema-<host-hash>.json` if present.
2. If absent OR `fetchedAt` is older than 24 hours OR the `schemaHash` doesn't match a fresh live response, re-runs the burst.
3. Returns the parsed field list for the requested objCode.

The skill's per-write logic:

```
for each field-name the skill plans to write:
  if field-name is in cached fields → use as-is
  else if a known-alternate is in cached fields (e.g. reportObjCode when uiObjCode is missing) → swap and print a one-line warning
  else → stop; surface the cached field list; ask the admin
```

## TTL and force refresh

**TTL:** 24 hours. After that, the next `get` call re-runs the burst transparently.

**Force refresh:** the admin can say "refresh the reports schema" or run:

```bash
python3 skills/workfront-reports/scripts/schema_cache.py refresh <host>
```

This deletes the cache file for that host and re-runs the burst on the next write.

## Schema-hash invalidation

The cache stores SHA-256 of the raw metadata response body. If the live metadata response shape ever changes (Adobe ships a new field, renames one, removes one), the hash changes and the cache invalidates rather than serving stale data.

This matters for the clone flow specifically: if the source environment is on a different Workfront version than the destination, the metadata shape may differ. The host-hashed cache key + the per-object `schemaHash` together guarantee source and destination caches never interfere.

## Debug entry point

```bash
python3 skills/workfront-reports/scripts/schema_cache.py inspect <host>
```

Prints the cache contents in human-readable form: host, `fetchedAt`, and the field list for each of the four objCodes. The skill exposes this via the NL phrase `workfront-reports schema` or `show me the reports schema for <host>`.

## Field-name resolution example

Concrete walkthrough for the `uiObjCode` vs `reportObjCode` case:

1. Skill is about to POST a REPORT row. The composed payload has key `uiObjCode`.
2. Skill calls `schema_cache.py get <host> report` and gets back the cached field list.
3. Searches for `uiObjCode` in the list.
   - **Present** → use `uiObjCode`. Send the payload as-is.
   - **Absent** → searches for `reportObjCode`. If present, swap the key in the payload and print: `WARN: this tenant uses 'reportObjCode' instead of 'uiObjCode'; renamed automatically.`
   - **Neither present** → stop. Print the cached field list filtered to anything matching `*obj*` or `*type*`. Ask the admin which field the tenant uses for the target object reference.

The same pattern applies to every field that isn't on the short whitelist in `01-report-object-shape.md`: chart fields, `categoryID`, any future REPORT-row fields v2 adds.

## How pre-flight validation uses the cache

Before any UIFT/UIGB/UIVW/REPORT POST, the skill runs `pre_flight_validator.py` (documented in `08-pre-flight-validation.md`). The validator's first action is to call `schema_cache.get(host, uiObjCode)` to retrieve the cached metadata for the report's target object. Every field reference in the about-to-POST bundle is checked against this cached field list:

- Bare field names (`status`, `plannedCompletionDate`) — must appear in `cached_metadata["fields"]`.
- Joined fields (`project:portfolioID`) — the validator walks each hop, resolving the relation's `targetTypeObjCode` to know which sub-object's metadata to check next.
- DE: custom-field references — bypass the per-object metadata and instead query `/parameter/search?name=<name>&name_Mod=eq` on the destination environment.

Cache hit means pre-flight runs entirely against in-memory data after the initial 4-call burst — sub-second. Cache miss triggers a metadata fetch via `schema_cache.put`.

If the validator finds the cache missing the target uiObjCode's metadata (rare — only happens when an admin changes uiObjCode mid-interview), it fetches that one metadata response and caches it before continuing.

## Cross-references

- The REPORT / UIFT / UIGB / UIVW field map (whitelist + UNVERIFIED names): `01-report-object-shape.md`.
- The recipes that invoke this discovery (Phase A.3 for create, Phase 7 for clone): `02-create-from-scratch-recipe.md`, `03-clone-and-adapt-recipe.md`.
- The script implementing the cache: `skills/workfront-reports/scripts/schema_cache.py`.
- Auth headers and host resolution: `workfront-api`.
