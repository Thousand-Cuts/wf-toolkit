#!/usr/bin/env bash
# wf-curl.sh — verified Workfront curl wrapper for the workfront-api skill.
#
# Reads the active environment credential from ~/wf-envs/<slug>/.env (managed by
# /wf-env-add and /wf-env-use), builds the URL, and places apiKey in the
# query string (required for POST/PUT/DELETE per
# knowledge/api/02-authentication.md).
#
# Safety guards enforced at the wrapper level:
#   1. Explicit-OK gate for non-disposable environments: preview/sandbox/dev/
#      test-drive write freely; a prod environment (or an unrecognized host with
#      no WF_ENV_TYPE) requires an explicit per-invocation WF_VERIFY_WRITE_ACK=1,
#      set only after a typed confirmation. There is NO portfolio scoping — the
#      old WF_SCOPE_PORTFOLIO_ID guard was replaced by this explicit-OK model
#      (mirrors wf-env-curl.sh).
#   2. Prefix on creates: any create (POST /<objcode> with no ID in the path)
#      must include name=[wf-api-verify] ... in the body. Wrapper refuses
#      otherwise. Every created object is unambiguously a throwaway.
#   3. Audit log on mutations: any PUT/DELETE or POST /<id>/<action> first
#      does a preflight GET and writes the captured state to
#      ~/wf-envs/<slug>/audit/<UTC>-<method>-<objcode>-<id>.json
#      The audit file is the evidence + revert record.
#
# Credential note: the API key is read from the .env (never from this script's
# argv, never from chat) but is placed in the request URL's query string, as
# Workfront's API-key auth requires for POST/PUT/DELETE. It is therefore visible
# in `ps` for the curl child's lifetime, and would leak into a transcript if
# curl -v were ever added. Do not add -v.
#
# Usage:
#   wf-curl <path> [curl args...]

set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
ACTIVE_FILE="${WF_ENVS_HOME}/.active"
VERIFY_PREFIX="${WF_VERIFY_PREFIX:-[wf-api-verify]}"
# Per-objCode prefix overrides. Some objCodes (notably PARAM) reject `[` in
# name/label and require a no-brackets variant. Phase A finding 2026-05-18.
PARAM_VERIFY_PREFIX="${WF_VERIFY_PARAM_PREFIX:-wf_verify_}"

die() { echo "wf-curl: $*" >&2; exit 1; }

[ -f "$ACTIVE_FILE" ] || die "no active environment. Run /wf-env-add <slug> (one-time) or /wf-env-use <slug>."

ACTIVE="$(<"$ACTIVE_FILE")"
ENV_FILE="${WF_ENVS_HOME}/${ACTIVE}/.env"
[ -f "$ENV_FILE" ] || die "active environment '${ACTIVE}' has no .env file at ${ENV_FILE}"

PERM="$(stat -f '%Lp' "$ENV_FILE" 2>/dev/null || stat -c '%a' "$ENV_FILE")"
[ "$PERM" = "600" ] || die "permissions on ${ENV_FILE} are ${PERM}, expected 600. Run: chmod 600 ${ENV_FILE}"

# shellcheck disable=SC1090
source "$ENV_FILE"
: "${WF_HOST:?WF_HOST not set in ${ENV_FILE}}"
: "${WF_API_KEY:?WF_API_KEY not set in ${ENV_FILE}}"
LABEL="${WF_ENV_LABEL:-${WF_LABEL:-${ACTIVE}}}"
ENV_TYPE="${WF_ENV_TYPE:-}"

AUDIT_DIR="${WF_ENVS_HOME}/${ACTIVE}/audit"

