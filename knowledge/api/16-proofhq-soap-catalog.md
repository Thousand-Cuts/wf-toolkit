# 16 — Workfront Proof (ProofHQ) SOAP API: full surface catalog

Complete traversal of the legacy Workfront Proof SOAP API at `soap.proofhq.com`. Companion to [`15-proofing.md`](15-proofing.md), which covers *how to drive proofing end-to-end* across the three surfaces; **this file is the reference catalog of the SOAP surface itself** — every operation, its signature, and what it can and cannot do.

**The headline:** the SOAP surface is **exactly 90 operations, with no hidden methods** (proven, §2), and **none of them can post proof markup** (arrows, boxes, lines). Markup is REST-only — the verified recipe is in §6.

**Signature markers:** `✅✅` = call-verified authenticated (returned real data, 2026-08-07 read sweep) · `✅` = call-verified in the 2026-07-03 pass (`15-proofing.md`) · `🔒` = exists but returned a permission fault on the non-admin test account (needs admin rights) · unmarked = existence-proven (WSDL + fault oracle), behaviour not yet exercised.

---

## Verification status

| Claim | How verified | Date |
|---|---|---|
| 90 operations in the WSDL | Parsed `soap.proofhq.com/soap?wsdl` (181 KB) | 2026-08-06 |
| **No hidden methods beyond the WSDL** | 125 candidate names probed via fault oracle → 0 hits | 2026-08-06 |
| **All 85 probeable WSDL ops exist live** | Fault oracle, 85/85 non-"not present" | 2026-08-06 |
| Fault oracle itself is sound | 8/8 known-good detected; gibberish correctly absent | 2026-08-06 |
| SOAP cannot post markup | No method exists; Adobe doc-site states markups unsupported | 2026-08-06 |
| **Markup IS postable via REST** | Live: 5 types posted, read back, deleted | 2026-08-06 |
| **Cookie-free ProofHQ REST session** | Live, API-key only, on a live production tenant | 2026-08-06 |
| **REST surface is 136 ops; session is proof-scoped** | 58 GETs probed live, 42×`200`; `/authorize/user` reports `context: recipient` | 2026-08-06 |
| Argument signatures (all 90) | Extracted from WSDL message parts | 2026-08-06 |
| **25 SOAP reads call-verified authenticated** | `doLogin` + 24 reads returned real data on a partner-sandbox proof account | 2026-08-07 |
| **Account tier is non-admin (Creator)** | Directory reads OK; account-config / billing / satellite / `decodeProofID` → `403` | 2026-08-07 |
| **Callback (webhook) `Type` enum recovered** | 17 live event types read from `getProofCallbacks` | 2026-08-07 |

⚠️ **Verification tier is per-operation.** The **reads** in §3–§4 were call-verified authenticated on 2026-08-07 (see the ✅✅ list below); the earlier ✅ marks are from the 2026-07-03 pass in `15-proofing.md`. **Writes and account-provisioning ops remain schema/existence-verified only** — they were deliberately not exercised (no mutation of the live account). Everything unmarked rests on the WSDL + fault-oracle existence proof.

**Call-verified authenticated (2026-08-07, read sweep, `doLogin` session):** `doLogin`, `checkSession`, `getAllProofs`, `getOpenProofs`, `getClosedProofs`, `getLateProofs`, `getProofsByOwnership`, `getProofDetails`, `getProofStatus`, `getProofReviewers`, `getProofComments`, `getProofURL`, `getProofVersions`, `getProofTags`, `getProofEmbedCode`, `getProofDownloadURL`, `getActivity`, `getProofCallbacks`, `getActions`, `getTags`, `getWorkspaces`, `getOwners`, `getUsers`, `getPeople`, `getPeopleAccounts` — 25 ops, real data returned.

**Privilege-gated on this account (returned `403`/permission fault, so they exist but need higher rights):** `getAccountDetails` ("no access to this account"), `getBillingPlans` ("Creators and Billing administrator rights required"), `getAccountCallbacks` ("no permissions to access settings"), `getSatelliteAccounts`, `decodeProofID` ("user does not have permission"). See the permission-tier note under §4.11.

---

## 1. Endpoint and auth

- **Endpoint:** `https://soap.proofhq.com/soap.php` (SOAP 1.1, RPC style). `…/soap` resolves identically.
- **WSDL:** `https://soap.proofhq.com/soap?wsdl`
- **Namespace:** `https://soap.proofhq.com/` · **SOAPAction:** `https://soap.proofhq.com/<methodName>`
- **Regions:** US `soap.proofhq.com`, EU `soap.proofhq.eu`. Accounts are region-scoped — the same credential returns different faults per region.

Two ways in:

| Method | Credential | Notes |
|---|---|---|
| `doLogin(Login, Password)` ✅ | ProofHQ **account password** | Works without the Public API toggle. Returns `<session>` + account limits. |
| `getSessionId(EmailAddress, AuthToken)` | ProofHQ **API authtoken** | Token-based alternative; likely gated behind the same Public-API/Integrations toggle as REST. Not yet exercised. |

