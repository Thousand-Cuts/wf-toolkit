# 08 — Related Objects and Collections

The Workfront API can return related data inline with a request, so you don't have to make N+1 calls for related records. This is done through the `fields=` parameter — the same parameter that selects which fields come back, but with relationship paths instead of just field names.

This is the API equivalent of text-mode `nested(collectionName).lists` collections, but with more flexibility: you can return both relation fields AND fields on the related records in one call.

## Returning fields on a single related object

Use a colon-separated path. The relation name comes first, then the field on the relation.

```
GET /attask/api/v<version>/task/<taskID>
  ?fields=name,status,project:name,project:portfolio:name,assignedTo:name
```

Each colon means "step into this relation." There's no syntactic depth cap in the path itself — though performance and response size degrade as you fetch wider trees.

Result shape (illustrative):

```json
{
  "data": {
    "name": "Wire up auth",
    "status": "INP",
    "project": {
      "name": "Q3 Platform Work",
      "portfolio": {
        "name": "Engineering Initiatives"
      }
    },
    "assignedTo": {
      "name": "Jane Admin"
    }
  }
}
```

## Returning fields on a collection (one-to-many)

Use the collection name as the path segment. The response contains an array under that name.

```
GET /attask/api/v<version>/project/<projectID>
  ?fields=name,tasks:name,tasks:status,tasks:percentComplete
```

Result shape:

```json
{
  "data": {
    "name": "Q3 Platform Work",
    "tasks": [
      { "name": "Wire up auth", "status": "INP", "percentComplete": 40 },
      { "name": "Write API docs", "status": "PLN", "percentComplete": 0 }
    ]
  }
}
```

## Nested collections

You can chain into collections inside collections:

```
GET /attask/api/v<version>/project/<projectID>
  ?fields=tasks:name,tasks:assignments:assignedTo:name,tasks:assignments:assignedTo:emailAddr
```

This returns each task and each of its assignments with the assignee's name and email.

Watch the response size — a 200-task project with 4 assignments each pulls 800 assignment rows and 800 user objects.

## Common collection names

These match what's in text-mode collections (see text-mode file `08-collections.md`). Verify in the API Explorer per object.

### On Project
- `tasks`
- `assignments` (where applicable)
- `documents`
- `projectUsers`
- `milestones`
- `issues`
- `roles`

> **`documentFolders` does NOT expand reliably.** `fields=documentFolders:...` on `/project/<id>` returns 422 with a gzip-corrupted body. Query `/docfdr/search?projectID=<id>` directly instead — see `11-tips-and-gotchas.md` ("Document folders: don't expand, invert the query").

### On Task
- `assignments`
- `predecessors`
- `documents`

### On User
- `roles`
- `teams`

### On Issue / OpTask
- `assignments`
- `documents`

## Custom forms and custom field collections

Custom fields are accessed via the `DE:` prefix on the parent object's field list, not as a collection. You don't iterate them — you list them explicitly.

```
?fields=name,DE:Region,DE:Vendor Name,DE:Approval Status
```

To pull every custom field value on an object in one call, use `fields=parameterValues` (also accepts `parameterValues:*`). The response contains a `parameterValues` object keyed by `DE:<field name>`. `fields=DE:*` does **NOT** work — the API returns `"no such field: '*'"`. Empirically verified on v17.0, 2026-05. See `04-fields-and-naming.md` for an example response shape.

## When to use related-field expansion vs separate calls

**Use `fields=` expansion when:**
- You know upfront which related fields you need.
- The result set is bounded (one task, a handful of related records each).
- Latency matters and you'd otherwise make a chain of dependent calls.

**Make separate calls when:**
- You don't know what related IDs you'll need until you've seen the first response.
- The collection is unbounded or very wide (e.g., every assignment across every task in a 5000-task project — better to paginate the child object directly).
- You need filters on the related object that go beyond what relation expansion supports.

## Comparison to text-mode collections

