# Example — `--clone-options-from <parameterID>`

Use case: you're authoring a new dropdown and want to seed its options from an existing dropdown in the same environment (or a different one).

## Scenario A — same environment

> Admin: "Add a 'Backup Region' dropdown to the disaster recovery form. Use the same options as the existing 'Primary Region' dropdown."

```bash
# Suppose Primary Region's parameterID is param-abc-123 in this environment.

# Resolve the source options:
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/parameterOption/search \
  --data-urlencode "parameterID=param-abc-123" \
  --data-urlencode "fields=label,value,displayOrder,isHidden" \
  --data-urlencode '$$LIMIT=100'

# Returns (e.g.):
[
  {"label": "us-east-1", "value": "us_east_1", "displayOrder": 1},
  {"label": "us-west-2", "value": "us_west_2", "displayOrder": 2},
  {"label": "eu-central-1", "value": "eu_central_1", "displayOrder": 3},
  {"label": "ap-southeast-1", "value": "ap_southeast_1", "displayOrder": 4}
]

# Skill creates the new parameter + clones options:
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh -X POST /attask/api/v17.0/parameter \
  --data-urlencode "name=backup_region" \
  --data-urlencode "displayName=Backup Region" \
  --data-urlencode "parameterType=DROP"
# Returns: parameterID = param-xyz-456

# Bulk-POST the cloned options:
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh -X PUT \
  "/attask/api/v17.0/parameterOption?method=POST" \
  --data-urlencode 'updates=[
    {"parameterID":"param-xyz-456","label":"us-east-1","value":"us_east_1","displayOrder":1},
    {"parameterID":"param-xyz-456","label":"us-west-2","value":"us_west_2","displayOrder":2},
    {"parameterID":"param-xyz-456","label":"eu-central-1","value":"eu_central_1","displayOrder":3},
    {"parameterID":"param-xyz-456","label":"ap-southeast-1","value":"ap_southeast_1","displayOrder":4}
  ]'
```

## Scenario B — cross-environment

> Admin: "Use the same country dropdown options we already have in the preview sandbox, applied to prod."

Same procedure but the GET runs against the source environment; sanitiser strips the source `parameterID` reference (which doesn't apply to the destination) before the bulk-POST is composed for the destination's new parameter.

```bash
# 1. Switch to source — /wf-env-use sandbox

# 2. Pull options
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/parameterOption/search \
  --data-urlencode "parameterID=<src-paramID>" \
  --data-urlencode "fields=label,value,displayOrder,isHidden" \
  --data-urlencode '$$LIMIT=200' \
  > /tmp/source-country-options.json

# 3. Switch to dest — /wf-env-use prod

# 4. Create the new parameter on dest
# (Skill collects displayName + parameterType from the admin)

# 5. Re-target option list to dest parameterID + bulk-POST
# (Skill rewrites parameterID in the cloned options to the just-created
#  dest parameterID before POSTing)
```

## What `option_list_parser.py` and the bulk-POST flow handle

- The fetched JSON from step 2 is a valid input to `option_list_parser.parse_option_list()` if first re-serialised as CSV — but the typical path is direct: skip the parser and re-use the structured option dicts directly.
- The bulk-POST cap (Phase A Step 5 confirms) drives chunking when option count > cap.
- displayOrder is preserved from source unless the admin overrides.

## What this demonstrates

- Existing option lists are reusable for new dropdowns — no retyping.
- Cross-environment cloning works for individual fields too, not just whole forms.
- Pattern composes with Flow 1 / Flow 2: any new DROP/RADIO/CHECKBOX parameter can be seeded from an existing one.