The session renews on each call; `checkSession(SessionID)` tests liveness and `doLogout` ends it.

### Fault codes (observed live)

| Code | Meaning |
|---|---|
| `303` | Log-in details not valid |
| `305` | Invalid Session ID |
| `307` | **Account is locked** — brute-force lockout is real; see `setAccountPasswordSettings` (`BruteforceAttempts`, `BruteforceLockTime`) |
| `400` | Required parameter missing |
| `SOAP-ENV:Server` + `Procedure 'X' not present` | Method does not exist |

---

## 2. Traversal technique: the fault oracle

The endpoint distinguishes *unknown method* from *known method, bad session* **before authenticating**, which makes the whole surface enumerable with no credential at all:

```bash
# Unknown method  → SOAP-ENV:Server "Procedure 'zzzNotAMethod' not present"
# Known method    → 305 "Invalid Session ID."
```

Send any method name with a junk `SessionID` and read the fault. This is the SOAP analogue of walking `/metadata` on the main REST API.

**Result of the sweep (2026-08-06):** 125 plausible-but-undocumented names probed — every comment/markup verb (`addComment`, `addAnnotation`, `addMarkup`, `addArrow`, `addBox`, `addShape`, `addPin`, …), decision verbs, workflow/stage verbs, archive/copy/share verbs, reporting verbs — **zero hits**. Controls confirmed the oracle works (8/8 real methods detected, gibberish rejected).

> **Conclusion: the WSDL is the complete surface.** Unlike the main Workfront REST API — where `/metadata` exposes actions the docs never mention — ProofHQ SOAP hides nothing. Do not go looking for a secret markup verb; §6 explains what to use instead.

Conversely, all 85 probeable WSDL ops answered `305` (not "not present"), so **the WSDL has no stale entries** either. Three of the five skipped ops (`doLogin`, `getSessionId`, `orderSampleProof`) take no `SessionID` at all, so a junk-session probe would have exercised them for real instead of returning `305`. The other two, `createAccount` and `createSatelliteAccount`, do take `SessionID` as their first argument (§4.12) but were skipped as account-provisioning calls, to keep the sweep free of side effects.

> **Historical note:** `addComment` **is** documented on `api.proofhq.com` but is **not present** on the live service — the doc site is stale. That page also explicitly states *"Proof markups"* are unsupported for the method, so even the documented-but-absent verb never did markup.

---

## 3. What `15-proofing.md` already covered

These 16 are the operations `15-proofing.md` touches. **Verification tier is per-operation — read the markers, not a single summary sentence.**

- **Call-verified live (2026-07-03):** `doLogin` ✅, `getAllProofs` ✅, `getProofDetails` ✅, `getProofStatus` ✅, `getProofReviewers` ✅, `getProofComments` ✅, `getProofURL` ✅ (raw SOAP reads), and `updateProofReviewer` ✅ — the decision path, exercised via Fusion's Custom API Call, which flipped a reviewer's decision to `Approved`.
- **Called and blocked:** `createProof` ⛔ (fault `400`, missing `Hash`), `doUpload` ⛔ (proprietary attachment encoding). Existence proven; capability not.
- **Named but never called:** `addProofReviewer`, `addCommentReply`, `setCommentAction`, `getCommentAction` — cited from the WSDL, or appearing only as steps in `15-proofing.md`'s hypothetical "raw-API flow (once `doUpload` is solved via an SDK)" — and `deleteProof`, which appears there solely as that flow's "clean up a test" step. `getProofVersions` is not mentioned in `15-proofing.md` at all; like the other 74, its existence rests on the 2026-08-06 fault-oracle sweep.

The remaining **74** are catalogued below.

---

## 4. Capability catalog (the 74 undocumented operations)

### 4.1 Webhooks / callbacks — the biggest genuinely new capability

Nothing anywhere else in the toolkit exposes push notification from proofing. Fusion's "Watch Proofs" trigger polls; this does not.

```
setProofCallback(SessionID, FileID, Type, Url, RetryInterval)   -> SOAPCallbackObject
setAccountCallback(SessionID, Type, Url, RetryInterval)         -> SOAPCallbackObject
getProofCallbacks(SessionID, FileID)              ✅✅          -> SOAPCallbackObjectArray
getAccountCallbacks(SessionID)                    🔒 admin      -> SOAPCallbackObjectArray
```

`SOAPCallbackObject` = `{type, url, interval, proof_name}`. Scope is per-proof or account-wide, with a server-side retry interval. `getProofCallbacks` is **call-verified** — it returned 17 configured callbacks on a live proof; `getAccountCallbacks` is admin-gated (`"no permissions to access settings"` on the Creator-tier test account, see §4.11).

**The `Type` enum — recovered live 2026-08-07** (the WSDL types it as a bare `string`). A proof with a full callback set exposed all 17 event types, each usable as the `Type` argument to `setProofCallback`/`setAccountCallback`:

`comments`, `comment_updated`, `actions`, `decisions`, `stage_decision`, `overall_decision`, `decision_maker_changed`, `active_stage_changed`, `state`, `opened`, `processed`, `trashed`, `deleted`, `archived`, `unarchived`, `proof_owner_changed`, `proof_deadline`.

