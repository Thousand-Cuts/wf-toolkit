# 02 — Access Level Reference

Reference for the Workfront `AccessLevel` (objCode `ACSLVL`) object and its `accessLevelPermissions` collection (objCode `ALVPER`).

Updated 2026-05-18 with Phase A empirical findings against a live Workfront tenant. The earlier spec drafts conjectured a flat permissions field — wrong. Phase A confirmed the capability matrix lives in a **collection** of ALVPER rows.

## AccessLevel field map (empirical)

| Field | Type | Notes |
|---|---|---|
| `ID` | string | GUID |
| `name` | string | "System Administrator", "Standard", "Light", etc. |
| `description` | string | Free text. |
| `descriptionKey`, `nameKey` | string | Localisation keys. |
| `extRefID` | string | External integration reference. |
| `customerID`, `lastUpdatedByID`, `lastUpdatedDate`, `entryDate` | various | System-managed. |
| **`isAdmin`** | boolean | **The System Admin gate.** When true, the user holding this level bypasses all per-object grant checks. `accessLevelPermissions` is empty for isAdmin levels by design. |
| `isUnsupportedWorkerLicense` | boolean | Internal flag. Read-only. |
| `accessRestrictions` | string[] | `AccessRestrictionTypeEnum`. **Empirical values (single-tenant survey 2026-05-18):** `AIOFF` (AI opt-out per access level; present on 5 of 6 levels except System Admin), `CGT` (custom-group-tier marker; only on "Standard with Limits"). **NOT visibility-related** despite earlier hypotheses — see `07-system-wide-overrides`. |
| `fieldAccessPrivileges` | string[] | `PrivilegeTypeEnum`. **Empirical values (single-tenant survey):** 18 codes — `VFN, EFN` (financial fields), `VDE, EDE, SDE` (DE custom-data), `TAD, HAD`, `PAP, TAP, IAP` (project/task/issue access privileges), `PRE, PDO, PCA, VPR, MGU, CPJ, VTMAWMG, VALLTM`. Per-field-class grants alongside the ALVPER matrix. Distribution: System Admin has all 18; Standard / Standard with Limits have 12; Contributor / Light / External User have 4 (just `VDE, EDE, VTMAWMG, VALLTM`). v0.16.0 — the resolver surfaces these on every verdict as `field_privileges: {raw, decoded, undecoded}` using `PRIVILEGE_CODE_LABELS` in `permission_resolver.py`. Confidently-decoded codes (VFN/EFN/VDE/EDE/SDE/PAP/TAP/IAP/VTMAWMG/VALLTM) come with human labels; the 8 remaining codes (TAD/HAD/PRE/PDO/PCA/VPR/MGU/CPJ) surface in `undecoded[]` so the admin sees them raw rather than silently dropped. |
| `licenseType` | string | Single letter, e.g. `F` for full. License-tier-coupled. v0.17.0 — resolver surfaces this on every verdict as `license_tier: {code, label, is_decoded}` using `LICENSE_TYPE_LABELS`. Phase A only confirmed `F` empirically (both System Admin and Standard carried it on the surveyed tenant); other tiers (Light Worker, External User) likely have their own codes but weren't surveyed. Unknown codes surface with `is_decoded: False`. Modelled as informational metadata, NOT a verdict constraint — the empirical surface is too thin to safely auto-DENY based on tier. |
| `securityModelType` | string | e.g. `D` for default. |

**Collections:**

- `accessLevelPermissions → ALVPER` — the capability matrix (see below).
- `accessRulePreferences → ARPREF` — not surveyed in Phase A.

## ALVPER (AccessLevelPermission)

Each row represents **one granted permission**: "this access level grants `coreAction` on `objObjCode`."

| Field | Type | Notes |
|---|---|---|
| `ID` | string | Row GUID |
| `objCode` | string | Always `"ALVPER"`. |
| `objObjCode` | string | The objCode this row applies to (e.g. `PROJ`, `TASK`, `DOCU`, `ALIGN`, `AGILC`, `BGHRIN`, ...). |
| `coreAction` | string | One of `ADD`, `DELETE`, `EDIT`, `LIMITED_EDIT`, `VIEW` on v17.0 (toolkit default). v20+ tenants surface up to 8 values — see `../api/14-api-version-drift.md` § Permissions. |
| `forbiddenActions` | string[] | Feature-flag denials (see `03-accessrule-shape`). |
| `secondaryActions` | string[] | Extra named grants beyond `coreAction`. |
| `isAdmin` | boolean | Mirrors parent AccessLevel.isAdmin. |

**Important:** ALVPER is a **collection-only** object. `/accessLevelPermission/metadata` returns empty — there's no top-level endpoint. Must be accessed via the parent AccessLevel:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/accessLevel/<id> \
  --data-urlencode "fields=*,accessLevelPermissions:*"
