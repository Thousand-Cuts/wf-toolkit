#!/usr/bin/env bash
#
# create-demo-proof.sh — headless Workfront proof generator (reverse-engineered)
#
# Creates a proof on an already-proofable document version, then posts a comment,
# a reply, promotes the owner to approver, and stamps an "Approved" decision —
# ALL WITHOUT FUSION. Verified working 2026-07-04 on a live production tenant.
#
# ── Why this exists ──────────────────────────────────────────────────────────
# The public REST `createProof` action/field is a NO-OP (see knowledge/api/15-proofing.md).
# The Workfront UI creates proofs via UNDOCUMENTED /internal/ endpoints authenticated
# by the WEB SESSION COOKIE (not the API key). This script replays that path.
#
# ── Auth model (three credentials) ───────────────────────────────────────────
#   1. WF_API_KEY        — public REST (/attask/api): upload, create doc, poll, getProofingTokens
#   2. web session cookie — /internal/* endpoints (create proof, mint ProofHQ session).
#                           MUST include the full `wf-auth` JWT + `attask` + `XSRF-TOKEN`.
#   3. ProofHQ sessionId  — minted from the cookie via /internal/getProofhqRestApiToken;
#                           used as the `sessionid` header on rest.proofhq.com.
#
# ── GOTCHAS (do not skip) ─────────────────────────────────────────────────────
#   * The document must be proofable (isProofable=true). Workfront derives the file
#     type from the document NAME'S EXTENSION, not the bytes — so the document name
#     MUST keep its extension (e.g. "art.jpg", not "art"). A name without an extension
#     → "Undefined File Type" → isProofable=false → the create silently no-ops.
#     (This script names the document after the file's basename, so it Just Works.)
#   * rest.proofhq.com WRITES frequently return HTTP 500 but SUCCEED. Never trust the
#     status code — verify by reading the object back. This script does.
#   * The session cookie is EPHEMERAL (expires with the browser session / on logout)
#     and is a full-account bearer credential. Treat the cookie file like a password.
#
# ── Usage ─────────────────────────────────────────────────────────────────────
#   export WF_HOST=yourtenant.my.workfront.com
#   export WF_API_KEY=...
#   # cookie file = the raw `Cookie:` header from any /internal/ request (DevTools)
#   ./create-demo-proof.sh <cookie-file> <file-path.jpg> <projectID>
#
set -euo pipefail

: "${WF_HOST:?set WF_HOST (e.g. tenant.my.workfront.com)}"
: "${WF_API_KEY:?set WF_API_KEY}"
COOKIE_FILE="${1:?usage: create-demo-proof.sh <cookie-file> <file-path> <projectID>}"
FILE="${2:?path to a real image or PDF to proof}"
PROJID="${3:?parent projectID where the document attaches}"
[ -f "$FILE" ] || { echo "ERROR: file not found: $FILE" >&2; exit 1; }

H="$WF_HOST"; K="$WF_API_KEY"
CK="$(tr -d '\n' < "$COOKIE_FILE")"
# x-xsrf-token value == the XSRF-TOKEN cookie value
XSRF="$(printf '%s' "$CK" | sed -n 's/.*XSRF-TOKEN=\([^;]*\).*/\1/p')"
[ -n "$XSRF" ] || { echo "ERROR: XSRF-TOKEN not found in cookie file" >&2; exit 1; }

api()  { curl -s --compressed "https://$H/attask/api/v17.0/$1" "${@:2}"; }
intl() { curl -s --compressed "https://$H/internal/$1" -b "$CK" -H "x-xsrf-token: $XSRF" -H "x-requested-with: XMLHttpRequest" "${@:2}"; }
jget() { python3 -c 'import sys,json;d=json.load(sys.stdin);print(eval("d"+sys.argv[1]))' "$1"; }

echo "==> 0. verify session cookie authenticates /internal/"
if [ "$(intl 'getProofhqRestApiToken?proofID=1' -o /dev/null -w '%{http_code}')" = "401" ]; then
  echo "ERROR: cookie rejected (401). Re-grab a fresh Cookie header incl. full wf-auth JWT." >&2; exit 1
fi

