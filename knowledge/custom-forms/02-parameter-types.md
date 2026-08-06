# 02 — Parameter Types Reference

A Workfront custom field's "type" is actually **two fields** on the Parameter object:

- **`dataType`** — storage/value semantics
- **`displayType`** — UI render hint (also gates whether ParameterOption rows are accepted)

Both must be set at create-time. Workfront silently rejects unknown enum values for both and falls back to `TEXT`. **Use the canonical 4-letter codes verbatim.**

Verified empirically against a live production tenant v17.0, 2026-05-18, across 573 production parameters + create-time probes.

**API version notes.** The Phase A enums below reflect v17.0 (the toolkit default). v20 (2025-05) added `INTRNL`, `MULTINTRNL`, `UIEXTNSION` to `displayType`; v21 (2025-10) added `HTML` to `dataType`, `SNGLROLLUP` to `displayType`, and `Parameter.isActive`. The Phase B-1 / B-2 probes on client-d-preview (2026-05-22) discovered most of these empirically — they appear in the tables below — but won't work on a strictly v17.0-pinned tenant. See `../api/14-api-version-drift.md` § Custom Forms for the per-version breakdown.

## `dataType` enum

| Code | Meaning |
|---|---|
| `TEXT` | Text-flavored storage; also the value for USER pickers, GROUP pickers, DROP-style fields, etc. |
| `NMBR` | Number (integer / decimal — visual format via `displayType` or `formatConstraint`) |
| `DATE` | Date or datetime |
| `CURC` | Currency (separate from `NMBR`) |
| `RICH` | Rich text |
| `WIDGET` | Widget (specialised; usually visual elements) |

## `displayType` enum

| Code | Meaning | Accepts ParameterOption? |
|---|---|---|
| `TEXT` | Plain text input | No |
| `SLCT` | Single-select dropdown | **Yes** |
| `CHCK` | Checkboxes (multi-select) | **Yes** |
| `RDIO` | Radio buttons | **Yes** |
| `TXTA` | Textarea | No |
| `MULT` | Multi-select (variant) | likely yes (not verified) |
| `TYAH` | Typeahead / autocomplete | likely yes (not verified) |
| `RICH` | Rich text editor | No |
| `CALC` | Calculated (formula on the CategoryParameter link, not on Parameter) | No |
| `WIDGET` | **DEPRECATED in v17.0** as a standalone displayType. Phase B-1 (2026-05-22) probed the 15 replacements and confirmed they fall into 4 categories — see below. | No |
| `DTXT` | Date-text (rare; 2 samples in the survey) | No |
| `HIERARCHY` | Hierarchical picker (Phase B-confirmed on client-d-preview, 2026-05-22 — newer Workfront release than the surveyed tenant) | unknown — not probed |
| `ICON` | Icon picker (Phase B-confirmed on client-d-preview, 2026-05-22) | unknown — not probed |
| `LOCATION` | Location picker (Phase B-confirmed on client-d-preview, 2026-05-22) | unknown — not probed |
| `DOCUMENT` | Document-attachment field — Phase B-1 confirmed on client-d-preview as a drop-in displayType pair `(TEXT, DOCUMENT)` | unknown — not probed |
| `EXTRNL` | **External Lookup** — Phase B-2 confirmed authoring via `fieldDefinition: {link, jsonPath, httpMethod}` at create-time. See "External Lookup authoring" below. | No |
| `MULTEXTRNL` | External Lookup multi-value. Same `fieldDefinition` shape as EXTRNL. | No |
| `INTRNL` | **Internal Lookup** (Workfront-object typeahead). Phase B-2 confirmed authoring via top-level `refObjCode: <objCode>` (e.g. `USER`, `PROJ`). Server error message says "required key `[referenceObjectType]`" — that's the human-readable name; the actual API field is `refObjCode`. | No |
| `MULTINTRNL` | Internal Lookup multi-value. Same `refObjCode` top-level field. | No |
| `ADOBEXD`, `IMAGE`, `PDF`, `UIEXTNSION`, `VIDEO`, `WFNATIVE`, `WFPLANNING` | Widget subtypes — require `dataType=WIDGET`. Pairing pattern is `(WIDGET, <subtype>)`, e.g., `(WIDGET, ADOBEXD)` for an Adobe XD embed. Replaces the deprecated `(WIDGET, WIDGET)` pairing. | No |
| `ROLLUP`, `SNGLROLLUP`, `TIMEPHASED` | Aggregation displayTypes — require `dataType` from `{NMBR, CURC, DATE}`. Pairings: `(NMBR, ROLLUP)`, `(NMBR, SNGLROLLUP)`, `(DATE, TIMEPHASED)`, plus `(CURC, ROLLUP)`, `(CURC, SNGLROLLUP)` per server hint. Aggregates child-record values (sum / avg / min / max for ROLLUP; date-bucketed for TIMEPHASED). | No |

