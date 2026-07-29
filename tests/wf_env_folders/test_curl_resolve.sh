#!/usr/bin/env bash
# tests/wf_env_folders/test_curl_resolve.sh
set -euo pipefail
cd "$(dirname "$0")"
. ./lib.sh

setup_tmphome
trap teardown_tmphome EXIT

ADD="${SCRIPTS_DIR}/wf-env-add.sh"
SETKEY="${SCRIPTS_DIR}/wf-env-setkey.sh"
USE="${SCRIPTS_DIR}/wf-env-use.sh"
CURL="${SCRIPTS_DIR}/wf-env-curl.sh"
RESOLVE="${SCRIPTS_DIR}/wf-env-resolve.sh"

# No active environment → curl exits 1.
"$ADD" preview "Acme — Preview" acme.preview.workfront.com preview "" ""
echo "fake-key" | WF_ENV_SETKEY_FROM_STDIN=1 "$SETKEY" preview --skip-handshake

set +e
"$CURL" /attask/api/v17.0/user/search >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "1" "curl with no active environment exits 1"

# After /wf-env-use, curl tries to invoke real curl. We hijack curl by
# putting a shim earlier on PATH that prints its args.
SHIM_DIR="$(mktemp -d -t wf-curl-shim.XXXXXX)"
trap 'rm -rf "$SHIM_DIR"; teardown_tmphome' EXIT
cat > "$SHIM_DIR/curl" <<'EOF'
#!/usr/bin/env bash
echo "CURL_INVOKED"
for a in "$@"; do echo "ARG: $a"; done
EOF
chmod +x "$SHIM_DIR/curl"

"$USE" preview
OUT="$(PATH="${SHIM_DIR}:${PATH}" "$CURL" /attask/api/v17.0/user/search 2>&1 || true)"

# Key must NOT appear as a plain CLI arg printed to stdout — it goes inside the URL.
assert_eq "$(printf '%s' "$OUT" | grep -c 'CURL_INVOKED')" "1" "curl was invoked"
assert_eq "$(printf '%s' "$OUT" | grep -c 'apiKey=fake-key')" "1" "apiKey in URL query string"
assert_eq "$(printf '%s' "$OUT" | grep -c 'https://acme.preview.workfront.com/attask/api/v17.0/user/search')" "1" "URL built from host + path"

# Prod writes require an explicit per-invocation OK (WF_ENV_WRITE_ACK=1).
# There is no portfolio scope anymore — a prod environment may be created with none.
"$ADD" prod "Acme — Prod" acme.my.workfront.com prod "" ""
echo "fake-key-2" | WF_ENV_SETKEY_FROM_STDIN=1 "$SETKEY" prod --skip-handshake
"$USE" prod

# Prod write with no ack → refused; message names the PROD environment + confirmation.
set +e
OUT="$(PATH="${SHIM_DIR}:${PATH}" "$CURL" -X PUT /attask/api/v17.0/project/abc --data-urlencode "name=x" 2>&1)"
GOT=$?
set -e
assert_eq "$GOT" "3" "prod write with no ack exits 3"
assert_eq "$(printf '%s' "$OUT" | grep -c 'PROD environment')" "1" "refusal mentions PROD environment"
assert_eq "$(printf '%s' "$OUT" | grep -c 'requires explicit confirmation')" "1" "refusal mentions explicit confirmation"

# Prod write with WF_ENV_WRITE_ACK=1 → proceeds (skill-driven, after typed OK).
OUT="$(WF_ENV_WRITE_ACK=1 PATH="${SHIM_DIR}:${PATH}" "$CURL" -X PUT /attask/api/v17.0/project/abc --data-urlencode "name=x" 2>&1 || true)"
assert_eq "$(printf '%s' "$OUT" | grep -c 'CURL_INVOKED')" "1" "prod write with WF_ENV_WRITE_ACK=1 proceeds"

# Method-detection: writes that omit an explicit -X must still be caught, so the
# ack gate cannot be bypassed. Each of these on prod with no ack → refused (3).
set +e
PATH="${SHIM_DIR}:${PATH}" "$CURL" --request=POST /attask/api/v17.0/optask --data-urlencode "name=x" >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "3" "--request=POST (equals form) detected as write, refused without ack"

