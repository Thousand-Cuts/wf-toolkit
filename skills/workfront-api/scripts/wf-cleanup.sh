#!/usr/bin/env bash
# wf-cleanup.sh — find and delete leftover verification test objects.
#
# Searches for objects whose name starts with the verification prefix
# (default '[wf-api-verify]') across every configured objCode, instance-wide.
# The prefix is the sole selector — there is no portfolio scoping.
#
# Usage:
#   wf-cleanup.sh             # list mode: show what would be deleted
#   wf-cleanup.sh --delete    # actually hard-delete (force=true), with confirmation

set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
ACTIVE_FILE="${WF_ENVS_HOME}/.active"
PREFIX="${WF_VERIFY_PREFIX:-[wf-api-verify]}"
# Per-objCode prefix overrides — some objCodes (notably PARAM) reject `[` in
# name/label, so they need a no-brackets variant. Default surfaces both
# Categories (with brackets) and Parameters (without).
PARAM_PREFIX="${WF_VERIFY_PARAM_PREFIX:-wf_verify_}"
OBJCODES="${WF_VERIFY_OBJCODES:-project,optask,task,team,user,role,group,category,parameter}"
# Comma-separated exact-name matches that wf-cleanup will NEVER delete, even
# if they match the prefix. The bootstrap scratch project lives here so it
# survives sweeps. Override per-environment by setting WF_VERIFY_KEEP_NAMES in
# the active env file.
KEEP_NAMES_DEFAULT="[wf-api-verify] scratch project"
ACTION="list"

case "${1:-}" in
  --delete|-d) ACTION="delete" ;;
  --help|-h|"") : ;;
  *) echo "wf-cleanup: unknown arg '${1}'. Use --delete or no args." >&2; exit 2 ;;
esac

die() { echo "wf-cleanup: $*" >&2; exit 1; }

[ -f "$ACTIVE_FILE" ] || die "no active environment. Run /wf-env-use <slug> first."
ACTIVE="$(<"$ACTIVE_FILE")"
ENV_FILE="${WF_ENVS_HOME}/${ACTIVE}/.env"
[ -f "$ENV_FILE" ] || die "active environment '${ACTIVE}' has no .env file"

# shellcheck disable=SC1090
source "$ENV_FILE"
: "${WF_HOST:?WF_HOST not set}"
: "${WF_API_KEY:?WF_API_KEY not set}"
LABEL="${WF_ENV_LABEL:-${WF_LABEL:-${ACTIVE}}}"
KEEP_NAMES="${WF_VERIFY_KEEP_NAMES:-${KEEP_NAMES_DEFAULT}}"

echo "wf-cleanup: active=${ACTIVE} label='${LABEL}' host=${WF_HOST}"
echo "wf-cleanup: prefix='${PREFIX}' (parameter prefix: '${PARAM_PREFIX}') objcodes='${OBJCODES}' action=${ACTION}"
echo "wf-cleanup: keep-names (never delete): ${KEEP_NAMES}"
echo

# Per-objCode prefix resolver — Parameter uses the no-brackets variant.
prefix_for_objcode() {
  local objcode="$1"
  if [ "$objcode" = "parameter" ]; then
    echo "$PARAM_PREFIX"
  else
    echo "$PREFIX"
  fi
}

# Search helper: GET /attask/api/v17.0/<objcode>/search with name_Mod=cicontains.
# Workfront does not support startswith natively, so we use cicontains and then
# filter the response to only keep names that actually start with the prefix.
search_by_prefix() {
  local objcode="$1"
  local extra_filters="${2:-}"
  local prefix
  prefix="$(prefix_for_objcode "$objcode")"
  curl -sG --compressed "https://${WF_HOST}/attask/api/v17.0/${objcode}/search" \
    --data-urlencode "apiKey=${WF_API_KEY}" \
    --data-urlencode "name=${prefix}" \
    --data-urlencode "name_Mod=cicontains" \
    --data-urlencode "fields=ID,name" \
    --data-urlencode '$$LIMIT=200' \
    ${extra_filters:+--data-urlencode "$extra_filters"}
}

# Parse: emit one "objcode<TAB>id<TAB>name" line per match whose name actually
# starts with the prefix AND is not in the keep-names list.
extract_prefix_matches() {
  local objcode="$1"
  local json="$2"
  local prefix
  prefix="$(prefix_for_objcode "$objcode")"
  printf '%s' "$json" | python3 -c '
import json, sys
objcode = sys.argv[1]
prefix = sys.argv[2]
keep_names = set(n.strip() for n in (sys.argv[3] or "").split(",") if n.strip())
data = json.load(sys.stdin)
for row in data.get("data", []) or []:
    name = row.get("name", "") or ""
    if name.startswith(prefix) and name not in keep_names:
        row_id = row.get("ID", "")
        print(f"{objcode}\t{row_id}\t{name}")
' "$objcode" "$prefix" "$KEEP_NAMES"
}

TARGETS_FILE="$(mktemp -t wf-cleanup-targets.XXXXXX)"
trap 'rm -f "$TARGETS_FILE"' EXIT

# Sweep every configured objCode by prefix, instance-wide.
IFS=',' read -ra REQUESTED <<< "$OBJCODES"
for OBJ in "${REQUESTED[@]}"; do
  OBJ="$(echo "$OBJ" | tr -d ' ')"
  [ -n "$OBJ" ] || continue
  RESP="$(search_by_prefix "$OBJ")"
  extract_prefix_matches "$OBJ" "$RESP" >> "$TARGETS_FILE" || true
done

if [ ! -s "$TARGETS_FILE" ]; then
  echo "wf-cleanup: nothing matching '${PREFIX}' found. Done."
  exit 0
fi

echo "wf-cleanup: matches:"
while IFS=$'\t' read -r OBJ ID NAME; do
  printf '  [%s] %s — %s\n' "$OBJ" "$ID" "$NAME"
done < "$TARGETS_FILE"
echo

if [ "$ACTION" = "list" ]; then
  echo "wf-cleanup: list mode. Re-run with --delete to hard-delete these."
  exit 0
fi

if [ ! -t 0 ]; then
  die "delete mode requires an interactive TTY."
fi

echo "wf-cleanup: about to hard-delete the above objects (force=true)."
echo -n "Type 'delete' to confirm: "
read -r REPLY < /dev/tty
[ "$REPLY" = "delete" ] || die "confirmation declined. Aborting."

while IFS=$'\t' read -r OBJ ID NAME; do
  RESP="$(curl -s --compressed -X DELETE \
    "https://${WF_HOST}/attask/api/v17.0/${OBJ}/${ID}?apiKey=${WF_API_KEY}&force=true" || true)"
  if echo "$RESP" | grep -q '"success":true'; then
    echo "  deleted: [${OBJ}] ${ID} — ${NAME}"
  else
    echo "  FAILED: [${OBJ}] ${ID} — ${NAME} — ${RESP}" >&2
  fi
done < "$TARGETS_FILE"
