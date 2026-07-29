#!/usr/bin/env python3
"""phase_b_probe.py — empirical-discovery probe driver for workfront-custom-forms Phase B.

Two modes:

  coverage-matrix  Probe (dataType, displayType) combinations against the
                   verification sandbox across multiple objCodes via wf-curl.sh.
                   End-of-run sweep via wf-cleanup.sh (script does not delete
                   inline).

  displaytype-discovery <displayType>
                   Probe a candidate displayType against the active environment
                   folder via wf-env-curl.sh. Self-cleaning — each probe
                   POSTs, captures ID, DELETEs before returning.

Pure-logic parts (name building, matrix building, decision logic, JSON output
shape) are unit-tested in tests/test_phase_b_probe.py. The probe runs themselves
are manual smoke against live tenants.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import subprocess
import sys
import time
from typing import Optional

# --- constants ---

DEFAULT_OBJCODES_COVERAGE = [
    "PROJ", "TASK", "OPTASK", "USER", "GROUP", "PORT", "PROG", "DOCU", "TMPL", "TTSK",
]

DEFAULT_COMBINATIONS = [
    ("TEXT", "TEXT"), ("TEXT", "TXTA"), ("TEXT", "SLCT"), ("TEXT", "CHCK"),
    ("TEXT", "RDIO"), ("TEXT", "MULT"), ("TEXT", "TYAH"), ("TEXT", "CALC"),
    ("NMBR", "TEXT"), ("NMBR", "CALC"),
    ("CURC", "TEXT"), ("CURC", "CALC"),
    ("DATE", "TEXT"), ("DATE", "CALC"),
    ("RICH", "RICH"),
    ("WIDGET", "WIDGET"),
]

CATEGORY_PREFIX_COVERAGE = "[wf-api-verify] phase-b"
CATEGORY_PREFIX_DISCOVERY = "[wf-phase-b-probe]"
PARAM_PREFIX_COVERAGE = "wf_verify_phase_b_"
PARAM_PREFIX_DISCOVERY = "wf_phase_b_probe_"

WRAPPER_VERIFY = "bash skills/workfront-api/scripts/wf-curl.sh"
WRAPPER_ENV = "bash skills/_shared/scripts/wf-env-curl.sh"


# --- name builders ---


def build_category_name(*, mode: str, objcode: str, ts: str) -> str:
    if mode == "coverage-matrix":
        return f"{CATEGORY_PREFIX_COVERAGE} {objcode} {ts}"
    if mode == "displaytype-discovery":
        return f"{CATEGORY_PREFIX_DISCOVERY} {objcode} {ts}"
    raise ValueError(f"unknown mode: {mode}")


def build_parameter_name(*, mode: str, data_type: str, display_type: str, ts: str) -> str:
    if mode == "coverage-matrix":
        return f"{PARAM_PREFIX_COVERAGE}{data_type}_{display_type}_{ts}"
    if mode == "displaytype-discovery":
        return f"{PARAM_PREFIX_DISCOVERY}{data_type}_{display_type}_{ts}"
    raise ValueError(f"unknown mode: {mode}")


# --- decision logic ---


def decide_displaytype_verdict(result: dict) -> str:
    """Classify a single displaytype-discovery probe result.

    Returns one of: 'accepted', 'absent', 'present-but-needs-config', 'inconclusive'.
    """
    status = result.get("http_status")
    response = result.get("response") or {}
    err = (response.get("error") or {}).get("message", "") if isinstance(response, dict) else ""

    if status == 200:
        return "accepted"
    if status == 400 and "unknown display type" in err.lower():
        return "absent"
    if status == 400 and "missing required field" in err.lower():
        return "present-but-needs-config"
    return "inconclusive"


# --- matrix builder ---


def build_matrix(probe_results: list, objcodes: Optional[list] = None) -> dict:
    """Build a per-(dataType, displayType) -> per-objCode availability map.

    Cells: (accepted), (rejected), — (not probed).
    """
    if objcodes is None:
        objcodes = sorted({r["objcode"] for r in probe_results})
    combos = sorted({(r["data_type"], r["display_type"]) for r in probe_results})
    matrix: dict = {}
    for combo in combos:
        matrix[combo] = {oc: "—" for oc in objcodes}
    for r in probe_results:
        combo = (r["data_type"], r["display_type"])
        if combo not in matrix:
            matrix[combo] = {oc: "—" for oc in objcodes}
        matrix[combo][r["objcode"]] = "✓" if r["accepted"] else "✗"
    return matrix


# --- JSON output ---


def write_output_json(*, mode: str, tenant: str, ts: str, probe_results: list, out_path: pathlib.Path) -> None:
    payload = {
        "mode": mode,
        "tenant": tenant,
        "captured_at": ts,
        "probes": probe_results,
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))


# --- live-probe stubs (Tasks 3+4 fill these in) ---


def run_coverage_matrix(*, dry_run: bool, throttle_ms: int, out_path: pathlib.Path) -> int:
    """Probe every (dataType, displayType) combination across DEFAULT_OBJCODES_COVERAGE
    against the verification sandbox via wf-curl.sh.

    For each objCode: POST one Category (carries the objTypes=[objCode] selector),
    then POST one Parameter per combination. The Parameter's name carries the
    wf_verify_ prefix (per Phase A's Parameter-name rule); the Category carries
    the [wf-api-verify] prefix. Cleanup is end-of-run via wf-cleanup.sh.

    Records per-probe: HTTP status, accepted flag, server error message,
    captured paramID/categoryID for sweep verification.
    """
    ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    tenant = _read_active_env_host()
    if tenant is None:
        print("phase_b_probe: no active environment slug. Run /wf-env-add first.", file=sys.stderr)
        return 1

    probe_results: list = []

    if dry_run:
        print(f"DRY RUN — coverage-matrix mode, tenant={tenant}, ts={ts}")
        for objcode in DEFAULT_OBJCODES_COVERAGE:
            cat_name = build_category_name(mode="coverage-matrix", objcode=objcode, ts=ts)
            print(f"  would POST Category: name='{cat_name}', objTypes=['{objcode}']")
            for (dt_, disp) in DEFAULT_COMBINATIONS:
                param_name = build_parameter_name(mode="coverage-matrix", data_type=dt_, display_type=disp, ts=ts)
                print(f"    would POST Parameter: name='{param_name}', dataType={dt_}, displayType={disp}")
        return 0

    print(f"phase_b_probe: coverage-matrix vs {tenant} — ts={ts}", file=sys.stderr)

    for objcode in DEFAULT_OBJCODES_COVERAGE:
        cat_name = build_category_name(mode="coverage-matrix", objcode=objcode, ts=ts)
        cat_id = _post_via(WRAPPER_VERIFY, "/attask/api/v17.0/category",
                           {"name": cat_name, "objTypes": [objcode]})
        if cat_id is None:
            print(f"  [{objcode}] CATEGORY-POST FAILED — skipping all combos", file=sys.stderr)
            for (dt_, disp) in DEFAULT_COMBINATIONS:
                probe_results.append({
                    "objcode": objcode, "data_type": dt_, "display_type": disp,
                    "http_status": -1, "accepted": False, "response": None,
                    "error": "category-post failed", "param_id": None, "category_id": None,
                    "cleanup_done": False,
                })
            continue

        print(f"  [{objcode}] Category created (ID={cat_id})", file=sys.stderr)

        for (dt_, disp) in DEFAULT_COMBINATIONS:
            # Append objCode to disambiguate — Parameter.name is unique across the
            # whole tenant, so the same (dataType, displayType) probed on different
            # objCodes needs distinct names.
            param_name = build_parameter_name(mode="coverage-matrix", data_type=dt_, display_type=disp, ts=ts) + f"_{objcode}"
            body = {
                "name": param_name,
                "label": param_name,
                "dataType": dt_,
                "displayType": disp,
            }
            status, response = _post_via_capture(WRAPPER_VERIFY, "/attask/api/v17.0/parameter", body)
            accepted = status == 200 and isinstance(response, dict) and "data" in response
            err = ""
            if not accepted and isinstance(response, dict):
                err = ((response.get("error") or {}).get("message") or "")
            param_id = (response.get("data") or {}).get("ID") if isinstance(response, dict) else None
            probe_results.append({
                "objcode": objcode, "data_type": dt_, "display_type": disp,
                "http_status": status, "accepted": accepted, "response": response,
                "error": err, "param_id": param_id, "category_id": cat_id,
                "cleanup_done": False,
            })
            mark = "✓" if accepted else "✗"
            print(f"    [{objcode} × {dt_}/{disp}] {mark} status={status} err={err[:80]}", file=sys.stderr)
            time.sleep(throttle_ms / 1000.0)

    write_output_json(mode="coverage-matrix", tenant=tenant, ts=ts,
                      probe_results=probe_results, out_path=out_path)
    print(f"phase_b_probe: wrote {out_path}", file=sys.stderr)
    print("phase_b_probe: NEXT: run wf-cleanup.sh to sweep test objects.", file=sys.stderr)
    return 0


def _split_env_prefix(wrapper_cmd: str) -> tuple:
    """Split a wrapper_cmd string with leading KEY=VALUE env-var tokens.

    Returns (env_extra_dict, argv_list). For 'WF_ENV_WRITE_ACK=1 bash foo.sh',
    returns ({'WF_ENV_WRITE_ACK': '1'}, ['bash', 'foo.sh']). For 'bash foo.sh'
    returns ({}, ['bash', 'foo.sh']). subprocess.run accepts env via kwarg —
    can't shell-interpret KEY=VALUE prefix tokens itself.
    """
    import os
    tokens = wrapper_cmd.split()
    env_extra: dict = {}
    while tokens and "=" in tokens[0] and tokens[0].split("=", 1)[0].isupper():
        k, v = tokens[0].split("=", 1)
        env_extra[k] = v
        tokens.pop(0)
    env = None
    if env_extra:
        env = os.environ.copy()
        env.update(env_extra)
    return (env, tokens)


def _post_via(wrapper_cmd: str, path: str, body: dict) -> Optional[str]:
    """Shell out to the wrapper, return created object's ID or None on failure.

    Body fields go through --data-urlencode 'updates={json}'.
    """
    env, argv = _split_env_prefix(wrapper_cmd)
    cmd = argv + ["-X", "POST", path, "--data-urlencode", f"updates={json.dumps(body)}"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        return None
    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    data = resp.get("data") or {}
    return data.get("ID")


def _post_via_capture(wrapper_cmd: str, path: str, body: dict) -> tuple:
    """Like _post_via but returns (http_status_proxy, response_json).

    The wrappers don't surface HTTP status directly; we infer from response shape:
    - response has 'data' → treat as 200
    - response has 'error' → treat as 400
    - neither → -1
    """
    env, argv = _split_env_prefix(wrapper_cmd)
    cmd = argv + ["-X", "POST", path, "--data-urlencode", f"updates={json.dumps(body)}"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        return (-1, None)
    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError:
        return (-1, {"raw": result.stdout})
    if isinstance(resp, dict) and "data" in resp:
        return (200, resp)
    if isinstance(resp, dict) and "error" in resp:
        return (400, resp)
    return (-1, resp)


def run_displaytype_discovery(*, display_type: str, target_objcode: str, env_slug: str,
                              dry_run: bool, throttle_ms: int, out_path: pathlib.Path) -> int:
    """Probe a candidate displayType against the active environment folder.

    Self-cleaning: each probe POSTs Category + Parameter, captures both IDs,
    then DELETEs Parameter + Category before returning. Prepends
    WF_ENV_WRITE_ACK=1 to every wrapper invocation (covers the case where
    the active environment is WF_ENV_TYPE=prod).
    """
    ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    tenant = _read_active_env_host()
    if tenant is None:
        print("phase_b_probe: no active environment slug. Run /wf-env-use first.", file=sys.stderr)
        return 1

    cat_name = build_category_name(mode="displaytype-discovery", objcode=target_objcode, ts=ts)
    param_name = build_parameter_name(mode="displaytype-discovery", data_type="TEXT",
                                      display_type=display_type, ts=ts)

    if dry_run:
        print(f"DRY RUN — displaytype-discovery mode, displayType={display_type}, "
              f"target={target_objcode}, tenant={tenant}, ts={ts}")
        print(f"  would POST Category: name='{cat_name}', objTypes=['{target_objcode}']")
        print(f"  would POST Parameter: name='{param_name}', dataType=TEXT, displayType={display_type}")
        print(f"  would DELETE Parameter then Category (self-cleaning)")
        return 0

    print(f"phase_b_probe: displaytype-discovery '{display_type}' vs {tenant} — ts={ts}", file=sys.stderr)

    wrapper_write = f"WF_ENV_WRITE_ACK=1 {WRAPPER_ENV}"

    # 1. Category POST
    cat_id = _post_via(wrapper_write, "/attask/api/v17.0/category",
                       {"name": cat_name, "objTypes": [target_objcode]})
    if cat_id is None:
        print("  CATEGORY-POST failed — aborting probe", file=sys.stderr)
        probe_results = [{
            "objcode": target_objcode, "data_type": "TEXT", "display_type": display_type,
            "http_status": -1, "accepted": False, "response": None,
            "error": "category-post failed", "param_id": None, "category_id": None,
            "cleanup_done": False, "verdict": "inconclusive",
        }]
        write_output_json(mode="displaytype-discovery", tenant=tenant, ts=ts,
                          probe_results=probe_results, out_path=out_path)
        return 1

    # 2. Parameter POST (the actual probe)
    body = {
        "name": param_name, "label": param_name,
        "dataType": "TEXT", "displayType": display_type,
    }
    status, response = _post_via_capture(wrapper_write, "/attask/api/v17.0/parameter", body)
    param_id = (response.get("data") or {}).get("ID") if isinstance(response, dict) else None
    accepted = status == 200 and param_id is not None
    err = ""
    if not accepted and isinstance(response, dict):
        err = ((response.get("error") or {}).get("message") or "")
    verdict = decide_displaytype_verdict({"http_status": status, "response": response, "error": err})
    print(f"  PROBE: status={status} accepted={accepted} verdict={verdict} err={err[:80]}", file=sys.stderr)

    time.sleep(throttle_ms / 1000.0)

    # 3. Cleanup — DELETE Parameter (if created), then Category
    cleanup_ok = True
    if param_id is not None:
        if not _delete_via(wrapper_write, f"/attask/api/v17.0/parameter/{param_id}"):
            print(f"  CLEANUP: failed to DELETE Parameter {param_id}", file=sys.stderr)
            cleanup_ok = False
        else:
            print(f"  CLEANUP: deleted Parameter {param_id}", file=sys.stderr)
    if not _delete_via(wrapper_write, f"/attask/api/v17.0/category/{cat_id}"):
        print(f"  CLEANUP: failed to DELETE Category {cat_id}", file=sys.stderr)
        cleanup_ok = False
    else:
        print(f"  CLEANUP: deleted Category {cat_id}", file=sys.stderr)

    probe_results = [{
        "objcode": target_objcode, "data_type": "TEXT", "display_type": display_type,
        "http_status": status, "accepted": accepted, "response": response,
        "error": err, "param_id": param_id, "category_id": cat_id,
        "cleanup_done": cleanup_ok, "verdict": verdict,
    }]
    write_output_json(mode="displaytype-discovery", tenant=tenant, ts=ts,
                      probe_results=probe_results, out_path=out_path)
    print(f"phase_b_probe: wrote {out_path}", file=sys.stderr)
    return 0


def _read_active_slug() -> Optional[str]:
    active_file = pathlib.Path.home() / "wf-envs" / ".active"
    if not active_file.exists():
        return None
    return active_file.read_text().strip() or None


def _read_active_env_host() -> Optional[str]:
    envs_home = pathlib.Path.home() / "wf-envs"
    active_file = envs_home / ".active"
    if not active_file.exists():
        return None
    slug = active_file.read_text().strip()
    env_file = envs_home / slug / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text().splitlines():
        if line.startswith("WF_HOST="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def _delete_via(wrapper_cmd: str, path: str) -> bool:
    env, argv = _split_env_prefix(wrapper_cmd)
    cmd = argv + ["-X", "DELETE", path]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        return False
    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return resp.get("success") is True or (isinstance(resp.get("data"), dict) and "success" in resp.get("data", {}))


# --- CLI ---


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="phase_b_probe.py", description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)

    cov = sub.add_parser("coverage-matrix", help="probe (dataType, displayType) across objCodes (verification sandbox)")
    cov.add_argument("--dry-run", action="store_true")
    cov.add_argument("--throttle-ms", type=int, default=100)
    cov.add_argument("--output", type=pathlib.Path, default=pathlib.Path("/tmp/pb-matrix.json"))

    dis = sub.add_parser("displaytype-discovery", help="probe a candidate displayType on the active environment folder")
    dis.add_argument("display_type", help="e.g. HIERARCHY, ICON, LOCATION")
    dis.add_argument("--target-objcode", default="PROJ")
    dis.add_argument("--env-slug", default=None,
                     help="for traceability only — defaults to the active slug from "
                          "~/wf-envs/.active; the wrapper sources whichever environment is active")
    dis.add_argument("--dry-run", action="store_true")
    dis.add_argument("--throttle-ms", type=int, default=100)
    dis.add_argument("--output", type=pathlib.Path, default=pathlib.Path("/tmp/pb-displaytype.json"))

    return p


def main(argv: Optional[list] = None) -> int:
    args = _make_parser().parse_args(argv)
    if args.mode == "coverage-matrix":
        return run_coverage_matrix(dry_run=args.dry_run, throttle_ms=args.throttle_ms, out_path=args.output)
    if args.mode == "displaytype-discovery":
        env_slug = args.env_slug or _read_active_slug()
        if env_slug is None:
            print("phase_b_probe: no --env-slug given and no active environment "
                  "(~/wf-envs/.active missing). Run /wf-env-use first.", file=sys.stderr)
            return 1
        return run_displaytype_discovery(
            display_type=args.display_type, target_objcode=args.target_objcode,
            env_slug=env_slug, dry_run=args.dry_run, throttle_ms=args.throttle_ms,
            out_path=args.output,
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