| Text mode | API |
|---|---|
| `listmethod=nested(tasks).lists` | `fields=tasks:<fieldlist>` |
| `valuefield=name` inside the collection | The field follows the colon in `tasks:name` |
| `listdelimiter` joins items into one cell | API returns a JSON array; the caller controls formatting |
| Cannot sort or filter the collection | API also doesn't filter inside expansion — fetch the collection separately if you need filters on it |
| Single column per collection | A response can include many expanded relations |

The biggest difference: text-mode collections produce one display string per record; API expansion produces structured data. The API is strictly more flexible — you can always join or filter the data on the consumer side.

## Multi-form attachments via `ObjectCategory` (OBJCAT)

A single Workfront record (`OPTASK`, `PROJ`, `TASK`, etc.) can have **multiple custom forms attached** at once. The same is true of queue topics. The relationship is held in the `ObjectCategory` join table (objCode `OBJCAT`), NOT in the record's primary `categoryID` field or the topic's `defaultCategoryID`.

**Why this matters:** `categoryID` on a record is the *primary* form only. Reading just that field will under-report which custom-form fields the record actually has access to. The same gap applies to `QUET.defaultCategoryID` — that's the form auto-attached at request creation; additional forms attached by the queue topic via the Edit Queue Topic UI's "Add custom form" arrangement section live as OBJCAT join rows referencing the topic.

**Consequence for `DE:` accessors:** `DE:<field name>` reads across all attached forms regardless of which one the field "lives" on. A Fusion scenario or report can pull a triage-form field from a record whose `categoryID` points at the customer-facing request form, as long as the triage form is also attached. The implication for audit work: never conclude "field F is not on form" by checking only the record's primary `categoryID`. Enumerate OBJCAT first.

**Discovery query — "what forms are attached to record R?":**

```bash
GET /attask/api/v17.0/objectcategory/search?objID=<recordID>&fields=ID,objObjCode,categoryID,category:name
```

Returns one row per attached form. Example response from a real request-queue issue:

```json
{"data": [
  {"ID":"...","objObjCode":"OPTASK","categoryID":"69fa28a100056f842e48bcaa67671cfd","category":{"name":"3. LP - Marketing Piece Creation - Acute/Medical"}},
  {"ID":"...","objObjCode":"OPTASK","categoryID":"69fb5660000648f5f08c526fedd7f3fc","category":{"name":"0. Internal/Triage"}},
  {"ID":"...","objObjCode":"OPTASK","categoryID":"69fb574c00046f01dcad1d8ff2b34531","category":{"name":"0. Asset Calculations - Admin Only"}}
]}
```

**Endpoint name:** `/objectcategory` is the canonical path. The shorter `/objcat` alias also works in v17.0. Other plausible-sounding aliases (`/objectctgy`, `/objctg`, `/objctgy`, `/oc`) all return *"Unknown object type."*

**Cannot be POSTed/PUT directly via the top-level endpoint** — OBJCAT is a secondary object. To attach a new form to a queue topic or to manage per-record form attachments, the supported path is the in-product UI (Setup → Queues → Edit Queue Topic → "Add custom form") or, for records, the form-attach API on the parent (no v17 REST path verified). Reads via `/objectcategory/search` work fine.

**Symptoms of having missed OBJCAT in an audit:**
- "The field exists tenant-wide but isn't attached to <form>" — true at the `CategoryParameter` level, but the field may still be reachable on the record via a sibling form attached via OBJCAT.
- "DE:X returns null even though the form has the field" — the form may not be attached to *this* record (check `objID` on the join table) even though it's the queue topic's default.
- "I need to add an internal-only field to a customer-facing form" — wrong frame. Add the field to an internal-prefix sibling form (a convention seen in the field: `0.<name>`) and attach that sibling form to the topic via OBJCAT. Customer never sees it; AE / triager fills it during workflow.

Source: empirical discovery 2026-06-08 against a preview sandbox tenant v17.0. Originally surfaced when an audit concluded a shared-service field was "missing from the request form" — it was on a sibling triage form auto-attached to every request via the queue topic's OBJCAT rows.
