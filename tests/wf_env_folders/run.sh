#!/usr/bin/env bash
# tests/wf_env_folders/run.sh — run every test_*.sh in this directory.
# Each test runs in a fresh subshell so $WF_ENVS_HOME doesn't leak.
set -euo pipefail

shopt -s nullglob

cd "$(dirname "$0")"
PASS=0
FAIL=0
for t in test_*.sh; do
  echo "=== $t ==="
  if bash "$t"; then
    PASS=$((PASS+1))
    echo "PASS: $t"
  else
    FAIL=$((FAIL+1))
    echo "FAIL: $t"
  fi
done
echo
echo "Total: $((PASS+FAIL)) — Pass: $PASS — Fail: $FAIL"
[ "$FAIL" = 0 ]
