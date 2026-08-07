# 09 — Gotchas

The most common ways consultants get tripped up by Workfront custom forms. Updated 2026-05-18 with Phase A empirical findings. Renumbered 2026-07-07 to remove duplicate headings (the file had accumulated two `## 15`s and a scrambled 11-16 block from separate edit passes); gotcha #15 also corrected — see below.

## 1. Parameter renames don't update `DE:` references

**Surprise:** "I renamed `Vendor Name` to `Supplier Name`. My existing `DE:Vendor Name` filters still work, but `DE:Supplier Name` finds nothing."
**Mechanic:** Workfront keeps an internal alias from the parameter's original `name`. Existing `DE:OldName` references continue to function; new `DE:NewName` references won't match unless you also update the consuming places.
**Diagnostic:** Run Flow 4b ("which forms have field Y?") with both old and new names.

## 2. Hard-block: changing `dataType` or `displayType` destroys data

**Surprise:** "I switched this field from `(TEXT, TEXT)` to `(TEXT, SLCT)`. The previous values are gone."
**Mechanic:** Changing either of the two type fields deletes existing values across every record. Workfront does not migrate values automatically.
**Mitigation:** Wrapper hard-block. Skill refuses the modify. Recommendation: create a new field with the new types, migrate values via dedicated bulk-update tooling, then delete the old field.

## 3. Form attachment is per-record, not per-form-definition

**Surprise:** "I added a field to the form. The 200 existing projects show the new field, but it's empty everywhere."
**Mechanic:** Adding a field propagates the structure instantly; values are not back-filled. Each existing record has the new field at null until set.
**Mitigation:** Flow 2 (add field) prints attachment count and routes to dedicated bulk-update tooling for backfill.

## 4. Per-tenant uniqueness of `Parameter.name`

**Surprise:** "I can't create a second `Vendor Name` field for issues — Workfront says it already exists."
**Mechanic:** Tenant-wide unique constraint on `Parameter.name`. Confirmed empirically: `Parameter with name "X" already exists.` (Code: 0, msgKey: `exception.attask`.)
**Mitigation:** Use prefixed naming: `PROJ_Vendor_Name`, `OPTASK_Vendor_Name`. Pre-flight check via `/parameter/search?name=<proposed>&name_Mod=eq`.

## 5. `[` is rejected on Parameter `name` and `label`

**Surprise:** "I'm using `[wf-api-verify]` as the prefix per the toolkit convention. It's rejected."
**Mechanic:** Workfront rejects `[` (and likely other special chars) in both `name` and `label` on Parameter. Error: `Invalid character in 'name'/'label' : '['`. Empirically confirmed.
**Mitigation:** Use a no-brackets variant for verification objects on Parameter:
- `Parameter.name`: snake_case ASCII like `wf_verify_vendor_name_<ISO8601>`
- `Parameter.label`: hyphenated like `wf-verify Vendor Name`
- Category is fine — `[wf-api-verify]` works on `Category.name`.

This means the toolkit-wide prefix convention is partially incompatible with custom forms. The `wf-curl.sh` wrapper (maintainer-side, for the `[wf-api-verify]` flow) enforces a Phase A-aware prefix policy that maps `Parameter` to the `wf_verify_` snake_case variant. For client-engagement writes through `wf-client-curl.sh`, there is no prefix enforcement at all — the wrapper has no prefix guard, since real client forms shouldn't carry a verify-prefix in the first place.

## 6. `objTypes` is immutable

**Surprise:** "I created this form for PROJ but I meant DOCU. Can I retarget?"
**Mechanic:** Once a Category is created with a particular `objTypes`, you can't change it. Must recreate.
**Mitigation:** Skill warns at design time when the target objCode is ambiguous.

## 7. Calc fields with hard-coded tenant identifiers don't clone cleanly

**Surprise:** "The cloned form's `Over Budget` calc returns nothing on the client's tenant."
**Mechanic:** A `customExpression` that references `$$USER.ID = 'guid'` (tenant-specific) or hard-coded portfolio/group GUIDs breaks on destination.
**Diagnostic:** Form_sanitizer flags these during Flow 5 (clone) as `manual_review`.

## 8. Sharing isn't auto-cloned

