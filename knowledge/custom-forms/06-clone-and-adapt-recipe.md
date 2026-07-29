# 06 — Clone-and-Adapt Recipe (Flow 5)

Cross-environment clone: build and verify a form in one environment (typically the preview sandbox, e.g. `acme.preview.workfront.com`), then promote a sanitised copy to another (typically prod, e.g. `acme.my.workfront.com`). Updated 2026-05-18 per Phase A empirical findings — the POST sequence is corrected to PUT-on-Category for the link step, and the display-logic non-portability is now explicit.

## Resolving source and destination

Custom-forms clone uses the same source/dest pattern as the reports skill:

- **Source** — resolved via `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --source`. Any configured environment folder can serve as the source (typically the sandbox or preview environment where you build and verify forms). Activate the source slug via `/wf-env-use <source-slug>` (e.g. `sandbox`) and read via `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh`.
- **Destination** — resolved via `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --dest`. The active environment folder is where the cloned form will be written (typically `prod`). Refuse if `WF_READ_ONLY="1"`. If `WF_ENV_TYPE=prod`, prod-write-ack required for the write phases (see SKILL.md § Safety / Credentials): prepend `WF_ENV_WRITE_ACK=1` to every `wf-env-curl.sh` write call.

**Switch active environment between phases.** Reads (pulling from source) need the source slug active. Writes (POSTing to destination) need the dest slug active. Both use `wf-env-curl.sh`. Switch with:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-use.sh <slug>
```

Verify the wf-env-use confirmation line matches the slug you intended before proceeding.

## Procedure

```
1. Resolve SOURCE: bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --source
   (Reads via wf-env-curl.sh with the source slug active.)
2. Resolve DEST:   bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --dest
                   Refuse if WF_READ_ONLY=1. If WF_ENV_TYPE=prod, plan to prepend WF_ENV_WRITE_ACK=1 on writes.

3. Source pull (single GET with full expansion — v0.26.0 adds cascade rules):
   GET source/category/<id>?fields=ID,name,objTypes,description,categoryOrder,
       parameters:ID,parameters:name,parameters:label,
       parameters:dataType,parameters:displayType,parameters:formatConstraint,
       parameters:displaySize,parameters:isRequired,parameters:description,
       parameters:parameterOptions:ID,parameters:parameterOptions:label,
       parameters:parameterOptions:value,parameters:parameterOptions:displayOrder,
       parameters:parameterOptions:isHidden,parameters:parameterOptions:isDefault,
       parameterGroups:ID,parameterGroups:name,parameterGroups:description,
       parameterGroups:displayOrder,
       categoryParameters:ID,categoryParameters:parameterID,
       categoryParameters:parameterGroupID,categoryParameters:displayOrder,
       categoryParameters:isRequired,categoryParameters:customExpression,
       categoryParameters:hideFormulaFromDescription,
       categoryCascadeRules:ID,categoryCascadeRules:ruleType,
       categoryCascadeRules:nextParameterID,categoryCascadeRules:nextParameterGroupID,
       categoryCascadeRules:otherwiseParameterID,categoryCascadeRules:toEndOfForm,
       categoryCascadeRules:categoryCascadeRuleMatches:matchType,
       categoryCascadeRules:categoryCascadeRuleMatches:parameterID,
       categoryCascadeRules:categoryCascadeRuleMatches:value

4. Destination schema discovery (parallel; cached) — fetch /metadata for
   all 5 form objects on the destination environment.

5. Sanitise the source payload via form_sanitizer.sanitise_form_payload():
   - drop_default actions: customerID, ownerID, enteredByID, lastUpdatedByID
   - remap_required actions: categoryID, parameterID, parameterGroupID
     (these all need destination equivalents)
   - manual_review actions: any embedded user/role/group GUIDs in
     customExpression bodies
   - DE: parity-check actions: DE:<FieldName> references in
     customExpression that may not exist on destination

6. DE:-field parity check:
   For each DE: token found, GET dest/parameter/search?name=<bareName>
   If any are missing: BLOCK with a numbered list.

7. Mutation pass (optional):
   If the NL request includes changes, apply them to the sanitised payload
   before write.

8. Show payload + single `apply` confirm

