# 03 — Create-from-Scratch Recipe (Flow 1)

End-to-end NL-create flow. Updated 2026-05-18 per Phase A empirical findings — the POST sequence in earlier drafts was wrong on the CategoryParameter step.

## Procedure

```
1. Confirm credentials
   ./skills/workfront-api/scripts/wf-creds-check.sh

2. Schema discovery (cached if recent; see `08-runtime-schema-discovery`)

3. Interview gaps (see 00-rubric, "Interview script — Flow 1")

4. Compose payloads:
   - Category POST body (with objTypes for the target objCode)
   - ParameterGroup POSTs (one per section, if grouping used)
   - Parameter POSTs (one per field — dataType + displayType + label per `02-parameter-types`)
   - ParameterOption POSTs (one per option per SLCT/CHCK/RDIO; bulk if ≥10, cap 100)
   - PUT to Category with nested categoryParameters (link step) AND nested categoryCascadeRules if the brief contained display-logic phrasings (see § Display logic (v0.26.0))

5. Show payload — print the call sequence with resolved JSON bodies + count
   ("this will fire N calls against $$HOST")

6. Single confirm: consultant types `apply`

7. Write in order (CORRECTED — see Phase A findings):

     POST /attask/api/v17.0/category               → categoryID
       body: name="<form-name>"
             objTypes=["PROJ"]   (multi-objCode requires updates= JSON)
             description="..."

     POST /attask/api/v17.0/parameterGroup × M (if grouping used)
       body per group: name, description, displayOrder
       → parameterGroupID[]

     For each field:
       POST /attask/api/v17.0/parameter
         body: name="wf_verify_<...>"   (snake_case ASCII; NO [ allowed)
               label="<UI label>"        (NO [ allowed)
               dataType=<TEXT|NMBR|DATE|CURC|RICH|WIDGET>
               displayType=<TEXT|SLCT|CHCK|RDIO|TXTA|MULT|TYAH|RICH|CALC|WIDGET|DTXT>
               formatConstraint=<optional render hint>
               isRequired=<bool>
               # description: OMIT unless the consultant explicitly asked for
               # end-user helper text. The `description` field renders as
               # "Instructions" under the field label in the form-fill UI —
               # do NOT write action-item refs, audit dates, or skill-internal
               # metadata into it. See `09-gotchas` § "Parameter.description
               # is end-user-facing".
         → parameterID

       [for displayType=SLCT/CHCK/RDIO only]
       Bulk PUT /attask/api/v17.0/parameterOption?method=POST&updates=[...]
         (up to 100 entries per call; chunk if >100)
         → parameterOptionID[]

     PUT /attask/api/v17.0/category/<categoryID>   ← LINK STEP (corrected)
       updates={"categoryParameters":[
         {"parameterID":"<p1>","displayOrder":1,"isRequired":false},
         {"parameterID":"<p2>","displayOrder":2,"isRequired":true,
          "parameterGroupID":"<g1>"},
         {"parameterID":"<calc-p>","displayOrder":3,
          "customExpression":"{DE:Spend Approved} > 50000"}
       ],
       "categoryCascadeRules":[                          ← NEW in v0.26.0 (cascade rules)
         {"ruleType":"DISPLAY",
          "nextParameterID":"<p3>",
          "toEndOfForm":false,
          "categoryCascadeRuleMatches":[
            {"matchType":"EXIST","parameterID":"<p1>","value":"Other"}
          ]}
       ]}
       → categoryParameter IDs come back as composite "<categoryID>_<parameterID>"
       → cascade-rule IDs auto-assigned; nested matches' categoryCascadeRuleID is auto-derived

8. Print result: form URL + the in-product builder URL + follow-up suggestions
   ("attach to existing records via dedicated bulk-update tooling")
```

**Total call count:** 1 (Category) + M (groups) + 2N (params + bulk-options) + 1 (final link PUT — also carries cascade rules) = `2 + M + 2N` typical. Cascade rules add zero new HTTP calls; they piggyback on the final PUT.

## Bulk-options handling

For DROP / RADIO / CHECKBOX parameters with many options (10+, real-world cases routinely 50–200), the skill supports four input modes:

1. **Inline paste** — line-separated, comma-separated, or `label = value` pairs (autodetected by `option_list_parser.py`).
2. **CSV / TSV import** — header row required; columns `label`, `value` (opt), `displayOrder` (opt), `isHidden` (opt).
3. **Clone options from an existing parameter** — same tenant: `--clone-options-from <parameterID>`. Cross-tenant: pass a source-tenant parameterID; ID sanitisation applies.
4. **Generate from a Workfront query** — e.g. "use the active portfolio names as options".

When option count ≥10, the skill switches from N sequential POSTs to a single bulk POST per chunk of 100.

> **Prod destination note:** the `WF_ENV_WRITE_ACK=1` prefix below assumes the consultant has typed `yes` to the prod-write-ack prompt for this batch. See `skills/workfront-custom-forms/SKILL.md` § Safety / Credentials.

```bash
WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh -X PUT \
  "/attask/api/v17.0/parameterOption?method=POST" \
  --data-urlencode 'updates=[{"parameterID":"<id>","label":"o1","value":"o1","displayOrder":1},...up to 100 entries...]'
```

**Bulk-POST cap is exactly 100 per call, atomic.** Verified 2026-05-18. 101+ entries → "Can not add more than 100 objects at once" with no rows inserted. For 200 options, chunk into 2 calls of 100.

## displayType is the gate for options

