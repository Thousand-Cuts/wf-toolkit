#!/usr/bin/env bash
# tests/wf_env_folders/test_remove.sh
set -euo pipefail
cd "$(dirname "$0")"
. ./lib.sh

setup_tmphome
trap teardown_tmphome EXIT

ADD="${SCRIPTS_DIR}/wf-env-add.sh"
REMOVE="${SCRIPTS_DIR}/wf-env-remove.sh"

"$ADD" preview "Acme — Preview" acme.preview.workfront.com preview "" ""

# 1. Refuses without --yes-i-typed-it confirmation.
set +e
"$REMOVE" preview >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "2" "remove without confirmation flag exits 2"

# 2. Refuses unknown slug.
assert_exit 1 "remove unknown slug" "$REMOVE" nosuch --yes-i-typed-it nosuch

# 3. Refuses mismatched confirmation (slug doesn't match what was typed).
set +e
"$REMOVE" preview --yes-i-typed-it sandbox >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "1" "remove with mismatched confirmation slug"

# 4. Happy path on empty exports/.
"$REMOVE" preview --yes-i-typed-it preview
[ ! -d "$WF_ENVS_HOME/preview" ] || { echo "FAIL: preview folder still exists" >&2; exit 1; }

# 5. Non-empty exports/ → refuses without --force-keep-exports.
"$ADD" sandbox "Acme — Sandbox" acme.sandbox.workfront.com sandbox "" ""
echo "report" > "$WF_ENVS_HOME/sandbox/exports/report.md"
set +e
"$REMOVE" sandbox --yes-i-typed-it sandbox >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "1" "remove refuses non-empty exports without --force-keep-exports"
[ -d "$WF_ENVS_HOME/sandbox" ] || { echo "FAIL: sandbox folder removed when it shouldn't be" >&2; exit 1; }

# 6. --force-keep-exports archives them, then removes.
"$REMOVE" sandbox --yes-i-typed-it sandbox --force-keep-exports
[ ! -d "$WF_ENVS_HOME/sandbox" ] || { echo "FAIL: sandbox folder still exists after archive+remove" >&2; exit 1; }
ARCHIVED="$(ls -d "$WF_ENVS_HOME"/_archived/sandbox-* 2>/dev/null | head -1)"
[ -n "$ARCHIVED" ] || { echo "FAIL: no archive dir created" >&2; exit 1; }
assert_file "$ARCHIVED/report.md" "export preserved in archive"

echo "test_remove.sh OK"