**Surprise:** "The cloned form is admin-only — source had it shared with the whole Marketing team."
**Mechanic:** v1 strips form sharing on clone. Groups don't exist on destination; the remap is interactive and error-prone.
**Mitigation:** Adjust in-product after clone. v2 may automate.

## 9. Renaming a `ParameterOption.value` is destructive

**Surprise:** "I updated this dropdown option from `high` to `high_priority`. All the records that had `high` selected now show as empty."
**Mechanic:** `ParameterOption.value` is what's stored on every record. Changing it orphans every stored value (records display the *label* until reload, but the stored value no longer matches any option). `ParameterOption.label` is the UI display only and is safe to rename.
**Mitigation:** Skill hard-blocks any modify-flow that changes a `value`. Recommends: create a new option, migrate stored values via dedicated bulk-update tooling, then hide or delete the old option.

## 10. Bulk options need bulk POST — cap is exactly 100

**Surprise:** "Adding 200 country options via sequential POSTs takes 4 minutes."
**Mechanic:** N sequential POSTs cost N round-trips. The bulk-POST tunnel handles up to 100 per call. 101+ rejects all entries atomically with `"Can not add more than 100 objects at once."`
**Mitigation:** `option_list_parser.py` + Flow 1 auto-switch to bulk POST when option count ≥10, and chunk into 100-row batches when >100.

## 11. Unknown `dataType` / `displayType` silently falls back to TEXT

**Surprise:** "I passed `displayType=DROPDOWN` but the field renders as plain text."
**Mechanic:** Workfront silently accepts ANY string for these enums and stores `TEXT` for unknown values — no error returned. You only notice when the UI renders wrong.
**Mitigation:** Use the canonical 4-letter codes verbatim (see `02-parameter-types`). Pre-flight validation in the skill: confirm the passed values are in the empirical enum before POSTing.

## 12. CategoryParameter is not a top-level object

**Surprise:** "I tried POST /categoryParameter and got `CTGYPA is not a top level object`."
**Mechanic:** CategoryParameter rows are created via **PUT to the parent Category** with a nested `categoryParameters` collection. Direct POST/GET on the endpoint is rejected.
**Mitigation:** Use the PUT-on-Category pattern from `03-create-form-recipe` step 7's link step. CategoryParameter IDs come back as composite `<categoryID>_<parameterID>`.

## 13. `categoryParameters` PUT is a collection-replace

**Surprise:** "I added one new field and the existing 6 fields disappeared from the form."
**Mechanic:** PUT to Category with `updates={"categoryParameters":[...]}` REPLACES the collection. Entries not in the new list are dropped.
**Mitigation:** Flow 2 GETs the existing categoryParameters first and PUTs all existing rows plus the new one. See `04-add-field-to-existing-form`. **On forms that contain External Lookup fields, strip the composite `ID` from each echoed row — see gotcha #32** — or the whole PUT 400s.

## 14. `displayOrder` is integer-only

**Surprise:** "I tried `displayOrder=1.5` to insert between 1 and 2 — got `NumberFormatException`."
**Mechanic:** Workfront's parser rejects decimals. Integer-only.
**Mitigation:** Bump-and-insert when inserting mid-list. The wrapper / skill handles this in Flow 2.

## 15. Display logic IS REST-accessible via `categoryCascadeRules` — not UI-only

**Surprise (historical, now corrected):** Phase A's empirical survey found no field on any of the 5 custom-form objects' metadata that obviously represented display logic — four candidate endpoints (`parameterRule`, `paramRule`, `fieldRule`, `parameterDisplayRule`) all returned empty — and concluded display logic was UI-only in v17.0. **That conclusion was wrong** and is superseded below.

**Mechanic:** Phase B-3 (2026-05-22) found the actual REST surface: the `categoryCascadeRules` collection on Category (`CTCSRL` for the rule, `CTCSRM` for its nested matches). It's read and written via the same PUT-replace-on-parent pattern as `categoryParameters` — see gotcha #25 for the exact GET/PUT shape and `07-display-logic.md` for the full JSON schema plus the `ruleType` (`DISPLAY`/`SKIP`) and `matchType` (`EXIST`/`NOTEXIST`) enums.

