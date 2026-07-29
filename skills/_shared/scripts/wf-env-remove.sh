#!/usr/bin/env bash
# wf-env-remove.sh — remove an environment folder. Requires explicit
# confirmation: --yes-i-typed-it <slug-again>. If exports/ is
# non-empty, refuses unless --force-keep-exports is also passed
# (in which case exports are moved to ~/wf-envs/_archived/<slug>-<ts>/).
# Part of the wf-env-folders convention.
#
# Usage: wf-env-remove.sh <slug> --yes-i-typed-it <slug-again> [--force-keep-exports]
set -euo pipefail

WF_ENVS_HOME="${WF_ENVS_HOME:-${HOME}/wf-envs}"
die() { echo "wf-env-remove: $*" >&2; exit 1; }
usage() { echo "wf-env-remove: usage: <slug> --yes-i-typed-it <slug-again> [--force-keep-exports]" >&2; exit 2; }

[ $# -ge 1 ] || usage
SLUG="$1"; shift

CONFIRM=""
FORCE_KEEP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --yes-i-typed-it)
      [ $# -ge 2 ] || usage
      CONFIRM="$2"; shift 2 ;;
    --force-keep-exports) FORCE_KEEP=1; shift ;;
    *) die "unknown flag: $1" ;;
  esac
done

[ -n "$CONFIRM" ] || usage
[ "$CONFIRM" = "$SLUG" ] || die "confirmation slug '${CONFIRM}' does not match '${SLUG}'. Aborting."

ENV_DIR="${WF_ENVS_HOME}/${SLUG}"
[ -d "$ENV_DIR" ] || die "no environment folder at ${ENV_DIR}"

EXPORTS="${ENV_DIR}/exports"
if [ -d "$EXPORTS" ] && [ -n "$(ls -A "$EXPORTS" 2>/dev/null)" ]; then
  if [ "$FORCE_KEEP" = "0" ]; then
    die "exports/ is non-empty for ${SLUG}. Re-run with --force-keep-exports to archive them under ~/wf-envs/_archived/ before removal."
  fi
  TS="$(date -u +%Y%m%dT%H%M%SZ)"
  ARCHIVE_DIR="${WF_ENVS_HOME}/_archived/${SLUG}-${TS}"
  mkdir -p "$ARCHIVE_DIR"
  chmod 700 "${WF_ENVS_HOME}/_archived" "$ARCHIVE_DIR"
  mv "$EXPORTS"/* "$ARCHIVE_DIR"/
  echo "wf-env-remove: exports archived to ${ARCHIVE_DIR}"
fi

# Clear .active if it pointed here.
if [ -f "${WF_ENVS_HOME}/.active" ]; then
  ACTIVE_SLUG="$(<"${WF_ENVS_HOME}/.active")"
  if [ "$ACTIVE_SLUG" = "$SLUG" ]; then
    rm "${WF_ENVS_HOME}/.active"
    echo "wf-env-remove: cleared .active (was '${SLUG}')"
  fi
fi

rm -rf "$ENV_DIR"
echo "wf-env-remove: removed ${ENV_DIR}"
