#!/usr/bin/env python3
"""Pre-flight validation for workfront-reports v0.9.0.

Walks an about-to-POST bundle (2/3/4 JSON bodies) and validates every field
reference against cached /<uiObjCode>/metadata. Catches errors like
`isTemplate` on PROJ (no such field) before any byte writes.

Returns: {"valid": bool, "errors": [...], "warnings": [...]}.
Exit code: 0 valid, 1 invalid, 2 usage error.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

DEFAULT_WHITELIST_DIR = os.path.expanduser("~/.cache/wf-toolkit")


def _host_hash(host: str) -> str:
    return hashlib.sha256(host.encode("utf-8")).hexdigest()[:12]


def _whitelist_path(host: str, cache_dir: Optional[str] = None) -> str:
    base = cache_dir or DEFAULT_WHITELIST_DIR
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"reports-pseudo-fields-{_host_hash(host)}.json")


def _load_whitelist(host: str, cache_dir: Optional[str] = None) -> dict:
    path = _whitelist_path(host, cache_dir)
    if not os.path.exists(path):
        return {"host": host, "fields": []}
    try:
        return json.loads(Path(path).read_text())
    except (json.JSONDecodeError, ValueError):
        # corrupted whitelist: treat as empty + warn caller via return
        return {"host": host, "fields": [], "_corrupt": True}


def _save_whitelist(wl: dict, host: str, cache_dir: Optional[str] = None) -> None:
    path = _whitelist_path(host, cache_dir)
    wl.pop("_corrupt", None)
    Path(path).write_text(json.dumps(wl, indent=2, sort_keys=True))


def learn(host: str, uiObjCode: str, fieldname: str, slot: str,
          cache_dir: Optional[str] = None,
          learned_via: str = "manual",
          session: Optional[str] = None) -> dict:
    wl = _load_whitelist(host, cache_dir)
    # de-dup by (uiObjCode, fieldname); merge slots
    for entry in wl["fields"]:
        if entry["uiObjCode"] == uiObjCode and entry["fieldname"] == fieldname:
            if slot not in entry.get("slots", []):
                entry.setdefault("slots", []).append(slot)
                _save_whitelist(wl, host, cache_dir)
            return entry
    new_entry = {
        "uiObjCode": uiObjCode,
        "fieldname": fieldname,
        "slots": [slot],
        "learned_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "learned_via": learned_via,
    }
    if session:
        new_entry["blocked_in_session"] = session
    wl["fields"].append(new_entry)
    _save_whitelist(wl, host, cache_dir)
    return new_entry


def learn_from_blocked(host: str, uiObjCode: str, preflight_output_path: str,
                       cache_dir: Optional[str] = None,
                       session: Optional[str] = None) -> list:
    """Read forced warnings from a prior preflight output and write them to
    the per-tenant whitelist. Returns list of added entries."""
    data = json.loads(Path(preflight_output_path).read_text())
    forced = [w for w in data.get("warnings", []) if w.get("forced")]
    added = []
    for w in forced:
        path = w.get("path", "")
        if not path:
            continue
        slot = _slot_from_path(path)
        value = w.get("value", "")
        fieldname = value if value else path.rsplit(".", 1)[-1]
        if not fieldname:
            continue
        entry = learn(host, uiObjCode, fieldname, slot,
                      cache_dir=cache_dir, learned_via="auto-force",
                      session=session)
        added.append(entry)
    return added


def forget(host: str, uiObjCode: str, fieldname: str,
           cache_dir: Optional[str] = None) -> bool:
    wl = _load_whitelist(host, cache_dir)
    before = len(wl["fields"])
    wl["fields"] = [
        f for f in wl["fields"]
        if not (f.get("uiObjCode") == uiObjCode and f.get("fieldname") == fieldname)
    ]
    if len(wl["fields"]) != before:
        _save_whitelist(wl, host, cache_dir)
        return True
    return False


def forget_all(host: str, cache_dir: Optional[str] = None) -> bool:
    path = _whitelist_path(host, cache_dir)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "workfront-reports" / "scripts"))

try:
    import schema_cache  # for default cache integration
except ImportError:
    schema_cache = None

PREFIX_RE = re.compile(r"^(?:OR:\d+:|EXISTS:[a-z]:)")
EXISTS_CONTROL = frozenset({"$$EXISTSMOD", "$$OBJCODE", "$$ID"})
SESSION_TOKEN_RE = re.compile(r"^\$\$[A-Z_]")
BRACE_REF_RE = re.compile(r"\{([^{}$][^{}]*)\}")

# Curly-quote linter (gotcha #14). Workfront's text-mode parser only
# recognises straight ASCII quotes — the four Unicode "smart" curlies
# silently break valueexpression / aggregator parsing. Bite is hardest
# when users compose expressions in Google Docs / Word / Notion
# (auto-substitute on insertion) and paste into the in-product Text Mode
# tab. See knowledge/reports/05-gotchas.md #14.
CURLY_QUOTE_RE = re.compile(r"[‘’“”]")

# Hard-coded cross-objCode synonym hints
SYNONYM_HINTS = {
    ("PROJ", "isTemplate"):
        "Templates are a separate objCode (TMPL). Drop this filter or change uiObjCode to TMPL.",
    ("TASK", "isTemplate"):
        "Template tasks are a separate objCode (TTSK). Drop this filter or change uiObjCode to TTSK.",
    ("TASK", "isComplete"):
        "Use `status` enum compared with COMPLETE state (e.g. status_Mod=in with value CPL).",
    ("PROJ", "isComplete"):
        "Use `status` enum compared with COMPLETE state.",
    ("USER", "isPrimary"):
        "USER doesn't track that flag; check ROLE or TEAM membership instead.",
    ("OPTASK", "isComplete"):
        "Use `statusEquatesWith` compared with COMPLETE state.",
}

# Runtime-real fields that don't appear in /<obj>/metadata.
# Each entry: (uiObjCode, fieldname) -> {"slots": [...], "reason": "..."}.
# Slot strings match the validation context where the pseudo-field is acceptable.
PSEUDO_FIELDS = {
    ("OPTASK", "statusEquatesWith"): {
        "slots": ["uift.definition"],
        "reason": "Query-time pseudo-field for state-equivalence comparison; accepted in UIFT keys.",
    },
    ("OPTASK", "assignmentsListString"): {
        "slots": ["uivw.column.valuefield"],
        "reason": "Tile data source for component.assignmentslist; accepted only in UIVW column valuefield paired with the matching tile.",
    },
    ("TASK", "assignmentsListString"): {
        "slots": ["uivw.column.valuefield"],
        "reason": "Same as OPTASK — tile data source.",
    },
}


def _slot_from_path(path: str) -> str:
    """Map a validator-internal path to a PSEUDO_FIELDS slot key."""
    if path.startswith("uift.definition"):
        return "uift.definition"
    if path.startswith("uivw.definition.column[") and (path.endswith(".valuefield") or ".valuefield:" in path):
        return "uivw.column.valuefield"
    if path.startswith("uigb.definition.group["):
        return "uigb.group.valuefield"
    if path.startswith("report.sortBy"):
        return "report.sortBy"
    return path


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(
                prev[j] + 1,         # deletion
                curr[-1] + 1,        # insertion
                prev[j-1] + (ca != cb)  # substitution
            ))
        prev = curr
    return prev[-1]


def _suggest(field: str, metadata: dict, max_distance: int = 3) -> list:
    candidates = list(metadata.get("fields", {}).keys())
    scored = [(c, _levenshtein(field, c)) for c in candidates]
    scored = [(c, d) for c, d in scored if d <= max_distance]
    scored.sort(key=lambda t: t[1])
    return [c for c, d in scored[:3]]


def _strip_prefix(key: str) -> tuple:
    m = PREFIX_RE.match(key)
    if m:
        return m.group(0), key[m.end():]
    return "", key


def _strip_de_and_mod(key: str) -> tuple:
    """Returns (has_DE, join_path, base_field)."""
    s = key
    if s.endswith("_Mod"):
        s = s[:-4]
    has_de = False
    if s.startswith("DE:"):
        has_de = True
        s = s[3:]
    # Join path: split on `:` except inside DE: name
    if ":" in s:
        parts = s.split(":")
        return has_de, parts[:-1], parts[-1]
    return has_de, [], s


def _is_session_token(value: Any) -> bool:
    return isinstance(value, str) and SESSION_TOKEN_RE.match(value) is not None


def _resolve_uiObjCode_for_exists_block(
        defn: dict, block_id: str) -> Optional[str]:
    """For EXISTS:<letter>: blocks, return the block's $$OBJCODE value."""
    key = f"EXISTS:{block_id}:$$OBJCODE"
    return defn.get(key)


