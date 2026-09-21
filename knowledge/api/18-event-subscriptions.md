# 18 — Event Subscriptions

Workfront's native outbound webhook. You register a subscription against an objCode and an event
type, Workfront POSTs a payload to your endpoint when a matching change is logged, typically in
under a second and normally within five.

This is a separate service from the REST API, on a separate base path, with separate auth and its
own versioning. Nothing in `01-api-fundamentals.md` about `/attask/api/v22.0/` applies here.

## When to reach for this instead of Fusion

Fusion's `Watch Events` module is built on this service: it creates an event subscription for you
and consumes the payload. That makes the choice a question of who owns the plumbing.

| Use event subscriptions directly | Use Fusion `Watch Events` |
|---|---|
| The consumer is a system the client already runs and can host an endpoint on. | There is no endpoint, or the consumer is another SaaS Fusion already connects to. |
| You need the raw `oldState`/`newState` pair and will do your own diffing. | You want mapped bundles and a visual chain. |
| Volume is high enough that per-operation Fusion billing matters. | Volume is modest and operations are cheap. |
| The client has infrastructure people who will own retries, 2xx-within-5s and the IP allowlist. | Nobody wants to own an endpoint's uptime. |

Two consequences of the shared foundation are worth saying out loud in a design conversation:

- **A Fusion `Watch Events` webhook *is* an event subscription.** Editing its filter in Fusion
  deletes and recreates the subscription on the Workfront side, which is why history is lost and
  events can double or drop during the swap. That behaviour is documented in
  `../fusion/00-rubric-and-workflow.md`; this file explains why it happens.
- **Subscriptions do not travel between environments.** They are not Workfront data and are not
  copied by a sandbox refresh. A subscription made in Preview stays in Preview. Every promotion
  recreates them.

## Access and authentication

- The calling user needs a **System Administrator** access level. There is no lesser grant.
- Auth is the **`sessionID` header**, not an API key and not an OAuth bearer token. See
  `02-authentication.md` for obtaining a `sessionID`.
- `403` means the user behind the `sessionID` is not an administrator. `401` means the `sessionID`
  was empty or invalid. The distinction is reliable and worth reading before you start debugging
  the payload.

## Endpoints

Base path, note that it is **not** under `/attask/api`:

```
https://<domain>.my.workfront.com/attask/eventsubscription/api/v1/subscriptions
```

| Operation | Method | Path | Notes |
|---|---|---|---|
| Create | POST | `/subscriptions` | `201` on success. The `Location` response header carries the new subscription's URI. Anything other than `201` means nothing was created. |
| List | GET | `/subscriptions` | `page` (default 1) and `limit` (default 100, max 1000). Response carries `page_count` and `total_count`. |
| Read one | GET | `/subscriptions/{id}` | |
| Delete | DELETE | `/subscriptions/{id}` | |
| Change version, one | PUT | `/subscriptions/{id}/version` | Body `{"version": "v2"}` |
| Change version, many | PUT | `/subscriptions/version` | By list of IDs, or a flag for all of the customer's subscriptions. |

`409 Conflict` on create means the subscription is a duplicate. Workfront refuses to create two
identical subscriptions, and "identical" means every field matches; changing any one field makes it
a distinct subscription.

## The subscription resource

| Field | Required | Notes |
|---|---|---|
| `objCode` | yes | See the table below. |
| `eventType` | yes | `CREATE`, `UPDATE` or `DELETE`. One per subscription. |
| `url` | yes | Where the POST goes. Validated on create; a bad URL is the usual `400`. |
| `authToken` | on create | The OAuth2 bearer token Workfront presents to *your* endpoint. |
| `objId` | no | Restricts to one record. Omit it and you get every record of that type. |
| `filters` | no | See § Filtering. |

**`authToken` is write-only.** The create response omits it entirely, and every later response masks
it to the last four characters (`****1234`), or fully if it is eight characters or shorter. Keep
your own copy at the moment you send it. There is no way to read it back and no way to rotate it in
place: changing it means creating a new subscription.

Read responses also carry a `subscription_url` block with `successes`, `failures`, `disabled_at` and
`frozen_at`. That is the first thing to look at when a client reports missing events, and it is the
only health signal the service exposes.

## Supported objects

38 objects. The objCode casing is inconsistent and it matters, because these are the literal strings
the service accepts:

**Conventional uppercase objCodes** (as in `03-object-codes.md`): `ASSGN` Assignment, `BOOKNG`
Booking, `CMPY` Company, `PARAM` Custom Field, `CTGY` Custom Form, `PTLTAB` Dashboard, `DOCU`
Document, `DOCV` Document Version, `EXPNS` Expense, `FIELD` Field, `HOUR` Hour, `OPTASK` Issue,
`NLBRCY` Non-Labor Category, `NLBR` Non-Labor Resource, `NOTE` Note, `PORT` Portfolio, `PRGM`
Program, `PROJ` Project, `PRFAPL` Proof Approval, `PTLSEC` Report, `STAFFP` Staffing Plan, `SPVAL`
Staffing Plan Parameter Value, `STAFFR` Staffing Plan Resource, `SPAVAL` Staffing Plan Resource
Attribute Value, `SAVSET` Staffing Plan Resource Attribute Value Set, `SRPVAL` Staffing Plan Resource
Parameter Value, `TASK` Task, `TEAMOB` Team, `TEAMMB` Team Member, `TMPL` Template, `TSHET`
Timesheet, `USER` User.

