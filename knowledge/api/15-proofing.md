# 15 — Proofing (Proofs, Decisions, Comments)

How to drive Workfront proofing programmatically: create proofs, stamp reviewer decisions, and add comments. This is a **three-surface** problem — no single API does all of it — and the split is the whole point of this file.

| Action | Surface | Reachable from main REST API? |
|---|---|---|
| Create a proof (+ workflow/stages/recipients) | **ProofHQ API or Fusion Create Proof** — `document/createProof` exists but is a verified no-op via REST (see §1) | ⛔ not via main REST |
| Make a reviewer decision (Approved / Changes required …) | Documented: main WF REST `docv/setDocumentReviewerDecision`. Verified working: ProofHQ REST, or Fusion → SOAP `updateProofReviewer` | ⚠️ documented but unverified — `403`'d live (see §3) |
| Add a standalone proof comment (page-anchored, markup, threads) | **Workfront Proof / ProofHQ API** (`rest.proofhq.com`, or legacy SOAP) | ❌ **not in the main API** — no comment action exists on any proofing object |

**The one thing to remember:** the main Workfront REST API is the only *documented* decision path — `docv/setDocumentReviewerDecision` writes a decision plus an optional comment in one call — but it is **not round-trip-verified**. The one live attempt `403`'d even after the recipient was promoted to approver, because Workfront does not see a ProofHQ-side role change (§3). Every decision actually stamped on this tenant went through ProofHQ: Fusion → SOAP `updateProofReviewer` (`statusCode 200`), or `PUT rest.proofhq.com/api/v1/proofs/{token}/recipients/{rt}` with a `decision` body. **Stamp decisions there until the main-API setter is proven.** Proof comments have no main-API action at all; only the decision comment rides along with that setter.

> 📖 **Companion file:** [`16-proofhq-soap-catalog.md`](16-proofhq-soap-catalog.md) catalogs the **complete** ProofHQ SOAP surface (all 90 operations, proven to have no hidden methods) and documents the **verified recipe for posting drawing markup** — arrows, boxes, lines, freehand, highlights. It also **corrects two claims in this file**; both are flagged inline below (§3).

---

## Verification status

Verified live against a live production tenant (v17.0), 2026-07-02/03, acting as the instance owner:

- ✅ **Data model** (DOCU/DOCV/PRFAPL objCodes, action names, argument signatures, field lists) — from `/metadata`.
- ✅ **Real enum values** — harvested from 82 existing proofs on the instance (see §2).
- ✅ **Document upload + create** — the two-step `POST /upload` → `POST /document` flow works.
- ⛔ **`document/createProof` / `createProofRest` DO NOT generate a proof via REST** — both return `{"data":{"result":null}}` with no error and no proof queued, even for a valid PNG uploaded by the System-Admin instance owner. Confirmed no-op (see §1). **This is the headline finding: the main-API proof-creation path is unreliable/non-functional here** — use the ProofHQ API or Fusion's Create Proof module instead.
- ✅ **ProofHQ auth bridge mapped** — `getProofingTokens` (as a **PUT** action) returns a per-proof `token` + `mediaViewerApi`; the ProofHQ REST session is minted via `POST /authorize` (JSON `{email, authtoken}` → `{sessionId}`, header `sessionId:`); the `authtoken` is the personal **ProofHQ API token** at Workfront Proof → User Settings → Integrations (see §3). Confirmed by the error-response fingerprints; the final authenticated write awaits that token.
- ✅ **Legacy SOAP API authenticated end-to-end** — `soap.proofhq.com/soap.php` `doLogin(Login, Password)` succeeded with the account password (no Public API toggle needed); session + org confirmed; `getAllProofs` and other reads work. Decisions have a clear write path (`updateProofReviewer` → `RecipientDecision`). See §3.
- ⛔ **File-based proof CREATION is walled for raw clients** — `createProof` requires a `Hash` that only `doUpload` produces, and `doUpload`'s attachment encoding is proprietary/undocumented (no `mime:` binding in the WSDL; raw SwA → `Bad Request`). No create-from-URL alternative exists. A real file→proof pipeline needs **Fusion's Create Proof module** or ProofHQ's SOAP SDK — not hand-rolled curl. (I did **not** create/mutate anything: `doUpload` returned empty and `createProof` 400'd on the missing Hash, so nothing landed in the account's 17 real proofs.)
- ✅ **Full create → reviewer → decision VERIFIED end-to-end via Fusion** (2026-07-03): a live scenario (Get File → Upload File → Create Proof → getProofReviewers → updateProofReviewer) created a fresh proof and stamped `Approved` (`statusCode 200`). This is the working demo-data generator — see the Fusion section below and `examples/fusion/06-demo-proof-generator.json`. Dynamic reviewer ref: `{{<getReviewers>.body.data.item[1].id}}` (1-indexed; `item[]` alone resolves empty in a text field).
- ✅ **Original top-level comments ARE reachable — via ProofHQ REST, with only a Workfront API key.** Not from SOAP (no `addComment` — absent from all 90 operations) and not from the main WF REST API (no comment action on DOCU/DOCV/PRFAPL). But `POST /proofs/{token}/comments` on `rest.proofhq.com` works against a **proof-scoped `sessionId`** minted by `getProofingTokens` (PUT, API key) → viewer RPC `startup` — **no Public-API `authtoken` and no session cookie**. Verified 2026-08-06 on a partner-sandbox proof account, where the Public API feature is *off*: five markup comments posted `201`, read back, deleted `204`. `text` is the only required field; `drawings[]` is optional. Re-mint per proof. Recipe: [`16-proofhq-soap-catalog.md`](16-proofhq-soap-catalog.md) §6.1.