def _relation_exists(rel: str, metadata: dict) -> bool:
    """A relation hop may live in `references` (most common) or, on some metadata
    shapes, as a field whose type indicates a reference. Check both."""
    if rel in metadata.get("references", {}):
        return True
    if rel in metadata.get("collections", {}):
        return True
    # Fallback: some metadata shapes store relations alongside fields
    if rel in metadata.get("fields", {}):
        return True
    return False


def validate(bundle: dict, host: str, cache=None, force: bool = False,
             api_key: Optional[str] = None,
             de_fetch=None,
             whitelist_dir: Optional[str] = None) -> dict:
    cache = cache or _default_cache_adapter()
    errors: list = []
    warnings: list = []
    de_refs: list = []
    tenant_whitelist = _load_whitelist(host, whitelist_dir)
    if tenant_whitelist.get("_corrupt"):
        warnings.append({
            "reason": (f"Per-tenant whitelist at {_whitelist_path(host, whitelist_dir)} "
                       f"is corrupt; treated as empty. Recover via --forget-all.")
        })
    report_uiObjCode = (
        bundle.get("report", {}).get("uiObjCode")
        or bundle.get("uift", {}).get("uiObjCode")
        or bundle.get("uigb", {}).get("uiObjCode")
        or bundle.get("uivw", {}).get("uiObjCode")
    )
    if not report_uiObjCode:
        return {"valid": True, "errors": [], "warnings": [
            {"reason": "No uiObjCode in bundle; nothing to validate."}
        ], "de_refs": de_refs}

    metadata = cache.get(host, report_uiObjCode)
    if metadata is None:
        warnings.append({
            "reason": f"No cached metadata for uiObjCode={report_uiObjCode} on host={host}; "
                      f"pre-flight running in best-effort mode."
        })
        # Soft-pass when metadata is missing
        return {"valid": True, "errors": [], "warnings": warnings,
                "de_refs": de_refs}

    # Walk UIFT.definition keys
    uift = bundle.get("uift") or {}
    defn = uift.get("definition") or {}
    if isinstance(defn, dict):
        for key in defn.keys():
            _validate_filter_key(key, defn, report_uiObjCode, metadata,
                                 cache, host, errors, warnings, de_refs,
                                 tenant_whitelist=tenant_whitelist)

    # EXISTS-block count gate (gotcha #17). Adobe documents 5 as the hard
    # cap; the reporting engine usually errors above that, and prompt-driven
    # filtering is the escape hatch. Count DISTINCT EXISTS letter blocks
    # (each `EXISTS:<letter>:<inner>` key shares a letter with its siblings
    # — they're all the same block).
    _check_exists_count(defn, errors, warnings, force=force)

    # Walk UIVW.definition.column[]
    uivw = bundle.get("uivw") or {}
    vdefn = uivw.get("definition") or {}
    if isinstance(vdefn, dict):
        for idx, col in enumerate(vdefn.get("column", [])):
            _validate_column(col, idx, report_uiObjCode, metadata,
                             cache, host, errors, warnings,
                             tenant_whitelist=tenant_whitelist)

    # Walk UIGB.definition.group[]
    uigb = bundle.get("uigb") or {}
    gdefn = uigb.get("definition") or {}
    if isinstance(gdefn, dict):
        for idx, grp in enumerate(gdefn.get("group", [])):
            _validate_group(grp, idx, report_uiObjCode, metadata, errors,
                            tenant_whitelist=tenant_whitelist)

    # Walk REPORT.sortBy fields
    report = bundle.get("report") or {}
    for sort_field in ("sortBy", "sortBy2", "sortBy3"):
        sb = report.get(sort_field)
        if isinstance(sb, str) and sb and sb != "":
            _validate_field_against_metadata(
                sb, f"report.{sort_field}", metadata, report_uiObjCode, errors,
                tenant_whitelist=tenant_whitelist,
            )

    if de_refs:
        if api_key:
            fetcher = de_fetch or _default_de_fetch
            names = sorted({r["name"] for r in de_refs})
            resp = fetcher(host, names, api_key)
            if "_fetch_error" in resp:
                for r in de_refs:
                    warnings.append({
                        "path": r["path"], "value": r["name"],
                        "reason": f"DE: parity HTTP failed ({resp['_fetch_error']}); "
                                  f"could not confirm '{r['name']}' on destination."
                    })
            else:
                found_names = {row.get("name") for row in resp.get("data", [])
                               if row.get("name")}
                for r in de_refs:
                    if r["name"] not in found_names:
                        errors.append({
                            "path": r["path"], "value": r["name"],
                            "reason": (f"DE:{r['name']} not found on destination "
                                       f"({r['uiObjCode']}). No custom-form parameter "
                                       f"by that name exists on this tenant."),
                            "suggestions": [],
                        })
        else:
            for r in de_refs:
                warnings.append({
                    "path": r["path"], "value": r["name"],
                    "reason": (f"DE: parity skipped (no API key — export "
                               f"WF_API_KEY or pass --api-key); cannot "
                               f"confirm '{r['name']}' exists on destination."),
                })

    if force:
        if errors:
            for e in errors:
                warnings.append({
                    "forced": True,
                    "path": e.get("path"),
                    "value": e.get("value"),
                    "reason": e.get("reason"),
                    "suggestions": e.get("suggestions", []),
                })
            errors = []
        else:
            warnings.append({
                "forced": True,
                "reason": "nothing to force: no errors to override.",
            })

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "de_refs": de_refs,
    }