if [ $# -lt 1 ]; then
  cat >&2 <<EOF
Usage: wf-curl <path> [curl args...]

Active:    ${LABEL}
Host:      ${WF_HOST}
Env type:  ${ENV_TYPE:-<unspecified>}
Audit dir: ${AUDIT_DIR}/

Guards on writes:
  - Prod/non-disposable env requires WF_VERIFY_WRITE_ACK=1 (set after a typed OK)
  - Creates must use name='${VERIFY_PREFIX} ...' (or '${PARAM_VERIFY_PREFIX}...' for /parameter, which rejects '[')
  - Mutations are audit-logged to AUDIT_DIR before sending
  - Reverts: use scripts/wf-revert.sh <audit-file>

Examples:
  wf-curl /attask/api/v17.0/team/search --data-urlencode "name=Design" --data-urlencode "name_Mod=eq"
  wf-curl -X POST /attask/api/v17.0/optask --data-urlencode "name=${VERIFY_PREFIX} test issue" --data-urlencode "projectID=..."
  wf-curl -X PUT /attask/api/v17.0/optask/<id>/assignMultiple --data-urlencode 'updates={...}'
EOF
  exit 2
fi

# Detect the HTTP method. Recognizes -X POST / --request POST (value in next
# arg), -XPOST (attached), and --request=POST (equals). When no method is given,
# curl implies POST if a raw-body data flag is present — mirror that, but
# deliberately exclude --data-urlencode, which is this wrapper's GET read idiom
# (-G is added for GET below so those fields become query params). Without this,
# a write passed as -XPOST/--request=POST or a bare -d slips through as a GET,
# bypassing every write guard below.
METHOD=""
NEXT_IS_METHOD=0
HAS_RAW_DATA=0
for a in "$@"; do
  if [ "$NEXT_IS_METHOD" = "1" ]; then METHOD="$a"; NEXT_IS_METHOD=0; continue; fi
  case "$a" in
    -X|--request)  NEXT_IS_METHOD=1 ;;
    --request=*)   METHOD="${a#--request=}" ;;
    -X*)           METHOD="${a#-X}" ;;
    -d|--data|--data-raw|--data-binary|--data-ascii|-F|--form) HAS_RAW_DATA=1 ;;
    --data=*|--data-raw=*|--data-binary=*|--data-ascii=*|--form=*) HAS_RAW_DATA=1 ;;
  esac
done
if [ -z "$METHOD" ]; then
  if [ "$HAS_RAW_DATA" = "1" ]; then METHOD="POST"; else METHOD="GET"; fi
fi
METHOD="$(printf '%s' "$METHOD" | tr '[:lower:]' '[:upper:]')"

# Find the API path arg.
PATH_ARG=""
for a in "$@"; do
  case "$a" in /attask/*) PATH_ARG="$a"; break ;; esac
done
[ -n "$PATH_ARG" ] || die "no API path found (expected an arg starting with /attask/api/...)"

PATH_NO_QS="${PATH_ARG%%\?*}"

# POST against /search is a read (large-filter workaround).
IS_WRITE=0
case "$METHOD" in
  GET|HEAD) IS_WRITE=0 ;;
  POST)
    case "$PATH_NO_QS" in *"/search") IS_WRITE=0 ;; *) IS_WRITE=1 ;; esac
    ;;
  *) IS_WRITE=1 ;;
esac

# Parse <objcode> and <id> from the path.
parse_path_components() {
  local path="$1"
  local tail="${path#/attask/api/}"
  tail="${tail#*/}"   # drop version segment
  local objcode="${tail%%/*}"
  local rest="${tail#"$objcode"}"
  rest="${rest#/}"
  local id="${rest%%/*}"
  PATH_OBJCODE="$objcode"
  PATH_ID="$id"
  PATH_ACTION="${rest#"$id"}"
  PATH_ACTION="${PATH_ACTION#/}"
}

parse_path_components "$PATH_NO_QS"

# Helper: raw GET that doesn't go through wf-curl (used for preflight/audit).
preflight_get() {
  local path="$1"
  curl -sG --compressed "https://${WF_HOST}${path}" \
    --data-urlencode "apiKey=${WF_API_KEY}" "${@:2}"
}

# Extract a form-body field value from the arg list. Looks for
# --data-urlencode "<field>=<value>" (and -d / --data variants) and prints
# <value>. Also extracts from updates={"<field>":"..."} JSON if present.
get_body_field() {
  local field="$1"; shift
  local prev=""
  for a in "$@"; do
    if [ "$prev" = "--data-urlencode" ] || [ "$prev" = "-d" ] || [ "$prev" = "--data" ]; then
      case "$a" in
        "${field}="*) echo "${a#${field}=}"; return 0 ;;
        "updates="*)
          # JSON inside updates= — best-effort parse.
          local json="${a#updates=}"
          local val
          val="$(printf '%s' "$json" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