`interval` was `1` on every configured callback. An account-level callback on `overall_decision` (or `decisions`) is the cleanest "notify me when any proof is decided" integration available — a genuine push alternative to Fusion's polling *Watch Proofs* trigger. (Registering one is a `setAccountCallback` **write** and needs settings/admin rights; not exercised here.)

### 4.2 Proof lifecycle

```
updateProof(SessionID, FileID, OwnerID, Name, Subject, Message, WorkspaceId,
            EnableSubscriptions, EnableSubscriptionsValidation, DefaultEmailNotifications,
            DefaultRole, AuthorizedOnly, EnableAutoclose, EnableOneDecision, EnableDownload,
            EnableTeamURL, EnableEmbedPlayer, Show*Link…, CustomLinkUrl, CustomLinkLabel,
            SWF, ShowDashboardFunctions, PrimaryDecisionMakerReviewerID) -> SOAPFileObject
lockProof(SessionID, FileID)     -> boolean
unlockProof(SessionID, FileID)   -> boolean
createProofVersion(SessionID, ParentFileID, OwnerID, Hash, …)  -> SOAPFileObject
createFile(SessionID, OwnerID, Hash, Name, SourceName, Subject, Message,
           Deadline, Recipients, WorkspaceId, BatchID, SWF, SuppressNewFileNotification)
```

`updateProof` is the broadest write in the API — it retargets owner, workspace, sharing, download/embed permissions, and **`PrimaryDecisionMakerReviewerID`** after creation. `EnableAutoclose` / `EnableOneDecision` are the only verified programmatic **write** path for those two workflow behaviours (`setAccountProofingDefaults` carries only messages and button labels). They are, however, **readable** over ProofHQ REST — `GET /proofs/{token}/settings` → `isAutoLockingEnabled` / `isOneDecisionRequiredEnabled` (per proof) and `GET /settings/proofing` → `autoclose` / `oneDecision` (account defaults for new proofs), both `200` in the 2026-08-06 sweep. REST also declares `PUT`/`PATCH /proofs/{token}`, so a REST write path plausibly exists; untested for these fields.

> ⛔ **`createFile` and `createProofVersion` both require `Hash`** — same wall as `createProof`. `Hash` comes only from `doUpload`, whose attachment encoding is proprietary. **The July finding stands: there is no create-from-URL and no hand-rollable file→proof path.** Use Fusion's Create Proof module or a real SOAP SDK.

### 4.3 Query / list surface

```
getOpenProofs   (SessionID, StartFrom, SearchQuery, ItemsPerPage) ✅✅ -> SOAPFileObjectArray
getClosedProofs (SessionID, StartFrom, SearchQuery, ItemsPerPage) ✅✅ -> SOAPFileObjectArray
getLateProofs   (SessionID, StartFrom, SearchQuery, ItemsPerPage) ✅✅ -> SOAPFileObjectArray
getProofsByOwnership(SessionID, UserID)                           ✅✅ -> SOAPFileObjectArray
getProofsByListView(SessionID, ListViewID, StartFrom, ItemsPerPage,
                    ExcludedMediaTypes, SendArchivedProofs)       -> SOAPFileListViewCollectionObject
decodeProofID(SessionID, EncodedProofID)                          🔒 -> int
```

`getLateProofs` is a ready-made overdue-review report with no filter construction (call-verified; `0` late on the test account). `getProofsByListView` mirrors the UI's saved list views (`SendArchivedProofs` is the only route to archived proofs found anywhere). List rows carry `{file_id, type, filename, filesize, version, versions, upload_time, uploader, …}`.

> 💡 **`decodeProofID` solves the two-ID-systems footgun — *if your account has the right.*** It converts an encoded proof ID to the numeric `FileID`. **But it is privilege-gated:** it returned `403 "the user does not have permission to perform this action"` on the Creator-tier test account (§4.11). When it's unavailable, ProofHQ REST is the fallback — `GET /proofs/{token}/versions` exposes the numeric `id` beside the token (§6.5).

### 4.4 Activity / audit

```
getActivity(SessionID, FileID, Offset) ✅✅ -> SOAPFileActivityObjectArray
```

`SOAPFileActivityObject` = `{file_id, filename, created_at, action, details}` (**call-verified 2026-08-07** — returned the expected fields) — a paged per-proof audit trail. No equivalent exists in the main Workfront REST API (`PRFAPL` gives decisions, not an event log) — but this is **not** the platform's only proof audit feed. **ProofHQ REST exposes `GET /proofs/{token}/activity`** (verified `200`, cookie-free, §6.1) with richer per-event structure: `{created, person, action (int), actionLabel, detailsPhrase, detailsParams[]}`, though it drops `file_id`/`filename` (implicit in the token). **Prefer the REST feed** when all you hold is a Workfront API key. Reach for SOAP `getActivity` only when you already hold an account-level SOAP session and want to sweep many `FileID`s with `Offset` paging, since the REST route costs one session mint per proof. Fusion also ships a **Watch Proof Activity** trigger.

