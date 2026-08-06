# 08 — Runtime Schema Discovery

The permissions skill discovers Workfront's per-tenant schema for three objects at runtime, rather than hard-coding field names. Same pattern as `workfront-reports` and `workfront-custom-forms`.

## What we discover

Three parallel `/metadata` GETs on the first write of a session:

```
GET $$HOST/attask/api/v17.0/accessLevel/metadata
GET $$HOST/attask/api/v17.0/accessRule/metadata
```

(Phase A 2026-05-18 confirmed `/customerInformation/metadata` returns empty; system-wide preferences aren't freely browsable via REST. See `07-system-wide-overrides`.)

Each returns the live field list. The skill consumes them to:

1. Confirm the AccessLevel field map. **The capability matrix is NOT a flat field** — it lives in the `accessLevelPermissions` collection (objCode `ALVPER`, accessible only as a child of AccessLevel). Phase A confirmed this.
2. Validate the `coreAction` enum. Phase A confirmed `ADD / DELETE / EDIT / LIMITED_EDIT / VIEW` on a live production tenant (2026-05-18). Other tenants may have additions.
3. Validate the `accessorObjCode` enum (`USER` / `GROUP` / `TEAMOB` / `ROLE` confirmed).
4. Confirm `forbiddenActions` shape — Phase A locked it down as `string[]` (a list, not CSV or dict). Common values: `EDIT_FINANCE`, `SHARE_SYSTEMWIDE`, etc. — see `03-accessrule-shape`.
5. Note: `AccessRule` (`ACSRUL`) is itself NOT a top-level object — `/accessRule/search` is rejected. Direct rule queries go via parent inline.

## Caching

Implemented by `skills/workfront-permissions/scripts/schema_cache.py`. See module docstring.

Cache file: `~/.cache/wf-claude-toolkit/permissions-schema-<sha8(host)>.json`. Mode 600. TTL 24h.

Invalidation:
- Time-based: 24h from `captured_at_epoch`.
- Content-based: stored `schemaHash` ≠ recomputed `schemaHash` (catches manual tampering or schema-shape drift).
- Explicit: `python3 -c "import schema_cache; schema_cache.invalidate('<host>')"`.

## When to refresh

- Adobe ships a new Workfront release — wait a day; let the 24h TTL invalidate naturally.
- Tenant admin creates a custom AccessLevel — schema fields are the same; no need to refresh.
- The skill reports a field-name mismatch error — force refresh and retry.

## Debug entry point

```bash
python3 -c "
import sys
sys.path.insert(0, 'skills/workfront-permissions/scripts')
import schema_cache, json
host = '<your-tenant-host>'
data = schema_cache.read(host)
print(json.dumps(data, indent=2) if data else 'no cache')
"
```

Prints the cached schema or "no cache" if no valid cache exists.

## Cross-tenant flows

For Flow 5 (cross-tenant access level compare), the skill maintains independent caches per host. Schema differences between source and destination tenants are themselves part of the diff output:

> "Source tenant uses `permissions` (dict-of-lists); destination uses `accessLevelPermissions` (list-of-dicts). The cross-tenant comparison normalises both shapes to a flat capability table before diffing."

The resolver's `_access_level_grants()` handles both shapes; the diff routine in Flow 5 normalises before comparing.

## Cross-references

- `workfront-reports` knowledge/reports/04-runtime-schema-discovery.md — peer pattern
- `workfront-custom-forms` knowledge/custom-forms/08-runtime-schema-discovery.md — sibling implementation
