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

This is about adding a field to a form that is already attached. Attaching a form to a record that did not have it is a different write, with its own body and side effects (calculated fields compute in the same call): see § 41.

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

This means the toolkit-wide prefix convention is partially incompatible with custom forms. The `wf-curl.sh` wrapper (maintainer-side, for the `[wf-api-verify]` flow) enforces a Phase A-aware prefix policy that maps `Parameter` to the `wf_verify_` snake_case variant. For client-engagement writes through `wf-env-curl.sh`, there is no prefix enforcement at all — the wrapper has no prefix guard, since real client forms shouldn't carry a verify-prefix in the first place.

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
POST /attask/api/v22.0/category
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
- For **API writes**, the form must be attached to the record first or the DE: write is rejected. Attach it by sending the record's existing forms plus the new one in `objectCategories`, each with a `categoryOrder` (§ 41); a body naming only the new form risks detaching the others. This gate is API-only: the UI attaches the form automatically when a user inline-edits the field from a report column (gotcha #38).
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

## 34. Internal Lookup (INTRNL/MULTINTRNL) end-user search matches the referenced object's name — not its reference number

**Surprise:** "Users could always paste a reference number (e.g. `172401`) into our legacy Typeahead picker and get the project. The same number typed into the new Internal Lookup field returns *No results* — only searching by the object's name works."

**Mechanic:** a reported behavioral difference, not an Adobe-documented one: the INTRNL/MULTINTRNL widget's backing search appears to match only the referenced object's **name**, where the legacy TYAH widget also matched `referenceNumber`. The data layer is not the constraint — `referenceNumber` is a searchable field at the REST layer — so the restriction lives in the widget's UI query (inference; the thread's only explanation is a secondhand "our Adobe rep [said] this is intentional with this update", with no release note or in-thread Adobe statement backing it). Note this scopes `02-parameter-types` § TYAH's "identical in behavior to INTRNL+USER": that equivalence covers DE: value semantics — end-user search affordances differ.

