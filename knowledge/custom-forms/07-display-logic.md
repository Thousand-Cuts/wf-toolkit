# 07 — Display Logic (REST-accessible via categoryCascadeRules)

**v0.13.x said:** Display logic (show/hide rules) is NOT REST-accessible in v17.0; configure in the Workfront UI.

**v0.25.0 (Phase B-3, 2026-05-22) reverses that claim.** Display logic IS REST-accessible via the `categoryCascadeRules` collection on Category. Phase A missed it because it enumerated Category's `fields` only, not its `collections`. The full write path — including server validation — was verified empirically (2026-05-22).

## The objects

Two non-top-level objCodes that live as nested collections on Category:

| objCode | Role | Parent |
|---|---|---|
| `CTCSRL` (CategoryCascadeRule) | The "what happens" half — which Parameter to show/hide when the rule fires | Category, via `categoryCascadeRules` |
| `CTCSRM` (CategoryCascadeRuleMatch) | The "when does it fire" half — which trigger Parameter and value to match against | CTCSRL, via `categoryCascadeRuleMatches` |

Neither is reachable via `GET /attask/api/v17.0/<objCode>/<id>` (they're not top-level). Read via parent: `GET /attask/api/v17.0/category/<id>?fields=categoryCascadeRules:*,categoryCascadeRules:categoryCascadeRuleMatches:*`.

## CTCSRL fields

```
ruleType                — "DISPLAY" or "SKIP" (binary enum, Phase B-4 confirmed)
nextParameterID         — what Parameter to show / skip when the rule fires (nullable)
nextParameterGroupID    — what ParameterGroup to show / skip (nullable; mutually exclusive with nextParameterID in practice)
otherwiseParameterID    — what to show if the rule does NOT fire (nullable; the "else" branch)
toEndOfForm             — boolean; when true, show all subsequent fields (skip to end)
```

`categoryID` and `customerID` are auto-derived; don't pass them.

### ruleType enum (Phase B-4)

| ruleType | Frequency in production (client-d-preview) | Semantic |
|---|---|---|
| `DISPLAY` | 382 | When the match condition fires, **show** the `nextParameterID` / `nextParameterGroupID` |
| `SKIP` | 0 | When the match condition fires, **skip** (hide) the target. Inverse of DISPLAY |

Both values are accepted by the API. `SKIP` is observed nowhere in client-d-preview production but is a valid enum value — likely corresponds to a UI option in the form-editor's logic panel that real-world tenants haven't used.

### Section-level (ParameterGroup) display logic (Phase B-4)

The same CTCSRL object handles both per-Parameter and per-Group cascade rules. Discriminator: which of `nextParameterID` / `nextParameterGroupID` is non-null. Verified empirically that setting `nextParameterGroupID` to a real PGRP ID creates a valid rule that persists. ParameterGroup itself has 9 fields and 0 collections — no group-level `cascadeRules` collection exists. Section-level logic is always authored on the parent Category.

PGRP create gotcha: requires `name` only (rejects `label` — `field 'label' is not available on com.attask.model.RKParameterGroup`). To attach a Parameter to a PGRP, add `parameterGroupID` to the `categoryParameters` row when PUTting on Category.

## CTCSRM fields

```
matchType               — "EXIST" or "NOTEXIST" (only 2 values in the enum; see below)
parameterID             — the trigger Parameter (whose value the rule inspects)
value                   — the value that triggers the match (must be a valid ParameterOption.value)
```

`categoryCascadeRuleID` and `customerID` are auto-derived from nesting.

### matchType enum is binary

Production survey across client-d-preview (400 CTCSRM rows):

| matchType | Count |
|---|---|
| `EXIST` | 396 |
| `NOTEXIST` | 4 |

**No other matchType values are accepted.** Probes for `NOT_EXIST` (with underscore — common guess), `EQUALS`, `IN`, `CONTAINS`, `NULL`, `NOT_NULL`, etc. all returned `Invalid Parameter: matchType value "<X>"`.

Workfront's display logic is therefore a binary trigger model: "trigger parameter has value X" or "trigger parameter does NOT have value X". For richer conditions, combine via AND (multi-match on a single CTCSRL) or OR (multiple CTCSRL rows on a single Category). For "EQUALS-like" semantics on free-text parameters, EXIST/NOTEXIST won't reach you — the matchType requires a concrete `value` to compare against, which works for SLCT/CHCK/RDIO/MULT (option-based) but doesn't extend to TEXT/NMBR/DATE arbitrary values.

Note the spelling: it's `NOTEXIST` (one token, no underscore). Easy to guess wrong.

## Authoring pattern

Create cascade rules via PUT-on-Category with the nested collection in the body:

```bash
WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  -X PUT /attask/api/v17.0/category/<cat_id> \
  --data-urlencode 'updates={
    "categoryCascadeRules": [
      {
        "ruleType": "DISPLAY",
        "nextParameterID": "<show_this>",
        "toEndOfForm": false,
        "categoryCascadeRuleMatches": [
          {"matchType": "EXIST", "parameterID": "<trigger>", "value": "Other"}
        ]
      }
    ]
  }'
```

**Collection-REPLACE semantics:** the PUT replaces the entire `categoryCascadeRules` list with what you send. To add a rule without dropping existing rules, GET-modify-PUT:

```bash
existing=$(... GET /category/<id>?fields=categoryCascadeRules:*,categoryCascadeRules:categoryCascadeRuleMatches:* ...)
# Merge new rule into existing[].categoryCascadeRules
# PUT the merged list back
```

This matches the standard Workfront REST behaviour for parent-collection writes (same as `categoryParameters`).

## Validation Workfront enforces

- The match `value` must be a real `ParameterOption.value` on the trigger Parameter. Reject message: `Cascade Rule Match value, "X" is invalid with associated Parameter, "<name>".`
- `nextParameterID` and `otherwiseParameterID` must reference Parameters that are attached to the same Category (via `categoryParameters` link). Otherwise the rule references nothing.
- `toEndOfForm: true` is compatible with `nextParameterID: null`. The "show to end" pattern doesn't need a specific next target.

Workfront does NOT validate that a multi-match condition is semantically satisfiable (e.g., "trigger=A AND trigger=B" — impossible since a parameter has one value at a time — is accepted by the server but the rule will never fire).

## Tested rule patterns (all returned PUT success + read-back persistence)

1. **Simple show-on-trigger:** `{ruleType:"DISPLAY", nextParameterID:T, matches:[{matchType:EXIST, parameterID:X, value:"V"}]}`
2. **Multi-match AND:** `matches: [{EXIST, X, "A"}, {EXIST, Y, "B"}]` — fires when X=A AND Y=B
3. **Else branch:** add `otherwiseParameterID: T2` to the rule
4. **End-of-form:** `{toEndOfForm: true, nextParameterID: null, matches: [{EXIST, X, "V"}]}`

## What this unblocks

- **Flow 1 (NL-create):** can now author cascade rules end-to-end. Interview the admin for trigger + condition + target, build the CTCSRL+CTCSRM payload, PUT it onto the Category in the same multi-call sequence as Parameter creation.
- **Flow 5 (cross-environment clone):** can now lift cascade rules along with the form. The `parameterID` references inside CTCSRL/CTCSRM need remapping (source IDs → destination IDs) the same way `categoryParameters.parameterID` does. `form_sanitizer.py` should be extended to walk `categoryCascadeRules`.
- **Flow 3 (single-form audit):** the audit output should include cascade rules — currently it only enumerates parameters.

## What's still NOT REST-accessible

A handful of UI-only configurations remain outside the REST surface:

- **Display logic on Section / ParameterGroup level** (vs Parameter-level cascade rules) — not separately probed; Phase B-4 candidate.
- **Conditional REQUIRED-state** (parameter becomes required when another parameter has a specific value) — likely a different ruleType than `DISPLAY` (server has only `DISPLAY` in production but the field exists, suggesting other ruleType values may be valid). Phase B-4 candidate.
- **Field formula authoring** (`defaultValueFormula`, `validationFormula`, `valueEditabilityFormula`, `formattingFormula` inside `fieldDefinition`) — surfaced in Phase B-2 but not probed for syntax. Phase B-3 candidate.

## Historical context

Earlier HAR-capture work (2026-05-18) captured the UI's `/internal/customForms/saveForm` payload and concluded the auth wall meant display logic was inaccessible. The work isn't wasted — the captured payload shape clarified how the UI bundles cascade rules with other form-edit operations. But the REST surface (`categoryCascadeRules` collection) is simpler and doesn't require any of the `/internal/*` auth scaffolding.

The Phase B lesson: when probing for a documented surface, enumerate both `fields` AND `collections` from `/metadata`. Filter both with the same keyword set. `categoryCascadeRules` would have been visible from day one if Phase A's metadata pass had included collections.

## Cross-references

- `knowledge/custom-forms/02-parameter-types.md` — ParameterOption shape (the `value` field is what cascade matches reference).
- `knowledge/custom-forms/01-object-model.md` — Category/Parameter/CategoryParameter relationships (cascade rules sit alongside these).
- `knowledge/custom-forms/03-create-form-recipe.md` — Flow 1 NL-create (will gain cascade-rule authoring in v0.26.0).
- `knowledge/custom-forms/06-clone-and-adapt-recipe.md` — Flow 5 cross-environment clone (will gain cascade-rule cloning in v0.26.0).
