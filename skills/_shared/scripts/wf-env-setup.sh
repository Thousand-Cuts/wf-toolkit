#!/usr/bin/env bash
# wf-env-setup.sh — one-command interactive environment onboarding.
#
# Folds the three-step flow (wf-env-add → wf-env-setkey → wf-env-use)
# into a single terminal run: prompts for all metadata, then the API key with
# hidden input, validates the key with one live API call, and activates the
# environment. The key is never passed on a command line and never enters chat.
#
# Run this in your terminal — it needs a tty for the hidden key prompt.
# The underlying primitives (wf-env-add/setkey/use) remain available for
# scripted/automated use and are what the test suite drives.
#
# Usage: wf-env-setup.sh [<slug>]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
die() { echo "wf-env-setup: $*" >&2; exit 1; }

[ -t 0 ] || die "interactive terminal required (this prompts for the API key with hidden input). For scripted use, call wf-env-add.sh + wf-env-setkey.sh + wf-env-use.sh directly."

# prompt <var> <question> [default]
prompt() {
  local __var="$1" __q="$2" __def="${3:-}" __ans
  if [ -n "$__def" ]; then
    read -r -p "${__q} [${__def}]: " __ans < /dev/tty || __ans=""
    [ -n "$__ans" ] || __ans="$__def"
  else
    read -r -p "${__q}: " __ans < /dev/tty || __ans=""
  fi
  printf -v "$__var" '%s' "$__ans"
}

SLUG="${1:-}"
[ -n "$SLUG" ] || prompt SLUG "Environment slug ([a-zA-Z0-9_-], e.g. prod, preview, sandbox)" ""
case "$SLUG" in
  ''|*[!a-zA-Z0-9_-]*) die "slug must be non-empty and [a-zA-Z0-9_-] only" ;;
esac
[ -e "${WF_ENVS_HOME}/${SLUG}" ] && die "environment '${SLUG}' already exists. Use /wf-env-remove first, or wf-env-setkey.sh ${SLUG} --rotate to change just the key."

prompt LABEL   "Human-readable label (e.g. 'Acme — Production')" ""
[ -n "$LABEL" ] || die "label required"
prompt HOST    "Workfront host (no scheme, e.g. acme.my.workfront.com)" ""
[ -n "$HOST" ] || die "host required"
prompt ENV_TYPE "Env type (preview/sandbox/prod)" "preview"
prompt RO_ANS  "Read-only folder? writes always refused (y/N)" "N"
case "$RO_ANS" in y|Y|yes|YES) READ_ONLY="1" ;; *) READ_ONLY="" ;; esac
prompt EMAIL   "Default user email for 'me' references (optional, Enter to skip)" ""
prompt SCOPE   "Reference portfolio ID (optional, NOT enforced, Enter to skip)" ""

echo
echo "wf-env-setup: creating folder for '${SLUG}' ..."
bash "${SCRIPT_DIR}/wf-env-add.sh" "$SLUG" "$LABEL" "$HOST" "$ENV_TYPE" "$SCOPE" "$EMAIL" "$READ_ONLY"

echo
echo "wf-env-setup: now set the API key for '${SLUG}' (input hidden, validated with one live call)."
bash "${SCRIPT_DIR}/wf-env-setkey.sh" "$SLUG"

echo
bash "${SCRIPT_DIR}/wf-env-use.sh" "$SLUG"

echo
echo "wf-env-setup: done — '${SLUG}' is configured and active. GETs work now."
if [ "$ENV_TYPE" = "prod" ] && [ -z "$READ_ONLY" ]; then
  echo "wf-env-setup: NOTE — this is a PROD environment. Writes require an explicit typed OK per session (the skill prepends WF_ENV_WRITE_ACK=1 after you confirm)."
fi