**Mitigation:** Author, read, or migrate display logic via the API using `07-display-logic.md`'s GET-modify-PUT sequence — there's no need to fall back to the Custom Form Editor UI. v0.26.0 ships NL cascade-rule authoring in Flow 1, a GET-modify-PUT cascade-rule sub-flow in Flow 2, cascade-rule rendering in the Flow 3 audit, and source→dest cascade-rule remap in Flow 5 clone.

## 16. Multi-objCode Category requires `updates=` JSON

**Surprise:** "I sent `objTypes=PROJ&objTypes=TASK` as form fields. The Category only targets PROJ."
**Mechanic:** Repeated form params only keep the first/last value. Workfront's multi-objCode support is JSON-only:
```
updates={"name":"...","objTypes":["PROJ","TASK","OPTASK"]}
```
**Mitigation:** Skill uses `updates=` JSON when more than one objCode is supplied.

## 17. `matchType` on cascade rules is `NOTEXIST`, not `NOT_EXIST`

**Surprise:** "I tried to write a cascade rule with `matchType: NOT_EXIST` and got 'Invalid Parameter'."

**Mechanic:** Workfront's `CategoryCascadeRuleMatch.matchType` enum is binary: `EXIST` and `NOTEXIST`. The latter is one token, no underscore. Common guess `NOT_EXIST` (with underscore, mirroring `NOT_EQUALS` / `NOT_IN` patterns) is rejected. Production survey across client-d-preview (400 CTCSRM rows) confirmed only these two values are used. No EQUALS / IN / CONTAINS / NULL variants exist.

**Mitigation:** Use `NOTEXIST`. If you need richer match semantics, combine multiple rules (OR via multi-CTCSRL on a Category) or multiple matches (AND via multi-CTCSRM on one CTCSRL). For TEXT/NMBR/DATE parameters where there's no fixed value set to "EXIST" against, display logic doesn't reach you — that pattern isn't supported.

## 18. `operations` metadata can lie — `copy` isn't a REST surface

**Surprise:** Category's `/metadata` lists `operations: [add, copy, count, delete, edit, get, report, search]`. The intuitive "POST `/category/<id>/copy`" returns `unrecognized URI format: too many parts`. Six URL+method variants all rejected (smoke gate 2026-05-22, client-d-preview, v17.0):

| Variant | Server response |
|---|---|
| `POST /category/<id>/copy` | `unrecognized URI format: too many parts` |
| `POST /category/copy` | `unrecognized URI format: too many parts` |
| `POST /category?method=copy&ID=<id>` | `Unsupported HTTP method: COPY` |
| `PUT /category/<id>?method=copy` | `Unsupported HTTP method: COPY` |
| `PUT /category/<id>/copy` (as action) | `does not support action copy (CTGY)` |
| `GET /category/copy?ID=<id>` (as namedQuery) | `does not support namedQuery copy (CTGY)` |

`GET /category/<id>/copy` returns the source's own data with no clone created. Same finding for Report's `copy` operation.

**Mechanic:** The `copy` token in `operations` is a UI-side hook (likely consumed by the in-product "Duplicate" action via `/internal/*`), not a REST verb. The metadata audit (2026-05-22 cross-skill audit) flagged `copy` as a same-tenant-clone fast-path — that assumption was wrong.

**Mitigation:** For same-tenant duplicates, run the full Flow 5 cross-tenant sequence with identity-remap simplifications. See `06-clone-and-adapt-recipe` § "Same-tenant duplicate".

**Lesson:** Before basing a Flow design on a `operations` / `actions` token in metadata, verify the URL is actually reachable with at least one minimum-payload probe. Phase B-style empirical verification beats metadata enumeration when the two disagree.

## 19. Category does not expose `parameters` as a nested traversal field

**Surprise:** Phase A's Flow 3 audit recipe documents `GET /category/<id>?fields=parameters:ID,parameters:name,parameters:label,...` to pull the joined Parameter rows in one round-trip. On client-d-preview (v17.0, 2026-05-22 smoke gate) this returns `APIModel V17_0 does not support field parameters (Category)`.

**Mechanic:** Category exposes the join via `categoryParameters` (the CTGYPA composite), not via `parameters` directly. To get Parameter names you need either:

```bash
# Two-step: get param IDs, then fetch their names
GET /category/<id>?fields=ID,name,categoryParameters:parameterID,...
# then for each parameterID:
GET /parameter/search?ID=<p1>,<p2>,...&fields=ID,name,label,dataType,displayType
```

```bash
# Or use /metadata's custom census (v0.26.0 Flow 4b path):
GET /<objcode>/metadata  # data.custom maps Parameter.name → categories[]
```

**Mitigation:** Flow 3 audit recipe in `05-audit-recipes` needs to drop the `parameters:` nested-traversal pattern and replace with the two-step lookup. Pending update.

## 20. ParameterGroup (PGRP) rejects `label` on create

**Surprise:** "I tried to POST `/pgrp` with `{name: 'Section A', label: 'Section A'}` and got `field 'label' is not available on com.attask.model.RKParameterGroup in version INTERNAL`."

**Mechanic:** Unlike Parameter and Category — which carry both `name` (internal) and `label` (UI-facing) — ParameterGroup has only `name`. The 9 PGRP fields are `ID, customerID, description, displayOrder, extRefID, isDefault, lastUpdateDate, lastUpdatedByID, name`.

**Mitigation:** POST with `name` only. The UI shows the `name` value as the section header.

## 21. `Parameter.description` is end-user-facing — do NOT write skill metadata into it

**Surprise:** "I created a parameter with `description='added 2026-05-26 per action item #1787'`. The consultant filling out the form now sees that string as 'Instructions' under the field label."

**Mechanic:** `Parameter.description` is rendered to every user filling out the form as the field's **Instructions** helper text in the Workfront UI. It is NOT a backstage / audit / changelog field. Notes for the consultant should go in commit messages, action-item notes, or the toolkit's own logs — never on the Parameter object.

**Mitigation:** Leave `description` empty by default. Only populate it when the consultant explicitly asks for user-facing helper text (e.g., "add the instructions 'Use ISO format' under this date field"). Hard rule: agent-generated audit markers, action-item IDs, dates, and skill-internal metadata are forbidden in this field. Same applies to `Category.description` (form-level instructions shown to filers) and `ParameterGroup.description`.

## 22. `CategoryParameter.securityLevel` is an enum string, not an integer

**Surprise:** "I added a new CP via PUT-replace with `securityLevel: 0`. The PUT failed with `Cannot invoke ParameterSecurityLevelEnum.getAction() because securityLevel is null`."

**Mechanic:** Despite the error wording, `securityLevel` and `viewSecurityLevel` are not numeric — they're enum strings. Existing CPs come back with `securityLevel: "LE"` (Limited Edit) and `viewSecurityLevel: "V"` (View). Passing the integer `0` fails the enum lookup and surfaces as "is null".

**Mitigation:** When constructing a new CP for PUT-replace, copy enum values verbatim from an existing CP in the same Category. Default for newly-added fields: `securityLevel: "LE"`, `viewSecurityLevel: "V"`. Other enum values exist (FE/Full Edit, etc.) — match an existing peer rather than guessing.

## 23. `parameterGroup` doesn't filter by `categoryID` — fetch by ID list instead

**Surprise:** "I tried `GET /parameterGroup/search?categoryID=<id>` to list a form's sections. Got `APIModel V17_0 does not support field categoryID (ParameterGroup)`."

**Mechanic:** ParameterGroup has no `categoryID` field. The relationship is the other direction: each `CategoryParameter` row carries `parameterGroupID`, so groups are discovered by walking the form's CP collection. Once you have the IDs, batch-fetch via `GET /parameterGroup?ID=<id1>,<id2>,...&fields=ID,name,description`.

**Mitigation:** Pattern:
```bash
# 1. Get the form's CPs, extract distinct parameterGroupIDs
GET /category/<id>?fields=ID,categoryParameters:parameterGroupID
# 2. Batch fetch group metadata
GET /parameterGroup?ID=<csv>&fields=ID,name,description
```

## 24. Section render order is determined by min `categoryParameter.displayOrder`, NOT `parameterGroup.displayOrder`

**Surprise:** "I changed `parameterGroup.displayOrder` to reorder sections. Nothing happened — the form still renders in the old order."