**Mitigation:** when a client workflow depends on typing/pasting reference numbers to pick an object, do not spec an INTRNL/MULTINTRNL field for the picker. Options: (a) author the field as `(TEXT, TYAH)` + `refObjCode` if the legacy widget is still available and still matches reference numbers in the target tenant — verify there before promising it; (b) add a companion plain-text field carrying the reference number so users can search/filter on it (same mirror-a-searchable-scalar pattern as #33's name workaround); (c) train users to search by name and surface the reference number in the naming convention. Raise it at form-design review for request-intake and cross-object-linking solutions — the OP hit it after build.

<!-- UNVERIFIED -->
UI behavior — no read-only API call can observe it. Reported 2026-07: the OP's accepted self-answer relays an unconfirmed Adobe-rep statement; the underlying name-only-match behavior was independently corroborated by two other posters in the thread. Confirm by typing a known reference number into an INTRNL field on the target tenant. Provenance in Sources below.

## 35. Display logic hides fields but never clears their stored values — and visibility is not readable from a calculated field

Two closely-related limits that bite request-intake forms, both structural rather than configuration mistakes.

**(a) Hiding is render-time only; the stored value survives.** A cascade rule's entire vocabulary is the five writable fields on `CTCSRL` — `ruleType` (`DISPLAY`/`SKIP`), `nextParameterID`, `nextParameterGroupID`, `otherwiseParameterID`, `toEndOfForm` — plus `matchType`/`parameterID`/`value` on `CTCSRM`. None of them touches the target parameter's value. So when a user fills a field, then changes the trigger (or copies a previous request), the now-hidden field keeps whatever was in it, and any calc field reading that parameter silently consumes a stale value. There is no native "clear on hide" and no clear-on-submit option.

**(b) A calculated field cannot ask whether a field is visible.** There is no `.visible` accessor, and nothing in the object model stores runtime visibility to read: `PARAM` exposes exactly 15 fields, and the only two matching any visibility-ish keyword are `displaySize` and `displayType`, which describe widget geometry and widget kind, not render state. Visibility is derived at render time from the Category's cascade rules and is never persisted per-record.

**Mitigation — guard the calculation on the trigger, not on the target.** Because `matchType` is binary (`EXIST`/`NOTEXIST`) against a concrete `ParameterOption.value`, every display condition is by construction expressible as an equality on the trigger parameter. Restate it inside the formula so the stale value becomes unreachable:

```
IF({DE:Field 1}="A", {DE:Field 2}, 0)
```

rather than consuming `{DE:Field 2}` directly. This keeps the guard and the display rule in sync by construction, and it is the only fix that does not require a background job. To actually blank the stored data (for reporting or export cleanliness) a scheduled write is required — the form layer cannot do it.

**Verified 2026-08-24** on the surveyed sandbox tenant (`WF_ENV_TYPE=sandbox`), read-only metadata:

```bash
# Negative control — enumerate the whole cascade-rule vocabulary
GET /attask/api/v22.0/CTCSRL/metadata?fields=fields
#   -> 8 fields: ID, categoryID, customerID, nextParameterGroupID,
#      nextParameterID, otherwiseParameterID, ruleType, toEndOfForm
GET /attask/api/v22.0/CTCSRM/metadata?fields=fields
#   -> 6 fields: ID, categoryCascadeRuleID, customerID, matchType, parameterID, value
# Neither object carries any value-clearing attribute.

# Discriminator — scan PARAM for any persisted visibility state
GET /attask/api/v22.0/PARAM/metadata?fields=fields
#   -> 15 fields; keyword scan (visib|hidden|clear|reset|display|cascade)
#      matches only displaySize, displayType. No visibility state is stored.
```

**Scope limits.** Metadata enumeration proves the fields do not exist, which is what rules out both a clear-on-hide attribute and a readable visibility flag. Not tested: whether the Workfront UI's form editor offers a clear-on-hide toggle backed by some non-REST internal surface (the `/internal/customForms/saveForm` payload was not re-captured for this), and no calc-field formula was executed against a hidden field to observe evaluation. The mitigation formula is the standard guard pattern and was not run end-to-end on a live form in this pass.

**(c) The corollary that matters on an integration: display logic is not an access control, and not a data filter.** (b) established that visibility is computed at render time and persisted nowhere. The consequence generalizes past calculated fields to *every* consumer outside the form UI: a hidden field's stored value is returned to an authorized reader — REST, Fusion, a report, an export — exactly as a visible one is. Two things follow, and both are worth saying out loud to a client:

- **Hiding a field does not keep its contents from anyone who can read the record.** Display logic is a user-experience feature; if a value must not be seen, that is a `CategoryParameter.securityLevel` question (§ 22) or a field that is never populated, not a cascade rule.
- **"Field 2 has a value" is not evidence that Field 2 was shown.** An automation that infers the former from the latter will act on values stranded by a trigger change or a copied request — the same stale-value path as (a), reached from the integration side instead of the calc-field side.

<!-- UNVERIFIED --> Community-reported from the Fusion surface specifically (thread below, best answer 2026-09-01): **Fusion exposes no supported runtime property such as `isVisible`** for a Workfront custom-form field, and the recommended design is to reproduce the display rule's own condition as a Fusion router or filter placed ahead of the modules that consume the dependent field — the guard-on-the-trigger mitigation above, applied one layer out. Consistent with the metadata enumeration in (b) (nothing persists visibility, so nothing can return it), but the Fusion-side statement itself is community hearsay and no GET settles what a Fusion module exposes. The same thread reports that the Workfront *Copy* misc action carries a `clearCustomData` option that clears **all** custom data rather than selected fields; that is a write-side claim this routine cannot confirm, and it is recorded here only so the next person knows to check it rather than rediscover it.

## 36. Reordering the forms on a record silently changes its primary `categoryID`

**Surprise:** "A consultant reordered the three forms on a request so the triage form showed first. Nothing about the data changed. The next day a report filtered on `categoryID` stopped returning those requests."

**Mechanic:** Per-record form order is `categoryOrder` on the `ObjectCategory` (OBJCAT) join row, 0-indexed, and the form at position 0 *is* the record's primary `categoryID`. They are one fact with two accessors, and every write to either updates the other. Verified on `a sandbox tenant.workfront.com` v17.0, 2026-08-27:

- `PUT /ctgy/reorderCategories` with `categoryIDs:[C,A,B]` on a record whose primary was A → `categoryID` becomes C.
- `PUT /optask/<id>` with `categoryID=<B>` → B moves to `categoryOrder` 0, the others shift down keeping their relative order.

There is no way to promote a form to primary without moving it to the front of the form list, and no way to reorder without re-pointing `categoryID`.

**Mitigation:** Before reordering, check what keys on the primary form: report and Fusion filters on `categoryID`, and any `/search?categoryID=` in a scenario or script. The durable fix is to filter on the OBJCAT collection instead, which is order-independent: `/<obj>/search?objectCategories:categoryID=<id>`. Reordering is a display-layer change everywhere except `categoryID`, which is exactly where nobody looks for it.

**Also note the namesake trap.** `CTGY.categoryOrder` is a *different field*, the form's tenant-wide default position in Setup. Setting it changes nothing on any existing record. Reaching for it to fix a per-record ordering complaint is the natural first mistake.

Full dispatch shapes, the exact-set constraint on `reorderCategories`, and the three-way comparison table live in `api/05-http-methods-and-actions` § "Assigning custom forms".

## 37. The AI Assistant cannot fill a typeahead or Internal Lookup from a display name — it needs the ID

**Surprise:** "I had the AI Assistant populate a request form from an Excel file and every plain field landed. The typeahead fields stayed empty. I converted the typeahead to an Internal Lookup and it was *still* empty. Putting the raw user ID in the spreadsheet column filled the Internal Lookup immediately."

<!-- UNVERIFIED -->
**Mechanic:** Reported from the field, not reproduced here. The reported behaviour is exactly the write-side asymmetry gotchas #30 and #33 already document at the REST layer, surfacing one layer up: a reference-typed parameter (`TYAH` with `refObjCode`, or `INTRNL`/`MULTINTRNL`) **writes as a bare ID string** and reads back as the canonical envelope `{"objCode","name","ID"}`. Nothing in that path resolves a human-readable name to an object. The AI Assistant is writing through the same door, so a spreadsheet column holding `"Jane Cooper"` has nothing to bind to, while one holding the user's ID binds on the first try. Converting `TYAH` → `INTRNL` changes nothing because both are the same reference mechanism — which is why the reporter's second attempt failed the same way as the first.

**Mitigation:** When scoping an AI-Assistant or document-driven intake, treat every reference-typed field as **ID-in, envelope-out** and say so before the client builds the spreadsheet. Either carry IDs in the source data, or resolve names to IDs in a prior step (a Fusion lookup, or `/USER/search?firstName=…&lastName=…` returning `ID`) and hand the assistant the IDs.

**The limit that usually kills this design:** IDs are tenant-scoped. The reporter's actual goal was pulling requests from a *client's* instance into their own, where an ID from the source tenant resolves to nothing in the target — so the ID workaround rescues same-tenant intake and does not rescue cross-tenant intake. For cross-tenant, the name→ID resolution has to run against the **target** tenant before the assistant sees the data.

Not checkable by GET: what the AI Assistant does or does not resolve is UI behaviour, and `sweep-verify.sh` was unavailable this run besides (see the run's PR digest). The underlying REST-layer asymmetry it is attributed to *is* verified — 2026-06-09, gotcha #30.

## 38. The `DE:` write gate is API-only: the UI auto-attaches the form on inline edit

**Surprise:** "This document has no custom form attached, so users can't set the field. We'll need an automation to attach the form to every record first."

**Mechanic:** the attachment requirement in gotcha #31 constrains the **REST write path**, not the product. When a user inline-edits a `DE:` field from a report column, Workfront attaches that field's parent form to the record as part of the save. The record needs no form beforehand.

**Verified:** production tenant, 2026-09-22. A proof document confirmed to carry zero `objectCategories` was given a value for a radio field directly in a report row; the owning form was attached automatically by that save.

**Why it matters:** the inference "form not attached, therefore users cannot set this field" is wrong, and it is expensive to get wrong. On the tenant above it produced a recommendation for a Fusion auto-attach scenario plus a 183-record backfill, when the real fix was adding one column to two report views. **Attachment counts tell you who has used a field, not who can.**

**Diagnostic:** when a user reports a missing custom field in the UI, check the report's **view columns** before the record's form attachment.

```
GET /REPORT/<id>?fields=viewID,filterID
GET /UIVW/<viewID>?fields=definition     # columns live under definition.column
GET /UIFT/<filterID>?fields=definition   # filter clauses are a separate object
```

A field that a report filters on but has no column for is invisible and unsettable from that screen, whatever the record's attachment state. Sibling reports over one object drift apart easily: on the tenant above, six reports over the same document set disagreed on **both** the column and the matching filter clause, in both directions, which reached users as "it works on some records but not others" when the real variable was which report they had open.

This does not relax gotcha #31. Scripted `DE:` writes still need the form attached first.

## 39. Adjacent surface (Workfront Planning request forms): the logic set is smaller than the custom-form designer's, and choices are not editable on the form

Planning has no bucket; a request form is form design, so a consultant looks for it here. Preview **2026-09-25**, fast release 2026-10-14, everyone **2026-10-15**.

**Surprise:** "The form designer has validation and editability logic, so we scoped the intake form around a validation rule. On the Planning request form there is no validation option — and we cannot even fix the choice labels without leaving the form."

**Mechanic:** a Planning **request form** is a distinct designer from the Workfront custom-form designer this bucket otherwise documents, and it is behind it on two axes:

1. **The logic set differs by environment, and the Production set is two options.** In Production a Planning request-form field offers only **Display Logic** and **Skip Logic**. The Preview environment expands that to **Display, Skip, Default value, Validation, Formatting, Editability** — the set `07-display-logic.md` § "Not yet mapped" lists as the `defaultValueFormula` / `validationFormula` / `valueEditabilityFormula` / `formattingFormula` keys inside `fieldDefinition`. So a rule set designed against Preview, or against the Workfront form designer, does not necessarily port to a Planning request form in Production today. Adobe also notes that validation and default-value rules "are not available for all field types".
2. **Logic needs a select field to hang off.** Adobe now states plainly that *"Add logic is available only when fields are, or are preceded by, single- and multi-select fields."* This generalises what the Display Logic option already required to the whole logic feature — a field with no select field at or above it in the form order has no logic available at all, which reads as a missing feature rather than an ordering problem.

**The choices trap is the one that costs an afternoon:** *"You cannot rename or remove choices on a Planning request form. You must edit the field choices in the table view of the record type."* The request form surfaces choice **ordering** controls (Sort Choices A-Z, drag-and-drop, and per-choice Select by Default / Hide choice) which makes it look like the place choices are managed — but the label set itself lives on the record-type field, edited from the record type's **table view**. Hiding a choice on the form and deleting it are different operations in different places.

**Mitigation:** establish the record type's fields and their choice labels *before* building the request form, and treat the form as presentation and routing only. When a stakeholder asks for validation on a Planning intake form, confirm which environment they saw it in before agreeing to it. Where Production cannot express the rule, the fallback is the approval rules on the form's Settings tab (which route on submitted field values) rather than field-level validation.

**Related:** `07-display-logic.md` for the CTCSRL/CTCSRM rule objects on the Workfront side, and the four formula keys this Preview set appears to expose in the UI; `../permissions/09-gotchas.md` § 21 for the request *sharing* half of the same release.

First-party and dated. No live re-check was available this run (`sweep-verify.sh` blocked — see the PR digest); Planning request-form logic is UI behaviour on a non-Planning sandbox regardless, so this carries first-party provenance rather than a verification line.

## 40. AI Form Fill now reads a linked Workfront object — same-instance only, which is exactly where gotcha #37 broke

**Already live everywhere.** Adobe shipped this off-schedule on **2026-09-22**, with Preview, fast release and quarterly all carrying that one date, so unlike most of the 26-Q4 list there is no rollout window to wait out.

**Surprise:** "We can point AI Form Fill at an existing project and have it fill the request from that. So we can point it at the client's project in their instance too." — no.

**Mechanic:** AI Form Fill accepts a third prompt input alongside a typed prompt and an uploaded document: **a link to an existing project, task, or issue**, pasted into the prompt window, applied either to the whole form or to one section. Adobe states the constraint in one line: *"The project, task, or issue must be in the same instance of Workfront as your request."*

**Why that line is the interesting part.** Gotcha #37 records the AI Assistant failing to fill typeahead and Internal Lookup fields from display names, where the working answer was to supply the raw ID — and the limit that made the workaround useless in practice was that **IDs are tenant-scoped**, so the reporter's actual goal, pulling requests from a client's instance into their own, could not work. This feature is the same boundary drawn by Adobe from the other side: object references resolve within one instance and nowhere else. A link-based fill is a genuinely faster intake path for same-tenant work and is not a cross-tenant migration tool, and it will be asked for as one.

**Mitigation:** use it for same-instance intake — cloning a request from a comparable project is the obvious fit. For anything crossing instances, the path is still name→ID resolution against the *target* tenant first, per gotcha #37. Note also that unreviewed field suggestions are **accepted automatically on submit**, so a link-filled form carries whatever it inferred unless someone rejects it explicitly.

**Related:** gotcha #37 for the ID-in / envelope-out asymmetry underneath this, and the tenant-scoped-ID limit it shares.

First-party; no live re-check was available this run (`sweep-verify.sh` blocked — see the PR digest), and AI Form Fill behaviour is not GET-checkable in any case.

## 41. Attaching a form to a record that already has forms: send the full set, with `categoryOrder`

**Surprise:** "I attached the new reporting form with `updates={"objectCategories":[{"categoryID":"<new>"}]}`. Did the record keep its request form?"

**The safe body:** read the record's current forms, then send all of them plus the new one at the next `categoryOrder`:

```
GET /attask/api/v22.0/project/<id>?fields=objectCategories:categoryID,objectCategories:categoryOrder

PUT /attask/api/v22.0/project/<id>
updates={"objectCategories":[
  {"categoryID":"<existing>","categoryOrder":0},
  {"categoryID":"<new>","categoryOrder":1}
]}
```

Verified on a client prod tenant 2026-09-30 (REST v17.0) on 3 projects, among them one with 1 prior form and one with 2 prior forms (a request form and a legacy details form): every prior form stayed attached, in its original order, and every existing field value was unchanged (19, 31 and 40 values compared before and after). The new form landed at the end.

**Not verified: sending only the new form.** Whether a body naming just the new form merges with the attached set or replaces it has not been observed. `../api/05-http-methods-and-actions.md` documents this PUT as a replace, and Adobe's general rule is that a collection in `updates` replaces, so assume it would detach every form you leave out and never rely on the short body. The `PUT /ctgy/assignCategories` action is the documented additive alternative (`../api/05-http-methods-and-actions.md` § Assigning custom forms), but its effect on calculated fields was not tested.

**`POST /objcat` does not attach a form.** OBJCAT is a secondary object; `/objcat` and `/objectcategory` are read-only, and a POST is refused (`unable to find method for service endpoint type: ADD`, seen on the firm's tenant 2026-06-12). Write through the parent record's `objectCategories`.

**The attach PUT is a save, so it recalculates.** The new form's calculated fields compute in the same call (a 5-field form on 3 of 3 records, values matching ones computed independently), and the calculated fields on the record's **other** forms are re-evaluated too. A stale calc value on an already-attached form can therefore change during an attach. For a bulk attach, guard with a before/after read of `parameterValues` and `objectCategories` on every record:

- **Log, don't stop:** a calculated field changing from one filled value to another, or filling in on the new form.
- **Stop:** any non-calculated field changing; a calculated field going from filled to blank (a missing or broken formula, see § 42); any previously attached form missing afterwards.
- **Telling them apart:** `GET /param/search?displayType=CALC&fields=name` lists the calculated fields (raise `$$LIMIT` past 100 on a large tenant). Detail: `../calculated-fields/07-limitations-and-gotchas.md` § Recalculation on Form Attachment. The bulk recipe is `../bulk-updates/05-common-patterns.md` Pattern 5.

## 42. `categoryParameters:*` omits `customExpression`, so a PUT built from it blanks every formula

**Surprise:** "I read the form with `fields=categoryParameters:*`, changed one row, and PUT the collection back. Days later the calculated fields stopped populating."

**Mechanic:** the `*` expansion of `categoryParameters` does not include `customExpression`, although the field reads fine when named. The link PUT is a collection replace that resets any key a row leaves out (`04-add-field-to-existing-form.md` § Field-style fields), so a payload built from a `*` read writes an empty formula to every calculated field on the form. Nothing errors, `isInvalidExpression` stays false, and the fields still render. A backup captured the same way cannot restore them, and `customExpression` is not versioned or in the audit trail.

**Mitigation:** name the fields: `fields=categoryParameters:parameterID,categoryParameters:displayOrder,categoryParameters:customExpression,...` (the full list is in `04-add-field-to-existing-form.md` step 2). Count the non-empty `customExpression` values before and after any form PUT and compare. The same trap exists on reports, where `fields=*,definition` returns no `definition` (`../reports/05-gotchas.md` #25).

Observed on a client tenant 2026-09-08, where a form edited from a `*` read had all 10 formulas blank while an untouched sibling form returned its 1,771-character formula when named explicitly. Re-observed on a client prod tenant 2026-09-30: reading back newly created formulas needed an explicit `fields=categoryParameters:customExpression`.

## Cross-references

- `01-object-model` — value-vs-label distinction, composite CategoryParameter ID
- `api/05-http-methods-and-actions`: CTGY-hosted attach / detach / reorder actions and their dispatch shape
- `api/08-related-objects-and-collections`: OBJCAT join table, multi-form attachment reads
- `calculated-fields/07-limitations-and-gotchas` § Recalculation on Form Attachment: the calc side of gotcha #41
- `bulk-updates/05-common-patterns` Pattern 5: gotcha #41 as a bulk write, with the before/after guard
- `02-parameter-types` — empirical enums for `dataType` / `displayType`
- `03-create-form-recipe` — corrected POST sequence
- `07-display-logic` — REST authoring pattern + matchType + ruleType enums (since v0.25.0)
- `reports/07-view-patterns` § 14: the view-column side of gotcha #38, where a `DE:` column doubles as the user's write surface and omitting it makes the field unsettable from that report
- `calculated-fields/05-cross-object-references` — `{program}.{DE:NAME}` dotted syntax for cross-object refs; DE: lookups use parameter **name**, not label
- dedicated bulk-update tooling — backfill / migration patterns
- `fusion/02-module-configs` — the Fusion side of gotcha #35(c): a scenario reading a custom field cannot ask whether that field was displayed, so the display rule's condition has to be restated as a filter

## Sources

| URL | What it provided |
|---|---|
| Direct observation, consultant-run test on a production tenant, 2026-09-22 | Gotcha #38: inline-editing a `DE:` field from a report column auto-attaches the owning custom form to a record that had none. Reproduced deliberately against a document verified to carry zero `objectCategories`. |
| Direct observation, consultant-run writes on a client prod tenant (REST v17.0), 2026-09-30 | Gotcha #41: the full-set `objectCategories` attach body keeping 1 and 2 prior forms and 19, 31 and 40 field values unchanged; calculated fields computing in the attach call on 3 of 3 records; calc fields on other forms re-evaluated by the same save. Gotcha #42: an explicit `categoryParameters:customExpression` needed to read new formulas back. |
| Consultant incident on a client tenant, 2026-09-08 | Gotcha #42: 10 formulas blanked by a PUT built from a `categoryParameters:*` read, against a 1,771-character formula on an untouched sibling form read by name. |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/use-reference-number-in-internal-lookup-251783` | INTRNL end-user search matches name only, not reference number (gotcha #34) — best answer by jayciedido, 2026-07-17 |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-fusion-24/capture-form-visibility-display-with-fusion-252470` | Independent corroboration of gotcha #35 from the Fusion surface, and the source of #35(c): no `isVisible` runtime property in Fusion, display logic is not a data-clearing or security rule, reproduce the display condition as a Fusion filter. Also the unconfirmed `clearCustomData` copy-action remark — best answer by etaylor-1, 2026-09-01 |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-general-23/workfront-ai-assistant-typeahead-fields-252748` | Gotcha #37: the AI Assistant leaves typeahead fields empty when fed display names from a spreadsheet, converting to Internal Lookup does not help, and supplying the raw ID works — plus the cross-tenant limit that makes the workaround unusable for pulling requests between instances — best answer by MorganHatcher, 2026-09-14 |
| AdobeDocs/workfront.en `help/quicksilver/planning/requests/create-request-form.md` @ `da1df635` (2026-09-25) | Gotcha #39: the Production (Display, Skip) versus Preview (Display, Skip, Default value, Validation, Formatting, Editability) logic sets on a Planning request form, the "logic is available only when fields are, or are preceded by, single- and multi-select fields" rule, the Size and Choices field options, and the "you cannot rename or remove choices on a Planning request form — edit them in the record type's table view" constraint. All confirmed as live prose outside `<!-- -->` staging at this SHA. Blob: `https://github.com/AdobeDocs/workfront.en/blob/da1df63501d251518dc65a56c38524774aa25caa/help/quicksilver/planning/requests/create-request-form.md` |
| AdobeDocs/workfront.en `help/quicksilver/manage-work/requests/create-requests/autofill-from-prompt-document.md` @ `da1df635` (2026-09-25) | Gotcha #40: the link-to-an-object prompt input for AI Form Fill, its "must be in the same instance of Workfront" constraint, the apply-to-form / apply-to-section split, and the auto-accept-on-submit behaviour for unreviewed suggestions. Blob: `https://github.com/AdobeDocs/workfront.en/blob/da1df63501d251518dc65a56c38524774aa25caa/help/quicksilver/manage-work/requests/create-requests/autofill-from-prompt-document.md` |
| AdobeDocs/workfront.en `help/quicksilver/product-announcements/product-releases/26-q4-release-activity/26-q4-release-overview.md` @ `da1df635` (2026-09-25) | Gotchas #39 and #40: the release dates. AI Form Fill's link input is flagged **Off schedule** with Preview, fast release and quarterly all 2026-09-22; the Planning request-form items are Preview 2026-09-25 → everyone 2026-10-15. Blob: `https://github.com/AdobeDocs/workfront.en/blob/da1df63501d251518dc65a56c38524774aa25caa/help/quicksilver/product-announcements/product-releases/26-q4-release-activity/26-q4-release-overview.md` |