**Lowercase and snake_case, the approvals family:** `approval`, `approval_stage`,
`approval_stage_participant`.

**Planning objects, uppercase words:** `RECORD`, `RECORD_TYPE`, `WORKSPACE`.

Note `TEAMOB` for Team, not `TEAM`, and `PTLSEC` for Report. Both differ from what a consultant
reaching for the REST objCode table would guess.

## Filtering

Filters cut delivery volume, which is the single most effective thing you can do for an endpoint
that is struggling. A filter is an object in the `filters` array:

```json
{
  "objCode": "TASK",
  "eventType": "UPDATE",
  "authToken": "token",
  "url": "https://example.com/api/endpoint/UpdatedTasks",
  "filters": [
    { "fieldName": "status", "fieldValue": "CUR", "comparison": "eq", "state": "newState" }
  ]
}
```

| Key | Meaning |
|---|---|
| `fieldName` | The payload field. Nested fields are addressed by name, see below. |
| `fieldValue` | The value to compare. Case-sensitive. Ignored entirely by `changed`. |
| `comparison` | `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`, `containsOnly`, `notContains`, `changed`. |
| `state` | `newState` or `oldState`. `oldState` is not available on `CREATE`. |

**Rules that catch people out.**

- **Multiple filters are ANDed.** There is no OR. The documented substitute is several subscriptions
  pointing at the same URL, which is allowed as long as they differ in at least one field.
- **Filters cannot be edited.** Changing a filter means deleting the subscription and creating a new
  one. This is the same constraint Fusion surfaces when you edit a `Watch Events` module.
- **A malformed filter fails silently.** Bad syntax, or a `fieldName` that matches nothing in the
  payload, returns no validation error. The subscription is created and simply never fires. When a
  client says "the subscription does nothing", suspect the filter before the endpoint.
- **These fields cannot be filtered at all:** `DOCU.groups`, `RECORD.data`, `RECORD_TYPE.data`,
  `RECORD_TYPE.fields`.

**Nested fields** are addressed by the parent field name with an object `fieldValue`. To match
`newState.data.customField1 == "myValue"` on a Planning record:

```json
{ "fieldName": "data", "fieldValue": { "customField1": "myValue" },
  "comparison": "eq", "state": "newState" }
```

**Arrays of objects** (`tags`, for instance) match partially with `contains` / `notContains`:
`fieldValue` needs only the keys you care about, and the filter passes if any element matches those
keys. Other fields on the element are ignored.

```json
{ "fieldName": "tags", "fieldValue": { "objID": "6229be410016986cfc6eb4b37c618a17" },
  "comparison": "contains", "state": "newState" }
```

`changed` fires when `fieldName` differs between `oldState` and `newState`, and only then. Updating
any other field on the record produces no delivery. This is the cheapest way to watch one field.

## Versioning

Event subscription versioning is **its own version number, independent of the REST API version.**
Adobe says so explicitly: v2 is a change to the event subscription functionality, not to the API.
Do not reason about it from the `v22.0` in a REST path, and do not read
`14-api-version-drift.md` § Event Subscriptions v2 as meaning "arrived with API v21" in any
stronger sense than "was announced alongside it".

Timeline: all subscriptions created after the 25.2 release (2025-04-10) are v2, and **all remaining
v1 subscriptions were migrated to v2 on 2026-01-15**. v1 is gone. Any client integration still
written to v1 expectations has been broken since that date, which makes it worth checking on a tenant
whose integrations predate 2025.

What changed in v2, in the order it is likely to bite:

- **Multi-select fields always deliver as arrays.** v1 collapsed a single-value multi-select to a
  bare string; v2 sends `["oneValue"]`. Any consumer, Fusion scenarios included, must handle the
  array shape. A v1 filter that compared against the bare string needs recreating against the array.
- **Calculated fields now arrive on CREATE.** When an object is created from a template carrying a
  custom form with calculated fields, v1 sent a CREATE and then an UPDATE with the calculated
  values. v2 sends one CREATE containing them. An integration that listened for that follow-up
  UPDATE now waits forever, and the fix is a CREATE subscription.
- **Spurious null-to-value updates are gone.** `ASSGN.projectID/taskID/opTaskID/customerID` and
  `DOCU.referenceObjID` used to report a change from `null` on unrelated updates. They now report
  only real changes, so a filter on those fields fires less often, correctly.