**Phase B-1 caveat:** the 8 displayTypes from DOCUMENT through TIMEPHASED were probed with a minimal `(TEXT, X)` payload. DOCUMENT and the lookup families returned recognized-but-needs-config errors confirming the displayType exists. The widget subtypes and rollup variants returned "wrong Format" errors confirming the displayType is real but the dataType pairing was wrong. Phase B-2 will re-probe with correct dataType + extra payload fields. See the internal verification notes.

Attempting to POST a ParameterOption to a parameter whose `displayType` doesn't accept options returns: `"Parameter with selected Display Type does not support Parameter Options"`.

## Per-objCode coverage matrix

Empirically verified via Phase B `phase_b_probe.py coverage-matrix` against a live tenant on 2026-05-22. 15 of 16 combinations work uniformly across the 7 supported objCodes; `(WIDGET, WIDGET)` is deprecated everywhere (see displayType enum above). Cells: ✓ accepted, ✗ rejected.

| (dataType, displayType) | UI label | DOCU | GROUP | OPTASK | PORT | PROJ | TASK | USER |
|---|---|---|---|---|---|---|---|---|
| `(TEXT, TEXT)` | Text field | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(TEXT, TXTA)` | Text area | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(TEXT, SLCT)` | Drop-down list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(TEXT, CHCK)` | Checkboxes | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(TEXT, RDIO)` | Radio buttons | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(TEXT, MULT)` | Multi-select | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(TEXT, TYAH)` | Typeahead | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(TEXT, CALC)` | Calculated text | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(NMBR, TEXT)` | Number | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(NMBR, CALC)` | Calculated number | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(CURC, TEXT)` | Currency | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(CURC, CALC)` | Calculated currency | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(DATE, TEXT)` | Date | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(DATE, CALC)` | Calculated date | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(RICH, RICH)` | Rich text | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `(WIDGET, WIDGET)` | Widget (deprecated) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

**Excluded objCodes (Category-create rejected):** `PROG`, `TMPL`, `TTSK` are NOT valid `Category.objTypes` values. Server returns `invalid value <X> for enum CategoryObjTypesEnum`. Custom forms cannot be created against Programs, Templates, or Template Tasks. See the internal verification notes § 1.



## `formatConstraint`

Free-form string. Workfront stores it verbatim — no enum validation at create-time. For `CURC` and `DATE` types it influences locale/precision/datetime mode; for `TEXT` and `NMBR` it's a hint that the UI may or may not honour depending on context. Empirical values seen in the survey: `CURRENCY`, `PERCENT`, `INTEGER`, `DECIMAL`, `DATE`, `TEXTAREA` — but also bogus inputs like `CURENCY` (typo) and `DOLLAR` were accepted unchanged.

Treat `formatConstraint` as a render-hint string, not a behavioural enum.

## What does NOT live on Parameter

