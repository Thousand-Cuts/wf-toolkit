---
description: Remove a Workfront environment folder — requires two-factor confirmation. Archives any exports if --force-keep-exports is given.
---

You are removing an environment folder. This is destructive — confirm carefully.

## Steps

1. **Ask which slug to remove.** Show the user the output of `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-list.sh` first so they can see what's there.

2. **Confirm explicitly.** Ask the user to retype the slug to confirm. Do not proceed if the retyped slug doesn't match exactly.

3. **Check for exports.** If `~/wf-envs/<slug>/exports/` is non-empty, warn the user and ask whether they want to:
   - Cancel and inspect manually.
   - Archive the exports to `~/wf-envs/_archived/<slug>-<timestamp>/` and remove the folder (pass `--force-keep-exports`).

4. **Invoke the removal:**

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-remove.sh "<slug>" --yes-i-typed-it "<retyped-slug>" [--force-keep-exports]
   ```

5. **Report what was removed and where any archives went.**
