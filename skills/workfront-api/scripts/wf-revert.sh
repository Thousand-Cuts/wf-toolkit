#!/usr/bin/env bash
# wf-revert.sh — replay a wf-curl audit file to restore an object's pre-write state.
#
# Usage:
#   wf-revert.sh <audit-file>
#   wf-revert.sh --latest        # revert the most recently captured audit file
#   wf-revert.sh --list          # list captured audit files for the active environment
#
# Behavior:
#   - For regular PUT/DELETE mutations: PUTs the captured scalar fields back
#     to the object via `updates=<JSON>`. Read-only fields are silently
#     ignored by Workfront.
#   - For action endpoints (e.g. assignMultiple): prints the captured state
#     and the revert command to run (action-specific revert needs operator
#     judgment). Does NOT auto-call action endpoints.

set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
ACTIVE_FILE="${WF_ENVS_HOME}/.active"

die() { echo "wf-revert: $*" >&2; exit 1; }

[ -f "$ACTIVE_FILE" ] || die "no active environment. Run /wf-env-use <slug> first."
ACTIVE="$(<"$ACTIVE_FILE")"
AUDIT_DIR="${WF_ENVS_HOME}/${ACTIVE}/audit"

usage() {
  cat >&2 <<EOF
Usage:
  wf-revert.sh <audit-file>      # revert the object captured in <audit-file>
  wf-revert.sh --latest          # revert the most recent audit
  wf-revert.sh --list            # list captured audit files for ${ACTIVE}
EOF
  exit 2
}

case "${1:-}" in
  "" ) usage ;;
  --list)
    if [ ! -d "$AUDIT_DIR" ] || [ -z "$(ls -A "$AUDIT_DIR" 2>/dev/null)" ]; then
      echo "wf-revert: no audit files in ${AUDIT_DIR}"
      exit 0
    fi
    ls -1t "$AUDIT_DIR"
    exit 0
    ;;
  --latest)
    AUDIT_FILE="$(ls -1t "$AUDIT_DIR" 2>/dev/null | head -1 || true)"
    [ -n "$AUDIT_FILE" ] || die "no audit files in ${AUDIT_DIR}"
    AUDIT_FILE="${AUDIT_DIR}/${AUDIT_FILE}"
    ;;
  -h|--help) usage ;;
  *)
    AUDIT_FILE="$1"
    if [ ! -f "$AUDIT_FILE" ] && [ -f "${AUDIT_DIR}/$1" ]; then
      AUDIT_FILE="${AUDIT_DIR}/$1"
    fi
    ;;
esac

[ -f "$AUDIT_FILE" ] || die "audit file not found: ${AUDIT_FILE}"

# Parse audit file via python.
parsed="$(python3 -c '
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
before = d.get("before", {}).get("data", {}) or {}
# Strip non-revertible fields: ID and any collection (list-typed) fields,
# which we will print separately for the operator.
scalars = {k: v for k, v in before.items() if not isinstance(v, list) and not isinstance(v, dict) and k != "ID" and k != "objCode"}
print(json.dumps({
    "objcode": d.get("objcode"),
    "object_id": d.get("object_id"),
    "action": d.get("action") or "",
    "path": d.get("path"),
    "method": d.get("method"),
    "captured_at": d.get("captured_at"),
    "scalars": scalars,
    "collections_present": [k for k, v in before.items() if isinstance(v, list)],
    "before_full": before,
}, indent=2))
' "$AUDIT_FILE")"

OBJCODE="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("objcode",""))')"
OBJ_ID="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("object_id",""))')"
ACTION="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("action",""))')"

echo "wf-revert: audit file ${AUDIT_FILE}"
echo "wf-revert: objcode=${OBJCODE} id=${OBJ_ID} action=${ACTION:-<none>}"

if [ -n "$ACTION" ]; then
  echo "wf-revert: this audit captured an action-endpoint call (${ACTION})."
  echo "wf-revert: action reverts are endpoint-specific and not auto-replayed."
  echo "wf-revert: captured before-state:"
  printf '%s\n' "$parsed" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin).get("before_full",{}), indent=2))'
  case "$ACTION" in
    assignMultiple)
      echo
      echo "wf-revert: to restore the assignMultiple state, replay:"
      python3 -c '
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
b = d.get("before", {}).get("data", {}) or {}
assigns = b.get("assignments") or []
team_ids = sorted({a.get("teamID") for a in assigns if a.get("teamID")})
user_ids = sorted({a.get("assignedToID") for a in assigns if a.get("assignedToID")})
role_ids = sorted({a.get("roleID") for a in assigns if a.get("roleID")})
updates = {"teamIDs": team_ids, "userIDs": user_ids, "roleIDs": role_ids}
print("  ./skills/workfront-api/scripts/wf-curl.sh -X PUT /attask/api/v17.0/" + d["objcode"] + "/" + d["object_id"] + "/assignMultiple \\\\")
print("    --data-urlencode \"updates=" + json.dumps(updates) + "\"")
' "$AUDIT_FILE"
      ;;
  esac
  exit 0
fi

# Regular mutation: PUT scalars back.
SCALARS_JSON="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin).get("scalars",{})))')"
if [ "$SCALARS_JSON" = "{}" ]; then
  echo "wf-revert: no scalar fields to restore (captured state had no plain fields). Manual revert required."
  exit 0
fi

echo "wf-revert: replaying scalar fields via PUT:"
echo "  ${SCALARS_JSON}"
echo "wf-revert: targeting /attask/api/v17.0/${OBJCODE}/${OBJ_ID}"
echo

# Use wf-curl.sh so the same scope guards apply on revert.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"${SCRIPT_DIR}/wf-curl.sh" -X PUT "/attask/api/v17.0/${OBJCODE}/${OBJ_ID}" \
  --data-urlencode "updates=${SCALARS_JSON}"
