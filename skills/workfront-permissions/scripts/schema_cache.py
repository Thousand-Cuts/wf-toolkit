"""Host-hashed schema cache for the workfront-permissions skill.

Copy-and-adapted from skills/workfront-custom-forms/scripts/schema_cache.py
per the plan's "Shared helpers note" — duplication is intentional in v1;
a shared helper is a v2 candidate once a third skill needs it.

Cache file: ~/.cache/wf-toolkit/permissions-schema-<sha8(host)>.json
Stored with mode 600.

TTL: 24 hours. Force refresh via `invalidate(host)`.

`objects` payload holds the three metadata responses relevant to
permissions diagnostics:
  - accessLevel
  - accessRule
  - customerInformation

See knowledge/permissions/08-runtime-schema-discovery.md for usage.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cache" / "wf-toolkit"
CACHE_PREFIX = "permissions-schema-"
DEFAULT_TTL_SECONDS = 24 * 60 * 60


def cache_path(host: str) -> Path:
    return CACHE_DIR / f"{CACHE_PREFIX}{_short_hash(host)}.json"


def read(host: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict | None:
    path = cache_path(host)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    captured = data.get("captured_at_epoch")
    if not isinstance(captured, (int, float)):
        return None
    if time.time() - captured > ttl_seconds:
        return None

    expected_hash = data.get("schemaHash")
    recomputed = hash_of(data.get("objects") or {})
    if expected_hash != recomputed:
        return None

    return data


def write(host: str, objects: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(host)
    data = {
        "host": host,
        "captured_at_epoch": int(time.time()),
        "schemaHash": hash_of(objects),
        "objects": objects,
    }
    path.write_text(json.dumps(data, indent=2))
    os.chmod(path, 0o600)


def invalidate(host: str) -> None:
    path = cache_path(host)
    if path.exists():
        path.unlink()


def hash_of(objects: dict[str, Any]) -> str:
    canonical = json.dumps(objects, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _short_hash(host: str) -> str:
    return hashlib.sha256(host.encode()).hexdigest()[:8]
