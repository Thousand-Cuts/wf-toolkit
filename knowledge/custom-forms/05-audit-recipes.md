# 05 — Audit Recipes (Flows 3 and 4)

## Flow 3 — Audit a single form

Input: `categoryID` or display name.

```
1. Resolve to ID if name given:
   GET /category/search?name=<name>&name_Mod=eq&fields=ID,name,objCode

2. Pull Category structure — TWO STEPS because Category does not expose `parameters:` as a nested-traversal field (verified failing on client-d-preview, 2026-05-22; see `09-gotchas` #19).

   Step 2a — Category + categoryParameters + groups + cascade rules:
   GET /category/<id>?fields=ID,name,objTypes,catObjCode,description,categoryOrder,
       parameterGroups:ID,parameterGroups:name,parameterGroups:displayOrder,
       categoryParameters:ID,categoryParameters:parameterID,
       categoryParameters:parameterGroupID,categoryParameters:displayOrder,
       categoryParameters:isRequired,categoryParameters:customExpression,
       categoryCascadeRules:ID,categoryCascadeRules:ruleType,
       categoryCascadeRules:nextParameterID,categoryCascadeRules:nextParameterGroupID,
       categoryCascadeRules:otherwiseParameterID,categoryCascadeRules:toEndOfForm,
       categoryCascadeRules:categoryCascadeRuleMatches:ID,
       categoryCascadeRules:categoryCascadeRuleMatches:matchType,
       categoryCascadeRules:categoryCascadeRuleMatches:parameterID,
       categoryCascadeRules:categoryCascadeRuleMatches:value

   Step 2b — fetch the Parameter rows referenced by categoryParameters[].parameterID:
   GET /parameter/search?ID=<p1>,<p2>,<p3>,...&ID_Mod=in
       &fields=ID,name,label,dataType,displayType,isRequired,formatConstraint,description

3. For each SLCT/CHCK/RDIO parameter (i.e. options-accepting), expand options:
   GET /parameterOption/search?parameterID=<paramID>
       &fields=ID,label,value,displayOrder,isHidden,isDefault

4. Attachment count (per target objCode in Category.objTypes):
   GET /<objCode>/count?categoryID=<id>&categoryID_Mod=eq

5. Print structured summary:
   Form: <name>  (targets: <objTypes>)
   Attached to:
     <objCode1>: <N1> records
     <objCode2>: <N2> records (if multi-objCode form)
   Sections:
     <ParameterGroup 1>:
       1. <label> (<dataType>/<displayType>) [required] [calc: "<expr>"]
       2. ...
     <ParameterGroup 2>: ...
     (Ungrouped):
       N. ...
   Display rules:                                      ← NEW in v0.26.0
     Rule 1: Show 'Other notes' when 'Vendor type' = 'Other'
     Rule 2: Hide 'Approval notes' when 'Status' = 'Draft'
     Rule 3: Show the rest of the form when 'Region' ≠ 'EMEA'
   Total parameters: <K>
```

### Rendering cascade rules

For each CTCSRL row, resolve `nextParameterID` / `nextParameterGroupID` / `otherwiseParameterID` / each match's `parameterID` to the human-readable Parameter (or ParameterGroup) name from step 2's joined response. Use the prose form documented in `skills/workfront-custom-forms/scripts/cascade_rule_parser.py` via `render_rule_for_apply_gate()`:

| CTCSRL shape | Audit prose |
|---|---|
| `ruleType=DISPLAY`, simple EXIST match | `Show '<target>' when '<trigger>' = '<value>'` |
| `ruleType=SKIP`, simple EXIST | `Hide '<target>' when '<trigger>' = '<value>'` |
| `matchType=NOTEXIST` | use `≠` instead of `=` |
| `toEndOfForm=true` | replace `'<target>'` with `the rest of the form` |
| `nextParameterGroupID` set | replace `'<target>'` with `section '<group-name>'` |
| `otherwiseParameterID` set | append ` otherwise show '<other>'` |
| Multi-match (≥2 in `categoryCascadeRuleMatches`) | append ` AND '<trigger2>' = '<value2>'` per extra match |

