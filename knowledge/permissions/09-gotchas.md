# 09 — Gotchas

The most common ways consultants get tripped up by Workfront's permission model. Updated 2026-05-18 with Phase A empirical findings.

## 1. `coreAction` enum is NOT VIEW/CONTRIBUTE/MANAGE/DELETE

**Surprise:** "I'm querying for `coreAction=CONTRIBUTE` rules and getting nothing."
**Mechanic:** The real `coreAction` enum is `ADD / DELETE / EDIT / LIMITED_EDIT / VIEW`. `CONTRIBUTE` and `MANAGE` never existed in the API. The spec drafts were wrong. `EDIT` is the action the spec called "CONTRIBUTE"/"MANAGE".
**Mitigation:** Use the 5-value empirical enum from `01-permission-model`.

## 2. `ADD` is a separate axis (not on the ordinal ladder)

**Surprise:** "I granted the user DELETE. They still can't ADD new tasks."
**Mechanic:** `ADD` (create new objects) is NOT implied by DELETE / EDIT / VIEW. It's a separate grant axis. To let a user create new tasks, you need a rule (or ALVPER row) with `coreAction=ADD` specifically.
**Diagnostic:** Inspect the access level's ALVPER rows; look for `(objObjCode=TASK, coreAction=ADD)`.

## 3. The resolver requires exact `coreAction` match — not ordinal

**Surprise:** "I have a DELETE share but the resolver says no EDIT."
**Mechanic:** The empirical model treats coreActions as discrete, not ranked. A `coreAction=DELETE` rule does NOT auto-grant EDIT or VIEW. Workfront's UI typically configures shares with multiple rules per (user, object) when the user needs multiple actions.
**Mitigation:** When auditing a user's overall access, iterate the 5 coreActions and accept the strongest ALLOW returned.

## 4. AccessRule is NOT a top-level object

**Surprise:** "`/accessRule/search` returns an error: ACSRUL is not a top level object."
**Mechanic:** Same constraint as CTGYPA in custom-forms. AccessRule rows must be accessed via the parent object's `accessRules` collection. Direct queries on the endpoint are rejected.
**Mitigation:** For "what rules apply to user X?" use the inverted parent-query pattern:
```bash
GET /project/search
  ?accessRules:accessorID=<userID>
  &accessRules:accessorID_Mod=eq
  &fields=ID,name,accessRules:*
```
Repeat across multiple parent objCodes. See `03-accessrule-shape` and `05-audit-recipes`.

## 5. Field is `accessorID`, not `accessorObjID`

**Surprise:** "I'm filtering by `accessorObjID` and getting an error."
**Mechanic:** Phase A confirmed the field is named `accessorID` (with `accessorObjCode` for the type). The `accessorObjID` name was a spec-era guess.
**Mitigation:** Use `accessorID` + `accessorObjCode` consistently.

## 6. System Admin bypass uses `isAdmin`, not empty `forbiddenActions`

**Surprise:** "I added `MANAGE` to a System Admin's forbiddenActions. They can still MANAGE."
**Mechanic:** Workfront's System Admin gate is the `isAdmin: true` flag on the AccessLevel itself, not the contents of `forbiddenActions`. System Admin's ALVPER collection is empty by design — they don't have per-object rules; they bypass the matrix entirely.
**Diagnostic:** Check `access_level.isAdmin`. If true, the user has unrestricted access regardless of any other input.

## 7. `forbiddenActions` are feature-flag denials, not coreAction subtractions

**Surprise:** "I added `EDIT` to `forbiddenActions` on a `coreAction=DELETE` rule. The user can still EDIT."
**Mechanic:** `forbiddenActions` is NOT a list of coreAction values. It's a list of granular feature-flag names like `EDIT_FINANCE`, `EDIT_TEAMS_I_AM_ON`, `VIEW_CONTACTINFO`, `SHARE_SYSTEMWIDE`. Putting `EDIT` in `forbiddenActions` does nothing — `EDIT` isn't a valid feature-flag name.
**Mitigation:** Use the 11 empirically-observed feature-flag values from `03-accessrule-shape`. To actually prevent EDIT, remove the rule that grants `coreAction=EDIT` or override with a `LIMITED_EDIT` variant.