**Mechanic:** Empirically (client-d sandbox, 354-CP Marketing Request form, 2026-05-26): every `parameterGroup.displayOrder` was `0` while the form rendered sections in a clearly meaningful order. Workfront orders sections by the **minimum `displayOrder` of the categoryParameters belonging to that group** within the Category — the parameterGroup's own `displayOrder` is unused in v17.0 render.

**Mitigation:** To reorder sections, renumber the constituent CPs' `displayOrder` so the new section's first field comes before the next section's first field. This is a category-wide CP renumber, not a parameterGroup tweak. Flow 2 (modify display logic / add field) handles this when the consultant says "move section X up".

## 25. `CategoryCascadeRule` (CTCSRL) metadata reports `operations: []` but PUT-replace via Category works fine

**Surprise:** "I tried `POST /categoryCascadeRule` to add a new display-logic rule. `/metadata` shows `operations: []` so direct POST seemed wrong."

**Mechanic:** Like `categoryParameter` (CTGYPA), `categoryCascadeRule` is owned by Category and updated via PUT to the parent with the full `categoryCascadeRules` collection replaced. The empty `operations` array reflects "no top-level surface for this object" rather than "writes are blocked". Nested `categoryCascadeRuleMatches` come along inside each rule's payload (no separate write call needed for matches).

**Mitigation:** Use the PUT-replace pattern:
```bash
GET  /category/<id>?fields=categoryCascadeRules:*,categoryCascadeRules:categoryCascadeRuleMatches:*
# mutate the list (add / remove / edit rules in-place)
PUT  /category/<id> updates={"categoryCascadeRules": [...full new list...]}
```
New rules use `objCode: "CTCSRL"`, omit `ID` (Workfront assigns); nested matches use `objCode: "CTCSRM"`, omit `ID` and `categoryCascadeRuleID` (auto-filled).

## 26. Category POST requires `objTypes` array, not `catObjCode`

**Surprise:** "I POSTed a new Category with `{name, catObjCode: 'PRGM'}` and got `Cannot invoke CategoryObjTypesEnum.getFeature() because objTypeEnum is null` — even though the GET response on every Category has `catObjCode` as a top-level field."

**Mechanic:** The wire format on Category POST/PUT is `objTypes: ["PRGM"]` (an array, even for a single object code). `catObjCode` is a derived read-only field on the GET response. Passing `catObjCode` on POST leaves `objTypeEnum` null on the server side and the validator surfaces a misleading exception.

**Mitigation:** Always POST/PUT a Category with the array form:
```bash
POST /attask/api/v17.0/category
  updates={"name":"Campaign Details","objTypes":["PRGM"]}
```
For single-objCode forms it's a one-element array; for multi-objCode forms it's `["PROJ","TASK"]` etc. See `03-create-form-recipe` step 7.

## 27. Workfront's Program objCode is `PRGM`, not `PGRM`

**Surprise:** `objTypes: ["PGRM"]` returns `invalid value PGRM for enum CategoryObjTypesEnum`.

**Mechanic:** Easy 4-letter typo. Workfront's Program is `PRGM` (the letters are P-R-G-M, not P-G-R-M).

**Mitigation:** Verify objCode strings against `01-object-model`'s reference table before composing the body. The 4-letter enum is unforgiving: `PROJ`, `TASK`, `OPTASK`, `PORT`, `PRGM`, `TMPL`, `USER`, `DOCU`, `COMPANY`, etc.

## 28. Brand-new PRGM-attached CategoryParameters reject `securityLevel`/`viewSecurityLevel` values

**Surprise:** "First-ever PRGM custom form. PUT to link parameters fails with `Specified section break security cannot be applied on all object types`, even though I'm passing the same `securityLevel: 'LE'` / `viewSecurityLevel: 'V'` values that PROJ-attached CPs use."

**Mechanic:** The enum values for `securityLevel` and `viewSecurityLevel` aren't universally valid across all `objTypes`. PROJ accepts `"LE"` / `"V"`; PRGM (and possibly other less-common types) doesn't recognize them yet on a fresh form, surfacing the section-break-security error. Workfront seems to need these omitted so it can apply the type-appropriate default.

