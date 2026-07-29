# 04 — Add Field to Existing Form (Flow 2)

Shorter than Flow 1. Input is `categoryID` + field spec. Output is one new Parameter (+ options if applicable) linked via a PUT-on-Category step.

## Procedure

```
1. Resolve categoryID if a name was given:
   GET /category/search?name=<name>&name_Mod=eq&fields=ID,name,objTypes

2. Pull current form structure (needed to compute displayOrder and avoid
   wiping existing categoryParameters via the PUT collection-replace):
   GET /category/<categoryID>?fields=ID,name,objTypes,
       parameters:ID,parameters:name,parameters:dataType,parameters:displayType,
       parameterGroups:ID,parameterGroups:name,parameterGroups:displayOrder,
       categoryParameters:ID,categoryParameters:parameterID,
       categoryParameters:parameterGroupID,categoryParameters:displayOrder,
       categoryParameters:isRequired,categoryParameters:customExpression,
       categoryParameters:rowShared,categoryParameters:hideFormulaFromDescription,
       categoryParameters:securityLevel,categoryParameters:viewSecurityLevel

   **You must request `rowShared` and include it in every row of the step-6 PUT.**
   It controls two-up vs full-width layout. If omitted, every paired field
   collapses to its own row across the whole form — see "Field-style fields
   the PUT must round-trip" below.

3. Validate:
   - The Category's `objTypes` supports this (dataType, displayType)
     combination (some combinations may not work on all objCodes —
     Phase A only tested PROJ; widen as needed)
   - The Parameter.name doesn't collide with an existing parameter on this
     tenant (per-tenant uniqueness — see `09-gotchas`); surface with
     prefix recommendation like "PROJ_<name>" if collision occurs

4. Compute displayOrder:
   - Default: max(existing categoryParameter displayOrders) + 1
   - If the admin wants insert at specific position: bump subsequent
     entries by 1 (decimals NOT supported — see `09-gotchas`)

5. Show payload + single `apply` confirm

6. Write:

     POST /attask/api/v17.0/parameter
       body: name=<wf_verify_...>
             label=<UI label>
             dataType, displayType, formatConstraint, isRequired
       → parameterID

     [for displayType=SLCT/CHCK/RDIO]
     Bulk PUT /parameterOption?method=POST × ceil(N_options / 100)
       → parameterOptionID[]

     PUT /attask/api/v17.0/category/<categoryID>
       updates={"categoryParameters":[
         ...EXISTING categoryParameter rows (preserved verbatim from step 2)...
         {"parameterID":"<new-parameterID>","displayOrder":<new-order>,...}
       ]}
       → CategoryParameter composite ID "<categoryID>_<new-parameterID>"

7. Print:
   - parameterID + the composite categoryParameter ID
   - Field added to form "<name>" — visible on all <N> records using this form
   - If N > 0: "the field is empty on those <N> records; bulk backfill is
     outside this toolkit's scope — use in-product bulk edit or your own
     API scripting"
```

## Why the PUT must include existing rows

`PUT /category/<id>` with `updates={"categoryParameters":[...]}` is a **collection-replace** — entries not in the new list are dropped. Step 2 GETs the full current collection so step 6 can PUT all existing rows plus the new one. Forgetting to include existing rows wipes the form.

> **Strip the composite `ID` from every echoed row.** Include each row's `parameterID` (plus the round-trip fields below), but **not** its composite `ID` (`<categoryID>_<parameterID>`). If any parameter on the form is an External Lookup field (`EXTRNL` / `MULTEXTRNL` / `TYAH`), sending `ID` makes Workfront re-validate that field's `link`/`jsonPath`/`httpMethod` schema — which isn't API-readable — and the entire PUT 400s. Keying by `parameterID` alone reconciles the same rows without that validation. Harmless on forms without external-lookup fields. See `09-gotchas` #32.

## Field-style fields the PUT must round-trip

Collection-replace replaces *the whole row*, not just the keys you mention — so any field you don't echo back is reset to its default. The non-obvious offenders on CategoryParameter:

| Field | What it does | Reset behaviour if omitted |
|---|---|---|
| `rowShared` | Two-up layout: `true` means this field shares a row with its sibling, rendering as a 2-column pair in the UI | Reset to `false` → field renders full-width on its own line. **Every paired field on the form collapses to single-column.** |
| `customExpression` | The formula on calc fields (displayType=CALC) | Calc body lost — the field still exists but stops computing |
| `hideFormulaFromDescription` | Calc-field UI flag controlling whether the formula text appears in the field's description tooltip | Reset to `false` → formula leaks into UI description |
| `securityLevel` / `viewSecurityLevel` | Per-field edit/view security (LE, V, etc.) | Reset to defaults — field becomes editable/viewable to roles that previously couldn't see it |

Pattern that bites: on a form with no calc fields, calc-field preservation isn't needed, so it's tempting to drop `customExpression` and `rowShared` "since I don't see them being used." `rowShared` is the trap — it's used silently for visual layout on most non-trivial forms.

Verified on `client-d.preview.workfront.com`, v17.0, 2026-05-21: a PUT that bumped displayOrders on 321 of 354 rows but omitted `rowShared` from the payload zeroed all 94 paired rows on the form. Re-syncing `rowShared` from prod (94 paired rows) and re-PUTting restored the layout.

## displayOrder insertion strategies

`displayOrder` is integer-only. To insert at position 3 of a 5-field form:

**Strategy A (preferred): bump and insert**
- Existing rows have displayOrder 1, 2, 3, 4, 5
- Bump rows 3-5 to 4-6 in the PUT
- New row at displayOrder=3
- Total cost: same single PUT (collection-replace handles it atomically)

**Strategy B: append + UI re-order**
- New row at displayOrder=6 (or 100 to be safe)
- Tell the admin to drag it into position in the UI
- Cheaper if the admin doesn't care about exact integer ordering

The skill defaults to **Strategy A** since it keeps the API and UI in sync.

### Server-side renumbering inside `parameterGroupID`

Workfront silently re-numbers `displayOrder` after PUT if the new row is assigned to a `parameterGroupID` that already has populated rows — the server places the new row at the next available position **inside that section**, not at the absolute integer you sent.

Empirical example (`client-d.preview.workfront.com`, v17.0, 2026-06-02): a PUT that appended a row to a 363-row form with `displayOrder: 364` and `parameterGroupID: <Creative-Intake-section>` came back from the verifying GET with `displayOrder: 15` — slotted in after the section's last existing row (the Creative Intake informational fields were at displayOrders 1–14 in that section).

Implications:
- You can't "force" a row to a specific displayOrder inside a populated section by passing a high integer — the server collapses it back.
- If absolute ordering matters, you must either (a) PUT with `parameterGroupID: null` (rare; orphans the field from its section) or (b) renumber every row inside the target section in the same PUT so your row's intended position is the only valid slot. Both are heavier than letting the server slot it.
- Verifying GET should always check `displayOrder` against the request, not just confirm row count. A mismatch is the server having opinions about your integer.

## Parameter.name collision handling

Workfront rejects duplicate `name` values tenant-wide. Pre-flight check:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/parameter/search \
  --data-urlencode "name=<proposed-name>" \
  --data-urlencode "name_Mod=eq" \
  --data-urlencode "fields=ID,name"
```

If a row comes back, suggest a variant: prefix with the objCode (`PROJ_vendor_name`), suffix with a discriminator (`vendor_name_v2`), or append a timestamp.

## Cascade-rule sub-flow (v0.26.0)

In addition to adding fields, Flow 2 supports adding, editing, and removing display logic on an existing form. The wire format is the same `categoryCascadeRules` collection documented in `07-display-logic`; collection-replace semantics mean every operation is GET-modify-PUT.

### Add a rule

```
1. Resolve categoryID (same as add-field step 1).

2. GET current rules + matches + the form's parameters (needed for name → ID resolution):
   GET /category/<categoryID>?fields=
       parameters:ID,parameters:name,
       categoryCascadeRules:*,
       categoryCascadeRules:categoryCascadeRuleMatches:*

3. Print existing rules, numbered, in the same prose form as Flow 1:
     Rule 1: Show 'Other notes' when 'Vendor type' = 'Other'
     Rule 2: Hide 'Approval' when 'Status' = 'Draft'

4. Parse the admin's NL request via cascade_rule_parser.parse_cascade_rules().
   Validate names against the form's actual Parameter list (see "validation"
   below).

5. Append the new rule to the existing list. Print the resulting full list
   numbered. apply gate.

6. PUT /category/<id> with updates={"categoryCascadeRules":[<full list>]}.
```

### Edit a rule

Same GET as add. The admin references the rule by number ("edit rule 2: change condition to 'Status' is 'In Review'"). Parser produces the replacement; the existing rule at that index is replaced verbatim. apply gate. PUT.

### Remove a rule

Same GET. The admin references rules by number ("drop rule 1 and 3"). Filter the existing list. apply gate. PUT.

### Validation (all three sub-flows)

1. Every `trigger_param_name`, `target_param_name`, `otherwise_param_name`, and each `multi_match[].trigger_param_name` must resolve to a Parameter currently on the form. If not, reject with the closest available Parameter name (likely a typo).
2. For SLCT/CHCK/RDIO triggers, validate each `value` exists as a `ParameterOption.value` on the trigger Parameter. The server's own error (`Cascade Rule Match value "X" is invalid with associated Parameter, "<name>"`) is acceptable as a fallback, but pre-check produces a better experience for the admin.
3. If an edit would orphan a rule by changing the trigger to point at a non-existent Parameter, **reject the edit** rather than silently writing a bad rule.

### Why GET-modify-PUT (and not PUT just the one rule)

`categoryCascadeRules` is collection-REPLACE on PUT — same semantics as `categoryParameters` (see "Why the PUT must include existing rows" above). PUTting only the new rule wipes every existing rule on the form. Always GET first.

### Section-level rules (`nextParameterGroupID`)

Phase B-4 (2026-05-22) verified section-level display logic uses the SAME CTCSRL object, discriminated by which `next*` field is non-null:

- `nextParameterID` set, `nextParameterGroupID` null → per-Parameter rule
- `nextParameterID` null, `nextParameterGroupID` set → section-level rule (whole ParameterGroup shown/hidden)

If the admin says "show the Approval section when Status is Active", the NL parser maps "the Approval section" to the form's ParameterGroup by name, and the resulting CTCSRL uses `nextParameterGroupID` instead of `nextParameterID`.

## Cross-references

- `03-create-form-recipe` — full create flow (Flow 1); this file is the smaller sibling
- `01-object-model` — what `categoryParameters` collection looks like
- `07-display-logic` — `categoryCascadeRules` + CTCSRL/CTCSRM wire format
- `09-gotchas` — `name` rejection on `[`, name uniqueness scope, displayOrder integer-only
- Backfilling new field values across existing records is outside this toolkit's scope — use in-product bulk edit or your own API scripting
