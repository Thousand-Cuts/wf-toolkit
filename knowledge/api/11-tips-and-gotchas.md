# 11 — Tips and Gotchas

Grab-bag of API hard-won knowledge. Light on day one; grow this file as you hit issues in real integrations.

## Cross-cutting truths from text mode that also apply to the API

- **Don't guess field names.** The API Explorer is the source of truth for exact camelCase names, data types, and read-only flags. (See file `04-fields-and-naming.md`.)
- **OPTASK and ISSUE are the same object.** Older filters and field names (`optaskID`) coexist with newer ones. Treat them as synonyms. (See file `03-object-codes.md`.)
- **Status codes, not display names.** Filters and request bodies compare against codes like `CPL` / `CUR`, not "Complete" / "Current." (See file `10-status-and-enum-codes.md`.)
- **`$$USER.*` resolves to the authenticated caller.** For service accounts and impersonation flows, this may not be the user you expect — pass explicit IDs. (See file `06-filtering-queries.md`.)
- **EXISTS bypasses depth limits.** If a filter seems to fail at 3 hops, restructure with EXISTS. (See file `07-exists-in-api.md`.)

## Soft delete vs hard delete

`DELETE /attask/api/v17.0/task/<id>` performs a **soft delete** by default. The object moves to the Workfront Recycle Bin and can be restored by an admin for up to 30 days.

Add `force=true` for a **hard delete**:
```
DELETE /attask/api/v17.0/task/<id>?force=true
```

Hard delete removes the object and all its dependents permanently. There is no undo.

**Practical implication:** If you're calling DELETE in a cleanup script and expecting the records to be gone, confirm whether the objects ended up in the Recycle Bin instead of being actually removed. A subsequent search returning 0 results doesn't mean a hard delete happened — it means the soft-deleted record isn't surfaced in normal search results.

**Template tasks (TTSK) MUST use `force=true`:** TTSK does not support a soft-delete path. A plain `DELETE /attask/api/v17.0/ttsk/<id>` returns:

```
{"error":{"message":"This Template Task cannot be deleted since it is referenced by other objects. Please use force delete."}}
```

`?force=true` is required whenever the task has children, predecessor links, or assignments — which is almost always. DELETE on a parent TTSK **cascades** to its children, so iterating a pre-fetched ID list will produce one or two "primary key not found" responses at the tail when children were already removed by an earlier parent delete. Treat those as success. (Empirically verified on v17.0, 2026-06.)

## Template task child collections (TASSGN, TPRED) — write through the parent

Both `TASSGN` (template-task assignments) and `TPRED` (template-task predecessors) refuse direct top-level POSTs:

```
POST /attask/api/v17.0/tassgn  →  {"error":{"message":"invalid objCode: null"}}
POST /attask/api/v17.0/tpred   →  {"error":{"message":"TPRED is not a top level object and can't be requested directly in internal"}}
```

Write them by PUTting the parent TTSK with an `updates={"assignments":[...]}` or `updates={"predecessors":[...]}` collection. The collection is replaced, not merged — fetch + append + put back if you need to preserve existing entries. (Empirically verified on v17.0, 2026-06.)

## Template task `workRequired` is set via `bulkCopy`, not direct write

On v17.0, every form of direct write to `workRequired` / `work` / `originalWorkRequired` on a freshly-created TTSK (and on its child TASSGN) silently persists `0`. Tested with form-encoded fields, `updates=` JSON, every `durationType` value, `isWorkRequiredLocked=true`, `workRequiredExpression="10 Hours"`, `workUnit=H|M|D`, and inline assignments at POST time — none of them set the value. (`durationType=D` does write a non-zero `workRequired`, but only to its own auto-computed value of `duration × 8h × 60 min`, not to what you asked for.)

**The working path is `TTSK.bulkCopy` from a donor task that already has the desired `workRequired`.** Action signature:

```
PUT /attask/api/v17.0/ttsk?action=bulkCopy
  updates={"templateTaskIDs":["<donor-id>"], "templateID":"<dest-template-id>"}

# Response: {"data":{"result":["<new-ttsk-id>"]}}
```

