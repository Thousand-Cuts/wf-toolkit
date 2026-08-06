# Example — Clone-and-Adapt walkthrough

Flow 5 end-to-end. Lift the "Project Vendor Tracking" form from the firm's reference tenant into a client tenant.

## Scenario

> Consultant: "Clone our Project Vendor Tracking form into Acme's instance. Same fields, but change the Department options to match Acme's org chart."

## Steps

```bash
# 1. SOURCE creds (firm's reference tenant)
./skills/workfront-api/scripts/wf-use.sh firm-reference

# 2. Pull the source form with full expansion
./skills/workfront-api/scripts/wf-curl.sh /attask/api/v17.0/category/<srcCategoryID> \
  --data-urlencode "fields=ID,name,objCode,description,categoryOrder,\
parameters:ID,parameters:name,parameters:displayName,parameters:parameterType,\
parameters:dataFormat,parameters:isRequired,parameters:displayLogic,parameters:calculation,\
parameters:description,parameters:parameterOptions:*,\
parameterGroups:*,categoryParameters:*" \
  > /tmp/firm-vendor-form.json

# 3. Switch to DEST tenant
./skills/workfront-api/scripts/wf-use.sh acme-tenant

# 4. Schema discovery (cached if recent)
# (Skill runs the 5 /metadata GETs in parallel)

# 5. Sanitiser walks /tmp/firm-vendor-form.json
# Findings printed:
```

```
Cross-tenant clone — sanitiser findings:

  drop_default actions (4):
    customerID         (source: <firm-customer-guid>) — dropped
    ownerID            (source: <firm-user-guid>)     — dropped
    enteredByID        (source: <firm-user-guid>)     — dropped
    parameters[2].ownerID   (source: <firm-user-guid>) — dropped

  remap_required actions (0):
    (no displayLogic in this form references other parameterIDs)

  manual_review actions (0):
    (no homeGroupID / roleID references)

  parity_check_required actions (0):
    (no DE: references in any calculation body — there are no COMP fields)

No prerequisite check blocked. Proceeding.
```

```
# 6. Consultant's mutation: change Department options
Skill: "I noticed you wanted to change Department options to match Acme. The source has
[Marketing, Sales, Operations, Engineering]. Replace with which options?"

Consultant: "Acme uses: Brand, Demand Gen, Customer Success, Engineering, Finance.
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
  POST dest/category                        — name="[wf-api-verify] Project Vendor Tracking"
  POST dest/parameterGroup × 1               — "Vendor Details"
  POST dest/parameter × 6                    — same field set as source
  Bulk POST dest/parameterOption × 5         — the new Department options
  Bulk POST dest/categoryParameter × 6       — link rows

Type `apply` to execute, anything else to abort.
```

```
Consultant: apply
```

```
# 8. Skill executes
[wf-curl: audit captured -> ~/.claude/secrets/workfront/audit/acme-tenant/...]
[POST /category — categoryID = <dest-cat-guid>]
[POST /parameterGroup — parameterGroupID = <dest-grp-guid>]
[POST /parameter × 6 — collected parameterIDs]
[PUT /parameterOption?method=POST × 1 — 5 options created]
[PUT /categoryParameter?method=POST × 1 — 6 link rows created]

# 9. Done
Form created: https://acme.my.workfront.com/category/<dest-cat-guid>
In-product builder: https://acme.my.workfront.com/setup/customForms/<dest-cat-guid>

To attach this form to existing projects, use dedicated bulk-update tooling with its own pre-state capture and rollback model.
```

## What this demonstrates

- Sanitiser flagged 4 customer/user IDs (expected).
- No DE: parity checks needed (the source form has no COMP fields).
- Consultant overlay (different Department options) applied on top of the sanitised payload before write.
- Final write is one Category + one ParameterGroup + six Parameters + one bulk-options POST + one bulk-link POST.