v = d.get(sys.argv[1])
if v is not None:
    print(v)
" "$field" 2>/dev/null || true)"
          if [ -n "$val" ]; then echo "$val"; return 0; fi
          ;;
      esac
    fi
    prev="$a"
  done
  return 1
}

# Pick a fields= value for audit capture, based on objcode and action.
audit_fields_for() {
  local objcode="$1" action="$2"
  case "$action" in
    assignMultiple)
      echo "ID,name,assignedToID,teamID,roleID,assignments:ID,assignments:assignedToID,assignments:teamID,assignments:roleID,assignments:assignmentPercent"
      return
      ;;
  esac
  case "$objcode" in
    project|proj)
      # Projects have no `assignments` collection (v17/v18 reject the field), which
      # aborted the audit preflight on every project mutation. Removed 2026-06-24.
      echo "ID,name,status,plannedStartDate,plannedCompletionDate,ownerID,sponsorID,description,portfolioID,programID,condition,priority" ;;
    task)
      echo "ID,name,status,plannedStartDate,plannedCompletionDate,duration,assignedToID,projectID,parentID,description,priority,percentComplete,assignments:ID,assignments:assignedToID,assignments:teamID,assignments:roleID" ;;
    optask|issue)
      echo "ID,name,status,plannedStartDate,plannedCompletionDate,assignedToID,projectID,description,priority,severity,isHelpDesk,ownerID,assignments:ID,assignments:assignedToID,assignments:teamID,assignments:roleID" ;;
    user)
      echo "ID,name,firstName,lastName,emailAddr,username,isActive,accessLevelID,homeGroupID,timezone,locale" ;;
    team)
      echo "ID,name,description,isPublic" ;;
    role)
      echo "ID,name,description,layoutTemplateID" ;;
    group)
      echo "ID,name,description,parentID" ;;
    *)
      echo "ID,name" ;;
  esac
}