Before any ParameterOption POST, the parent Parameter MUST have `displayType` set to `SLCT`, `CHCK`, or `RDIO`. Posting an option to a `displayType=TEXT` parameter returns: `"Parameter with selected Display Type does not support Parameter Options"`.

## Label vs value handling

`ParameterOption.label` is the UI display (safe to rename). `ParameterOption.value` is what's stored on every record using the option — **changing a value later orphans every record's stored value.** The option_list_parser defaults `value = label` when only one is given. See `09-gotchas` gotcha #9.

## displayOrder

**Integer-only.** Decimals are rejected with `NumberFormatException`. Defaults to input position (paste-order preserved). Skill offers alphabetical sort before write when option count >10 and the input is unsorted.

## Failure recovery mid-sequence

If a call in step 7 fails after the sequence starts, the skill prints the IDs of whatever was already created plus exact `DELETE` curls:

- Categories: `DELETE /category/<id>?force=true`
- Parameters: `DELETE /parameter/<id>?force=true` (also clears its ParameterOptions)
- ParameterGroups: `DELETE /parameterGroup/<id>?force=true`
- CategoryParameters: not directly deletable (they were never created if the link PUT didn't run; if it partially ran, re-PUT with the desired subset to remove items)

No auto-rollback (matches the rejected-safety-machinery choice — same as `workfront-reports`).

## Verification prefix workaround for Parameter

The toolkit-wide `[wf-api-verify]` prefix convention applies cleanly to Category (`name=[wf-api-verify] Form Name`) but **breaks on Parameter** — Workfront rejects `[` in both `name` and `label`. Convention for Parameter verification:

- `Parameter.name`: snake_case ASCII, e.g. `wf_verify_vendor_name_20260518T130000Z`
- `Parameter.label`: regular string with `wf-verify` prefix (hyphens OK), e.g. `wf-verify Vendor Name`

This is enforced by `09-gotchas` and surfaced by the wrapper's Phase A-aware prefix policy.

## Display logic (v0.26.0)

Phase B-3 (2026-05-22) confirmed display logic IS REST-accessible via the `categoryCascadeRules` collection on Category — reverses the earlier v1 claim that this was UI-only. See `07-display-logic` for the wire format.

### How Flow 1 handles cascade rules

The consultant can volunteer display rules in their initial natural-language brief alongside the field list. **No separate interview phase** — the parser runs over the brief and lifts out any sentences that match a recognised pattern. Supported phrasings (see `skills/workfront-custom-forms/scripts/cascade_rule_parser.py` for the canonical list):

| Pattern | Builds |
|---|---|
| `show X when Y is Z` / `show X if Y equals Z` | DISPLAY rule, EXIST match |
| `hide X when Y is Z` / `skip X if Y equals Z` | SKIP rule, EXIST match |
| `show X when Y is NOT Z` / `show X unless Y is Z` | DISPLAY rule, NOTEXIST match |
| `show the rest of the form when Y is Z` | DISPLAY rule, `toEndOfForm: true` |
| `show X when Y is Z, otherwise show W` | DISPLAY rule, `otherwiseParameterID = W` |
| `when Y is Z and W is V` | Multi-match AND (one rule, two matches) |

Field and value names can be quoted (`'X'` or `"X"`) or left bare for single-word names. Keywords (`show`, `hide`, `skip`, `when`, `if`, `is`, `equals`, `unless`, `and`, `otherwise`) are case-insensitive; field names and values are preserved verbatim.

### Resolution + validation (runs before the apply gate)

1. Resolve each rule's trigger / target / multi-match by Parameter name to the IDs the skill is about to create. Names that don't match any field in the form → reject with the closest-name suggestion (likely consultant typo).
2. For SLCT/CHCK/RDIO triggers, validate each `value` exists as a `ParameterOption.value` on the trigger Parameter. Reject early with the available options — better than waiting for the server's `Cascade Rule Match value "X" is invalid` rejection.
3. Render the parsed rules in human-readable prose alongside the parameter list in the apply-gate prompt:

   ```
   Cascade rules to be created:
     Rule 1: Show 'Other notes' when 'Vendor type' = 'Other'
     Rule 2: Hide 'Approval notes' when 'Status' = 'Draft'
     Rule 3: Show the rest of the form when 'Region' ≠ 'EMEA'
   ```

   The consultant sees what the parser understood before any write. If wrong, they say "edit" and clarify.

### Payload integration

No new HTTP calls — the existing `PUT /category/<id>` link step (step 7's final call) carries both `categoryParameters` and `categoryCascadeRules` in the same `updates=` JSON body, as shown in the corrected sequence above.

### Out of scope (Flow 1)

- Section-level rules (`nextParameterGroupID`) — supported by Flow 2 modify; Flow 1 NL parser maps every target to a Parameter by default. If the consultant wants a group-level rule, use Flow 2 after the form is created.
- `ruleType=SKIP` is supported but rarely the natural NL phrasing — `hide X when Y is Z` is parsed as SKIP+EXIST, which is the canonical SKIP form.

## Cross-references

- `01-object-model` — the five-object graph (corrected objCodes + composite-key)
- `02-parameter-types` — full `dataType` and `displayType` enum
- `07-display-logic` — the `categoryCascadeRules` (CTCSRL/CTCSRM) wire format for show/hide rules
- `09-gotchas` — value-rename destruction, prefix workaround, silent fallback to TEXT
- `workfront-api` `knowledge/api/05-http-methods-and-actions.md` — bulk-POST tunneling pattern
