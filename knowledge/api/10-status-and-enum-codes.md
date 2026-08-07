# 10 — Status and Enum Codes

Workfront returns and accepts short codes (not display names) for status, priority, severity, and similar enumerated fields. Hard-code the codes — never the display names.

## Status codes (Project, Task, Issue)

| Code | Display name |
|---|---|
| `INP` | In Progress |
| `CPL` | Complete |
| `CUR` | Current |
| `PLN` | Planning |
| `DED` | Dead |
| `APR` | Approved (project) |
| `REJ` | Rejected |
| `ONH` | On Hold (project) |
| `REQ` | Requested (project) |
| `IDA` | Idea (project) |

> **Project "Approved" is `APR`, not `APV`.** Verified on a live v17.0 tenant (2026-06-28): filtering `project.status=APV` returns `Invalid custom enum value(s) for field 'Status': ['APV']`, while `APR` is accepted. `APV` is the approval-process *action* code (see "Approval-process action codes" below) — do not use it as a project status. Some Adobe/MCP reference docs are correct here (`APR`); this file previously was not.

### Pending-approval suffix

Append `:A` to a status code to mean "pending approval to enter this status."

| Code | Display name |
|---|---|
| `CPL:A` | Pending Approval (Complete) |
| `CUR:A` | Pending Approval (Current) |

### Custom statuses

Organizations can add custom statuses with their own codes. Verify the codes in your instance via **Setup → Project Preferences → Statuses** (and the equivalent for Task and Issue). Custom codes are typically uppercase 3-letter strings following the same convention.

### Assignment statuses

Assignment status (`ASSGN` records) uses a different small enumeration. Documented values:

| Code | Display name | Notes |
|---|---|---|
| `NEW` | New | |
| `WRK` | Working On It | |
| `RDY` | Ready | |
| `DN` | Done | Set by `markDone(status)` or by Workfront when `task.status` transitions to CPL. Home dashboard filters DN assignments out. |
| `AA` | Assignment Accepted / Active | Default state when a new assignment is created. |
| `AD` | (semantic ambiguous — see below) | |

`AA`, `AD`, and `DN` were empirically observed across 2,000 assignments on a live v17.0 sandbox (re-verified 2026-05-29).

**Re-interpretation of `AD` (2026-05-29):** the "Assignment Declined" label that Adobe's documentation suggests is **incomplete at best, misleading at worst** based on empirical behavior. On a Client D sandbox, calling `markNotDone(assignmentID)` against a `DN` assignment flips its status to **`AD`**, not back to `AA`. The Workfront UI continues to treat `AD` as an active, on-Home-dashboard assignment (the doer sees the task return). So `AD` is at minimum a polymorphic state — it can mean either "declined" (if reached by an assignee rejecting work) or "marked-done-then-undone" (if reached by `markNotDone`). When reading `assignment.status` programmatically, do not assume `AD` means "declined"; verify with the upstream transition or with `editedByID` on the change.

### Discovering the status enum in your instance

**v17.0 does NOT expose a top-level Status object via the REST API.** Endpoints like `/stat/search`, `/status/search`, `/STAT/search`, `/sttsv/search` all return `"Unknown object type"`. Empirically verified 2026-05.

To discover what status values are actually in use for any object type, scan existing records:

```bash
curl -sS --compressed \
  "https://<host>/attask/api/v17.0/assignment/search?fields=status&\$\$LIMIT=2000" \
  -H "apiKey: <KEY>" \
  | jq '[.data[].status] | unique | sort'
```

Replace `assignment` with `project`, `task`, `optask`, etc. for other object types. Then cross-reference codes against the UI at **Setup → System Preferences → Statuses** (or **Setup → Project Preferences → Statuses** for project-status overrides).

### Object-metadata enum is the base enum only — custom statuses are NOT surfaced

`GET /<objcode>/metadata` returns `fields.status.possibleValues` for each object — but only the BASE enum from `com.attask.common.constants.<Type>StatusEnum`. Custom statuses added by the org (system-level or group-level) do NOT appear there.

Empirical example (a preview sandbox tenant, v17.0, 2026-06-02): the tenant has a custom Issue status `LAP`. `GET /optask/metadata` returns only the 10 base values (`NEW`, `INP`, `AWF`, `ONH`, `ROP`, `CND`, `WTR`, `RLV`, `VCP`, `CLS`). `LAP` is absent. So metadata is a starting point, never the source of truth for custom statuses.

### Verifying a custom status exists (write round-trip)

