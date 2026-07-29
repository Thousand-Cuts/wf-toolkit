# Example — Clone-between-environments walkthrough

Flow 5 end-to-end. Promote the "Project Vendor Tracking" form you built and verified in the preview sandbox (`acme.preview.workfront.com`) into production (`acme.my.workfront.com`).

## Scenario

> Admin: "Clone the Project Vendor Tracking form from our preview sandbox into prod. Same fields, but change the Department options to match the reorg."

## Steps

```bash
# 1. SOURCE creds (the preview sandbox) — /wf-env-use sandbox
# (wf-env-curl.sh reads creds from ~/wf-envs/<active>/.env)

# 2. Pull the source form with full expansion
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/category/<srcCategoryID> \
  --data-urlencode "fields=ID,name,objCode,description,categoryOrder,\
parameters:ID,parameters:name,parameters:displayName,parameters:parameterType,\
parameters:dataFormat,parameters:isRequired,parameters:displayLogic,parameters:calculation,\
parameters:description,parameters:parameterOptions:*,\
parameterGroups:*,categoryParameters:*" \
  > /tmp/source-vendor-form.json

# 3. Switch to DEST — /wf-env-use prod

# 4. Schema discovery (cached if recent)
# (Skill runs the 5 /metadata GETs in parallel)

# 5. Sanitiser walks /tmp/source-vendor-form.json
# Findings printed:
```

```
Cross-environment clone — sanitiser findings:

  drop_default actions (4):
    customerID         (source: <source-customer-guid>) — dropped
    ownerID            (source: <source-user-guid>)     — dropped
    enteredByID        (source: <source-user-guid>)     — dropped
    parameters[2].ownerID   (source: <source-user-guid>) — dropped

  remap_required actions (0):
    (no displayLogic in this form references other parameterIDs)

  manual_review actions (0):
    (no homeGroupID / roleID references)

  parity_check_required actions (0):
    (no DE: references in any calculation body — there are no COMP fields)

No prerequisite check blocked. Proceeding.
```

```
# 6. Admin's mutation: change Department options
Skill: "I noticed you wanted to change Department options for prod. The source has
[Marketing, Sales, Operations, Engineering]. Replace with which options?"

Admin: "We now use: Brand, Demand Gen, Customer Success, Engineering, Finance.
Paste:
Brand
Demand Gen
Customer Success
Engineering
Finance"

Skill: "Got 5 options. Will replace the source's 4 with these 5."
```

```
# 7. Show payload
Skill prints the resolved POST sequence:
  POST dest/category                        — name="Project Vendor Tracking"
  POST dest/parameterGroup × 1               — "Vendor Details"
  POST dest/parameter × 6                    — same field set as source
  Bulk POST dest/parameterOption × 5         — the new Department options
  Bulk POST dest/categoryParameter × 6       — link rows

Type `apply` to execute, anything else to abort.
```

```
Admin: apply
```

```
# 8. Prod write acknowledgment
Skill: "The destination is **prod** (`acme.my.workfront.com`, WF_ENV_TYPE=prod).
wf-env-curl.sh refuses every write to a non-disposable environment (exit 3)
until WF_ENV_WRITE_ACK=1 is set on the invocation. Type `yes` to confirm
writing this form to production."

Admin: yes
```

```
# 9. Skill executes — WF_ENV_WRITE_ACK=1 prepended to each wrapper write for
# this batch only (authorised by the typed `yes`; never exported persistently), e.g.:
#   WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
#     -X POST /attask/api/v17.0/category --data-urlencode 'updates={...}'
[POST /category — categoryID = <dest-cat-guid>]
[POST /parameterGroup — parameterGroupID = <dest-grp-guid>]
[POST /parameter × 6 — collected parameterIDs]
[PUT /parameterOption?method=POST × 1 — 5 options created]
[PUT /categoryParameter?method=POST × 1 — 6 link rows created]

# 10. Done
Form created: https://acme.my.workfront.com/category/<dest-cat-guid>
In-product builder: https://acme.my.workfront.com/setup/customForms/<dest-cat-guid>

To attach this form to existing projects, use the in-product bulk edit
(bulk attach is out of scope for this toolkit).
```

## What this demonstrates

- Sanitiser flagged 4 customer/user IDs (expected).
- No DE: parity checks needed (the source form has no COMP fields).
- Admin overlay (different Department options) applied on top of the sanitised payload before write.
- Prod destination is double-gated: the `apply` gate authorises the payload, then a separate typed `yes` authorises `WF_ENV_WRITE_ACK=1` on each write call — without it, `wf-env-curl.sh` refuses prod writes with exit 3.
- Final write is one Category + one ParameterGroup + six Parameters + one bulk-options POST + one bulk-link POST.