EXISTS_PREFIX_RE = re.compile(r"^EXISTS:([a-z]):")
EXISTS_CAP = 5  # Adobe-documented hard cap per filter
EXISTS_WARN_AT = 4  # one shy — surface the upcoming ceiling


def _check_exists_count(defn: dict, errors: list, warnings: list,
                        force: bool = False) -> None:
    """Count distinct EXISTS letter blocks in a UIFT definition.

    At EXISTS_WARN_AT (4), emit a warning suggesting prompt-driven
    filtering. At EXISTS_CAP+ (5+), emit a hard error that `--force`
    overrides. See knowledge/reports/05-gotchas.md #17.
    """
    if not isinstance(defn, dict):
        return
    letters: set[str] = set()
    for key in defn.keys():
        m = EXISTS_PREFIX_RE.match(key)
        if m:
            letters.add(m.group(1))
    n = len(letters)
    if n >= EXISTS_CAP:
        message = (
            f"UIFT.definition contains {n} distinct EXISTS letter block(s) — "
            f"at or above Adobe's documented cap of {EXISTS_CAP}. The "
            "reporting engine usually errors at this point. Escape hatch: "
            "hoist the EXISTS blocks into a custom prompt (one option per "
            "intended filter — only the picked option fires per query). See "
            "knowledge/reports/05-gotchas.md #17."
        )
        if force:
            warnings.append({
                "path": "uift.definition",
                "value": sorted(letters),
                "reason": "[--force overrode EXISTS-cap error] " + message,
            })
        else:
            errors.append({
                "path": "uift.definition",
                "value": sorted(letters),
                "reason": message,
                "suggestions": [
                    "Refactor: hoist the EXISTS blocks into a custom prompt "
                    "with one option per filter.",
                    "Or split the report into two reports.",
                    "Or re-run with --force if you've confirmed this "
                    "specific tenant tolerates a value above the documented "
                    f"cap of {EXISTS_CAP}.",
                ],
            })
    elif n >= EXISTS_WARN_AT:
        warnings.append({
            "path": "uift.definition",
            "value": sorted(letters),
            "reason": (
                f"UIFT.definition contains {n} distinct EXISTS letter "
                f"block(s) — approaching Adobe's documented cap of "
                f"{EXISTS_CAP}. Consider migrating to prompt-driven "
                "filtering before adding another."
            ),
        })


