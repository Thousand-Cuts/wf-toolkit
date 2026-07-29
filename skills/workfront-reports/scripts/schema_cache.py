#!/usr/bin/env python3
"""Host-hashed metadata cache for workfront-reports.

Stores /metadata responses for the REPORT and the three UI-objects (UIVW,
UIFT, UIGB) under ~/.cache/wf-toolkit/reports-schema-<host-hash>.json,
with SHA-256 of the raw response so a tenant-side schema change forces a
re-parse. TTL: 24 hours.

CLI: put | get | inspect | refresh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cache" / "wf-toolkit"
TTL_SECONDS = 24 * 3600
# The 4 v0.8.0 'wrapper' objects + Workfront uiObjCodes the pre-flight
# validator needs to cache. Workfront supports many more objCodes; this is
# the union of (a) the 4 wrappers, (b) the 13 uiObjCodes observed across
# the empirical survey, and (c) common builtins. Add to this list as new
# uiObjCodes appear in your environments.
SUPPORTED_OBJECTS = (
    # v0.8.0 wrapper objects (referenced from REPORT row)
    "report", "uivw", "uift", "uigb",
    # Workfront uiObjCodes seen in survey + common builtins
    "proj", "task", "optask", "user", "hour", "assgn",
    "docu", "param", "pgrp", "prgm", "prfapl", "ttsk", "tpro",
    # Future-proofing common ones not in survey
    "tmpl", "team", "group", "role", "company", "portfolio", "program",
)


def host_hash(host: str) -> str:
    return hashlib.sha256(host.lower().encode("utf-8")).hexdigest()[:12]


def now_epoch() -> int:
    return int(time.time())


def cache_path(host: str) -> Path:
    return CACHE_DIR / f"reports-schema-{host_hash(host)}.json"


def _load(host: str) -> dict[str, Any]:
    path = cache_path(host)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(host: str, bundle: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(host)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(bundle, indent=2, sort_keys=True))
    tmp.replace(path)


def put(host: str, obj_code: str, raw_metadata: Any) -> None:
    if obj_code not in SUPPORTED_OBJECTS:
        raise ValueError(f"unsupported obj_code: {obj_code}")
    bundle = _load(host)
    serialized = json.dumps(raw_metadata, sort_keys=True)
    fields = raw_metadata.get("fields") if isinstance(raw_metadata, dict) else None
    bundle[obj_code] = {
        "schemaHash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "fetchedAt": now_epoch(),
        "fields": fields if fields is not None else raw_metadata,
    }
    _save(host, bundle)


def get(host: str, obj_code: str) -> dict[str, Any] | None:
    bundle = _load(host)
    entry = bundle.get(obj_code)
    if entry is None:
        return None
    if now_epoch() - entry.get("fetchedAt", 0) > TTL_SECONDS:
        return None
    return entry


def inspect(host: str) -> dict[str, Any]:
    return _load(host)


def refresh(host: str) -> None:
    path = cache_path(host)
    if path.exists():
        path.unlink()


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    p_put = sub.add_parser("put")
    p_put.add_argument("host")
    p_put.add_argument("obj_code", choices=SUPPORTED_OBJECTS)
    p_put.add_argument("--from-stdin", action="store_true",
                       help="read raw metadata JSON from stdin")
    p_get = sub.add_parser("get")
    p_get.add_argument("host")
    p_get.add_argument("obj_code", choices=SUPPORTED_OBJECTS)
    p_ins = sub.add_parser("inspect")
    p_ins.add_argument("host")
    p_ref = sub.add_parser("refresh")
    p_ref.add_argument("host")
    args = p.parse_args()
    if args.cmd == "put":
        if not args.from_stdin:
            print("error: --from-stdin required", file=sys.stderr)
            return 2
        raw = json.loads(sys.stdin.read())
        put(args.host, args.obj_code, raw)
        return 0
    if args.cmd == "get":
        entry = get(args.host, args.obj_code)
        if entry is None:
            return 1
        print(json.dumps(entry, indent=2, sort_keys=True))
        return 0
    if args.cmd == "inspect":
        bundle = inspect(args.host)
        print(json.dumps(bundle, indent=2, sort_keys=True))
        return 0
    if args.cmd == "refresh":
        refresh(args.host)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