`GET /optask/search?status=<CODE>` silently returns `data: []` whether the code is real-but-unused or completely bogus — the filter does not validate the enum. An empty array is NOT proof the code is invalid (see also `11-tips-and-gotchas`).

The canonical existence check is a write round-trip on a throwaway record:

```bash
# 1. Create a throwaway issue (any hidden project works)
CREATE_RESPONSE=$(./wf-curl.sh '/attask/api/v17.0/optask' -X POST \
  --data-urlencode 'updates={"name":"[wf-api-verify] status round-trip","projectID":"<some_project_id>"}')
TEST_ID=$(echo "$CREATE_RESPONSE" | jq -r '.data.ID')

# 2. PUT the status. If accepted, the response echoes status: "<CODE>".
./wf-curl.sh "/attask/api/v17.0/optask/$TEST_ID" -X PUT \
  --data-urlencode 'updates={"status":"<CODE>"}'

# 3. GET to confirm persistence
./wf-curl.sh "/attask/api/v17.0/optask/$TEST_ID?fields=ID,status"

# 4. Clean up
./wf-curl.sh "/attask/api/v17.0/optask/$TEST_ID?force=true" -X DELETE
```

If the code exists, step 2 returns the OPTASK with `"status": "<CODE>"`. If it doesn't, step 2 errors with an "invalid status" message.

This is the only API-side proof of custom status existence in v17 short of finding a record already in that state. Statuses themselves are not a top-level REST object — `/stat`, `/stsch`, `/sttsch`, and `/groupStatus` all return `Unknown object type`. Status creation/editing is UI-only via **Setup → System → Statuses**.

## Priority codes

Project and Task `priority` is an integer (0–4 by default, though admins can customize):

| Value | Display name |
|---|---|
| `0` | None |
| `1` | Low |
| `2` | Normal |
| `3` | High |
| `4` | Urgent |

Filter on integer values, not display names:

```
?priority=3
&priority_Mod=gte
```

Custom priority schemes can shift these — confirm in your instance.

## Severity codes (Issue)

Issues have a `severity` field that follows the same integer-with-custom-overrides pattern as priority. Verify against your instance for the exact mapping; the API Explorer or Setup → Issue Preferences will show the configured values.

## Condition codes

Project / Task `condition`:

| Code | Display name |
|---|---|
| `ON` | On Target |
| `AR` | At Risk |
| `IT` | In Trouble |

These are computed by Workfront based on schedule, not directly settable.

> **The stored code for On Target is `ON`, not `OT`.** Verified on a live v17.0 tenant (2026-06-28): a 200-project sample carried only `ON` / `AR` / `IT`. Some Adobe/MCP reference docs erroneously list `OT` for On Target — ignore that; filter on `ON`.

## Duration Type codes (Task)

Task `durationType` controls whether effort or duration is the input. **Codes verified on client-c.preview v18.0, 2026-06-24:**

| Code | Display name | Effort (`workRequired`) behavior |
|---|---|---|
| `A` | Calculated Assignment | **Default** for new/converted tasks. `workRequired` is *calculated* from the assignment — a direct PUT of `workRequired` is silently ignored. |
| `D` | Effort Driven | `workRequired` is the **input**; duration is calculated from it. Use this to set or pin Planned Hours. |
| `S` | Simple | Duration is a manual input, independent of effort — BUT POSTing `durationType:"S"` with a `duration` and no `workRequired` reads back **`duration:0`** (a planned-completion date collapses onto the start). To pin an explicit multi-day duration on a task, **omit `durationType`** (defaults to `A`) or use `D`. Verified on a sandbox tenant v15.0, 2026-07-02. |

(The UI also offers "Calculated Work"; that code was not verified — confirm via a GET on a task of that type before hardcoding.)

**Two effort gotchas, both verified 2026-06-24:**

- **`plannedHours` is NOT a Task/Issue API field.** Both GET and PUT return `APIModel V18_0 does not support field plannedHours (Task)` (same on v17.0). The writable effort field is **`workRequired`, in minutes** (480 = 8h); `plannedHours` exists only in reports / text mode. See `04-fields-and-naming`.
- **Effort can't live on a task with no assignments.** Setting `workRequired` on an unassigned task reads back `0` regardless of duration type — there's no assignment to hold the hours. Assign first, then set effort.

