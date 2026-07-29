# Environment credentials & write safety (shared reference)

The single source of truth for how every write-capable Workfront skill handles
environment credentials and gates writes. Skills link here instead of restating it.

## The environment credential store

Each environment of your Workfront instance (production, preview sandbox,
dedicated sandbox) is one folder: `~/wf-envs/<slug>/` with a mode-600
`.env` holding `WF_ENV_LABEL`, `WF_HOST`, `WF_ENV_TYPE` (preview/sandbox/prod),
`WF_SCOPE_PORTFOLIO_ID` (optional reference metadata — **not** enforced),
`WF_DEFAULT_USER_EMAIL` (optional), `WF_READ_ONLY` (`1` or empty), and
`WF_API_KEY`. The active environment is named in `~/wf-envs/.active`.

Every Workfront API call goes through
`bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh <path> [curl args…]`.
The wrapper sources the active `.env`, so the API key is never in this script's
argv and never in chat. (It is placed in the request URL's query string, which
Workfront's API-key auth requires for POST/PUT/DELETE — so it is visible in `ps`
for the curl child's lifetime and would leak into a transcript if `curl -v` were
added. Do not add `-v`.)

## Onboarding — one command

Setup is a single interactive terminal command:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-setup.sh <slug>
```

It prompts for label, host, env type, read-only, and default email, then the API
key with hidden input, validates the key with one live call, writes the `.env`,
and activates the environment. **Never ask the user to paste the API key into
chat.** If they offer it, refuse and point them at this command. To switch the
active environment later: `/wf-env-use <slug>`. To rotate just the key:
`wf-env-setkey.sh <slug> --rotate`.

(The underlying primitives — `wf-env-add.sh`, `wf-env-setkey.sh`,
`wf-env-use.sh` — remain available for scripted/automated use.)

## Write guards enforced by wf-env-curl.sh

1. **Read-only folders** (`WF_READ_ONLY=1`): every write is refused (exit 3),
   regardless of host or env. GETs and `POST /search` reads still work. Use this
   for assessments, audits, and any read-only diagnostic work.

2. **Explicit-OK for non-disposable environments.** preview/sandbox/dev/test-drive
   are treated as disposable and write freely. **prod** (or an unrecognized host
   with no `WF_ENV_TYPE`) refuses writes unless `WF_ENV_WRITE_ACK=1` is set.
   There is **no portfolio scoping** — the admin's typed OK is the gate.
   (The removed v1 "scope portfolio" guard only checked that an env var was set;
   it never verified the write target was inside the portfolio, so it was
   theatre.)

   The skill's flow for a prod write:
   1. Surface the target host + label and a plain-English summary of the write.
   2. Wait for the admin to type an explicit `yes`.
   3. Prepend `WF_ENV_WRITE_ACK=1` to each wrapper invocation **for that batch
      only** — e.g. `WF_ENV_WRITE_ACK=1 bash …/wf-env-curl.sh -X PUT …`.
      Do not `export` it persistently. If the session/shell changes or the
      admin resumes later, re-confirm before writing again.

   Never set `WF_ENV_WRITE_ACK=1` pre-emptively or without a fresh typed OK.

## Method detection (why writes can't slip past the guard)

`wf-env-curl.sh` classifies the HTTP method from `-X`/`--request` (including
the `-XPOST` attached and `--request=POST` equals forms) and treats a raw-body
data flag (`-d`/`--data`/`--data-raw`/`--data-binary`/`-F`…) with no explicit
method as an implicit POST — mirroring curl. `--data-urlencode` is deliberately
**not** treated as a write: it is the GET read idiom (the wrapper adds `-G` so
those fields become query params). So build reads with `--data-urlencode` and
writes with an explicit `-X` (plus `--data-urlencode` for the body fields).

## Verification handshake

Before acting against an environment, confirm creds resolve with a cheap read:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  /attask/api/v17.0/user/search --data-urlencode '$$LIMIT=1' --data-urlencode 'fields=customer:name'
```

Echo the returned `customer:name` back to the user so they can confirm
they are pointed at the right environment.

## Rotate / revoke reminder

API keys are the admin's responsibility to rotate/revoke in Workfront
(Setup → System → Customer Info → API Key Settings). Remind
them when an environment is retired. `WF_HOST`/`WF_ENV_TYPE` are safe to edit by
hand; never hand-edit `WF_API_KEY` — use `wf-env-setkey.sh <slug> --rotate`.