```

## Granularity scale (empirical)

Surveyed across all 6 access levels on the surveyed tenant (393 ALVPER rows total):

| Level | ALVPER row count |
|---|---|
| System Administrator | 0 (isAdmin bypass) |
| Light | 79 |
| External User | 56 |
| Contributor | 74 |
| Standard | 92 |
| Standard with Limits (custom) | 92 |

Each row is one `(objObjCode, coreAction)` grant. The objObjCode space is fine-grained — includes "user-facing" codes like `PROJ`, `TASK`, `DOCU` AND internal/specialised codes like `ACK` (acknowledgment), `AGILCF` (agile card field), `ALIGN`, `BGHRIN`, `ESPPLN`, etc.

## `coreAction` distribution observed

Across the 393 ALVPER rows surveyed:

| coreAction | Count |
|---|---|
| `DELETE` | majority — most rows grant the full read/write/delete tier |
| `EDIT` | small minority — restricted-edit cases |
| `VIEW` | small minority — read-only grants |
| `ADD` | a few rows — explicit create grants |
| `LIMITED_EDIT` | a few rows — constrained-edit cases |

Conclusion: the typical ALVPER row pattern is "this access level can fully manage (`DELETE`-tier) this objObjCode" with occasional restricted variants.

## `forbiddenActions` observed on ALVPER rows

Most ALVPER rows have `forbiddenActions: []`. The 4 rows with non-empty values from the survey:

```
{objObjCode: NLBR,   coreAction: DELETE, forbidden: ["EDIT_FINANCE"]}
{objObjCode: NLBRCY, coreAction: DELETE, forbidden: ["EDIT_FINANCE"]}
{objObjCode: TEAMOB, coreAction: DELETE, forbidden: ["EDIT_TEAMS_I_AM_ON"]}
{objObjCode: <other>, ...}
```

So restricted access levels (e.g. "Standard with Limits") use `forbiddenActions` on specific rows to narrow what the user can actually do.

## Inspecting a single access level (Flow 4)

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/accessLevel/search \
  --data-urlencode "name=Standard" --data-urlencode "name_Mod=eq" \
  --data-urlencode "fields=*,accessLevelPermissions:*"
```

Plus user count:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/user/count \
  --data-urlencode "accessLevelID=<id>" \
  --data-urlencode "accessLevelID_Mod=eq"
```

The user count is critical context for any subsequent design discussion — changing an access level affects every user holding it.

**Note:** the field `isDefault` does NOT exist on AccessLevel in v17.0 (Phase A confirmed via error message). Earlier spec drafts referenced it. Don't use.

## Cross-environment compare (Flow 5)

```bash
# Pull source (sandbox)
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-use.sh sandbox
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/accessLevel/<src-id> \
  --data-urlencode "fields=*,accessLevelPermissions:*" > /tmp/src-level.json

# Pull dest (production)
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-use.sh prod
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/accessLevel/<dest-id> \
  --data-urlencode "fields=*,accessLevelPermissions:*" > /tmp/dest-level.json

# Diff the ALVPER collections by (objObjCode, coreAction).
```

The diff normalisation logic should be:

1. For each side, build a set of `(objObjCode, coreAction)` tuples from the ALVPER rows.
2. Symmetric difference yields the divergence.
3. Per-row `forbiddenActions` and `secondaryActions` are sub-diffs within matching tuples.
4. Plus a flag diff for `isAdmin`, `licenseType`, `accessRestrictions`, `fieldAccessPrivileges`.

## Default access levels shipped by Adobe

The names below are common defaults but **organisations customise heavily**. Same display name across environments does NOT imply the same capability matrix. Always inspect via Flow 4.

| Access Level | Typical pattern (single-tenant sample) |
|---|---|
| System Administrator | `isAdmin: true`, empty ALVPER collection |
| Standard | ~92 ALVPER rows, mostly DELETE |
| Plan / Worker / Contributor | similar shape, fewer rows |
| Reviewer | mostly VIEW + COMMENT-style secondaryActions |
| Requestor | OPTASK ADD + VIEW |
| External User | VIEW on a small set of objCodes |

> TODO (v2): cross-tenant survey to confirm the defaults' shape across multiple Workfront orgs.

## Cross-references

- `01-permission-model` — how AccessLevel sits in the 6-input model
- `03-accessrule-shape` — AccessRule object (the per-object shares — different from AccessLevel which is per-user)
- `05-audit-recipes` — Flow 4 (single level) and Flow 5 (cross-environment compare)
- `09-gotchas` — `isDefault` doesn't exist; isAdmin bypass; fieldAccessPrivileges as a separate axis