The copy inherits the donor's `workRequired`, `work`, `roleID`, `categoryID`, and one TASSGN row. A subsequent PUT can change `name`, `parentID`, `duration` (yes — duration is editable post-copy), and clear/override role/category. `workRequired` itself stays locked at the donor's value, so the donor must be picked to match the target hours. Cannot mix `updates=` JSON with plain form fields in one call — split into two PUTs (`Cannot mix 'updates' JSON parameter with non-JSON update parameter '<field>'`). The donor's predecessors and assignments also carry over; clear with `updates={"assignments":[],"predecessors":[]}` unless you mean to keep them.

`bulkCopy` is same-tenant only. For a cross-tenant template-task migration, find donors **on the destination tenant** with matching `workRequired` + `duration`, not the source tenant. (Empirically verified on v17.0, 2026-06.)

## Collection updates replace, not merge

When you PUT an object with a nested collection in `updates`, the collection is **completely replaced**, not merged with the existing value.

```
PUT /attask/api/v17.0/task/4c7...
updates={"assignments":[{"assignedToID":"user-A"}]}
```

This **removes all existing assignees** and sets only user-A. If you want to add an assignee, fetch the current assignments first, append to the list, and send the full array.

Top-level scalar fields behave normally (sparse update — only fields you send are changed). The replace behavior applies only to nested objects and arrays.

### Workfront auto-attaches `roleID` when you assign a user

When you create or assign a user (via `assignedToID=<userID>` on POST/PUT, or via `updates={"assignments":[{"assignedToID":"..."}]}`), Workfront silently populates the assignment row's `roleID` with the user's default/primary role. The role wasn't in your request — Workfront added it.

Practical effects:

- A subsequent collection replace that only specifies `assignedToID` produces a new row with a fresh auto-role, **discarding whatever role was previously bound to that assignment.** If you want to preserve a specific `roleID` across a replace, include it explicitly: `updates={"assignments":[{"assignedToID":"<user>","roleID":"<role>"}]}`.
- Team-only assignment rows (no user, no role) are not durable on issues — see the `assignMultiple` OPTASK collapse note below. The assignments collection effectively requires each row to bind a user or role.

Verified v17.0 on a live production tenant, 2026-05-13: created an OPTASK with `assignedToID=<user>`; the audit-captured assignment row showed both `assignedToID` and a `roleID` we never sent.

**Corollary — an explicit `roleID` must be a role the user actually holds.** If you send `assignedToID=<user>` + `roleID=<role>` where `<user>` doesn't have `<role>` on their profile, the whole POST/PUT is rejected: `<User Name> cannot be assigned to Role: <Role Name>`. When you don't care about the role, **omit `roleID`** and let Workfront pick the user's default (per the auto-attach above). Only pin `roleID` when you've confirmed the user carries it. Verified on a sandbox tenant v15.0, 2026-07-02.

### Fully unassigning an issue: clear the role too

The inverse of the auto-attach gotcha bites just as hard. PUT with `updates={"assignedToID": null}` — even when combined with `"assignments": []` — does **not** clear the `roleID` that Workfront attached when the user was originally assigned. The OPTASK retains the role, and a ghost ASSGN row lingers with `assignedTo: null` but `roleID: <previous role>`. The issue still shows a Consultant (or whatever the role was) bound in the UI.

Use the action endpoint instead:

```bash
curl -X PUT "$$HOST/attask/api/v17.0/optask/<id>/assignMultiple?apiKey=<key>" \
  -H "Content-Type: application/json" \
  -d '{"userIDs": [], "roleIDs": [], "teamIDs": []}'
```

That single call nulls `assignedToID`, nulls `roleID`, and empties the `assignments` collection. The response is `{"data":{"result":null}}` on success.

Verified v17.0 on a live production tenant, 2026-05-21: PUT `updates={"assignedToID":null,"assignments":[]}` left `roleID="<consultant role>"` and a ghost ASSGN row. Re-running with PUT `/optask/<id>/assignMultiple {"userIDs":[],"roleIDs":[],"teamIDs":[]}` cleared all three fields cleanly.

### Clearing a user's teams: `teams: []` alone leaves the Home Team

The replace-not-merge rule does half the job on USER: PUT `updates={"teams": []}` empties the **Other Teams** collection, but the Home Team is a separate scalar (`homeTeamID`) on USER — not a member row of `teams` — so it survives untouched. Same failure shape as the issue-unassignment gotcha above (empty the collection, a scalar lingers), with the resolution inverted: USER has no `assignMultiple`-style action endpoint, and none is needed — the scalar is directly writable in the same PUT:

```
PUT /attask/api/v17.0/user/<id>
updates={"homeTeamID": "", "teams": []}
```

