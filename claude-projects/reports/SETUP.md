# Setup — Workfront Reports Project (Claude.ai)

**STRONG WARNING — use Route A (Claude Code plugin) for this skill if you possibly can.** Reports is a write-capable skill with cross-environment clone, and Route B (Claude.ai Project) has material drawbacks here:

1. **You must paste up to two API keys into chat** — destination, and source if cloning from another environment. Claude.ai cannot run the `wf-env-curl.sh` wrapper, so keys come through chat. Anything you paste into a Claude.ai chat can be retained server-side per Anthropic's data policies. Treat every key you paste here as potentially logged and **rotate immediately after the run**.
2. **You run every API call yourself** — including the 4-call write sequence (UIFT → UIGB → UIVW → REPORT), the schema-discovery burst, the clone read sequence, and pre-flight. Route A does this in one continuous flow; Route B requires you to copy-paste each curl and response back.

Route A setup is in the top-level README ("Environment credentials" + "Route A — Claude Code"). If you've never used Claude Code: it's bundled in the Claude Desktop App.

Continue below only if Route A is not an option for you.

## What this recipe is

A Claude.ai Project setup that turns a chat into a Workfront-reports assistant for two flows:

1. **NL-create / modify** — author a list report from a natural-language description, or modify an existing one via PUT.
2. **Clone-and-adapt** — lift a known-good report from a source environment and write a sanitised copy to another environment (e.g. sandbox → prod).

The Project handles the interview, payload composition, sanitisation reasoning, and DE: parity check by referencing the uploaded knowledge files. You handle the actual HTTP requests in a terminal.

## Prerequisites

- Any Claude.ai plan (Free, Pro, Max, Team, or Enterprise — Projects are available on all plans)
- The repo files on your local machine (Code → Download ZIP on github.com, or clone this repo with `gh`/`git`)
- An admin-level API key for the destination environment (and a source-environment key if you're cloning)
- A way to run curl (Terminal on macOS, WSL on Windows, etc.)

## Files to upload

Every knowledge file plus every example:

- `knowledge/reports/00-rubric-and-workflow.md`
- `knowledge/reports/01-report-object-shape.md`
- `knowledge/reports/02-create-from-scratch-recipe.md`
- `knowledge/reports/03-clone-and-adapt-recipe.md`
- `knowledge/reports/04-runtime-schema-discovery.md`
- `knowledge/reports/05-gotchas.md`
- `knowledge/reports/06-filter-patterns.md`
- `knowledge/reports/07-view-patterns.md`
- `knowledge/reports/08-pre-flight-validation.md`
- `knowledge/reports/09-verification-flow.md`
- `examples/reports/active-projects-list.json`
- `examples/reports/overdue-tasks-by-portfolio.json`
- `examples/reports/user-activity-30d.json`
- `examples/reports/filter-or-group-example.json`
- `examples/reports/filter-exists-block-example.json`
- `examples/reports/view-with-valueexpression.json`
- `examples/reports/view-with-styledef.json`
- `examples/reports/clone-between-environments.md`

The list above exists to show what each file covers, not as an exhaustive checklist that must be kept in sync by hand — simplest approach is to upload every file in both `knowledge/reports/` and `examples/reports/`.

## Steps

1. Create a new Project in Claude.ai → **+ New Project** → name it "Workfront Reports".
2. Paste the entire contents of `claude-projects/reports/project-instructions.md` into the project's custom instructions field.
3. Upload every file listed above to the project's Knowledge panel.
4. In a chat, describe what you want:
   - **Create:** "Create a report of active projects grouped by portfolio."
   - **Modify:** "Modify the filter on report 65f2a... to also include status=PLN."
   - **Clone:** "Clone the 'Active Projects by PM' report from the preview sandbox into prod."
5. Claude will interview you for any missing fields, draft the curl commands, run a pre-flight field-existence check against the cached schema, and walk you through the 2/3/4-call sequence (UIFT → UIGB → UIVW → REPORT — UIFT and/or UIGB skipped when not needed). Run each curl yourself, paste the response, and Claude will compose the next call from it.
6. After the REPORT POST succeeds, run the smoke-test GET Claude provides and paste the result back so Claude can diff `filterID`/`groupByID`/`viewID` for silent UI-object re-resolution.

## Note about scripts

The Claude Code variant of this skill ships three Python helpers under `skills/workfront-reports/scripts/`:

- `schema_cache.py` — caches per-host `/metadata` responses for `report`, `uivw`, `uift`, `uigb` so the 2/3/4-call sequence has resolved field names.
- `sanitize_clone.py` — a deterministic JSON-object walker that flags tenant-specific values (IDs, dates, customer references, hardcoded host URLs in `valueexpression`) in a cloned source payload. 5-bucket output: strip / prompt / parity_check / host_rewrite / cleaned.
- `pre_flight_validator.py` — walks every field reference in the about-to-POST bundle and resolves it against the cached `/<uiObjCode>/metadata` JSON, blocking with suggestions when a reference doesn't exist (catches the PROJ-vs-TMPL class of error before any byte writes).

**These scripts cannot run inside a Claude.ai chat.** Route B has no shell environment, so Claude can't actually execute them — it will instead reason through the equivalent steps manually:

- Instead of `schema_cache.py put`, Claude will ask you to run the four `/metadata` curls yourself and paste the JSON back; the schema lives in chat context for the rest of the session, not on disk.
- Instead of `sanitize_clone.py`, Claude will walk the source payload field-by-field in the chat, flagging tenant-specific values for your review across the same 5 buckets.
- Instead of `pre_flight_validator.py`, Claude will mentally walk through the field-existence check: enumerate every `field` / `valuefield` / `group.fieldName` / column `name` reference in the composed UIFT/UIGB/UIVW/REPORT bundle, compare each against the schema-cache JSON you pasted earlier for the relevant `uiObjCode`, and block with a suggestion if any reference is missing. Don't pretend the script ran.

This works but is slower and more error-prone than Route A. For any production clone or when the field-schema surface is large, prefer Route A.

## Why Route A is meaningfully better for this skill

Route A: Claude Code runs the `/metadata` discovery, payload composition, the 4 writes, and the smoke-test GET directly. A typical create takes ~30 seconds end-to-end with a single typed `apply` confirmation.

Route B (this path): you run 5+ curls per create (4 metadata + 4 writes + 1 smoke test = 9 round-trips minimum) and paste responses between each. Same operation takes 5–10 minutes and increases the risk of misordering or skipping the smoke-test diff.

## Updates

When this repo updates a knowledge or example file, re-download and re-upload the changed file to your Project's Knowledge panel. There's no auto-sync. Watch the repo's commit history on GitHub for what changed.

## Troubleshooting

- **Claude is composing payloads without running `/metadata` first:** remind it that `04-runtime-schema-discovery.md` requires the schema burst before any write. Verify that file is uploaded.
- **Claude is using a version other than `v17.0`:** the repo convention is `v17.0` in every URL. Tell it to re-emit with `v17.0`.
- **Claude is URL-encoding `DE:` field names:** that's a `workfront-api` rule (`DE:Field Name` stays literal, no percent-encoding). Remind it.
- **Claude is drifting into text-mode authoring guidance:** the report skill defers all text-mode decisions to `workfront-textmode`. Ask Claude to stay in the reports lane and point you at the text-mode recipe if you need column-level guidance.
- **Clone flow: Claude is writing to source instead of destination:** the banner-every-step rule lives in `00-rubric-and-workflow.md` and `03-clone-and-adapt-recipe.md`. Stop the run, verify both files are uploaded, and re-confirm which host is the destination.