- **`calculation` / formula body** — lives on the **CategoryParameter** join row as `customExpression`. The same Parameter can have different formulas on different forms.
- **`displayLogic` / show-hide rules** — not a field on Parameter at all; it lives on **Category** as the `categoryCascadeRules` collection (CTCSRL/CTCSRM), REST-accessible via GET-modify-PUT on the parent Category. See `07-display-logic`.
- **`defaultValue`** — not directly settable on Parameter via Phase A probes.
- **`fieldDefinition`** — **writable at create-time** (Phase B-2 correction; was previously documented as read-only). Carries 14 keys: `configurations, defaultValueFormula, dependencies, fieldType, format, formattingFormula, headers, httpMethod, isActive, isMultiSelect, isQueryRequired, jsonPath, link, validationFormula, valueEditabilityFormula`. For EXTRNL/MULTEXTRNL it's the primary configuration surface (see "External Lookup authoring" below). The 4 formula-fields (`defaultValueFormula`, `validationFormula`, `valueEditabilityFormula`, `formattingFormula`) likely accept calc-field syntax — empirically un-probed; Phase B-3 candidate.

## External Lookup authoring (EXTRNL / MULTEXTRNL)

Minimum POST body to create an External Lookup parameter:

```bash
WF_CLIENT_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh \
  -X POST /attask/api/v17.0/parameter \
  --data-urlencode 'updates={
    "name": "Choose Vendor",
    "label": "Choose Vendor",
    "dataType": "TEXT",
    "displayType": "EXTRNL",
    "fieldDefinition": {
      "link": "$$HOST/attask/api/v15.0/company/search?fields=ID,name",
      "jsonPath": "$.data[*].name",
      "httpMethod": "GET"
    }
  }'
```

The server auto-fills additional fieldDefinition keys: `fieldType` ("extrnl" or "multextrnl"), `isMultiSelect` ("false" for EXTRNL, omitted for MULTEXTRNL), `isQueryRequired` (false), `dependencies` ([]), `headers` ([]).

**Full fieldDefinition keys** (from existing production EXTRNL parameter):
- `link` — URL. Supports `$$HOST` token (resolves to tenant host) and `{DE:fieldName}` substitution tokens for cascading lookups.
- `jsonPath` — JSONPath for extracting display values from the response.
- `httpMethod` — typically `"GET"`.
- `dependencies` — array of `{DE:fieldName}` or `{queueTopic}.{name}` tokens that this lookup depends on (other fields whose values get substituted into `link`).
- `headers` — array of HTTP headers (e.g. for auth on external APIs).
- `isQueryRequired` — bool; whether the consultant must type something before the lookup fires.
- `isMultiSelect` — **string** `"false"` / `"true"` (NOT a boolean). EXTRNL = `"false"`; MULTEXTRNL surfaces it as null in our probe but production examples may vary.

See the internal verification notes § 1 for a cascading-lookup example and more shape detail.

## Internal Lookup authoring (INTRNL / MULTINTRNL)

Minimum POST body:

```bash
WF_CLIENT_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh \
  -X POST /attask/api/v17.0/parameter \
  --data-urlencode 'updates={
    "name": "Choose User",
    "label": "Choose User",
    "dataType": "TEXT",
    "displayType": "INTRNL",
    "refObjCode": "USER"
  }'
```

`refObjCode` lives at the top level of the Parameter body (NOT inside `fieldDefinition` like External Lookup). Accepted values: any Workfront objCode that supports typeahead (USER confirmed; PROJ/TASK/PORT/PROG/GROUP/ROLE plausible but unprobed).

MULTINTRNL uses the same `refObjCode` field; the multi-select behavior is implicit in the displayType.

Workfront's server error message when `refObjCode` is missing says `"required key [referenceObjectType] not found"` — that's the human-readable display name. The actual API field is `refObjCode` (camelCase).

