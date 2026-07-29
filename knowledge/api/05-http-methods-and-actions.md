# 05 — HTTP Methods and Actions

The Workfront API combines standard HTTP verbs (GET, POST, PUT, DELETE) with an `action` parameter for operations that don't map cleanly to CRUD — things like "search," "copy," "approve," or "log time."

## The four HTTP verbs

| Method | Operation | Notes |
|---|---|---|
| `GET` | Read — retrieve by ID, search, run reports, named queries | Safe; no side effects |
| `POST` | Create — insert a new object | Body carries field values |
| `PUT` | Update — edit an existing object | Body carries changed field values |
| `DELETE` | Delete — remove an object | Soft-delete by default; see tips in `11-tips-and-gotchas.md` |

### GET — retrieving objects

**By ID:**
```
GET /attask/api/v17.0/project/4c78821c0000d6fa8d5e52f07a1d54d0
```

**By a list of IDs:**
```
GET /attask/api/v17.0/project?id=4c78...54d0,4c78...54d1
```

**Search with filters** (the most common pattern):
```
GET /attask/api/v17.0/project/search
  ?status=CUR
  &status_Mod=eq
  &fields=name,status,plannedCompletionDate
```

See `06-filtering-queries.md` for the full filter syntax.

**Count only** (no data rows, just how many match):
```
GET /attask/api/v17.0/project/count?status=CUR&status_Mod=eq
```
Returns `{"count": 42}`.

**Report (aggregated):**
```
GET /attask/api/v17.0/hour/report
  ?project:name_1_GroupBy=true
  &hours_AggFunc=sum
```

**Named query (shortcut for common views):**
```
GET /attask/api/v17.0/work/myWork
```

### POST — creating objects

```
POST /attask/api/v17.0/project
Content-Type: application/x-www-form-urlencoded

name=My+New+Project&status=PLN&portfolioID=4c7...
```

**Copy an existing object** — include `copySourceID` in the POST body:
```
POST /attask/api/v17.0/project
Content-Type: application/x-www-form-urlencoded

copySourceID=4c7...&name=Copied+Project
```

**Create a project from a template** — include `templateID` in the POST body (empirical, verified against a live Workfront sandbox, v17.0, 2026-07-06):
```
POST /attask/api/v17.0/project
Content-Type: application/x-www-form-urlencoded

updates={"name":"New Project","programID":"<prgm-id>","templateID":"<tmpl-id>","status":"CUR"}
```
`templateID` is a real copy trigger, not just a reference field: the created project comes back populated with the template's task structure. Verified end-to-end — a project created from the "Creative Master" template (objCode `TMPL`) returned **25 copied tasks** on a `GET /TASK/search?projectID=<new-id>` immediately after create. Distinct from `copySourceID` (which clones an existing *project*); `templateID` instantiates a *template* into a live project. The template's own tasks are objCode `TMPLTASK` — but note a portfolio-scoped API key may return nothing when reading `TMPLTASK`/`TMPL` internals directly, so verify the copy by counting `TASK` on the *resulting project*, not by pre-reading the template.

**Upload a document** (two-step):
```
POST /attask/api/v17.0/upload
(multipart body with file)
```
Returns `{"handle": "4c7c08fa..."}`. Then POST a `document` object referencing that handle.

### PUT — updating objects

**Simple update (ID in path):**
```
PUT /attask/api/v17.0/project/4c7...
Content-Type: application/x-www-form-urlencoded

name=Updated+Name
```

**JSON update via `updates` parameter** (cleaner for nested data):
```
PUT /attask/api/v17.0/project/4c7...
Content-Type: application/x-www-form-urlencoded

updates={"name":"Updated Name","status":"CUR"}
```

**Nested collection update** (collections are replaced entirely, not merged):
```
updates={"assignments":[{"assignedToID":"222...","assignmentPercent":50},{"roleID":"111..."}]}
```

The API docs note: *"Updates made to the top level are sparse, updates to a collection or nested object completely replace the existing collection."* Partial collection updates are not supported — always send the full desired collection state.

### DELETE — removing objects

```
DELETE /attask/api/v17.0/task/4c7...
```

By default this is a **soft delete** — the object goes to the Workfront Recycle Bin and can be restored within 30 days. To hard-delete the object and its dependents:

```
DELETE /attask/api/v17.0/task/4c7...?force=true
```