def _validate_filter_key(key: str, defn: dict, uiObjCode: str, metadata: dict,
                         cache, host: str, errors: list, warnings: list,
                         de_refs: list, tenant_whitelist=None) -> None:
    if key == "" or not isinstance(key, str):
        return
    prefix, inner = _strip_prefix(key)
    # EXISTS block: resolve sub-objCode
    if prefix.startswith("EXISTS:"):
        block_letter = prefix.split(":")[1]
        if inner in EXISTS_CONTROL:
            return
        sub_objcode = _resolve_uiObjCode_for_exists_block(defn, block_letter)
        if not sub_objcode:
            return  # block missing $$OBJCODE; skip
        sub_metadata = cache.get(host, sub_objcode)
        if sub_metadata is None:
            warnings.append({
                "reason": f"EXISTS block references {sub_objcode}; no cached metadata"
            })
            return
        if inner.endswith("_Mod"):
            return
        has_de, join_path, base = _strip_de_and_mod(inner)
        if not base or base == "ID":
            return  # ID is implicit join key
        if has_de:
            # EXISTS:<l>+DE — parity ref resolves against the block's $$OBJCODE
            de_refs.append({
                "name": base, "uiObjCode": sub_objcode,
                "path": f"uift.definition.{key}",
            })
            return
        _validate_field_against_metadata(
            base, f"uift.definition.{key}", sub_metadata, sub_objcode, errors,
            tenant_whitelist=tenant_whitelist,
        )
        return
    # OR group or no prefix: same uiObjCode context as bare keys
    if inner.endswith("_Mod"):
        return  # _Mod sibling handled with base key
    has_de, join_path, base = _strip_de_and_mod(inner)
    if has_de:
        # OR:<n>+DE inherits outer uiObjCode (OR conditions logic, not scope)
        de_refs.append({
            "name": base, "uiObjCode": uiObjCode,
            "path": f"uift.definition.{key}",
        })
        return
    if not base:
        return
    # Join path: walk relations (best-effort)
    if join_path:
        # Single-hop check: assert join_path[0] is a relation on uiObjCode's metadata
        rel = join_path[0]
        if not _relation_exists(rel, metadata):
            errors.append({
                "path": f"uift.definition.{key}",
                "value": defn.get(key),
                "reason": f"{uiObjCode} has no relation '{rel}' for join path",
                "suggestions": _suggest(rel, metadata),
            })
        # Don't recurse beyond one hop in v0.9.0
        return
    _validate_field_against_metadata(
        base, f"uift.definition.{key}", metadata, uiObjCode, errors,
        tenant_whitelist=tenant_whitelist,
    )