## 8. Capability matrix is a collection, not a flat field

**Surprise:** "I'm doing `GET /accessLevel/<id>?fields=permissions` and not finding it."
**Mechanic:** Phase A confirmed there's no flat `permissions` field. The capability matrix lives in a **collection** called `accessLevelPermissions` (objCode `ALVPER`). Standard access level has ~92 ALVPER rows.
**Mitigation:** Expand `accessLevelPermissions:*` instead. See `02-access-level-reference`.

## 9. Inheritance surfaces inline — no parent walk needed (usually)

**Surprise:** "I'm walking up the parent chain to find inherited rules. Slow."
**Mechanic:** Phase A confirmed the child's `accessRules` collection already includes inherited rules inline, each marked with `isInherited=true` + `ancestorID` + `ancestorObjCode`. The walker isn't needed for the headline Flow 1 use case.
**Mitigation:** Single GET on the target with `accessRules:*`. The walker remains for the few cases where you need to query parents directly (e.g. "what shares COULD apply to a future child of this portfolio?").

## 10. `isDefault` doesn't exist on AccessLevel

**Surprise:** "I'm filtering AccessLevel by `isDefault=true` and getting an error."
**Mechanic:** `isDefault` is not a real field. Spec drafts referenced it; Phase A confirmed it returns "APIModel V17_0 does not support field isDefault (AccessLevel)".
**Mitigation:** Don't use. To find Adobe's shipped levels vs custom ones, look at the GUID prefix (system-shipped use `64f8d9d1...` on the surveyed tenant; customs have a different prefix) — but this is tenant-specific.

## 11. The "users see all projects" toggle isn't a thing in v17.0

**Surprise:** "How do I read the 'users see all projects' toggle via REST?"
**Mechanic:** It doesn't appear to exist as a discoverable setting in modern v17.0 Workfront. Phase A tried 6 endpoint variants (customerInformation, customer, customerPreferences, tenant, preferences, siteSettings) — all failed or required a name. HAR captures of the internal preference endpoints surfaced 53 keys, none visibility-related. Capture #6 surveyed AccessLevel.accessRestrictions (only `AIOFF` and `CGT` values) and probed 13 candidate visibility names against v17.0 `/customerPreferences/search` (0 hits).
**Mitigation:** Stop looking for it. Visibility is controlled by AccessLevel ALVPER matrix + per-object AccessRules + ownership + group/team/role membership. The resolver had a layer-4 short-circuit for this in v0.14.x; v0.15.0 removed it. See `07-system-wide-overrides` and the internal verification notes §Finding 7 for the full empirical record.

## 12. Public-link / share-link bypasses the whole model

**Surprise:** "User has no AccessRule on this report but can see it via a URL."
**Mechanic:** REPORT and DASHBD objects support public-link sharing (toggled in-product). A link recipient bypasses every sharing rule.
**Mitigation:** Out of scope for v1's debug flow. Check the report's public-share status manually in-product. v2 candidate.

## 13. Additive model — no general "deny"

**Surprise:** "I removed a sharing rule but the user can still see the object."
**Mechanic:** Removing one AccessRule only removes that *accessor*'s grant. Other rules (different accessor, inherited, owner, isAdmin level) may still grant. No general "deny" mechanism at the sharing level. The only subtraction is `forbiddenActions` on the same rule.
**Diagnostic:** Run Flow 1 — the verdict's per-layer summary names every layer that's still granting.

## 14. Owner = implicit `DELETE` (top tier)

