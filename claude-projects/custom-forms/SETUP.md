# Claude.ai Project setup — workfront-custom-forms

**STRONG WARNING — use Route A (Claude Code plugin) for this skill if you possibly can.** Custom-forms is a write-capable skill with cross-environment clone, and Route B (Claude.ai Project) has material drawbacks here:

1. **You must paste up to two API keys into chat** — destination, and source if cloning from another environment. Claude.ai cannot run the `wf-env-curl.sh` wrapper, so keys come through chat. Anything you paste into a Claude.ai chat can be retained server-side per Anthropic's data policies. Treat every key you paste here as potentially logged and **rotate immediately after the run**.
2. **You run every API call yourself** — including the form/parameter/parameterGroup/parameterOption/category-link sequence (5+ POSTs per form) and the audit-flow queries. Route A does this in one continuous flow; Route B requires you to copy-paste each curl and response back.

Route A setup is in the top-level README ("Route A setup — Claude Code" + "Environments"). If you've never used Claude Code: it's bundled in the Claude Desktop App.

Continue below only if Route A is not an option for you.

## What Route B is

Setting up a Claude.ai Project to use this skill via Route B.

## What this Project enables

Design / audit / clone discussions for Workfront custom forms in a Claude.ai chat. The Project knows the object model, the recipes, and the gotchas. Claude composes API call sequences which you run locally (paste-back the responses for next steps).

**Caveat:** Route A (Claude Code) is materially better for this skill. The `option_list_parser.py` + `form_sanitizer.py` + `schema_cache.py` pure-Python helpers execute deterministically there; in Route B you have to drive each shell command manually and paste responses back.

## Steps

1. **Create a new Claude.ai Project** named "Workfront Custom Forms".

2. **Upload the knowledge files** from this repo into Project Knowledge:
   - `knowledge/custom-forms/00-rubric-and-workflow.md`
   - `knowledge/custom-forms/01-object-model.md`
   - `knowledge/custom-forms/02-parameter-types.md`
   - `knowledge/custom-forms/03-create-form-recipe.md`
   - `knowledge/custom-forms/04-add-field-to-existing-form.md`
   - `knowledge/custom-forms/05-audit-recipes.md`
   - `knowledge/custom-forms/06-clone-and-adapt-recipe.md`
   - `knowledge/custom-forms/07-display-logic.md`
   - `knowledge/custom-forms/08-runtime-schema-discovery.md`
   - `knowledge/custom-forms/09-gotchas.md`

   Simplest approach: just upload every file in `knowledge/custom-forms/` — the list above exists to show what each file covers, not as an exhaustive checklist that must be kept in sync by hand.

3. **Upload the example payloads** to give Claude concrete reference shapes:
   - `examples/custom-forms/project-vendor-tracking.json`
   - `examples/custom-forms/project-country-dropdown.json`
   - `examples/custom-forms/user-skills-tag.json`
   - `examples/custom-forms/task-effort-band.json`
   - `examples/custom-forms/optask-triage-form.json`
   - The three narrated `.md` walkthroughs (`clone-between-environments.md`, `clone-options-from-existing-field.md`, `audit-form-usage.md`)

4. **Optional:** upload peer-skill knowledge for inline reference:
   - `knowledge/api/05-http-methods-and-actions.md` (bulk-POST tunneling)
   - `knowledge/api/12-external-lookup-fields.md` (URL parameterType caveat)

5. **Add Project instructions** from `claude-projects/custom-forms/project-instructions.md` to the Project's "Project instructions" / system prompt field.

6. **Confirm the version uploaded.** Re-upload changed files when the repo updates (no auto-sync from GitHub).

## How the admin uses it

In a Project chat:

> "Create a custom form for projects to track vendor info. Fields: vendor name (text), spend approved (currency), department (dropdown: Marketing, Sales, Ops, Engineering)."

Claude:
- Asks for the form's display name + objCode (if not clear)
- Builds the POST sequence
- Shows the curl commands to run
- Asks you to paste the responses
- Tracks created IDs for the categoryParameter link calls at the end

For audits, you paste API responses and Claude interprets them per `05-audit-recipes.md`.

## What doesn't work in Route B

- The `option_list_parser.py` autodetection — Claude can parse the same input modes manually but it's slower.
- The `form_sanitizer.py` automated ID walk — you have to identify environment-specific IDs by hand or paste them all and ask Claude to flag them.
- The schema_cache — every session re-discovers schema from pasted `/metadata` responses.

## Maintenance

Knowledge files change with the repo. When the maintainer ships a new version (CHANGELOG entry), download the changed files and replace them in the Project.