<!-- UNVERIFIED -->
The collection-replace half follows from the rule documented above. The rest is the community answerer's tested report, not independently confirmed here — specifically that `homeTeamID` clears with `""` where `null` errors (the thread's `null` error could equally describe an attempt at `teams: null`). Provenance: best answer by Tracy_Parmeter, 2026-07-16 (Sources below).

Two cautions:

- **Fusion blueprint trap.** Do not put a literal `""` for `homeTeamID` in blueprint JSON — literal `""` becomes `null` on import (the Fusion record § Null vs empty), which is exactly the value reported to error. Use `{{emptystring}}`. Hand-configured modules are unaffected.
- **Destructive by design.** The same `"teams": []` on an *active* user wipes every team membership, no merge, no undo. Gate the scenario on `isActive=false` and capture pre-state (`GET /user/<id>?fields=homeTeamID,teams:ID,teams:name`) before running in bulk.

## Some child objects can't be POSTed directly — write through the parent

A collection field on a parent (e.g. `nonWorkDays` on `SCHED`) exposes child rows that carry their own `objCode`. It is tempting to create a new row by POSTing to that child's endpoint — for some object codes that fails with:

```
HTTP 422
{"error":{"message":"NONWKD is not a top level object and can't be requested directly in internal"}}
```

These children only exist as nested rows of the parent. They have no `/search`, no `/{id}` GET, and no direct POST. To add or modify them, PUT the parent with the full collection in `updates`:

```
PUT /attask/api/v17.0/sched/<schedule-id>
updates={"nonWorkDays":[{"nonWorkDate":"2026-01-01"},{"nonWorkDate":"2026-01-19"}]}
```

The same collection-replace semantics apply (see "Collection updates replace, not merge" above) — fetch the existing rows first via `fields=<collection>:<child-field>` and send the full merged list. Otherwise the rows you omit are deleted.

**How to spot one ahead of time:** the child `objCode` doesn't appear in `03-object-codes.md`, and a direct `GET /<objcode>/search` returns the "not a top level object" error. `NONWKD` (non-working day on a schedule) is one verified example.

Verified on `client-d.preview.workfront.com`, v17.0, 2026-05-21: `POST /nonwkd` returned the 422 above; `PUT /sched/<id>` with `updates={"nonWorkDays":[...]}` succeeded and the collection reflected the new rows on a follow-up `GET /sched/<id>?fields=nonWorkDays:nonWorkDate`.

## Collection filtering requires a separate query

The `fields=` expansion (e.g., `fields=tasks:name,tasks:status`) returns a full unfiltered collection inline. You cannot filter a collection inline — if you want "tasks in progress" for a project, query the task endpoint directly with a `projectID` filter rather than expanding tasks on the project response.

(See file `08-related-objects-and-collections.md` for when to use expansion vs separate calls.)

## Document folders: don't expand, invert the query

`GET /project/<id>?fields=documentFolders:name,documentFolders:ID` returns **422** with a gzip-corrupted body — the response cannot be decoded even with `curl --compressed`. The expansion path is unreliable for `documentFolders` on a project.

Use the inverted shape instead — query the folder endpoint directly with `projectID` as a filter:

```
GET /attask/api/v17.0/docfdr/search?projectID=<projectID>&fields=ID,name,parentID
```

`DOCFDR` (Document Folder) is a first-class object code, so it accepts `/search` with the normal filter and field syntax. This is the reliable shape for "list the folder tree on a project." Same pattern works for tasks (`taskID=<taskID>`) and issues (`opTaskID=<id>`).

Verified v17.0, 2026-05-20.

## Enum-filtered `/search` returns `data: []` for ANY string

`GET /<objcode>/search?<enumField>=<value>` does NOT validate the value against the field's enum. If `<value>` is bogus (or just unused), the response is `{"data": []}` with HTTP 200 — same shape as "the filter was valid but matched no records." There is no warning.

Confirmed for `status` on OPTASK / TASK / PROJ:

```bash
# These two calls return identical responses (empty data array):
curl -sS "https://<host>/attask/api/v17.0/optask/search?status=ZZZ&apiKey=<KEY>"
curl -sS "https://<host>/attask/api/v17.0/optask/search?status=LAP&apiKey=<KEY>"
```

`ZZZ` is bogus. `LAP` is a real custom status on the tenant (with zero records currently in that state). Same empty response, no way to tell them apart from this call alone.

