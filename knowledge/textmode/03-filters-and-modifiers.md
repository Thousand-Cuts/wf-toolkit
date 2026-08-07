# 03 — Filters and Modifiers

## Filter syntax basics

**Filter object-reference cap: 5.** A single filter can reference at most 5 objects beyond the report object itself. Adobe documents this number explicitly in their filters-overview docs. Every distinct join hop (e.g., `project:portfolio:owner:homeGroup` — 4 hops) plus every `EXISTS:N:$$OBJCODE` block (1 hop each) counts toward the 5. Beyond that, the reporting engine errors out. Reports that need broader scope refactor into a custom prompt (each option fires independently — only one per render) or split into two reports. Cross-link: `knowledge/reports/05-gotchas.md` #17 covers the engine-side failure mode and the prompts escape hatch in detail.

Source: Adobe `report-elements/filters-overview`.

Every filter line takes one of two forms:

```
fieldName=value
fieldName_Mod=modifier
```

The `_Mod` line declares HOW to compare the value (equals, contains, greater than, etc.).

### Minimal example: status equals Current
```
status=CUR
status_Mod=eq
```

### Custom field filter
```
DE:Region=North America
DE:Region_Mod=eq
```

## Filter modifiers (full list)

| Modifier | Meaning |
|---|---|
| `eq` | Equal to |
| `ne` | Not equal to |
| `gt` | Greater than |
| `lt` | Less than |
| `gte` | Greater than or equal |
| `lte` | Less than or equal |
| `contains` | Contains substring (case-sensitive) |
| `notcontains` | Does not contain (case-sensitive) |
| `cicontains` | Contains substring (case-insensitive) |
| `like` | Like (SQL-style, case-sensitive) |
| `clike` | Like (case-insensitive) |
| `in` | Value is in list |
| `notin` | Value is not in list |
| `between` | Value between two values (REQUIRES paired `_Range=` key — see below) |
| `notbetween` | Value not between two values (same `_Range=` pairing) |
| `isnull` | Value is null |
| `notnull` | Value is not null |
| `isblank` | Value is blank (null or empty string) |
| `notblank` | Value is not blank |

## Range filters (`_Mod=between` + `_Range=`)

The `between` modifier requires a paired `_Range=` key on the same field. Example:

```
plannedCompletionDate=2026-01-01
plannedCompletionDate_Mod=between
plannedCompletionDate_Range=2026-12-31
```

Reads as "plannedCompletionDate between 2026-01-01 and 2026-12-31, inclusive." The `_Range` value is the upper bound; the base key is the lower bound. Both bounds accept date wildcards (`$$TODAY`, `$$TODAY+30d`). Source: Adobe `text-mode/edit-text-mode-in-filter`.

## AND logic (default)

Multiple filter lines are AND-ed together automatically. No prefix needed.

```
status=CUR
status_Mod=eq
priority=3
priority_Mod=gte
```

This finds records where status = Current AND priority >= 3.

## OR logic

Use the `OR:N:` prefix where `N` is a group number. All lines with the same number are OR-ed together.

```
status=CUR
status_Mod=eq
OR:1:status=PLN
OR:1:status_Mod=eq
OR:1:priority=3
OR:1:priority_Mod=gte
```

This finds records where status = Current OR (status = Planned AND priority >= 3).

### OR with custom fields
```
OR:1:DE:Region=North America
OR:1:DE:Region_Mod=eq
```

### OR with EXISTS (see file 06)
```
OR:1:EXISTS:a:$$OBJCODE=TASK
OR:1:EXISTS:a:projectID=FIELD:ID
OR:1:EXISTS:a:status=INP
```

## Escaping commas in multi-value `_Mod=in` filters

When a `_Mod=in` value contains a literal comma (e.g., a custom-field option labeled "Red, Blue"), escape with a forward slash before the comma:

```
DE:check=red/, blue
DE:check_Mod=in
```

Without the slash, Workfront splits on the literal comma and looks for two separate values ("red" and " blue"). Source: Adobe `report-elements/filters-overview`.