def _scan_for_curly_quotes(expr: str, path: str, errors: list) -> None:
    """Detect Unicode curly quotes inside any expression string.

    Workfront's text-mode parser only recognises straight ASCII `"` / `'`.
    Smart curlies — `'` (U+2018), `'` (U+2019), `"` (U+201C), `"` (U+201D) —
    parse as unterminated string tokens, silently breaking the column /
    aggregator. See knowledge/reports/05-gotchas.md #14.
    """
    if not isinstance(expr, str):
        return
    if not CURLY_QUOTE_RE.search(expr):
        return
    found = sorted({c for c in expr if CURLY_QUOTE_RE.match(c)})
    errors.append({
        "path": path,
        "value": expr,
        "reason": (
            f"valueexpression contains Unicode curly quote(s) {found} — "
            "Workfront's text-mode parser only accepts straight ASCII "
            "quotes (\" U+0022 and ' U+0027). Curly quotes parse as "
            "unterminated string tokens; the column will render empty."
        ),
        "suggestions": [
            "Re-paste through a plain-text editor (TextEdit in plain mode "
            "on macOS, Notepad on Windows) before sending.",
            "Or pipe through sed: `pbpaste | sed 's/[“”]/\"/g; "
            "s/[‘’]/'\"'\"'/g' | pbcopy`",
            "See knowledge/reports/05-gotchas.md #14 for the full mechanic.",
        ],
    })