echo "==> 1. upload the file + create the document (API key)"
# CRITICAL: the document NAME must keep the file extension, or Workfront tags it
# "Undefined File Type" (ext:'', fileType:unk) and isProofable stays false.
BASENAME="$(basename "$FILE")"
HANDLE="$(curl -s --compressed -X POST "https://$H/attask/api/v17.0/upload?apiKey=$K" -F "uploadedFile=@$FILE" | jget "['data']['handle']")"
DOC="$(api "document?apiKey=$K" -X POST --data-urlencode "name=$BASENAME" --data-urlencode "handle=$HANDLE" --data-urlencode "docObjCode=PROJ" --data-urlencode "objID=$PROJID" --data-urlencode "fields=ID,currentVersionID")"
DVID="$(echo "$DOC" | jget "['data']['currentVersionID']")"
PROOFABLE="$(api "docv/$DVID?apiKey=$K&fields=isProofable,documentTypeLabel" | jget "['data']['isProofable']")"
echo "    docv=$DVID isProofable=$PROOFABLE"
[ "$PROOFABLE" = "True" ] || { echo "ERROR: not proofable — is '$BASENAME' missing a file extension, or a non-proofable type?" >&2; exit 1; }

echo "==> 2. create the proof via /internal/document/proof/create (cookie auth)"
intl "document/proof/create" -X POST -H "content-type: application/x-www-form-urlencoded" --data "documentVersionID=$DVID" >/dev/null

echo "==> 3. poll for proofID (async, ~1 min)"
PROOFID=""
for i in $(seq 1 20); do
  PROOFID="$(api "docv/$DVID?apiKey=$K&fields=proofID" | jget "['data'].get('proofID') or ''")"
  [ -n "$PROOFID" ] && { echo "    proofID=$PROOFID"; break; }
  sleep 8
done
[ -n "$PROOFID" ] || { echo "ERROR: proof did not generate (proofID still null)." >&2; exit 1; }

echo "==> 4. mint ProofHQ sessionId + proof token"
SID="$(intl "getProofhqRestApiToken?proofID=$PROOFID" | jget "['data']['sessionId']")"
PT="$(api "docv/$DVID/getProofingTokens?apiKey=$K" -X PUT --data-urlencode "versionID=$DVID" | jget "['data']['result']['token']")"
TENANT_ID="$(printf '%s' "$CK" | sed -n 's/.*tenant_id[^0-9a-f]*\([0-9a-f]\{32\}\).*/\1/p' | head -1)"
rest() { curl -s --compressed -H "sessionid: $SID" -H "tcmssubdomain: ${H%%.*}" ${TENANT_ID:+-H "tcmstenantid: $TENANT_ID"} -H "content-type: application/json" "https://rest.proofhq.com/api/v1/$1" "${@:2}"; }

echo "==> 5. post a comment (rest.proofhq.com — 500 is a lie, verify after)"
rest "proofs/$PT/comments" -X POST -d '{"text":"Demo comment — looks great!","page":1}' >/dev/null || true
CT="$(rest "proofs/$PT/comments" | jget "[0]['token']")"
echo "    commentToken=$CT"

echo "==> 6. reply to the comment (500 is a lie)"
rest "proofs/$PT/comments/$CT/replies" -X POST -d '{"text":"Reply from the demo script."}' >/dev/null || true

echo "==> 7. promote owner recipient to approver (role 5 = roleReviewerApprover)"
RT="$(rest "proofs/$PT/recipients" | jget "[0]['token']")"
rest "proofs/$PT/recipients/$RT" -X PUT -d '{"role":5}' >/dev/null || true

echo "==> 8. stamp an Approved decision (500 is a lie)"
# resolve the account's "Approved" decision-option token dynamically
ACCT="$(rest "proofs/$PT?fields=accountToken" | jget "['accountToken']")"
DECTOK="$(rest "accounts/$ACCT/settings/decisions" | python3 -c "import sys,json;print(next(d['token'] for d in json.load(sys.stdin) if d['name']=='Approved'))")"
rest "proofs/$PT/recipients/$RT" -X PUT -d "{\"decision\":{\"token\":\"$DECTOK\"}}" >/dev/null || true

echo "==> 9. VERIFY (read-back — the only source of truth)"
rest "proofs/$PT/recipients" | python3 -c "import sys,json;r=json.load(sys.stdin)[0];print('    reviewer:',r['name'],'| role:',r['roleName'],'| decision:',r.get('decision',{}).get('name'))"
rest "proofs/$PT?fields=name,commentsCount,decision" | python3 -c "import sys,json;d=json.load(sys.stdin);print('    proof:',d['name'],'| comments:',d.get('commentsCount'),'| decision:',(d.get('decision') or {}).get('name'))"
echo "==> DONE. proofID=$PROOFID  token=$PT"
