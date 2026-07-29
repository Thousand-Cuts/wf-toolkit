# Example: Cross-environment clone walkthrough

End-to-end demonstration of the clone-and-adapt flow with the v0.9.0 sanitizer (5-bucket JSON-object walker). This walkthrough promotes a report between two environments of the same instance: the source is the preview sandbox (slug `sandbox`, `acme.preview.workfront.com`) where the report was built and verified; the destination is production (slug `prod`, `acme.my.workfront.com`). The report shape is the empirical OPTASK-rush-L report from the Client D sample corpus.

## Phase 1-2: Creds + banner

```bash
# Source (after /wf-env-use sandbox — wf-env-curl.sh reads creds from ~/wf-envs/<active>/.env):
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/user/search \
  --data-urlencode '$$LIMIT=1' \
  --data-urlencode 'fields=customer:name'
# data[0].customer.name → "Acme Corp"

# Destination (after /wf-env-use prod):
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/user/search \
  --data-urlencode '$$LIMIT=1' \
  --data-urlencode 'fields=customer:name'
# data[0].customer.name → "Acme Corp"
```

Banner:
> Cloning FROM **sandbox** AT `acme.preview.workfront.com` TO **prod** AT `acme.my.workfront.com`. Type `y` to continue.

## Phase 3: Source pull

```bash
# Source slug active (/wf-env-use sandbox)
REPORT_ID=6a1b2c3d000456789abcdef012345678  # OPTASK-rush-L

bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/report/$REPORT_ID \
  --data-urlencode 'fields=*,definition,filterID,groupByID,viewID,uiObjCode' \
  > /tmp/clone-report.json

FILTER_ID=$(jq -r .data.filterID /tmp/clone-report.json)
VIEW_ID=$(jq -r .data.viewID /tmp/clone-report.json)
# groupByID is null on this L-type report

bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/uift/$FILTER_ID \
  --data-urlencode 'fields=*,definition' \
  > /tmp/clone-uift.json
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/uivw/$VIEW_ID \
  --data-urlencode 'fields=*,definition' \
  > /tmp/clone-uivw.json

jq -n --slurpfile r /tmp/clone-report.json --slurpfile f /tmp/clone-uift.json --slurpfile v /tmp/clone-uivw.json '{report: $r[0].data, uift: $f[0].data, uivw: $v[0].data}' > /tmp/clone-bundle.json
```

## Phase 4: Sanitization (JSON-object walker)

```bash
python3 skills/workfront-reports/scripts/sanitize_clone.py --from-stdin < /tmp/clone-bundle.json > /tmp/clone-flags.json

jq '{strip: .strip|length, prompt: .prompt|length, parity_check: .parity_check|length, host_rewrite: .host_rewrite|length}' /tmp/clone-flags.json
# Expected output (approximate):
# {
#   "strip": 4,           # customerID, preferenceID, securityRootID, etc.
#   "prompt": 5,          # ownerID, hardcoded user GUIDs in OR:1: clauses
#   "parity_check": 1,    # "Is this a rush request?" DE: custom field
#   "host_rewrite": 2     # 2x hardcoded https://acme.preview.workfront.com/... in valueexpression
# }
```

## Phase 5: Interactive review (3 sub-phases)

### 5a. prompt items

For each prompt entry, ask the admin. Example resolution:
- `report.ownerID` → **drop** (let the destination environment assign to current user)
- `uift.definition.OR:1:assignedToID = <source-userID>` → **drop** (use $$USER.ID instead)

Apply the admin's decisions to the cleaned payload via `jq`.

### 5b. parity_check items

```bash
DE_NAME="Is this a rush request?"
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/parameter/search \
  --data-urlencode "name=$DE_NAME" \
  --data-urlencode 'name_Mod=eq' \
  --data-urlencode 'fields=ID,name,parameterGroup:name'
```

- 0 results → BLOCK with message per `05-gotchas.md` #8
- 1 result → proceed
- multiple → admin disambiguates

### 5c. host_rewrite items

For each entry, default to auto-rewrite — substitute the source host with the destination:

```bash
jq '(.cleaned.uivw.definition.column[] | select(has("valueexpression")) | .valueexpression) |= gsub("acme.preview.workfront.com"; "acme.my.workfront.com")' /tmp/clone-flags.json > /tmp/clone-cleaned.json
```

## Phase 6: Optional mutation

(Omit if no admin-requested changes.)

## Phase 7: Destination schema discovery

Run the 4-call burst against `$DST_HOST` per `04-runtime-schema-discovery.md`.

## Phase 8: Compose destination payloads

Take the cleaned bundle and rewrite the top-level metadata fields per `02-create-from-scratch-recipe.md` Phase C. The `definition` objects carry over unchanged (modulo Phase 5 decisions).

## Phase 9: Pre-flight against destination

```bash
python3 skills/workfront-reports/scripts/pre_flight_validator.py --from-stdin --host $DST_HOST < /tmp/dest-bundle.json
```

## Phase 10: Apply gate

Banner: "Writing to **prod** at `acme.my.workfront.com`. Source **sandbox** at `acme.preview.workfront.com` will NOT be modified. Type `apply` to proceed."

## Phase 11-12: Write + smoke test

Same 2/3/4-call sequence as `02-create-from-scratch-recipe.md` Phases F-G. The destination is prod, so prepend `WF_ENV_WRITE_ACK=1` to every write call after the typed `yes` at the prod-write-ack prompt. Print URLs at the end.
