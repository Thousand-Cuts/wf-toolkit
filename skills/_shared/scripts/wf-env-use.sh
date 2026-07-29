#!/usr/bin/env bash
# wf-env-use.sh — set ~/wf-envs/.active to an environment slug.
# With no arg: lists configured environments and exits 2 if none, 0 otherwise.
# Part of the wf-env-folders convention.
#
# Usage: wf-env-use.sh [<slug>]
set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
die() { echo "wf-env-use: $*" >&2; exit 1; }

list_envs() {
  local found=0
  if [ -d "$WF_ENVS_HOME" ]; then
    for d in "$WF_ENVS_HOME"/*/; do
      [ -d "$d" ] || continue
      local slug env_file label host env_type
      slug="$(basename "$d")"
      env_file="${d}.env"
      [ -f "$env_file" ] || continue
      label="$({ grep -E '^WF_ENV_LABEL=' "$env_file" || true; } | head -1 | sed -E 's/^WF_ENV_LABEL="?([^"]*)"?$/\1/')"
      host="$({ grep -E '^WF_HOST=' "$env_file" || true; } | head -1 | sed -E 's/^WF_HOST="?([^"]*)"?$/\1/')"
      env_type="$({ grep -E '^WF_ENV_TYPE=' "$env_file" || true; } | head -1 | sed -E 's/^WF_ENV_TYPE="?([^"]*)"?$/\1/')"
      echo "  ${slug}  —  ${label:-<no label>}  (${host}, ${env_type:-?})" >&2
      found=1
    done
  fi
  return $found  # 1 = at least one environment found, 0 = none
}

if [ $# -eq 0 ]; then
  echo "Configured environments:" >&2
  # list_envs returns 1 (truthy) when found, 0 when none — inverted from shell convention.
  # Shell 'if' is true on 0, false on non-zero; so: return 0 → if-branch (no environments); return 1 → else-branch (found).
  if list_envs; then
    echo "  (no environments configured — run /wf-env-add <slug>)" >&2
    exit 2
  fi
  exit 0
fi

SLUG="$1"
case "$SLUG" in
  *[!a-zA-Z0-9_-]*) die "slug must be [a-zA-Z0-9_-] only" ;;
esac

ENV_DIR="${WF_ENVS_HOME}/${SLUG}"
[ -d "$ENV_DIR" ] || die "no environment folder at ${ENV_DIR}. Run /wf-env-add ${SLUG} first."

mkdir -p "$WF_ENVS_HOME"
chmod 700 "$WF_ENVS_HOME"
printf '%s' "$SLUG" > "${WF_ENVS_HOME}/.active"
chmod 600 "${WF_ENVS_HOME}/.active"

label="$({ grep -E '^WF_ENV_LABEL=' "${ENV_DIR}/.env" || true; } | head -1 | sed -E 's/^WF_ENV_LABEL="?([^"]*)"?$/\1/')"
host="$({ grep -E '^WF_HOST=' "${ENV_DIR}/.env" || true; } | head -1 | sed -E 's/^WF_HOST="?([^"]*)"?$/\1/')"
echo "wf-env-use: active environment is now '${SLUG}' — ${label:-<no label>} (${host})"
