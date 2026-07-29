#!/usr/bin/env bash
# tests/wf_env_folders/test_setkey.sh
set -euo pipefail
cd "$(dirname "$0")"
. ./lib.sh

setup_tmphome
trap teardown_tmphome EXIT

ADD="${SCRIPTS_DIR}/wf-env-add.sh"
SETKEY="${SCRIPTS_DIR}/wf-env-setkey.sh"

# Bootstrap an environment.
"$ADD" preview "Acme — Preview" acme.preview.workfront.com preview "" ""

# 1. Refuses if folder doesn't exist.
assert_exit 1 "setkey refuses unknown slug" "$SETKEY" nosuch

# 2. --skip-handshake bypasses the live API ping (we don't hit a real instance in tests).
#    WF_ENV_SETKEY_FROM_STDIN=1 reads the key from stdin instead of /dev/tty.
echo "secret-key-aaaa" | WF_ENV_SETKEY_FROM_STDIN=1 \
  "$SETKEY" preview --skip-handshake

assert_contains "$WF_ENVS_HOME/preview/.env" 'WF_API_KEY="secret-key-aaaa"' "key written"
assert_perm "$WF_ENVS_HOME/preview/.env" 600 ".env still 600 after key write"
# Make sure the file still has the other fields.
assert_contains "$WF_ENVS_HOME/preview/.env" 'WF_HOST="acme.preview.workfront.com"' "host preserved"
assert_contains "$WF_ENVS_HOME/preview/.env" 'WF_ENV_LABEL="Acme — Preview"' "label preserved"

# 3. Refuses overwrite without --rotate.
set +e
echo "secret-key-bbbb" | WF_ENV_SETKEY_FROM_STDIN=1 \
  "$SETKEY" preview --skip-handshake >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "1" "refuses second key write without --rotate"

# 4. --rotate allows overwrite.
echo "secret-key-bbbb" | WF_ENV_SETKEY_FROM_STDIN=1 \
  "$SETKEY" preview --skip-handshake --rotate
assert_contains "$WF_ENVS_HOME/preview/.env" 'WF_API_KEY="secret-key-bbbb"' "rotated key written"

# 5. Empty key is rejected.
set +e
echo "" | WF_ENV_SETKEY_FROM_STDIN=1 \
  "$SETKEY" preview --skip-handshake --rotate >/dev/null 2>&1
GOT=$?
set -e
assert_eq "$GOT" "1" "empty key rejected"

echo "test_setkey.sh OK"