def _scan_valueexpression(expr: str, base_path: str, uiObjCode: str,
                          metadata: dict, cache, host: str,
                          errors: list, warnings: list,
                          tenant_whitelist=None) -> None:
    if not isinstance(expr, str):
        return
    # Curly-quote lint runs first — failing here implies the brace-ref
    # scan below would be parsing a syntactically broken expression.
    _scan_for_curly_quotes(expr, base_path, errors)
    matches = BRACE_REF_RE.findall(expr)
    # Pair adjacent `{rel}.{field}` references — detected by a literal `.{` in
    # the source after stripping the first match.
    i = 0
    seen_pairs = set()
    while i < len(matches):
        token = matches[i]
        # Look ahead: if expr contains "{<token>}.{<next>}", treat as join
        joined_lookahead = f"{{{token}}}.{{"
        if joined_lookahead in expr and i + 1 < len(matches):
            rel = token
            field = matches[i + 1]
            if (rel, field) in seen_pairs:
                i += 2
                continue
            seen_pairs.add((rel, field))
            if not _relation_exists(rel, metadata):
                errors.append({
                    "path": base_path,
                    "value": f"{{{rel}}}.{{{field}}}",
                    "reason": f"{uiObjCode} has no relation '{rel}' for brace-join in valueexpression",
                    "suggestions": _suggest(rel, metadata),
                })
            # don't recurse on join target — best-effort
            i += 2
            continue
        # Bare brace ref
        if token.startswith("$$"):
            i += 1
            continue
        _validate_field_against_metadata(
            token, f"{base_path}:{token}", metadata, uiObjCode, errors,
            tenant_whitelist=tenant_whitelist,
        )
        i += 1


def _validate_column(col: dict, idx: int, uiObjCode: str, metadata: dict,
                     cache, host: str, errors: list, warnings: list,
                     tenant_whitelist=None) -> None:
    if not isinstance(col, dict):
        return
    vf = col.get("valuefield")
    if isinstance(vf, str) and vf and ":" not in vf and not vf.startswith("$$"):
        # Bare field — validate. Skip DE-looking values (space in name or
        # leading uppercase like "Approved Hours") as those are custom-field
        # references handled by the DE: parity check.
        if " " not in vf and not (vf[0].isupper() and len(vf) > 1):
            _validate_field_against_metadata(
                vf, f"uivw.definition.column[{idx}].valuefield:{vf}",
                metadata, uiObjCode, errors,
                tenant_whitelist=tenant_whitelist,
            )

    qs = col.get("querysort")
    if isinstance(qs, str) and qs:
        # INVERTED grammar: [<join>:][DE:]<field>  (join FIRST, then DE:, then field)
        s = qs
        join_path = []
        # Walk hop tokens; stop when we hit DE: or run out of `:`
        while ":" in s and not s.startswith("DE:"):
            head, _, s = s.partition(":")
            join_path.append(head)
        has_de = s.startswith("DE:")
        if has_de:
            s = s[3:]
        base = s
        path = f"uivw.definition.column[{idx}].querysort:{qs}"
        if not base:
            pass
        elif join_path:
            rel = join_path[0]
            if not _relation_exists(rel, metadata):
                errors.append({
                    "path": path,
                    "value": qs,
                    "reason": f"{uiObjCode} has no relation '{rel}' for querysort join path",
                    "suggestions": _suggest(rel, metadata),
                })
            # don't recurse: querysort join terminus check is best-effort in v0.10.0
        elif has_de:
            # DE: parity is handled by A5; querysort with bare DE: is recorded there
            pass
        else:
            _validate_field_against_metadata(
                base, path, metadata, uiObjCode, errors,
                tenant_whitelist=tenant_whitelist,
            )

    ve = col.get("valueexpression")
    if isinstance(ve, str) and ve:
        _scan_valueexpression(
            ve, f"uivw.definition.column[{idx}].valueexpression",
            uiObjCode, metadata, cache, host, errors,
            warnings if warnings is not None else [],
            tenant_whitelist=tenant_whitelist,
        )

    # Aggregator can carry its own valueexpression (mutually exclusive
    # with aggregator.valuefield — see 07-view-patterns.md § Aggregator).
    # The curly-quote risk lives here too.
    agg = col.get("aggregator")
    if isinstance(agg, dict):
        agg_ve = agg.get("valueexpression")
        if isinstance(agg_ve, str) and agg_ve:
            _scan_valueexpression(
                agg_ve,
                f"uivw.definition.column[{idx}].aggregator.valueexpression",
                uiObjCode, metadata, cache, host, errors,
                warnings if warnings is not None else [],
                tenant_whitelist=tenant_whitelist,
            )


