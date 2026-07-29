#!/usr/bin/env bash
# wf-creds-setup.sh — compatibility shim for the shared environment store.
#
# Verification credentials live in the toolkit-wide environment store
# (~/wf-envs/, managed by /wf-env-add et al.), so setup is the same
# one-step interactive flow as registering any environment. This shim
# delegates to the shared onboarding script.
#
# NOTE: credentials used for the workfront-api skill's self-verification
# should point at your sandbox/preview environment — not production.
# Reflect that in the slug/label (e.g. 'sandbox').
#
# Usage: wf-creds-setup.sh [<slug>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "${SCRIPT_DIR}/../../_shared/scripts/wf-env-setup.sh" "$@"