**Mitigation:** When linking CategoryParameters to a category whose `catObjCode` you haven't seen before (especially PRGM, PORT, COMPANY, USER), omit `securityLevel` and `viewSecurityLevel` from the CP rows entirely. Workfront fills in the correct defaults server-side. For known types (PROJ, TASK, OPTASK) the explicit `"LE"` / `"V"` pattern remains fine — see gotcha #22.

## 29. EXTRNL / MULTEXTRNL parameter PUTs require the full External Lookup schema

**Surprise:** "I tried `PUT /parameter/<extrnl-paramID>?updates={'label':'New Label'}` to rename an existing External Lookup field. Got `Error in field schema validation: required key [link] not found, required key [jsonPath] not found, required key [httpMethod] not found`."

**Mechanic:** External Lookup parameters (`displayType=EXTRNL`, `MULTEXTRNL`, or sometimes `WIDGET`) carry a required schema with `link`, `jsonPath`, and `httpMethod` fields that describe the external HTTP endpoint they call. Any PUT against the Parameter row must include this full schema — even if you're only changing the label. Workfront's validator runs a full-schema check on PUT, not a partial-field merge.

**Mitigation:** Before PUTting an EXTRNL parameter:
1. `GET /parameter/<paramID>?fields=*,link,jsonPath,httpMethod` to capture the existing schema
2. Build the PUT body with all required fields preserved + your changes
3. PUT

Skill v0.26.x's External Lookup AUTHORING is out of scope — but reading + minimal PUT-with-preserved-schema is feasible if needed. For relabel/rename, often safer to leave the parameter alone and create a fresh one.

**Note:** this same schema check also fires *indirectly* on a parent Category `categoryParameters` collection PUT when the row carries its composite `ID` — even if you only meant to touch an unrelated TEXT field. See gotcha #32 for the omit-`ID` workaround.

## 30. TYAH typed-reference fields — `refObjCode` must be set at POST; DE: read/write is asymmetric

**Surprise:** "I created a `(TEXT, TYAH)` parameter for a user picker. POST succeeded. Tried to `PUT /parameter/<id> refObjCode=USER` to add the reference type after the fact — Workfront returns *'You cannot change the referenced object value for an existing Typeahead field.'* Tried to write a value via `PUT /optask/<id> updates={DE:fieldName: <userID>}` — *'Cannot invoke Object.hashCode() because pk is null.'* Tried `fields=DE:fieldName:ID` to read just the user ID back — Workfront silently returns nothing (no error, no field)."

**Mechanic:** TYAH typeahead parameters that should resolve to a typed Workfront object (User, Project, Task, etc.) take the same top-level `refObjCode` field documented for INTRNL/MULTINTRNL in `02-parameter-types` § Internal Lookup authoring. Empirically verified 2026-06-09 against a preview sandbox tenant v17.0 on a `(TEXT, TYAH)` user picker:

1. **`refObjCode` must be set at POST** — Workfront rejects all PUT attempts to add or change `refObjCode` on an existing TYAH parameter. POST body:
   ```json
   {"name": "...", "label": "...", "dataType": "TEXT", "displayType": "TYAH", "refObjCode": "USER"}
   ```
2. **DE: write accepts the bare ID as a string** — `updates={"DE:fieldName": "<32-char-user-id>"}` succeeds. Workfront wraps and stores the canonical envelope.
3. **DE: read returns a JSON-string envelope** — `GET ...?fields=DE:fieldName` returns the literal string `'{"objCode":"USER","name":"Jenny Dawkins","ID":"5bc636d2..."}'` (the inner quotes are escaped). NOT the bare ID.
4. **Sub-key field selectors don't work on DE: TYAH** — `fields=DE:fieldName:ID` and `:name` are parsed as part of the field name; Workfront returns the row with the DE: column omitted (or, on rare paths, `"Parameter with primary key value(s) '<field>:ID' not found"`).
5. **POSTing a JSON object instead of a string** — `updates={"DE:fieldName": {"ID": "...", "objCode": "USER"}}` fails with *"class java.util.LinkedHashMap cannot be cast to class java.lang.String."* Always send a string; let Workfront wrap.

**Mitigation:**

