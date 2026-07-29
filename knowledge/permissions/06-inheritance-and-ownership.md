# 06 — Inheritance and Ownership

Two inputs from the 6-input model in `01-permission-model`. Both are notorious sources of "I have no idea why this user can see this" surprises.

Updated 2026-05-18 with Phase A empirical findings — **inheritance surfaces inline on the child object's `accessRules` collection**, so the explicit parent walk is largely unnecessary.

## Ownership

The owner of an object has implicit **`DELETE`** (Workfront's top-tier coreAction). Always. Cannot be removed without changing ownership.

Most-overlooked permission source. An admin debugging "why can Adam edit project X?" who hasn't checked `project.ownerID` will spend an hour walking sharing rules unnecessarily.

### Which objCodes have an `ownerID` field

Empirical from Phase A:
- `PROJ`, `PORT`, `PROG` — project / portfolio / program owner
- `REPORT`, `DASHBD` — report / dashboard owner (the creator by default)
- `TMPL` — template owner
- `DOCU` — document owner

Tasks (`TASK`), issues (`OPTASK`), hours (`HOUR`), and expenses (`EXPNS`) do NOT have a direct `ownerID` — they inherit from the parent project.

### Owner of a deactivated user

The deactivated user's owned objects retain them as `ownerID`. The implicit DELETE grant doesn't transfer. Result: an orphan. Surface via the composite audit "find objects owned by departed users" in `05-audit-recipes`.

## Inheritance — surfaces inline (Phase A)

A child object's `accessRules` collection includes inherited rules **inline**. Each inherited rule has:

- `isInherited: true`
- `ancestorID: <parent object GUID>`
- `ancestorObjCode: <parent objCode>` (e.g. `PORT`, `PROG`, `PROJ`, `FOLDER`)

Empirical example from a live-tenant scratch project:

```json
{
  "ID": "0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a01",
  "accessorID": "0b0b0b0b...0b0b02",
  "accessorObjCode": "USER",
  "coreAction": "DELETE",
  "isInherited": true,
  "ancestorID": "0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c03",
  "ancestorObjCode": "PORT",
  "securityObjCode": "PROJ",
  "securityObjID": "0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d04"
}
```

**Implication for the skill:** a single `GET /<obj>/<id>?fields=accessRules:*` returns both direct AND inherited rules with provenance. The explicit parent walk in `inheritance_walker.py` is **no longer needed for the headline debug flow**.

## When the inheritance walker IS still useful

The walker remains in the toolkit for cases the inline approach doesn't cover:

1. **"What rules COULD apply to this object if it were re-parented?"** — query the parents directly to see their full accessRules without needing the target to exist.
2. **"What sharing should I propagate downward when I create a new child?"** — same logic, but pre-creation.
3. **Tenants that don't surface `isInherited` inline** — the surveyed tenant does, but other tenants on different Workfront versions may not. The walker is the fallback.

## Cascade direction (downward only)

Permissions cascade **downward** through the hierarchy:

```
PORT (portfolio)               ↓ grants on PORT cascade to PROJ
  └── PROJ (project)           ↓ grants on PROJ cascade to:
        ├── TASK               ↓ task
        ├── OPTASK (issue)     ↓ issue
        ├── DOCU               ↓ document (on the project)
        ├── HOUR               ↓ hour entry against the project
        └── EXPNS              ↓ expense against the project

PROG (program)                 ↓ grants on PROG cascade to projects
  └── PROJ
```

**Sharing a project does NOT cascade upward** to its portfolio. The cascade is one-way.

### parent_path_for_objcode mapping

If using the walker (e.g. for the v2 use cases above), the parent map is:

```
TASK / OPTASK / DOCU / HOUR / EXPNS → PROJ → PORT, PROG
PROJ                                → PORT, PROG
PORT, PROG, TMPL                    → (no parents)
```

> TODO: Phase A didn't deep-test whether HOUR and EXPNS truly inherit from PROJ via the inline mechanism. Worth confirming on a future probe (would need a project with HOUR/EXPNS records and direct shares on the project).

### Folder hierarchy for DOCU

Documents have an additional folder cascade. A folder share grants access to documents in it (recursively to subfolders). The walker caps DOCU folder traversal at `FOLDER_DEPTH_CAP=10`.

Whether the inline `isInherited` surfaces folder ancestors specifically — not tested in Phase A. Defer to v2.

## Read-up vs Read-down query strategies

| Question | Approach |
|---|---|
| "Can user see this task?" | Single GET on the task with `accessRules:*` — inherited rules show up inline with their ancestor info |
| "Who can see this portfolio?" | GET on the portfolio + direct rules. Walk DOWN if you want to know who has additional access via project-level shares (children may have additional users via their own shares not represented at the portfolio) |
| "Can user see this project?" | Same as task — inline accessRules cover it. Direct vs inherited is in the `isInherited` field. |

The `05-audit-recipes` Flow 1 (debug) uses the inline approach. Flow 3 (object audit) uses direct rules + accessor expansion + (optionally) walks down to children if asked.

## Cross-references

- `01-permission-model` — the 6-input model
- `03-accessrule-shape` — ancestorID / ancestorObjCode / isInherited fields
- `04-debug-playbook` — Flow 1's simplified GET sequence
- `09-gotchas` — silent-inheritance surprises
