#!/usr/bin/env bash
# wf-env-resolve.sh — pre-flight credential resolver.
#   No flag         → prints active environment slug, or exits 2 if none.
#   --source        → for clone/promotion flows: defaults to the active
#                     environment slug. Interactive: lists other configured
#                     environments and asks which to use.
#                     WF_ENV_RESOLVE_NONINTERACTIVE=1 skips the prompt and
#                     just uses the default.
#   --dest          → like no-flag but always echoes a confirmation line so
#                     the user can see they're about to write to X.
# Part of the wf-env-folders convention.
set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
die() { echo "wf-env-resolve: $*" >&2; exit 1; }

MODE="active"
case "${1:-}" in
  "")        MODE="active" ;;
  --source)  MODE="source" ;;
  --dest)    MODE="dest" ;;
  *) die "unknown flag: $1 (expected --source or --dest)" ;;
esac

get_active_env() {
  if [ ! -f "${WF_ENVS_HOME}/.active" ]; then
    return 1
  fi
  cat "${WF_ENVS_HOME}/.active"
}

case "$MODE" in
  active)
    if ACTIVE="$(get_active_env)"; then
      printf '%s\n' "$ACTIVE"
      exit 0
    fi
    echo "wf-env-resolve: no active environment. Run /wf-env-use <slug> first." >&2
    exit 2
    ;;

  dest)
    if ACTIVE="$(get_active_env)"; then
      ENV_FILE="${WF_ENVS_HOME}/${ACTIVE}/.env"
      label="$({ grep -E '^WF_ENV_LABEL=' "$ENV_FILE" || true; } | head -1 | sed -E 's/^WF_ENV_LABEL="?([^"]*)"?$/\1/')"
      host="$({ grep -E '^WF_HOST=' "$ENV_FILE" || true; } | head -1 | sed -E 's/^WF_HOST="?([^"]*)"?$/\1/')"
      echo "wf-env-resolve: destination = '${ACTIVE}' — ${label:-<no label>} (${host})" >&2
      printf '%s\n' "$ACTIVE"
      exit 0
    fi
    echo "wf-env-resolve: no active environment. Run /wf-env-use <slug> first." >&2
    exit 2
    ;;

  source)
    DEFAULT=""
    DEFAULT_STORE="env"
    if ACTIVE="$(get_active_env)"; then
      DEFAULT="$ACTIVE"
    else
      die "no active environment. Run /wf-env-use <slug> first."
    fi

    # Non-interactive shortcut for tests.
    if [ "${WF_ENV_RESOLVE_NONINTERACTIVE:-0}" = "1" ]; then
      printf '%s:%s\n' "$DEFAULT_STORE" "$DEFAULT"
      exit 0
    fi

    # Interactive: print the default + any other environment slugs, ask.
    echo "wf-env-resolve: default source = ${DEFAULT_STORE}:${DEFAULT}" >&2
    OTHER=()
    if [ -d "$WF_ENVS_HOME" ]; then
      for d in "$WF_ENVS_HOME"/*/; do
        if [ ! -d "$d" ]; then
          continue
        fi
        slug="$(basename "$d")"
        if [ "$slug" = "$DEFAULT" ]; then
          continue
        fi
        OTHER+=("$slug")
      done
    fi
    if [ "${#OTHER[@]}" -gt 0 ]; then
      echo "wf-env-resolve: other configured environments you could use as source:" >&2
      for s in "${OTHER[@]}"; do
        echo "    env:${s}" >&2
      done
      echo "wf-env-resolve: press Enter to use default '${DEFAULT_STORE}:${DEFAULT}', or type 'env:<slug>' to override:" >&2
      read -r CHOICE < /dev/tty || CHOICE=""
      if [ -n "$CHOICE" ]; then
        printf '%s\n' "$CHOICE"
        exit 0
      fi
    fi
    printf '%s:%s\n' "$DEFAULT_STORE" "$DEFAULT"
    ;;
esac
