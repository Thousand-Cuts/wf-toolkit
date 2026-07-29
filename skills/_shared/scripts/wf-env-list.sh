#!/usr/bin/env bash
# wf-env-list.sh — read-only listing of the environment folders
# (~/wf-envs/). Used by /wf-env-list.
# Part of the wf-env-folders convention.
set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"

echo "Workfront environments (~/wf-envs/):"
active=""
if [ -f "${WF_ENVS_HOME}/.active" ]; then active="$(<"${WF_ENVS_HOME}/.active")"; fi
found_env=0
if [ -d "$WF_ENVS_HOME" ]; then
  for d in "$WF_ENVS_HOME"/*/; do
    [ -d "$d" ] || continue
    slug="$(basename "$d")"
    env_file="${d}.env"
    [ -f "$env_file" ] || continue
    label="$({ grep -E '^WF_ENV_LABEL=' "$env_file" || true; } | head -1 | sed -E 's/^WF_ENV_LABEL="?([^"]*)"?$/\1/')"
    host="$({ grep -E '^WF_HOST=' "$env_file" || true; } | head -1 | sed -E 's/^WF_HOST="?([^"]*)"?$/\1/')"
    env_type="$({ grep -E '^WF_ENV_TYPE=' "$env_file" || true; } | head -1 | sed -E 's/^WF_ENV_TYPE="?([^"]*)"?$/\1/')"
    read_only="$({ grep -E '^WF_READ_ONLY=' "$env_file" || true; } | head -1 | sed -E 's/^WF_READ_ONLY="?([^"]*)"?$/\1/')"
    marker=" "
    if [ "$slug" = "$active" ]; then marker="*"; fi
    ro_suffix=""
    if [ -n "$read_only" ]; then ro_suffix=" [RO]"; fi
    printf '  %s %s  —  %s  (%s, %s)%s\n' "$marker" "$slug" "${label:-<no label>}" "$host" "${env_type:-?}" "$ro_suffix"
    found_env=1
  done
fi
if [ "$found_env" = "0" ]; then echo "  (no environments configured — run /wf-env-add <slug>)"; fi