**"Not Equal" misbehavior on multi-select custom fields.** A filter `DE:tags_Mod=ne&DE:tags=red` against a multi-select custom field only excludes records whose `tags` value is EXACTLY `"red"` and nothing else. Records with `tags=["red", "blue"]` are NOT excluded — the multi-select comparison is exact-set, not contains-set. To exclude all records containing "red", use `_Mod=notcontains` instead (and accept that it's a substring match, which carries its own edge cases). Source: Adobe `report-elements/filters-overview`.

**Typeahead custom fields filter by ID, never by name.** A `TYAH` field with a `refObjCode` stores a JSON envelope (`{"objCode":…,"name":…,"ID":…}`), but the filter engine indexes it by the referenced object's **ID** only. `DE:Assigned Strategist=<32-char user ID>` with `_Mod=eq` works; filtering on the person's name matches zero rows even though the name is inside the stored value. If users need to filter by name, mirror the name into a plain-text field at save time. Verified 2026-08-06 on a live production tenant, v17.0 — full test matrix and scope limits in `custom-forms/09-gotchas` § 33.

## Status code filter values

Common status codes (the underlying values, not display names):

| Code | Meaning |
|---|---|
| `INP` | In Progress |
| `CPL` | Complete |
| `CUR` | Current |
| `PLN` | Planning |
| `DED` | Dead |
| `APV` | Approved |
| `REJ` | Rejected |

**Pending approval suffix:** append `:A` to a status to mean "pending approval to enter this status." Example: `status=CPL:A` means "Pending Approval to Complete."

### `statusEquatesWith` — match custom statuses by the system status they map to

`status` matches a literal status key, so a filter built on it has to enumerate every group-level custom status by hand and be re-edited each time someone adds one. `statusEquatesWith` matches on the **system status the custom status is mapped to**, so it stays correct as custom statuses come and go:

```
statusEquatesWith=CUR
statusEquatesWith_Mod=in
```

Substitute any system status key from the table above (`CUR`, `PLN`, `CPL`, …). This is the same field the API and UIFT filter layers use — see `knowledge/reports/06-filter-patterns.md` § 1 for the JSON form and `knowledge/reports/05-gotchas.md` for why it is a query-time pseudo-field rather than a real object field (it does not appear in `/<obj>/metadata`).

<!-- UNVERIFIED -->
**Reported to have gone missing from the filter-builder UI.** A consultant reported on 2026-07-29 that "Status Equates With" vanished from the field picker on existing prompt-based project reports, with no release note. Adobe Support's reply, quoted in the thread, attributed it to the rolling reporting/filter-builder UI updates ("certain filter fields like Status Equates With can become hidden in the updated filter builder UI"), called it a known internal concern, and gave the two Text Mode lines above as the supported workaround — the filter still evaluates server-side even when the builder won't offer it. Support also suggested checking that group-level custom statuses are correctly mapped, since unmapped statuses can affect filter visibility.

This is a support-desk account of a UI regression, not a reproduction: neither the disappearance nor its scope (tenant-specific? all prompt reports? all objects?) has been confirmed here. The Text Mode syntax itself is independently corroborated by the reports bucket. Provenance: best answer by ConnorO2, 2026-08-03 (Sources below).

## Wildcards in filter values

```
ownerID=$$USER.ID
ownerID_Mod=eq

plannedCompletionDate=$$TODAY+30d
plannedCompletionDate_Mod=lte
```

## Common filter patterns

### Projects I own that are active
```
ownerID=$$USER.ID
ownerID_Mod=eq
status=CUR
status_Mod=eq
```

### Tasks due in the next 7 days, not complete
```
plannedCompletionDate=$$TODAY
plannedCompletionDate_Mod=gte
plannedCompletionDate=$$TODAY+7d
plannedCompletionDate_Mod=lte
percentComplete=100
percentComplete_Mod=lt
```

### Projects in a list of portfolios
```
portfolioID=PORTFOLIO_ID_1,PORTFOLIO_ID_2,PORTFOLIO_ID_3
portfolioID_Mod=in
```

### Custom field is blank
```
DE:Vendor Name=
DE:Vendor Name_Mod=isblank
```

## Custom prompts

Custom prompts can only be edited in text mode. Pattern:

```
fieldName=
fieldName_Mod=in
fieldName_Range=fieldName
fieldName_Prompt=Choose a value
```

## Where to find field names

The API Explorer at `experienceleague.adobe.com` lists every field on every object with its exact name and data type. When in doubt, look it up there — don't guess.

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/project-status-equates-with-filter-gone-252039` | `statusEquatesWith=CUR` + `_Mod=in` as the Text Mode fallback when "Status Equates With" is missing from the filter-builder UI; Adobe Support's attribution to the reporting-UI rollout — best answer by ConnorO2, 2026-08-03 |