See `11-tips-and-gotchas.md` for soft-delete vs hard-delete behavior.

## The `action=` parameter

Some operations don't fit CRUD. Pass `action=` (in the query string or body) to invoke them. They're typically sent as `PUT` or `GET` against the object URL.

```
PUT /attask/api/v17.0/project/4c7...?action=calculateTimeline
```
Or equivalently as a path segment:
```
PUT /attask/api/v17.0/project/4c7.../calculateTimeline
```

**Actions documented in Adobe's API basics page:**

| Action | Object(s) | What it does |
|---|---|---|
| `calculateTimeline` | Project | Recalculates the project timeline |
| `calculateFinance` | Project | Recalculates financial data |
| `calculateDataExtension` | Most objects | Recalculates custom data |
| `approveApproval` | Approval step | Approves the pending approval |
| `rejectApproval` | Approval step | Rejects the pending approval |
| `recallApproval` | Approval step | Recalls (withdraws) the approval |
| `markViewed` | Work items | Marks the item as viewed by the caller |
| `move` | Task, Issue | Moves to a different project. **For Issue (OPTASK) the wire format + a silent-no-op trap are in § "Moving an Issue (OPTASK) between projects" below.** |
| `generateApiKey` | User | Generates a new API key for a user |
| `getApiKey` | User | Retrieves an existing API key |
| `clearApiKey` | User | Invalidates a user's API key |
| `assignMultiple` | Task, Issue (OPTASK) | Replace team/user/role assignments in one call. See dedicated section below. |
| `bulkCopy` | Task | Duplicate one or more tasks into a project/parent. `taskIDs[], projectID, parentID, options[]` → returns new task IDs. **Preserves source completion metadata (`status`, `percentComplete`, `actualStartDate`, `actualCompletionDate`) when the source is CPL — but resets `assignment.status` to `AA`. The mismatch causes the duplicate to render incorrectly on the doer's Home dashboard.** See § "TASK action catalog and `bulkCopy` quirks" below. |
| `bulkCopy` | TTSK (Template Task) | Duplicate one or more template tasks into a destination template. `templateTaskIDs[], templateID, parentTemplateTaskID, options[]` → returns new TTSK IDs. **The only working API path to create a TTSK with a non-zero `workRequired` / `work`** — direct POST and PUT silently coerce those fields to 0. The copy inherits the donor's `workRequired`, `work`, `roleID`, `categoryID`, and one TASSGN row. Use a subsequent PUT to override the inherited fields. See § "TTSK action catalog and the `bulkCopy` workRequired path" below. |
| `bulkMove` / `move` | Task, TTSK | Relocate task(s) to a different project / parent. TTSK takes `templateTaskIDs[], templateID, parentID, options[]`. |
| `markDone` | Task | Sets the caller's assignment on the task to `DN` (Done). Argument: `status`. The Home dashboard filters DN assignments out. |
| `markNotDone` | Task | Inverse of `markDone`. Argument: `assignmentID`. Flips the named assignment **DN → AD** (not back to AA), so the task reappears on the assignee's Home. See § Assignment lifecycle quirks. |
| `acceptWork` / `unacceptWork` | Task | Caller-scoped accept/decline of the assignment. Argument: `status`. |
| `assign` / `unassign` | Task, Issue | Single-user assign/unassign by `userID`. |
| `convertToProject` | Task | Promote a task into its own project. |
| `convertToTask` | Issue (OPTASK) | Promote an issue into a task. Needs a **raw JSON body** with a nested `task` wrapper; form-encoding fails. See § "`convertToTask` — Issue → Task conversion" below. |

The set of available actions is object-specific. The API Explorer lists available actions per object endpoint. The actions above are the ones explicitly shown in Adobe's documentation OR catalogued empirically from `<obj>/metadata.actions` — not a complete list for all objects.

### Moving an Issue (OPTASK) between projects (empirical, 2026-06-17)

Use the `move` **action** endpoint — NOT a field update. Both of these work:

```bash
# updates=<JSON> form (consistent with other actions)
PUT /attask/api/v17.0/optask/<issueID>/move?apiKey=<key>
  updates={"projectID":"<dest-project-id>"}

# flat query-param form (also works for this action)
PUT /attask/api/v17.0/optask/<issueID>/move?projectID=<dest-project-id>&apiKey=<key>
```

