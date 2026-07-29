# Claude.ai Project setup — workfront-permissions

**STRONG WARNING — use Route A (Claude Code plugin) for this skill if you possibly can.** Permissions is a read-heavy skill that walks the 6-input permission graph against your Workfront instance. Route B requires pasting an admin-tier API key into chat, which Claude.ai may retain server-side. Treat any pasted key as logged and **rotate immediately after the run**.

Route A setup is in the top-level README ("Environments" + "Route A setup — Claude Code"). Continue below only if Route A is not an option for you.

## Route B setup

Setting up a Claude.ai Project to use this skill via Route B. See repo README §"Route B" for the dual-channel context.

## What this Project enables

The skill's diagnostic and audit flows run via Claude.ai chat against text-pasted Workfront API responses. No local script execution — the 6-input combiner runs manually in-context, following the procedure in `knowledge/permissions/04-debug-playbook.md`.

**Caveat:** Route A (Claude Code) is materially better for this skill — the `permission_resolver.py` combiner runs deterministically there. Route B requires Claude to walk the 7-step procedure manually for each diagnosis, which is slower and error-prone. Use Route B only when Route A isn't an option.

## Steps

1. **Create a new Claude.ai Project** named "Workfront Permissions" (or whatever fits your organisation's conventions).

2. **Upload the knowledge files** from this repo into the Project's Knowledge:
   - `knowledge/permissions/00-rubric-and-workflow.md`
   - `knowledge/permissions/01-permission-model.md`
   - `knowledge/permissions/02-access-level-reference.md`
   - `knowledge/permissions/03-accessrule-shape.md`
   - `knowledge/permissions/04-debug-playbook.md`  (most important — Claude follows this manually)
   - `knowledge/permissions/05-audit-recipes.md`
   - `knowledge/permissions/06-inheritance-and-ownership.md`
   - `knowledge/permissions/07-system-wide-overrides.md`
   - `knowledge/permissions/08-runtime-schema-discovery.md`
   - `knowledge/permissions/09-gotchas.md`

   Simplest approach: just upload every file in `knowledge/permissions/` — the list above exists to show what each file covers, not as an exhaustive checklist that must be kept in sync by hand.

3. **Optional:** also upload the relevant peer-skill knowledge files if you need auth or pagination help inline:
   - `knowledge/api/02-authentication.md`
   - `knowledge/api/09-pagination-and-limits.md`

4. **Add the Project instructions** from `claude-projects/permissions/project-instructions.md` to the Project's "Project instructions" / system prompt field.

5. **Confirm the version uploaded.** When the repo updates a knowledge file, re-download and re-upload (no auto-sync from GitHub).

## How you use it

In a Project chat:

> "Why can't Adam Gray edit project X? I ran these GETs already, here are the responses." (Pastes user + project + accessRules + accessLevel JSON.)

Claude walks the 7-step procedure from `04-debug-playbook.md`, produces a verdict, and explains each layer. You either confirm the diagnosis or run additional GETs and paste more context.

## What doesn't work in Route B

- The `permission_resolver.py` pytest suite — local execution only.
- The schema cache — every session re-discovers schema from pasted-in metadata responses.
- Cross-environment compare automation — Claude can do the diff manually if you paste both AccessLevel responses.

## Maintenance

Knowledge files change with the repo. When the maintainer ships a new version (CHANGELOG entry), download the changed files and replace them in the Project. The Project's instructions can stay stable.