**Surprise:** "I removed all sharing on this project but the original creator can still manage it."
**Mechanic:** `target_object.ownerID` grants implicit `DELETE` (Workfront's top action). Cannot be removed without changing ownership.
**Diagnostic:** Flow 1's owner short-circuit. Or directly: `GET /<obj>/<id>?fields=ownerID,owner:name`.

## 15. Cross-tenant access level names are NOT a guarantee

**Surprise:** "Both tenants have a 'Standard' access level — they should grant the same thing, right?"
**Mechanic:** Access levels are tenant-owned. Same display name + completely different ALVPER collections. The tenant survey showed 6 levels including a custom "Standard with Limits" that shares the same row count as plain "Standard" but with different `forbiddenActions`.
**Diagnostic:** Flow 5 (cross-tenant compare) — diff the ALVPER collections row-by-row.

## 16. `fieldAccessPrivileges` is a separate per-field grant axis

**Surprise:** "The user has `coreAction=EDIT` on PROJ. Why can't they edit certain fields?"
**Mechanic:** AccessLevel has a separate `fieldAccessPrivileges` string[] with codes like VFN, EFN, VDE, EDE, SDE — these grant specific per-field-class privileges (view/edit financial name, view/edit/share DE custom data, etc.). The resolver doesn't model these in v1; they're a separate axis from the ALVPER matrix.
**Mitigation:** Out of scope for v1's verdict combiner. Document the field's value in the audit output but don't try to interpret it.

## 17. License type + access level interaction

**Surprise:** "I gave the user the Standard access level but they still can't use feature X."
**Mechanic:** Workfront license tier (encoded in `AccessLevel.licenseType` as a single letter, e.g. `F` for full) caps what the access level can actually grant. A "External User" license can't do things a "Plan" license can, regardless of ALVPER rows.
**Diagnostic:** v0.17.0 — resolver surfaces `license_tier: {code, label, is_decoded}` on every verdict. Decoded values: `F` = Full license. Phase A only confirmed `F` empirically; Light Worker / External User tier codes weren't in the tenant survey and will appear as `is_decoded: false`. The resolver does NOT auto-DENY based on tier (empirical surface too thin) — when the consultant sees an `is_decoded: false` tier on a confusing verdict, that's the cue to check the in-product license-tier capability matrix manually.

## 18. Layout Template hides UI that the permission model grants

**Surprise:** "The resolver verdict is ALLOW at every layer but the user still says they can't see the Documents tab / can't see the Add button / can't see a whole section."
**Mechanic:** Layout Templates (Setup → Interface → Layout Templates) are a UI-layer gate assigned per-access-level, per-group, or per-user. They control which object tabs, sections, fields, and buttons render — completely independent of the REST permission model. A user with `coreAction=DELETE` on a project and `DOCU=DELETE` on their access level can still be unable to see the Documents tab on a task if their Layout Template hides it.
**Why this is invisible to the resolver:** `AccessLevel.layoutTemplateID` is not a v17.0 field — `GET /accessLevel/<id>?fields=layoutTemplateID` returns "APIModel V17_0 does not support field". The model has no read access to this layer at all.
**Diagnostic:** When Flow 1 produces ALLOW but the consultant insists the user is blocked, Layout Template is the #1 operational cause. Direct the consultant to Setup → Interface → Layout Templates → find the template bound to the user's access level (or their group, or their user record) and inspect tab/section/button visibility for the relevant objCode. Confirmed 2026-05-22 on a live-tenant ADD-document-on-task issue where the model said ALLOW and the actual blocker was Layout Template hiding the Documents tab on TASK.

## Cross-references

- `01-permission-model` — the 6-input model + exact-match coreAction
- `02-access-level-reference` — ALVPER collection, isAdmin semantics
- `03-accessrule-shape` — accessorID, ancestorID, forbiddenActions enum
- `06-inheritance-and-ownership` — inline isInherited
- `07-system-wide-overrides` — what's not REST-accessible