- **At create-time:** include `refObjCode` in the POST. If omitted, you'll need to DELETE + recreate the parameter to add it later.
- **At write-time:** send the bare ID string. Workfront handles the envelope.
- **At read-time:** ask for the full DE: field (`fields=DE:fieldName`), then parse the JSON envelope client-side to extract `.ID` / `.name` / `.objCode`. In Fusion `searchv3` / `custom` output, use `parseJSON(<step>.data[1].\`DE:fieldName\`).ID`.
- **For downstream consumers** that expect a bare ID (e.g. a Workfront update setting `assignedToID` from the envelope) — never wire the envelope directly. Pipe through `parseJSON(...).ID` first.
- **To FILTER a `/search` by one of these fields:** match the **bare** field name against the referenced object's **ID** with `_Mod=eq` — `DE:fieldName=<refID>&DE:fieldName_Mod=eq`. This works (verified on a client v18.0 `/search`, 2026-08) even though the `fields=DE:fieldName:ID` *projection* in point 4 does not — the `:ID`/`:name` sub-key fails identically on a filter key. See `api/06-filtering-queries.md` § Internal-lookup / typed-reference custom fields.

The asymmetry (write-as-ID vs read-as-envelope) is the surprise. The skill's NL-create flow should propose `refObjCode` whenever the consultant describes the field as "a user picker" / "a project picker" / "a task picker"; absent that, the typeahead stores raw strings and the UI offers a free-text autocomplete instead.

## 31. Writing custom-field VALUES: top-level `DE:<parameter name>`, not label, not a `parameterValues{}` wrapper

Setting a custom-form field value on a record (PROJ / TASK / OPTASK / …) via REST has exactly one shape that works, and two plausible-looking ones that fail:

| Attempt | Result |
|---|---|
| `PUT /<obj>/<id> updates={"DE:<parameter NAME>": value}` | ✅ **Works.** Value persists; read-back key is `DE:<parameter name>`. |
| `PUT /<obj>/<id> updates={"DE:<field LABEL>": value}` | ❌ `Parameter with primary key value(s) "<label>" not found` |
| `PUT /<obj>/<id> updates={"parameterValues": {"DE:<name>": value}}` | ❌ Silent no-op — returns 200, value does **not** persist. |

- The `DE:` key uses the Parameter **`name`** (the snake_case API identifier), **not** the UI `label` — mirrors the `DE:` filter rule.
- Keys go at the **top level** of `updates`, NOT nested in `parameterValues`. `parameterValues` is a **read-side** projection (what `GET …?fields=parameterValues` returns, keyed `DE:<name>`); it is not a write envelope.
- The form must be attached to the record first (`updates={"objectCategories":[{"categoryID":<cid>}]}`) or the DE: write is rejected — see gotcha #3.
- SLCT / RDIO fields must receive a value that exactly matches a `ParameterOption.value`; number/currency accept a bare numeric.

Generalizes gotcha #30 (documented there for TYAH): write-as-`DE:<name>` holds for every parameter type; only the read-side envelope shape differs by type. Verified on a sandbox tenant v15.0, 2026-07-02.

## 32. Category `categoryParameters` PUT: include the composite `ID` and Workfront re-validates every External Lookup field → 400

**Surprise:** "I did a normal Flow-2-style collection-replace PUT — GET all `categoryParameters`, echo every row back verbatim (including its `ID`), change one row's `isRequired`. On a form with no External Lookup fields it works; on a form that *contains* an EXTRNL / MULTEXTRNL / TYAH field it 400s with `Error in field schema validation: required key [link]/[jsonPath]/[httpMethod] not found` — the exact same error as gotcha #29, even though I never touched the external-lookup parameter."

