#!/usr/bin/env bash
# tests/wf_env_folders/test_use_list.sh
set -euo pipefail
cd "$(dirname "$0")"
. ./lib.sh

setup_tmphome
trap teardown_tmphome EXIT

ADD="${SCRIPTS_DIR}/wf-env-add.sh"
USE="${SCRIPTS_DIR}/wf-env-use.sh"
LIST="${SCRIPTS_DIR}/wf-env-list.sh"

# No environments yet: list exits 0, use with no arg exits 2 (usage).
OUT="$("$LIST")"
assert_eq "$(printf '%s' "$OUT" | grep -c 'no environments configured')" "1" "list says no environments"

set +e
"$USE" >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "2" "use with no arg + no environments exits 2"

# Register two environments.
"$ADD" preview "Acme — Preview" acme.preview.workfront.com preview "" ""
"$ADD" sandbox "Acme — Sandbox" acme.sandbox.workfront.com sandbox "" ""

# Set active.
"$USE" preview
assert_file "$WF_ENVS_HOME/.active" ".active file created"
assert_eq "$(cat "$WF_ENVS_HOME/.active")" "preview" ".active contains preview"

# Refuses unknown slug.
set +e
"$USE" nosuch >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "1" "use rejects unknown slug"

# Switch.
"$USE" sandbox
assert_eq "$(cat "$WF_ENVS_HOME/.active")" "sandbox" "active switched to sandbox"

# `use` with no arg lists when environments exist.
OUT="$("$USE" 2>&1 || true)"
assert_eq "$(printf '%s' "$OUT" | grep -c 'preview')" "1" "use-with-no-arg lists preview"
assert_eq "$(printf '%s' "$OUT" | grep -c 'sandbox')" "1" "use-with-no-arg lists sandbox"

# list shows the environment folder section with all registered slugs.
OUT="$("$LIST")"
assert_eq "$(printf '%s' "$OUT" | grep -c 'Workfront environments')" "1" "list has environment section header"
assert_eq "$(printf '%s' "$OUT" | grep -c 'preview')" "1" "list includes preview"
assert_eq "$(printf '%s' "$OUT" | grep -c 'sandbox')" "1" "list includes sandbox"

# Read-only environment surfaces [RO] marker in listing.
"$ADD" rolist "Acme — Prod RO" acme.my.workfront.com prod "" "" "1"
OUT="$("$LIST")"
assert_eq "$(printf '%s' "$OUT" | grep -c 'rolist.*\[RO\]')" "1" "RO marker appears next to rolist entry"

# Robustness: an older-schema .env with no WF_READ_ONLY line does not crash list or use.
mkdir -p "$WF_ENVS_HOME/legacy"
chmod 700 "$WF_ENVS_HOME/legacy"
cat > "$WF_ENVS_HOME/legacy/.env" <<'EOF'
WF_ENV_LABEL="Legacy — no RO field"
WF_HOST="acme.preview.workfront.com"
WF_ENV_TYPE="preview"
WF_SCOPE_PORTFOLIO_ID=""
WF_DEFAULT_USER_EMAIL=""
WF_API_KEY="x"
EOF
chmod 600 "$WF_ENVS_HOME/legacy/.env"

OUT="$("$LIST")"
assert_eq "$(printf '%s' "$OUT" | grep -c 'legacy')" "1" "list includes legacy-schema entry without crashing"
assert_eq "$(printf '%s' "$OUT" | grep -c 'legacy.*\[RO\]')" "0" "legacy entry has no [RO] marker (no WF_READ_ONLY line)"
"$USE" legacy
assert_eq "$(cat "$WF_ENVS_HOME/.active")" "legacy" "wf-env-use works against legacy schema"

echo "test_use_list.sh OK"
