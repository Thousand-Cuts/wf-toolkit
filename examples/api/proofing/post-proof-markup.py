#!/usr/bin/env python3
"""post-proof-markup.py — post drawing markup (arrow / box / line / freehand / highlight)
onto an existing Workfront proof, using ONLY a Workfront API key. No cookie, no Fusion,
no ProofHQ password, no Public-API authtoken.

Auth chain (all cookie-free) — see knowledge/api/16-proofhq-soap-catalog.md §6.1:
  WF apiKey  ── PUT /docv/<id>/getProofingTokens ─▶ token + codetodecode
  viewer RPC ── POST /proof/rpc/index.php {startup} ─▶ sessionId
  ProofHQ    ── sessionid header on rest.proofhq.com ─▶ comments + drawings

The proof must already exist (proofStatus=success); this does NOT create proofs.

Usage:
  export WF_HOST=tenant.my.workfront.com WF_API_KEY=... WF_TENANT_ID=<uuid from wf-auth JWT>
  ./post-proof-markup.py <docVersionID> --list
  ./post-proof-markup.py <docVersionID> --shape RECTANGLE --text "Tighten this headline"
  ./post-proof-markup.py <docVersionID> --cleanup-prefix "demo:"
"""
import argparse, json, os, sys, urllib.parse, urllib.request

RPC_FALLBACK = "https://us.my.workfront.com/proof/rpc/"
REST_US = "https://rest.proofhq.com/api/v1"
REST_EU = "https://rest.proofhq.eu/api/v1"

# Two different kinds of evidence — keep them apart:
#   Write-verified through this API (POST 201, read back intact, DELETE 204):
#     RECTANGLE, ARROW, LINE, FREEHAND, HIGHLIGHT.
#   Observed in real UI-created markup, so certain to render, but NEVER posted via this API:
#     TEXT_HIGHLIGHT, TEXT_REPLACE. The rectangles[] payload built for them below mirrors
#     4 harvested UI samples field-for-field, but the write path is untested.
#   ARROW/LINE are the inverse case: write-verified, but absent from all 45 harvested UI
#   drawings — documented Workfront drawing tools whose rendering was not confirmed.
# The server does NOT validate `type` (it stored "NOTREAL_XYZ"), so a 201 proves storage,
# not rendering.
SHAPES = ["RECTANGLE", "ARROW", "LINE", "FREEHAND", "HIGHLIGHT",
          "TEXT_HIGHLIGHT", "TEXT_REPLACE"]


def http(url, data=None, headers=None, method=None, timeout=45):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class Proof:
    def __init__(self, host, key, tenant, dvid):
        self.sub = host.split(".")[0]
        self.tenant = tenant
        api = f"https://{host}/attask/api/v17.0"
        st, b = http(f"{api}/docv/{dvid}/getProofingTokens?apiKey={key}",
                     data=urllib.parse.urlencode({"versionID": dvid}).encode(),
                     headers={"Content-Type": "application/x-www-form-urlencoded"},
                     method="PUT")
        r = (json.loads(b).get("data") or {}).get("result") or {}
        self.token, code = r.get("token"), r.get("codetodecode")
        if not self.token:
            sys.exit(f"ERROR: no proof token on docv {dvid} — is the proof created "
                     f"(proofStatus=success)?")
        # mediaViewerApi names the tenant's proofing region — don't hardcode "us."
        viewer = r.get("mediaViewerApi") or RPC_FALLBACK
        self.rpc = urllib.parse.urljoin(viewer, "index.php")
        self.rest_base = REST_EU if viewer.startswith("https://eu.") else REST_US
        st, b = http(self.rpc,
                     data=json.dumps({"method": "startup", "proofingCode": code,
                                      "token": self.token}).encode(),
                     headers={"content-type": "application/x-www-form-urlencoded",
                              "tcmssubdomain": self.sub, "tcmstenantid": self.tenant})
        self.sid = (json.loads(b) or {}).get("sessionId")
        if not self.sid:
            sys.exit(f"ERROR: viewer RPC startup at {self.rpc} returned no sessionId "
                     f"(check WF_TENANT_ID matches this tenant's wf-auth JWT, and that "
                     f"the RPC host matches the tenant region)")

    def rest(self, path, method="GET", body=None):
        h = {"sessionid": self.sid, "tcmssubdomain": self.sub,
             "tcmstenantid": self.tenant, "content-type": "application/json"}
        return http(f"{self.rest_base}/{path}", headers=h, method=method,
                    data=json.dumps(body).encode() if body is not None else None)

    def comments(self):
        st, b = self.rest(f"proofs/{self.token}/comments")
        try:
            return json.loads(b)
        except Exception:
            return []