Forms with no cascade rules: omit the "Display rules:" section entirely from the audit output. Forms whose CTCSRL references a Parameter no longer on the form (shouldn't happen with normal lifecycle, but possible after manual SQL or interrupted writes): render as `Rule N: [orphaned — references missing parameter ID '<id>']` and flag for cleanup.

## Flow 4a — Where is form X attached?

Input: `categoryID` (or name).

```
1. Resolve to ID + objTypes (Category.objTypes tells us where to look — may be multi)

2. Total count:
   GET /<objCode>/count?categoryID=<id>&categoryID_Mod=eq

3. First page (paginated; offer CSV export when total > 200):
   GET /<objCode>/search?categoryID=<id>&categoryID_Mod=eq
       &fields=ID,name&$$LIMIT=200&$$FIRST=0

4. Print:
   Form "<name>" is attached to <total> <objCode> records:
     1. <record name 1>
     2. <record name 2>
     ...
   (showing first 200 of <total>; pass --export-csv for the full list)
```

## Flow 4b — Which forms have field Y?

Input: parameter `label` (UI display) or `DE:`-prefixed `name`.

v0.26.0 rewrite — replaces the 2-step `/parameter/search → /category/search` walk with a single `GET /<objcode>/metadata` call. The `metadata.custom` block on Project / Task / OPTASK is a tenant-wide custom-field census indexed by field name, with `possibleValues` and `categories` already joined in. Identified in the cross-skill metadata audit (2026-05-22).

### Primary path (one call)

```
1. Ask which object type the field lives on (project / task / issue / user / etc.).
   Default to "project" if unspecified — most common case for retire-this-field
   questions.

2. GET /attask/api/v17.0/<objcode>/metadata
   The response's data.custom is a map keyed by Parameter.name:
     {
       "Vendor Name": {
         "label": "Vendor Name",
         "dataType": "TEXT",
         "displayType": "SLCT",
         "possibleValues": [...],
         "categories": [
           {"ID": "<cat1>", "name": "Marketing Request", "objCode": "PROJ"},
           {"ID": "<cat2>", "name": "Vendor Onboarding", "objCode": "PROJ"}
         ]
       },
       ...
     }

3. Look up custom[<bare-field-name>] (strip the DE: prefix if given).
   If UI label was given, scan the values for label match.

4. Print:
   Field "<label>" (name="<name>", type=<dataType>/<displayType>)
     attached to <K> forms on <objcode>:
       1. Form "<form-name 1>" (categoryID <cat1>)
       2. Form "<form-name 2>" (categoryID <cat2>)
```

### Fallback path (when metadata.custom doesn't find the field)

`metadata.custom` enumerates fields that are present on at least one record in the tenant. A custom field that's been created but not yet attached to any record won't appear. When `custom[<field-name>]` returns nothing, fall back to the old per-tenant `/parameter/search → /category/search` walk and surface the distinction explicitly:

```
1. GET /parameter/search?name=<bareName>&name_Mod=cieq
       &fields=ID,name,label,dataType,displayType
   (or label_Mod=cieq if UI label was given)

2. GET /category/search?categoryParameters:parameterID=<paramID>
       &categoryParameters:parameterID_Mod=eq
       &fields=ID,name,objTypes,catObjCode

3. Print:
   Field "<label>" exists in your tenant but isn't currently attached to any
   <objcode> records. It appears on form(s):
     1. Form "<form-name 1>" targeting <objTypes 1>
     2. Form "<form-name 2>" targeting <objTypes 2>
```

This dual-path keeps the common case fast (one call) while preserving completeness for the long-tail "field exists but isn't attached" case.

This is the most-asked audit question in real engagements ("we want to retire this custom field — where is it used?").

## Pagination

All flows can exceed default `$$LIMIT`. Use `workfront-api` `knowledge/api/09-pagination-and-limits.md`. Common patterns:

- Total counts via `/count` endpoint first
- `$$LIMIT=200` default for list flows
- Offer CSV export when total > 200

## Cross-references

- `01-object-model` — what each object means
- `09-gotchas` — value-rename impact on audits (you can't search by old display name after a value rename)
- `workfront-api` `knowledge/api/09-pagination-and-limits.md` — pagination semantics
