#!/usr/bin/env bash
# wf-use.sh — compatibility shim for the shared environment store's activation
# script. Sets ~/wf-envs/.active; run with no args to list configured
# environments.
#
# Usage: wf-use.sh [<env-slug>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "${SCRIPT_DIR}/../../_shared/scripts/wf-env-use.sh" "$@"
