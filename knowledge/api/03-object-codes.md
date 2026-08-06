# 03 — Object Codes (OBJCODEs)

Every object in Workfront has a short uppercase code (its OBJCODE) and a longer object name. The OBJCODE is what you use in:

- `EXISTS:N:$$OBJCODE=...` filters (in both text mode and API)
- Some action parameters and references that name an object by code
- Various places the API returns the object's type alongside its data

The longer object name (lowercased, camelCase as needed) is what typically appears in URL paths — but always verify the exact endpoint segment in the API Explorer rather than assuming a transformation.

## Full OBJCODE table

| OBJCODE | Object | Notes |
|---|---|---|
| `PROJ` | Project | The top-level work container |
| `TASK` | Task | Work item under a project |
| `ASSGN` | Assignment | Joins a task or issue to a user or role |
| `ISSUE` | Issue | Standalone issue or request |
| `OPTASK` | Issue / OpTask | Legacy name for Issue — many older filters still use OPTASK |
| `USER` | User | A person |
| `ROLE` | Job Role | The role users fulfill on assignments |
| `TEAM` | Team | A group of users |
| `PORT` | Portfolio | Container above projects |
| `PRGM` | Program | Sub-container under a portfolio |
| `HOUR` | Hour | A time entry |
| `EXPNS` | Expense | An expense entry |
| `DOCU` | Document | A document or attachment. Proof *creation* actions hang off here (`createProof`, `createProofRest`) — see `knowledge/api/15-proofing.md` |
| `DOCV` | Document Version | A version of a document. Proof *state* + decisions live here: fields `proofID`, `proofStatus`, `proofDecision`; actions `setDocumentReviewerDecision`, `getDocumentReviewerDecision`, `getProofingTokens`. URL segment `/docv/`. See `knowledge/api/15-proofing.md` |
| `PRFAPL` | ProofApproval | Read-only reporting join for proof decisions (`approverID`, `approverDecision`, `decisionDate`, `approverStage`, `isAwaitingDecision`, `documentVersionID`). **No write actions** — decisions are written via `DOCV/setDocumentReviewerDecision`. See `knowledge/api/15-proofing.md` |
| `TMPL` | Template | A project template |
| `TTSK` | Template Task | A task within a project template. URL segment is `/ttsk/`. See "Template task quirks" in `knowledge/api/11-tips-and-gotchas.md` — DELETE requires `?force=true`; `workRequired` is not writable via API |
| `TASSGN` | Template Task Assignment | Joins a TTSK to a user / role / team. **Not a top-level object** — POST/PUT directly to `/tassgn` returns "invalid objCode: null". Write via the parent TTSK's `updates={"assignments":[...]}` |
| `TPRED` | Template Task Predecessor | Predecessor link between two TTSKs on the same template. **Not a top-level object** — POST to `/tpred` returns "TPRED is not a top level object". Write via the successor TTSK's `updates={"predecessors":[...]}` |
| `LYTMPL` | Layout Template (Classic) | Legacy Workfront Classic layout templates; mostly the 6 Adobe stock per-license-type defaults on a modern tenant |
| `UITMPL` | Layout Template (New Experience) | Modern customer-built layout templates from the "Interface → Layout Templates" admin screen — **the one you almost always want** |

## Where you'll use OBJCODEs in API work

### In EXISTS query parameters

The text-mode EXISTS pattern works identically in API filter query strings:

```
GET /attask/api/v<version>/project/search
  ?EXISTS:1:$$OBJCODE=TASK
  &EXISTS:1:projectID=FIELD:ID
  &EXISTS:1:status=INP
  &EXISTS:1:status_Mod=eq
```

(URL-encode the special characters when you actually make the request — `$$`, `:`, and `=` inside parameter values need encoding.)

See `07-exists-in-api.md` for the full pattern.

### In `objCode` request fields

Some endpoints accept an `objCode` field in the body to disambiguate polymorphic relationships (e.g., a parameter that could reference either a task or an issue). The value is the OBJCODE from the table above.

### When returning mixed object types

Endpoints that can return more than one kind of object (e.g., search-across-objects endpoints) include the OBJCODE on each returned record so the caller can dispatch on type.

## A note on OPTASK vs ISSUE

`OPTASK` is the legacy code for an Issue (the object Workfront used to call "OpTask"). Internally the object is still often referred to as OpTask in the database and in field names like `optaskID`. In modern UI and documentation it's called "Issue." Both `OPTASK` and `ISSUE` may appear in your codebase — treat them as synonyms when reading older filters or scripts.

## A note on UITMPL vs LYTMPL (Layout Templates)