**`TYAH` also accepts `refObjCode`.** Verified 2026-06-09 against a preview sandbox tenant v17.0: POSTing `{dataType: TEXT, displayType: TYAH, refObjCode: USER}` succeeds and creates a user-typeahead identical in behavior to INTRNL+USER (DE: write accepts a bare ID string; DE: read returns the canonical envelope `{"objCode":"USER","name":"...","ID":"..."}`). Without `refObjCode`, the TYAH stores raw strings with no typed resolution. **Must be set at POST time** — Workfront rejects all PUT attempts to add or change `refObjCode` on an existing typeahead parameter with *"You cannot change the referenced object value for an existing Typeahead field."* DE: value semantics and the parseJSON workaround are documented in `09-gotchas` § 30.

## Sample POST bodies

> **Prod destination note:** the `WF_CLIENT_WRITE_ACK=1` prefix on each example below assumes the consultant has typed `yes` to the prod-write-ack prompt for this batch. See `skills/workfront-custom-forms/SKILL.md` § Safety / Credentials for the full gate flow. If the active client is preview/sandbox, `WF_CLIENT_WRITE_ACK=1` is a no-op (the wrapper only enforces the ack on `WF_ENV_TYPE=prod` folders).

### Single-line text

```bash
WF_CLIENT_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh -X POST /attask/api/v17.0/parameter \
  --data-urlencode "name=wf_verify_vendor_name_<ts>" \
  --data-urlencode "label=Vendor Name" \
  --data-urlencode "dataType=TEXT" \
  --data-urlencode "displayType=TEXT" \
  --data-urlencode "isRequired=true" \
  --data-urlencode "fields=ID,name,label,dataType,displayType"
```

### Dropdown (needs ParameterOption rows after)

```bash
WF_CLIENT_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh -X POST /attask/api/v17.0/parameter \
  --data-urlencode "name=wf_verify_department_<ts>" \
  --data-urlencode "label=Department" \
  --data-urlencode "dataType=TEXT" \
  --data-urlencode "displayType=SLCT" \
  --data-urlencode "fields=ID"
# Then POST ParameterOption × N (or bulk PUT — see `03-create-form-recipe`)
```

### Currency

```bash
WF_CLIENT_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh -X POST /attask/api/v17.0/parameter \
  --data-urlencode "name=wf_verify_spend_approved_<ts>" \
  --data-urlencode "label=Spend Approved" \
  --data-urlencode "dataType=CURC" \
  --data-urlencode "displayType=TEXT"
```

### Calculated number (formula set later via CategoryParameter PUT)

```bash
WF_CLIENT_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-client-curl.sh -X POST /attask/api/v17.0/parameter \
  --data-urlencode "name=wf_verify_over_budget_<ts>" \
  --data-urlencode "label=Over Budget Flag" \
  --data-urlencode "dataType=NMBR" \
  --data-urlencode "displayType=CALC"
# Formula body goes in step "PUT /category/<id>" with categoryParameters:[...customExpression...]
```

## Parameter.name uniqueness

**`Parameter.name` is unique tenant-wide, NOT per-Category.** Surfaced during Phase B probing — attempting to POST a second Parameter with the same `name` (even attached to a different Category) returns `Parameter with name "<X>" already exists`. Consultants creating per-form fields with semantically-overlapping names (e.g. "Vendor Name" on two unrelated forms) need to disambiguate via the `name` field; the UI-facing `label` can still collide freely.

## Name vs label

- `name` — API-stable identifier (used in `DE:` filter syntax). **Cannot contain `[`** or other special characters. Recommended convention: snake-case ASCII (`wf_verify_vendor_name_20260518T130000Z`).
- `label` — UI display string. **Also cannot contain `[`**. The `[wf-api-verify]` prefix convention used elsewhere in the toolkit **does NOT** work on Parameter — use a no-brackets variant.

Both fields return `"Invalid character in 'name'/'label' : '['"` when `[` is present. See `09-gotchas` for the prefix-convention workaround.

## Cross-references

- `01-object-model` — the five-object graph (corrected objCodes)
- `03-create-form-recipe` — full POST sequence with these enums
- `09-gotchas` — `[` rejection, silent-fallback to TEXT, name uniqueness
- `workfront-calc-fields` — calc body syntax (formula text; stored on CategoryParameter)