def _validate_group(grp: dict, idx: int, uiObjCode: str, metadata: dict,
                    errors: list, tenant_whitelist=None) -> None:
    if not isinstance(grp, dict):
        return
    vf = grp.get("valuefield")
    if isinstance(vf, str) and vf and ":" not in vf and not vf.startswith("$$"):
        if " " not in vf and not (vf[0].isupper() and len(vf) > 1):
            _validate_field_against_metadata(
                vf, f"uigb.definition.group[{idx}].valuefield",
                metadata, uiObjCode, errors,
                tenant_whitelist=tenant_whitelist,
            )
    # Group valueexpression — same curly-quote risk as column valueexpression.
    # (Note: per gotcha #18, groupBy via valueexpression silently breaks
    # the Summary tab + charts. We don't enforce that here — the user
    # gets a separate warning in the authoring interview. This pre-flight
    # call is only the curly-quote lint, not the design-shape warning.)
    g_ve = grp.get("valueexpression")
    if isinstance(g_ve, str) and g_ve:
        _scan_for_curly_quotes(
            g_ve, f"uigb.definition.group[{idx}].valueexpression", errors,
        )


def _validate_field_against_metadata(field: str, path: str, metadata: dict,
                                     uiObjCode: str, errors: list,
                                     tenant_whitelist=None) -> None:
    if field in metadata.get("fields", {}):
        return
    # Per-tenant whitelist (overrides global)
    if tenant_whitelist:
        for entry in tenant_whitelist.get("fields", []):
            if entry.get("uiObjCode") == uiObjCode and entry.get("fieldname") == field:
                if _slot_from_path(path) in entry.get("slots", []):
                    return
                break
    # PSEUDO_FIELDS allowlist (global, hard-coded). Slot must match.
    pseudo = PSEUDO_FIELDS.get((uiObjCode, field))
    if pseudo:
        slot = _slot_from_path(path)
        if slot in pseudo["slots"]:
            return
        # Right field, wrong slot — fall through to normal error path with
        # the pseudo's reason appended as a hint.
    hint = SYNONYM_HINTS.get((uiObjCode, field))
    suggestions = _suggest(field, metadata)
    error_entry = {
        "path": path,
        "value": field,
        "reason": f"{uiObjCode} has no field '{field}'.",
        "suggestions": suggestions,
    }
    if hint:
        error_entry["reason"] += " " + hint
    if pseudo and _slot_from_path(path) not in pseudo["slots"]:
        error_entry["reason"] += f" Pseudo-field allowed only in: {', '.join(pseudo['slots'])}."
    errors.append(error_entry)


class _DefaultCacheAdapter:
    def get(self, host: str, obj_code: str):
        if schema_cache is None:
            return None
        entry = schema_cache.get(host, obj_code.lower())
        if entry is None:
            return None
        # schema_cache stores {fields: {...}, schemaHash, fetchedAt}; the validator
        # expects {fields: {...}, references: {...}, collections: {...}} shape.
        fields_blob = entry.get("fields", {})
        # When schema_cache.put got the full metadata dict, `fields_blob` may
        # actually be the full metadata document (put falls back to the raw
        # payload when no "fields" subkey is present). Detect and unwrap.
        if isinstance(fields_blob, dict) and "fields" in fields_blob and isinstance(fields_blob.get("fields"), dict):
            return fields_blob
        return {"fields": fields_blob if isinstance(fields_blob, dict) else {}}


def _default_cache_adapter():
    return _DefaultCacheAdapter()