---

## The proofing data model (verified)

Proofing spans three objCodes. Proof *creation* hangs off the document; proof *state and decisions* hang off the document version; `PRFAPL` is the read-only reporting join.

**`DOCU` (Document) — where proofs are created.**
- Proof fields: `advancedProofingOptions`, `createProof`
- Proof actions: `createProof`, `createProofRest`, `createLinkedProofVersion`, `getProofRecipients`, `getProofStages`, `getProofTemplate`, `getDocumentProofTemplate`, `isProofAutoGenrationEnabled`

**`DOCV` (DocumentVersion) — where proof state and decisions live.**
- Proof fields: `proofID`, `proofStatus`, `proofDecision`, `proofStageID`, `proofStatusDate`, `proofStatusMsgKey`, `proofedByUserID`, `isProofable`, `isProofAutomated`, `activeProofStages`, `advancedProofingOptions`
- Proof actions: `setDocumentReviewerDecision`, `getDocumentReviewerDecision`, `getProofingTokens`

**`PRFAPL` (ProofApproval) — read-only reporting object, no write actions.**
- Fields: `ID`, `approverDecision`, `approverID`, `approverStage`, `decisionDate`, `documentVersionID`, `isAwaitingDecision`, `proofCreationDate`, `workflowTemplate`
- You *observe* per-reviewer decisions here (this is what proof-decision reports read); you never write to it directly. Writes land via `setDocumentReviewerDecision` on the DOCV, which updates the underlying proof, which surfaces as `PRFAPL` rows.

**Proof-workflow *configuration* is not exposed by the main Workfront REST API.** `/proofWorkflow/search`, `/proofApprovalWorkflow/search`, and case variants all return `Unknown object type`. (**ProofHQ REST does expose per-proof stages** — `GET /proofs/{token}/stages` and friends, verified `200`; see [`16-proofhq-soap-catalog.md`](16-proofhq-soap-catalog.md) §6.5. Different API.) You can read the workflow *template* a proof used (`workflowTemplate` on PRFAPL, `getProofTemplate` on DOCU), but workflows are configured only in the UI (Setup → System → Proof → Workflows). See the platform-assessment record.

---

## 1. Create a proof — main REST API

`createProof` (and the newer `createProofRest`) are actions on the **document**. Both take the same two args: `documentVersionID` (optional — defaults to current version) and `advancedProofingOptions` (a **string containing JSON**, not a nested object). Return type is void.

```
PUT $$HOST/attask/api/v17.0/document/<DOCUMENT_ID>/createProof?apiKey=<KEY>
Content-Type: application/x-www-form-urlencoded

documentVersionID=<DOCV_ID>&advancedProofingOptions={}
```

Pass `{}` for a bare proof (no workflow). For a full automated workflow, `advancedProofingOptions` is a stringified JSON like:

```json
{
  "stages": [
    {
      "name": "Review Stage 1",
      "position": 1,
      "activateOn": 1,
      "lockOn": 1,
      "isPrivate": false,
      "isMandatory": false,
      "isOneApproval": true,
      "recipients": [
        {
          "name": "Jane Reviewer",
          "email": "jane@example.com",
          "role": 5,
          "notifications": 0,
          "isPrimaryDecisionMaker": false
        }
      ]
    }
  ],
  "subject": "Demo proof",
  "message": "",
  "canDownload": true,
  "hasPublicSharing": true,
  "isAutomatedWorkflow": true
}
```

Adobe under-documents this shape and explicitly suggests reverse-engineering it from browser network traffic while building a proof in the UI. `getProofStages` / `getProofRecipients` / `getProofTemplate` (DOCU actions) help you discover valid `role` IDs, stage IDs, and template structure before composing the JSON.