def drawing(dtype, x1, y1, x2, y2, color=0xFF0000, thickness=3, page=1):
    """Build a drawing object. `color` is a 24-bit INT (0xFF0000 = red), not a hex string.
    Note `page` is 1-indexed while `pages[]` is 0-indexed — both are required."""
    pts = [{"x": x1, "y": y1}, {"x": x2, "y": y2}]
    d = {
        "type": dtype, "color": color,
        "alpha": 0.4 if "HIGHLIGHT" in dtype else 1,
        "thickness": thickness, "points": pts, "page": page, "pages": [page - 1],
        "minMax": {"minx": min(x1, x2), "maxx": max(x1, x2),
                   "miny": min(y1, y2), "maxy": max(y1, y2)},
        "width": abs(x2 - x1), "height": abs(y2 - y1),
        "x": min(x1, x2), "y": min(y1, y2), "index": 0,
        "isNew": True, "editable": True, "isBeingEdited": False,
        "handleTypes": "boundingBox",
    }
    if dtype == "FREEHAND":
        n = 12
        d["pathPoints"] = [{"x": x1 + (x2 - x1) * i / n,
                            "y": y1 + (y2 - y1) * i / n} for i in range(n + 1)]
    if dtype in ("TEXT_HIGHLIGHT", "TEXT_REPLACE"):
        d["rectangles"] = [{"x": 0, "y": 0, "width": abs(x2 - x1),
                            "height": abs(y2 - y1), "angle": 0}]
    return d


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dvid", help="Workfront document version ID (proof must exist)")
    p.add_argument("--shape", choices=SHAPES, default="RECTANGLE",
                   help="TEXT_HIGHLIGHT/TEXT_REPLACE are UI-observed but never written via API")
    p.add_argument("--text", default="demo: markup posted via API")
    p.add_argument("--coords", nargs=4, type=float, metavar=("X1", "Y1", "X2", "Y2"),
                   default=[60, 60, 260, 160])
    p.add_argument("--color", default="0xFF0000", help="24-bit colour, e.g. 0xFF0000")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--list", action="store_true", help="list comments and exit")
    p.add_argument("--cleanup-prefix", help="delete every comment whose text starts with this")
    a = p.parse_args()

    host, key = os.environ.get("WF_HOST"), os.environ.get("WF_API_KEY")
    tenant = os.environ.get("WF_TENANT_ID")
    if not (host and key and tenant):
        sys.exit("set WF_HOST, WF_API_KEY and WF_TENANT_ID")

    pr = Proof(host, key, tenant, a.dvid)
    print(f"proof token={pr.token}  session=ok")

    if a.list:
        for c in pr.comments():
            kinds = [d.get("type") for d in (c.get("drawings") or [])]
            print(f"  {c.get('token','')[:12]}  {str(c.get('text',''))[:50]:52} {kinds}")
        return

    if a.cleanup_prefix:
        targets = [c for c in pr.comments()
                   if str(c.get("text", "")).startswith(a.cleanup_prefix)]
        for c in targets:
            st, _ = pr.rest(f"proofs/{pr.token}/comments/{c['token']}", method="DELETE")
            print(f"  DELETE {str(c['text'])[:40]:42} HTTP {st}")
        left = [c for c in pr.comments()
                if str(c.get("text", "")).startswith(a.cleanup_prefix)]
        print(f"VERIFY: {len(left)} remaining with that prefix (expect 0)")
        return

    d = drawing(a.shape, *a.coords, color=int(a.color, 0), page=a.page)
    st, body = pr.rest(f"proofs/{pr.token}/comments", method="POST",
                       body={"text": a.text, "page": a.page, "drawings": [d]})
    print(f"  POST {a.shape} → HTTP {st}")

    # rest.proofhq.com sometimes returns 500 on a write that SUCCEEDED.
    # The read-back is the only trustworthy signal — never trust the status code.
    match = [c for c in pr.comments() if c.get("text") == a.text]
    if match:
        got = [x.get("type") for x in (match[0].get("drawings") or [])]
        print(f"VERIFIED by read-back: drawings={got} token={match[0]['token']}")
    else:
        sys.exit("NOT FOUND on read-back — the write did not land")


if __name__ == "__main__":
    main()
