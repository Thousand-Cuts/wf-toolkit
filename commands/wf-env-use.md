---
description: Set the active Workfront environment (read from ~/wf-envs/.active by every skill) or list configured environments when called with no argument.
---

You are switching the active Workfront environment for the wf-toolkit skills.

## Steps

1. **If the user supplied a slug**, invoke:

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-use.sh "<slug>"
   ```

   Confirm the new active environment to the user.

2. **If no slug was supplied**, invoke the same script with no args — it lists configured environments with their label, host, and env type. Show the listing to the user and ask which slug they want to activate.

## Important

- If the script exits 1 (unknown slug), help the user decide whether to `/wf-env-add` a new one or pick from the existing list.
- If the script exits 2 (no environments configured), prompt the user to run `/wf-env-add <slug>` first.