**Implications:**
- Empty `data: []` is NOT proof a code is invalid. Use a write round-trip to verify a custom status exists (``10-status-and-enum-codes` § Verifying a custom status exists`).
- Empty `data: []` is NOT proof a custom-field value is invalid either — same silent-accept behavior.
- Smoke-testing a filter with a known-good value first lets you distinguish "filter syntactically correct" from "filter unrecognized."

Verified on a preview sandbox tenant, v17.0, 2026-06-02.

## API versioning gotchas

- **Never rely on the default version.** Workfront updates the default to the latest version with each release. Integrations without a pinned version break silently.
- **`api-internal` is not a version.** It's an unversioned path that reflects the latest internal build, changes without notice, and should never be used in production code.
- **Fields come and go between versions.** Before upgrading a version pin, check the "What's new in API version X" release notes. Fields deprecated in one version are typically removed two versions later.
- **As of 2025, versions 1–14 have been removed.** If you have legacy integrations using those versions, they are now broken.

## Posting an update (NOTE) — schema changes from older Fusion/integration payloads

If you have a Fusion blueprint, integration, or example payload that fails with confusing errors like `APIModel V<n>_0 does not support field refObjID (Note)` or `objCode cannot be null`, the NOTE schema has been quietly cleaned up across **all** modern API versions — not just the newest. Three changes:

| Old field | Current status | Fix |
|---|---|---|
| `refObjID` / `refObjCode` | **Removed** — no replacement | Delete from payload. The note's context comes from `objID` + `noteObjCode` (parent), `projectID`, `opTaskID` (for issues), `taskID` (for tasks), etc. |
| `topNoteObjID` | **Renamed** to `topObjID` | Rename the key. `topNoteObjCode` is unchanged. |
| `tags: [{ userID }]` alone | **Insufficient** — NOTETAG requires the polymorphic discriminator | Each tag must include `objObjCode` (e.g. `"USER"`) AND `objID` matching the user. Keep `userID` for backwards-compat. |

**This is not a "v19 breaking change."** Workfront pruned these fields retroactively from the v15.0, v17.0, v18.0, and v19.0 API models on the same tenant — the v17 and v19 NOTE metadata listings are byte-for-byte identical (58 fields each, same names). Pinning your integration to an older version will NOT bring `refObjID`/`topNoteObjID` back. You have to fix the payload.

The misleading `"objCode cannot be null"` error refers to the **NOTETAG sub-object's `objObjCode`**, not the parent NOTE's `objCode`. The NOTE-level `objCode` is accepted as input but no longer appears in the metadata listing — `noteObjCode` is the discriminator field that actually drives behavior.

Working payload for "post an update on an issue and @-tag a user" (works on v17.0, v18.0, v19.0 identically):

```json
POST /attask/api/v17.0/note
{
  "objCode": "OPTASK",
  "noteObjCode": "OPTASK",
  "objID": "<issue ID>",
  "opTaskID": "<issue ID>",
  "projectID": "<project ID>",
  "topNoteObjCode": "OPTASK",
  "topObjID": "<issue ID>",
  "noteText": "...",
  "tags": [
    { "objObjCode": "USER", "objID": "<user ID>", "userID": "<user ID>" }
  ]
}
```

The `tags` collection notifies the tagged user but does NOT auto-insert a clickable `@First Last` link into the rendered body — to get the inline mention chip, include the literal `@First Last` text in `noteText` alongside the `tags` entry.

Verified on a live production tenant, 2026-05-21: identical payload returned `200 OK` on both `/attask/api/v17.0/note` and `/attask/api/v19.0/note`; sending the old shape (`refObjID`, `topNoteObjID`) returned `APIModel V<n>_0 does not support field refObjID (Note)` on v15.0, v17.0, v18.0, and v19.0.

## Authentication failure modes

| Symptom | Cause |
|---|---|
| `"Invalid session ID."` in error body | Expired token, token from wrong environment, or malformed header |
| `200 OK` with empty `data: []` | The authenticated user has no access to those records — not an auth error, a permissions issue |
| Request works in Preview but fails in Production | Different OAuth2 app credentials between environments (credentials are not shared) |
| `/login` endpoint returns an error for IMS orgs | Adobe Business Platform / IMS orgs cannot use password-based login via the API; must use OAuth2 |

## Sandbox vs production behavioral differences