> ⛔ **VERIFIED: `createProof` and `createProofRest` are a silent no-op via the REST API.** Tested 2026-07-03 on a proofing-enabled instance (82 real proofs present), acting as the System-Admin owner, with both a PDF and a valid PNG: `PUT .../document/<id>/createProof` returns `{"data":{"result":null}}` — **no error, no proof queued, `proofID`/`proofStatus` stay `null` indefinitely** (real proofs on the same instance finish in ~1 min). `createProofRest` behaves identically. The action exists in `/metadata` but does not drive proof generation from an API-key session. **Do not rely on the main API to create proofs.**
>
> **Method + payload variations all fail (re-verified 2026-07-04, so this can't be dismissed as "wrong method / empty options"):**
> - `POST .../document/<id>/createProof` → `{"error":"unrecognized URI format: too many parts"}`. Workfront **rejects POST** on `/obj/<id>/<action>` endpoints — POST is for creates (`POST /document`); actions require **PUT**. (So docs/answers citing `POST .../DOCU/<id>/createProof` are wrong at the HTTP-method level.)
> - `PUT` with a **fully populated** `advancedProofingOptions` (real stage + recipient + `isAutomatedWorkflow:true`) → still `{"result":null}`, no proof. Empty `{}` vs populated makes no difference.
> - Both `createProof` and `createProofRest` no-op identically.
> - **The `createProof` *field* (not the action) also no-ops — via every write path incl. new document versions.** `createProof` is a writable-looking boolean field on DOCU and DOCV. Tested `createProof=true` (+ `advancedProofingOptions`) via `POST /document` (create), `PUT /docv/<id>`, `PUT /document/<id>`, and **`POST /docv` (new version)** — none produce a proof; `proofID`/`proofStatus` stay null.
>   - **Important:** the field is flagged `DYNAMIC` (also `LAZY_READ`, `NOT_GROUPABLE`) in `/metadata`, so it **always reads back `null`** by design — the `createProof:null` echo does NOT prove the write was ignored. The **only trustworthy Workfront-side signal is `proofID`/`proofStatus`**, and those never populate on any path. So whether the write is silently dropped or triggers an orphaned ProofHQ proof that never links back, the result is identical: **no usable proof appears in Workfront.**
>   - Community thread `…document-create-proof-process-hangs-indefinitely-133172` (v16) matches: the proof may generate *orphaned* in ProofHQ while the WF link hangs (`proofID` stays null).
>
> Adobe's own guidance ([`api-create-proof-options-json`](https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/tips-troubleshooting-apis/api-create-proof-options-json)) recommends "create a simple proof, then finish via the SOAP ProofHQ API" — tacitly conceding the pure-REST path is incomplete. The endpoint/options are documented accurately; they just don't deliver a usable proof from an API session on a modern tenant.
>
> Working alternatives:
> - **ProofHQ API** — `POST https://rest.proofhq.com/api/v1/proofs` (auth: `WFServiceTokenAuth` / session).
> - **Fusion** — the Workfront Proof connector's **Create Proof** module (goes through the ProofHQ engine with proper auth). This is what practitioners actually use.
> - The 82 working proofs on the test instance were all created via UI/Fusion, never via `document/createProof`.

> ⚠️ **`isProofable` is NOT a "can this be proofed" flag.** It reads `false` on freshly-uploaded versions *and* on all 82 successfully-proofed versions. Do not gate creation on it. The real signals are `proofID` (numeric ProofHQ FileID, e.g. `125653549`) and `proofStatus` (`success` / `failed`).

**Other prerequisites for any creation path:**
- Proofing must be **licensed and enabled** on the instance. (`document/isProofAutoGenrationEnabled` is an *action*, not a `namedQuery` — a plain GET returns `does not support namedQuery` in v17.0.)
- Generation is **asynchronous** (the ProofHQ engine renders the file). Poll `docv.proofStatus` until `success` before making decisions or reading tokens. ~4/82 real proofs on the test instance sat at `failed` — generation is not guaranteed even for valid files.
- A proof needs a **real, valid source file**. A hand-built/minimal file (e.g. a stub PDF with a broken xref) is rejected. Use a genuine image/PDF.

`createLinkedProofVersion` (args `documentID`, `fileHandle`, `fileName`, `creatorName`; returns a map) adds a *new version* to an existing proof — use it to demo version-over-version review history.

**Verified upload → document flow (works):**
```
POST $$HOST/attask/api/v17.0/upload?apiKey=<KEY>      (multipart: uploadedFile=@file)  → {"data":{"handle":"<h>"}}
POST $$HOST/attask/api/v17.0/document?apiKey=<KEY>     name=[prefix] ...&handle=<h>&docObjCode=PROJ&objID=<projectID>&fields=ID,currentVersionID
```
Gotcha: `lastVersionID` is not a valid Document field in v17.0 (`APIModel V17_0 does not support field lastVersionID`) — request `currentVersionID` instead.

> ⚠️ **Email side-effect.** Recipients with `notifications` > 0 get **real proof-invitation emails**. On a production/shared instance, keep `notifications: 0` and avoid third-party addresses, or use a bare `{}` proof plus `setDocumentReviewerDecision` as the sole reviewer, so the demo emails no one.

---

## 2. Make a decision — main REST API (the demo goldmine)

`setDocumentReviewerDecision` is a **document-version** action. It writes a decision **and** an optional comment in one call, returns `Boolean`, and needs no ProofHQ hop.

```
PUT $$HOST/attask/api/v17.0/docv/<DOCV_ID>/setDocumentReviewerDecision?apiKey=<KEY>
Content-Type: application/x-www-form-urlencoded

documentVersionID=<DOCV_ID>&reviewerDecision=<DECISION>&comment=Looks+good+to+me
```

**Decision values — casing differs by object (verified against 82 real proofs, 2026-07-03):**

- **`PRFAPL.approverDecision`** (per-reviewer) is **Title Case**: `Approved`, `Approved with changes`, `Changes required`, `Not relevant`, `Pending`. Casing is *not* enforced consistently — the same instance held both `Pending`/`pending` and `Not relevant`/`Not Relevant`, reflecting per-account customization and history. The admin can rename/hide options, so confirm against the target tenant.
- **`DOCV.proofDecision`** (doc-level rollup) is **lowercase**: `approved`, `approved with changes`, `changes required`, `pending`, and `-` (dash = no decision yet / not applicable at doc level). This is the value report filters match, e.g. `currentVersion:proofDecision_Mod=cicontains` value `pending`.
- **`DOCV.proofStatus`** is the *generation* status, not a decision: `success` / `failed`.

For `setDocumentReviewerDecision`'s `reviewerDecision` arg, pass the label as configured (Title Case matching the account's options is the safe bet) — `_unverified live_`; the round-trip couldn't be tested because no self-created proof was available.

Read the current decision back with `getDocumentReviewerDecision` (arg `documentVersionID`, returns a map), or verify via a `PRFAPL` query:

```
GET $$HOST/attask/api/v17.0/prfapl/search?documentVersionID=<DOCV_ID>&fields=approverID,approverDecision,decisionDate,approverStage,isAwaitingDecision&apiKey=<KEY>
```

To simulate *multiple reviewers*, each reviewer must be a recipient on the proof; each decision surfaces as its own `PRFAPL` row. A single admin/service identity can drive the calls.

_Unverified live: the decision round-trip could not be exercised — creating a proof to write against is blocked by the `createProof` no-op (§1), and the instance's real proofs must not be mutated for a test. Still open: exact `reviewerDecision` casing the setter accepts, and whether one identity can set a decision on behalf of another `approverID`._

---

## 3. Add a comment — ProofHQ API only

There is **no comment action anywhere in the main Workfront REST API** (verified: no comment action on DOCU, DOCV, or PRFAPL). The *decision* comment in §2 is the only comment the main API writes. Real proof comments — page-anchored, markup annotations, reply threads — require the separate **Workfront Proof / ProofHQ API**, a distinct system underneath Workfront's proofing.

### The authentication bridge (verified 2026-07-03)

There are **two distinct token systems** — do not confuse them:

**(a) Per-proof viewer token — from Workfront, scoped to one existing proof.** Invoke `getProofingTokens` as a proper **PUT action** (a plain GET just echoes docv metadata — that was the earlier dead end):

```
PUT $$HOST/attask/api/v17.0/docv/<DOCV_ID>/getProofingTokens?apiKey=<KEY>   (body: versionID=<DOCV_ID>)
→ {"data":{"result":{
     "token":"8HXYLmqiABa12TxTWfGJ8zZbLjNF4Lkh",
     "codetodecode":"<hex>-8HXYLmqiABa12TxTWfGJ8zZbLjNF4Lkh-pdf<hex>",
     "mediaViewerApi":"https://us.my.workfront.com/proof/rpc/"
   }}}
```

`token` is the proof's `{token}` for `rest.proofhq.com/api/v1/proofs/{token}/...` path params. `mediaViewerApi` is the embedded viewer's **JSON-RPC** endpoint on the tenant's proofing region (`<region>.my.workfront.com/proof/rpc/`), used by the in-product viewer. This token identifies a proof but is **not** a REST session — it cannot authenticate a `rest.proofhq.com` call on its own (`sessionId: <thistoken>` → `{"error":"Session invalid"}`). The DOCV's `proofID` is the ProofHQ `FileID` (numeric string, e.g. `125653549`).

**(b) Account session — the actual REST credential.** The ProofHQ REST API authenticates with a **`sessionId`** you mint via `/authorize`:

```
POST https://rest.proofhq.com/api/v1/authorize
Content-Type: application/json
{"email":"<proof-user-email>","authtoken":"<ProofHQ API token>"}
→ {"sessionId":"<id>"}
```

Then send header **`sessionId: <id>`** on every subsequent call. Verified live: the JSON body shape is correct (a wrong secret returns `{"error":"Invalid login details"}`, not a shape error) and the header name is `sessionId` (a bad value returns `{"error":"Session invalid"}`).

**Where `authtoken` comes from — this is the credential you must supply.** It is **not** the Workfront API key and **not** the per-proof token from (a). It is the personal **ProofHQ API authentication token**, found in Workfront Proof at **User Settings → Integrations** ("your authentication token that allows third party software to connect to your account through the API"). Requires a proof license on the account. `WFServiceTokenAuth` is the same idea expressed as `(wfServiceToken, email, token)`.

Regional bases: US `https://rest.proofhq.com/api/v1`, EU `https://rest.proofhq.eu/api/v1` (preview: `rest.preview.proofhq.com` / `.eu`). Pick the region matching `mediaViewerApi`'s host.

> ⚠️ **The Integrations tab (and thus the `authtoken`) only exists if the account's Public API feature is enabled.** On a tenant where it's off, Proof → User Settings shows only Settings / Proofing defaults / Tags / Out of office — no Integrations tab (verified 2026-07-03 on a partner-sandbox proof account). Enabling Public API is an **account-admin** action (a Supervisor profile is not enough to see the token until the feature is on). Without it the `/authorize` + `authtoken` route is unavailable — but that is **not** the only REST path: the viewer-RPC session described in the correction above reaches `rest.proofhq.com` with just a Workfront API key. Only proof *creation* still needs Fusion or the internal app API (not supported — see next note).

> **Internal proof-app API is undocumented and unsupported — but IS scriptable with a captured session cookie.** The embedded proofing UI lives at `https://<tenant>.my.workfront.com/proof/` and its backends (`/proof/ajax/…`, `/internal/…`, heartbeat `/proof/checksession.php`) authenticate with the **httpOnly web-session cookie** + `x-xsrf-token`. It is not a *supported* integration point and can change without notice — but the cookie *can* be extracted from DevTools and replayed, and doing so drives the full create → comment → reply → decision flow headlessly (see "Full headless flow" below, and `examples/api/proofing/create-demo-proof.sh`). Prefer Fusion for durable automation; the cookie path is for on-demand demo-data generation.

### How the Workfront UI actually creates a proof (reverse-engineered from DevTools, verified 2026-07-04)

This is the definitive explanation of why the public REST `createProof` no-ops — **the UI never uses it.** Creating a proof in the web UI fires two `/internal/` calls, both authenticated by the **web session cookie + `x-xsrf-token`** (NOT the API key):

