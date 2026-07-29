#!/usr/bin/env bash
# tests/wf_env_folders/test_add.sh
set -euo pipefail
cd "$(dirname "$0")"
. ./lib.sh

setup_tmphome
trap teardown_tmphome EXIT

ADD="${SCRIPTS_DIR}/wf-env-add.sh"

# 1. Happy path: preview env, no scope.
"$ADD" preview "Acme — Preview" acme.preview.workfront.com preview "" ""
assert_perm "$WF_ENVS_HOME/preview" 700 "environment folder is 700"
assert_perm "$WF_ENVS_HOME/preview/audit" 700 "audit/ is 700"
assert_perm "$WF_ENVS_HOME/preview/exports" 700 "exports/ is 700"
assert_file "$WF_ENVS_HOME/preview/.env" ".env exists"
assert_perm "$WF_ENVS_HOME/preview/.env" 600 ".env is 600"
assert_contains "$WF_ENVS_HOME/preview/.env" 'WF_ENV_LABEL="Acme — Preview"' "label written"
assert_contains "$WF_ENVS_HOME/preview/.env" 'WF_HOST="acme.preview.workfront.com"' "host written"
assert_contains "$WF_ENVS_HOME/preview/.env" 'WF_ENV_TYPE="preview"' "env type written"
assert_contains "$WF_ENVS_HOME/preview/.env" 'WF_API_KEY=""' "key placeholder is empty string"
assert_contains "$WF_ENVS_HOME/preview/.env" '# DO NOT open this folder in screenshares' "screenshare warning present"

# 2. Prod env no longer requires a scope portfolio — creation succeeds with none.
#    (v1 required it; the guard moved to a write-time explicit OK.)
"$ADD" prod "Acme — Prod" acme.my.workfront.com prod "" ""
assert_contains "$WF_ENVS_HOME/prod/.env" 'WF_ENV_TYPE="prod"' "prod env type written"
assert_contains "$WF_ENVS_HOME/prod/.env" 'WF_SCOPE_PORTFOLIO_ID=""' "scope may be empty for prod"

# 3. An optional scope portfolio is still recorded as reference metadata.
"$ADD" prod2 "Acme — Prod (scoped)" acme.my.workfront.com prod 5f0aaaaaaaaaaaaaaaaaaaaa ""
assert_contains "$WF_ENVS_HOME/prod2/.env" 'WF_SCOPE_PORTFOLIO_ID="5f0aaaaaaaaaaaaaaaaaaaaa"' "optional scope portfolio recorded"

# 4. Slug validation rejects bad chars.
assert_exit 1 "slug with space rejected" "$ADD" "bad slug" "L" "h" "preview" "" ""
assert_exit 1 "slug with slash rejected" "$ADD" "bad/slug" "L" "h" "preview" "" ""

# 5. Refuses to overwrite existing folder.
assert_exit 1 "refuses to clobber existing environment" \
  "$ADD" preview "Acme — Preview" acme.preview.workfront.com preview "" ""

# 6. Host with scheme is stripped.
"$ADD" sandbox "Acme — Sandbox" "https://acme.sandbox.workfront.com/" sandbox "" ""
assert_contains "$WF_ENVS_HOME/sandbox/.env" 'WF_HOST="acme.sandbox.workfront.com"' "scheme stripped, trailing slash stripped"

# 7. Read-only flag: prod env without scope is allowed when read_only=1.
"$ADD" prodro "Acme — Prod RO" acme.my.workfront.com prod "" "" "1"
assert_contains "$WF_ENVS_HOME/prodro/.env" 'WF_READ_ONLY="1"' "read-only flag written"
assert_contains "$WF_ENVS_HOME/prodro/.env" 'WF_SCOPE_PORTFOLIO_ID=""' "scope still empty under RO"

# 8. Read-only off by default — existing 6-arg calls still produce WF_READ_ONLY="".
assert_contains "$WF_ENVS_HOME/preview/.env" 'WF_READ_ONLY=""' "RO defaults to empty when 7th arg omitted"

# 9. Prod env, no scope, read_only NOT set → now allowed (guard moved to write-time OK).
"$ADD" prod3 "Acme — Prod (plain)" acme.my.workfront.com prod "" "" ""
assert_contains "$WF_ENVS_HOME/prod3/.env" 'WF_ENV_TYPE="prod"' "prod created without scope or RO"

echo "test_add.sh OK"
