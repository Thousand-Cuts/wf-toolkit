# tests/wf_env_folders/lib.sh — shared helpers for wf-env-* smoke tests.
# Source this from each test_*.sh.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS_DIR="${REPO_ROOT}/skills/_shared/scripts"

# Each test gets its own temp HOME-ish dir. setup_tmphome must be called
# at the start of every test; teardown_tmphome at the end (or via trap).
setup_tmphome() {
  WF_ENVS_HOME="$(mktemp -d -t wf-envs.XXXXXX)"
  export WF_ENVS_HOME
}

teardown_tmphome() {
  [ -n "${WF_ENVS_HOME:-}" ] && rm -rf "$WF_ENVS_HOME"
}

# assert_eq <actual> <expected> <label>
assert_eq() {
  if [ "$1" != "$2" ]; then
    echo "FAIL: $3" >&2
    echo "  expected: $2" >&2
    echo "  actual:   $1" >&2
    exit 1
  fi
}

# assert_file <path> <label>
assert_file() {
  [ -f "$1" ] || { echo "FAIL: $2 — expected file at $1" >&2; exit 1; }
}

# assert_perm <path> <expected mode digits> <label>
assert_perm() {
  local perm
  perm="$(stat -f '%Lp' "$1" 2>/dev/null || stat -c '%a' "$1")"
  assert_eq "$perm" "$2" "$3"
}

# assert_contains <file> <substring> <label>
assert_contains() {
  grep -qF -- "$2" "$1" || { echo "FAIL: $3 — '$2' not found in $1" >&2; exit 1; }
}

# assert_exit <expected exit code> <label> <command...>
assert_exit() {
  local expected="$1" label="$2"; shift 2
  set +e
  "$@" >/dev/null 2>&1
  local got=$?
  set -e
  assert_eq "$got" "$expected" "$label"
}