### 4.5 Embed codes

```
getProofEmbedCode(SessionID, FileID)                        -> string
getProofEmbedCodes(SessionID, FileID)                       -> SOAPFileEmbedCodeObjectArray
getProofReviewerEmbedCode(SessionID, FileID, ReviewerID)    -> string
getPersonalProofEmbedCode(SessionID, FileID)                -> string
```

Embed the proof viewer in an external portal. The per-reviewer variant yields a link already bound to a reviewer identity — useful for client-facing review portals without provisioning Workfront licences.

### 4.6 Downloads and thumbnails

```
getProofDownloadURL(SessionID, FileID)          -> string
getFileDownloadLink(SessionID, FileID)          -> string
getProofThumbnail(SessionID, FileID, Type)      -> SOAPImageObject
getCommentThumbnail(SessionID, CommentID)       -> SOAPImageObject
```

`getCommentThumbnail` renders the **markup region of a specific comment** as an image — the only way to *see* a markup without opening the viewer. Handy for digest emails or audit reports. (`Type` on `getProofThumbnail` is an `int` with undocumented legal values — size variant, presumably. Not the untyped `string` `Type` of the callbacks in §4.1.)

### 4.7 Comments (read/reply only)

```
getProofComments(SessionID, FileID)                       ✅✅ -> SOAPCommentObjectArray
getProofCommentReplies(SessionID, FileID, CommentID)      -> SOAPCommentReplyObjectArray
addCommentReply(SessionID, FileID, ReviewerID, CommentID, Reply) -> SOAPCommentReplyObject
setCommentAction(SessionID, CommentID, ActionID)          -> boolean
getCommentAction(SessionID, CommentID)                    -> SOAPActionObject
getActions(SessionID, AccountID)                          ✅✅ -> SOAPActionObjectArray
```

`getProofComments` is call-verified — rows carry `{id, reviewer_id, author, comment, created_at, replies_count, replies, url}`. `getActions` (also call-verified: 3 actions, `{actionID, action, enabled}`) returns the account's valid comment-action labels — call it first to get legal `ActionID`s for `setCommentAction`.

> ⛔ **No top-level comment creation and no markup.** SOAP can read comments, reply to existing ones, and label them. Creating an original comment — with or without markup — is REST-only. See §6.

### 4.8 Batches

```
createBatch(SessionID)                                        -> int
finishBatch(SessionID, BatchID)                               -> boolean
addBatchProofReviewers(SessionID, BatchID, Recipients)        -> boolean
```

Group several proofs into one reviewer notification instead of N separate emails. `createProof`/`createFile` both take a `BatchID`. Flow: `createBatch` → create proofs with that `BatchID` → `addBatchProofReviewers` → `finishBatch` (which sends).

### 4.9 Reviewers

```
addProofReviewers(SessionID, FileID, Recipients)   -> boolean          # bulk
deleteProofReviewer(SessionID, ReviewerID)         -> boolean
```

The bulk `addProofReviewers` (plural) complements the singular `addProofReviewer` (never called — see §3); `deleteProofReviewer` removes a recipient. The `updateProofReviewer` half of the pair is the call-verified decision path from `15-proofing.md`.

### 4.10 Tags and workspaces

```
addTag(SessionID, TagName) -> SOAPTag       updateTag(SessionID, TagID, TagName) -> SOAPTag
deleteTag(SessionID, TagID) -> boolean      getTags(SessionID) -> SOAPTagArray
addProofTags(SessionID, FileID, TagID)      removeProofTags(SessionID, FileID, TagID)
getProofTags(SessionID, FileID) -> SOAPTagArray

createWorkspace(SessionID, ParentWorkspaceID, Name, Description, Client, Project, Personal)
updateWorkspace(…)   deleteWorkspace(SessionID, WorkspaceID)   getWorkspaces(SessionID)
```

Workspaces nest (`ParentWorkspaceID`) and carry `Client`/`Project`/`Personal` flags — a proofing-side organisational hierarchy independent of Workfront projects. These are the safest operations to smoke-test a credential with, since add→delete is fully reversible.

### 4.11 User administration

```
addUser(SessionID, AccountID, EmailAddress, FirstName, LastName, Position, PermissionsID,
        Password, ConfirmPassword, SendConfirmationEmail, OpenID, Timezone,
        ProductMarketingEmails, APIOnly)                       -> SOAPUserObject
updateUser(SessionID, UserID, …, PermissionsID, …, APIOnly)    -> SOAPUserObject
deleteUser(SessionID, UserID, NewOwnerID)                      -> boolean
activateUser / deactivateUser(SessionID, UserID)               -> boolean
updateUserEmail(SessionID, UserID, NewEmail, Confirm)          -> boolean
updateUserPassword(SessionID, UserID, Password)                -> boolean
getUsers(SessionID, AccountID) ✅✅ / getUserDetails(SessionID, UserID)
findUsersByEmail(SessionID, EmailPhrase, AccountID)            -> SOAPUserObjectArray
getPeople(SessionID, Offset) ✅✅ / getPeopleAccounts ✅✅ / getPeopleGroups ✅✅ / getOwners ✅✅
updateContactEmail(SessionID, OldEmail, NewEmail)              -> boolean
```

