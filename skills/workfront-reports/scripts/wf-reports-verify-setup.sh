#!/usr/bin/env bash
# wf-reports-verify-setup.sh — one-time setup for the [wf-reports-verify] flow.
#
# Drops a tiny env-var file at ~/wf-envs/reports-verify.env
# that SKILL.md sources before invoking wf-curl.sh / wf-cleanup.sh. Reuses
# the shared environment store's credentials at ~/wf-envs/<slug>/.env
# (provisioned via /wf-env-add).
#
# Idempotent: re-running overwrites with identical content.
#
# Usage:
#   bash skills/workfront-reports/scripts/wf-reports-verify-setup.sh

set -euo pipefail

ENVS_DIR="${HOME}/wf-envs"
TARGET="${ENVS_DIR}/reports-verify.env"

mkdir -p "$ENVS_DIR"

cat > "$TARGET" <<'EOF'
# Sourced by skills/workfront-reports SKILL.md before any wf-curl.sh write.
# Adjusts the shared verify scripts so reports objects get their own prefix
# and sweep set without disturbing workfront-api's [wf-api-verify] flow.
WF_VERIFY_PREFIX="[wf-reports-verify]"
WF_VERIFY_OBJCODES="report,uift,uigb,uivw"
EOF

chmod 600 "$TARGET"
echo "wf-reports-verify-setup: wrote ${TARGET}"
echo "wf-reports-verify-setup: reports flow will now use prefix '[wf-reports-verify]' and sweep report/uift/uigb/uivw."