1. **Create:** `POST /internal/document/proof/create` — body just `documentVersionID=<DOCV_ID>`. This is the real create trigger.
2. **ProofHQ REST bridge:** `GET /internal/getProofhqRestApiToken?proofID=<numeric proofID>` → returns a **ProofHQ `sessionId`**. The UI then calls `rest.proofhq.com/api/v1/...` with header `sessionid: <that token>`.

**Verified live:** the `sessionId` minted this way authenticates the full ProofHQ REST API — `GET rest.proofhq.com/api/v1/proofs/<token>` returned complete proof JSON (`processingStatus: "success"`, etc.). So `rest.proofhq.com` (create via `POST /proofs`, comments, decisions) **is** reachable — but the credential comes from this internal bridge, which **bypasses the personal `authtoken`/Integrations path entirely** (that's why the `/authorize` route was a dead end when Public API was off).

**Both `/internal/` endpoints reject the API key** (`apiKey` → HTTP 302 redirect-to-login). So there is no public-API-key path **to create a proof**: creation routes through the Workfront **web session cookie** (or Fusion). **Fusion works precisely because its connection carries a real user session**, giving the connector this same internal access under the hood.

> ✅ **CORRECTION (2026-08-06): minting a ProofHQ REST session does NOT require a cookie.** This section originally said there was no API-key path to *either* creating a proof or minting the session. The first half stands; **the second half is wrong.** The proof *viewer's* JSON-RPC exposes a `startup` method that accepts the `token` + `codetodecode` from `getProofingTokens` (an ordinary API-key call) and returns a `sessionId` that authenticates `rest.proofhq.com` directly:
>
> ```
> PUT  $$HOST/attask/api/v17.0/docv/<DOCV_ID>/getProofingTokens?apiKey=<KEY>   → token, codetodecode
> POST https://us.my.workfront.com/proof/rpc/index.php
>      headers: tcmssubdomain: <sub>, tcmstenantid: <tenant-uuid>
>      body:    {"method":"startup","proofingCode":"<codetodecode>","token":"<token>"}   → sessionId
> ```
>
> Verified live 2026-08-06 (comments read, posted, and deleted on a live production tenant with no cookie). This also corrects the "Two ID systems" gotcha below, which claims the RPC uses "a **different session token** than `getProofhqRestApiToken` mints" — the RPC-minted session works fine on `rest.proofhq.com`. Net: **comments, markup, decisions, and recipients are all reachable with nothing but a Workfront API key.** Only proof *creation* still needs the cookie or Fusion. Full recipe: [`16-proofhq-soap-catalog.md`](16-proofhq-soap-catalog.md) §6.1.

### Full headless flow — PROVEN end-to-end (2026-07-04)

Driving the web session cookie directly (captured from DevTools), the **entire demo-proofing flow works with no Fusion and no OAuth** — reference implementation: [`examples/api/proofing/create-demo-proof.sh`](../../examples/api/proofing/create-demo-proof.sh).

| Step | Endpoint | Auth | Verified |
|---|---|---|---|
| Create proof | `POST /internal/document/proof/create` (`documentVersionID`) | **cookie** | ✅ `proofID` + `proofStatus: success` |
| Mint ProofHQ session | `GET /internal/getProofhqRestApiToken?proofID=X` → `{sessionId, restURL}` | **cookie** | ✅ |
| Post comment | `POST rest.proofhq.com/api/v1/proofs/{token}/comments` `{text,page}` | **sessionId** | ✅ |
| Reply | `POST …/comments/{ct}/replies` `{text}` | **sessionId** | ✅ (500 but lands) |
| Promote to approver | `PUT …/recipients/{rt}` `{"role":5}` | **sessionId** | ✅ (`roleReviewerApprover`) |
| Set decision | `PUT …/recipients/{rt}` `{"decision":{"token":<opt>}}` | **sessionId** | ✅ (500 but lands) |
| Resolve thread | viewer RPC `resolve_comment` | RPC-minted `sessionId` (same system — see correction above) | ⚠️ not sourced |

**Load-bearing gotchas (each cost real time):**
- **The document version MUST be `isProofable: true`** before the create fires, or it returns `200` but generates nothing. **The gate is file-type recognition, and Workfront derives the type from the document `name`'s extension — NOT the file bytes.** Root cause found 2026-07-04: an API `POST /document` with `name` lacking an extension (e.g. `name=My Proof`) is tagged `ext:""`, `fileType:unk`, `documentTypeLabel:"Undefined File Type"` → `isProofable:false` → create no-ops. **Fix: name the document with a real extension** (`name=My Proof.jpg`) — `ext` then resolves, `documentTypeLabel` becomes e.g. "JPEG Image", and `isProofable` flips `true`. So API-uploaded docs proof fine; the earlier "must upload via UI" belief was wrong — the UI just always includes the extension. (`isProofable` also reads `false` on already-*proofed* versions — it's a pre-proof "eligible" flag, not a general capability flag; check `ext`/`documentTypeLabel` when debugging a non-proofable API upload.)
- **`rest.proofhq.com` writes routinely return HTTP `500` but SUCCEED.** Decision, reply, and comment writes all 500'd yet persisted. **Never trust the status code — read the object back.** This is the single biggest footgun.
- **The `wf-auth` JWT must be complete** in the cookie (RS256-signed; any truncation → `401`).
- **Decisions need an approver.** `roleReviewer` (3) → 403 "not an approver"; promote to `roleReviewerApprover` (5) or `roleApprover` (4) first. Role enum: 1=ReadOnly, 3=Reviewer, 4=Approver, 5=ReviewerApprover, 6=Author, 7=Moderator. The WF action `docv/setDocumentReviewerDecision` still 403s even after promotion (it doesn't see the ProofHQ role change) — set the decision via `rest.proofhq.com` instead.
- **Two ID systems:** `rest.proofhq.com` uses opaque **tokens**; the viewer RPC (`us.my.workfront.com/proof/rpc/index.php`, auth = `sessionId` in the POST body, `credentials: omit`) uses **numeric IDs** and a **different session token** than `getProofhqRestApiToken` mints. RPC methods: `comments` (list, `{method,sessionId}`), `add_reply` (`{method,commentId,text,isPending,notifyRecipients,attachmentIds,sessionId}`), `resolve_comment` (`{method,sessionId,commentId}`). Resolving = a `type:4` reply.

**Caveat:** the cookie is ephemeral (dies on logout/expiry) and a full-account credential. This path is unsupported and can break without notice. For durable/repeatable automation prefer Fusion; use the headless script only for on-demand demo-data generation. Net: the public REST API genuinely can't create proofs — but the internal surface **is** scriptable with a session cookie, which disproves the earlier "not an automation surface" framing for anyone willing to manage a captured session.

### Endpoints (once you hold a `sessionId`)

**Modern REST** — base `https://rest.proofhq.com/api/v1/`:
- `POST /proofs` — **create a proof** (this is the working creation path, unlike main-API `createProof`)
- `POST /proofs/{token}/comments` — create a comment. Required body: `text` (non-empty). Optional: `drawings[]`, `pins`, `page`, `pages`, `timestampBegin/End`, `metadata`, `actionToken`, `isLocked`, `layout`, `textDirection`
- `GET /proofs/{token}/comments` — list; `PUT`/`DELETE /proofs/{token}/comments/{id}` — edit/remove
- `GET /proofs/{token}/decision` — proof-level decision. **The path is singular** (the operationId is `getProofDecisions`, but there is no `/decisions` route). Verified `200` → `{token, decision, name, displayName, decisionAt}`
- `GET /proofs/{token}/stages/{st}/decision` (per-stage) and `GET /proofs/{token}/recipients/{rt}/decision` (per-recipient; adds `isSignedDecision`, `hasReasons`, `reasons[]`) — both verified `200`
- `GET /accounts/{token}/settings/decisions` — the account's decision catalog: `{token, decision (int), name, displayName, isEnabled, hasReasons, hasPostMessage}`. Submit that `token` on a decision write rather than guessing a label. Observed ints: `3`=Approved, `2`=Approved with changes, `4`=Not relevant, `0`=Pending
- Writes (catalogued, not exercised): `PUT /proofs/{token}/recipients/{rt}/decision`; `PUT`/`PATCH /proofs/{token}` edits the proof. The decision write verified in this repo is the alternative shape `PUT …/recipients/{rt}` with `{"decision":{"token":…}}` (500 but lands)

### Legacy SOAP API — the most accessible raw path (verified reachable 2026-07-03)

**This is the path that works when the REST Public API / Integrations `authtoken` is NOT enabled** (which is the common case). Verified: a `doLogin` with a wrong password returns SOAP `faultcode 303 "Your log in details are not valid."` — i.e. the account accepts SOAP logins; only the password is needed. It does **not** require the Public API feature toggle.

- **Endpoint:** `https://soap.proofhq.com/soap.php` — SOAP 1.1, RPC style. WSDL at `https://soap.proofhq.com/soap?wsdl` (185 KB, 70+ methods).
- **Namespace:** `https://soap.proofhq.com/` · **SOAPAction:** `https://soap.proofhq.com/<methodName>`.
- **Auth:** `doLogin(Login, Password)` (email + the ProofHQ **account** password — settable via "Change password" in Proof → Personal settings) → returns a **session key** used by every later call; it renews on each call. This password is a *different* credential from both the Workfront API key and the REST `authtoken`.
- **Verified `doLogin` envelope:**
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ns1="https://soap.proofhq.com/" xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <SOAP-ENV:Body><ns1:doLogin>
      <Login xsi:type="xsd:string">user@example.com</Login>
      <Password xsi:type="xsd:string">••••••</Password>
    </ns1:doLogin></SOAP-ENV:Body>
  </SOAP-ENV:Envelope>
  ```
  POST with `Content-Type: text/xml; charset=utf-8` and `SOAPAction: "https://soap.proofhq.com/doLogin"`.
- **`doLogin` returns** (verified): `<session>`, `user_id`, `organisation_id`, `organisation_name`, plus account limits (`limit_storage`, `limit_proofs`, `max_file_size` — ~4.5 MB on the test org). The `<session>` value is the `SessionID` for all later calls.
- **Reads that work today (verified):** `getAllProofs(SessionID, StartFrom, SearchQuery, ItemsPerPage)`, `getProofDetails(SessionID, FileID)`, `getProofStatus`, `getProofReviewers`, `getProofComments(SessionID, FileID)`, `getProofURL`.
- **Decisions (verified path):** there is **no `updateDecision`/`getDecisions`** on this endpoint. A reviewer's decision is set via **`updateProofReviewer(SessionID, RecipientID, RecipientDecision, …)`** — you add a reviewer with `addProofReviewer(SessionID, FileID, RecipientEmail, …, PrimaryDecisionMaker)`, then update that reviewer's `RecipientDecision`.
- **Comments (verified limitation):** this endpoint's WSDL has **no standalone `addComment`** (the api.proofhq.com index lists one, but the live SOAP service exposes only `getProofComments`, `addCommentReply(SessionID, FileID, ReviewerID, CommentID, Reply)`, `setCommentAction(SessionID, CommentID, ActionID)`, `getCommentAction`). So SOAP can read comments, reply to existing ones, and set action labels — original top-level comments need the REST API (`POST /proofs/{token}/comments`).
- **Full surface now catalogued.** All **90** SOAP operations are enumerated in [`16-proofhq-soap-catalog.md`](16-proofhq-soap-catalog.md), which also proves via an unauthenticated fault oracle that **no hidden methods exist** beyond the WSDL — including no markup verb of any kind. Notable capabilities that file surfaces and this one never mentioned: **webhooks** (`setProofCallback` / `setAccountCallback`), a per-proof **activity/audit feed** (`getActivity`), **`decodeProofID`** (converts a proof token to the numeric `FileID` — solves the two-ID-systems footgun below), embed codes, batches, and full user/workspace administration.

> ⛔ **The file-upload step is the wall for hand-rolled clients (verified 2026-07-03).** `createProof` **requires a non-empty `Hash`** (`faultcode 400 "Required string parameter 'Hash' is not present."`) — and `Hash` comes *only* from `doUpload`. There is **no** URL-capture / create-from-URL / hash-from-URL method (the web-URL proofs in the account were made via the UI's web capture, not an exposed API method). `doUpload` takes only `SessionID` and expects the file as a **SOAP attachment**, but the WSDL declares **no `mime:`/`xop:` binding**, and a standard multipart/related (SwA) POST returns `faultcode SOAP-ENV:Client "Bad Request"`. Matching the exact encoding requires ProofHQ's own SOAP client SDK (PHP/Java) — or a SOAP library with attachment support (e.g. Python `zeep` + MTOM). **Do not attempt raw-curl `doUpload`.** For a working file→proof pipeline, use **Fusion's Create Proof module** (handles upload+hash+create internally) or a real SOAP SDK.

**Raw-API flow (once `doUpload` is solved via an SDK):** `doLogin` → `doUpload` (stage file → `filehash`) → `createProof(…, Hash=filehash, …)` → poll `getProofStatus` → `addProofReviewer` + `updateProofReviewer(RecipientDecision=…)` for decisions → `addCommentReply` for comment threads → `deleteProof` to clean up a test.

**Practical route (community consensus):** use **Fusion's Workfront Proof "Custom API Call" module**, which auto-builds the SOAP envelope and passes the SessionID implicitly — you supply only the inner XML (e.g. `<FileID>123456</FileID>`). Described as tedious and trial-and-error; start with a read (get proof details) before attempting a comment write.


---

## Fusion route (Workfront Proof connector)

If orchestrating rather than curling:
- **Actions:** Create Proof, Update Proof, Download Proof, Read a Record, Upload File, Request PDF Summary, **Custom API Call** (escape hatch for comments/decisions)
- **Searches:** Search, List Workflow Templates
- **Triggers:** Watch Proofs (fires on create/decision), Watch Proof Activity, Watch for PDF Summary

There is no dedicated "Add Comment" or "Make Decision" module — those go through **Custom API Call** against the ProofHQ API. See the Fusion record and the `workfront-proof:` connector.

### Verified connector schema (2026-07-03, from a live Fusion import)

- **`workfront-proof:createProof`** — real required fields: `proofType` (`basic`|`automated`), `CombinedProof` (bool), `isProofVersion` (bool), `Hash` (**array** — map the file **data**, e.g. `["{{1.data}}"]`; the connector runs `doUpload` internally, solving the raw-client wall), `SourceName` (**array**, e.g. `["{{1.fileName}}"]`), `Name`. Reviewers go in **`Recipients`** (array, capital R). Also exposes `OwnerID`, `Deadline`, `SuppressNewProofNotification`, `EnableDownload`, and ~40 Show*/Enable* booleans. There is **no** `Subject`/`Message` field. Pull the file with `http:ActionGetFile` first, then map its `data`/`fileName` (never map a URL directly).
- **`workfront-proof:customApiCall`** — mapper is just **`method`** + **`bodyXML`**. `method` is the **ProofHQ SOAP operation name**; `bodyXML` is the **inner XML params only** (the connector wraps the envelope and injects `SessionID`). Output is under `body.data`.
- **Verified SOAP operations via Custom API Call** (against `soap.proofhq.com`, 2026-07-03):
  - Set a decision: `method=updateProofReviewer`, `bodyXML=<RecipientID>{{id}}</RecipientID><RecipientDecision>Approved</RecipientDecision>` (param names confirmed — a bad ID returns "Invalid Recipient ID", not a param error). Get the `RecipientID` from `method=getProofReviewers`, `bodyXML=<FileID>{{proofId}}</FileID>` (returns reviewers with `id`, `email`, `role`, `decision`, `primary_decision_maker`).
  - ⛔ **`addComment` is NOT available** on this SOAP endpoint (`Procedure 'addComment' not present`) — only `addCommentReply` (needs an existing `CommentID`). So a *top-level* comment on a fresh proof cannot be created via Fusion Custom API Call; it needs the REST API (`POST /proofs/{token}/comments`) — reachable with just a Workfront API key via the correction in §3, no `authtoken` required. For demo data, **create + reviewer + decision** is the fully-automatable set; comments are a manual/REST-gated add-on.

**Verified working flow (2026-07-03, live Fusion run):**
1. `http:ActionGetFile` → `data` (IMTBuffer) + `fileName`.
2. `workfront-proof:uploadFile` (map `data` + `fileName`) → returns the file **hash** (text). *Required* — Create Proof's `Hash` rejects a raw buffer ("Buffer can't be converted to text").
3. `workfront-proof:createProof` — `Hash: ["{{upload.hash}}"]`, `SourceName: ["{{1.fileName}}"]`, required booleans, **no `Recipients`** (the raw-JSON collection throws "Collection can't be converted to text" — leave it empty; Create Proof **auto-adds the connection owner as a reviewer**).
4. `customApiCall` `getProofReviewers`, `bodyXML=<FileID>{{createProof proof id}}</FileID>` → output `body.data.item[]` array with `id` (the RecipientID), `file_id`, `email`, `role`, `decision`, `stage_id`.
5. `customApiCall` `updateProofReviewer`, `bodyXML=<RecipientID>{{4.body.data.item[].id}}</RecipientID><RecipientDecision>Approved</RecipientDecision>` → flips the reviewer's `decision` empty → `Approved`.

Net: create + reviewer + decision are fully automatable via Fusion; only original top-level comments are not (no SOAP `addComment`) — post those via ProofHQ REST with an API-key-minted session (§3). See `examples/fusion/06-demo-proof-generator.json`.

---

## Current-state caveats (2026)

- **Standalone Workfront Proof** licenses stopped renewing ~Jan 2024. That is the separate standalone product — the **embedded proofing engine inside Workfront still runs**, and every API above still functions.
- Workfront is mid-migration to **Unified Approvals** (a.k.a. New Document Approvals, phased rollout from July 2025), plus an **AI Reviewer** and **Adobe Express** markup integration. Adobe has published a "Fusion remediation for unified approvals" guide — existing Fusion proof scenarios may need updates as this lands.
- **Net for automation:** `setDocumentReviewerDecision` (decisions) is core Workfront API and worth *trying* first — but it is unverified and `403`'d on the one live attempt (§3), so keep the ProofHQ REST / Fusion decision path as the fallback. **Proof *creation*, however, does not work via the main REST API** (verified no-op, §1) — route creation through the ProofHQ API or Fusion's Create Proof module regardless of the unified-approvals migration.

---

## Recommended demo recipe (fabricating proof activity)

1. Upload a valid file (real image/PDF) → get `DOCU` + `DOCV` IDs. (Verified: `POST /upload` → `POST /document`.)
2. **Create the proof via ProofHQ (`POST rest.proofhq.com/api/v1/proofs`) or Fusion's Create Proof module — NOT `document/createProof`, which no-ops (§1).** Poll `docv.proofStatus` until `success`.
3. For each fake reviewer, `docv/<id>/setDocumentReviewerDecision` with a decision + optional `comment` → decision history in `PRFAPL` and proof-decision reports. _(setter not yet round-trip-verified — see §2.)_
4. Only if you need visible markup or threaded comments: bridge to ProofHQ — `getProofingTokens` → viewer RPC `startup` → `sessionId` (cookie-free, Workfront API key only; [`16-proofhq-soap-catalog.md`](16-proofhq-soap-catalog.md) §6.1) → `POST /proofs/{token}/comments`, attaching a `drawings[]` array for visible markup (§6.2 — verified `201` create / `204` delete). **There is no SOAP `addComment`** (`Procedure 'addComment' not present`); Fusion's Custom API Call is only a SOAP envelope wrapper, so it can create neither a top-level comment nor any markup.
5. Verify: `prfapl/search` rows (`approverDecision`, `decisionDate`, `approverID`) and `docv.proofDecision`.

Two hard prerequisites bear repeating: proofing must be **licensed/enabled** on the demo tenant, and each proof needs a **real, valid source file**. And the creation step is the crux — budget time to get ProofHQ or Fusion auth working, since the one-call REST path is a dead end.

---

## Sources

- Live `/metadata` on a live production tenant (DOCU, DOCV, PRFAPL) — 2026-07-02.
- Live test on a live production tenant — 2026-07-03: verified `createProof`/`createProofRest` no-op; harvested real `proofDecision`/`approverDecision`/`proofStatus` enum values from 82 proofs; verified upload→document flow; probed `getProofingTokens` (PUT) token shape and `mediaViewerApi`; fingerprinted the `rest.proofhq.com/api/v1/authorize` contract; confirmed the Integrations-tab/Public-API and internal `/proof/ajax` cookie+XSRF auth realities.
- Adobe: [Add advanced proofing options with the Workfront API](https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/tips-troubleshooting-apis/api-create-proof-options-json), [The Workfront Proof API](https://experienceleague.adobe.com/en/docs/workfront/using/workfront-proof/wf-proof-integrations/wf-proof-api/workfront-proof-api), [Workfront Proof modules (Fusion)](https://experienceleague.adobe.com/en/docs/workfront-fusion/using/references/apps-and-their-modules/adobe-connectors/workfront-proof-modules), [Configure approval decision options](https://experienceleague.adobe.com/en/docs/workfront/using/workfront-proof/wf-proof-account-admin/account-settings-in-wf-proof/configure-approval-decision-in-wp).
- [ProofHQ REST API (rest.proofhq.com)](https://rest.proofhq.com/), [ProofHQ SOAP addComment](https://api.proofhq.com/home/proofs/addcomment.html).
- Community: [Comment on proof via API](https://experienceleaguecommunities.adobe.com/adobe-workfront-fusion-24/comment-on-proof-via-api-143113).