9. Write to DEST (corrected POST sequence per Phase A):

     POST dest/category                       → dest_categoryID
       (Use objTypes per source; if source has multi-objCode, send via
        updates= JSON to preserve the array.)

     POST dest/parameterGroup × M             → dest_parameterGroupID[]
       (Direct POST — PGRP is a top-level object.)

     For each parameter:
       POST dest/parameter                    → dest_parameterID
       (Note: source's name may collide with an existing dest parameter;
        the sanitiser flags this and the admin either renames or skips.)

       [for displayType=SLCT/CHCK/RDIO]
       Bulk PUT dest/parameterOption?method=POST × ceil(N/100)
                                              → dest_parameterOptionID[]

     PUT dest/category/<dest_categoryID>      ← LINK STEP (corrected)
       updates={"categoryParameters":[
         {"parameterID":"<dest-p1>","displayOrder":N1,
          "parameterGroupID":"<dest-g1>","isRequired":true,
          "customExpression":"<rewritten formula referencing dest DE: names>"},
         ...
       ],
       "categoryCascadeRules":[                          ← NEW in v0.26.0
         {"ruleType":"DISPLAY",
          "nextParameterID":"<dest-p-target>",
          "otherwiseParameterID":null,
          "nextParameterGroupID":null,
          "toEndOfForm":false,
          "categoryCascadeRuleMatches":[
            {"matchType":"EXIST","parameterID":"<dest-p-trigger>","value":"Other"}
          ]},
         ...
       ]}

10. Print: dest URL + the source-to-dest ID mapping table.
    + cascade-rule cloning report (see "Cascade-rule cloning" below)
