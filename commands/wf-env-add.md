---
description: Register a new Workfront environment — one terminal command sets up the folder, API key (hidden input), and activation in a single step.
---

You are helping the user register an environment of their Workfront instance (production, preview sandbox, or dedicated sandbox). Setup is a single interactive script run in their terminal — it prompts for all metadata, then the API key with hidden input, validates the key with one live call, writes `~/wf-envs/<slug>/.env`, and activates the environment. **The API key must never be pasted into chat.**

## Steps

1. **Suggest a slug.** `[a-zA-Z0-9_-]` only — a short name for the environment (e.g. `prod`, `preview`, `sandbox`). If they gave a name with spaces/punctuation, propose the normalised slug.

2. **Tell the user to run this one command in their terminal:**

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-setup.sh <slug>
   ```

   Explain what it will prompt for, so they can have answers ready:
   - **Label** — appears in listings, e.g. "Acme — Production".
   - **Host** — no scheme, no trailing slash, e.g. `acme.my.workfront.com`.
   - **Env type** — `preview`, `sandbox`, or `prod` (default `preview`). Preview/sandbox write freely; **prod writes require an explicit typed OK per session** (there is no portfolio scoping).
   - **Read-only?** — for assessments/audits. If yes, every write is refused regardless of env.
   - **Default user email** — optional, for skills that need a "me" reference.
   - **API key** — entered with hidden input (`read -s`) and validated with a single live call. Never enters chat.

3. **After it completes**, the environment is already active — no separate activation step. Confirm they can proceed. To switch environments later use `/wf-env-use <slug>`; to change just the key use `wf-env-setkey.sh <slug> --rotate`.

## Important

- Never ask the user to paste their API key into chat. If they offer it, refuse and point them at the terminal prompt in `wf-env-setup.sh`.
- Do not echo the key, write it via the Write tool, or pass it in any tool-call argument.
