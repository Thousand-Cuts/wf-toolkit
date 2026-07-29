#!/usr/bin/env bash
# wf-env-setkey.sh — set WF_API_KEY for an environment via hidden terminal input.
# Validates with a one-call handshake against the environment's host unless
# --skip-handshake is passed (tests). Refuses overwrite without --rotate.
# Part of the wf-env-folders convention. See
# skills/_shared/references/env-credentials-and-safety.md
#
# Usage: wf-env-setkey.sh <slug> [--rotate] [--skip-handshake]
set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
die() { echo "wf-env-setkey: $*" >&2; exit 1; }

[ $# -ge 1 ] || die "usage: wf-env-setkey.sh <slug> [--rotate] [--skip-handshake]"
SLUG="$1"; shift

ROTATE=0
SKIP_HANDSHAKE=0
for a in "$@"; do
  case "$a" in
    --rotate) ROTATE=1 ;;
    --skip-handshake) SKIP_HANDSHAKE=1 ;;
    *) die "unknown flag: $a" ;;
  esac
done

ENV_DIR="${WF_ENVS_HOME}/${SLUG}"
ENV_FILE="${ENV_DIR}/.env"
[ -d "$ENV_DIR" ] || die "no environment folder at ${ENV_DIR}. Run /wf-env-add ${SLUG} first."
[ -f "$ENV_FILE" ] || die "no .env at ${ENV_FILE}"

# Refuse if key already set, unless --rotate.
EXISTING_KEY="$(grep -E '^WF_API_KEY=' "$ENV_FILE" | head -1 | sed -E 's/^WF_API_KEY="?([^"]*)"?$/\1/')"
if [ -n "$EXISTING_KEY" ] && [ "$ROTATE" = "0" ]; then
  die "WF_API_KEY already set for ${SLUG}. Pass --rotate to overwrite."
fi

# Read key.
if [ "${WF_ENV_SETKEY_FROM_STDIN:-0}" = "1" ]; then
  read -r KEY
else
  [ -t 0 ] || die "interactive terminal required (or set WF_ENV_SETKEY_FROM_STDIN=1 for scripted use)"
  echo "wf-env-setkey: paste API key for ${SLUG} (input hidden):"
  read -r -s KEY < /dev/tty
  echo
fi
[ -n "$KEY" ] || die "empty key rejected"

# Handshake unless skipped.
if [ "$SKIP_HANDSHAKE" = "0" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  : "${WF_HOST:?WF_HOST missing from .env}"
  echo "wf-env-setkey: validating against https://${WF_HOST} ..."
  RESP="$(curl -sG --compressed "https://${WF_HOST}/attask/api/v17.0/user/search" \
    --data-urlencode "apiKey=${KEY}" \
    --data-urlencode 'fields=customer:name' \
    --data-urlencode '$$LIMIT=1' || true)"
  if [ -z "$RESP" ] || echo "$RESP" | grep -q '"error"'; then
    die "handshake failed against ${WF_HOST}. Response: ${RESP}"
  fi
  CUSTOMER="$(printf '%s' "$RESP" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
data = d.get("data") or []
if not data: sys.exit(0)
cust = (data[0].get("customer") or {}).get("name")
if cust: print(cust)
' || true)"
  echo "wf-env-setkey: handshake OK — customer:name = ${CUSTOMER:-<unknown>}"
fi

# Rewrite .env atomically with the new key, preserving every other line.
TMP="$(mktemp -t wf-env-setkey.XXXXXX)"
chmod 600 "$TMP"
awk -v key="$KEY" '
  BEGIN { written=0 }
  /^WF_API_KEY=/ { print "WF_API_KEY=\"" key "\""; written=1; next }
  { print }
  END { if (!written) print "WF_API_KEY=\"" key "\"" }
' "$ENV_FILE" > "$TMP"
mv "$TMP" "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "wf-env-setkey: wrote key to ${ENV_FILE}"