- **`DOCV` proof fields arrive once.** `proofDecision`, `proofName` and `proofProgress` used to
  generate two UPDATE events, the first without the fields. Now one event carries everything.
- **`DOCU` DELETE carries `groups`** in the before state instead of an empty array.

A version change delivers **duplicate events for five minutes**, one per version, deliberately, so
nothing is missed across the switch. Consumers must be idempotent through that window.

## Delivery requirements

Your endpoint must:

- Accept **HTTP POST**. Every delivery, including validation messages, is a POST.
- Return a **2xx within five seconds**. Anything else is treated as a failed delivery and enters the
  retry policy. For work that takes longer, persist the message, return 200 immediately, and process
  asynchronously.
- Tolerate **duplicates and out-of-order arrival**. Order by the `eventTime` metadata field, which
  carries nanoseconds and epoch seconds.

Payloads carry `oldState` and `newState` for the record, plus `eventTime`.

**Messages over 1 MB are not delivered.** A large record with many custom fields can exceed this,
and the failure is silent from the client's side.

**The sending IPs must be allowlisted** on the client's firewall. Adobe publishes a fixed set:

- Europe: `52.30.133.50`, `52.208.159.124`, `54.220.93.204`, `52.17.130.201`, `34.254.76.122`,
  `34.252.250.191`
- Everywhere else: `54.244.142.219`, `44.241.82.96`, `52.36.154.34`, `34.211.224.9`, `54.218.48.56`,
  `52.39.217.230`

Verify these against Adobe's page before handing them to a network team; an IP list is exactly the
kind of thing that changes without a release note.

## Retries, disabling and freezing

Failed deliveries retry for up to **48 hours over 11 attempts**, with the interval growing as
`((2^attempt) - 1) * 84800ms`. First retry at about 1.5 minutes, second near 5 minutes, eleventh
around 48 hours.

Failure is tracked **per URL**, not per subscription, so one bad consumer takes down every
subscription pointing at it.

| State | Trigger | Recovery |
|---|---|---|
| **Disabled** | Failure rate over 70% across more than 100 attempts, **or** 2,000 consecutive failures. After a 100-message grace period. | Automatic. Every 10 minutes Workfront tries the next message; success re-enables the URL, failure resets the timer. |
| **Frozen** | Over 2,000 consecutive failures with the last success more than 72 hours ago, **or** 50,000 consecutive failures. | Not automatic. Treat as needing Support. |

The 10-minute probe explains a complaint that otherwise looks like a Workfront bug: deliveries that
are intermittent and delayed rather than absent. The URL is disabled and being probed, not broken.

Do the client's endpoint testing inside the **100-message grace period**, before the failure
accounting starts.

## TLS client certificates

To prove a delivery genuinely came from Workfront, configure your server to request and validate
Workfront's x509 client certificate:

1. Download the PEM of the **DigiCert Global Root CA** certificate.
2. Turn on client certificate verification, trusting that CA.
3. Set **verification depth to 2** — Workfront's certificate is signed by DigiCert SHA2 Secure Server
   CA, an intermediate under that root.
4. Check the certificate's Subject DN really is Workfront's.

TLS 1.3 where the receiving server supports it, otherwise 1.2. Self-signed certificates are not
supported. `adobe-docs` is not vendored for this file; NGINX and Apache examples are on Adobe's page.

## Triage order when events are not arriving

1. Read `subscription_url.successes` / `failures` / `disabled_at` / `frozen_at` on a GET of the
   subscription. This answers "is it us or them" immediately.
2. Is the endpoint returning 2xx within 5 seconds? Timeouts look identical to outages.
3. Is a filter silently excluding everything? Recreate the subscription without filters and see if
   anything arrives.
4. Is the event even the one you think? Updating a document on a task raises a document event, not a
   task event. This is the most common wrong assumption.
5. Is the payload over 1 MB?
6. Are the IPs allowlisted?
7. Was the subscription created in a different environment? They do not travel.

## Rate limiting

A user generating events at a high rate in a short window can be sandboxed, with deliveries delayed.
Bulk updates are the usual cause: a mass change enqueues an event per affected record. When
dedicated bulk-update tooling runs against a tenant with live subscriptions, the subscription backlog is
a real consequence worth naming to the client before the run, not after.

## Sources

Adobe Experience League, `AdobeDocs/workfront.en` `help/quicksilver/wf-api/`:
`general/event-subs-api.md`, `general/event-subs-versioning.md`, `general/event-subs-faq.md`,
`general/event-sub-best-practice.md`, `general/setup-event-sub-endpoint.md`,
`api/event-sub-retries.md`, `api/event-sub-certs.md`, `api/message-format-event-subs.md`,
`api/filter-event-sub-messages.md`, `api/event-sub-resource-fields.md`. Read 2026-09-17.

Per-object payload field lists are in Adobe's `event-sub-resource-fields.md`; they are long, they
track the API version, and they are better read live from `/metadata` than copied here.
