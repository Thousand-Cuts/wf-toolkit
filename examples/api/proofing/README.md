# Headless Workfront proof generation (no Fusion)

`create-demo-proof.sh` fabricates demo proofing activity — a **proof with a comment, a reply, and an Approved decision** — by replaying the endpoints the Workfront UI uses, with no Fusion scenario and no Adobe OAuth setup. Reverse-engineered and verified live 2026-07-04. Full mechanism: [`knowledge/api/15-proofing.md`](../../../knowledge/api/15-proofing.md).

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

- **Resolving a comment thread** — the `resolve_comment` action runs through the proof *viewer's* JSON-RPC (`us.my.workfront.com/proof/rpc/index.php`), which uses a **separate session token** than `rest.proofhq.com` and numeric comment IDs. Not wired here. (Resolving is a `type:4` reply; the RPC methods are `comments` / `add_reply` / `resolve_comment`.)
- **Durable/unattended runs** — needs a cookie-free credential (Adobe IMS OAuth Server-to-Server, untested against `/internal/`) or a headless-browser login. See `15-proofing.md`.

## Support status

Unsupported, reverse-engineered, and fragile by nature (internal endpoints can change without notice). For production/repeatable proofing automation, **Fusion's Workfront Proof connector** ([`examples/fusion/06-demo-proof-generator.json`](../../fusion/06-demo-proof-generator.json)) is the sanctioned path. This script is for quick demo-data generation when you can't/won't use Fusion.