set +e
PATH="${SHIM_DIR}:${PATH}" "$CURL" -XPUT /attask/api/v17.0/project/abc --data-urlencode "name=x" >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "3" "-XPUT (attached form) detected as write, refused without ack"

set +e
PATH="${SHIM_DIR}:${PATH}" "$CURL" /attask/api/v17.0/optask -d "name=x" >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "3" "bare -d (implicit POST) detected as write, refused without ack"

# Read idiom preserved: GET-by-id using --data-urlencode for fields (no -X) must
# NOT be misclassified as a write — curl is still invoked.
OUT="$(PATH="${SHIM_DIR}:${PATH}" "$CURL" /attask/api/v17.0/project/abc --data-urlencode "fields=name,status" 2>&1 || true)"
assert_eq "$(printf '%s' "$OUT" | grep -c 'CURL_INVOKED')" "1" "GET + --data-urlencode read not blocked on prod"

# wf-env-resolve.sh without flags prints active slug.
OUT="$("$RESOLVE")"
assert_eq "$(printf '%s' "$OUT" | tr -d '[:space:]')" "prod" "resolve prints active slug"

# wf-env-resolve.sh --source defaults to the active environment.
# In test mode the script reads default rather than prompting (WF_ENV_RESOLVE_NONINTERACTIVE=1).
OUT="$(WF_ENV_RESOLVE_NONINTERACTIVE=1 "$RESOLVE" --source)"
assert_eq "$(printf '%s' "$OUT" | tr -d '[:space:]')" "env:prod" "resolve --source defaults to active environment"

# Read-only environment: writes are refused even when scope is set.
"$ADD" roenv "Acme — Prod RO" acme.my.workfront.com prod "" "" "1"
echo "fake-key-3" | WF_ENV_SETKEY_FROM_STDIN=1 "$SETKEY" roenv --skip-handshake
"$USE" roenv

# GET still works.
OUT="$(PATH="${SHIM_DIR}:${PATH}" "$CURL" /attask/api/v17.0/user/search 2>&1 || true)"
assert_eq "$(printf '%s' "$OUT" | grep -c 'CURL_INVOKED')" "1" "RO environment allows GET"

# PUT refused with exit 3 and "read-only" message.
set +e
OUT="$(PATH="${SHIM_DIR}:${PATH}" "$CURL" -X PUT /attask/api/v17.0/project/abc --data-urlencode "name=x" 2>&1)"
GOT=$?
set -e
assert_eq "$GOT" "3" "RO environment write exits 3"
assert_eq "$(printf '%s' "$OUT" | grep -c 'read-only')" "1" "RO refusal message mentions read-only"

# POST /search (read disguised as POST) still works on RO.
OUT="$(PATH="${SHIM_DIR}:${PATH}" "$CURL" -X POST /attask/api/v17.0/project/search --data-urlencode "filters=x" 2>&1 || true)"
assert_eq "$(printf '%s' "$OUT" | grep -c 'CURL_INVOKED')" "1" "POST /search not blocked under RO"

# 0.26.1: WF_ENV_TYPE=sandbox with a non-pattern-matching hostname must allow
# writes without a scope portfolio. Pre-fix the guard refused these (matched
# only *preview*/*sandbox*/*dev* substrings in the hostname).
"$ADD" sbx1 "Acme — Sandbox (UAT host)" acme.uat.workfront.com sandbox "" "" ""
echo "fake-key-4" | WF_ENV_SETKEY_FROM_STDIN=1 "$SETKEY" sbx1 --skip-handshake
"$USE" sbx1
OUT="$(PATH="${SHIM_DIR}:${PATH}" "$CURL" -X PUT /attask/api/v17.0/project/abc --data-urlencode "name=x" 2>&1 || true)"
assert_eq "$(printf '%s' "$OUT" | grep -c 'CURL_INVOKED')" "1" "sandbox env_type allows unscoped write regardless of hostname"

echo "test_curl_resolve.sh OK"
