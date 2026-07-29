#!/usr/bin/env bash
# wf-creds-check.sh — verify the active credentials and ping the host.
# Exit codes: 0 = OK, 1 = no creds, 2 = creds present but ping failed.

set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
ACTIVE_FILE="${WF_ENVS_HOME}/.active"

if [ ! -f "$ACTIVE_FILE" ]; then
  echo "wf-creds-check: no active environment configured."
  echo "wf-creds-check: run /wf-env-add <slug> (one-time) or /wf-env-use <slug>."
  exit 1
fi

ACTIVE="$(<"$ACTIVE_FILE")"
ENV_FILE="${WF_ENVS_HOME}/${ACTIVE}/.env"
[ -f "$ENV_FILE" ] || { echo "wf-creds-check: active environment '${ACTIVE}' has no .env file" >&2; exit 1; }

PERM="$(stat -f '%Lp' "$ENV_FILE" 2>/dev/null || stat -c '%a' "$ENV_FILE")"
if [ "$PERM" != "600" ]; then
  echo "wf-creds-check: WARNING — ${ENV_FILE} has mode ${PERM}, expected 600. Run: chmod 600 ${ENV_FILE}"
fi

# shellcheck disable=SC1090
source "$ENV_FILE"
: "${WF_HOST:?WF_HOST not set}"
: "${WF_API_KEY:?WF_API_KEY not set}"

LABEL="${WF_ENV_LABEL:-${WF_LABEL:-${ACTIVE}}}"
echo "wf-creds-check: active=${ACTIVE} label=${LABEL} host=${WF_HOST}"

echo "wf-creds-check: pinging ${WF_HOST} ..."
RESP="$(curl -sG --compressed "https://${WF_HOST}/attask/api/v17.0/user/search" \
  --data-urlencode "apiKey=${WF_API_KEY}" \
  --data-urlencode "fields=ID" \
  --data-urlencode '$$LIMIT=1' || true)"

if [ -z "$RESP" ]; then
  echo "wf-creds-check: FAILED — empty response from ${WF_HOST}" >&2
  exit 2
fi
if echo "$RESP" | grep -q '"error"'; then
  echo "wf-creds-check: FAILED — ${RESP}" >&2
  exit 2
fi
if echo "$RESP" | grep -q '"data"'; then
  echo "wf-creds-check: OK"
  exit 0
fi

echo "wf-creds-check: unexpected response: ${RESP}" >&2
exit 2
