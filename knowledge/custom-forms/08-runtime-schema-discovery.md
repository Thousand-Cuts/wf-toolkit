# 08 — Runtime Schema Discovery

The skill discovers Workfront's per-tenant schema for the five custom-form objects at runtime, rather than hard-coding field names. Same pattern as `workfront-reports` and `workfront-permissions`.

## What we discover

Five parallel `/metadata` GETs on the first write of a session:

```
GET $$HOST/attask/api/v17.0/category/metadata
GET $$HOST/attask/api/v17.0/parameter/metadata
GET $$HOST/attask/api/v17.0/parameterGroup/metadata
GET $$HOST/attask/api/v17.0/parameterOption/metadata
GET $$HOST/attask/api/v17.0/categoryParameter/metadata
```

The skill consumes them to:

1. Confirm the **`dataType`** enum (TEXT / NMBR / DATE / CURC / RICH / WIDGET — Phase A confirmed 2026-05-18) and the **`displayType`** enum (TEXT / SLCT / CHCK / RDIO / TXTA / MULT / TYAH / RICH / CALC / WIDGET / DTXT). New tenant versions may add codes; metadata refresh surfaces them.
2. Confirm `formatConstraint` semantics per tenant (a free-form string — see `02-parameter-types`).
3. Confirm the Category target field is `objTypes` (string array) — Phase A confirmed it isn't `objCode` or `appliesTo`. Plus the derived `catObjCode` mirror.
4. Validate which fields are writable vs read-only on each object (note `Parameter.fieldDefinition` is read-only despite being a map).
5. Discover any tenant-specific cascading flags on CategoryParameter.

## Caching

Implemented by `skills/workfront-custom-forms/scripts/schema_cache.py`.

Cache file: `~/.cache/wf-claude-toolkit/custom-forms-schema-<sha8(host)>.json`. Mode 600. TTL 24h.

Invalidation:
- Time-based: 24h from `captured_at_epoch`.
- Content-based: stored `schemaHash` ≠ recomputed `schemaHash` (catches manual tampering or schema-shape drift).
- Explicit: `python3 -c "import schema_cache; schema_cache.invalidate('<host>')"`.

## Debug entry point

```bash
python3 -c "
import sys
sys.path.insert(0, 'skills/workfront-custom-forms/scripts')
import schema_cache, json
host = '<your-tenant-host>'
data = schema_cache.read(host)
print(json.dumps(data, indent=2) if data else 'no cache')
"
```

## Cross-tenant flows (clone)

Flow 5 maintains independent caches for source and destination tenants. Schema differences are themselves part of the diff output: the sanitiser surfaces source fields that don't exist on destination's metadata as "drop_default" findings.

## Cross-references

- `workfront-reports` `knowledge/reports/04-runtime-schema-discovery.md` — peer pattern
- `workfront-permissions` `knowledge/permissions/08-runtime-schema-discovery.md` — sibling implementation