```

## Cascade-rule cloning (v0.26.0)

Phase B-3 (2026-05-22) confirmed display logic IS REST-accessible via the `categoryCascadeRules` collection — reverses the v1 "display logic doesn't clone" claim. Clone now lifts rules from source to dest with parameter-ID remap.

### Remap pipeline

1. **Source pull (step 3)** now requests `categoryCascadeRules:*` and `categoryCascadeRules:categoryCascadeRuleMatches:*`.
2. **Sanitization (step 5)** doesn't mutate the cascade-rule payload itself — only param/group IDs are flagged for remap. The cascade-rule wrapper stays intact.
3. **Partition (new step, runs after sanitization)** — call `form_sanitizer.partition_cascade_rules(source_payload, kept_param_source_ids, kept_group_source_ids)`. Returns two buckets:
   - `to_remap`: per-field substitution descriptors (`{rule_index, field, source_id, match_index}`)
   - `orphaned`: whole rules dropped because at least one referenced Parameter/Group was sanitized out
4. **Writer phase (step 9)** builds a source→dest ID map as each `POST /parameter` and `POST /parameterGroup` returns its dest ID. After all Parameters/Groups are created, walk `to_remap` and substitute `source_id` → `dest_id` on a deep-copy of the source rule list.
5. **Final PUT (step 9 link step)** carries the remapped `categoryCascadeRules` alongside `categoryParameters` in the same `updates=` body.

### Orphan handling — auto-skip + report

Per spec: rules whose references can't be cloned are auto-skipped, not prompted. Surfaced in:

- **End-of-run warning** printed to the admin:

  ```
  Cascade rules: 7 of 9 cloned successfully.
  Dropped 2 rules that depended on removed fields:
    - Rule referencing 'Project Manager' (dropped at Phase 5 sanitization)
    - Rule with target 'Approval Notes' (dropped at Phase 7 admin modification)
  The dropped rules are listed in <clone-report path> for recovery.
  ```

- **Clone-report artifact** (`~/wf-envs/<dest-slug>/exports/<UTC>-form-clone-cascade-orphans.md`) — contains the full source-side definitions of each orphaned rule so the admin can recreate manually via Flow 2.

Whole-rule policy (per `partition_cascade_rules`): if ANY field on a rule references a dropped ID, the entire rule is orphaned. We don't partially clone with broken matches.

## What does NOT clone

**Sharing / AccessRules.** v1 strips sharing on clone. Source-environment group IDs don't exist on the destination. Destination form defaults to admin-only visibility; adjust in-product.

**ParameterOption.isDefault.** Carried across for each option, but only one option per parameter can be the default — Workfront silently picks the lowest displayOrder default if multiple are flagged.

## Same-environment duplicate (v0.26.0)

**No REST `/copy` endpoint exists in v17.0.** The cross-skill metadata audit (2026-05-22) saw `copy` in Category's `operations` list and the v0.26.0 spec proposed routing same-environment duplicates through a one-call `POST /category/<id>/copy` fast-path. The smoke gate (2026-05-22, client-d-preview, v17.0) probed 6 URL+method variants and **all were rejected**:

| Variant | Server response |
|---|---|
| `POST /category/<id>/copy` | `unrecognized URI format: too many parts` |
| `POST /category/copy` (body `ID=<id>`) | `unrecognized URI format: too many parts` |
| `POST /category?method=copy&ID=<id>` | `Unsupported HTTP method: COPY` |
| `PUT /category/<id>?method=copy` | `Unsupported HTTP method: COPY` |
| `PUT /category/<id>/copy` (as action) | `does not support action copy (CTGY)` |
| `GET /category/copy?ID=<id>` (as named query) | `does not support namedQuery copy (CTGY)` |

`GET /category/<id>/copy` returns the source's own data (no clone created). The `copy` token in Category's `operations` metadata appears to be a UI-side hook, not a REST surface. Same finding empirically reproduced for Report's `copy` operation.

**The same-environment fast-path therefore does not exist via REST.** Same-environment duplicate runs the full Flow 5 sequence (steps 1-10 above) with the following simplifications:

1. **No ID sanitization needed** — Parameter / ParameterGroup IDs are tenant-scoped, so they're identical between source and dest within one environment.
2. **Cascade-rule remap is the identity function** — `partition_cascade_rules` returns every rule under `to_remap` with `source_id == dest_id`; orphan detection trivially passes since every source param exists on dest.
3. **DE: parity-check is a no-op** — same environment means same custom fields.
4. **Parameter-name collision IS an issue** — Workfront enforces tenant-wide unique `Parameter.name`. The duplicate Category needs new Parameter rows with new names (or it reuses the source's Parameters via the `categoryParameters` join, which is what the UI's Duplicate action does — but that means the duplicate Category shares Parameter rows with the source, and editing a field on the duplicate edits it on the source too. This is rarely what the admin wants for a "duplicate.")

**Recommended flow for "duplicate this form":**

- POST a new Category with the source's metadata (name suffix `" Copy"`).
- For each source Parameter: POST a new Parameter with a unique `name` (suffix with a discriminator) and the same `dataType` / `displayType` / options. The duplicate gets its own Parameter rows, so post-duplicate edits don't bleed back.
- Final link PUT with `categoryParameters` + `categoryCascadeRules` (rules carry over with identity remap on parameter IDs from the new-Parameter map).

This is functionally identical to a cross-environment clone where the dest schema happens to be the source schema — no shortcut available.

### Implication for the `parameter ID-reuse` claim

The original v0.26.0 design assumed `/copy` would reuse source Parameter rows (the UI's Duplicate action does this). Since `/copy` isn't reachable via REST, the duplicate-via-REST path creates new Parameter rows by necessity. The cascade-rule writer then uses the source→new-Parameter map (which is non-trivial, not identity) — the `partition_cascade_rules` infrastructure handles this exactly the same way as a cross-environment clone.

## Cross-environment safety

- **Never write to source.** Every interactive step banners the destination host + WF_ENV_LABEL.
- **Sanitisation is interactive.** A stripped `homeGroupID` might be desired or not.
- **DE: parity blocks the write** when missing prerequisites are detected.
- **Calc-body user/role/group GUIDs** in `customExpression` carry source-environment identity. Flagged for manual review.
- **Locale leak.** Hard-coded dates in calc bodies carry source-environment timezone. `$$TODAY` / `$$NOW` tokens are environment-neutral and pass through.
- **CategoryParameter composite IDs.** Source's `<src-cat>_<src-param>` doesn't transfer — every CategoryParameter on dest gets a fresh composite from `<dest-cat>_<dest-param>`.

## Where the artifacts land

- Sanitization report (output of `form_sanitizer.py`) → `~/wf-envs/<dest-slug>/exports/<UTC>-form-clone-sanitization.json`
- Source-to-dest ID mapping table (printed at end of run) → `~/wf-envs/<dest-slug>/exports/<UTC>-form-clone-id-map.md`

Use `$(date -u +%Y%m%dT%H%M%SZ)` for `<UTC>`.

## Cross-references

- `01-object-model` — IDs that need sanitisation, composite-key semantics
- `03-create-form-recipe` — base POST sequence
- `07-display-logic` — explicit non-portability
- `09-gotchas` — calc body leak; locale; sharing-isn't-cloned
- `form_sanitizer.py` in `skills/workfront-custom-forms/scripts/` — pure-Python walker
