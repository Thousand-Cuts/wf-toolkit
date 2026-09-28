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

## 19. A flat share list does not scale; group nesting is the way past an entry cap

**Surprise:** "This report has to reach 119 groups and the share dialog stops taking entries at 100."

**Mechanic:** A share is one `ACSRUL` row per accessor, and the share list is flat: there is no "all groups" accessor and no bulk-add on the object. `GROUP`, however, is a **hierarchy**, and that is the lever. Verified 2026-08-28 on `a sandbox tenant.workfront.com` (sandbox), v17.0: `GET /group/metadata` returns a `parentID` field, a `parent` reference with `typeObjCode: GROUP`, and a `children` collection (there is no `subGroups` collection; the name is `children`). A live nested pair on that tenant confirms it is populated in practice, not just declared: `GET /group/<id>?fields=ID,name,parentID,children:ID,children:name` on "Financial Marketing" returns one child, "Financial Marketing - Quarterly Reports", and that child's own row carries the matching `parentID`. Negative control: `fields=ID,zzzNotAField` on the same endpoint is rejected with `APIModel V17_0 does not support field zzzNotAField (Group)`, so the field names above resolving is evidence rather than permissiveness.

<!-- UNVERIFIED -->
The community claim built on that substrate: a share granted to a **parent** group reaches the users of its subgroups, so N sibling groups renested under one new parent collapse to a single share row. Unverified because proving the cascade needs a share to be created and then read back as a different user, which is a write; this routine is read-only. The same answer offers sharing at the **Company** level as the other escape hatch, which only fits when the intended audience really is everyone.

**Also unverified: the 100-entry cap itself.** It is the asker's premise, and nobody in the thread confirmed a number or named where the limit is enforced. No GET settles it, since reproducing it means creating more than 100 shares. Treat "around 100" as a reported ceiling to design away from, not a constant to quote at a client. What the sandbox does show is that real share lists sit nowhere near it: across 200 projects and 200 reports, the largest single `accessRules` collection held 10 rows.

**Mitigation:** When a share list is heading for triple digits, restructure the accessor rather than the list. Audit what already exists first, because a tenant that has been running for years may already have the hierarchy: `GET /group/search?fields=ID,name,parentID&$$LIMIT=200` and group the result by `parentID` shows how much nesting is in place (on the verification tenant, 1 of 50 groups had a parent, so effectively none). Nesting is a governance change and not a free one: it also merges those groups for group-admin scope, group-level Layout Templates, and every other object already shared to the new parent, so it should be proposed as a structural change, not slipped in to unblock one report.

**Related:** § 18 for the other reason a correct-looking share does not produce the visibility someone expects.

## 20. Adjacent surface (Workfront Planning): field-level sharing is enforced through the API, so an integration can silently read fewer fields

Planning has no bucket of its own; this is filed here because "why can't this identity see that value" is a permissions question and this is where a consultant searches for it.

**Surprise:** "The Fusion scenario reads the record fine and one column comes back missing. Nobody changed the record type's sharing, and the same call as an admin returns the field."

**Mechanic:** Workfront Planning shares permissions at the **individual field** level, below the record type, and Adobe states the restriction is enforced "everywhere where the field displays … including all the views, record details pages, request forms, connections and lookup fields, Canvas dashboards, **the API, and MCP tools**." So field-level sharing is not a UI-only nicety: it changes what a REST or Fusion identity reads back, and it does so without an error. This is the same shape as the `items: []` trap in `../fusion/11-platform-and-tenancy.md` § 7 — an empty or absent value that means "this identity cannot see it", not "there is nothing there".

The rules that decide what an identity gets:

- Access combines **inherited permissions** (a field inherits the record type's access by default: View → view values, Contribute/Manage → manage values) with either **Everyone with access to the record type can view** or **Only invited people can access**. Where several rules hit one person, the **highest** applies.
- **Lookup fields always inherit their source object's field permissions** and cannot be shared separately.
- **System fields (Created By, Record ID) and primary fields cannot be restricted at all** — so their presence proves nothing about whether other fields were withheld.
- Only **workspace owners and managers** can adjust field permissions, and a workspace manager's Manage access to every field cannot be lowered. Field sharing governs *values*, not the field's configuration.
- Granting someone a field does **not** grant workspace or record-type access; until they have that, the grant sits inactive behind a warning icon.
- For **global record types**, field permissions are set once and apply across all secondary workspaces, and cannot be overridden locally.
- Fields can only be shared **from the table view** of a record type.

**Two consequences for audit work, both stated by Adobe:** restricted field value changes are **not recorded in the record's History**, and field permission changes **trigger no notifications**. A field-level restriction is therefore close to invisible after the fact — the audit trail a consultant would normally reach for does not carry it.

**Mitigation:** When a Planning integration reports a missing or empty field, check field-level sharing for the integration's identity before debugging the scenario, the mapping or the API version. When designing one, give the integration identity a role whose field access is deliberate rather than incidental — and record it, because History will not.

**One Adobe-side open question, worth not relying on.** The published page carried "when you duplicate a record, the restricted values are not copied to the new records" until this commit, which **removed the line into an HTML comment** with the writer's own note: *"Not sure if this is right - right now, it allows me to duplicate with the values in the new record - checking with Lilit"*. Adobe has retracted that claim pending its own check, so do not design a redaction-by-duplication step on it. (Visible only because the upstream sweep reads HTML comments; the rendered Experience League page shows neither the claim nor the retraction.)

First-party; no live re-check was available this run (`sweep-verify.sh` blocked — see the PR digest), and the sandbox tenant is not a Planning tenant regardless.

## 21. Adjacent surface (Workfront Planning): a request inherits permissions from its record type and cannot be narrowed off them

Filed here for the same reason as § 20 — Planning has no bucket, and this is where a consultant looks for "who can see this". Preview **2026-09-25**, fast release 2026-10-14, everyone **2026-10-15**, so this reaches production within weeks of writing.

**Surprise:** "We locked the workspace down, then shared one intake request with a vendor at View. They can read every other request submitted through that form as well — and there is no inherited-permission row to remove."

**Mechanic:** Planning requests are now shareable objects in their own right (View / Contribute / Manage), but their access is *composed*, and two of the composition rules grant more than the person doing the sharing expects:

- **Manage on a record type inherits Manage on that record type's intake form and on every request submitted through it.** Request-level sharing is not the only path to a request, and the broad grant is usually a record-type grant someone made months earlier for an unrelated reason.
- **Requests inherit from the workspace and the record type, and for Planning requests those inherited permissions cannot be removed or edited.** A request therefore cannot be made *more* private than its record type. The narrowing move available on many Workfront objects — share explicitly, then strip inheritance — does not exist here.
- **Requesters are automatically granted Manage on what they submit**, unless an admin set a different default on the request form (a new Permissions section in the form's Settings area, same release).
- **Where grants collide the highest wins**, exactly as at field level in § 20: a user with Contribute whose group has View keeps Contribute. Restricting someone means finding *every* entity that grants them access, not adding a narrower row.
- Sharing is capped at your own level — Contribute cannot grant Manage. Workfront administrators reach every request regardless.

**Adobe widened who can be a sharee in the same window**, which enlarges the surface all of the above runs over: workspaces, record types and records can now be shared with **users, groups, teams, companies, and job roles**, where the page previously said only "people inside your organization". The job-role share is the one to watch on an audit, because its membership changes without anyone touching the share.

**Mitigation:** treat the record type as the real permission boundary for intake, because it is the level that propagates — assume anything holding record-type Manage can read every request through that form. When one request genuinely needs to be narrower than its record type, the answer is a separate record type, not a share edit, because the inheritance cannot be stripped. When auditing "why can this person see this", enumerate group, team, company and job-role grants before concluding the request-level share is the whole story.

**Related:** § 20 for the field-level half of the same model, including the same highest-wins rule; `../fusion/11-platform-and-tenancy.md` § 7 for why an integration identity reading less than expected looks like empty data rather than an error.

First-party and dated. No live re-check was available this run (`sweep-verify.sh` blocked — see the PR digest); the sandbox tenant is not a Planning tenant, and the Planning API is not reachable through the sweep's wrapper in any case, so this entry would carry first-party provenance rather than a verification line even with the wrapper working.

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/share-report-with-more-than-100-users-groups-252329` | § 19: the reported 100-entry share cap, and the parent-group / Company-level workarounds. Best answer by Lyndsy-Denk, 2026-08-14 |
| AdobeDocs/workfront.en `help/quicksilver/planning/requests/share-requests.md` @ `da1df635` (2026-09-25) | § 21: the View/Contribute/Manage levels on a Planning request, requester auto-Manage and the form-level default that overrides it, record-type Manage inheriting the intake form and every request through it, the un-removable inherited permissions, highest-wins across entities, and the share-at-or-below-your-own-level rule. New file this window. Blob: `https://github.com/AdobeDocs/workfront.en/blob/da1df63501d251518dc65a56c38524774aa25caa/help/quicksilver/planning/requests/share-requests.md` |
| AdobeDocs/workfront.en `help/quicksilver/planning/access/sharing-permissions-overview.md` @ `da1df635` (2026-09-25) | § 21: workspaces, record types and records shareable with users, groups, teams, companies and job roles (previously "people inside your organization"). The page's Preview-environment *field*-sharing block remains inside `<!-- -->` staging at this SHA and is deliberately not drawn on here — § 20 already carries the field-level model from `share-fields.md`. Blob: `https://github.com/AdobeDocs/workfront.en/blob/da1df63501d251518dc65a56c38524774aa25caa/help/quicksilver/planning/access/sharing-permissions-overview.md` |
| AdobeDocs/workfront.en `help/quicksilver/product-announcements/product-releases/planning-release-activity/planning-release-activity-26-q4.md` @ `da1df635` (2026-09-25) | § 21's release dates: Preview 2026-09-25, production fast release 2026-10-14, production for everyone 2026-10-15, for request sharing, field sharing and multi-stage request approvals alike. Blob: `https://github.com/AdobeDocs/workfront.en/blob/da1df63501d251518dc65a56c38524774aa25caa/help/quicksilver/product-announcements/product-releases/planning-release-activity/planning-release-activity-26-q4.md` |
| AdobeDocs/workfront.en `help/quicksilver/planning/access/share-fields.md` @ `136f06e5` (2026-09-18) | § 20: Planning field-level sharing, its enforcement through the API and MCP tools, the inheritance/override rules, the un-restrictable field classes, the History and notification gaps, and the retracted duplicate-record claim. The page left preview gating in this window (the `class="preview"` block was uncommented) and gained its full "Share fields" procedure. Blob: `https://github.com/AdobeDocs/workfront.en/blob/136f06e5336bba85bd7e8066f0662ffef81588ff/help/quicksilver/planning/access/share-fields.md` |


## Cross-references

- `01-permission-model` — the 6-input model + exact-match coreAction
- `02-access-level-reference` — ALVPER collection, isAdmin semantics
- `03-accessrule-shape` — accessorID, ancestorID, forbiddenActions enum
- `06-inheritance-and-ownership` — inline isInherited
- `07-system-wide-overrides` — what's not REST-accessible
- `03-accessrule-shape` — one ACSRUL row per accessor, which is why § 19's list is flat