# ----- write-only guards -----
if [ "$IS_WRITE" = "1" ]; then

  # Identify create vs mutation.
  IS_CREATE=0
  if [ "$METHOD" = "POST" ] && [ -z "$PATH_ID" ]; then
    IS_CREATE=1
  fi

  # 0. Read-only environment folder — every write refused (mirrors wf-env-curl.sh).
  if [ -n "${WF_READ_ONLY:-}" ]; then
    echo "wf-curl: REFUSED — environment '${LABEL}' is marked read-only (WF_READ_ONLY set in ${ENV_FILE})." >&2
    exit 3
  fi

  # 1. Explicit-OK gate for non-disposable environments.
  #    preview/sandbox/dev/test-drive are disposable → write freely.
  #    prod (or an unrecognized host with no WF_ENV_TYPE) → require an explicit
  #    per-invocation OK. WF_VERIFY_WRITE_ACK=1 is set by the skill ONLY after
  #    the user has typed a confirmation, or by an admin running the
  #    command directly who has read the warning.
  SAFE_ENV=0
  case "$ENV_TYPE" in
    preview|sandbox|dev|test-drive|testdrive) SAFE_ENV=1 ;;
    prod) SAFE_ENV=0 ;;
    *)
      # WF_ENV_TYPE not set — fall back to a hostname heuristic.
      case "$WF_HOST" in
        *preview*|*sandbox*|*test-drive*|*testdrive*|*dev*) SAFE_ENV=1 ;;
        *) SAFE_ENV=0 ;;
      esac
      ;;
  esac
  if [ "$SAFE_ENV" = "0" ] && [ -z "${WF_VERIFY_WRITE_ACK:-}" ]; then
    echo "wf-curl: REFUSED — ${METHOD} ${PATH_NO_QS} writes to non-disposable environment '${WF_HOST}' (env='${ENV_TYPE:-unknown}', label='${LABEL}') and requires explicit confirmation." >&2
    echo "wf-curl: Surface the target host + label to the user, get a typed 'yes', then re-invoke with WF_VERIFY_WRITE_ACK=1 prepended." >&2
    exit 3
  fi

  # Non-portfolio (org-level) objects have a wider blast radius — flag them.
  case "$PATH_OBJCODE" in
    project|proj|task|optask|issue|portfolio|program) : ;;
    *)
      echo "wf-curl: NOTE — ${METHOD} on org-level object /${PATH_OBJCODE} affects ALL users in the instance." >&2
      ;;
  esac

  # 2. Prefix enforcement on creates.
  # Per-objCode prefix: PARAM rejects `[` so use the no-brackets variant.
  if [ "$IS_CREATE" = "1" ]; then
    case "$PATH_OBJCODE" in
      parameter|param) ACTIVE_PREFIX="$PARAM_VERIFY_PREFIX" ;;
      *)               ACTIVE_PREFIX="$VERIFY_PREFIX" ;;
    esac
    BODY_NAME="$(get_body_field "name" "$@" || true)"
    if [ -z "$BODY_NAME" ]; then
      die "create POST /${PATH_OBJCODE} requires name= in body, prefixed with '${ACTIVE_PREFIX}'"
    fi
    case "$BODY_NAME" in
      "${ACTIVE_PREFIX}"*) : ;;
      *) die "create POST /${PATH_OBJCODE}: name '${BODY_NAME}' must start with '${ACTIVE_PREFIX}'. All created objects must be clearly labeled throwaways. (Parameter uses '${PARAM_VERIFY_PREFIX}' since Workfront rejects '[' in Parameter.name)" ;;
    esac
  fi

  # 3. Audit log on mutations.
  if [ "$IS_CREATE" = "0" ]; then
    mkdir -p "$AUDIT_DIR"
    chmod 700 "$AUDIT_DIR" 2>/dev/null || true
    TS="$(date -u +%Y%m%dT%H%M%SZ)"
    AUDIT_FILE="${AUDIT_DIR}/${TS}-${METHOD}-${PATH_OBJCODE}-${PATH_ID}.json"
    AUDIT_FIELDS="$(audit_fields_for "$PATH_OBJCODE" "$PATH_ACTION")"
    AUDIT_RESP="$(preflight_get "/attask/api/v17.0/${PATH_OBJCODE}/${PATH_ID}" --data-urlencode "fields=${AUDIT_FIELDS}" || true)"
    if [ -z "$AUDIT_RESP" ] || echo "$AUDIT_RESP" | grep -q '"error"'; then
      die "audit preflight GET failed for /${PATH_OBJCODE}/${PATH_ID}. Aborting write to preserve safety. Response: ${AUDIT_RESP}"
    fi
    # Wrap with metadata so wf-revert.sh has everything it needs.
    {
      printf '{\n'
      printf '  "captured_at": "%s",\n' "$TS"
      printf '  "active_env": "%s",\n' "$ACTIVE"
      printf '  "host": "%s",\n' "$WF_HOST"
      printf '  "method": "%s",\n' "$METHOD"
      printf '  "path": "%s",\n' "$PATH_NO_QS"
      printf '  "objcode": "%s",\n' "$PATH_OBJCODE"
      printf '  "object_id": "%s",\n' "$PATH_ID"
      printf '  "action": "%s",\n' "$PATH_ACTION"
      printf '  "before": '
      printf '%s' "$AUDIT_RESP"
      printf '\n}\n'
    } > "$AUDIT_FILE"
    chmod 600 "$AUDIT_FILE"
    echo "wf-curl: audit captured -> ${AUDIT_FILE}" >&2
  fi
fi

# Build final URL with apiKey in the query string.
case "$PATH_ARG" in
  *"?"*) URL="https://${WF_HOST}${PATH_ARG}&apiKey=${WF_API_KEY}" ;;
  *)     URL="https://${WF_HOST}${PATH_ARG}?apiKey=${WF_API_KEY}" ;;
esac

ARGS=()
for a in "$@"; do
  if [ "$a" = "$PATH_ARG" ]; then ARGS+=("$URL"); else ARGS+=("$a"); fi
done

CURL_FLAGS=("-s" "--compressed")
[ "$METHOD" = "GET" ] && CURL_FLAGS+=("-G")

exec curl "${CURL_FLAGS[@]}" "${ARGS[@]}"
