#!/usr/bin/env bash
# wf-env-curl.sh — read-mostly Workfront curl wrapper that resolves
# credentials from ${WF_ENVS_HOME}/.active.
#
# Write-side guards (v2):
#   1. Read-only folder (WF_READ_ONLY=1) — every write refused.
#   2. Prod / non-disposable env — writes require an explicit per-invocation OK
#      via WF_ENV_WRITE_ACK=1. The admin's typed confirmation in chat is
#      the gate. Preview/sandbox/dev/test-drive are disposable and write freely.
#      There is NO portfolio scoping — the v1 "scope portfolio" guard only
#      checked that an env var was set (it never verified the write target was in
#      the portfolio), so it was removed in favor of the explicit-OK model.
#
# Credential handling: the API key is read from the active .env (never from
# argv of THIS script, and never from chat). Note it is placed in the request
# URL's query string, which Workfront's API-key auth requires for POST/PUT/
# DELETE — so it IS visible in `ps` output for the lifetime of the curl child
# process, and would appear in a transcript if curl -v/--verbose were ever
# added. Do not add -v to invocations.
# Part of the wf-env-folders convention.
#
# Usage: wf-env-curl.sh <path> [curl args...]
set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
die() { echo "wf-env-curl: $*" >&2; exit 1; }
refuse() { echo "wf-env-curl: REFUSED — $*" >&2; exit 3; }

if [ ! -f "${WF_ENVS_HOME}/.active" ]; then
  die "no active environment. Run /wf-env-use <slug> first."
fi
ACTIVE="$(<"${WF_ENVS_HOME}/.active")"
ENV_DIR="${WF_ENVS_HOME}/${ACTIVE}"
ENV_FILE="${ENV_DIR}/.env"
if [ ! -f "$ENV_FILE" ]; then
  die "active environment '${ACTIVE}' has no .env at ${ENV_FILE}"
fi

PERM="$(stat -f '%Lp' "$ENV_FILE" 2>/dev/null || stat -c '%a' "$ENV_FILE")"
if [ "$PERM" != "600" ]; then
  die "permissions on ${ENV_FILE} are ${PERM}, expected 600. Run: chmod 600 ${ENV_FILE}"
fi

# shellcheck disable=SC1090
source "$ENV_FILE"
: "${WF_HOST:?WF_HOST not set in ${ENV_FILE}}"
: "${WF_API_KEY:?WF_API_KEY not set in ${ENV_FILE} — run wf-env-setkey.sh ${ACTIVE}}"
if [ -z "$WF_API_KEY" ]; then
  die "WF_API_KEY is empty — run wf-env-setkey.sh ${ACTIVE}"
fi

if [ $# -lt 1 ]; then
  die "usage: wf-env-curl.sh <path> [curl args...]"
fi

# Detect the HTTP method. Recognizes every form curl accepts:
#   -X POST / --request POST      (value in next arg)
#   -XPOST                        (attached short form)
#   --request=POST                (equals form)
# When no method is given explicitly, curl implies POST if a *raw body* data
# flag is present. We mirror that — BUT deliberately exclude --data-urlencode,
# because this wrapper's read idiom is `GET + --data-urlencode` (we auto-add -G
# below to push those fields into the query string). Treating --data-urlencode
# as a write would misclassify every GET-with-fields read as a blocked write.
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

# Find the API path arg (the one starting with /attask/).
PATH_ARG=""
for a in "$@"; do
  case "$a" in
    /attask/*)
      PATH_ARG="$a"
      break
      ;;
  esac
done
if [ -z "$PATH_ARG" ]; then
  die "no API path found (expected an arg starting with /attask/api/...)"
fi
PATH_NO_QS="${PATH_ARG%%\?*}"

# Is this a write? POST /search is read; everything else that isn't GET/HEAD is write.
IS_WRITE=0
case "$METHOD" in
  GET|HEAD)
    IS_WRITE=0
    ;;
  POST)
    case "$PATH_NO_QS" in
      *"/search")
        IS_WRITE=0
        ;;
      *)
        IS_WRITE=1
        ;;
    esac
    ;;
  *)
    IS_WRITE=1
    ;;
esac

# Write guards.
if [ "$IS_WRITE" = "1" ]; then
  # 1. Read-only environment folder: refuse every write, regardless of host or env.
  if [ -n "${WF_READ_ONLY:-}" ]; then
    refuse "environment folder '${ACTIVE}' is read-only (WF_READ_ONLY=1 in ${ENV_FILE}). Refusing ${METHOD} ${PATH_NO_QS}."
  fi

  # 2. Explicit-OK gate for non-disposable environments.
  #    preview/sandbox/dev/test-drive are disposable → write freely.
  #    prod (or an unrecognized host with no WF_ENV_TYPE) → require an explicit
  #    per-invocation OK. WF_ENV_WRITE_ACK=1 is set by the skill ONLY after
  #    the admin has typed a confirmation in chat, or by an admin
  #    running the command directly who has read the warning.
  SAFE_ENV=0
  case "${WF_ENV_TYPE:-}" in
    preview|sandbox|dev|test-drive|testdrive)
      SAFE_ENV=1
      ;;
    prod)
      SAFE_ENV=0
      ;;
    *)
      # WF_ENV_TYPE not set — fall back to a hostname heuristic.
      case "$WF_HOST" in
        *preview*|*sandbox*|*test-drive*|*testdrive*|*dev*) SAFE_ENV=1 ;;
        *) SAFE_ENV=0 ;;
      esac
      ;;
  esac
  if [ "$SAFE_ENV" = "0" ] && [ -z "${WF_ENV_WRITE_ACK:-}" ]; then
    refuse "${METHOD} ${PATH_NO_QS} writes to PROD environment '${WF_HOST}' (env='${WF_ENV_TYPE:-unknown}') and requires explicit confirmation. Surface the target host + label ('${WF_ENV_LABEL:-$ACTIVE}') to the user, get a typed 'yes', then re-invoke with WF_ENV_WRITE_ACK=1 prepended."
  fi
fi

# Build URL with apiKey in query string.
case "$PATH_ARG" in
  *"?"*)
    URL="https://${WF_HOST}${PATH_ARG}&apiKey=${WF_API_KEY}"
    ;;
  *)
    URL="https://${WF_HOST}${PATH_ARG}?apiKey=${WF_API_KEY}"
    ;;
esac

# Rebuild args list, replacing the PATH_ARG with the full URL.
ARGS=()
for a in "$@"; do
  if [ "$a" = "$PATH_ARG" ]; then
    ARGS+=("$URL")
  else
    ARGS+=("$a")
  fi
done

# Base curl flags: silent + compressed. Add -G for GET so --data-urlencode
# goes into the query string rather than the request body.
CURL_FLAGS=("-s" "--compressed")
if [ "$METHOD" = "GET" ]; then
  CURL_FLAGS+=("-G")
fi

exec curl "${CURL_FLAGS[@]}" "${ARGS[@]}"