Workfront Layout Templates are split across **two separate REST objCodes** depending on which experience the template targets — this is the single biggest landmine in layout-template API work and the one that wastes the most time:

- **`UITMPL`** — Layout Template for the **new Workfront experience**. The customer-built templates surfaced in the modern "Interface → Layout Templates" admin screen live here. Endpoint: `/attask/api/v17.0/UITMPL/search`. Fields: `ID, name, description, customerID, groupID, entryDate, enteredByID, lastUpdateDate, extRefID` — **no collections** (no `linkedUsers`/`linkedRoles`/`linkedTeams`).
- **`LYTMPL`** — Layout Template for **Workfront Classic** (legacy). Endpoint: `/attask/api/v17.0/layoutTemplate/search`. On a modern tenant this typically returns only the 6 Adobe stock per-license-type defaults (`objObjCode: APGLOB`, names like "Default Layout Template - Plan License"). Has `linkedUsers/linkedRoles/linkedTeams` collections, but they're usually empty.

**Assignment fields on user / role / team / group:**
- `uiTemplateID` → assignment for new-experience UITMPL
- `layoutTemplateID` → assignment for Classic LYTMPL
- `effectiveLayoutTemplate` (reference, user object only) → server-resolved, but **only resolves LYTMPL**, not UITMPL. Returns null on modern tenants even when a UITMPL is assigned via role inheritance. Do not trust it as a coverage signal.

**Practical rule:** If you're auditing or assigning Layout Templates on any tenant created after Workfront's new-experience rollout, query `/UITMPL/search` (not `/layoutTemplate/search`) and walk the priority chain (User → Role → Team → Group) using `uiTemplateID`. Querying only `/layoutTemplate/search` on a modern tenant returns 6 stock rows and makes it look like the customer has done nothing — even when they've built a full persona-based LT program.

For the full coverage-audit pattern (priority-chain walk, license-type breakdown of uncovered users, role-inheritance gap analysis), run the same walk per layout template.md`.

## A note on JRNLE (field-change history / audit log)

The field-level audit trail is the **`JRNLE`** object (`JournalEntry`), endpoint `/attask/api/v17.0/JRNLE/search`. This is the authoritative record of *who changed which field, from what, to what, and when* — and it captures changes the in-app **Updates feed does not surface**. For example, `ownerID` changes are not a default Update Type, so they never appear in the project's Updates tab, but every owner change is recorded in `JRNLE`. Reach for this whenever a user asks "was field X ever set to Y?" or "what changed the owner/status/group and who did it?"

- **Object code is `JRNLE`, not `JOURNENT`.** `JOURNENT` is a legacy/guessed code and returns `Unknown object type` on modern versions (verified failing on v19.0, two production tenants, 2026-07-06).
- **Query by parent:** filter on `projectID` (or `taskID`, `opTaskID`), or on `objObjCode` + `objID` for any object. Add `$$LIMIT` — a busy object accumulates many rows.
- **Value fields are split by type** (there is no generic `oldValue`/`newValue` — asking for those errors out):
  - reference/text fields → `oldTextVal` / `newTextVal` (for reference fields like `ownerID` these hold the **object ID** — resolve via a follow-up `USER`/etc. lookup)
  - numeric → `oldNumberVal` / `newNumberVal`
  - date → `oldDateVal` / `newDateVal`
- **Other useful fields:** `fieldName`, `changeType` (`E` = edit), `editedByID` (+ join `editedBy:name`), `entryDate`, `objObjCode`.

Example — owner-change history for a project:

```bash
curl -s --compressed -G "https://<host>/attask/api/v17.0/JRNLE/search" \
  --data-urlencode "projectID=<projectID>" \
  --data-urlencode "fieldName=ownerID" \
  --data-urlencode "fields=changeType,oldTextVal,newTextVal,editedBy:name,entryDate" \
  -H "apiKey: <key>"
```

## Discovering an object code when a guess fails

When an endpoint returns `Unknown object type: <CODE>`, don't keep guessing — list the real codes programmatically. `GET /attask/api/v17.0/metadata` returns every object under `data.objects` as `{DisplayName: {objCode: "..."}}`; grep it for the concept you want (e.g. `journal`, `audit`, `note`). For a specific object's fields, `GET /attask/api/v17.0/<OBJCODE>/metadata` returns `data.fields` — the ground truth for which field names exist in your API version (this is how the `oldTextVal`/`newTextVal` shape above was found).

## Verifying the URL path for an object

Don't assume the URL segment matches the OBJCODE. Look the endpoint up in the Adobe Workfront API Explorer — it gives you the exact URL path, the supported HTTP methods, and the available fields for every object.