def _default_de_fetch(host: str, names: list, api_key: str) -> dict:
    """One batched GET /parameter/search with OR-joined names."""
    import urllib.parse
    import urllib.request
    qs_pairs = [("apiKey", api_key), ("fields", "ID,name,parameterGroup:name"),
                ("$$LIMIT", "100")]
    for i, n in enumerate(names):
        if i == 0:
            qs_pairs.append(("name", n))
            qs_pairs.append(("name_Mod", "eq"))
        else:
            qs_pairs.append((f"OR:{i}:name", n))
            qs_pairs.append((f"OR:{i}:name_Mod", "eq"))
    url = (f"https://{host}/attask/api/v17.0/parameter/search?"
           + urllib.parse.urlencode(qs_pairs))
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"_fetch_error": str(exc)}


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-stdin", action="store_true",
                   required=False, default=False)
    p.add_argument("--host", default=None,
                   help="Destination tenant host; falls back to the WF_HOST "
                        "env var when omitted.")
    p.add_argument("--force", action="store_true",
                   help="Demote errors to warnings and set valid:true.")
    p.add_argument("--api-key", default=None,
                   help="API key for DE: parity check. Prefer exporting "
                        "WF_API_KEY instead — a key passed as a flag lands in "
                        "the process argv (visible in `ps`). Kept for "
                        "backward compat; if neither is set, DE refs become "
                        "warnings.")
    p.add_argument("--whitelist-dir", default=None,
                   help="Per-tenant whitelist directory (default ~/.cache/wf-toolkit).")
    p.add_argument("--learn", metavar="OBJ:FIELD:SLOT",
                   help="Add one whitelist entry, e.g. OPTASK:customField:uift.definition")
    p.add_argument("--learn-from-blocked", metavar="PREFLIGHT_OUTPUT.json",
                   help="Read forced-warnings from a prior preflight run and persist them.")
    p.add_argument("--learn-objcode", default=None,
                   help="uiObjCode for --learn-from-blocked (the bundle's uiObjCode).")
    p.add_argument("--forget", metavar="OBJ:FIELD",
                   help="Remove one whitelist entry.")
    p.add_argument("--forget-all", action="store_true",
                   help="Wipe the entire per-tenant whitelist.")
    args = p.parse_args()
    host = args.host or os.environ.get("WF_HOST")
    if not host:
        print("error: --host or the WF_HOST env var is required", file=sys.stderr)
        return 2
    api_key = args.api_key or os.environ.get("WF_API_KEY")
    if args.forget_all:
        if forget_all(host, cache_dir=args.whitelist_dir):
            print(json.dumps({"forgot_all": True, "host": host}))
        else:
            print(json.dumps({"forgot_all": False, "reason": "no whitelist file"}))
        return 0
    if args.forget:
        parts = args.forget.split(":")
        if len(parts) != 2:
            print("error: --forget expects OBJ:FIELD", file=sys.stderr)
            return 2
        ok = forget(host, parts[0], parts[1], cache_dir=args.whitelist_dir)
        print(json.dumps({"forgot": ok, "uiObjCode": parts[0], "fieldname": parts[1]}))
        return 0
    if args.learn:
        parts = args.learn.split(":", 2)
        if len(parts) != 3:
            print("error: --learn expects OBJ:FIELD:SLOT", file=sys.stderr)
            return 2
        entry = learn(host, parts[0], parts[1], parts[2],
                      cache_dir=args.whitelist_dir, learned_via="manual")
        print(json.dumps({"learned": entry}))
        return 0
    if args.learn_from_blocked:
        if not args.learn_objcode:
            print("error: --learn-from-blocked requires --learn-objcode OBJ",
                  file=sys.stderr)
            return 2
        if not os.path.exists(args.learn_from_blocked):
            print(f"error: no preflight output file at {args.learn_from_blocked}",
                  file=sys.stderr)
            return 2
        added = learn_from_blocked(
            host, args.learn_objcode, args.learn_from_blocked,
            cache_dir=args.whitelist_dir
        )
        print(json.dumps({"learned": added}))
        return 0
    # Normal validate path requires --from-stdin
    if not args.from_stdin:
        print("error: --from-stdin required when not using --learn/--forget", file=sys.stderr)
        return 2
    try:
        bundle = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: malformed JSON on stdin: {exc}", file=sys.stderr)
        return 2
    result = validate(bundle, host, force=args.force, api_key=api_key,
                      whitelist_dir=args.whitelist_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
