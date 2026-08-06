# 07 — System-Wide Overrides (Investigated, Disproven)

**Status:** layer removed from the resolver in v0.15.0. This file preserves the empirical record of why.

In v0.14.x the resolver had a "layer 4" that modelled tenant-wide visibility toggles like "users see all projects" or "users see only their own data". HAR capture round 2 and capture #6 (2026-05-18) showed that toggle doesn't appear to exist as a discoverable setting in modern v17.0 Workfront. v0.15.0 removed the layer; the resolver now combines 6 inputs instead of 7.

The capture detail below is preserved because the **internal preference endpoints themselves are still useful reference material** for v2 work, even if they don't surface the specific toggles we were chasing.

## What the empirical search ruled out

### v17.0 REST is too narrow

Phase A tried 6 endpoint variants against the surveyed tenant; all failed:

- `/customerInformation/metadata` → empty `{"data":{}}`
- `/customer/search` → server-side error
- `/customerPreferences/search` → requires a `name` field; cannot list-all
- `/tenant/metadata` → "Unknown object type: tenant in v17.0"
- `/preferences/metadata` → "Unknown object type"
- `/siteSettings/metadata` → "Unknown object type"

There's no v17.0 endpoint that enumerates the full system-preference list. The only way to read a v17.0 customerPreference is to know its `name` in advance.

### The internal endpoints (HAR-captured 2026-05-18)

**Save:**

```
POST /internal/setup/savepreferences
Content-Type: multipart/form-data

form=<JSON-stringified object containing ALL current preference key/value pairs>
```

Response: `{"data": {"success": true, "message": "Preferences have been successfully edited"}}`. Read-before-write: the UI GETs the entire prefMap, mutates the target key, POSTs the full mutated map back.

**Read:**

```
GET /internal/setup/loadSystemPreferences
```

Returns a wrapper object with read-only metadata (`isImsEnabled`, `ssoEnabled`, `testEnvironmentList`, etc.) plus the actual key/value preferences nested under `prefMap`:

```json
{
  "isImsEnabled": true,
  "prefMap": {
    "PASSWORD_ALLOW_IFRAME": "true",
    "PASSWORD_SESSIONTIMEOUT": "604800",
    "CUSTOMER_DEFAULT_STORAGE_MODE": "LEGACY",
    ...
  },
  ...
}
```

20 keys in the surveyed tenant's prefMap (full list in the internal verification notes).

**Two additional preference endpoints (also captured):**

```
GET /preferences/api/v1/project/groups/system      — 18 project-level defaults
GET /preferences/api/v1/task-issue/groups/system   — 15 task/issue defaults
```

Both require an `X-XSRF-TOKEN` header. The task-issue endpoint surfaces `taskAccess`, `issueAccess`, `requestAccess` — assignment-grant defaults that may interact with permissions in non-visibility ways. **Worth a closer look in v2** for the permission resolver's accuracy on assignment-related verdicts.

### Why the layer-4 hypothesis collapsed (capture #6, 2026-05-18)

After Findings 1–5 mapped the internal preference surface (53 keys total, none matching `*SEE_ALL*` / `*PROJECTS*` patterns), capture #6 tested the next hypothesis: maybe the visibility toggles live on AccessLevel definitions. Surveyed all 6 surveyed access levels:

- **`AccessLevel.accessRestrictions`** has only 2 values across all levels: `AIOFF` (AI opt-out, on 5/6 levels) and `CGT` (custom-group-tier marker, only on "Standard with Limits"). Neither is visibility-related.
- **`AccessLevel.fieldAccessPrivileges`** has 18 values — all per-field-class grants (financial, custom-data, time-management). Not visibility.
- **v17.0 `/customerPreferences/search`** uses a different namespace than the internal endpoint. Probed 13 candidate visibility names → 0 hits. Even known-existing keys from the internal endpoint return "Invalid Parameter" when probed against v17.0 customerPreferences.

**Conclusion:** the "tenant-wide visibility override" concept doesn't correspond to anything reachable via REST in modern v17.0. Visibility is controlled entirely through:

1. AccessLevel ALVPER matrix (presence/absence of `(objObjCode, coreAction)` rows)
2. AccessLevel.accessRestrictions (AI gating only)
3. Per-object AccessRules (direct + inherited inline)
4. Object ownership
5. Group / team / role memberships

The resolver was demoted to 6 inputs in v0.15.0 (removed the system-override short-circuit and the `customer_overrides=` parameter).

## Caveats — what we did NOT prove

- Single-tenant survey (single tenant). Other tenants on different Workfront editions / license tiers may surface additional `accessRestrictions` enum values that the survey missed.
- Could be hidden in an admin setup section we didn't navigate to.
- Could exist as group-scoped (`groupId != 'system'`) overrides that the system-tier capture missed.
- `fieldAccessPrivileges` 3-letter codes (VFN/EFN/VDE/...) decoded by inference, not confirmed against Adobe docs.

A multi-tenant survey or deeper Adobe documentation review could reopen this. If a future capture surfaces an actual visibility override mechanism, the resolver can be re-extended; the empirical record above keeps that door open.

## Auth gap that closed the v2 path

The `/internal/*` endpoints are not part of Workfront's published REST API contract. **The v17.0 API key does NOT authenticate `/internal/*` requests** (confirmed 2026-05-18 via the 5-strategy probe in Finding 6). Probes returned 302 redirects to Adobe IMS login when the API key was passed as query param, `apiKey:` header, `sessionID:` header, or `Authorization: Bearer`. The internal endpoints require a full user-context browser session (`webcache` + `wf-node` + `XSRF-TOKEN` cookies set by interactive login). This applies whether the consultant uses a maintainer-side or client-side credential wrapper — both pass the v17 API key, which `/internal/*` rejects. There's no client-folder convention that fixes this.

Any v2 work calling `/internal/*` would need a full OAuth2 / login flow first to mint a session token — substantial sub-project. Combined with Finding 7's conclusion that the toggles probably don't exist anyway, the cost-benefit pushed both directions of follow-up out of scope.

## Cross-references

- `01-permission-model` — the current 6-input model (v0.15.0)
- `04-debug-playbook` — debugging flows no longer reference layer 4
- `09-gotchas` — "system-wide preferences not browsable via v17.0" is still a useful gotcha
