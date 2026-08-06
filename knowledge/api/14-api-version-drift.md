# 14 — API Version Drift (v20 → v22)

The toolkit pins examples to `v17.0` per the consulting rule in `SKILL.md`. v17.0 is still the safe default — it works against virtually every modern tenant. But Adobe shipped three substantial releases between May 2025 and late 2025, and several enum lists and field shapes documented elsewhere in the toolkit's knowledge files reflect v17.0 only.

This file consolidates what changed across v20, v21, v22 — especially the items that materially affect existing skills.

**Release dates (per Adobe Experience League release notes):**
- v20 — 2025-05-04
- v21 — 2025-10-23
- v22 — late 2025 (post-v21)

## Layout Templates — unchanged across all three releases

Zero changes to `UITMPL`, `LYTMPL`, or `LTMCL` in v20, v21, or v22. Confirmed empirical write-surface probe against a live production tenant on 2026-05-22:

- **UITMPL operations: `[count, delete, get, report, search]`** — no `add`, no `edit`. POST returns `unable to find method for service endpoint type: ADD (class com.attask.biz.UITemplateMethods...)`. PUT returns the same for `EDIT`. The new-experience layout template is genuinely read-only over REST. Only 2 actions exposed: `migrateLayoutTemplates(IDs[], overrideIfExists)` and `migrateCustomersAllLayoutTemplates(overrideIfExists)` — Classic→New within-tenant only.
- **LYTMPL operations: `[add, count, delete, edit, get, report, search]`** — full CRUD. Writable: `name`, `description`, `extRefID`, `groupID`, `showHomeTimestamps`, `defaultNavItem`, `licenseType`, `navItems` (via `updates=` JSON envelope). NOT writable: `navBar` is server-computed from `navItems`; submitted JSON is discarded.
- **LTMCL (terminology):** add + delete only, no edit. Auto-created with sentinel labels (`project.label.original` etc.) when a LYTMPL is created; placeholders cannot be updated; new LTMCLs have no exposed link mechanism to attach to a LYTMPL (FK field is not `layoutTemplateID`).
- **Assignment writes:** `user.layoutTemplateID` / `role.layoutTemplateID` / `team.layoutTemplateID` / `group.layoutTemplateID` are all writable.

This is intentional Adobe architecture — REST is being deprecated as the admin surface for new-experience layout config. Adobe Workfront Migrator is the supported cross-tenant path.

## Permissions — `coreAction` enum grew

Affects `knowledge/permissions/02-access-level-reference.md` and the `workfront-permissions` skill description. Phase A verified the v17.0 enum as `ADD/DELETE/EDIT/LIMITED_EDIT/VIEW` (5 values).

| Version | Added values on `ALVPER.coreAction` / `ACSRUL.coreAction` / `ACSREQ.action` and the matching `forbiddenActions` / `secondaryActions` |
|---|---|
| v20 | `REMOVE_CUSTOMFORM`, `ADD_SUB_PROJECTS` |
| v21 | `EDIT_CONTACTINFO` |
| v22 | (modified fields, no new enum values surfaced in release notes) |

So v21+ tenants surface up to 8 distinct values, not 5. When a permission audit returns one of the new values on a v20+ tenant, treat it as a valid action, not an unknown enum.

`QueueDef.requestorCoreAction` / `requestorForbiddenActions` got the same v20+v21 additions.

## Custom Forms — `dataType` and `displayType` enums grew

Affects `knowledge/custom-forms/02-parameter-types.md`. Phase A verified v17.0 enums:

- `dataType`: TEXT / NMBR / DATE / CURC / RICH / WIDGET (6)
- `displayType`: TEXT / SLCT / CHCK / RDIO / TXTA / MULT / TYAH / RICH / CALC / WIDGET / DTXT (11)

Subsequent additions:

| Version | `dataType` additions | `displayType` additions | Other Parameter / Category changes |
|---|---|---|---|
| v20 | — | `INTRNL`, `MULTINTRNL`, `UIEXTNSION` | — |
| v21 | `HTML` | `SNGLROLLUP` | `Parameter.isActive` field (custom fields can be deactivated); `Category.catObjCode` and `objTypes` accept `TEAMOB` (custom forms on Teams) |
| v22 | — | — | `Parameter.enteredByID`, `Parameter.entryDate`; `Category.entryDate` |

The Phase B-1 probe on client-d-preview (2026-05-22) discovered most of these empirically — `02-parameter-types.md` already documents `INTRNL/MULTINTRNL/UIEXTNSION/SNGLROLLUP/HTML` as working displayTypes/dataTypes. What it doesn't make explicit is that these are v20+/v21+ surfaces and may not work against a v17.0-pinned tenant.

The most consequential is `Parameter.isActive` (v21). Custom-form field audits enumerating Parameters need to filter or report on isActive when run against v21+ tenants.

`SCOREQ` (ScoreCardQuestion) got the same v20+v21 displayType additions.

### `Parameter` fields that DON'T exist in v17

Adobe's API Explorer enumerates these `Parameter` fields, but they are post-v17 additions — querying them against a v17-pinned tenant returns a `APIModel V17_0 does not support field <X> (Parameter)` error:

| Field | First seen | Notes |
|---|---|---|
| `Parameter.isPrivate` | v18+ (best estimate) | Per-field visibility flag. |
| `Parameter.parameterType` | v18+ (best estimate) | The `COMP` (calc) vs regular discriminator surfaced as its own field; on v17 the distinction is derived from `displayType=CALC`. |
| `Parameter.isActive` | v21 | Already covered above. |
| `Parameter.enteredByID` / `Parameter.entryDate` | v22 | Created-by metadata. |

Practical implication for v17 tenants: pulling `displayType` and `dataType` is enough to characterize a field. Don't request `isPrivate` or `parameterType` in a `fields=` list against v17 — Workfront rejects the whole call rather than ignoring the unknown field.

Verified on a preview sandbox tenant, v17.0, 2026-06-02.

## Financial layer — v20 rewrite + v21 cleanup

Affects `workfront-api` callers in general and dedicated bulk-update tooling flows that touch rates / costs / currency.

**v20:**
1. 30+ Project, 15+ Task, 12+ Template, 16+ Work, 9+ TemplateTask financial fields gained the `RESTRICTABLE` flag and converted from `double` → `java.math.BigDecimal`. Currency reads against v20+ tenants return BigDecimal-as-string, not JS numbers. Naïve `parseFloat()` is fine; naïve number arithmetic without coercion silently truncates precision on large amounts.
2. `Rate (RATE)` became a first-class primitive with `currency`, `locked`, `type`, `value` fields. New `billingRates` / `costRates` collections on Approval / Template / User / Role.
3. Revenue type values `URH`, `URC`, `URF` added to Approval / Task / TemplateTask / Work.

**v21 then REMOVED:**
- `Role.overrideCurrency`, `Role.overrideCostRate`, `Role.overrideBillingRate` — rate overrides moved entirely off the role onto the Rate primitive.
- `Assignment.assignmentBillingRoles` collection.
- `Rate.localBillingPerHour`, `Rate.localCostPerHour`.

**Practical impact:** bulk-update flows that read or write `role.overrideCostPerHour` or `role.overrideBillingPerHour` against a v21+ tenant will silently no-op. Either pin the request to `v20.0` (or `v17.0`) to keep the old fields, or rewrite the flow against the Rate primitive.

## Multi-currency rollout

| Version | What gained `currency` (or override-currency) |
|---|---|
| v20 | `Group.currency` |
| v21 | `Portfolio.overrideCurrency`, `Program.currency` |

By v21 currency cascades Group → Portfolio → Program → Project. Assessment / reporting flows that assumed a single tenant currency need to walk the chain when run against v21+ tenants.

## Reports

v22 added `ReportShareableFolder (RPSHFD)` with full CRUD (`add/count/delete/edit/get/report/search`), plus `PortalSection.reportShareableFolderID` and `PortalSection.reportShareableFolder` reference. New primitive for organising shared report folders outside the per-user "Shared with me" surface. Relevant to `workfront-reports` clone/lift-and-shift flows on v22 tenants.

## Enterprise Storage Management (ESM) — v22

`esmID`, `isCscProject`, `isEsmDocStorageEnabled` propagated across `PROJ`, `PRGM`, `PORT`, `TMPL`, `CMPY`, `DOCU`, `DOCFDR`, `APPROVAL`, `DOCV`. Only relevant to ESM-enabled tenants. `Document` also gained `getTemporaryCloudURL` action (v21) and `sendToAEMDetails` action (v22) — useful for any skill that needs a short-lived document URL or AEM hand-off.

## Other notable additions

- **v20:** `Avatar.attachedObjectCode` + COPY operation on Avatar; `DOMAIN_EXTENDABLE` flag on Assignment / OpTask / Portfolio / Program / Task / Role / User; `SHARABLE` on Company; new `CustomerPreferences` project-settings values (worth surfacing in platform assessments).
- **v21:** `APPROVAL` / `OPTASK` / `PROJ` / `TASK` / `WORK` gained `actualWorkRequiredDouble`; `CUST.APDISAB`; `OriginalRequest (ORGREQ)` added as a new resource; `PARAM.HTML dataType` adds a rich-text variant distinct from `RICH`.
- **v22:** `USER.userLocations` collection removed entirely (`USRLOC` object removed); `TASK.convertedOpTaskID` + `convertedOpTask` reference (task↔issue conversion is now traceable); `JournalEntry.changeType` gained `PFM` (folder move) value.

## How to apply

- **Default to `v17.0` in examples.** Still the right call per `01-api-fundamentals.md` — broadest tenant compatibility, and the toolkit's empirical verification is all v17.0-based.
- **When debugging a client API issue and the surface doesn't match a documented enum,** suspect the tenant is on a newer API version before asking for a HAR. Check this file's enum tables first.
- **When a client is on v20+ and the work touches financials,** use BigDecimal coercion paths and the Rate primitive — not the deprecated `role.overrideX` fields, which return null on v21+ tenants.
- **When permission-audit output contains a `coreAction` value not in the v17.0 5-tuple,** look it up here, not in `02-access-level-reference.md`.
- **When building a custom-form audit against a v21+ tenant,** account for `Parameter.isActive` — the field exists from v21 and silently excludes inactive parameters from the user's perspective.

## Source

Adobe Experience League release notes at `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/api-notes/new-api-version-{20,21,22}`. Layout-template empirical re-verify against a live production tenant on 2026-05-22.