<!-- UNVERIFIED -->
> **Community-reported exception to the second gotcha — a flagged contradiction, not yet arbitrated.** An Adobe support response relayed in an Experience League Fusion thread (best answer, retested by the asker) reports that on **TASK** (not TTSK), setting `isWorkRequiredLocked: true` in the same create call makes the supplied `work` value persist on a Simple-duration, Fixed-Dates, *unassigned* task — the lock reportedly stops "project dates, task constraints, and other task values" from recomputing it away. What IS confirmed: the field exists on TASK in v17.0. Verified 2026-08-07 on a sandbox tenant.workfront.com (sandbox), v17.0: `GET /TASK/metadata` lists `isWorkRequiredLocked` (alongside `isDurationLocked`, `work`, `workRequired`). The behavioral claim requires a write to confirm; until a sandbox test settles it, the "assign first, then set effort" guidance above stands. Also unconfirmed: the thread's instruction to map `work` (hours) instead of `workRequired` (minutes) may just reflect the asker's own units mix-up rather than being a necessary part of the fix. The separately documented TTSK finding is unaffected — `isWorkRequiredLocked=true` was among the forms that failed there, but only on TTSK (`11-tips-and-gotchas.md` § "Template task `workRequired` is set via `bulkCopy`").

## Approval-process action codes

Approval steps return action codes like `APV` (approved), `REJ` (rejected), and various pending states. The exact set depends on the approval process configuration — verify per endpoint.

## Why codes, not display names?

- **Codes are stable across language / locale.** Display names are localized; codes are not.
- **Codes are stable across UI customizations.** An admin can rename "Complete" to "Done" in the UI without changing the underlying code `CPL`.
- **Filters and reports compare codes.** A filter `status=Complete` won't match anything — the stored value is `CPL`.

## Extracting labels anyway: `statusLabel` on the unversioned `api-unsupported` path

The guidance above stands — codes are what you filter, store, and hardcode on. But for one-off extraction (a label column in a data pull, an audit sheet), the unversioned `api-unsupported` path exposes a derived `statusLabel` field that the versioned APIModel withholds:

```
GET /attask/api-unsupported/PROJ/search?fields=ID,name,status,statusLabel&$$LIMIT=3
→ {"name": "...", "status": "CUR", "statusLabel": "Current"}
```

The same request on the versioned path fails — negative control:

```
GET /attask/api/v17.0/PROJ/search?fields=ID,name,status,statusLabel&$$LIMIT=2
→ {"error":{"message":"APIModel V17_0 does not support field statusLabel (Project)"}}
```

- **Works on TASK and OPTASK too** (`CPL → "Complete"`, `NEW → "New"`).
- **Resolves tenant-configured labels, not just the base enum.** A 100-project sample returned the distinct pairs `('AAM','Queue')`, `('CUR','Current')`, `('PLN','Planning')` — `AAM → "Queue"` is not a base-enum display name, so unlike `/metadata` (base-enum-only blind spot above), `statusLabel` reflects the tenant's configured label.
- **Unversioned = extraction-only.** `api-unsupported` carries no version segment and the same caveat this repo applies to `api-internal`: subject to change without notice, do not use in production. For durable code, keep resolving labels client-side from the code tables above.
- **Locale sensitivity NOT tested** (single-locale tenant). Do not assume the returned label is stable across user locales — locale drift is the very reason the codes-not-labels rule exists.

Verified 2026-08-07 on a sandbox tenant.workfront.com (sandbox), v17.0: the `api-unsupported` PROJ/TASK/OPTASK searches above (3/3, 1/1, 1/1 rows carrying `statusLabel`), the v17.0 negative control error verbatim, and the 100-project distinct-pair sample including `('AAM','Queue')`.

## Verifying codes in your instance

For any enumerated field:

1. The API Explorer's data type for the field tells you it's an enum.
2. The Workfront UI's setup area for that object (e.g., **Setup → Project Preferences → Statuses**) lists the codes alongside their display names.
3. A quick GET against an example record shows the actual value — `"status": "INP"` tells you the code is `INP` regardless of how it's labeled in the UI.

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-23/how-to-get-full-project-status-label-via-rest-api-251487` | `statusLabel` via the unversioned `api-unsupported` path — best answer by KellieGardner, 2026-07-07 |
| `https://experienceleaguecommunities.adobe.com/adobe-workfront-fusion-24/creating-tasks-through-fusion-with-planned-hours-and-no-assignment-251651` | `isWorkRequiredLocked` at create time reported to persist work on unassigned TASKs (unverified contradiction) — best answer by CamiD, 2026-07-14 |