A complete proofing-side user directory, separate from Workfront users. **The read side is call-verified** — `getUsers` (116 users), `getOwners` (58), `getPeople` (72), `getPeopleAccounts` (56), `getPeopleGroups` (0) all returned live directory data on the test account. Rows carry `{id, email, openid, first_name, last_name, position, status, permissions}`. Note **`APIOnly`** on add/update — provisioning a service account is a first-class concept. `deleteUser` requires `NewOwnerID` to reassign owned proofs.

> ⚠️ **The write side is destructive and identity-affecting.** `updateUserPassword` changes another user's password; `deleteUser` reassigns their proofs. Treat this whole group as admin-only and never exercise it against a client tenant without written authorisation. (Not exercised here — reads only.)

> 🔒 **Account-tier reality — the proof account used for this sweep is a non-admin (Creator) user, not an account admin.** This matters because §4.11–§4.12 read as a flat capability list, but the sweep found a clear privilege boundary. **Directory reads work** for an ordinary user (`getUsers`/`getOwners`/`getPeople*` all returned data). **Account-configuration reads are gated:** `getAccountDetails` → `403 "you do not have access to this account"`; `getBillingPlans` → `403 "Creators and Billing administrator rights required"`; `getAccountCallbacks` → `"no permissions to access settings"`; `getSatelliteAccounts` → permission fault; `decodeProofID` → `403`. So the account-admin and satellite-account capabilities in §4.12, the account-level webhook management in §4.1, and every write in §4.11 require an **account-administrator** ProofHQ login — a standard Creator (which is what a consultant's day-to-day proof account usually is) will `403`. Budget for a genuine admin credential before promising any account-level automation.

### 4.12 Account administration

```
getAccountDetails(SessionID, AccountID)     updateAccount(SessionID, OrganisationName, Street, …)
setAccountProofingDefaults(SessionID, OnLoadMessage, OnDecisionMessage, ConfirmButton, CancelButton)
setAccountPasswordSettings(SessionID, PasswordLength, LowercaseCharacters, UppercaseCharacters,
        NumericCharacters, SymbolCharacters, CharactersRepetition, PasswordLifetime,
        BruteforceAttempts, BruteforceLockTime)
getSatelliteAccounts / createSatelliteAccount(SessionID, Name, Timezone, Promocode)
getBillingPlans(SessionID)  updateBillingPlan(SessionID, PlanID, AccountID)
createAccount(SessionID, Timezone, OrganisationName, EmailAddress, …)
```

`setAccountProofingDefaults` customises viewer-facing copy (the on-load and on-decision messages, button labels) — a white-labelling hook with no UI equivalent in embedded Workfront proofing. **Satellite accounts** are a multi-tenant construct (agency managing sub-brands) not surfaced in Workfront at all.

### 4.13 Stubs — take only `SessionID`, return `boolean`

```
addProofLinks(SessionID)   deleteProofLink(SessionID)   getProofLinks(SessionID)   setProofMenus(SessionID)
```

These declare no meaningful parameters, so they cannot do anything useful as declared. Almost certainly vestigial or internal. **Do not build on them.**

### 4.14 Miscellaneous

```
orderSampleProof(Email, FirstName, LastName, OrganisationName) -> boolean   # unauthenticated marketing endpoint
checkSession(SessionID) -> boolean       doLogout(SessionID) -> boolean
```

---

## 5. Can SOAP post markup? No.

Definitively answered, three independent ways:

1. **No such method exists.** All 90 WSDL operations enumerated; none accepts drawing, shape, coordinate, or annotation parameters. The only comment writes are `addCommentReply` (text `Reply` string) and `setCommentAction` (a label).
2. **No hidden method exists.** 125 candidate verbs probed against the live fault oracle — `addMarkup`, `addAnnotation`, `addDrawing`, `addShape`, `addArrow`, `addBox`, `addLine`, `addRectangle`, `addEllipse`, `addFreehand`, `addHighlight`, `addPin`, `addStamp`, and 100+ more — **zero hits**.
3. **Adobe says so.** The `addComment` doc page (for a method that isn't even live) explicitly lists *"Proof markups"* as unsupported.

The same applies to Fusion's Workfront Proof **Custom API Call** module, which is just a SOAP envelope wrapper — it inherits this limitation exactly.

---

## 6. Markup IS postable — via ProofHQ REST (verified live)

Arrows, boxes, lines, freehand, and highlights are all postable through `POST /proofs/{token}/comments` using the `drawings[]` array. **Verified end-to-end 2026-08-06** on a live production tenant: five markup types posted (HTTP `201`), read back with geometry intact, then deleted (HTTP `204`, read-back confirmed clean).

### 6.1 Getting a session — cookie-free, API key only

> ✅ **This corrects `15-proofing.md`.** That file states there is "no public-API-key path" to a ProofHQ session and that the viewer RPC uses "a different session token" than `rest.proofhq.com`. **Both are wrong.** The viewer RPC's `startup` method mints a `sessionId` that authenticates `rest.proofhq.com` directly, using nothing but a Workfront API key. No web-session cookie, no Adobe OAuth, no Public-API toggle, no ProofHQ password.

```
1. PUT  $$HOST/attask/api/v17.0/docv/<DOCV_ID>/getProofingTokens?apiKey=<KEY>
        body: versionID=<DOCV_ID>
        → { token, codetodecode, mediaViewerApi }

2. POST <mediaViewerApi>index.php        (us.my.workfront.com/proof/rpc/ on a US tenant)
        headers: tcmssubdomain: <tenant-subdomain>, tcmstenantid: <tenant-uuid>
        body:    {"method":"startup","proofingCode":"<codetodecode>","token":"<token>"}
        → { sessionId }

3. Any rest.proofhq.com/api/v1/... call   (rest.proofhq.eu for an EU-region account)
        headers: sessionid: <sessionId>, tcmssubdomain: …, tcmstenantid: …
```

Take the RPC host from `mediaViewerApi` rather than hardcoding `us.` — it names the tenant's proofing region. ProofHQ's own OpenAPI declares region-split REST bases (`rest.proofhq.com` US, `rest.proofhq.eu` EU); only a US-region tenant has been observed here.

`tcmstenantid` comes from the tenant's `wf-auth` JWT (one-time capture per tenant). The session is scoped to the proof whose token minted it.

**This only works on proofs that already exist** — it does not solve creation. Proof creation still requires Fusion or the cookie path (`15-proofing.md` §1).

### 6.2 The drawing object

Reverse-engineered from **43 real UI-created markup comments (45 drawings) found on 10 proofs**, harvested by sweeping up to 40 proofed document versions, then confirmed by round-trip. The published OpenAPI spec types `drawings` as an untyped `[{}]`, so this is the only accurate record of the shape. The sample is heavily skewed — 38 of the 45 drawings are `RECTANGLE`, and all 45 use `color: 16711680` — so treat the field list below as an attested minimum, not an exhaustive schema.

```jsonc
{
  "type": "RECTANGLE",          // see enum below
  "color": 16711680,            // 24-bit integer, NOT a hex string (16711680 = 0xFF0000 red)
  "alpha": 1,                   // 1 for strokes; 0.4 observed for highlights
  "thickness": 3,               // line weight
  "points": [ {"x":18,"y":-601}, {"x":247,"y":-503} ],   // two corner/end points
  "page": 1,                    // 1-indexed
  "pages": [0],                 // 0-indexed — BOTH fields, different bases
  "minMax": {"minx":18,"maxx":247,"miny":-601,"maxy":-503},
  "width": 229, "height": 98,   // derived from points
  "x": 433, "y": 174,           // anchor, independent of points
  "index": 0,
  "isNew": true, "editable": true, "isBeingEdited": false,
  "handleTypes": "boundingBox",
  "responseClass": "drawingResponse"   // present on read; not required on write
}
```

Type-specific extras:
- **`FREEHAND`** adds `pathPoints[]` — the full stroke path as float `{x,y}` pairs (round-trips intact; 11-point path verified).
- **`TEXT_HIGHLIGHT`** / **`TEXT_REPLACE`** add `rectangles[]` — `{x, y, width, height, angle}` per covered text run; every sample carries a single rectangle at `{x: 0, y: 0}` sized to the text line (height ≈13–15). **Alpha differs by type:** `TEXT_HIGHLIGHT` is `0.4` (2/2 samples, like plain `HIGHLIGHT`), `TEXT_REPLACE` is `1` (2/2, like the stroke types).

Post it as:

```json
POST /api/v1/proofs/{token}/comments
{ "text": "Tighten this headline", "page": 1, "drawings": [ { …drawing… } ] }
```

### 6.3 Type enum

**Observed in real UI-created markup** (therefore certain to render), with sample counts: `RECTANGLE` (38), `FREEHAND` (2), `TEXT_HIGHLIGHT` (2), `TEXT_REPLACE` (2), `HIGHLIGHT` (1).

**Round-trip verified** (posted via REST, read back with geometry intact, then deleted): `RECTANGLE`, `HIGHLIGHT`, `FREEHAND`, `ARROW`, `LINE` — **five** types. `TEXT_HIGHLIGHT` and `TEXT_REPLACE` are **read-verified only**: they appear in harvested UI markup, so they certainly render, but neither was ever posted — their write path, including the `rectangles[]` array they carry, is unexercised.

> ⚠️ **The server does not validate `type`.** A probe posting `NOTREAL_XYZ` was accepted and echoed back unchanged, as were `ELLIPSE`, `CIRCLE`, `POLYGON`, `CLOUD`, `CALLOUT`, `STAMP`, `BOX`, `SQUARE` and others. **Acceptance proves storage, not rendering** — the viewer decides what it can draw, and an unrecognised type most likely renders as nothing while still counting as a comment. Stick to the five round-trip-verified names when writing; `TEXT_HIGHLIGHT`/`TEXT_REPLACE` are safe to *read* but their write payload is untested. `ARROW`/`LINE` are the inverse case — write-verified, yet absent from all 45 harvested UI drawings; they are documented Workfront drawing tools, but their *rendering* was not visually confirmed in this pass.

### 6.4 Gotchas

- **`color` is an integer, not a hex string.** `16711680` = red. Passing `"#FF0000"` is untested and likely silently wrong.
- **`page` is 1-indexed but `pages[]` is 0-indexed** in the same object. Set both.
- **Coordinates can be negative** — real samples carry `y: -601`. The origin is not the top-left of the page as rendered; treat coordinates as viewer-space and copy geometry from an existing markup on the same proof rather than computing from page dimensions.
- **`rest.proofhq.com` writes sometimes return `500` but succeed** (`15-proofing.md` §3). In this pass comment creation cleanly returned `201` and deletion `204`, so the 500 behaviour is not universal — but **always verify by read-back** regardless.
- ⚠️ **Deletion works, but it is NOT reversible in the audit trail.** `DELETE /proofs/{token}/comments/{commentToken}` → `204`, verified by read-back: the comment really is gone from the comment list. The **event log is not**. `GET /proofs/{token}/activity` permanently retains both the `newComment` (action `15`) and `commentDeleted` (action `67`) events, each attributed by name in `person`, with the delete carrying name *and* email in `detailsParams` and the create carrying **the comment text**. Verified live: a test proof whose comment list was restored to its original 2 entries still showed 24 `newComment` + 26 `commentDeleted` events naming the tester. **No undo exists** — none of the 136 ProofHQ REST operations or 90 SOAP operations is a restore/undelete verb. Trial markup only on a throwaway proof on your own tenant, never on a client's.

---

### 6.5 The rest of the ProofHQ REST surface (verified 2026-08-06)

`POST /proofs/{token}/comments` is one of **136 operations**. The full list is only recoverable from the Redoc page state embedded in `rest.proofhq.com`'s HTML — `GET /swagger/openapi.json` is a `404` unauthenticated. 58 GETs were probed live; **42 returned `200`**.

**Session scope is the thing to understand first.** `GET /authorize/user` reports what you actually hold:

```json
{"context":"recipient","permissions":{"can_create_proofs":true,"can_create_files":true,
 "can_create_folders":true,"can_edit_all_proofs":true},
 "userToken":"…","accountToken":"…","contactToken":"…","proofToken":"…"}
```

The RPC-minted session is **proof-scoped**, not account-scoped — bound to the `proofToken` that minted it. Everything *about that proof* works; collection and global paths fail with `{"error":"Not supported in this context"}` regardless of the permissive-looking `permissions` block.

| Reachable with the cookie-free proof-scoped session | Requires an account-context session (password / `authtoken` / cookie) |
|---|---|
| `/proofs/{t}` · `/activity` · `/comments` (+replies, attachments) · `/recipients` (+`/decision`, `/urls`) · `/stages` (+`/{s}`, `/decision`, `/recipients`) · `/versions` · `/sourcefiles` · `/urls` · `/controls` · `/settings` · `/customfields` · `/decision` · `/proofingCode` · `/update` · `/export/excel` · plus that proof's `/accounts/{a}/…` settings, limits, membership, domains, devices · `/contacts` · `/customdata` · `/folders` · `/users` · `/settings/proofing` | `GET`/`POST /proofs` (list, **create**) · `POST /upload` · `POST /convert` · `POST /crawler` (web capture) · `/tags` · `/proofs/{t}/tags` · `/workflow/templates` · `/settings/limits` · `/accounts` · `/basecamp/*` |

**Proof creation is still not reachable cookie-free** — `POST /proofs`, `/upload`, and `/convert` all return `403 "Not supported in this context"`. The §1 finding stands: creation needs Fusion or the cookie path.

Capabilities worth knowing, none of which appear elsewhere in this toolkit:

- **Proof workflow stages ARE exposed** — `GET /proofs/{t}/stages`, `/stages/{s}`, `/stages/{s}/decision`, `/stages/{s}/recipients` all `200`, returning `{token, name, number, position, parentPosition, activateOn, activateOnDecision, activateOnDate, lockOn, deadline*}`. Writes are declared but untested: `POST /stages`, `PUT`/`PATCH /stages/{s}`, `POST`/`PUT /stages/{s}/recipients`. This does **not** contradict `15-proofing.md`'s "proof-workflow configuration is not exposed" — that claim is about the *main* Workfront REST API, where `/proofWorkflow/search` really does return `Unknown object type`. Different API.
- **The tenant's decision catalog is readable** — `GET /accounts/{a}/settings/decisions` → `{token, decision (int), name, displayName, isEnabled, hasReasons, hasPostMessage}`; observed `3`=Approved, `2`=Approved with changes, `4`=Not relevant, `0`=Pending. This settles `15-proofing.md` §2's open question about decision label casing: **don't guess a label — read the catalog and submit its `token`.** Also `/settings/decisionreasons`.
- **Comment-action labels** — `GET /accounts/{a}/settings/actions` → `[{token, name}]` (the REST equivalent of SOAP `getActions`; feeds `setCommentAction`).
- **One-call comment export** — `GET /proofs/{t}/export/excel` returns a real XLS binary. No SOAP or main-REST equivalent. `POST /proofs/{t}/export/request/pdf` is also declared (untested).
- **Two REST answers to the two-ID-systems problem**, so SOAP `decodeProofID` isn't needed: `GET /proofs/{t}/versions` returns the numeric `id` (= Workfront `proofID` = SOAP `FileID`) beside the opaque token, and `GET /proofs/{t}/proofingCode` returns the `codetodecode` shape — letting a live session re-mint its own RPC `startup` without another Workfront call.

> ⚠️ **`GET /logout` is a GET that mutates state — it destroys your session.** This is a genuine trap when enumerating the API: an innocuous-looking read in an alphabetical sweep silently invalidated the session, and every subsequent call returned `401 "Session invalid"`, which looks exactly like a short TTL. **Exclude `/logout` from any sweep.** The session is not in fact short-lived — a 30-second heartbeat held `200` for 20+ consecutive calls across 10 minutes, and 6-way concurrent use did not disturb it.

---

## 7. Practical guidance

**Use SOAP for:** account-level push webhooks (§4.1), embed codes (§4.5), batches (§4.8), workspace/tag structure (§4.10), `lockProof`/`unlockProof` (§4.2), and bulk user administration (§4.11) — none of which the main Workfront REST API exposes, and none of which has a dedicated Fusion module.

> 🔑 **Mind the account tier.** The 2026-08-07 sweep proved a hard privilege boundary: **proof-level reads and directory reads work for any authenticated user, but account-level configuration — webhook management (`setAccountCallback`/`getAccountCallbacks`), billing, satellite accounts, account details, and `decodeProofID` — needs an account-administrator ProofHQ login.** A consultant's ordinary proof account is typically Creator-tier and will `403` on all of those. Confirm you hold an admin credential before promising account-level automation (see §4.11).

Two qualifications. **"Via SOAP" includes Fusion's Custom API Call**, which wraps arbitrary SOAP operations (§5), so Fusion can reach anything in this catalog that way — though only `getProofReviewers` and `updateProofReviewer` have been call-verified through it. And two capabilities are deliberately absent from that list because other surfaces cover them natively: broader proof lifecycle writes (§4.2 — Fusion ships an **Update Proof** action) and the per-proof activity feed (§4.4 — Fusion's **Watch Proof Activity** trigger, plus ProofHQ REST's `GET /proofs/{token}/activity`).

**Do not use SOAP for:** creating proofs from a file (blocked on `doUpload`), creating top-level comments, or **any markup**.

**Use ProofHQ REST for:** comments, markup, decisions, recipients, workflow **stages**, and the per-proof **activity/audit** feed — all reachable cookie-free with just a Workfront API key (§6.1, §6.5).

**Use Fusion for:** proof *creation* from a file, and for durable unattended automation generally.

---

## Sources

- Live WSDL `https://soap.proofhq.com/soap?wsdl` — parsed 2026-08-06 (90 operations, all signatures).
- Live fault-oracle sweep against `soap.proofhq.com/soap.php` — 2026-08-06 (125 candidate probes → 0 hidden; 85/85 WSDL ops confirmed live; oracle controls passed).
- Live markup verification on a live production tenant — 2026-08-06 (43 UI markup comments / 45 drawings from 10 proofs, found by sweeping up to 40 proofed document versions; 5 types posted/read/deleted on test proof `147112693`; type-enum validation probe).
- Live REST sweep on the same tenant — 2026-08-06 (136 operations extracted from the embedded Redoc state; 58 GETs probed, 42×`200`; session-scope, `/logout`, and session-liveness findings).
- **Authenticated SOAP read sweep** — 2026-08-07, `doLogin` session on a partner-sandbox ProofHQ org (non-admin Creator user). 25 read ops returned live data; 5 account-config ops returned permission faults; the 17-value callback `Type` enum was recovered from `getProofCallbacks`. Reads only — no writes, no mutation of the account's proofs.
- Embedded OpenAPI (Redoc state) at [`rest.proofhq.com`](https://rest.proofhq.com/) — comment request/response schemas.
- Adobe: [ProofHQ SOAP `addComment`](https://api.proofhq.com/home/proofs/addcomment.html) (documents a method absent from the live service; states markups unsupported), [The Workfront Proof API](https://experienceleague.adobe.com/en/docs/workfront/using/workfront-proof/wf-proof-integrations/wf-proof-api/workfront-proof-api), [FAQ — Review proofs](https://experienceleague.adobe.com/en/docs/workfront/using/workfront-proof/get-started-wf-proof/wf-proof-faq/faq-review-proofs) (drawing tools: arrows, lines, rectangles, highlighting, freehand).
- Prior art in this repo: [`15-proofing.md`](15-proofing.md), `examples/api/proofing/create-demo-proof.sh`.
