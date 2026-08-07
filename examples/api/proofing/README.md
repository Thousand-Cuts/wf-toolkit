# Headless Workfront proof generation (no Fusion)

Two scripts here, with different credential requirements:

| Script | Does | Needs |
|---|---|---|
| `create-demo-proof.sh` | **Creates** a proof + comment + reply + Approved decision | API key **+ web session cookie** |
| `post-proof-markup.py` | Posts **drawing markup** (arrow/box/line/freehand/highlight) onto an **existing** proof | API key only — **no cookie** |

`create-demo-proof.sh` fabricates demo proofing activity — a **proof with a comment, a reply, and an Approved decision** — by replaying the endpoints the Workfront UI uses, with no Fusion scenario and no Adobe OAuth setup. Reverse-engineered and verified live 2026-07-04. Full mechanism: [`knowledge/api/15-proofing.md`](../../../knowledge/api/15-proofing.md).

---

## `post-proof-markup.py` — drawing markup, cookie-free

Posts real viewer markup (the shapes a reviewer draws by hand) using **only a Workfront API key**. Verified live 2026-08-06. Schema and mechanism: [`knowledge/api/16-proofhq-soap-catalog.md`](../../../knowledge/api/16-proofhq-soap-catalog.md) §6.

```bash
export WF_HOST=tenant.my.workfront.com WF_API_KEY=... WF_TENANT_ID=<uuid>
./post-proof-markup.py <docVersionID> --list
./post-proof-markup.py <docVersionID> --shape ARROW --text "Fix this" --coords 90 340 320 430
./post-proof-markup.py <docVersionID> --cleanup-prefix "demo:"
```

It sidesteps the cookie entirely: `getProofingTokens` (API key) → viewer RPC `startup` → a `sessionId` that authenticates `rest.proofhq.com`. **This does not create proofs** — the proof must already exist with `proofStatus=success`. Creation still needs the cookie path or Fusion.

- `WF_TENANT_ID` is the tenant UUID from the `wf-auth` JWT — a one-time capture per tenant (DevTools → any `/internal/` request).
- Write-verified shapes: `RECTANGLE`, `ARROW`, `LINE`, `FREEHAND`, `HIGHLIGHT`. Also accepted, and certain to render, but never posted via this script: `TEXT_HIGHLIGHT`, `TEXT_REPLACE`. **The server does not validate `type`** — it stores any string, including nonsense (`NOTREAL_XYZ` was accepted and echoed back unchanged). Acceptance proves storage, not rendering: an unrecognised type most likely draws nothing while still creating a visible comment. Neither outcome was visually confirmed. Stick to the list.
- ⚠️ `--cleanup-prefix` deletes and verifies read-back — but **this is not reversible in the audit trail**. Both the create *and* the delete stay permanently in the proof's activity feed (`GET /proofs/{token}/activity`) under your name and email, and the create keeps the comment text. There is no undo anywhere in the API. Use it only on a disposable proof on your own tenant.
- Verified on a single US-region tenant. The ProofHQ REST bases are region-split and vendor-declared (`rest.proofhq.com` US / `rest.proofhq.eu` EU, per the embedded OpenAPI); the script picks its base from the `mediaViewerApi` host that `getProofingTokens` returns, rather than hardcoding US. No non-US viewer-RPC host has been observed.
- **Markup is impossible via SOAP** — no such method exists, hidden or otherwise (proven in `16-proofhq-soap-catalog.md` §5). Fusion's Custom API Call inherits that limit, since it only wraps SOAP.

---

## `create-demo-proof.sh` — full creation flow (needs a cookie)

## Why it exists

The public REST `createProof` action/field is a **verified no-op** — it never generates a proof. The UI creates proofs via **undocumented `/internal/` endpoints** authenticated by the **web session cookie** (not the API key). This script uses that path.

## The three credentials

| Credential | Used for |
|---|---|
| `WF_API_KEY` | Public REST (`/attask/api`): create the document, poll `proofID`, mint the proof token |
| **Web session cookie** | `/internal/document/proof/create` and `/internal/getProofhqRestApiToken`. Must include the full **`wf-auth` JWT** + `attask` + `XSRF-TOKEN` |
| ProofHQ `sessionId` | Minted from the cookie via the bridge; used as the `sessionid` header on `rest.proofhq.com` |

## Usage

```bash
export WF_HOST=yourtenant.my.workfront.com
export WF_API_KEY=...
# cookie file = the raw `Cookie:` header value from any /internal/ request (DevTools → Network → Headers)
./create-demo-proof.sh cookie.txt ./artwork.jpg <projectID>
```

The script uploads the file itself (API), so **no UI upload is needed** — it just requires the file path to keep its extension (see below).

## Hard requirements & gotchas

- **Proofability is gated by the document name's file extension, not the bytes.** Workfront derives the file type from the document `name` — a name with no extension → "Undefined File Type" → `isProofable=false` → the create silently no-ops. The script names the document after the file's basename, so keep the extension on your file path (`artwork.jpg`, not `artwork`). *(This was the "API-uploaded docs can't be proofed" red herring — the UI just always kept the extension.)*
- **`rest.proofhq.com` writes return HTTP 500 but succeed.** Never trust the status code — the script verifies every write by reading the object back. This burned hours; don't re-learn it.
- **The cookie is ephemeral and sensitive** — it's a full-account bearer credential that expires with the browser session. Treat the file like a password; delete it after.
- **Decisions require an approver.** The script promotes the owner recipient to `roleReviewerApprover` (role 5) before stamping the decision — a `roleReviewer` cannot decide (403 "not an approver").

## What's NOT covered

- **Resolving a comment thread** — the `resolve_comment` action runs through the proof *viewer's* JSON-RPC (`us.my.workfront.com/proof/rpc/index.php`), which addresses comments by **numeric ID** rather than the opaque tokens `rest.proofhq.com` uses. Not wired here. (The RPC is *not* a separate session system: its `startup` method mints the very `sessionId` that authenticates `rest.proofhq.com` — that is what `post-proof-markup.py` relies on. Untested is the reverse direction: whether the cookie-minted `getProofhqRestApiToken` session *this* script holds can also drive the RPC. Resolving is a `type:4` reply; the RPC methods are `comments` / `add_reply` / `resolve_comment`.)
- **Durable/unattended runs** — needs a cookie-free credential (Adobe IMS OAuth Server-to-Server, untested against `/internal/`) or a headless-browser login. See `15-proofing.md`.

## Support status

Unsupported, reverse-engineered, and fragile by nature (internal endpoints can change without notice). For production/repeatable proofing automation, **Fusion's Workfront Proof connector** ([`examples/fusion/06-demo-proof-generator.json`](../../fusion/06-demo-proof-generator.json)) is the sanctioned path. This script is for quick demo-data generation when you can't/won't use Fusion.