**Silent-no-op trap:** a plain field update — `PUT /attask/api/v17.0/optask/<issueID>` with body `{"projectID":"<dest>"}` — returns **HTTP 200 but does not move the issue** (the `projectID` is unchanged on a follow-up GET). `projectID` is not a writable field on the issue via a direct PUT; only the `move` action relocates it. Verified on a live Workfront preview sandbox, v17.0, 2026-06-17.

The collection form `PUT /attask/api/v17.0/optask?action=move` with `updates={"IDs":[...],"projectID":...}` returns `422 ... action move does not support argument named IDs` — use the per-id `/optask/<id>/move` path instead.

Logging hours against the moved issue uses `opTaskID` on the HOUR object (issues are OPTASK), not `taskID`: `POST /hour {"opTaskID":"<issueID>","hours":...,"entryDate":...,"description":...}`.

### TASK action catalog and `bulkCopy` quirks (empirical, 2026-05-29)

`<task>/metadata.actions` enumerates the full set: `acceptWork`, `approveApproval`, `assign`, `assignMultiple`, `bulkCopy`, `bulkMove`, `calculateDataExtension`, `calculateDataExtensions`, `convertToProject`, `linkExternalObject`, `markDone`, `markNotDone`, `move`, `recallApproval`, `rejectApproval`, `replyToAssignment`, `unacceptWork`, `unassign`, `unassignOccurrences`, `unlinkExternalObject`.

**`bulkCopy` is the canonical task-duplication action.** The misleading `POST /task/<id>/copy` shape (which `metadata.operations` lists) is the Category `copy` situation all over again — it's a UI hook, not a REST surface. Use `bulkCopy` instead.

**Wire format** — same `updates=<JSON>` pattern as `assignMultiple`, with the args as a JSON object inside:

```bash
PUT /attask/api/v17.0/task?action=bulkCopy
  updates={"taskIDs":["<src-id>"],"projectID":"<dest-project-id>"}

# Response: {"data":{"result":["<new-task-id>"]}}
```

Failure modes empirically observed:

| Variant | Result |
|---|---|
| `updates={"taskIDs":[...],"projectID":...}` | ✅ Works |
| `--data-urlencode "taskIDs=<id>" "projectID=<pid>"` (flat form) | ❌ `argument type mismatch` — form decoder can't map flat string into `string[]` |
| `--data-urlencode "taskIDs[]=<id>"` (PHP-style) | ❌ `does not support argument named taskIDs[]` |
| `updates={"taskIDs":["X"]}` JSON value passed bare as `taskIDs=["X"]` | ❌ `argument type mismatch` — has to be inside `updates={…}` |

**`options[]` enum is opaque.** The argument is accepted but every candidate value returns `unknown copy option: <value>`. Tested 17 plausible names (`resetStatus`, `resetActuals`, `copyAsNew`, `descendants`, `notes`, `dependencies`, `predecessors`, `documents`, `assignments`, `customForms`, `customData`, `expenses`, `INHERIT_STATUS`, `RESET_PROGRESS`, `clean`, `resetActualsAndStatus`, `resetCompletionData`) — none accepted. Workfront's option set is internal; there is **no built-in flag to reset completion metadata on copy**.

**Critical behavior: source state determines duplicate cleanliness.**

