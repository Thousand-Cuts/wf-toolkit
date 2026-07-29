# Example — Audit form usage across the tenant

Flows 4a + 4b — the most-asked audit question in real assessments.

## Scenario A — "Where is form X attached?"

> Admin: "Where is the 'Vendor Tracking' form attached? Before we deprecate it I need to know which projects are using it."

```bash
# 1. Resolve form name to ID + objCode
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/category/search \
  --data-urlencode "name=Vendor Tracking" --data-urlencode "name_Mod=eq" \
  --data-urlencode "fields=ID,name,objCode"
# Returns: ID=cat-abc, objCode=PROJ

# 2. Count
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/project/count \
  --data-urlencode "categoryID=cat-abc" --data-urlencode "categoryID_Mod=eq"
# Returns: {"count": 47}

# 3. First page
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/project/search \
  --data-urlencode "categoryID=cat-abc" --data-urlencode "categoryID_Mod=eq" \
  --data-urlencode "fields=ID,name,status" \
  --data-urlencode '$$LIMIT=200' --data-urlencode '$$FIRST=0'
```

Output:

```
Form "Vendor Tracking" (PROJ form, categoryID=cat-abc)
Attached to 47 projects:

  Status  | Name
  --------|------------------------------------------
  CUR     | Q4 Marketing Plan
  CUR     | Brand Refresh 2026
  CUR     | Customer Conference Logistics
  CPL     | Legacy Vendor Onboarding (closed)
  ...

(Showing all 47. For CSV export of the project IDs, pass --export-csv)
```

## Scenario B — "Which forms have field Y?"

> Admin: "We want to rename the `Spend Approved` field. Which forms is it on?"

```bash
# 1. Resolve parameter
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/parameter/search \
  --data-urlencode "name=Spend Approved" --data-urlencode "name_Mod=cieq" \
  --data-urlencode "fields=ID,name,displayName,parameterType"
# Or, if the admin gave the DE: form, search by Parameter.name
# (strip the DE: prefix first).

# Returns: parameterID = param-spend-123

# 2. Find CategoryParameter rows referencing this parameter
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/categoryParameter/search \
  --data-urlencode "parameterID=param-spend-123" \
  --data-urlencode "fields=categoryID"
# Returns: [{categoryID: cat-abc}, {categoryID: cat-def}, {categoryID: cat-ghi}]

# 3. Resolve each Category
for catID in cat-abc cat-def cat-ghi; do
  bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/category/$catID \
    --data-urlencode "fields=ID,name,objCode"
done
```

Output:

```
Parameter "Spend Approved" (name="spend_approved", type=NUMBER currency)
Attached to 3 forms:

  Form Name                       | objCode
  --------------------------------|---------
  Vendor Tracking                  | PROJ
  Procurement Request              | OPTASK
  Annual Vendor Renewal            | PROJ

Plus a name-rename caveat: see knowledge/custom-forms/09-gotchas.md #1.
Existing DE:Spend Approved references in calc fields / reports / filters
will continue to work via Workfront's internal alias even after rename,
but new DE:<new-name> references won't find this field unless you also
update the consuming places.

Suggested remediation:
  1. Audit the field's consumers FIRST (run a global text search across
     report definitions and calc bodies for 'DE:Spend Approved')
  2. Rename the displayName (UI-only — safe)
  3. Consider whether to also rename the API `name` (creates the alias
     and breaks search-by-new-name diagnostic clarity)
```

## What this demonstrates

- Flow 4a uses the inline `categoryID` field on the target objCode — no join table walk needed.
- Flow 4b walks Parameter → CategoryParameter → Category. Two API levels.
- Both flows are read-only and paginate cleanly.
- The "rename caveat" output combines the audit result with `09-gotchas.md` knowledge — proactive surfacing.
