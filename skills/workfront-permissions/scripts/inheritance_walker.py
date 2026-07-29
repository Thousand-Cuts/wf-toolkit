"""Up-tree parent walk for the permission inheritance rules.

Pure function. The caller pre-fetches the parent chain via API and hands
it to the walker. The walker returns the chain in walk order — the
permission_resolver then re-runs its rule matcher against each parent's
accessRules.

Walk-order rules (from spec §6 and Phase A findings):

  TASK / OPTASK / DOCU / HOUR / EXPNS  →  PROJ  →  PORT, PROG
  PROJ                                  →  PORT, PROG
  DOCU                                  → folder hierarchy (cap 10 levels)
  TMPL                                  → none

Empirical answers may shift this map; the `set_parent_map()` hook lets
the caller override at runtime if Phase A finds different cascades.
"""

from __future__ import annotations

from typing import Any

# objCode → ordered list of parent objCodes to consult.
_PARENT_MAP: dict[str, list[str]] = {
    "TASK": ["PROJ", "PORT", "PROG"],
    "OPTASK": ["PROJ", "PORT", "PROG"],
    "ISSUE": ["PROJ", "PORT", "PROG"],
    "DOCU": ["FOLDER", "PROJ", "PORT", "PROG"],
    "HOUR": ["PROJ", "PORT", "PROG"],
    "EXPNS": ["PROJ", "PORT", "PROG"],
    "PROJ": ["PORT", "PROG"],
    "PORT": [],
    "PROG": [],
    "TMPL": [],
}

FOLDER_DEPTH_CAP = 10


def set_parent_map(mapping: dict[str, list[str]]) -> None:
    """Override the default parent map (Phase A hook)."""
    global _PARENT_MAP
    _PARENT_MAP = dict(mapping)


def parent_path_for_objcode(objcode: str) -> list[str]:
    """Return the ordered list of parent objCodes the caller should fetch.

    Empty list means no inheritance walk applies for this objCode.
    """
    return list(_PARENT_MAP.get(objcode, []))


def walk_for_rules(target_object: dict) -> list[dict]:
    """Return the flat parent list in walk order.

    Caller is responsible for populating `target_object["parents"]` via
    API GETs against the parent path. The walker returns those parents,
    capped at FOLDER_DEPTH_CAP for any DOCU folder chain.

    Each returned dict matches the shape the resolver expects:

      {"objCode": "PROJ", "ID": "...", "accessRules": [...], "ownerID": "..."}
    """
    parents = list(target_object.get("parents") or [])
    objcode = target_object.get("objCode")

    if objcode == "DOCU":
        # Cap deep folder chains to avoid runaway walks.
        return _cap_depth(parents, FOLDER_DEPTH_CAP)

    return parents


def _cap_depth(chain: list[dict], cap: int) -> list[dict]:
    if len(chain) <= cap:
        return chain
    capped = chain[:cap]
    capped.append({
        "objCode": "DEPTH_CAP",
        "ID": None,
        "accessRules": [],
        "_note": (
            f"Inheritance walk capped at {cap} levels. "
            f"{len(chain) - cap} additional parents not consulted."
        ),
    })
    return capped


def needs_inheritance_walk(objcode: str) -> bool:
    """Return True iff this objCode has any parent path configured."""
    return bool(_PARENT_MAP.get(objcode))


def is_known_objcode(objcode: str) -> bool:
    """Return True iff the parent map has an entry for this objCode."""
    return objcode in _PARENT_MAP
