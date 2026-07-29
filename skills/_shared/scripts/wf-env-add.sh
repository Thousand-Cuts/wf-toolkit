#!/usr/bin/env bash
# wf-env-add.sh — materialise ~/wf-envs/<slug>/{,audit,exports} +
# .env skeleton (no API key). Slash command /wf-env-add wraps this.
# Part of the wf-env-folders convention. See
# skills/_shared/references/env-credentials-and-safety.md
#
# Usage: wf-env-add.sh <slug> <label> <host> <env_type> [scope_portfolio_id] [default_user_email]
set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
die() { echo "wf-env-add: $*" >&2; exit 1; }
validate_slug() {
  local slug="$1"
  [ -n "$slug" ] || die "slug required"
  case "$slug" in
    *[!a-zA-Z0-9_-]*) die "slug must be [a-zA-Z0-9_-] only" ;;
  esac
}

[ $# -ge 4 ] || die "usage: wf-env-add.sh <slug> <label> <host> <env_type> [scope_portfolio_id] [default_user_email] [read_only]"

SLUG="$1"; LABEL="$2"; HOST="$3"; ENV_TYPE="$4"
SCOPE="${5:-}"; EMAIL="${6:-}"; READ_ONLY="${7:-}"

# Normalise read-only to "1" or "".
case "$READ_ONLY" in
  1|true|TRUE|yes|YES) READ_ONLY="1" ;;
  *) READ_ONLY="" ;;
esac

validate_slug "$SLUG"
[ -n "$LABEL" ] || die "label required"
[ -n "$HOST" ] || die "host required"

# Normalise host.
HOST="${HOST#https://}"
HOST="${HOST#http://}"
HOST="${HOST%/}"

case "$ENV_TYPE" in
  preview|sandbox|prod) : ;;
  *) die "env_type must be preview, sandbox, or prod (got '${ENV_TYPE}')" ;;
esac

# NOTE: env_type=prod no longer requires a scope portfolio. The v1 scope guard
# only checked that WF_SCOPE_PORTFOLIO_ID was set — it never verified writes
# stayed inside the portfolio — so it was dropped. Prod writes are gated at
# write time by an explicit per-invocation OK (WF_ENV_WRITE_ACK=1); see
# wf-env-curl.sh. WF_SCOPE_PORTFOLIO_ID is kept as optional reference metadata.

ENV_DIR="${WF_ENVS_HOME}/${SLUG}"
[ -e "$ENV_DIR" ] && die "environment folder already exists at ${ENV_DIR}. Use /wf-env-remove first if you want to recreate."

umask 077
mkdir -p "${WF_ENVS_HOME}"
chmod 700 "${WF_ENVS_HOME}"
mkdir -p "${ENV_DIR}" "${ENV_DIR}/audit" "${ENV_DIR}/exports"
chmod 700 "${ENV_DIR}" "${ENV_DIR}/audit" "${ENV_DIR}/exports"

ENV_FILE="${ENV_DIR}/.env"
{
  printf '# wf-env-folders managed file — DO NOT edit WF_API_KEY by hand.\n'
  printf '# DO NOT open this folder in screenshares — it contains API credentials.\n'
  printf '# Set the key with: bash %s %s\n' "$(cd "$(dirname "$0")" && pwd)/wf-env-setkey.sh" "$SLUG"
  printf '\n'
  printf 'WF_ENV_LABEL="%s"\n' "$LABEL"
  printf 'WF_HOST="%s"\n' "$HOST"
  printf 'WF_ENV_TYPE="%s"\n' "$ENV_TYPE"
  printf 'WF_SCOPE_PORTFOLIO_ID="%s"\n' "$SCOPE"
  printf 'WF_DEFAULT_USER_EMAIL="%s"\n' "$EMAIL"
  printf 'WF_READ_ONLY="%s"\n' "$READ_ONLY"
  printf 'WF_API_KEY=""\n'
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "wf-env-add: created ${ENV_DIR}"
echo "wf-env-add: next step — set the API key:"
echo "  bash $(cd "$(dirname "$0")" && pwd)/wf-env-setkey.sh ${SLUG}"