- **Data:** Preview refreshes weekly from production. Records created after the last refresh don't exist in Preview. This trips people up when testing against production-like record IDs.
- **Email and notifications:** Disabled by default in Preview. Don't test notification workflows in Preview expecting emails to arrive.
- **OAuth2 apps:** Must be created separately per environment. A production Client ID will not work against the Preview base URL.
- **API keys:** Production keys are copied to Preview during the weekly refresh, overwriting Preview keys. If your script generates a Preview key between refreshes, it will be wiped on the next refresh.
- **Concurrent thread limit:** Same cap applies in Preview as in production — correct for load testing.
- **Code version:** Preview is always ahead of production code (unreleased features visible in Preview first). A field that exists in Preview may not exist in production yet.

## Task-level behavioral gotchas (`bulkCopy`, status, assignments)

These don't cause API errors — they cause **silently wrong dashboard state**. Verified 2026-05-29 on a Client D v17.0 sandbox.

### `bulkCopy` on a CPL source preserves completion metadata

Duplicating a task whose `status=CPL` returns a new task that copies `status`, `percentComplete`, `actualStartDate`, and `actualCompletionDate` verbatim from the source — **but resets `assignment.status` to `AA`**. The mismatch is the bug: the assignment is active (not filtered off the doer's Home dashboard), while the task itself reads "complete." The UI tries to reconcile and renders an "In Progress"-looking row that doesn't make sense.

**Same bulkCopy on a NEW source returns a clean duplicate** (status=NEW, pct=0, null actuals, AA assignment). The problem is CPL-source-specific.

**`options[]` on `bulkCopy` has no reset semantic.** The argument is accepted but every plausible "reset" value (`resetStatus`, `resetActuals`, `copyAsNew`, etc.) returns `unknown copy option: <value>`. Workfront's option set is internal; no built-in flag fixes this.

**Mitigations**:
1. Don't duplicate CPL tasks — duplicate before completion, or duplicate from a NEW template task.
2. After bulkCopy against a CPL source, immediately PUT the new task with `{"status":"NEW","percentComplete":0,"actualStartDate":null,"actualCompletionDate":null}`. Easily automated via a Fusion scenario on TASK creation.

See `05-http-methods-and-actions.md` § "TASK action catalog and `bulkCopy` quirks" for the full reproduction.

### Task status changes don't cascade to `assignment.status`

PUT `task.status` from CPL back to NEW (or any non-CPL value). Every assignment whose status was `DN` ("Done") **stays at `DN`**. Those assignees lose visibility — the task is filtered off their Home dashboard, so they don't see it return.

To restore Home visibility, call `markNotDone(assignmentID)` for each previously-DN assignment. The transition is `DN → AD` (not `DN → AA` — see `10-status-and-enum-codes.md` for the AD ambiguity). The UI treats AD as active.

If this matters at scale (e.g., a project-management workflow that reopens completed work), build a Fusion scenario that watches TASK updates for the CPL → non-CPL transition and iterates `markNotDone` over the task's DN assignments.

## Common "why is my API call failing" checklist

1. **Is the sessionID header present and current?** Token expiry is the most common cause of sudden failures in long-running scripts.
2. **Is the URL pinned to a specific API version?** If not, a Workfront release may have shifted the default version.
3. **Is the field name exactly right?** Use the API Explorer, not the UI display name. `plannedCompletionDate`, not `Planned Completion Date`.
4. **Is the object ID from the right environment?** A GUID from production doesn't exist in Preview and vice versa.
5. **Is the filter returning 0 results when it should return data?** Check whether the authenticated user has access to those records (sharing rules, group visibility). Use a Workfront admin account to rule out permissions as the cause.
6. **Is a 429 appearing?** You've hit the concurrent thread limit. Add retry logic with exponential backoff. (See file `09-pagination-and-limits.md`.)
7. **Does DELETE return 200 but the record still shows up in a search?** That's soft delete. Use `force=true` or restore from the Recycle Bin as appropriate.

## URI length limit

Workfront's CDN enforces an **8,892-byte maximum URI length** for production, Preview, and test-drive environments. Complex EXISTS filters with many conditions can exceed this limit. When you hit it, move the filter parameters to a POST body:

```
POST /attask/api/v17.0/task/search
Content-Type: application/x-www-form-urlencoded

status=CUR&status_Mod=eq&EXISTS:1:$$OBJCODE=ASSGN&...
```

## Custom form metadata

Custom fields are accessed via `DE:FieldName` on the object. The metadata (what forms exist, what fields they contain) is stored on `Category` (form) and `Parameter` (field) objects. If an admin changes a custom form after you've fetched the form metadata, your cached metadata is stale — re-fetch `Category` objects if your integration needs to know what custom fields are available dynamically.

`parameterValues` is a wildcard that returns all custom field values on an object in one call — useful when you don't know field names ahead of time:

```
GET /attask/api/v17.0/project/<id>?fields=parameterValues
```

`fields=parameterValues` is the working wildcard for custom fields (verified on v17.0, 2026-05). The alternative `fields=DE:*` does **NOT** work — the API returns `"no such field: '*'"`. Stick with `parameterValues` for "give me all custom field values," or list specific `DE:` fields by name. See `04-fields-and-naming.md` for the response shape.

## Building API queries faster

1. **Build the filter in the Workfront UI first.** Switch to text mode in a report, copy the filter lines, prefix with `EXISTS:N:` if needed, drop into your API call.
2. **Use `fields=` aggressively.** Default field sets are minimal. Asking for what you need up front avoids N+1 follow-up requests.
3. **Test in the API Explorer's "try it" pane** when available — it handles auth and URL-encoding for you so you can iterate on the query shape.
4. **Start with `$$LIMIT=1`** when iterating on a new query. Once the shape and filters look right, raise the limit.

## `assignMultiple` on OPTASK with team-only payload collapses to primary team

`PUT /optask/<id>/assignMultiple` with the body `{"teamIDs":["A","B"],"userIDs":[],"roleIDs":[]}` returns `{"data":{"result":null}}` (success) — but only the **first** team ends up applied, as the issue's primary `teamID` scalar. The second team is silently dropped and the `assignments` collection stays empty.

Likely cause: issues require each assignment "slot" to combine a team with a user or role; pure team-only assignments collapse to the primary `teamID`.

Workarounds:
- Pair each team with a user (`userIDs` parallel array of equal length).
- Use the same shape against a task (`/task/<id>/assignMultiple`) where the assignments collection accepts team-only rows.
- Or, replace the `assignments` collection directly via `PUT /optask/<id>` with `updates={"assignments":[{"teamID":"A"},{"teamID":"B"}]}` (collection replace semantics apply — see "Collection updates replace, not merge" above).

Verified on v17.0 preview, 2026-05.

## Gzipped responses break naive curl

Workfront sometimes returns `Content-Encoding: gzip` even when the request did not send `Accept-Encoding: gzip`. Without decompression, `curl` prints binary garbage and pipe-into-`jq` scripts fail silently.

Fix: always pass `--compressed` to curl (or send `Accept-Encoding: identity` if you need to force uncompressed for log capture):

```
curl --compressed -G "https://<host>/attask/api/v17.0/project/search" ...
```

## When stuck

1. Confirm the field name in the API Explorer (exact case, exact spelling, including `DE:` prefix for custom fields).
2. Reproduce the request in the API Explorer's interactive UI — if it works there but not from your code, the issue is in your client (auth, encoding, headers).
3. Search the Adobe Experience League community forums.
4. Compare against the matching text-mode filter — if you can build the same query as a text-mode report and it returns the records you expect, the issue is in API translation, not in the filter logic itself.

## Parameter + Category (Custom Form) gotchas

These bit us during a pilot 2026-06-18 and are not obvious from the API metadata alone.

### `POST /parameter` — required fields differ from older docs

In v17.0+, **no** `parameterType` field exists on PARAM. The schema uses two separate fields:

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Internal name |
| `label` | yes | Display label — separate field, also required |
| `dataType` | yes | Enum: `TEXT`, `DATE`, `DTTM`, `NMBR`, `CURC`, `RICH`, `WIDGET` (plus v20+ additions per [`14-api-version-drift.md`]) |
| `displayType` | yes | Enum: `SLCT` (drop), `MULT`, `TEXT`, `TXTA` (textarea), `RDIO`, `CHCK`, `PSWD`, `DTXT`, `TYAH`, `RICH`, `WIDGET`, `CALC` |

A POST that includes a `parameterType` field returns `APIModel V17_0 does not support field parameterType (Parameter)`. A POST without `label` returns `Label is required and cannot be empty`.

**Parameter names can't contain parens.** A name like `Logged At (ET)` returns `Invalid character in 'name' : '('` with code 1200. Use `Logged At ET` instead.

### Date vs Date/Time — pick before you write any data

`dataType=DATE` stores only the date portion. `dataType=DTTM` (Date/Time) stores date+time. **WF refuses dataType conversion once any value exists on the parameter**, even after the value is deleted:

```
PUT /parameter/<id> updates={"dataType":"DTTM"}
→ "Data Type conversions between Date to Date/Time are not allowed if data exists for this Parameter."
```

Workaround (drop + recreate): detach the parameter from its category (PUT `/category/<id>` with `categoryParameters` array NOT containing the bad param), DELETE the parameter with `force=true`, recreate with the correct `dataType`, re-link to the category. Capture the new ID — anything referencing the old parameterID (Fusion blueprints, reports) needs updating.

### `POST /categoryParameter` is rejected — use PUT /category instead

`CTGYPA` is not exposed as a top-level object in v17.0:

```
POST /categoryParameter updates={...}
→ "CTGYPA is not a top level object and can't be requested directly in internal"
```

To link parameters to a category, **PUT the category with the full `categoryParameters` collection** (this is a collection-replace — the array you send replaces the existing set):

```bash
PUT /attask/api/v17.0/category/<categoryID>
updates={
  "categoryParameters": [
    {"parameterID": "...", "displayOrder": 1, "isRequired": false},
    {"parameterID": "...", "displayOrder": 2, "isRequired": true}
  ]
}
```

If a referenced parameter was deleted, the PUT errors with `Parameter with primary key value(s) "<id>" not found` because Make/WF validates the existing collection. Workaround: PUT with `categoryParameters: []` first to clear, then PUT again with the new list.

### OPTASK custom form ≠ PROJ custom form

A category created with `catObjCode: OPTASK` can only be attached to OPTASK records, not to projects:

```
PUT /project/<id> updates={"objectCategories":[{"categoryID":"<optask-category-id>"}]}
→ "Category: <name> is not a Category of the type: PROJ"
```

For a queue that creates ISSUES (OPTASKs) via a custom form, attach the category at issue-creation time via the `categoryID` field on the optask POST. The project never needs to know about the form.

### Posting notes — auto-notification behavior

Workfront sends an email to the target object's `assignedTo` (issues) or `owner` (projects) whenever a NOTE is posted on it. **No `tags` array is required** to notify the assignee about a new note on their own issue. Use `tags` only when you want to @-mention SOMEONE OTHER THAN the natural owner/assignee.

Minimal "post an update visible to the assignee" payload:

```json
POST /note
{
  "noteObjCode": "OPTASK",
  "objID": "<issue ID>",
  "noteText": "..."
}
```

The assignee receives the email; no `tags` needed.

## Pinning task dates: use the `MSO` constraint, not planned dates or "Fixed Dates"

Directly setting `plannedStartDate` + `plannedCompletionDate` on a task via POST/PUT does **not** stick — the scheduler recomputes them from the project start + predecessors + duration, collapsing both onto the project start when the task has no predecessor. The `taskConstraint:"FIXEDDATES"` (and `"Fixed Dates"`) value the UI exposes as "Fixed Dates" is **silently ignored over REST** — it falls back to `ASAP`.

To pin a task to an explicit window over REST, use a **Must-Start-On** constraint plus a duration:

```
POST /attask/api/v17.0/task
  updates={"projectID":"<pid>","name":"…",
           "taskConstraint":"MSO","constraintDate":"2026-07-01T08:00:00",
           "duration":"3","durationUnit":"D"}
```

- `MSO` pins the **start** to `constraintDate`; completion is computed as start + `duration` working days (respecting the assignee's schedule under the default `durationType:"A"`).
- `MFO` (Must-Finish-On) pins the **completion** instead and back-computes the start.
- Do **not** set `durationType:"S"` here — it zeroes the duration (see `10-status-and-enum-codes` § Duration Type). Omit `durationType` (defaults to `A`) or use `D`.
- Parent (phase) tasks roll their dates up from children automatically — leave them unconstrained.

Verified on a sandbox tenant v15.0, 2026-07-02 (building a 59-task project WBS with pinned per-task dates).

## Creating a request queue over REST (QueueDef + QueueTopic)

Turning a project into a request queue touches three objects — Project, `QUED` (QueueDef), `QUET` (QueueTopic) — and neither sub-object is created the obvious way:

1. **`QUED` has no `ADD`/`EDIT` REST method.** `POST /QUED` → `unable to find method for service endpoint type: ADD`; `PUT /QUED/<id>` → same for `EDIT`. Create/modify the QueueDef **nested under the project** instead — the project's `queueDefID` links automatically, and arrays serialize correctly through this nested PUT:
   ```
   PUT /attask/api/v17.0/project/<id>
     updates={"queueDef":{"isPublic":1,"hasQueueTopics":true,
                          "defaultCategoryID":"<request-form categoryID>",
                          "allowedOpTaskTypes":["ISU","REQ","CHO","BUG"]}}
   ```
2. **QueueTopics are NOT created via the nested `queueDef.queueTopics` array** — a nested `queueTopics:[…]` in the project PUT is silently dropped (`hasQueueTopics` stays false, collection stays empty).
3. **Create topics with `POST /QUET`, but only AFTER the parent QueueDef's `allowedOpTaskTypes` is set.** Each topic's `allowedOpTaskTypes` (from `ISU`/`BUG`/`CHO`/`REQ` — the `OpTaskTypeEnum`) must be a **subset** of the QueueDef's. If the QueueDef doesn't yet allow the type, `POST /QUET` rejects even a single valid value with `Invalid Parameter: allowedOpTaskTypes value "REQ"` — a misleading error whose real cause is the un-set parent.
   ```
   POST /attask/api/v17.0/QUET
     updates={"queueDefID":"<qd>","name":"New RFP Response",
              "defaultCategoryID":"<OPTASK form>","allowedOpTaskTypes":["REQ"]}
   ```
   A topic's `defaultCategoryID` request form must be an **OPTASK/ISSUE** category (requests land as issues), not a PROJ category.

Verified on a sandbox tenant v15.0, 2026-07-02.

## Adjacent surface: Workfront Data Connect staleness is self-reporting

Not the REST API — Data Connect is the separate Snowflake data-share surface — but it lands in the same consultant question ("how do I get Workfront data out, and how fresh is it?"), so the pointer belongs here.

Adobe documents the refresh interval as every 4 hours but publishes no wall-clock schedule, and it is not a value to guess at: a report built on Data Connect is up to one full interval stale, and the interval's phase determines whether a morning report includes yesterday evening's work. Do not infer the schedule from the documented interval — read it out of the share, which reports its own freshness two ways:

- `MONITORING_DATA_REFRESHES` — a view giving the last refresh time per object type.
- `DL_LOAD_TIMESTAMP` — a column present on the object rows themselves, giving when that individual row was last loaded.

<!-- UNVERIFIED -->
One tenant's reported observation: refreshes land at 4:20 / 8:20 / 12:20 and so on, which the answerer read as the *completion* of a run started on the hour, with the timestamps rendered in **UTC** rather than the instance timezone. Treat the specific times as that tenant's phase, not a platform constant — the answerer explicitly hedged ("I'm not sure if it's the same for everyone"), and no second tenant confirmed it in the thread. The two artifact names are the durable part: query them per tenant instead of assuming a schedule. Provenance: best answer by BrookeSt5, 2026-07-28 (Sources below).

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/api-general-information/api-basics` | soft/hard delete (`force=true`), collection replace behavior, URI length limit, `parameterValues` |
| `https://experienceleague.adobe.com/en/docs/workfront/using/administration-and-setup/set-up-wf/testing-environments/wf-preview-sandbox-environment` | Preview sandbox behavioral differences, credential sync behavior |
| `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/api-notes/api-version-support-schedule` | Version removal timeline, api-internal guidance |
| `https://experienceleague.adobe.com/en/docs/workfront/using/administration-and-setup/manage-wf/security/manage-api-keys` | API key copy behavior on Preview refresh |
| `https://experienceleaguecommunities.adobe.com/t5/workfront-questions/is-anyone-else-getting-429-too-many-concurrent-api-requests/td-p/485050` | 429 concurrent limit behavior |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-fusion-24/fusion-module-to-clear-other-teams-251712` | one-PUT `{"homeTeamID": "", "teams": []}` to fully clear a user's teams — best answer by Tracy_Parmeter, 2026-07-16 |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/data-connect-refresh-251986` | Data Connect freshness is readable from the share itself — `MONITORING_DATA_REFRESHES` view and the `DL_LOAD_TIMESTAMP` row column; one tenant's observed :20-past phase, read as UTC — best answer by BrookeSt5, 2026-07-28 |