| Source `status` | Duplicate `status` | Duplicate `percentComplete` | Duplicate `actualStartDate` / `actualCompletionDate` | Duplicate `assignment.status` | Dashboard behavior |
|---|---|---|---|---|---|
| `NEW` | `NEW` ✅ | `0` ✅ | `null` ✅ | `AA` ✅ | Clean — task lands as fresh work |
| `CPL` | `CPL` ❌ | `100` ❌ | copied from source ❌ | `AA` ✅ | **Contradictory.** Assignment is active (so the task isn't filtered off Home) but task itself reads "complete" — UI renders an in-between state that AMs describe as "In Progress" |

Two paths to avoid the CPL-source corruption:

1. **Don't duplicate CPL tasks.** Duplicate before marking the source complete, or duplicate from a NEW template task.
2. **Sanitize the duplicate.** After `bulkCopy` against a CPL source, PUT the new task with `{"status":"NEW","percentComplete":0,"actualStartDate":null,"actualCompletionDate":null}`. Easy to wrap in a Fusion scenario that watches TASK creation events.

### TTSK action catalog and the `bulkCopy` workRequired path (empirical, 2026-06-06)

`<ttsk>/metadata.actions` enumerates four actions: `bulkCopy`, `bulkMove`, `calculateDataExtension`, `move`. `bulkCopy` is the **only working REST path to land a non-zero `workRequired` (Planned Hours) on a TTSK** — direct POST and PUT silently coerce the field to `0`, regardless of `durationType`, `workUnit`, `workRequiredExpression`, or inline-assignment shape.

**Wire format:**

```bash
PUT /attask/api/v17.0/ttsk?action=bulkCopy
  updates={"templateTaskIDs":["<donor-id>"],"templateID":"<dest-template-id>"}

# Response: {"data":{"result":["<new-ttsk-id>"]}}
```

**The copy inherits all of these from the donor:**
- `workRequired` (the whole reason we're using `bulkCopy`)
- `work` (hours form of workRequired)
- `duration`, `durationUnit`, `durationType`
- `roleID`
- `categoryID` (custom form attachment)
- One `TASSGN` row (the donor's primary assignment, with `assignmentPercent` carried)
- Any `TPRED` rows (which now point at a foreign TTSK — almost always wants clearing)

**Subsequent PUTs can override most fields without disturbing `workRequired`:**

```bash
# 1. Plain field updates — name, parent, role, category, duration are all editable
PUT /attask/api/v17.0/ttsk/<new-id>
  name=<your-name>
  parentID=<parent-new-id>
  roleID=                     # empty to clear
  categoryID=
  duration=1.0                # duration IS editable post-copy; workRequired stays put

# 2. Collection updates — assignments, predecessors. MUST be in a separate call:
#    API errors with "Cannot mix 'updates' JSON parameter with non-JSON update parameter 'name'"
PUT /attask/api/v17.0/ttsk/<new-id>
  updates={"assignments":[{"assignedToID":"<userID>","roleID":"<roleID>"}],"predecessors":[]}
```

**Caveats:**

- **Same tenant only.** The donor TTSK must be on the destination tenant — `bulkCopy` doesn't reach across customer instances. For cross-tenant template-task migration, find donors on the *destination* tenant whose `workRequired` + `duration` match what you need, not on the source.
- **`workRequired` post-copy is locked.** Direct PUTs to `workRequired` still no-op. Pick a donor whose `workRequired` matches exactly; you can't tune it after the copy.
- **`duration` IS editable post-copy** (verified: `duration=1.0` PUT on a 5d/600min donor copy → 1d/600min). Useful when no donor has both the right `workRequired` AND the right `duration`.
- **`options[]` enum is opaque** (same as `TASK.bulkCopy`). Tested options all return "unknown copy option"; no built-in flag resets the donor's role/category/assignments. Clear them via subsequent PUTs.

### `markDone` / `markNotDone` and the no-cascade gap

`markDone(status)` sets the caller's assignment on the task to `DN`. `markNotDone(assignmentID)` flips a named assignment off DN.

**Empirical surprise: `markNotDone` lands in `AD`, not back in `AA`.** From a starting state of `assignment.status=DN`, calling `markNotDone` returns `assignment.status=AD`. The Workfront UI still treats AD as "active, on Home" — but if you're reading `assignment.status` programmatically, expect AD rather than AA after an undo.

**Workfront does NOT cascade task-status changes to assignment status.** Reverting `task.status` from CPL to NEW via PUT leaves every previously-DN assignment stuck at DN. The task disappears from those assignees' Home dashboards even though the task is technically active again. To restore Home visibility, you have to call `markNotDone(assignmentID)` for each DN assignment after the revert.

Wire shape mirrors `bulkCopy`:

```bash
# Mark one assignment as not-done
PUT /attask/api/v17.0/task/<task-id>?action=markNotDone
  updates={"assignmentID":"<assignment-id>"}

# Response: {"data":{"result":null}}
```

### `assignMultiple` — assigning users, roles, and teams in one call

Available on `optask` (Issue) and `task`. Takes arrays of team / user / role IDs and **replaces** the current assignments — it is **not additive**. Verified on v17.0 preview, 2026-05: assigning user A, then calling `assignMultiple` with `userIDs=[B]`, leaves only user B (user A is removed).

**Both transport forms work.** Pick based on your client.

**Form-encoded (curl / standard Workfront pattern):**
```
PUT /attask/api/v17.0/optask/{issueID}/assignMultiple?apiKey=<key>
Content-Type: application/x-www-form-urlencoded

updates={"teamIDs":["aabbccdd000000000000000000000001","aabbccdd000000000000000000000002"],"userIDs":[],"roleIDs":[]}
```

**Raw JSON body (Fusion / HTTP module / clients that prefer JSON):**
```
PUT /attask/api/v17.0/optask/{issueID}/assignMultiple?apiKey=<key>
Content-Type: application/json
Authorization: Bearer <token>   (or apiKey= query param)

{
  "teamIDs": ["aabbccdd000000000000000000000001", "aabbccdd000000000000000000000002"],
  "userIDs": [],
  "roleIDs": []
}
```

Both verified on v17.0 preview, 2026-05.

**Gotchas confirmed in testing:**
- **Replaces, does not append.** Pre-fetch current assignments and include the ones you want to keep, or you will silently unassign them.
- Pass action as a **path segment** (`/assignMultiple`); `?action=assignMultiple` also works but path-segment is more common.
- `teamIDs` / `userIDs` / `roleIDs` must be **JSON arrays**, not comma-separated strings, not `teamIDs[]=` query params. Query-param array notation causes a 422 "JSON parsing error."
- Pass empty arrays for unused ID types (`"userIDs": [], "roleIDs": []`) — omitting them has caused silent failures in some instances.
- **OPTASK team-only collapse:** on issues (OPTASK), a body with `teamIDs` populated but `userIDs` and `roleIDs` empty applies only the **first** team — as the issue's primary `teamID` scalar. The rest are silently dropped. To multi-assign teams on an issue, pair each team with a user (parallel `userIDs` of equal length), or use a task instead. See `11-tips-and-gotchas.md`.

**Building this body dynamically in Fusion (confirmed working pattern):**
```
{
  "teamIDs": ["{{join(map(DATA; "ID"); """,""")}}"],
  "userIDs": [],
  "roleIDs": []
}
```
- The separator `""","""` uses Fusion's double-double-quote escaping (`""` = one literal `"`) to produce `","` — joining IDs as `id1","id2`, then the outer `["` and `"]` complete the array.
- Do NOT use `\"` — Fusion does not support backslash escaping inside expressions.
- Do NOT use `char(34)` — not a valid Fusion function.
- Do NOT use `["{{join(map(...); ",")}}"]` — produces one quoted string `["id1,id2"]` instead of `["id1","id2"]`.

### Assigning custom forms (categories) — `assignCategories` action on CTGY

Custom-form (category) assignment actions are hosted on **`CTGY`** (Category), not on the target object. They take the target via `objCode` + `objID` arguments. Working on v17.0; verified 2026-05-15 against a live Workfront sandbox.

```
# Attach one or more forms to an issue (additive)
PUT /attask/api/v17.0/ctgy/assignCategories?apiKey=<key>
Content-Type: application/x-www-form-urlencoded

updates={"objCode":"OPTASK","objID":"<issueID>","categoryIDs":["<ctgyID1>","<ctgyID2>"]}
```

Success returns `{"data":{"result":null}}`. The action is **additive** (unlike `assignMultiple` and unlike a direct `objectCategories` collection PUT). If any of the supplied category IDs is already attached, the entire call rejects with `Categories with the following IDs are already attached: <id>` — there's no partial success. Read the current `objectCategories` collection first and filter out already-attached IDs.

**Mandatory dispatch shape — every other shape fails:**

| Shape | Result |
|---|---|
| `PUT /ctgy/assignCategories` body `updates=<JSON>` | ✅ Works |
| `PUT /ctgy/assignCategories` with form params (`objCode=...&categoryIDs=...`) | ❌ `argument type mismatch` — form decoder can't map flat params into a `string[]` argument |
| `GET /ctgy/assignCategories?...` | ❌ `does not support namedQuery assignCategories (CTGY)` (GET is the namedQuery dispatch path; actions don't live there) |
| `PUT /optask/<id>/assignCategories` | ❌ `does not support action assignCategories (OPTASK)` — the action is on CTGY, not on the target |
| `POST /ctgy/assignCategories` | ❌ `unrecognized URI format: too many parts` (POST routes to create) |

Sibling actions on `CTGY` follow the same shape:

| Action | Args (in `updates=` JSON) | Behavior |
|---|---|---|
| `assignCategory` | `objCode, objID, categoryID` | Additive; same "already attached" error if duplicate |
| `assignCategories` | `objCode, objID, categoryIDs[]` | Additive; rejects whole batch if any duplicate |
| `unassignCategory` | `objCode, objID, categoryID` | Removes one |
| `unassignCategories` | `objCode, objID, categoryIDs[]` | Removes many |
| `getAttachableCategories` | `searchTerm, catObjCode, excludedIDs[], limit` | **Listed in metadata but does not dispatch on v17.0** — returns `does not support action getAttachableCategories (CTGY)` whether GET or PUT. Use `GET /ctgy/search?catObjCode=<OBJCODE>&fields=name,catObjCode` instead. |

**Alternative — full collection replace via `objectCategories`.** When you want to set the exact final set of forms in one call (drop any not in the list, keep any in it), PUT the target object directly with the `objectCategories` collection. This is replace, not additive:

```
PUT /attask/api/v17.0/optask/<issueID>?apiKey=<key>
updates={"objectCategories":[{"categoryID":"<ctgyID1>"},{"categoryID":"<ctgyID2>"}]}
```

The primary form (the `categoryID` scalar on the object) is independent of the `objectCategories` collection — it has its own slot and is updated by setting `categoryID=<ctgyID>` on the object directly.

**General rule this surfaces:** assignment-style actions in Workfront are hosted on the *metadata* object (here, `CTGY`) and routed by `PUT /<metaobj>/<action>` with all arguments serialized into the `updates=<JSON>` parameter. The action does not live on the target object's endpoint. If you see an action in `<obj>/metadata` and want to call it, this is the dispatch shape to try first.

**Verify the dispatchability of each action you use.** Metadata listing does not guarantee dispatch — `getAttachableCategories` is the counterexample. The four assignment actions above work; the discovery action does not. There's no flag in the metadata that distinguishes the two; only attempting the call reveals it.

**`search` is not an `action=` value** — it's a URL path segment appended to the object name:
```
GET /attask/api/v17.0/project/search?...
```

### `convertToTask` — Issue → Task conversion (empirical, client preview sandbox, v18.0, 2026-06-24)

Promotes an Issue (OPTASK) into a Task. The new task's fields go in a nested `task` wrapper alongside the conversion flags.

**Wire format — must be a raw JSON body.** Unlike `assignMultiple`, the nested `task` object does NOT survive form-encoding:

```
PUT /attask/api/v18.0/optask/<issueID>/convertToTask?apiKey=<key>
Content-Type: application/json

{
  "task": { "name": "...", "projectID": "<projID>", "priority": 2 },
  "copyNativeFields": true,
  "copyCategories": true,
  "options": []
}
```
Returns `{"data":{"result":"<newTaskID>"}}` — the new Task's ID.

| Variant | Result |
|---|---|
| Raw JSON body with nested `task` object | ✅ Works |
| Form-encoded `task={...}` (`--data-urlencode`) | ❌ `class java.lang.String cannot be cast to class java.util.Map` — the form decoder hands `task` over as a String |
| Any `fields=` query param on the action | ❌ Validated against the **source OpTask**, so a Task-only field (e.g. `durationType`) aborts the whole call with "does not support field … (OpTask)". GET the returned task ID separately to inspect it. |

**The convert builds the task through an INTERNAL model (`RKTask`) with a restricted field set.** `plannedHours` is rejected outright: `field 'plannedHours' is not available on com.attask.model.RKTask in version INTERNAL`. (`plannedHours` is not a Task API field anywhere — see `04-fields-and-naming` and `10-status-and-enum-codes` § Duration Type.) `name`, `projectID`, `priority` are accepted.

**`copyNativeFields:true` copies the issue's assignment AND its `workRequired` (Planned Hours) onto the new task**, which lands as `durationType:"A"` (Calculated Assignment). The original issue is consumed by the convert (404 afterward) **unless you pass `options:["preserveIssue"]`** — see § "Preserving the source issue" below.

**To pin Planned Hours on the converted task, do a follow-up PUT** — you cannot set effort in the convert body, and under the default `"A"` duration type a direct `workRequired` write is ignored (effort is calculated from the assignment). Flip to Effort Driven:

```
PUT /attask/api/v18.0/task/<newTaskID>?apiKey=<key>
Content-Type: application/json

{ "durationType": "D", "workRequired": 0 }
```
Verified: `workRequired` holds at `0` (and the copied assignment's `work` → 0) only under `durationType:"D"`. Plain `workRequired=0` under `"A"` stays at the copied value. See `10-status-and-enum-codes` § Duration Type.

### Preserving the source issue (`options` array) — client HAR capture, 2026-07-13

By default (`options:[]`) the convert **consumes** the issue (404 afterward). To KEEP the original issue/request and tie its resolution to the new task, pass preservation tokens in `options`:

```
{ "task": { "name": "...", "projectID": "<projID>" },
  "copyNativeFields": true, "copyCategories": true,
  "options": ["preserveIssue"] }
```

The convert dialog's three toggles (from `GET /internal/qs/convertToTask/metaData?opTaskID=<id>`):

| Option token | UI label | Effect |
|---|---|---|
| `preserveIssue` | "Keep the original request and tie its resolution to this task" | Issue survives (no 404); becomes the new task's *resolving object* |
| `preserveCompletionDate` | "Keep the planned completion date of the request" | Task inherits the issue's planned completion date |
| `preservePrimaryContact` | "Allow \<requestor\> to have access to this task" | Grants the issue's primary contact access to the new task |

`preserveIssue` is confirmed in the **public REST** action's `options` array (Adobe Experience League community thread 578794; the client's UI convert also POSTs `preserveIssue=on` to `/internal/issue/convertToTask`). `preserveCompletionDate` / `preservePrimaryContact` are the UI-dialog field names (the internal endpoint submits `preserveCompletionDate=on`); verify those two against the public action before relying on them.

## Method tunneling (`method=` parameter)

If your HTTP client or infrastructure doesn't support all four verbs, you can tunnel the intended method as a query parameter on a `GET` or `POST`:

```
GET /attask/api/v17.0/project?id=4c7...&method=delete&sessionID=abc123
```

```
PUT /attask/api/v17.0/proj
  ?updates=[{"name":"Test_Project_1"},{"name":"Test_Project_2"}]
  &method=POST
  &apiKey=123ab...
```

Tunneling is mainly needed for bulk operations where the HTTP verb semantics need to differ from what the transport layer allows.

## Bulk operations

Send an array to `updates` to create or modify multiple objects in one call. Max 100 objects per bulk call.

**Bulk create (using method tunneling):**
```
PUT /attask/api/v17.0/proj
  ?updates=[{"name":"Project A"},{"name":"Project B"}]
  &method=POST
  &apiKey=<key>
```

**Bulk update:**
```
PUT /attask/api/v17.0/proj
  ?updates=[{"ID":"abc...","name":"Project A Updated"},{"ID":"def...","name":"Project B Updated"}]
  &apiKey=<key>
```

Bulk operations are atomic per item — the response is `success: true` or an error per item. A failure on one item does not roll back the others.

## Request body: form-encoded vs JSON

Workfront accepts two request body formats, and they can be mixed (some fields in query string, complex data in body):

| Format | When to use |
|---|---|
| `application/x-www-form-urlencoded` | Simple field values on POST/PUT |
| `updates=<JSON string>` form field | Nested objects, collections, complex updates |

There is no native `application/json` body for the core REST API — JSON must be passed as the string value of the `updates` parameter, not as a raw JSON body.

For filter-heavy GET requests that exceed the 8,892-byte URL limit, post as form-encoded to the `/search` endpoint instead:
```
POST /attask/api/v17.0/task/search
Content-Type: application/x-www-form-urlencoded

status=CUR&status_Mod=eq&EXISTS:1:$$OBJCODE=ASSGN&EXISTS:1:taskID=FIELD:ID&...
```

## Idempotency

| Method | Idempotent? |
|---|---|
| `GET` | Yes — safe to retry |
| `PUT` | Yes — same update applied twice produces the same state |
| `DELETE` | Yes — deleting an already-deleted object returns an error but has no further effect |
| `POST` (create) | No — retrying creates duplicate objects; use a unique `name` or check-then-create pattern |
| Bulk `POST` | No — same caveat |

Always check for existence before creating if your code might retry on transient errors.

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/api-general-information/api-basics` | All four HTTP methods, action= examples, method= tunneling, updates= JSON format, bulk operations, copy via copySourceID, force=true on DELETE, count endpoint, named queries, report endpoint |