**Mechanic:** Including the composite `ID` (`<categoryID>_<parameterID>`) on a `categoryParameter` row routes Workfront through an existing-object update path that runs a **full-schema re-validation** of each referenced parameter. For External Lookup fields that means the `link`/`jsonPath`/`httpMethod` schema (gotcha #29) — and that schema is **not readable via any v17.0 Parameter field** (`externalLookup`, `link`, `jsonPath`, `httpMethod`, `isExternalLookup`, … all return `does not support field`), so a GET→PUT round-trip can never satisfy it. Result: the whole collection PUT is rejected and **no** row updates, including the plain TEXT ones you actually wanted to change.

**Mitigation:** **Omit the composite `ID` from every row; key each row by `parameterID` instead.** Without `ID`, Workfront reconciles by `parameterID` and skips the external-lookup re-validation. The composite ID is deterministic (`categoryID_parameterID`), so nothing churns — cascade rules and per-record values that reference the CategoryParameter stay intact. This is the one case where Flow 2's "echo rows verbatim" guidance must be amended: strip `ID`. Harmless on forms *without* external-lookup fields too, so it's safe to strip `ID` unconditionally.

Corollary (still a true collection-replace — gotcha #13 unchanged): you must still send **all** rows. A subset PUT tries to drop the omitted rows and 403s with `"<field>" Parameter doesn't exists in currernt Category` [sic] the moment a dropped row is an external-lookup field.

Verified 2026-07-08 on a live production tenant + a preview sandbox tenant, v17.0: flipping 21 "Additional Info" fields to not-required on a 346-row PROJ form ("Project Details [new]") with 4 MULTEXTRNL + 1 TYAH field. With `ID` → 400 (schema); without `ID` → 200, all 346 rows and 5 external-lookup fields preserved.

## 33. Typeahead `DE:` filters resolve to the referenced object's **ID** — not the stored envelope text

**Surprise:** "Gotcha #30 says a TYAH field stores a JSON envelope (`{"objCode":…,"name":…,"ID":…}`), so I assumed a filter had to match that string, and that filtering by a bare ID could never work. Both assumptions are wrong. `DE:<field>=<32-char ID>` with `_Mod=eq` matches fine. Filtering on the referenced object's **name** — which is sitting right there inside the stored envelope — matches nothing at all."

**Mechanic:** the read representation and the filter representation are two different surfaces. Reads return the envelope string (#30). The search/report filter engine indexes the field by the referenced object's **ID only**; string modifiers operate on that ID text, never on the envelope.

Verified 2026-08-06 on a live production tenant, v17.0, against a `(TEXT, TYAH)` parameter with `refObjCode: PROJ`, populated on 7 `OPTASK` records that all reference the same project:

| Filter | Result |
|---|---|
| `DE:<field>=<full ID>` + `_Mod=eq` | ✅ 7 rows |
| `DE:<field>=<first 6 chars of the ID>` + `_Mod=cicontains` | ✅ 7 rows |
| `DE:<field>=<a word from the referenced object's name>` + `_Mod=cicontains` | ❌ 0 rows |
| `DE:<field>=objCode` + `_Mod=cicontains` | ❌ 0 rows |
| `DE:<field>=<32 zeros>` + `_Mod=eq` (negative control) | ❌ 0 rows |

The `objCode` probe is the discriminator. That literal key appears in every stored envelope, so a raw string comparison would match all 7 rows. It matches none — the comparison target is the ID, not the JSON.

**Consequences:**

- To filter or prompt on a typeahead, pass the **ID**. `eq` against a full ID is the correct form; partial-ID `cicontains` also works but has no practical use.
- You **cannot** filter a typeahead by the referenced object's display name. If users need to filter by name, write the name into a separate plain-text field at save time, or filter on the native object instead.
- `fields=DE:<field>:ID` still returns nothing (#30 item 4). That is a *read-side* selector limitation and is unrelated to the filter behaviour above — both were confirmed in the same run.

**Scope of this verification — read before citing it:** tested with `refObjCode: PROJ` via `/optask/search` on the REST API. Not re-tested for `refObjCode: USER`, and **not** tested through a report **prompt**, which adds a UI resolution layer above the filter. Community reports of typeahead *prompts* returning zero rows are therefore **not** explained by this mechanic — at the API level the filter works correctly when handed an ID, so a prompt failure points at the prompt layer or at a separate companion field, not at envelope storage.

## Cross-references

- `01-object-model` — value-vs-label distinction, composite CategoryParameter ID
- `02-parameter-types` — empirical enums for `dataType` / `displayType`
- `03-create-form-recipe` — corrected POST sequence
- `07-display-logic` — REST authoring pattern + matchType + ruleType enums (since v0.25.0)
- `calculated-fields/05-cross-object-references` — `{program}.{DE:NAME}` dotted syntax for cross-object refs; DE: lookups use parameter **name**, not label
- dedicated bulk-update tooling — backfill / migration patterns
